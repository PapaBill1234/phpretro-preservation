"""Apply the maintained source extension to pinned upstream, never edit built JS."""
import json,shutil,sys
from pathlib import Path
root=Path(sys.argv[1]); here=Path(__file__).parent
def replace(path,old,new):
    target=root/path; source=target.read_text()
    assert source.count(old)==1,(path,old)
    target.write_text(source.replace(old,new))
replace('src/types/skill.ts',"  | 'hermes'","  | 'hermes'\n  | 'openhands'")
replace('src/platforms/adapters/index.ts',"import { hermesAdapter } from './hermes';","import { hermesAdapter } from './hermes';\nimport { openhandsAdapter } from './openhands';")
replace('src/platforms/adapters/index.ts','  hermesAdapter,','  hermesAdapter,\n  openhandsAdapter,')
(root/'src/platforms/adapters/openhands.ts').write_text("""import { DEFAULT_SKILL_COST_POLICY } from '../defaults';
import type { PlatformAdapter } from '../types';
export const openhandsAdapter: PlatformAdapter = {
 platform: 'openhands', displayName: 'OpenHands', aliases: [], confidence: 'high',
 global: [{path:'~/.openhands/skills',mode:'recursive-dir',layout:'skill-dirs'}],
 project: [{path:'.openhands/skills',mode:'recursive-dir',layout:'skill-dirs'}],
 detectionPaths: {project:['ops/openhands/policy.json']},
 extensions:['.md'], installTargets:[], mcpConfigFiles:[], costPolicy:DEFAULT_SKILL_COST_POLICY,
};
""")
replace('web/src/App.tsx',"'openclaw','hermes','workbuddy'","'openclaw','hermes','openhands','workbuddy'")
replace('web/src/components/ui.tsx',"hermes: 'Hermes',","hermes: 'Hermes', openhands: 'OpenHands',")
replace('web/src/components/ui.tsx','<span className="platform-icon" style={style}>','<span aria-hidden="true" className="platform-icon" style={style}>')
replace('web/src/pages/ContextOptimizationPage.tsx',"import './contextOptimizationPage.css';","import './contextOptimizationPage.css';\nimport { OpenHandsSessions } from './OpenHandsSessions';")
replace('web/src/pages/ContextOptimizationPage.tsx',"  if (platform === 'codex')", "  if (platform === 'openhands') return active ? <OpenHandsSessions /> : null;\n\n  if (platform === 'codex')")
replace('web/src/pages/ContextOptimizationPage.tsx',"import { OpenHandsSessions } from './OpenHandsSessions';", "import { OpenHandsSessions } from './OpenHandsSessions';\nimport type { RuntimeReport } from './RuntimeDashboard';")
replace('web/src/pages/ContextOptimizationPage.tsx','  onToggle,\n}: {','  onToggle,\n  runtime,\n}: {')
replace('web/src/pages/ContextOptimizationPage.tsx','  active: boolean;','  runtime?: {report:RuntimeReport|null;error:string;reload:()=>void};\n  active: boolean;')
replace('web/src/pages/ContextOptimizationPage.tsx',"  if (platform === 'openhands') return active ? <OpenHandsSessions /> : null;", """  if (platform === 'openhands') return active ? <section>
    <nav className="context-optimization-tabs" role="tablist" aria-label="OpenHands context views">{tabs.map(tab=><button key={tab.id} role="tab" aria-selected={view===tab.id} onClick={()=>setView(tab.id)}><span>{tab.label}</span><small>{tab.detail}</small></button>)}</nav>
    <OpenHandsSessions report={runtime?.report} error={runtime?.error} reload={runtime?.reload} view={view}/>
    {view==='recommendations'&&<ContextPage active={active} snapshot={snapshot} openResource={openResource} onToggle={onToggle}/>}
  </section> : null;""")
