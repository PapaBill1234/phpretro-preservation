// @vitest-environment jsdom
import React from 'react';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {mergeRuntimeSnapshot,RuntimeCoverage,type RuntimeReport} from '../../web/src/pages/RuntimeDashboard';
import {OpenHandsSessions} from '../../web/src/pages/OpenHandsSessions';
import type {DoctorSnapshot} from '../../src/application/types';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const session={id:'run',runtime:'openhands',unit:'F61',role:'reviewer',model:'sol',status:'running',started:1,tokens:20,cached:null,complete:false,context_complete:false,context:{tool_calls:2,tool_errors:1,repeated_commands:1},context_requests:[{estimated_context_tokens:20,estimated_tool_schema_tokens:3,estimated_system_tokens:5}],unused_tools:[],journal_available:true};
const issue={id:'runtime:tool-errors:run',kind:'context' as const,severity:'low' as const,title:'Tool executions returned errors',summary:'1 error',resourceIds:[],resourceNames:['openhands','F61','reviewer'],evidence:[{label:'Session',value:'run'}],runtime:'openhands',session_id:'run'};
const report:RuntimeReport={sessions:[session],provider_calls:[],billing_collected_at:1,billing_scope:'today',evidence:'Older history unknown',session_limit:500,collected_at:1,issues:[issue],runtimes:[{id:'openhands',label:'SDK',state:'running',sessions:1,source:'Receipts'}]};
it('merges live findings into issue counts and linked resources without mutating saved scans',()=>{
 const snapshot={resources:[{id:'resource',name:'reviewer-sol',platform:'openhands',issueIds:[],status:'healthy'}],issues:[],summary:{issues:0,high:0,medium:0,low:0}} as unknown as DoctorSnapshot;
 const merged=mergeRuntimeSnapshot(snapshot,report,'openhands')!;
 expect(merged.summary.low).toBe(1);expect(merged.issues[0].resourceIds).toEqual(['resource']);expect(merged.resources[0].issueIds).toEqual([issue.id]);
 expect(snapshot.issues).toEqual([]);expect(snapshot.resources[0].status).toBe('healthy');expect(mergeRuntimeSnapshot(snapshot,report,'codex')!.issues).toEqual([]);
});
it('shows runtime coverage and a redacted timeline with working filters and recommendations',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,json:async()=>({complete:false,truncated:true,events:[{kind:'tool',at:1,text:'synthetic output [redacted]',rc:1}]})}));
 const reload=vi.fn();render(<><RuntimeCoverage report={report} error="" reload={reload}/><OpenHandsSessions report={report} reload={reload} view="recommendations"/></>);
 expect(screen.getByText(/1 running/)).toBeTruthy();await screen.findByText('synthetic output [redacted]');expect(screen.getByText('Optimization evidence')).toBeTruthy();
 expect(screen.getByText(/bounded retention truncated/)).toBeTruthy();fireEvent.change(screen.getByLabelText('Find session'),{target:{value:'missing'}});
 expect(screen.getByText(/No retained agent sessions/)).toBeTruthy();fireEvent.change(screen.getByLabelText('Find session'),{target:{value:'F61'}});
 expect(screen.getByText('F61 · reviewer')).toBeTruthy();fireEvent.click(screen.getByRole('button',{name:'Reload sessions'}));expect(reload).toHaveBeenCalledOnce();
});
it('renders unknown billing prices and retains explicit collection errors',()=>{
 render(<OpenHandsSessions report={{...report,sessions:[],provider_calls:[{request_id:'call',created_at:null,model:'other',input_tokens_including_cache:null,cache_read_tokens:null,output_tokens:null,billed_usd:null}]}} error="HTTP 401"/>);
 expect(screen.getByRole('alert').textContent).toContain('HTTP 401');expect(screen.getAllByText('Unknown').length).toBeGreaterThan(0);
});
