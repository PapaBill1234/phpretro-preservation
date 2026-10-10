#!/usr/bin/env python3
"""Exercise the actual stdio MCP bridge and Docker sandbox, with no inference."""
import json,sys,tempfile,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import integrity as control,sandbox
from claude_code import tool_bridge

def main():
    root=Path(__file__).resolve().parents[2];rid=control.identity();box=sandbox.Sandbox(rid,root,writable=True)
    try:
        box.prepare()
        with tempfile.TemporaryDirectory(prefix='claude-bridge-') as folder:
            private=Path(folder);receipt=private/'receipt.json';secret=private/'host-only-sentinel';secret.write_text('never-visible')
            receipt.write_text(json.dumps({'run_id':rid,'runtime':'claude-code','role':'builder','status':'running',
              'cwd':str(root),'prepared_at':time.time(),'timeout':120}))
            def call(command):return tool_bridge.answer({'method':'tools/call','params':{'name':'execute','arguments':{'command':command,'timeout':10}}},receipt)
            answer=call("printf 'BRIDGE_ACCEPTED\\n'");payload=json.loads(answer['content'][0]['text'])
            assert payload['rc']==0 and payload['output'].strip()=='BRIDGE_ACCEPTED'
            answer=call('cat '+str(secret));assert answer['isError'] is True and 'never-visible' not in json.dumps(answer)
            receipt.with_suffix('.cancel.json').write_text('{}')
            try:call('echo should-not-run')
            except ValueError:pass
            else:raise AssertionError('Cancelled bridge remained executable')
    finally:box.close()
    sandbox.assert_absent(rid);print(json.dumps({'passed':True,'actual_bridge':True,'docker':True,'host_file_denied':True,'cancel_denied':True,'inference_calls':0}))
if __name__=='__main__':main()
