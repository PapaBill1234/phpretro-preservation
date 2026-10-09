import { useEffect, useState } from 'react';

type Session = {id:string;unit:string;role:string;model:string;provider:string;status:string;rc:number|null;started:number|null;tokens:number|null;cached:number|null;requests:number|null;complete:boolean;context_complete:boolean;context:Record<string,number|null>};
type Call = {request_id:string;created_at:number;model:string;input_tokens_including_cache:number;cache_read_tokens:number;output_tokens:number;billed_usd:number};
type Report = {sessions:Session[];provider_calls:Call[];billing_collected_at:number;billing_scope:string;evidence:string;session_limit:number};
const count=(v:number|null|undefined)=>v==null?'Unknown':v.toLocaleString();
const date=(v:number|null)=>v?new Date(v*1000).toLocaleString():'Unknown';
export function OpenHandsSessions(){
 const [report,setReport]=useState<Report|null>(null),[error,setError]=useState(''),[selected,setSelected]=useState(''),[role,setRole]=useState('all'),[model,setModel]=useState('all');
 const load=()=>{setError('');fetch('/api/openhands-sessions').then(async r=>{if(!r.ok)throw new Error(`Session evidence unavailable (HTTP ${r.status})`);setReport(await r.json());}).catch(e=>setError(e.message));};
 useEffect(load,[]);
 const rows=(report?.sessions||[]).filter(s=>(role==='all'||s.role===role)&&(model==='all'||s.model===model));
 const session=rows.find(s=>s.id===selected)||rows[0];
 return <section><h2>OpenHands sessions and A6API calls</h2><p>Builders, reviewers and failed runs from retained runtime receipts. Provider calls below are separate billing records.</p>
  <button className="button" onClick={load}>Reload sessions</button>{error&&<p role="alert">{error}</p>}
  <label className="field">Role<select value={role} onChange={e=>setRole(e.target.value)}><option value="all">All roles</option>{[...new Set(report?.sessions.map(s=>s.role))].map(r=><option key={r}>{r}</option>)}</select></label>
  <label className="field">Model<select value={model} onChange={e=>setModel(e.target.value)}><option value="all">All models</option>{[...new Set(report?.sessions.map(s=>s.model))].map(m=><option key={m}>{m}</option>)}</select></label>
  <label className="field">Session<select value={session?.id||''} onChange={e=>setSelected(e.target.value)}>{rows.map(s=><option key={s.id} value={s.id}>{date(s.started)} · {s.unit} · {s.role} · {s.model} · {s.status} · {s.id.slice(-8)}</option>)}</select></label>
  {report&&!rows.length&&<p>No retained OpenHands receipts match these filters.</p>}
  {session&&<><h3>{session.unit} · {session.role}</h3><p>{session.model} · {session.provider||'Provider not recorded'} · {session.status} · exit {session.rc??'pending'}</p><table><tbody>{[['Accounted tokens',count(session.tokens)],['Cache read tokens',count(session.cached)],['API calls',count(session.requests)],['Usage coverage',session.complete?'Complete':'Partial / unknown'],['Tool calls',count(session.context.tool_calls)],['Tool errors',count(session.context.tool_errors)],['Repeated commands',count(session.context.repeated_commands)],['Tool history coverage',session.context_complete?'Complete':'Partial / unknown']].map(([k,v])=><tr key={k}><th>{k}</th><td>{v}</td></tr>)}</tbody></table><h3>Optimization evidence</h3><p>{session.context_complete&&session.context.tool_calls===0?'The completed run recorded zero Execute tool calls. Review the tool schema overhead before changing the runtime.':'Only recorded counts support conclusions. Missing history does not establish unused tools or skills.'}</p>{!!session.context.repeated_commands&&<p>Repeated commands were observed. Inspect the run workflow before removing instructions.</p>}</>}
  <p>{report?.evidence} Latest {report?.session_limit} runtime sessions maximum.</p>
  <h3>A6API account calls</h3><p>Collected {date(report?.billing_collected_at||null)} · {report?.billing_scope}. These include other account callers within this window, not just builders. Refresh follows the billing timer.</p>
  <div style={{overflowX:'auto'}}><table><thead><tr><th>Time</th><th>Model</th><th>Input incl. cache</th><th>Cached</th><th>Output</th><th>Billed USD</th></tr></thead><tbody>{report?.provider_calls.map(c=><tr key={c.request_id}><td>{date(c.created_at)}</td><td>{c.model}</td><td>{count(c.input_tokens_including_cache)}</td><td>{count(c.cache_read_tokens)}</td><td>{count(c.output_tokens)}</td><td>{c.billed_usd.toFixed(6)}</td></tr>)}</tbody></table></div>
 </section>;
}
