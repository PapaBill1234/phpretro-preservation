"""One bounded planner process; only the owning cycle applies its proposal."""
import copy,json,os,subprocess,time
import throughput

# Documented maintenance-B gaps are not permission to invent acceptance or a
# persistence adapter merely to fill the queue. These roadmap cards stay intact.
ACCEPTANCE_GAPS={'F31','F32','F33','F34','F39','F41','F42','F43','F44','F45','F46','F47'}
ADAPTER_GAPS={'F35','F38'}

def targets(o,roadmap):
    ready=throughput.ready_buffer(roadmap,o.REPO,o.PER_UNIT_TOKEN_CAP)
    if len(ready)>=throughput.READY_TARGET: return []
    paths=[p for uid in ready for p in roadmap[uid].get('paths',[])]
    result=[]
    for u in sorted(roadmap.values(),key=throughput.priority):
        if u['id'] in ACCEPTANCE_GAPS and not u.get('acceptance'): continue
        if u['id'] in ADAPTER_GAPS and not u.get('adapter_contract'): continue
        if int(u.get('planner_retries',0))>=o.PLANNER_RETRIES: continue
        if int(u.get('planner_depth',0))>=2: continue
        if u.get('status')=='parked' and any(word in str(u.get('reason','')).lower() for word in ('protected','guard','policy','merge refused','unreviewed','missing exact-head')): continue
        mode='split' if u.get('status')=='todo' and u.get('split_requested') else 'promote' if u.get('status')=='design' else 'rewrite' if u.get('status')=='parked' else ''
        if not mode or not o.deps_merged(u,roadmap): continue
        if mode=='promote' and not u.get('design_doc'): continue
        if mode=='promote' and throughput.overlap(u.get('paths'),paths): continue
        try: revision=throughput.revision(roadmap,u,o.REPO)
        except ValueError: continue
        if u.get('planner_stale_revision')==revision: continue
        result.append((u,mode,revision))
    return result

def start(o,roadmap,state):
    # Reservations survive crashes. Never launch around an already held planner.
    if any(r.get('role')=='planner' for r in state.get('reservations',{}).values()): return None
    choices=targets(o,roadmap)
    if not choices: return None
    eligible=[choice for choice in choices if o.paid_allowed(state,choice[0],'planner')]
    if not eligible: return None
    target,mode,revision=eligible[0]
    design=(o.REPO/target['design_doc']).read_text()[:12000] if target.get('design_doc') else ''
    prompt=o.planner_brief(target,mode,design)
    prompt+=('\nExisting IDs are immutable and reserved: '+', '.join(sorted(roadmap))+
        '\nUse fresh IDs; never emit the parent ID. Keep the approved roadmap, architecture, persistence and theme scope. '
        'Copy acceptance behavior from the supplied approved source; do not invent missing contracts. '
        'Every entry needs acceptance, tests and existing source fixtures. Prefer disjoint production paths. '
        'Produce at most three S/M slices within this parent scope; dependencies must be acyclic. '
        'You only prepare YAML: never modify repository, runtime state, counters or files. '
        f'The buffer target is {throughput.READY_TARGET} evidence-ready disjoint units across successive bounded jobs.\n')
    rid=o.admit_paid(state,target,'planner')
    dest=o.STATE_DIR/'planner-stage'/rid;dest.mkdir(parents=True)
    snapshot={'run_id':rid,'parent':target['id'],'mode':mode,'revision':revision,
              'target':copy.deepcopy(target),'board':copy.deepcopy(roadmap)}
    o.control.atomic_json(dest/'snapshot.json',snapshot)
    o.control.atomic_text(o.BRIEF_DIR/f'{target["id"]}-planner-{rid}.md',prompt)
    usage=o.LOG_DIR/f'{target["id"]}-planner-{rid}.usage.json'
    log_path=o.LOG_DIR/f'{target["id"]}-planner-{rid}.log';log=log_path.open('x')
    model=o.planner_model(target);ts=o.now();started=time.monotonic()
    cmd=[o.HERMES,'-z',prompt,'--usage-file',str(usage),'-m',model,'--provider',o.PROVIDER,
         '--reasoning',throughput.reasoning('planner'),'-t','file','-s',o.SKILL_NAME['planner'],
         '--in',str(o.REPO),'--accept-hooks']
    try:
        proc=subprocess.Popen(cmd,cwd=o.REPO,env={**os.environ,'HERMES_HOME':str(o.PROFILE_HOME['planner'])},
            stdout=log,stderr=subprocess.STDOUT,text=True,start_new_session=True)
    except OSError:
        log.close()
        o.log_model_run('planner',model,target['id'],None,127,'provider_error',{'total_tokens':0,'api_calls':0},
            'planner','file',ts,o.now(),run_id=rid,charged_tokens=0,reasoning='low')
        o.release_paid(state,rid);o.write_json(o.STATE_JSON,state)
        raise
    observer=throughput.Completion(proc,started,900,o.kill_process_group,
        lambda result:o.process_event('process_completed',target['id'],ts=throughput.iso(result.ended_wall),
            run_id=rid,role='planner',model=model,reasoning='low',rc=result.rc,elapsed_s=result.ended-started)).start()
    metadata_error=False
    try:
        o.process_event('process_dispatched',target['id'],run_id=rid,role='planner',model=model,reasoning='low',ts=ts)
        o.event(state,f'{target["id"]}: staged planner ({model}/low) {mode}; target ready buffer {throughput.READY_TARGET}')
    except Exception:
        o.STOP_FILE.touch();metadata_error=True
    return {'target':target,'snapshot':snapshot,'dest':dest,'usage':usage,'log':log,'log_path':log_path,
            'observer':observer,'model':model,'run_id':rid,'ts_start':ts,'metadata_error':metadata_error}

