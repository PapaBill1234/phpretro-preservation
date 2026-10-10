import {afterEach,expect,it,vi} from 'vitest';
import {loadOptimization} from '../../web/src/api';
afterEach(()=>vi.unstubAllGlobals());
it('shows string API errors instead of a generic status',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({error:'Open the UI for this project before optimizing it.'}),{status:400,statusText:'Error',headers:{'Content-Type':'application/json'}})));
 await expect(loadOptimization('/project')).rejects.toThrow('Open the UI for this project');
});
