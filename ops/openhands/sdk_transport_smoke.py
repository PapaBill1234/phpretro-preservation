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
from unittest.mock import patch

os.environ.update(OPENHANDS_SUPPRESS_BANNER="1", OTEL_SDK_DISABLED="true")
logging.disable(logging.CRITICAL)
warnings.filterwarnings("ignore")
import runner
from litellm import ModelResponse
from litellm.types.llms.openai import ResponsesAPIResponse


def main(model, small_allowance=False, reviewer=False, optimized=False):
    nonce = "SDK_TRANSPORT_" + secrets.token_hex(12)
    reply = json.dumps({"verdict":"pass","findings":[]}) if reviewer else nonce
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
            return 0, nonce+('x'*20000)+nonce if optimized else nonce
    runner.sandbox.Sandbox = Box

    with tempfile.TemporaryDirectory(prefix="phpretro-sdk-transport-") as td:
        root = Path(td)
        os.environ.update(HOME=td, OPENHANDS_PERSISTENCE_DIR=td)
        os.environ.pop('PHPRETRO_OPS',None)
        profile={'revision':str(uuid.uuid4()),
                 'values':{'reviewer-thinking':optimized,'compact-tool-output':optimized},
                 'versions':{'reviewer-thinking':str(uuid.uuid4()) if optimized else None,
                             'compact-tool-output':str(uuid.uuid4()) if optimized else None}}
        profile_root=root/'phpretro-ops/state/runtime-optimization'
        profile_root.mkdir(mode=0o700,parents=True)
        runner.control.atomic_json(profile_root/'settings.json',profile)
        host_context='PRIVATE_HOST_CONTEXT_'+secrets.token_hex(12)
        (root/'SOUL.md').write_text(host_context)
        host_skill=root/'.openhands/skills/private-host/SKILL.md'
        host_skill.parent.mkdir(parents=True)
        host_skill.write_text('---\nname: private-host\ndescription: '+host_context+'\n---\n'+host_context)
        usage = root / "usage.json"

        def synthetic(**kwargs):
            assert host_context not in str(kwargs),'operator host context leaked into SDK transport'
            calls.append(kwargs["api_base"])
            pending.append(json.loads(usage.read_text())["conservative_tokens"])
            if reviewer:
                assert not kwargs.get('tools'), 'reviewer advertised execution tools'
                payload = str(kwargs.get('instructions', '')) + str(kwargs.get('messages', kwargs.get('input', [])))
                assert 'diff-only code reviewer' in str(payload), 'review contract missing on actual transport'
                assert 'use ExecuteTool' not in str(payload), 'builder instructions leaked into reviewer'
                if optimized and model.startswith('deepseek-'):
                    assert kwargs.get('extra_body',{}).get('thinking')=={'type':'disabled'},'direct-review control missing on actual SDK transport'
                    assert not kwargs.get('reasoning_effort'),'conflicting thinking effort on direct review'
            if not small_allowance and len(calls) in (2, 3):
                raise TimeoutError()
            tool_turn = len(calls) == 1 and not reviewer
            arguments = json.dumps({"command": "synthetic-only", "timeout": 5, "summary": "synthetic tool output"})
            if model.startswith("deepseek-"):
                messages = kwargs["messages"]
                if not tool_turn and not reviewer:
                    assert any(nonce in str(m.get("content")) for m in messages if m["role"] == "tool"), "actual tool output lost"
                    assert any(m.get("reasoning_content") == "synthetic reasoning" for m in messages if m["role"] == "assistant"), "DeepSeek reasoning dropped"
                    if optimized:
                        text=next(str(m.get('content')) for m in messages if m['role']=='tool')
                        assert 'truncated' in text and len(text)<9000,'optimized observation not bounded'
                message = {"role": "assistant", "content": reply if not tool_turn else None,
                           "reasoning_content": "synthetic reasoning"}
                if tool_turn:
                    message["tool_calls"] = [{"id": "call_synthetic", "type": "function",
                                              "function": {"name": "execute", "arguments": arguments}}]
                return ModelResponse(model=model, choices=[{"index": 0, "finish_reason": "tool_calls" if tool_turn else "stop", "message": message}],
                                     usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120,
                                            "completion_tokens_details":{"reasoning_tokens":0 if optimized and reviewer else 10}})
            if not tool_turn and not reviewer:
                assert any(nonce in str(m.get("output")) for m in kwargs["input"] if m.get("type") == "function_call_output"), "actual tool output lost"
                if optimized:
                    text=next(str(m['output']) for m in kwargs['input'] if m.get('type')=='function_call_output')
                    assert 'truncated' in text and len(text)<9000,'optimized observation not bounded'
            output = ([{"type": "function_call", "id": "fc_synthetic", "call_id": "call_synthetic", "name": "execute", "arguments": arguments, "status": "completed"}]
                      if tool_turn else [{"type": "message", "id": "msg_synthetic", "role": "assistant", "status": "completed",
                                          "content": [{"type": "output_text", "text": reply, "annotations": []}]}])
            return ResponsesAPIResponse.model_validate({"id": "resp_synthetic_" + str(len(calls)), "created_at": 1, "object": "response", "status": "completed",
                                                        "model": model, "output": output, "usage": {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}})

        module.litellm_completion = synthetic
        module.litellm_responses = synthetic
        prompt = root / "prompt.md"
        prompt.write_text("Review this supplied diff and acceptance. Exact reviewed head: synthetic-head." if reviewer
                          else "Run the execute tool once and return its result.")
        receipt = root / "receipt.json"
        run_id=str(uuid.uuid4())
        receipt.write_text(json.dumps({"run_id": run_id, "status": "running", "model": model,
                                      "role": "reviewer" if reviewer else "builder", "cwd": td, "allowed_paths": [], "reserved_tokens": 20000 if small_allowance else 300000,
                                      "prompt_path": str(prompt), "usage_path": str(usage)}))
        sdk=importlib.import_module('openhands.sdk');real_agent=sdk.Agent;constructed=[]
        def isolated_agent(*args,**kwargs):
            expected=root/(run_id+'-sdk')
            assert Path.home()==expected and Path(os.environ['OPENHANDS_PERSISTENCE_DIR'])==expected,'operator HOME was not isolated before SDK construction'
            constructed.append(True)
            return real_agent(*args,**kwargs)
        with patch.object(sdk,'Agent',new=isolated_agent):
            assert runner.main(receipt) == 0, "actual SDK conversation failed"
        assert constructed,'actual SDK Agent construction was not observed'
        journal=json.loads(receipt.with_suffix('.session.json').read_text())
        assert journal['schema']=='phpretro.session-journal.v1'
        assert reviewer or any(e['kind']=='tool' for e in journal['events']), 'tool timeline missing'
        assert small_allowance or any(e['kind']=='provider_error' for e in journal['events']), 'fallback failure timeline missing'
        assert all('synthetic-only' not in e['text'] for e in journal['events']), 'known credential was not redacted'
        recorded = json.loads(usage.read_text())
        ceiling = runner.requests.CALL_CEILING
        if reviewer:
            assert calls == ["https://api.a6api.com/v1"], calls
            assert recorded['api_calls'] == 1 and recorded['total_tokens'] == 120, recorded
            assert recorded['usage_complete'] is True and recorded['conservative_tokens'] == 120, recorded
            assert pending == [20000], pending
            assert tool_calls == [], 'diff-only reviewer executed a tool'
            assert not any(e['kind']=='tool' for e in journal['events']), 'fabricated reviewer tool timeline'
            final = next(e['text'] for e in journal['events'] if e['kind']=='assistant')
            assert json.loads(final) == {'verdict':'pass','findings':[]}, final
        elif small_allowance:
            assert calls == ["https://api.a6api.com/v1"] * 2, calls
            assert recorded["api_calls"] == 2 and recorded["total_tokens"] == 240, recorded
            assert recorded["usage_complete"] is True and recorded["conservative_tokens"] == 240, recorded
            assert pending == [20000, 20000], pending
            assert recorded["unknown_request_ceilings"] == []
            assert runner.requests.bounded_tokens(recorded, 240) == 240
        else:
            assert calls == ["https://api.a6api.com/v1", "https://api.a6api.com/v1", "https://portdan.com/v1", "https://api.a6api.com/v1"], calls
            assert recorded["api_calls"] == 4 and recorded["total_tokens"] == 240, recorded
            assert recorded["usage_complete"] is False and recorded["conservative_tokens"] == 240 + 2 * ceiling, recorded
            assert pending == [ceiling, ceiling + 120, 2 * ceiling + 120, 3 * ceiling + 120], pending
            assert runner.requests.bounded_tokens(recorded, 240) == 240 + 2 * ceiling
        assert len(tool_calls) == (0 if reviewer else 1), "unexpected or replayed tool action"
        history=runner.context_usage.summary(json.loads(receipt.with_suffix('.context.json').read_text()))
        assert history['tool_calls']==(0 if reviewer else 1) and history['tool_errors']==0 and history['usage_status']=='complete', history
        assert history['requests']==(1 if reviewer else 2 if small_allowance else 4) and history['unused_tools']==[],history
        assert nonce not in receipt.with_suffix('.context.json').read_text(), 'tool output leaked into metadata'
        metadata=json.loads(receipt.with_suffix('.context.json').read_text())
        assert metadata['optimization']==profile,'real operator profile lost when SDK isolated HOME'
        assert metadata['optimization']['values']['compact-tool-output']==optimized
        if optimized and not reviewer:
            assert metadata['truncated_observations']==1 and metadata['original_tool_output_chars']>metadata['sent_tool_output_chars']
        if optimized and reviewer and model.startswith('deepseek-'):
            assert metadata['reasoning_reports_complete'] and metadata['reported_reasoning_tokens']==0
    print(json.dumps({"sdk_transport": "passed", "model": model, "small_allowance":small_allowance,
                      "reviewer":reviewer,"optimized":optimized,"http_calls": "synthetic-only"}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    main(ap.parse_args().model)
    main(ap.parse_args().model, small_allowance=True)
    main(ap.parse_args().model, small_allowance=True, reviewer=True)
    main(ap.parse_args().model, small_allowance=True, optimized=True)
    main(ap.parse_args().model, small_allowance=True, reviewer=True, optimized=True)
