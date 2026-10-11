import {afterEach,expect,it,vi} from 'vitest';
import {loadOptimization,cancelScan,streamScan,ApiRequestError} from '../../web/src/api';
afterEach(()=>vi.unstubAllGlobals());
it('shows string API errors instead of a generic status',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({error:'Open the UI for this project before optimizing it.'}),{status:400,statusText:'Error',headers:{'Content-Type':'application/json'}})));
 await expect(loadOptimization('/project')).rejects.toThrow('Open the UI for this project');
});
it('normalizes structured errors without rendering object coercions',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({error:{message:{private:'not displayed'}}}),{status:502,headers:{'Content-Type':'application/json'}})));
 await expect(loadOptimization('/project')).rejects.toThrow('Request failed (HTTP 502)');
});
it('ignores an already completed scan but preserves a failed cancellation',async()=>{
 const response=(status:number)=>new Response(JSON.stringify({error:{message:'Scan not found.'}}),{status,headers:{'Content-Type':'application/json'}});
 vi.stubGlobal('fetch',vi.fn().mockResolvedValueOnce(response(404)).mockResolvedValueOnce(response(503)));
 await expect(cancelScan('completed')).resolves.toBeUndefined();
 await expect(cancelScan('active')).rejects.toBeInstanceOf(ApiRequestError);
});
it('normalizes structured scan-stream failures and closes the stream',()=>{
 const handlers={progress:vi.fn(),complete:vi.fn(),cancelled:vi.fn(),error:vi.fn()};
 let listener:((event:MessageEvent)=>void)|undefined;
 const close=vi.fn();
 class FakeSource {static CLOSED=2;readyState=1;close=close;addEventListener(name:string,fn:(e:MessageEvent)=>void){if(name==='error')listener=fn;}}
 vi.stubGlobal('EventSource',FakeSource);
 streamScan('fixture',handlers);
 listener!(new MessageEvent('error',{data:JSON.stringify({message:{message:'Scan cancelled'}})}));
 expect(handlers.error).toHaveBeenCalledWith(expect.objectContaining({message:'Scan cancelled'}));
 expect(close).toHaveBeenCalledOnce();
});
