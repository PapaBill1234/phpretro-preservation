#!/usr/bin/env python3
"""Offline real-SDK transport regression; HTTP and tool execution are replaced."""
from __future__ import annotations
import argparse
import importlib
import json
import logging
import os
from pathlib import Path
import secrets
import tempfile
import uuid
import warnings

os.environ.update(OPENHANDS_SUPPRESS_BANNER="1", OTEL_SDK_DISABLED="true")
logging.disable(logging.CRITICAL)
warnings.filterwarnings("ignore")
import runner
from litellm import ModelResponse
from litellm.types.llms.openai import ResponsesAPIResponse


def main(model):
    nonce = "SDK_TRANSPORT_" + secrets.token_hex(12)
    calls, pending, tool_calls = [], [], []
    module = importlib.import_module("openhands.sdk.llm.llm")
    runner.runtime_policy.ready = lambda model: True
    runner.runtime_policy.verified_providers = lambda model: ["a6api", "portdan"]
    runner.provider_credentials = lambda path: {"a6api": "synthetic", "portdan": {"openai": "synthetic", "deepseek": "synthetic"}}
    runner.time.sleep = lambda _: None

    class Box:
        def __init__(self, *args, **kwargs): pass
        def prepare(self): pass
        def close(self): pass
        def export(self): pass
        def execute(self, command, timeout):
            tool_calls.append(command)
            return 0, nonce
    runner.sandbox.Sandbox = Box

    with tempfile.TemporaryDirectory(prefix="phpretro-sdk-transport-") as td:
        root = Path(td)
        os.environ.update(HOME=td, OPENHANDS_PERSISTENCE_DIR=td)
        usage = root / "usage.json"

        def synthetic(**kwargs):
            calls.append(kwargs["api_base"])
            pending.append(json.loads(usage.read_text())["conservative_tokens"])
            if len(calls) in (2, 3):
                raise TimeoutError()
            tool_turn = len(calls) == 1
            arguments = json.dumps({"command": "synthetic-only", "timeout": 5, "summary": "synthetic tool output"})
            if model.startswith("deepseek-"):
                messages = kwargs["messages"]
                if not tool_turn:
                    assert any(nonce in str(m.get("content")) for m in messages if m["role"] == "tool"), "actual tool output lost"
                    assert any(m.get("reasoning_content") == "synthetic reasoning" for m in messages if m["role"] == "assistant"), "DeepSeek reasoning dropped"
                message = {"role": "assistant", "content": nonce if not tool_turn else None,
                           "reasoning_content": "synthetic reasoning"}
                if tool_turn:
                    message["tool_calls"] = [{"id": "call_synthetic", "type": "function",
                                              "function": {"name": "execute", "arguments": arguments}}]
                return ModelResponse(model=model, choices=[{"index": 0, "finish_reason": "tool_calls" if tool_turn else "stop", "message": message}],
                                     usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120})
            if not tool_turn:
                assert any(nonce in str(m.get("output")) for m in kwargs["input"] if m.get("type") == "function_call_output"), "actual tool output lost"
            output = ([{"type": "function_call", "id": "fc_synthetic", "call_id": "call_synthetic", "name": "execute", "arguments": arguments, "status": "completed"}]
                      if tool_turn else [{"type": "message", "id": "msg_synthetic", "role": "assistant", "status": "completed",
                                          "content": [{"type": "output_text", "text": nonce, "annotations": []}]}])
            return ResponsesAPIResponse.model_validate({"id": "resp_synthetic_" + str(len(calls)), "created_at": 1, "object": "response", "status": "completed",
                                                        "model": model, "output": output, "usage": {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}})

        module.litellm_completion = synthetic
        module.litellm_responses = synthetic
        prompt = root / "prompt.md"
        prompt.write_text("Run the execute tool once and return its result.")
        receipt = root / "receipt.json"
        receipt.write_text(json.dumps({"run_id": str(uuid.uuid4()), "status": "running", "model": model,
                                      "role": "builder", "cwd": td, "allowed_paths": [], "reserved_tokens": 300000,
                                      "prompt_path": str(prompt), "usage_path": str(usage)}))
        assert runner.main(receipt) == 0, "actual SDK conversation failed"
        recorded = json.loads(usage.read_text())
        assert calls == ["https://api.a6api.com/v1", "https://api.a6api.com/v1", "https://portdan.com/v1", "https://api.a6api.com/v1"], calls
        assert recorded["api_calls"] == 4 and recorded["total_tokens"] == 240, recorded
        assert recorded["usage_complete"] is False and recorded["conservative_tokens"] == 139504, recorded
        assert pending == [69632, 69752, 139384, 209016], pending
        assert runner.requests.bounded_tokens(recorded, 240) == 139504
        assert len(tool_calls) == 1, "reconnection replayed a completed tool action"
    print(json.dumps({"sdk_transport": "passed", "model": model, "http_calls": "synthetic-only"}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    main(ap.parse_args().model)
