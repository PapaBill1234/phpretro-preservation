import {useEffect,useState} from 'react';
import {OpenHandsSessions} from './OpenHandsSessions';
import {count,date,type RuntimeReport,type RuntimeSession} from './RuntimeDashboard';
import './optimizationWizard.css';

type Suggestion={id:string;title:string;detail:string;available:boolean;enabled:boolean;reason:string;role:string};
type Session=RuntimeSession & {cost:{usd:number|null;basis:string};suggestions:Suggestion[];reasoning?:number|null;resources?:Array<{name:string;kind:string;required:boolean;tokens:number|null}>;optimization?:{revision:string}};
type Operation={id:string;target:string;enabled:boolean;status:string;created_at:number;session_id:string};
type Overview={sessions:Session[];settings:{revision:string;values:Record<string,boolean>};operations:Operation[];period_start:number;period_end:number;evidence:string};
type Preview={id:string;confirmation:string;detail:string;before:boolean;enabled:boolean;scope:string};
type Verification={status:string;reason:string;session_id?:string;measured_savings:null};

async function request<T>(body:Record<string,unknown>,signal?:AbortSignal):Promise<T>{
 const response=await fetch('/api/runtime-optimization',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify(body),signal});
 const value=await response.json();
 if(!response.ok)throw new Error(typeof value.error==='string'?value.error:`Optimization unavailable (HTTP ${response.status})`);
 return value;
}

