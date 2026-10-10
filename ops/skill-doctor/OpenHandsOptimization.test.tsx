// @vitest-environment jsdom
import React from 'react';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {OpenHandsOptimization} from '../../web/src/pages/OpenHandsOptimization';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const row={id:'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',runtime:'openhands',unit:'F61',role:'reviewer',model:'deepseek-v4.1-flash',status:'failed',rc:1,started:1,tokens:17571,input:4771,cached:4608,output:8192,reasoning:8192,complete:false,context_complete:false,context:{},context_requests:[],unused_tools:[],cost:{usd:null,basis:'Unknown'},resources:[{name:'Full review diff',kind:'instructions',required:true,tokens:null}],suggestions:[{id:'reviewer-thinking',title:'Request a direct DeepSeek review verdict',role:'reviewer',available:true,enabled:false,detail:'Full diff remains required',reason:'Savings unmeasured'}]};
const overview={sessions:[row],period_start:1,period_end:2,settings:{revision:'default',values:{}},operations:[],evidence:'Missing counters remain unknown'};
function fake(){
 const calls:any[]=[];
 vi.stubGlobal('fetch',vi.fn(async(_url,init)=>{
  const body=JSON.parse(init?.body||'{}');calls.push(body);
  const response=body.action==='preview'?{id:'preview',confirmation:'confirm',before:false,enabled:true,detail:'Full diff remains required',scope:'Future SDK reviewers'}:
   body.action==='apply'?{id:'operation',target:'reviewer-thinking',enabled:true,status:'applied',created_at:2,session_id:row.id}:
   body.action==='verify'?{status:'pending',reason:'Waiting for a new session',measured_savings:null}:
   body.action==='undo'?{id:'operation',target:'reviewer-thinking',enabled:true,status:'restored',created_at:2,session_id:row.id}:overview;
  return {ok:true,json:async()=>response};
 }));return calls;
}
it('uses real runtime costs, failure outcome, required resources and period/model filters',async()=>{
 const calls=fake();const setView=vi.fn();render(<OpenHandsOptimization view="current" setView={setView}/>);
 await screen.findByText('Recorded session costs');expect(screen.getByText('Full review diff')).toBeTruthy();
 expect(screen.getAllByText(/F61 · reviewer · deepseek-v4.1-flash · failed/)).toHaveLength(2);
 expect(screen.getByText('Required for this role')).toBeTruthy();
 fireEvent.click(screen.getByRole('button',{name:'This week'}));await waitFor(()=>expect(calls.some(c=>c.period==='week')).toBe(true));
 fireEvent.click(screen.getByRole('button',{name:'Choose an optimization'}));expect(setView).toHaveBeenCalledWith('recommendations');
});
it('previews, applies, verifies and undoes through the runtime API, never Codex or inference',async()=>{
 const calls=fake();render(<OpenHandsOptimization view="recommendations" setView={()=>{}}/>);
 await screen.findByText('Recorded session costs');fireEvent.click(screen.getByRole('button',{name:'Choose an optimization'}));
 fireEvent.click(await screen.findByRole('button',{name:'Preview change'}));await screen.findByLabelText('Optimization preview');
 expect(calls.some(c=>c.action==='apply')).toBe(false);
 fireEvent.click(screen.getByRole('button',{name:'Apply to future SDK runs'}));await screen.findByRole('button',{name:'Check subsequent sessions'});
 fireEvent.click(screen.getByRole('button',{name:'Check subsequent sessions'}));await screen.findByText('Waiting for a new session');
 fireEvent.click(screen.getByRole('button',{name:'Undo this change'}));await waitFor(()=>expect(calls.some(c=>c.action==='undo')).toBe(true));
 expect(calls.map(c=>c.action)).toEqual(expect.arrayContaining(['overview','preview','apply','verify','undo']));
 expect(calls.some(c=>c.action==='scan'||c.action==='resume')).toBe(false);
});
it('reports API failure without claiming empty history',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,json:async()=>({error:'Sign in required'})}));
 render(<OpenHandsOptimization view="current" setView={()=>{}}/>);
 expect((await screen.findByRole('alert')).textContent).toContain('Sign in required');
 expect(screen.queryByText(/No retained runtime sessions/)).toBeNull();
});
it('renders empty history honestly and disables controls for native/Canvas sessions',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,json:async()=>({...overview,sessions:[]})}));
 const view=render(<OpenHandsOptimization view="current" setView={()=>{}}/>);
 await screen.findByText(/This does not mean usage was zero/);view.unmount();
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,json:async()=>({...overview,sessions:[{...row,runtime:'codex',suggestions:row.suggestions.map(s=>({...s,available:false}))}]})}));
 render(<OpenHandsOptimization view="recommendations" setView={()=>{}}/>);await screen.findByText('Recorded session costs');
 fireEvent.click(screen.getByRole('button',{name:'Choose an optimization'}));
 expect((screen.getByRole('button',{name:'Preview change'}) as HTMLButtonElement).disabled).toBe(true);
});
