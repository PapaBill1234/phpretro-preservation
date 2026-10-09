#!/usr/bin/env python3
"""OpenHands inference on the trusted host; all agent tools run in Docker."""
from __future__ import annotations

import contextlib
import json
import logging
import os
from pathlib import Path
import signal
import stat
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import integrity as control
import runtime_policy
import sandbox

os.environ["OPENHANDS_SUPPRESS_BANNER"] = "1"
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["DO_NOT_TRACK"] = "1"


def provider_credentials(path):
    metadata = path.stat()
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise control.IntegrityError("provider source must be owned by the runner with mode 600")
    # The key is used only by trusted inference code. No tool receives it.
    return json.loads(path.read_text())


def normalized_usage(metrics, settings, *, started, finished, complete):
    usage = metrics.accumulated_token_usage
    if usage is None:
        return {"usage_complete": False, "runtime": "openhands", "accounting_source": "unknown"}
    prompt, output = int(usage.prompt_tokens), int(usage.completion_tokens)
    read, write = int(usage.cache_read_tokens), int(usage.cache_write_tokens)
    if settings["input_includes_cache"]:
        if read + write > prompt:
            raise control.IntegrityError("provider cache counters exceed prompt tokens")
        prompt -= read + write
    known = len(metrics.token_usages)
    return {"runtime": "openhands", "input_tokens": prompt, "output_tokens": output,
            "cache_read_tokens": read, "cache_write_tokens": write,
            "reasoning_tokens": int(usage.reasoning_tokens),
            "total_tokens": prompt + output + read + write, "api_calls": started,
            "usage_complete": bool(complete and started == finished == known),
            "input_includes_cache": False, "cost_status": "quoted-estimate",
            "accounting_source": "openhands-usage"}


