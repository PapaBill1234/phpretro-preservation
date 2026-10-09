import {useCallback,useEffect,useState} from 'react';
import type {DoctorSnapshot,UiIssue} from '../../../src/application/types';
export type RuntimeSession={id:string;runtime?:string;unit:string;unit_state?:string;role:string;model:string;provider?:string;status:string;rc?:number|null;started:number|null;ended?:number|null;tokens:number|null;input?:number|null;output?:number|null;cached:number|null;requests?:number|null;complete:boolean;context_complete:boolean;context:Record<string,number|null>;context_requests:Array<{estimated_context_tokens:number;estimated_tool_schema_tokens:number;estimated_system_tokens:number}>;unused_tools:string[];journal_available?:boolean;action?:string;skills?:{activated:string[];invoked:string[]};session_url?:string};
export type RuntimeReport={sessions:RuntimeSession[];provider_calls:Array<{request_id:string;created_at:number|null;model:string;input_tokens_including_cache:number|null;cache_read_tokens:number|null;output_tokens:number|null;billed_usd:number|null}>;billing_collected_at:number|null;billing_scope:string;evidence:string;session_limit:number;collected_at?:number;runtimes?:Array<{id:string;label:string;state:string;sessions:number|null;source:string}>;issues?:Array<UiIssue & {runtime:string;session_id:string|null}>};
export const count=(v:number|null|undefined)=>v==null?'Unknown':v.toLocaleString();
export const date=(v:number|null|undefined)=>v?new Date(v*1000).toLocaleString():'Unknown';
export function useRuntimeReport(enabled=true){
 const [report,setReport]=useState<RuntimeReport|null>(null),[error,setError]=useState(''),[version,setVersion]=useState(0);
 const reload=useCallback(()=>setVersion(v=>v+1),[]);
 useEffect(()=>{
  if(!enabled)return;
  let alive=true,request:AbortController|null=null;
  const load=async()=>{
   request?.abort();request=new AbortController();
   try{const response=await fetch('/api/openhands-sessions',{signal:request.signal});
    if(!response.ok)throw new Error(`Session evidence unavailable (HTTP ${response.status})`);
    const data=await response.json();if(!Array.isArray(data.sessions)||!Array.isArray(data.provider_calls))throw new Error('Invalid runtime evidence');
    if(alive){setReport(data);setError('');}
   }catch(e){if(alive&&!(e instanceof DOMException&&e.name==='AbortError'))setError(e instanceof Error?e.message:String(e));}
  };
  void load();const timer=window.setInterval(()=>{if(document.visibilityState==='visible')void load();},15000);
  return()=>{alive=false;request?.abort();window.clearInterval(timer);};
 },[enabled,version]);
 return {report,error,reload};
}
export function mergeRuntimeSnapshot(snapshot:DoctorSnapshot|null,report:RuntimeReport|null,platform:string):DoctorSnapshot|null{
 if(!report)return snapshot;
 // Live failures must remain visible while a static scan is pending, cancelled
 // or unavailable. This temporary view is explicit and never saved as a scan.
 if(!snapshot)snapshot={id:'runtime-only',generatedAt:new Date((report.collected_at||Date.now()/1000)*1000).toISOString(),durationMs:0,status:'partial',
  target:{projectDir:'',scope:'all',platform:platform==='all'?null:platform as DoctorSnapshot['target']['platform']},
  summary:{resources:0,issues:0,high:0,medium:0,low:0,conflicts:0,duplicates:0,security:0,fixedTokens:0,activationTokens:0,disabledResources:0,platforms:{},scopes:{}},
  resources:[],issues:[],skills:[],conflicts:[],audit:{scanned:0,findings:[],aiFindings:[],summary:{high:0,med:0,low:0}},
  warnings:[{id:'static-pending',phase:'discovering',code:'static-scan-pending',message:'Live runtime evidence is available; static resource scanning is pending or unavailable.',recoverable:true}],
  capabilities:{aiAuditConfigured:false,embeddingConfigured:false,canToggleCodexResources:false,canExecuteCleanup:false,canInstall:false,canUninstall:false,canExportDashboard:false}};
 const additional=(report.issues||[]).filter(i=>platform==='all'||i.runtime===platform||i.runtime==='all').map(issue=>{
  const session=report.sessions.find(s=>s.id===issue.session_id);
  const resources=snapshot.resources.filter(r=>r.platform==='openhands'&&session?.runtime==='openhands'&&r.name.includes(session.role)&&r.name.includes(session.model));
  return {...issue,resourceIds:resources.map(r=>r.id),resourceNames:resources.length?resources.map(r=>r.name):issue.resourceNames};
 });
 const issues=[...snapshot.issues.filter(i=>!i.id.startsWith('runtime:')),...additional];
 return {...snapshot,issues,resources:snapshot.resources.map(r=>({...r,issueIds:[...r.issueIds,...additional.filter(i=>i.resourceIds.includes(r.id)).map(i=>i.id)],status:additional.some(i=>i.resourceIds.includes(r.id)&&i.severity!=='info')?'attention':r.status})),
  summary:{...snapshot.summary,issues:issues.length,high:issues.filter(i=>i.severity==='high').length,medium:issues.filter(i=>i.severity==='med').length,low:issues.filter(i=>i.severity==='low').length}};
}
export function RuntimeCoverage({report,error,reload}:{report:RuntimeReport|null;error:string;reload:()=>void}){
 return <section className="panel" aria-label="Runtime coverage"><div className="panel-heading"><div><h3>Live agents and session coverage</h3><p>Refreshes every 15 seconds while this page is visible. Local metadata collection uses no inference.</p></div><button className="button" onClick={reload}>Refresh runtime evidence</button></div>
 {error&&<p role="alert">{error} Previously loaded evidence may be stale.</p>}
 {!report&&!error&&<p>Loading runtime evidence…</p>}
 {report&&<><p>Updated {date(report.collected_at)} · {report.sessions.filter(s=>s.status==='running').length} running · {report.sessions.length} retained sessions</p><div className="runtime-scroll"><table><thead><tr><th>Runtime</th><th>State</th><th>Retained</th><th>Evidence</th></tr></thead><tbody>{report.runtimes?.map(r=><tr key={r.id}><th>{r.label}</th><td>{r.state}</td><td>{count(r.sessions)}</td><td>{r.source}</td></tr>)}</tbody></table></div><p>{report.evidence}</p></>}
 </section>;
}
