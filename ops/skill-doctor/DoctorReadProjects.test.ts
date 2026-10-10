import {mkdtempSync,mkdirSync,rmSync} from 'node:fs';
import {join} from 'node:path';import {tmpdir} from 'node:os';import {Readable} from 'node:stream';
import type {IncomingMessage,ServerResponse} from 'node:http';
import {afterEach,expect,it,vi} from 'vitest';
vi.mock('../../src/context/optimization',()=>({optimizationOverview:vi.fn().mockResolvedValue({sessions:[{suggestions:[{available:true,canEnable:true}]}],diagnostics:[]}),applyOptimization:vi.fn(),previewOptimization:vi.fn(),undoOptimization:vi.fn(),verifyOptimization:vi.fn()}));
vi.mock('../../src/context/codexSkillCatalog',()=>({readCodexSkillCatalogs:vi.fn().mockResolvedValue({sessions:[],diagnostics:[]})}));
import {handleOptimizationRoute} from '../../src/ui-server/optimizationHandlers';
import type {ApiRequestContext} from '../../src/ui-server/apiContext';
afterEach(()=>vi.unstubAllEnvs());
it('admits allowlisted native history reads and rejects writes and unlisted projects',async()=>{
 const root=mkdtempSync(join(tmpdir(),'doctor-guard-'));const controller=join(root,'controller'),native=join(root,'native'),other=join(root,'other');
 try{for(const p of [controller,native,other])mkdirSync(p);vi.stubEnv('PHPRETRO_DOCTOR_READ_PROJECTS',JSON.stringify([native]));
  async function call(action:string,projectDir:string){let status=0,payload='';
   const request=Readable.from([JSON.stringify({action,projectDir})]);Object.assign(request,{method:'POST'});
   const response={setHeader:()=>{},writeHead:(code:number)=>{status=code;},end:(text:string)=>{payload=text;}} as unknown as ServerResponse;
   await handleOptimizationRoute(request as IncomingMessage,response,new URL('http://local/api/optimization'),{projectDir:controller,homeDir:root} as ApiRequestContext);
   return {status:response.statusCode||status,data:JSON.parse(payload)};
  }
  const read=await call('overview',native);expect(read.status).toBe(200);expect(read.data.sessions[0].suggestions[0].available).toBe(false);
  expect(read.data.sessions[0].suggestions[0].canEnable).toBe(false);
  expect(read.data.diagnostics[0]).toContain('read-only');
  expect((await call('skill-catalogs',native)).status).toBe(200);
  for(const action of ['preview','apply','verify','undo'])expect((await call(action,native)).status).toBe(400);
  expect((await call('overview',other)).status).toBe(400);
 }finally{rmSync(root,{recursive:true,force:true});}
});