export function OpenHandsOptimization({runtime,view,setView}:{runtime?:{report:RuntimeReport|null;error:string;reload:()=>void};view:'current'|'recommendations'|'evidence';setView:(value:'current'|'recommendations'|'evidence')=>void}){
 const [data,setData]=useState<Overview>(),[error,setError]=useState(''),[loading,setLoading]=useState(true),[period,setPeriod]=useState('month'),[revision,setRevision]=useState(0);
 const [sessionId,setSessionId]=useState(()=>new URLSearchParams(location.hash.split('?')[1]||'').get('session')||''),[role,setRole]=useState('all'),[model,setModel]=useState('all'),[runtimeFilter,setRuntimeFilter]=useState('all');
 const [step,setStep]=useState(1),[preview,setPreview]=useState<Preview>(),[busy,setBusy]=useState(false),[operation,setOperation]=useState<Operation>(),[verification,setVerification]=useState<Verification>();
 useEffect(()=>{
  const controller=new AbortController();setLoading(true);setError('');
  request<Overview>({action:'overview',period},controller.signal).then(value=>{if(!controller.signal.aborted)setData(value);}).catch(e=>{if(!controller.signal.aborted)setError(e.message);}).finally(()=>{if(!controller.signal.aborted)setLoading(false);});
  return()=>controller.abort();
 },[period,revision,runtime?.report?.collected_at]);
 const rows=(data?.sessions||[]).filter(s=>(runtimeFilter==='all'||s.runtime===runtimeFilter)&&(role==='all'||s.role===role)&&(model==='all'||s.model===model));
 const session=rows.find(s=>s.id===sessionId)||rows[0];
 const options=(key:'runtime'|'role'|'model')=>[...new Set(data?.sessions.map(s=>s[key]||'Unknown'))].sort();
 const known=rows.filter(s=>s.tokens!=null),priced=rows.filter(s=>s.cost.usd!=null);
 const total=known.reduce((sum,s)=>sum+s.tokens!,0),cost=priced.reduce((sum,s)=>sum+s.cost.usd!,0);
 const refresh=()=>{setRevision(v=>v+1);runtime?.reload();};
 async function action(work:()=>Promise<void>){setBusy(true);setError('');try{await work();}catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}}
 function select(id:string){setSessionId(id);setPreview(undefined);}
 return <section className="optimization-wizard runtime-optimization" aria-label="OpenHands optimization">
 <header className="opt-heading"><div><h1>{view==='current'?'Current usage · OpenHands':view==='evidence'?'Benefit basis · OpenHands':'Optimization suggestions · OpenHands'}</h1><p>Builders and reviewers use their actual SDK receipts and context observations.</p></div><button className="button" onClick={refresh} disabled={busy}>Reload optimization</button></header>
 <div className="runtime-filters">
 <div role="group" aria-label="Optimization period"><button className="button" aria-pressed={period==='month'} onClick={()=>setPeriod('month')}>This month</button><button className="button" aria-pressed={period==='week'} onClick={()=>setPeriod('week')}>This week</button></div>
 <label className="field">Runtime<select aria-label="Optimization runtime" value={runtimeFilter} onChange={e=>{setRuntimeFilter(e.target.value);setPreview(undefined);}}><option value="all">All runtimes</option>{options('runtime').map(v=><option key={v}>{v}</option>)}</select></label>
 <label className="field">Role<select aria-label="Optimization role" value={role} onChange={e=>{setRole(e.target.value);setPreview(undefined);}}><option value="all">All roles</option>{options('role').map(v=><option key={v}>{v}</option>)}</select></label>
 <label className="field">Model<select aria-label="Optimization model" value={model} onChange={e=>{setModel(e.target.value);setPreview(undefined);}}><option value="all">All models</option>{options('model').map(v=><option key={v}>{v}</option>)}</select></label>
 <label className="field">Session<select aria-label="Optimization session" value={session?.id||''} onChange={e=>select(e.target.value)}>{rows.map(s=><option key={s.id} value={s.id}>{date(s.started)} · {s.unit} · {s.role} · {s.model} · {s.status} · {s.id.slice(-8)}</option>)}</select></label></div>
 {data&&<p>{date(data.period_start)} – {date(data.period_end)} UTC · {rows.length} retained sessions · {known.length} with recorded tokens · {rows.filter(s=>s.complete).length} with complete usage</p>}
 {loading&&!data&&<p role="status">Loading runtime optimization…</p>}{error&&<p role="alert">{error}{data&&' Previously loaded evidence may be stale.'}</p>}
 {data&&!rows.length&&<p>No retained runtime sessions match this period and these filters. This does not mean usage was zero.</p>}
 {view==='recommendations'&&<nav className="opt-steps" aria-label="OpenHands optimization steps">{['Review session costs','Choose an optimization','Verify the result'].map((label,i)=><button key={label} className={'opt-step '+(step===i+1?'active':'')} aria-current={step===i+1?'step':undefined} onClick={()=>setStep(i+1)}><span className="opt-step-number">{i+1}</span><strong>{label}</strong></button>)}</nav>}
 {(view==='current'||view==='recommendations'&&step===1)&&session&&<>
 <h2>Recorded session costs</h2><p>{session.unit} · {session.role} · {session.model} · {session.status} · exit {session.rc??'Unknown'}</p>
 <div className="runtime-scroll"><table><tbody>{[['Recorded usage tokens',count(session.tokens)],['Conservative usage bound',count(session.conservative_tokens)],['Unknown API calls',count(session.unknown_requests)],['Input (excludes cache for SDK receipts)',count(session.input)],['Cache read',count(session.cached)],['Output (includes reasoning)',count(session.output)],['Reasoning, already included in output',count(session.reasoning)],['Selected quote estimate',session.cost.usd==null?'Unknown':`$${session.cost.usd.toFixed(6)}`],['Usage coverage',session.complete?'Complete':'Partial / unknown'],['Period recorded token subtotal',known.length?count(total):'Unknown'],['Period quote subtotal',priced.length?`$${cost.toFixed(6)} (${priced.length}/${rows.length} priced sessions)`:'Unknown']].map(([label,value])=><tr key={label}><th>{label}</th><td>{value}</td></tr>)}</tbody></table></div><p>{session.cost.basis}. Recorded usage is separate from conservative ledger charges. Cached tokens and provider billing are not added twice.</p>
 <button className="button primary" onClick={()=>{setView('recommendations');setStep(2);}}>Choose an optimization</button>
 </>}
 {view==='current'&&session&&<><h2>Context actually observed</h2><p>System and schema counts are SDK estimates. Instructions supplied with the unit are required; a file existing on disk does not prove injection.</p>
 <div className="runtime-scroll"><table><thead><tr><th>Resource</th><th>Type</th><th>First-request tokens</th><th>Control</th></tr></thead><tbody>{session.resources?.map(r=><tr key={r.name}><th>{r.name}</th><td>{r.kind}</td><td>{count(r.tokens)}</td><td>{r.required?'Required for this role':'Role-specific; inspect actual use'}</td></tr>)}</tbody></table></div>
 {session.runtime==='openhands'&&<p>Automatic SDK skill catalog: disabled by the trusted runner. Unit instructions are supplied explicitly. There is no evidence that every audit-library skill was injected.</p>}
 <p>Tool calls: {count(session.context.tool_calls)} · repeated commands: {count(session.context.repeated_commands)} · context coverage: {session.context_complete?'Complete':'Partial / unknown'}.</p>
 {session.unused_tools.length>0&&<p>Observed unused tools: {session.unused_tools.join(', ')}. One run does not establish that a later builder can work without them.</p>}
 <button className="button" onClick={()=>setView('evidence')}>View session evidence and timeline</button></>}
 {view==='recommendations'&&step===2&&session&&<><h2>Role-specific controls</h2><p>Manual changes apply only to future SDK runs. Provider routes, caps, required tools, the full diff and acceptance/security instructions remain protected.</p>
 {session.suggestions.map(s=><article className="panel" key={s.id}><h3>{s.title}</h3><p>{s.detail}</p><p>{s.reason}</p><p>Current setting: {s.enabled?'Enabled':'Default behavior'} · savings: Unknown / unmeasured</p><button className="button" disabled={busy||!s.available} onClick={()=>void action(async()=>{setPreview(await request<Preview>({action:'preview',session_id:session.id,target:s.id,enabled:!s.enabled}));})}>{s.enabled?'Preview restore':'Preview change'}</button>{!s.available&&<p>This SDK control does not apply to the selected runtime/role/model.</p>}</article>)}
 {preview&&<section className="panel" aria-label="Optimization preview"><h3>Review the proposed change</h3><p>{preview.detail}</p><p>{preview.before?'Enabled':'Default behavior'} → {preview.enabled?'Enabled':'Default behavior'} · {preview.scope}</p><p>Estimated and measured token savings: Unknown. Running agents keep their original settings.</p><button className="button primary" disabled={busy} onClick={()=>void action(async()=>{const next=await request<Operation>({action:'apply',preview_id:preview.id,confirmation:preview.confirmation});setOperation(next);setVerification(undefined);setPreview(undefined);setStep(3);refresh();})}>Apply to future SDK runs</button></section>}
 </>}
 {view==='recommendations'&&step===3&&<section><h2>Verify the result</h2><p>Verification reads subsequent receipts. It does not start a model call, resume a parked unit or run Deep Scan.</p>
 {data?.operations.length? <label className="field">Change<select aria-label="Optimization change" value={operation?.id||''} onChange={e=>{setOperation(data.operations.find(o=>o.id===e.target.value));setVerification(undefined);}}><option value="">Select a recorded change</option>{data.operations.map(o=><option key={o.id} value={o.id}>{date(o.created_at)} · {o.target} · {o.enabled?'enabled':'default'} · {o.status}</option>)}</select></label>:<p>No SDK efficiency changes have been applied. Choose an optimization first.</p>}
 {operation&&<><p>{operation.target} · {operation.status}</p><button className="button" disabled={busy} onClick={()=>void action(async()=>setVerification(await request<Verification>({action:'verify',operation_id:operation.id})))}>Check subsequent sessions</button><button className="button" disabled={busy||operation.status==='restored'} onClick={()=>void action(async()=>{setOperation(await request<Operation>({action:'undo',operation_id:operation.id,confirmation:operation.id}));setVerification(undefined);refresh();})}>Undo this change</button></>}
 {verification&&<div role="status"><strong>{verification.status}</strong><p>{verification.reason}</p>{verification.session_id&&<p>Observed session: {verification.session_id}</p>}<p>Measured savings: Unknown; different tasks are not a matched comparison.</p></div>}
 </section>}
 {view==='evidence'&&<><h2>Verification history</h2>{data?.operations.map(o=><p key={o.id}>{date(o.created_at)} · {o.target} · {o.status} <button className="button" onClick={()=>{setOperation(o);setVerification(undefined);setView('recommendations');setStep(3);}}>Verify / undo</button></p>)}<OpenHandsSessions report={runtime?.report} error={runtime?.error} reload={runtime?.reload} view="evidence" selectedSessionId={session?.id}/></>}
 <p>{data?.evidence}</p>
 </section>;
}
