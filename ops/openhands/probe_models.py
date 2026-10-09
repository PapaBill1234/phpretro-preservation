#!/usr/bin/env python3
"""Explicit, bounded paid capability probes, with durable worker accounting."""
from __future__ import annotations
import argparse
import fcntl
import json
import logging
import os
import re
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import integrity as control
import runtime_policy


def run_probe(path):
    rec = json.loads(path.read_text())
    # No inference can occur before the measured request barrier below.
    control.atomic_json(Path(rec["usage_path"]), {"runtime":"openhands","model":rec["model"],
                        "provider":"custom:a6api","session_id":rec["run_id"],"api_calls":0,
                        "input_tokens":0,"output_tokens":0,"cache_read_tokens":0,"cache_write_tokens":0,
                        "total_tokens":0,"usage_complete":True,"accounting_source":"not-launched"})
    private = path.parent / (rec["run_id"] + "-sdk")
    private.mkdir(mode=0o700, exist_ok=True)
    os.environ.update(HOME=str(private), OPENHANDS_PERSISTENCE_DIR=str(private), OTEL_SDK_DISABLED="true", OPENHANDS_SUPPRESS_BANNER="1")
    logging.disable(logging.CRITICAL)
    from pydantic import SecretStr
    from openhands.sdk import Agent, Conversation, LLM
    from openhands.sdk.event import MessageEvent
    from openhands.sdk.security.confirmation_policy import NeverConfirm
    from openhands.sdk.tool import Action, Observation, Tool, ToolDefinition, ToolExecutor, register_tool
    from runner import provider_credentials, normalized_usage
    policy = runtime_policy.load()
    credentials = provider_credentials(Path(policy["providers_file"]))
    nested = credentials.get("a6api", {})
    key = credentials.get("a6api_api_key") or credentials.get("A6API_API_KEY") or (nested.get("api_key") or nested.get("key") if isinstance(nested, dict) else nested)
    if not isinstance(key, str) or not key:
        return 1
    model = rec["model"]
    settings = runtime_policy.model_settings(model)
    observed = {"started": 0, "finished": 0, "tool": False, "final": False, "identity": True}
    error = {}
    reported_models = set()
    class ProbeLLM(LLM):
        def completion(self, *args, **kwargs):
            return self.measured(super().completion, args, kwargs)
        def responses(self, *args, **kwargs):
            return self.measured(super().responses, args, kwargs)
        def measured(self, method, args, kwargs):
            if observed["started"] >= 4:
                raise control.IntegrityError("probe call limit")
            observed["started"] += 1
            checkpoint(False)
            result = method(*args, **kwargs)
            reported = str(getattr(result.raw_response, "model", "")).removeprefix("openai/")
            if re.fullmatch(r"[A-Za-z0-9_./-]{1,128}", reported):
                reported_models.add(reported)
            observed["identity"] &= reported == model
            if getattr(result.raw_response, "usage", None) is None:
                raise control.IntegrityError("provider usage absent")
            observed["finished"] += 1
            checkpoint(False)
            return result
    llm = ProbeLLM(model="openai/" + model, api_key=SecretStr(key), base_url="https://api.a6api.com/v1",
                   api_mode=settings["api_mode"], max_input_tokens=65536, max_output_tokens=512,
                   num_retries=0, caching_prompt=False, log_completions=False)
    def checkpoint(complete):
        usage = normalized_usage(llm.metrics, settings, started=observed["started"], finished=observed["finished"], complete=complete)
        usage["api_calls"] = observed["started"]
        if complete and observed["started"] == 0:
            usage.update(input_tokens=0,output_tokens=0,cache_read_tokens=0,cache_write_tokens=0,
                         total_tokens=0,usage_complete=True,accounting_source="not-launched")
        usage.update(model=model, provider="custom:a6api", session_id=rec["run_id"])
        control.atomic_json(Path(rec["usage_path"]), usage)
    class MarkerAction(Action):
        pass
    class MarkerExecutor(ToolExecutor):
        def __call__(self, action, conversation=None):
            observed["tool"] = True
            return Observation.from_text("PHPRETRO_OK")
    class MarkerTool(ToolDefinition):
        @classmethod
        def create(cls, conv_state=None, **params):
            return [cls(description="Return the fixed PHPRETRO_OK marker; no arguments or side effects.", action_type=MarkerAction, observation_type=Observation, executor=MarkerExecutor())]
    register_tool("PHPRetroMarker", MarkerTool)
    def callback(event):
        if isinstance(event, MessageEvent) and event.source == "agent":
            observed["final"] = "PHPRETRO_OK" in "".join(getattr(x, "text", "") for x in event.llm_message.content)
    conversation = None
    passed = False
    try:
        agent = Agent(llm=llm, tools=[Tool(name="PHPRetroMarker")], include_default_tools=[])
        conversation = Conversation(agent=agent, workspace=str(private), persistence_dir=None, callbacks=[callback], max_iteration_per_run=4)
        conversation.set_confirmation_policy(NeverConfirm())
        conversation.send_message("Call MarkerTool exactly once, then respond with exactly the marker returned by the tool.")
        conversation.run()
        passed = observed["tool"] and observed["final"] and observed["identity"]
    except Exception as exc:
        passed = False
        error = {"error_type": type(exc).__name__}
        status = getattr(exc, "status_code", None)
        if isinstance(status, int) and not isinstance(status, bool) and 100 <= status <= 599:
            error["http_status"] = status
    finally:
        try:
            if conversation is not None:
                conversation.close()
        finally:
            checkpoint(observed["started"] == observed["finished"])
    control.atomic_json(path.with_suffix(".capability.json"), {"tool_calls": bool(passed), "usage": normalized_usage(llm.metrics, settings, started=observed["started"], finished=observed["finished"], complete=True).get("usage_complete") is True,
                       "calls_started": observed["started"], "calls_finished": observed["finished"], **error})
    detail = json.loads(path.with_suffix(".capability.json").read_text())
    detail.update(marker_tool_executed=observed["tool"], final_marker=observed["final"],
                  model_identity=observed["identity"], reported_models=sorted(reported_models))
    control.atomic_json(path.with_suffix(".capability.json"), detail)
    return 0 if passed else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--paid-probes", action="store_true")
    ap.add_argument("--run", type=Path)
    args = ap.parse_args()
    if args.run:
        return run_probe(args.run)
    if not args.paid_probes:
        ap.error("--paid-probes explicitly starts paid calls")
    import orchestrator as o
    if not o.STOP_FILE.is_file():
        raise control.IntegrityError("probes require STOP")
    o.ensure_dirs()
    models = {}
    with (o.LOCK_DIR / "orchestrator.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = o.load_state()
        if state.get("reservations"):
            raise control.IntegrityError("settle previous runs before probing")
        for model, settings in runtime_policy.load()["models"].items():
            if not settings.get("automatic"):
                continue
            if state.get("tokens_today", 0) + 1000000 > o.DAILY_TOKEN_CAP:
                raise control.IntegrityError("probe allowance exceeds daily cap")
            rid = control.identity()
            reservation = {"record_type": "reservation", "run_id": rid, "unit": "", "role": "other", "reserved_tokens": 1000000, "ts_start": o.now()}
            control.append_record(o.STATE_DIR / "runs.jsonl", reservation)
            state.setdefault("reservations", {})[rid] = reservation
            control.atomic_json(o.STATE_JSON, state)
            receipt = o.STATE_DIR / "receipts" / (rid + ".json")
            usage = o.LOG_DIR / ("probe-" + rid + ".usage.json")
            record = dict(reservation, runtime="openhands", model=model, profile="probe", profile_home=str(receipt.parent / (rid + "-sdk")),
                          status="prepared", cwd=str(o.REPO), usage_path=str(usage), timeout=120, grace=o.TERM_GRACE,
                          unit_name="phpretro-run-" + rid + ".service", prepared_at=time.time(),
                          command=[runtime_policy.load()["sdk_python"], str(Path(__file__).resolve()), "--run", str(receipt)])
            control.atomic_json(receipt, record)
            with (o.LOG_DIR / ("probe-" + rid + ".log")).open("w") as log:
                subprocess.run([sys.executable, str(Path(o.__file__).with_name("worker.py")), str(receipt)], stdout=log, stderr=subprocess.STDOUT, check=False)
            done = o.completed_receipt(receipt, rid, state)
            normalized = o.accounted_usage(done.get("usage"))
            o.log_model_run("other", model, "", None, done["rc"], "other", normalized, run_id=rid, charged_tokens=normalized["accounted_tokens"])
            o.release_paid(state, rid)
            state["tokens_today"] += normalized["accounted_tokens"]
            control.atomic_json(o.STATE_JSON, state)
            result = o.read_json(receipt.with_suffix(".capability.json"), {})
            models[model] = {"tool_calls": done["rc"] == 0 and result.get("tool_calls") is True, "usage": result.get("usage") is True}
    control.atomic_json(o.STATE_DIR / "openhands-provider-evidence.json", {"capability_sha256": runtime_policy.capability_fingerprint(), "completed_at": time.time(), "models": models})
    print(json.dumps(models))
    return 0 if len(models) == 3 and all(all(row.values()) for row in models.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
