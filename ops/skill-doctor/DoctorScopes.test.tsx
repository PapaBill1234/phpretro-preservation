// @vitest-environment jsdom
import React from 'react';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
const api=vi.hoisted(()=>({getScanSources:vi.fn(),resetScanSources:vi.fn(),saveScanSources:vi.fn(),validateScanSources:vi.fn()}));
vi.mock('../../web/src/api',()=>api);
import {ScanPathsPage} from '../../web/src/pages/ScanPathsPage';
import {I18nProvider} from '../../web/src/i18n';
afterEach(()=>{cleanup();vi.clearAllMocks();});
it('switches OpenHands paths away from Codex and saves/rescans the selected scope',async()=>{
 const storage=new Map([['skill-doctor-locale','en-US']]);
 Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:(key:string)=>storage.get(key)??null,setItem:(key:string,value:string)=>storage.set(key,value),removeItem:(key:string)=>storage.delete(key)}});
 const workshop='/home/ubuntu/phpretro-skill-doctor/agents';
 const source={id:'openhands-project',platform:'openhands',scope:'project',resource:'skill',path:'.openhands/skills',resolvedPath:workshop+'/.openhands/skills',enabled:true,origin:'override',status:'exists'};
 api.getScanSources.mockImplementation(async projectDir=>({configPath:'/tmp/config',projectDir,sources:[source,{...source,id:'codex',platform:'codex'}]}));
 api.validateScanSources.mockResolvedValue({valid:true});api.saveScanSources.mockResolvedValue({sources:[source]});
 const saved=vi.fn().mockResolvedValue(undefined);
 render(<I18nProvider><ScanPathsPage platforms={['codex','openhands']} preferredPlatform="codex" projectDir="/home/ubuntu/phpretro-codex/work" setToast={()=>{}} onSaved={saved}/></I18nProvider>);
 await waitFor(()=>expect(api.getScanSources).toHaveBeenCalledWith('/home/ubuntu/phpretro-codex/work'));
 fireEvent.click(screen.getByRole('button',{name:'OpenHands'}));
 await waitFor(()=>expect(api.getScanSources).toHaveBeenCalledWith(workshop));
 expect(await screen.findByText(workshop+'/.openhands/skills')).toBeTruthy();
 expect(screen.getByText('Included in audit')).toBeTruthy();
 expect(screen.getByText(/not loaded into builders/)).toBeTruthy();
 fireEvent.click(screen.getByRole('button',{name:/Save.*rescan/i}));
 await waitFor(()=>expect(api.saveScanSources).toHaveBeenCalledWith(expect.any(Object),workshop));
 expect(saved).toHaveBeenCalledWith(true,{platform:'openhands',projectDir:workshop});
});