replace('web/src/pages/ContextOptimizationPage.tsx','    <nav className="context-optimization-tabs" role="tablist" aria-label={t(\'context.views\')}>',"    {platform==='all'&&active&&<OpenHandsSessions report={runtime?.report} error={runtime?.error} reload={runtime?.reload} view={view}/>}\n    <nav className=\"context-optimization-tabs\" role=\"tablist\" aria-label={t('context.views')}>")
replace('web/src/App.tsx',"import { I18nProvider, useTranslation } from './i18n';", "import { I18nProvider, useTranslation } from './i18n';\nimport {useRuntimeReport,mergeRuntimeSnapshot,RuntimeCoverage} from './pages/RuntimeDashboard';\nimport './pages/runtimeDashboard.css';")
replace('web/src/App.tsx','const [snapshot, setSnapshot] = useState<DoctorSnapshot | null>(null);','const [scanSnapshot, setSnapshot] = useState<DoctorSnapshot | null>(null);')
replace('web/src/App.tsx','  const [scan, setScan] = useState<ScanState>',"  const runtime = useRuntimeReport();\n  const snapshot = useMemo(()=>mergeRuntimeSnapshot(scanSnapshot,runtime.report,scanOptions.platform),[scanSnapshot,runtime.report,scanOptions.platform]);\n  const [scan, setScan] = useState<ScanState>")
replace('web/src/App.tsx','const next = { ...scanOptions, platform };',"const next = { ...scanOptions, platform, projectDir: platform==='codex'?'/home/ubuntu/phpretro-codex/work':scanOptions.projectDir };")
replace('web/src/App.tsx','        <div className="page-container">',"""        {runtime.error&&<InlineNotice kind="warning" title="Runtime evidence unavailable">{runtime.error} Previously loaded runtime findings may be stale.</InlineNotice>}
        <div className="page-container">
          {['overview','resources','history'].includes(route)&&<RuntimeCoverage {...runtime}/>}
          {route==='issues'&&<p>Live runtime findings refresh every 15 seconds. Session coverage gaps appear under Info; click a runtime issue for evidence.</p>}""")
