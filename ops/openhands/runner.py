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
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import integrity as control
import runtime_policy
import sandbox
import routing
import request_accounting as requests
import context_usage
import session_journal

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
    for name in ("OPENAI_API_KEY", "A6API_API_KEY", "PORTDAN_API_KEY", "OPENROUTER_API_KEY"):
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
    routes = runtime_policy.verified_providers(model)
    if not routes:
        raise control.IntegrityError("model has no verified provider route")
    usage_path = Path(manifest["usage_path"])
    state = {"started": 0, "finished": 0, "depth": 0, "complete": False,
             "unknown_calls": 0, "providers": [], "failed": set(), "recoverable": set()}
    context = context_usage.Recorder(receipt_path.with_suffix('.context.json'))
    journal = session_journal.Journal(receipt_path.with_suffix('.session.json'),
        [routing.credential(credentials,p,model) for p in routes])
    box = sandbox.Sandbox(rid, manifest["cwd"], writable=manifest["role"] == "builder",
                          paths=manifest.get("allowed_paths", []))
    conversation = None
    final = []

    class BoundedLLM(LLM):
        _observer = PrivateAttr(default=None)

        def completion(self, *args, **kwargs):
            return routed_call(self, "completion", args, kwargs)

        def responses(self, *args, **kwargs):
            return routed_call(self, "responses", args, kwargs)

    options = dict(model=runtime_policy.sdk_model(model), api_mode=settings["api_mode"],
                     usage_id="agent", max_input_tokens=requests.MAX_INPUT, max_output_tokens=requests.MAX_OUTPUT,
                     num_retries=0, timeout=120, reasoning_effort="low", caching_prompt=False, log_completions=False,
                     input_cost_per_token=settings["input"] / 1e6,
                     output_cost_per_token=settings["output"] / 1e6)
    clients = {p: LLM(**options, api_key=SecretStr(routing.credential(credentials, p, model)),
                      base_url=policy["providers"][p]["base_url"]) for p in routes}
    llm = BoundedLLM(**options, api_key=SecretStr(routing.credential(credentials, routes[0], model)),
                     base_url=policy["providers"][routes[0]]["base_url"])

    def routed_call(owner, method, args, kwargs):
        def invoke(provider):
            client = clients[provider]
            client.restore_metrics(owner.metrics)
            with call_budget(args, kwargs, provider):
                result = getattr(client, method)(*args, **kwargs)
                verify_provider_response(result)
                return result
        return routing.call(routes, invoke, state["failed"], wait=reconnect_wait, recoverable=state["recoverable"])

    def reconnect_wait(seconds):
        # Preserve the same SDK conversation and sandbox while reconnecting.
        # No new message, builder attempt, receipt, deadline or allowance.
        for _ in range(seconds):
            if receipt_path.with_suffix(".cancel.json").exists():
                raise InterruptedError("run cancelled")
            time.sleep(1)

    def verify_provider_response(result):
        raw = result.raw_response
        reported = str(getattr(raw, "model", ""))
        if not runtime_policy.model_label_matches(model, reported) or getattr(raw, "usage", None) is None:
            raise control.IntegrityError("provider model identity or usage unavailable")

    def checkpoint(complete=False):
        data = normalized_usage(llm.metrics, settings, started=state["started"],
                                finished=state["finished"], complete=complete)
        data["api_calls"] = state["started"]
        if complete and state["started"] == 0:
            data.update(input_tokens=0, output_tokens=0, cache_read_tokens=0, cache_write_tokens=0,
                        total_tokens=0, usage_complete=True, accounting_source="not-launched")
        used = set(state["providers"])
        provider = "mixed:a6api-portdan" if len(used) > 1 else "custom:" + next(iter(used), routes[0])
        data.update(model=model, provider=provider, session_id=rid,
                    usage_schema=requests.SCHEMA, request_token_ceiling=requests.CALL_CEILING,
                    completed_api_calls=state["finished"], unknown_api_calls=state["started"] - state["finished"],
                    usage_known_calls=len(llm.metrics.token_usages),
                    conservative_tokens=data.get("total_tokens", 0) + (state["started"] - state["finished"]) * requests.CALL_CEILING)
        # Portdan Luna/DeepSeek prices have not been verified. Do not reuse A6 rates.
        if "portdan" in used and model != "gpt-6.1-sol":
            data["cost_status"] = "unknown-price"
        control.atomic_json(usage_path, data)
        return data

    @contextlib.contextmanager
    def call_budget(args, kwargs, provider):
        outer = state["depth"] == 0
        if outer:
            messages = args[0] if args else kwargs.get("messages", [])
            tools = args[1] if len(args) > 1 else kwargs.get("tools")
            if llm.get_token_count(messages, tools) > requests.MAX_INPUT:
                raise control.IntegrityError("context exceeds the reserved next-call ceiling")
            system = [m for m in messages if getattr(m,'role',None)=='system' or isinstance(m,dict) and m.get('role')=='system']
            context.request(llm.get_token_count(messages,tools),llm.get_token_count(messages,None),llm.get_token_count(system,None))
            usage = checkpoint(False)
            # Reserve maximum next-call context/output before starting it.
            if usage.get("conservative_tokens", 0) + requests.CALL_CEILING > manifest["reserved_tokens"]:
                raise control.IntegrityError("next inference would exceed the reserved allowance")
            if receipt_path.with_suffix(".cancel.json").exists():
                raise InterruptedError("run cancelled")
            state["started"] += 1
            state["providers"].append(provider)
            journal.add('provider_request','Request admitted',provider=provider,request=state['started'])
            checkpoint(False)  # Durable before the provider request can start.
        state["depth"] += 1
        try:
            yield
            if outer:
                state["finished"] += 1
        except Exception as exc:
            if outer:
                state["unknown_calls"] += 1
                journal.add('provider_error',type(exc).__name__,provider=provider,request=state['started'])
            raise
        finally:
            state["depth"] -= 1
            if outer:
                checkpoint(False)

    class ExecuteAction(Action):
        command: str = Field(max_length=20000, description="Shell command executed only in the disposable /repo container")
        timeout: int = Field(default=300, ge=1, le=1800)

    class ExecuteObservation(Observation):
        pass

    class ExecuteExecutor(ToolExecutor):
        def __call__(self, action, conversation=None):
            context.tool(action.command)
            rc, output = box.execute(action.command, action.timeout)
            context.data['tool_errors']+=int(rc!=0)
            context.save()
            journal.add('tool',action.command+'\n\n'+output,rc=rc)
            checkpoint(False)
            return ExecuteObservation.from_text("exit=" + str(rc) + "\n" + output, is_error=rc != 0)

    class ExecuteTool(ToolDefinition):
        @classmethod
        def create(cls, conv_state=None, **params):
            return [cls(description="Run shell commands and read/edit files in /repo. No host/network/secrets. Every command drains background processes. Git publication belongs to the controller.",
                        action_type=ExecuteAction, observation_type=ExecuteObservation, executor=ExecuteExecutor())]

    register_tool("PHPRetroExecute", ExecuteTool)

    def event_callback(event):
        context.data['events']+=1
        context.save()
        if isinstance(event, MessageEvent) and event.source == "agent":
            final[:] = ["".join(getattr(item, "text", "") for item in event.llm_message.content)]
            journal.add('assistant',final[-1])
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
                                    persistence_dir=None, visualizer=None, max_iteration_per_run=policy["max_iterations"])
        conversation.set_confirmation_policy(NeverConfirm())
        role = manifest["role"]
        brief = Path(manifest["prompt_path"]).read_text()
        context.data['brief_chars']=len(brief)
        context.save()
        if role == "reviewer":
            brief += "\nReturn exactly one JSON verdict: {\"verdict\":\"pass|fix|block\",\"findings\":[{\"severity\":\"blocker|minor\",\"file\":\"\",\"line\":0,\"issue\":\"\"}]}. Tools are read-only; do not run tests."
        conversation.send_message(brief + "\nTools see only /repo; use ExecuteTool for file reads and edits. Provider secrets, host files and publication tools are unavailable.")
        journal.add('brief',brief)
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
        print(json.dumps({"status": "provider unavailable" if routing.retryable(exc) else "failed",
                          "error_type": type(exc).__name__}), flush=True)
        rc = 1
    finally:
        context.finish(state['complete'])
        journal.add('result','Completed' if state['complete'] else 'Interrupted' if rc==130 else 'Failed',rc=rc)
        journal.finish(state['complete'])
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