def main(receipt_path):
    os.umask(0o077)
    manifest = json.loads(receipt_path.read_text())
    rid = manifest["run_id"]
    sandbox.container_name(rid)
    if receipt_path.with_suffix(".cancel.json").exists() or manifest.get("status") != "running":
        return 130
    policy = runtime_policy.load()
    model = manifest["model"]
    settings = runtime_policy.model_settings(model)
    if not runtime_policy.ready(model):
        return 75
    # SDK provider errors must not serialize request headers or credentials.
    logging.disable(logging.CRITICAL)
    private = receipt_path.parent / (rid + "-sdk")
    private.mkdir(mode=0o700)
    for name in ("OPENAI_API_KEY", "A6API_API_KEY", "OPENROUTER_API_KEY"):
        os.environ.pop(name, None)
    # Prevent auto-loading host SOUL/MCP/hooks/skills from an interactive home.
    os.environ["OPENHANDS_PERSISTENCE_DIR"] = str(private)
    os.environ["HOME"] = str(private)
    from pydantic import Field, PrivateAttr, SecretStr
    from openhands.sdk import Agent, Conversation, LLM
    from openhands.sdk.event import MessageEvent
    from openhands.sdk.security.confirmation_policy import NeverConfirm
    from openhands.sdk.tool import Action, Observation, Tool, ToolDefinition, ToolExecutor, register_tool
    credentials = provider_credentials(Path(policy["providers_file"]))
    # Provisioning formats are handled explicitly, without printing values.
    key = credentials.get("a6api_api_key") or credentials.get("A6API_API_KEY")
    nested = credentials.get("a6api")
    if isinstance(nested, dict):
        key = key or nested.get("api_key") or nested.get("key")
    elif isinstance(nested, str):
        key = key or nested
    if not isinstance(key, str) or not key:
        raise control.IntegrityError("A6API credential unavailable")
    usage_path = Path(manifest["usage_path"])
    state = {"started": 0, "finished": 0, "depth": 0, "complete": False}
    box = sandbox.Sandbox(rid, manifest["cwd"], writable=manifest["role"] == "builder",
                          paths=manifest.get("allowed_paths", []))
    conversation = None
    final = []

    class BoundedLLM(LLM):
        _observer = PrivateAttr(default=None)

        def completion(self, *args, **kwargs):
            with call_budget(args, kwargs):
                result = super().completion(*args, **kwargs)
                verify_provider_response(result)
                return result

        def responses(self, *args, **kwargs):
            with call_budget(args, kwargs):
                result = super().responses(*args, **kwargs)
                verify_provider_response(result)
                return result

    llm = BoundedLLM(model="openai/" + model, api_key=SecretStr(key),
                     base_url="https://api.a6api.com/v1", api_mode=settings["api_mode"],
                     usage_id="agent", max_input_tokens=65536, max_output_tokens=4096,
                     num_retries=0, caching_prompt=False, log_completions=False,
                     input_cost_per_token=settings["input"] / 1e6,
                     output_cost_per_token=settings["output"] / 1e6)

    def verify_provider_response(result):
        raw = result.raw_response
        reported = str(getattr(raw, "model", ""))
        if reported.removeprefix("openai/") != model or getattr(raw, "usage", None) is None:
            raise control.IntegrityError("provider model identity or usage unavailable")

    def checkpoint(complete=False):
        data = normalized_usage(llm.metrics, settings, started=state["started"],
                                finished=state["finished"], complete=complete)
        data["api_calls"] = state["started"]
        if complete and state["started"] == 0:
            data.update(input_tokens=0, output_tokens=0, cache_read_tokens=0, cache_write_tokens=0,
                        total_tokens=0, usage_complete=True, accounting_source="not-launched")
        data.update(model=model, provider="custom:a6api", session_id=rid)
        control.atomic_json(usage_path, data)
        return data

    @contextlib.contextmanager
    def call_budget(args, kwargs):
        outer = state["depth"] == 0
        if outer:
            messages = args[0] if args else kwargs.get("messages", [])
            tools = args[1] if len(args) > 1 else kwargs.get("tools")
            if llm.get_token_count(messages, tools) > 60000:
                raise control.IntegrityError("context exceeds the reserved next-call ceiling")
            usage = checkpoint(False)
            # Reserve maximum next-call context/output before starting it.
            if usage.get("total_tokens", 0) + 65536 + 4096 > manifest["reserved_tokens"]:
                raise control.IntegrityError("next inference would exceed the reserved allowance")
            if receipt_path.with_suffix(".cancel.json").exists():
                raise InterruptedError("run cancelled")
            state["started"] += 1
            checkpoint(False)  # Durable before the provider request can start.
        state["depth"] += 1
        try:
            yield
            if outer:
                state["finished"] += 1
        finally:
            state["depth"] -= 1
            if outer:
                checkpoint(False)

    class ExecuteAction(Action):
        command: str = Field(max_length=20000, description="Shell command executed only in the disposable /repo container")
        timeout: int = Field(default=300, ge=1, le=1800)

    class ExecuteExecutor(ToolExecutor):
        def __call__(self, action, conversation=None):
            rc, output = box.execute(action.command, action.timeout)
            checkpoint(False)
            return Observation.from_text("exit=" + str(rc) + "\n" + output, is_error=rc != 0)

    class ExecuteTool(ToolDefinition):
        @classmethod
        def create(cls, conv_state=None, **params):
            return [cls(description="Run shell commands and read/edit files in /repo. No host/network/secrets. Every command drains background processes. Git publication belongs to the controller.",
                        action_type=ExecuteAction, observation_type=Observation, executor=ExecuteExecutor())]

    register_tool("PHPRetroExecute", ExecuteTool)

    def event_callback(event):
        if isinstance(event, MessageEvent) and event.source == "agent":
            final[:] = ["".join(getattr(item, "text", "") for item in event.llm_message.content)]
        checkpoint(False)

    def interrupted(*args):
        raise InterruptedError("supervisor requested cancellation")

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    rc = 1
    checkpoint(False)
    try:
        box.prepare()
        agent = Agent(llm=llm, tools=[Tool(name="PHPRetroExecute")], include_default_tools=[])
        conversation = Conversation(agent=agent, workspace=str(private), callbacks=[event_callback],
                                    persistence_dir=None, max_iteration_per_run=policy["max_iterations"])
        conversation.set_confirmation_policy(NeverConfirm())
        role = manifest["role"]
        brief = Path(manifest["prompt_path"]).read_text()
        if role == "reviewer":
            brief += "\nReturn exactly one JSON verdict: {\"verdict\":\"pass|fix|block\",\"findings\":[{\"severity\":\"blocker|minor\",\"file\":\"\",\"line\":0,\"issue\":\"\"}]}. Tools are read-only; do not run tests."
        conversation.send_message(brief + "\nTools see only /repo; use ExecuteTool for file reads and edits. Provider secrets, host files and publication tools are unavailable.")
        conversation.run()
        if not final:
            raise control.IntegrityError("agent did not provide a final response")
        if role == "builder":
            box.export()
        print(final[-1][-16000:], flush=True)
        state["complete"] = True
        rc = 0
    except InterruptedError:
        rc = 130
    except Exception as exc:
        # Only a typed error is emitted; SDK exception strings may contain secrets.
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__}), flush=True)
        rc = 1
    finally:
        try:
            if conversation is not None:
                conversation.close()
        finally:
            try:
                checkpoint(state["complete"] or state["started"] == 0)
            finally:
                box.close()
                control.atomic_json(receipt_path.with_suffix(".sandbox.json"), {"run_id": rid, "drained": True})
    return rc


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1])))