replace('web/src/App.tsx','<ContextOptimizationPageView active=', '<ContextOptimizationPageView runtime={runtime} active=')
replace('web/src/App.tsx','<select value={options.platform}',"<select aria-label={t('settings.platform')} value={options.platform}")
replace('web/src/App.tsx','<select value={props.analysisMode}',"<select aria-label={t('topbar.analysis')} value={props.analysisMode}")
replace('web/src/App.tsx',"{route === 'scan-paths' && <ScanPathsPageView", "{route === 'scan-paths' && <ScanPathsPageView projectDir={scanOptions.projectDir}")
replace('web/src/pages/ScanPathsPage.tsx','{ platforms, preferredPlatform, setToast, onSaved }','{ platforms, preferredPlatform, setToast, onSaved, projectDir }')
replace('web/src/pages/ScanPathsPage.tsx','{ platforms: Platform[];', '{ projectDir?:string; platforms: Platform[];')
replace('web/src/pages/ScanPathsPage.tsx','void getScanSources()', 'void getScanSources(projectDir)')
replace('web/src/pages/ScanPathsPage.tsx','  }, []);','  }, [projectDir]);')
replace('web/src/pages/ScanPathsPage.tsx','await saveScanSources(config)', 'await saveScanSources(config,projectDir)')
replace('web/src/pages/ScanPathsPage.tsx','await resetScanSources(active)', 'await resetScanSources(active,projectDir)')
replace('web/src/api.ts','getScanSources():','getScanSources(projectDir?:string):')
replace('web/src/api.ts',"return request('/api/scan-sources');", "return request('/api/scan-sources'+(projectDir?'?projectDir='+encodeURIComponent(projectDir):''));")
replace('web/src/api.ts','saveScanSources(scanSources: Record<string, AgentScanSourcesUserConfig>)', 'saveScanSources(scanSources: Record<string, AgentScanSourcesUserConfig>,projectDir?:string)')
replace('web/src/api.ts',"method: 'PUT', body: JSON.stringify({ scanSources }),", "method: 'PUT', body: JSON.stringify({ scanSources,projectDir }),")
replace('web/src/api.ts','resetScanSources(platform: Platform)', 'resetScanSources(platform: Platform,projectDir?:string)')
replace('web/src/api.ts',"method: 'POST', body: JSON.stringify({ platform }),", "method: 'POST', body: JSON.stringify({ platform,projectDir }),")
replace('src/ui-server/configHandlers.ts',"  if (request.method === 'GET' && url.pathname === '/api/scan-sources') {", "  if (request.method === 'GET' && url.pathname === '/api/scan-sources') {\n    const projectDir=url.searchParams.get('projectDir')||context.projectDir;")
replace('src/ui-server/configHandlers.ts','      sources: context.getScanSources(),','      sources: context.getScanSources(projectDir),')
replace('src/ui-server/configHandlers.ts',"    const projectDir=url.searchParams.get('projectDir')||context.projectDir;\n    sendJson(response, 200, {\n      projectDir: context.projectDir,", "    const projectDir=url.searchParams.get('projectDir')||context.projectDir;\n    sendJson(response, 200, {\n      projectDir,")
replace('src/ui-server/configHandlers.ts','saved: true, sources: context.getScanSources()','saved: true, sources: context.getScanSources(typeof body.projectDir===\'string\'?body.projectDir:undefined)')
replace('src/ui-server/configHandlers.ts','reset: true, sources: context.getScanSources()','reset: true, sources: context.getScanSources(typeof body.projectDir===\'string\'?body.projectDir:undefined)')
replace('web/src/App.tsx','try { setResourceDetail(await getResourceDetail(resource.id)); }',"try { const detail=await getResourceDetail(resource.id);setResourceDetail({...detail,issues:[...detail.issues,...(snapshot?.issues.filter(i=>i.id.startsWith('runtime:')&&i.resourceIds.includes(resource.id))||[])]}); }")
replace('web/src/pages/ManagePage.tsx','  return <section className="skill-library-page">',"  return <section className=\"skill-library-page\">{selectedAgent==='openhands'&&<div className=\"panel\"><h3>OpenHands audit resources</h3><p>The skill library can store audit resources. SDK instructions are compiled into controller-owned briefs; changing an active builder requires a reviewed source change. Audit snapshots are not deployment targets.</p></div>}")
replace('web/src/App.tsx','      {selectedIssue && <IssueDrawer',"""      {selectedIssue?.id.startsWith('runtime:')&&selectedIssue.evidence.find(e=>e.label==='Session')&&<div className="toast"><button className="button" onClick={()=>{
        const identity=selectedIssue.evidence.find(e=>e.label==='Session')!.value;setSelectedIssue(null);
        setScanOptions(current=>({...current,platform:'all'}));setContextView('evidence');setRoute('context');window.location.hash='/context?view=evidence&session='+encodeURIComponent(identity);
      }}>View this agent session</button></div>}
      {selectedIssue && <IssueDrawer""")
# Upstream's model settings were hard-coded in Chinese, even in English mode.
app=root/'web/src/App.tsx';text=app.read_text();before,fragment=text.split('function ModelServiceSettings',1)
fragment,after=fragment.split('function emptyModelServiceForm',1)
fragment=fragment.replace("  const [config, setConfig]", "  const {locale}=useTranslation();const label=(zh:string,en:string)=>locale==='zh-CN'?zh:en;\n  const [config, setConfig]",1)
fragment=fragment.replace("  const update = (next:", "  const {locale}=useTranslation();const label=(zh:string,en:string)=>locale==='zh-CN'?zh:en;\n  const update = (next:",1)
literal={
 '模型服务已保存。分析模型用于 AI 审计，嵌入模型用于语义冲突分析。':'Model services saved. Analysis supports AI auditing; embeddings support semantic conflict analysis.',
 '（已保存；留空则保留）':'(saved; leave empty to retain)', '（可选）':'(optional)',
 '输入新 Key 以替换':'Enter a new key to replace', '本地服务可留空':'Optional for a local service'}
for zh,en in literal.items():fragment=fragment.replace("'"+zh+"'",'label('+json.dumps(zh,ensure_ascii=False)+','+json.dumps(en)+')')
for zh,en in {'模型服务':'Model services','分析模型（/chat/completions）':'Analysis model (Sol uses Responses)','嵌入模型（/embeddings）':'Embedding model (/embeddings)'}.items():
 fragment=fragment.replace('title="'+zh+'"','title={label('+json.dumps(zh,ensure_ascii=False)+','+json.dumps(en)+')}')
