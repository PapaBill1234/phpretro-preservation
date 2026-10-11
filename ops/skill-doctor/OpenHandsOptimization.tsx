import { ArrowRight, FileText, Info, RefreshCw, Undo2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { InlineNotice, PageHeading } from '../components/ui';
import { OpenHandsSessions } from './OpenHandsSessions';
import { OptimizationHeader, OptimizationSessionBar, OptimizationSteps } from './OptimizationLayout';
import { count, type RuntimeReport, type RuntimeSession } from './RuntimeDashboard';
import './optimizationWizard.css';

type Suggestion = { id: string; title: string; detail: string; available: boolean; enabled: boolean; reason: string; role: string };
type Session = RuntimeSession & { cost: { usd: number | null; basis: string }; suggestions: Suggestion[]; reasoning?: number | null; resources?: Array<{ name: string; kind: string; required: boolean; tokens: number | null }> };
type Operation = { id: string; target: string; enabled: boolean; status: string; created_at: number; session_id: string };
type Overview = { sessions: Session[]; settings: { revision: string; values: Record<string, boolean> }; operations: Operation[]; period_start: number; period_end: number; evidence: string };
type Preview = { id: string; confirmation: string; detail: string; before: boolean; enabled: boolean; scope: string };
type Verification = { status: string; reason: string; session_id?: string; measured_savings: null };
type View = 'current' | 'recommendations' | 'evidence';
const labels = ['Review session costs', 'Choose an optimization', 'Verify the result'];
const money = (value: number | null | undefined) => value == null ? 'Unknown' : '$' + value.toFixed(6);
const utc = (value: number | null | undefined) => value == null ? 'Unknown' : new Date(value * 1000).toLocaleString(undefined, { timeZone: 'UTC' });
const sum = (rows: Session[], field: 'tokens' | 'input' | 'cached' | 'cache_write' | 'output') => {
  const values = rows.map(row => row[field]).filter((value): value is number => value != null);
  return values.length ? values.reduce((total, value) => total + value, 0) : null;
};

async function request<T>(body: Record<string, unknown>, signal?: AbortSignal): Promise<T> {
  const response = await fetch('/api/runtime-optimization', { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin', body: JSON.stringify(body), signal });
  const value = await response.json();
  if (!response.ok) throw new Error(typeof value.error === 'string' ? value.error : `Optimization unavailable (HTTP ${response.status})`);
  return value;
}

export function OpenHandsOptimization({ runtime, view, setView, platform='all' }: { runtime?: { report: RuntimeReport | null; error: string; reload: () => void }; view: View; setView: (value: View) => void; platform?:'openhands'|'claude'|'all' }) {
  const agentLabel=platform==='claude'?'Claude Code':platform==='openhands'?'OpenHands':'Agent';
  const [data, setData] = useState<Overview>(), [error, setError] = useState(''), [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState('month'), [revision, setRevision] = useState(0);
  const [sessionId, setSessionId] = useState(() => new URLSearchParams(location.hash.split('?')[1] || '').get('session') || '');
  const [role, setRole] = useState('all'), [model, setModel] = useState('all'), [runtimeFilter, setRuntimeFilter] = useState('all');
  const [step, setStep] = useState(view === 'evidence' ? 3 : 2), [selected, setSelected] = useState('');
  const [preview, setPreview] = useState<Preview>(), [busy, setBusy] = useState(false);
  const [operation, setOperation] = useState<Operation>(), [verification, setVerification] = useState<Verification>();
  const [undoPending, setUndoPending] = useState(false), [exampleOpen, setExampleOpen] = useState(false);
  useEffect(() => {
    const controller = new AbortController(); setLoading(true); setError('');
    request<Overview>({ action: 'overview', period }, controller.signal).then(value => {
      if (!controller.signal.aborted) {
        setData(value);
        setOperation(previous => previous ? value.operations.find(item => item.id === previous.id) : value.operations.find(item => item.status === 'applied'));
      }
    }).catch(e => { if (!controller.signal.aborted) setError(e.message); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [period, revision, runtime?.report?.collected_at]);
  useEffect(() => { if (view === 'evidence') setStep(3); }, [view]);
  const platformRows=(data?.sessions || []).filter(s=>platform==='all'||s.runtime===(platform==='claude'?'claude-code':platform));
  const rows = platformRows.filter(s => (runtimeFilter === 'all' || s.runtime === runtimeFilter) && (role === 'all' || s.role === role) && (model === 'all' || s.model === model));
  const session = rows.find(s => s.id === sessionId) || rows[0];
  const options = (key: 'runtime' | 'role' | 'model') => [...new Set(platformRows.map(s => s[key] || 'Unknown'))].sort();
  const known = rows.filter(s => s.tokens != null), priced = rows.filter(s => s.cost.usd != null);
  const totalCost = priced.length ? priced.reduce((total, s) => total + s.cost.usd!, 0) : null;
  const suggestion = session?.suggestions.find(item => item.id === selected && item.available);
  const disabled = busy || loading || Boolean(error);
  const refresh = () => { setPreview(undefined); setRevision(value => value + 1); runtime?.reload(); };
  const go = (next: number) => { setStep(next); if (view !== 'recommendations') setView('recommendations'); };
  const clear = () => { setSelected(''); setPreview(undefined); setExampleOpen(false); };
  const select = (id: string) => { setSessionId(id); clear(); };
  async function action(work: () => Promise<void>) { setBusy(true); setError(''); try { await work(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); } }
  const toolbar = <OptimizationSessionBar>
    <div className="opt-period-switch" role="group" aria-label="Optimization period">{['month', 'week'].map(value => <button key={value} className={`button ghost compact ${period === value ? 'active' : ''}`} aria-pressed={period === value} disabled={busy || loading} onClick={() => { setPeriod(value); clear(); }}>This {value}</button>)}</div>
    <label><span className="sr-only">Session</span><select aria-label="Optimization session" value={session?.id || ''} disabled={busy || loading || !rows.length} onChange={e => select(e.target.value)}>
      {!rows.length && <option value="">{loading ? 'Loading sessions' : 'No sessions to analyze yet'}</option>}
      {rows.map(s => <option key={s.id} value={s.id}>{utc(s.started)} · {count(s.tokens)} Token · {money(s.cost.usd)} · {s.unit} · {s.role} · {s.status} · {s.id.slice(-6)}</option>)}
    </select></label>
    <button className="button ghost compact" aria-label="Reload optimization" disabled={busy || loading} onClick={refresh}><RefreshCw size={15} className={loading ? 'spin' : ''} /></button>
    <span className="opt-pricing-toggle" title="Configured quotes for recorded actual models; unknown prices stay unknown">Actual model quotes</span>
    {data && <small>This {period} · {utc(data.period_start)} – {utc(data.period_end)} UTC · all filtered sessions included</small>}
  </OptimizationSessionBar>;
  const filters = <details className="opt-limitations"><summary>Filter agent sessions</summary><div className="filter-row">{(['runtime', 'role', 'model'] as const).map(key => <label key={key}>{key}<select aria-label={`Optimization ${key}`} disabled={busy || loading} value={key === 'runtime' ? runtimeFilter : key === 'role' ? role : model} onChange={e => { (key === 'runtime' ? setRuntimeFilter : key === 'role' ? setRole : setModel)(e.target.value); clear(); }}><option value="all">All {key === 'runtime' ? 'runtimes' : key === 'role' ? 'roles' : 'models'}</option>{options(key).map(value => <option key={value}>{value}</option>)}</select></label>)}</div></details>;
  const evidence = <details className="opt-limitations"><summary>Data and verification evidence</summary><p>{data?.evidence}</p><OpenHandsSessions report={runtime?.report} error={runtime?.error} reload={runtime?.reload} view="evidence" selectedSessionId={session?.id} /></details>;
  const context = session && <>
    <div className="section-toolbar"><div><strong>Context actually observed</strong><small>{session.unit} · {session.role} · {session.model} · {session.status} · exit {session.rc ?? 'Unknown'}</small></div></div>
    <p className="muted">System and schema counts are SDK estimates. Required unit instructions are supplied explicitly; audit files on disk do not prove injection.</p>
    <div className="opt-table-wrap"><table><thead><tr><th>Resource</th><th>Type</th><th>First-request tokens</th><th>Control</th></tr></thead><tbody>{session.resources?.map(resource => <tr key={resource.name}><th>{resource.name}</th><td>{resource.kind}</td><td>{count(resource.tokens)}</td><td>{resource.required ? 'Required for this role' : 'Role-specific; inspect actual use'}</td></tr>)}</tbody></table></div>
    <p className="muted">Tool calls: {count(session.context.tool_calls)} · repeated commands: {count(session.context.repeated_commands)} · context coverage: {session.context_complete ? 'Complete' : 'Partial / unknown'}.</p>
    {session.unused_tools.length > 0 && <p>Observed unused tools: {session.unused_tools.join(', ')}. This observation does not establish that later builders can work without them.</p>}
  </>;
  return <section className={view === 'current' ? 'codex-current-context' : 'optimization-wizard runtime-optimization'} aria-label={`${agentLabel} optimization`}>
    {view === 'current' ? <>
      <PageHeading title="Current usage" subtitle={`Context observed in actual ${agentLabel} sessions, with coverage gaps shown explicitly.`} />
      <div className="codex-context-next"><div><strong>Reduce automatically injected context?</strong><p>Review session usage and the impact of supported changes before applying them.</p></div><button className="button primary" onClick={() => go(2)}>View optimization suggestions<ArrowRight size={16} /></button></div>
      <InlineNotice kind="info" title={session?.role==='interactive'?'Interactive context coverage is unknown':'Automatic agent skill catalog is disabled'}>{session?.role==='interactive'?'Interactive Claude sessions may load their own instructions and tools; transcript metadata does not prove their full context.':'The trusted runner isolates host skills, memories and plugins. Doctor\'s audit library is separate from agent injection. Required unit instructions and tools are recorded below.'}</InlineNotice>
      {toolbar}{filters}
    </> : <>
      <OptimizationHeader title="Optimization suggestions" subtitle="Understand the impact before changing settings." backLabel={step === 1 ? 'Back to suggestions' : 'Session costs'} onBack={() => go(step === 1 ? 2 : 1)} />
      <OptimizationSteps step={step} sessionPresent={Boolean(session)} labels={labels} onStep={go} />
      {toolbar}{filters}
    </>}
    {error && <div role="alert"><InlineNotice kind="danger" title="Action incomplete">{error}{data && ' Previously loaded evidence may be stale. Reload before applying a change.'}</InlineNotice></div>}
    {loading && <p role="status">Loading runtime optimization…</p>}
    {!loading && !error && !rows.length && <div className="opt-empty"><FileText size={32} /><h2>No sessions to analyze yet</h2><p>No retained runtime sessions match this period and these filters. This does not mean usage was zero.</p><button className="button primary" onClick={refresh}>Reload sessions</button></div>}
    {view === 'current' && context}
    {view !== 'current' && step === 1 && session && <div className="opt-cost">
      <h2>Period usage and cost</h2><p className="muted">Recorded usage across this {period}. Configured provider quote estimates cover known counters only; they are not a matched invoice or conservative ledger charge.</p>
      <div className="opt-period-total"><strong>Full-period total</strong><span>{rows.length} sessions · {known.length} with recorded tokens · {rows.filter(s => s.complete).length} with complete usage</span></div>
      <dl className="opt-cost-metrics"><div><dt>Total tokens</dt><dd>{count(sum(rows, 'tokens'))}</dd></div><div><dt>Input tokens, excluding cache</dt><dd>{count(sum(rows, 'input'))}</dd><small>Cache read: {count(sum(rows, 'cached'))}; cache write: {count(sum(rows, 'cache_write'))}; included in total</small></div><div><dt>Output tokens</dt><dd>{count(sum(rows, 'output'))}</dd><small>Includes reasoning where reported</small></div><div><dt>Provider quote estimate</dt><dd>{money(totalCost)}</dd><small>{priced.length} / {rows.length} priced sessions · partial when counters are unknown</small></div></dl>
      <div className="opt-table-wrap"><table><caption>Sessions in this period</caption><thead><tr><th>Session</th><th>Token</th><th>Provider quote estimate</th><th>Action</th></tr></thead><tbody>{rows.map(s => <tr key={s.id}><td>{utc(s.started)}<small>{s.unit} · {s.role} · {s.model} · {s.status} · {s.id.slice(-6)}</small></td><td>{count(s.tokens)}</td><td>{money(s.cost.usd)}</td><td><button className="button secondary compact" onClick={() => { select(s.id); go(2); }}>View suggestions<ArrowRight size={14} /></button></td></tr>)}</tbody></table></div>
      <details className="opt-limitations"><summary>Recorded session costs</summary><p>{session.unit} · {session.role} · {session.model} · {session.status} · exit {session.rc ?? 'Unknown'}</p><div className="opt-table-wrap"><table><tbody>{[['Recorded usage tokens', count(session.tokens)], ['Conservative usage bound', count(session.conservative_tokens)], ['Unknown API calls', count(session.unknown_requests)], ['Reasoning, included in output', count(session.reasoning)], ['Usage coverage', session.complete ? 'Complete' : 'Partial / unknown']].map(([name, value]) => <tr key={name}><th>{name}</th><td>{value}</td></tr>)}</tbody></table></div><p>{session.cost.basis}</p></details>
    </div>}
    {view !== 'current' && step === 2 && session && <div className="opt-select">
      <div className="opt-decision-grid"><div className="opt-options"><div className="opt-options-heading"><h2>Where would you like to start?</h2><Info size={17} aria-hidden="true" /></div>
        <fieldset className="opt-choices"><legend className="sr-only">Choose a supported optimization</legend>
          {session.suggestions.map(item => <div key={item.id} className={`opt-choice ${selected === item.id ? 'selected' : ''} ${!item.available ? 'unavailable' : ''}`}>
            <input id={`runtime-opt-${item.id}`} type="checkbox" aria-label={item.title} checked={selected === item.id} disabled={disabled || !item.available} onChange={() => { setSelected(selected === item.id ? '' : item.id); setPreview(undefined); }} />
            <label className="opt-choice-name" htmlFor={`runtime-opt-${item.id}`}>{item.title}</label><span className="opt-scope">Future SDK runs</span><span className="opt-off">{item.enabled ? 'Enabled' : 'Default'}</span>
          </div>)}
          {['Hide the automatic skill catalog', 'Stop injecting memories', 'Turn off Plugins'].map(title => <div className="opt-choice unavailable" key={title}><input type="checkbox" aria-label={title} disabled checked={false} readOnly /><label className="opt-choice-name">{title}</label><span className="opt-off">{session.role!=='interactive'&&['openhands','claude-code'].includes(session.runtime||'') ? 'Already isolated' : 'Runtime control unavailable'}</span></div>)}
        </fieldset><p className="opt-selection-meta">{suggestion ? 1 : 0} selected; one role-specific change at a time.</p><p className="opt-compact-note">Verify in a new SDK session. Existing conversations are unchanged.</p>
        {session.suggestions.map(item => <details className="opt-limitations" key={item.id}><summary>{item.title} · details</summary><p>{item.detail}</p><p>{item.reason}</p>{!item.available && <p>This SDK control does not apply to the selected runtime, role or model.</p>}</details>)}
      </div><div className="opt-impact"><section aria-label="Estimated savings across covered responses"><h3>Estimated savings across covered responses</h3><small>{rows.length} sessions in the selected period</small><div className="opt-savings-layout"><div className="opt-total-saving"><div className="opt-saving">— <span>Token</span></div><div className="opt-money">Cost not yet estimable</div></div><aside className="opt-first-saving"><small>Selected session · text estimate</small><strong>— Token</strong><small>Unknown / unmeasured</small></aside></div><small>{suggestion ? suggestion.detail : 'Choose a supported optimization to inspect its impact.'}</small><small>A profile change is not proof of savings. Future actual receipts establish adoption; matched comparisons establish savings.</small></section></div></div>
      <div className="opt-example-toggle"><button className="button ghost compact" aria-expanded={exampleOpen} onClick={() => setExampleOpen(!exampleOpen)}>Selected session context<ArrowRight size={15} /></button><small>Retained context estimates; missing transcripts stay unknown</small></div>{exampleOpen && <section className="opt-example">{context}</section>}
      {preview && <section className="opt-confirm" aria-label="Optimization preview"><h3>Review the proposed change</h3><p>{preview.detail}</p><p>{preview.before ? 'Enabled' : 'Default behavior'} → {preview.enabled ? 'Enabled' : 'Default behavior'} · {preview.scope}</p><p>Running agents keep their original settings. Required tools, full diff and review criteria remain protected.</p><button className="button primary" disabled={disabled} onClick={() => void action(async () => { setOperation(await request<Operation>({ action: 'apply', preview_id: preview.id, confirmation: preview.confirmation })); setVerification(undefined); setPreview(undefined); go(3); refresh(); })}>Apply to future SDK runs</button></section>}
      <div className="opt-actions"><button className="button primary" disabled={disabled || !suggestion} onClick={() => void action(async () => setPreview(await request<Preview>({ action: 'preview', session_id: session.id, target: suggestion!.id, enabled: !suggestion!.enabled })))}>Review change</button><button className="button secondary" disabled={busy} onClick={() => { setPreview(undefined); go(1); }}>Later</button></div>
    </div>}
    {view !== 'current' && step === 3 && <div className="opt-verification" aria-live="polite"><h2>{operation ? operation.status === 'restored' ? 'Change restored' : 'Verify the result' : 'No pending change'}</h2>
      <p>{operation ? 'Verification reads subsequent actual receipts. It does not start a model call, resume a parked unit or run Deep Scan.' : 'Choose a supported optimization, review its impact and confirm to begin verification.'}</p>
      {data?.operations.length ? <label className="field">Change<select aria-label="Optimization change" value={operation?.id || ''} disabled={busy} onChange={e => { setOperation(data.operations.find(item => item.id === e.target.value)); setVerification(undefined); setUndoPending(false); }}><option value="">Select a recorded change</option>{data.operations.map(item => <option key={item.id} value={item.id}>{utc(item.created_at)} · {item.target} · {item.status}</option>)}</select></label> : null}
      {operation && <><p>{operation.target} · {operation.status}</p>{operation.status !== 'restored' && <div className="opt-actions"><button className="button primary" disabled={busy} onClick={() => void action(async () => setVerification(await request<Verification>({ action: 'verify', operation_id: operation.id })))}>Check subsequent sessions</button><button className="button secondary" disabled={busy} onClick={() => setUndoPending(true)}><Undo2 size={17} />Undo this change</button></div>}
        {undoPending && <div className="opt-confirm"><p>Restore only this change if it still owns the setting? Other changes are retained.</p><button className="button secondary" disabled={busy} onClick={() => void action(async () => { setOperation(await request<Operation>({ action: 'undo', operation_id: operation.id, confirmation: operation.id })); setVerification(undefined); setUndoPending(false); refresh(); })}>Confirm undo</button><button className="button ghost" disabled={busy} onClick={() => setUndoPending(false)}>Cancel</button></div>}
      </>}
      {verification && <div className="opt-verification-result" role="status"><strong>{verification.status}</strong><p>{verification.reason}</p>{verification.session_id && <p>Observed session: {verification.session_id}</p>}<p>Measured savings: Unknown; different tasks are not a matched comparison.</p></div>}
      {!operation && <button className="button primary" onClick={() => go(2)}>Back to suggestions</button>}
    </div>}
    {view !== 'current' && <footer className="opt-footnote"><p>Analysis stays local. Known provider quotes are estimates; account billing remains separate and is not counted twice.</p>{evidence}<button className="button ghost compact" onClick={() => setView('current')}>Back to current context</button></footer>}
    {view === 'current' && evidence}
  </section>;
}
