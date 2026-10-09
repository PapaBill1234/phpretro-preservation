// @vitest-environment jsdom
import React from 'react';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {OpenHandsSessions} from '../../web/src/pages/OpenHandsSessions';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('renders runtime sessions, model filters and separate billed calls with partial history',async()=>{
 const session={id:'run-one',unit:'F61',role:'reviewer',model:'deepseek',provider:'a6api',status:'complete',rc:1,started:100,tokens:30,cached:10,requests:2,complete:false,context_complete:false,context:{tool_calls:null,tool_errors:null,repeated_commands:null},context_requests:[],unused_tools:[]};
 const fetch=vi.fn().mockResolvedValue({ok:true,json:async()=>({sessions:[session,{...session,id:'run-two',role:'builder',model:'sol'}],provider_calls:[{request_id:'call',created_at:100,model:'other-model',input_tokens_including_cache:100,cache_read_tokens:20,output_tokens:3,billed_usd:.001}],billing_collected_at:100,billing_scope:'all account keys, today',evidence:'No retained transcript',session_limit:500})});
 vi.stubGlobal('fetch',fetch);render(<OpenHandsSessions/>);
 await screen.findByText('F61 · reviewer');expect(screen.getAllByText('Partial / unknown')).toHaveLength(2);
 expect(screen.getByText('0.001000')).toBeTruthy();expect(screen.getByText('other-model')).toBeTruthy();
 fireEvent.change(screen.getByLabelText('Model'),{target:{value:'sol'}});
 expect(screen.getByText('F61 · builder')).toBeTruthy();
 fireEvent.click(screen.getByRole('button',{name:'Reload sessions'}));
 await waitFor(()=>expect(fetch).toHaveBeenCalledTimes(2));
 expect(fetch.mock.calls[0][0]).toBe('/api/openhands-sessions');
});
it('surfaces authentication/API failure instead of saying there are no sessions',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,status:401}));render(<OpenHandsSessions/>);
 expect((await screen.findByRole('alert')).textContent).toContain('HTTP 401');
});