for zh,en in {
 '模型服务':'Model services','使用 OpenAI-compatible API。云端模型与已运行的本地/局域网模型服务都填写 endpoint；本应用不会下载模型或启动推理引擎。':'Use an OpenAI-compatible endpoint. These settings apply to manual Doctor analysis, separate from builder routing.',
 '测试分析模型':'Test analysis model','测试嵌入模型':'Test embedding model','保存模型服务':'Save model services','模型名称':'Model name',
 '清除保存的 API Key':'Clear saved API key','保存后将不再发送 Authorization 请求头。':'Saving this removes the authorization header.',
 '请求超时（毫秒，可选）':'Request timeout (milliseconds, optional)'}.items():
 fragment=fragment.replace('>'+zh+'<','>{label('+json.dumps(zh,ensure_ascii=False)+','+json.dumps(en)+')}<')
app.write_text(before+'function ModelServiceSettings'+fragment+'function emptyModelServiceForm'+after)
replace('web/src/App.tsx','}保存模型服务</button>',"}{label('保存模型服务','Save model services')}</button>")
# Connection tests request five output tokens: high reasoning cannot fit inside
# that ceiling. Keep the real analysis path high; the tiny test uses no reasoning.
replace('src/models/testOpenAiCompatible.ts',"max_tokens: 5", "max_tokens: 512")
replace('src/audit/ai-scanner.ts','    if (!raw) continue;',"    if (!raw) throw new Error('AI audit did not return valid JSON for ' + skill.name + '; check provider status, timeout and output allowance.');")
shutil.copyfile(here/'OpenHandsSessions.tsx',root/'web/src/pages/OpenHandsSessions.tsx')
shutil.copyfile(here/'OpenHandsSessions.test.tsx',root/'tests/ui/OpenHandsSessions.test.tsx')
shutil.copyfile(here/'RuntimeDashboard.tsx',root/'web/src/pages/RuntimeDashboard.tsx')
shutil.copyfile(here/'runtimeDashboard.css',root/'web/src/pages/runtimeDashboard.css')
shutil.copyfile(here/'RuntimeDashboard.test.tsx',root/'tests/ui/RuntimeDashboard.test.tsx')
replace('tests/ui/App.test.tsx',"import { beforeEach, describe, expect, it, vi } from 'vitest';", "import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';\nafterEach(()=>{cleanup();vi.unstubAllGlobals();});")
replace('tests/ui/App.test.tsx',"expect(mocks.resetScanSources).toHaveBeenCalledWith('codex')", "expect(mocks.resetScanSources).toHaveBeenCalledWith('codex','/tmp/project')")
replace('tests/ui/App.test.tsx',"    vi.clearAllMocks();\n    mocks.loadOptimization", "    vi.clearAllMocks();\n    vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,json:async()=>({sessions:[],provider_calls:[],issues:[],runtimes:[]})}));\n    mocks.loadOptimization")
replace('tests/ui/App.test.tsx',"  it('keeps the fixed style controls independent of legacy theme preferences',", """  it('wires live OpenHands issues, resources, sessions and all context tabs into real pages',async()=>{
    localStorage.setItem('skill-doctor-locale','en-US');
    const runtimeIssue={id:'runtime:failed:run',kind:'context',severity:'med',title:'Agent run needs review',summary:'Failed reviewer',resourceIds:[],resourceNames:['openhands','F61','reviewer'],evidence:[{label:'Session',value:'run'}],runtime:'openhands',session_id:'run'};
    const resource={id:'openhands-brief',name:'reviewer-gpt-6.1-sol',kind:'skill',kindLabel:'Skill',sourcePath:'/tmp/project/.openhands/skills/reviewer/SKILL.md',platform:'openhands',scope:'project',shared:false,consumers:[{platform:'openhands',scope:'project'}],controllable:false,triggers:[],fixedTokens:10,activationTokens:0,issueIds:[],status:'healthy'};
    const agent={platform:'openhands',displayName:'OpenHands',projectDetected:true,globalDetected:true,recommended:true};
    const openSnapshot={...snapshot,target:{...snapshot.target,platform:'openhands'},resources:[resource],summary:{...snapshot.summary,resources:1,platforms:{openhands:1}}};
    const report={sessions:[{id:'run',runtime:'openhands',unit:'F61',role:'reviewer',model:'gpt-6.1-sol',status:'complete',rc:1,started:1,tokens:20,complete:false,context_complete:false,context:{},context_requests:[],unused_tools:[]}],provider_calls:[],issues:[runtimeIssue],runtimes:[{id:'openhands',label:'OpenHands SDK',state:'paused',sessions:1,source:'Receipts'}],evidence:'Missing older history stays unknown',session_limit:500};
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,json:async()=>report}));
    mocks.getBootstrap.mockResolvedValue({version:'test',projectDir:'/tmp/project',configPath:'/tmp/config',defaultScope:'all',supportedPlatforms:['openhands','codex'],detectedAgents:[agent],capabilities:snapshot.capabilities,registry:[],snapshot:openSnapshot});
    mocks.getResourceDetail.mockResolvedValue({resource,issues:[]});
    render(<App/>);
    await screen.findByText('Live agents and session coverage');
    fireEvent.click(screen.getByRole('button',{name:/^Issues/}));
    fireEvent.click(await screen.findByRole('button',{name:/Agent run needs review/}));
    expect(screen.getByText('run')).toBeTruthy();expect(screen.getByRole('button',{name:'View this agent session'})).toBeTruthy();
    fireEvent.keyDown(window,{key:'Escape'});
    fireEvent.click(screen.getByRole('button',{name:'Resources'}));
    fireEvent.click(await screen.findByRole('button',{name:/reviewer-gpt-6.1-sol/}));
    expect(await screen.findByRole('button',{name:/Agent run needs review/})).toBeTruthy();
    fireEvent.keyDown(window,{key:'Escape'});
    fireEvent.click(screen.getByRole('button',{name:'Optimization suggestions'}));
    await screen.findByText('Agent sessions and provider evidence');
    const tabs=screen.getAllByRole('tab');expect(tabs).toHaveLength(3);
    fireEvent.click(tabs[1]);expect(screen.getByText('Optimization evidence')).toBeTruthy();
    fireEvent.click(tabs[2]);expect(screen.getByText('A6API account calls')).toBeTruthy();
    fireEvent.click(screen.getByRole('button',{name:'Scan records'}));
    expect(await screen.findByRole('heading',{name:'Scan records'})).toBeTruthy();
  });

  it('keeps the fixed style controls independent of legacy theme preferences',""")
