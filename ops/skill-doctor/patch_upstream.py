"""Apply the maintained source extension to pinned upstream, never edit built JS."""
import shutil,sys
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
replace('web/src/pages/ContextOptimizationPage.tsx',"import './contextOptimizationPage.css';","import './contextOptimizationPage.css';\nimport { OpenHandsSessions } from './OpenHandsSessions';")
replace('web/src/pages/ContextOptimizationPage.tsx',"  if (platform === 'codex')", "  if (platform === 'openhands') return active ? <OpenHandsSessions /> : null;\n\n  if (platform === 'codex')")
# Connection tests request five output tokens: high reasoning cannot fit inside
# that ceiling. Keep the real analysis path high; the tiny test uses no reasoning.
replace('src/models/testOpenAiCompatible.ts',"max_tokens: 5", "max_tokens: 512")
replace('src/audit/ai-scanner.ts','    if (!raw) continue;',"    if (!raw) throw new Error('AI audit did not return valid JSON for ' + skill.name + '; check provider status, timeout and output allowance.');")
shutil.copyfile(here/'OpenHandsSessions.tsx',root/'web/src/pages/OpenHandsSessions.tsx')
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