def finish(o,job,roadmap,state):
    target=job['target'];uid=target['id'];mode=job['snapshot']['mode']
    metadata_error=job.get('metadata_error',False)
    try: rc=job['observer'].join()
    except RuntimeError:
        o.STOP_FILE.touch();metadata_error=True;rc=job['observer'].rc
        if job['observer'].ended is None:
            job['observer'].proc.wait()
            job['observer'].ended=time.monotonic();job['observer'].ended_wall=time.time();rc=job['observer'].proc.returncode
    job['log'].close()
    usage=o.read_json(job['usage'],{}) or {};out=job['log_path'].read_text(errors='replace')[-200000:]
    explicit_zero=usage.get('api_calls')==0 and usage.get('total_tokens')==0
    charge=o.usage_tokens(usage)
    if not explicit_zero and (charge<=0 or usage.get('partial') or usage.get('failed') and not usage.get('completed')): charge=max(charge,o.TIMEOUT_FALLBACK_TOKENS)
    outage=o.control.provider_error(rc,out)
    held=state['reservations'][job['run_id']]['reserved_tokens']
    o.log_model_run('planner',job['model'],uid,None,rc,'provider_error' if outage else 'other',usage,
        'planner','file',job['ts_start'],throughput.iso(job['observer'].ended_wall),
        run_id=job['run_id'],charged_tokens=charge,reasoning='low',revision_id=job['snapshot']['revision'][:16])
    o.release_paid(state,job['run_id']);o.add_tokens(state,target,charge)
    if charge>held: raise o.control.IntegrityError('planner exceeded its reservation')
    if metadata_error:
        o.save_roadmap(roadmap);o.write_json(o.STATE_JSON,state)
        raise o.control.IntegrityError('planner completion telemetry unavailable; spend retained')
    result='rejected'
    if outage:
        o.note_provider(state,True,uid);result='provider_error'
    else:
        if rc==0: o.note_provider(state,False,uid)
        try: current=throughput.revision(roadmap,target,o.REPO)
        except ValueError: current=None
        stale=current!=job['snapshot']['revision']
        target['planner_retries']=int(target.get('planner_retries',0))+1
        with o.measured_stage('planner_validation',uid,job['run_id']):
            if stale:
                result='stale'
                try: target['planner_stale_revision']=throughput.revision(roadmap,target,o.REPO)
                except ValueError: target['planner_stale_revision']='source unavailable'
            elif rc==0 and o.paid_allowed(state,target,'planner'):
                candidate=copy.deepcopy(roadmap)
                if o.apply_planner_output(candidate,state,candidate[uid],out,old_id=uid,mode=mode):
                    ids=set(candidate)-set(roadmap)
                    paths=[p for old,u in roadmap.items() if old!=uid and u.get('status') in ('building','todo','queued','pr_open') for p in u.get('paths',[])]
                    valid=0<len(ids)<=o.SPLIT_MAX_UNITS
                    for new in sorted(ids):
                        entry=candidate[new]
                        valid=valid and throughput.evidence_ready(entry,o.REPO) and not throughput.overlap(entry['paths'],paths)
                        paths.extend(entry['paths'])
                        entry['severity']=target.get('severity','medium')
                        entry['planner_root']=target.get('planner_root',uid)
                        entry['planner_depth']=int(target.get('planner_depth',0))+1
                        if target.get('kind'): entry['kind']=target['kind']
                    if valid:
                        for old,entry in candidate.items():
                            if old in roadmap: roadmap[old].update(entry)
                            else: roadmap[old]=entry
                        target['status']='promoted' if mode=='promote' else 'parked-final'
                        target['split_requested']=False;result='applied'
            elif o.STOP_FILE.exists(): result='STOP'
        if result!='applied' and not stale:
            target['reason']=f'staged planner {result}; no proposal applied'
            if target['planner_retries']>=o.PLANNER_RETRIES:
                target['status']='design-blocked' if mode=='promote' else 'todo'
                target['split_requested']=False
    o.control.atomic_json(job['dest']/'result.json',{'run_id':job['run_id'],'parent':uid,'result':result,'rc':rc,'charged_tokens':charge})
    o.save_roadmap(roadmap);o.write_json(o.STATE_JSON,state)
    o.event(state,f'{uid}: staged planner {result}; single writer retained')
    return result