registry_test=root/'tests/platforms/registry.test.ts'
registry_test.write_text(registry_test.read_text().replace("      'hermes',", "      'hermes',\n      'openhands',"))
audit_test=root/'tests/audit/ai-scanner.test.ts'
text=audit_test.read_text()
old="""    const result = await runAiAudit(
      [makeSkill('skill', 'desc')],
      { llmOptions: makeLlmOptions(), useCache: false },
    );

    expect(result).toHaveLength(0);"""
assert text.count(old)==2
text=text.replace(old,"""    await expect(runAiAudit(
      [makeSkill('skill', 'desc')],
      { llmOptions: makeLlmOptions(), useCache: false },
    )).rejects.toThrow('AI audit did not return valid JSON');""")
text=text.replace("    const first = await runAiAudit(skills, { llmOptions: makeLlmOptions(), useCache: true, homeDir: dir });\n    expect(first).toHaveLength(0);", "    await expect(runAiAudit(skills, { llmOptions: makeLlmOptions(), useCache: true, homeDir: dir })).rejects.toThrow('AI audit did not return valid JSON');")
audit_test.write_text(text)
# Ship the extension's real discovery scenario, rather than skipping upstream's
# manifest check (the published source omits its internal scenario documents).
scenario=root/'doc/scenarios/phpretro-openhands'
(scenario/'evidence').mkdir(parents=True,exist_ok=True)
(scenario/'spec.md').write_text('OpenHands audit snapshots must be discovered under their own platform at global and project scope. They must not become Codex skills or writable deployment targets. Runtime receipt evidence remains separate from provider billing calls.\n')
(scenario/'tasks.md').write_text('Run npm test, typecheck:ui and build. Run the PHPRetro receipt privacy tests and manual preview Deep Scan. Verify OpenHands in scan settings and optimization sessions through the authenticated dashboard. Never count missing history as zero use.\n')
(scenario/'discovery.md').write_text('Create synthetic global/project .openhands/skills entries. Verify scope and canonical platform, no Codex records, and no installation target. See tests/platforms/openhands.test.ts.\n')
(scenario/'manifest.json').write_text(json.dumps({'feature':'phpretro-openhands','spec':'doc/scenarios/phpretro-openhands/spec.md','tasks':'doc/scenarios/phpretro-openhands/tasks.md','evidenceDir':'doc/scenarios/phpretro-openhands/evidence','scenarios':[{'id':'discovery','stage':'it','doc':'doc/scenarios/phpretro-openhands/discovery.md','test':'tests/platforms/openhands.test.ts'}]}))
(root/'tests/platforms/openhands.test.ts').write_text("""import {mkdtempSync,mkdirSync,writeFileSync,rmSync} from 'node:fs';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {expect,it} from 'vitest';
import {resolvePaths} from '../../src/discovery/resolvePaths';
import {getPlatformAdapter,normalizePlatformName} from '../../src/platforms/registry';
it('discovers OpenHands snapshots without Codex ownership or deployment writes',()=>{
 const root=mkdtempSync(join(tmpdir(),'openhands-fixture-')),home=join(root,'home'),project=join(root,'project');
 try {
  for(const base of [home,project]){const dir=join(base,'.openhands/skills/test');mkdirSync(dir,{recursive:true});writeFileSync(join(dir,'SKILL.md'),'---\\nname: test\\ndescription: Audit fixture\\n---\\nbody');}
  const rows=resolvePaths(project,{homeDir:home});
  expect(rows.filter(r=>r.platform==='openhands').map(r=>r.scope).sort()).toEqual(['global','project']);
  expect(rows.filter(r=>r.platform==='codex')).toHaveLength(0);
  expect(normalizePlatformName('openhands')).toBe('openhands');
  expect(getPlatformAdapter('openhands')?.installTargets).toEqual([]);
 } finally {rmSync(root,{recursive:true,force:true});}
});
""")
(root/'tests/ui-server/openhandsScope.test.ts').write_text("""import {mkdtempSync,mkdirSync,rmSync} from 'node:fs';
import {join} from 'node:path';import {tmpdir} from 'node:os';import {it,expect} from 'vitest';
import type {IncomingMessage,ServerResponse} from 'node:http';
import {handleConfigRoute} from '../../src/ui-server/configHandlers';
import {createApiRequestContext,type ApiServerContext} from '../../src/ui-server/apiContext';
it('resolves scan paths against the selected OpenHands workshop, not the server checkout',async()=>{
 const root=mkdtempSync(join(tmpdir(),'openhands-scope-')),home=join(root,'home'),controller=join(root,'controller'),workshop=join(root,'agents');
 try {mkdirSync(home,{recursive:true});mkdirSync(controller);mkdirSync(join(workshop,'.openhands/skills'),{recursive:true});
  const context=createApiRequestContext({projectDir:controller,homeDir:home,scans:{},benefits:{}} as unknown as ApiServerContext);
  let payload='';const response={setHeader:()=>{},writeHead:()=>{},end:(text:string)=>{payload=text;}} as unknown as ServerResponse;
  await handleConfigRoute({method:'GET'} as IncomingMessage,response,new URL('http://localhost/api/scan-sources?projectDir='+encodeURIComponent(workshop)),context);
  const data=JSON.parse(payload);expect(data.projectDir).toBe(workshop);
  const source=data.sources.find((s:{platform:string;scope:string})=>s.platform==='openhands'&&s.scope==='project');
  expect(source.status).toBe('exists');expect(source.resolvedPath).toBe(join(workshop,'.openhands/skills'));
 } finally {rmSync(root,{recursive:true,force:true});}
});
""")
