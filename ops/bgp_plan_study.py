"""Bounded opt-in BGP study; immutable inputs, one request at a time, no retries."""
import argparse,hashlib,json,os,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from a1_intent_routing.bgp_hybrid_eval import evaluate,load_case,dump
from a1_intent_routing.bgp_plan import render,unique_json,semantic_digest,digest
from a1_intent_routing.bgp_plan_feedback import messages,feedback
from a1_intent_routing.run_lock import acquire
from a1_intent_routing.verifiers import Evidence
from a1_intent_routing.ollama_client import OllamaClient,metric_snapshot
from a1_intent_routing.context import ContextGuard
OUT=ROOT/'runs/bgp-plan-study-20261120'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def files():
    paths=[]
    for pattern in ['src/a1_intent_routing/*.py','ops/bgp_plan*.py','prompts/bgp-plan-v1.txt','schemas/bgp-plan-v1.json','data/benchmark/**/*.json','data/benchmark/**/*.conf','labs/*/images.lock.json','scripts/lab.py','scripts/six_lab.py','scripts/batfish_health.py','scripts/count_context.py','configs/tokenizer.json','configs/one-pass-pilot.json','configs/batfish.json']:
        paths.extend(p for p in ROOT.glob(pattern) if p.is_file())
    paths.extend(p for parent in [OUT/'controls',OUT/'origination'] for p in parent.rglob('*') if p.is_file())
    paths.extend([OUT/'definition.json',ROOT/'requirements/bgp-plan.txt'])
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(set(paths))}
def freeze():
    target=OUT/'manifest.json'
    if target.exists():raise RuntimeError('Manifest already frozen')
    client=OllamaClient();tags,_=client.request('/api/tags');definition=json.loads((OUT/'definition.json').read_text())
    model=next(x for x in tags['models'] if x['name']==definition['pilot_model'])
    expected=json.loads((ROOT/'configs/one-pass-pilot.json').read_text())['model']['digest']
    if model['digest'].removeprefix('sha256:')!=expected.removeprefix('sha256:'):raise RuntimeError('Model differs from pinned4B')
    dump(target,{'version':'bgp-plan-study-v1','files':files(),'model':model,'options':definition['options'],'stop_policy':'first pass/environment error/semantic cycle/5 repairs; no imputation','session_policy':'max2 calls; 1800s session; reserve1100s before call','created':time.time()})
def check():
    manifest=json.loads((OUT/'manifest.json').read_text())
    for p,h in manifest['files'].items():
        if sha(ROOT/p)!=h:raise RuntimeError('Frozen input changed: '+p)
    return manifest
def restore(directory):
    directory.mkdir(parents=True,exist_ok=True)
    with (directory/'restore.log').open('w') as log:
        for script,args in [('six_lab.py',['destroy']),('lab.py',['reset'])]:
            subprocess.run([sys.executable,str(ROOT/'scripts'/script),*args],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240)
    dump(directory/'restore.json',{'status':'pass','time':time.time()})
def capture(t,out):
    ev=Evidence(out,lab_name='a1-sixrouter');rows=[]
    for node in t.nodes:
        if node.kind!='router':continue
        for command in ['show running-config','show ip route json','show bgp ipv4 unicast json','show bgp ipv4 unicast import-check-table json']:
            r=ev.dexec(node.name,'vtysh','-c',command,check=False)
            rows.append({'node':node.name,'command':command,'returncode':r.returncode,'stdout':r.stdout,'artifact':ev.last})
        for link in t.links:
            for a,b in [(link.a,link.b),(link.b,link.a)]:
                if a.node==node.name and next(n for n in t.nodes if n.name==b.node).kind=='router':
                    command='show bgp ipv4 unicast neighbors '+str(t.interfaces[b].ip)+' advertised-routes json'
                    r=ev.dexec(node.name,'vtysh','-c',command,check=False);rows.append({'node':node.name,'command':command,'returncode':r.returncode,'stdout':r.stdout,'artifact':ev.last})
    dump(out/'captures.json',rows)
def summary(state):
    rows=[]
    for key,t in state.get('trajectories',{}).items():
        rounds=t['rounds'];metrics={}
        for field in ['input_tokens','output_tokens','api_total_seconds']:
            values=[r['metrics'].get(field) for r in rounds]
            metrics[field]=sum(values) if values and all(v is not None for v in values) else None
        rows.append({'trajectory':key,'status':t['status'],'stop_reason':t.get('stop_reason'),'generations_observed':len(rounds),'repair_milestones_observed':{str(k):next((r['status'] for r in rounds if r['index']==k),None) for k in [1,3,5]},'metrics':metrics})
    return {'version':'bgp-plan-study-v1','primary_updated':False,'calls_started':state.get('calls',0),'trajectories':rows,'calibration':state.get('completed',{}),'last_restore':state.get('last_restore')}

def run(args):
    if os.geteuid()!=0:raise RuntimeError('Lab stages need sudo; use launcher')
    manifest=check();lock=acquire(ROOT);definition=json.loads((OUT/'definition.json').read_text())
    statepath=OUT/'state.json';state=json.loads(statepath.read_text()) if statepath.exists() else {'completed':{},'trajectories':{},'calls':0}
    state['active_pid']=os.getpid()
    stop=OUT/'STOP';started=time.monotonic();session=OUT/('session-'+str(time.time_ns()));session.mkdir()
    dump(session/'active.json',{'pid':os.getpid(),'started':time.time()})
    def halted(*unused):stop.touch()
    signal.signal(signal.SIGINT,halted);signal.signal(signal.SIGTERM,halted)
    def save():
        dump(statepath,state);dump(OUT/'summary.json',summary(state))
    def pause():return stop.exists() or time.monotonic()-started>args.seconds
    try:
        # No nested --start lock. Health only; never generates.
        subprocess.run([sys.executable,str(ROOT/'scripts/batfish_health.py'),'--query','--out',str(session/'health')],check=True,timeout=180)
        for group,entries in [('origination',definition['origination']),('controls',definition['controls'])]:
            for entry in entries:
                key=group+'/'+entry['label']
                if key in state['completed']:continue
                if pause():return
                directory=session/group/entry['label'];directory.parent.mkdir(parents=True,exist_ok=True)
                cid=entry.get('case_id','dev_ebgp_prefix_01')
                result=evaluate(ROOT,cid,entry['configs'],directory,diagnostic_connected=group=='origination' and entry.get('backing')=='connected')
                if group=='origination' and any(r.get('tool')=='lab_ping_tester' for r in result.get('reports',[])):
                    _,t,_,_=load_case(ROOT,cid)
                    capture(t,directory/'diagnostics')
                    # Query both RIBs without using lab values as Batfish answers.
                    from pybatfish.client.session import Session
                    bf=Session(host='127.0.0.1',timeout=15);bf.set_network('a1-intent-routing')
                    snap=next((r.get('snapshot_name') for r in result.get('reports',[]) if r.get('snapshot_name')),None)
                    if snap:
                        bf.set_snapshot(snap)
                        for rib in ['main','bgp']:
                            try:
                                frame=bf.q.routes(nodes='r2',network=entry['prefix'],rib=rib).answer().frame()
                                dump(directory/('bf-'+rib+'.json'),json.loads(frame.to_json(orient='records',default_handler=str)))
                            except Exception as e:dump(directory/('bf-'+rib+'.json'),{'unavailable':str(e)})
                passed=result['status']==entry.get('expected',result['status'])
                if group=='controls' and entry['variant']=='sender-allows-receiver-denies':
                    legacy=json.loads((directory/'legacy-result.json').read_text());passed=passed and legacy['status']=='pass'
                state['completed'][key]={'status':result['status'],'calibrated':passed,'result':str(directory/'result.json')};save();print(key,result['status'],'calibrated',passed,flush=True)
                if group=='controls' and not passed:state['blocked']='Calibration control mismatch: '+key;save();return
        if not args.pilot:print('Calibration complete; pilot explicitly not requested');return
        if any(not v['calibrated'] for k,v in state['completed'].items() if k.startswith('controls/')):raise RuntimeError('Controls not calibrated')
        client=OllamaClient();tags,_=client.request('/api/tags');current=next(x for x in tags['models'] if x['name']==definition['pilot_model'])
        if current['digest']!=manifest['model']['digest']:raise RuntimeError('Model digest changed')
        guard=ContextGuard(ROOT);calls=0
        for cid in definition['case_ids']:
            public,t,base,d=load_case(ROOT,cid)
            initial=[{'role':'system','content':(ROOT/'prompts/bgp-plan-v1.txt').read_text()},{'role':'user','content':json.dumps({'public':public,'topology':json.loads((d/public['topology']).read_text()),'base':base,'output_schema':definition['schema']},ensure_ascii=False)}]
            for mode in ['B1','A1','A2']:
                key=cid+'--'+mode;trajectory=state['trajectories'].setdefault(key,{'rounds':[],'status':'pending','seen':[]})
                if trajectory['status']!='pending':continue
                history=[{'content':r['content'],'feedback':r['feedback']} for r in trajectory['rounds']]
                for index in range(len(history),1 if mode=='B1' else 6):
                    if pause() or calls>=args.calls or args.seconds-(time.monotonic()-started)<1100:save();return
                    if state['calls']>=26:raise RuntimeError('Global26call cap reached')
                    payload={'model':definition['pilot_model'],'messages':messages(initial,history,mode),'options':definition['options'],'format':definition['schema'],'stream':False,'think':False,'keep_alive':'30m'}
                    preflight=guard.measure(payload)
                    if not preflight['within_budget'] and len(history)>1:
                        payload['messages']=messages(initial,history[-1:],mode);preflight=guard.measure(payload)
                    if not preflight['within_budget']:trajectory.update(status='environment_error',stop_reason='context_budget');save();break
                    rd=OUT/'pilot'/key/('round-'+str(index));rd.mkdir(parents=True,exist_ok=False)
                    dump(rd/'payload.json',payload);dump(rd/'preflight.json',preflight)
                    state['calls']+=1;calls+=1;trajectory['inflight']=str(rd);save()
                    try:
                        response,elapsed=client.chat_once(payload,timeout=900,raw_path=rd/'raw-response.json')
                        loaded,_=client.request('/api/ps');dump(rd/'loaded-models.json',loaded)
                        actual=next((m for m in loaded.get('models',[]) if m.get('digest')==manifest['model']['digest']),None)
                        if actual is None or actual.get('context_length')!=definition['options']['num_ctx']:raise RuntimeError('Actual loaded model/context differs from frozen pilot')
                        content=response.get('message',{}).get('content','');metrics,unavailable=metric_snapshot(response)
                        plan=None
                        try:
                            plan=unique_json(content);configs=render(plan,base);dump(rd/'ir.json',plan)
                            target=rd/'configs';target.mkdir()
                            for n,text in configs.items():(target/(n+'.conf')).write_text(text)
                        except (ValueError,TypeError,KeyError) as e:
                            plan=None
                            result={'status':'fail','errors':[{'status':'fail','tool':'ir_validator','property':'raw_ir_schema','observed':{'message':str(e),'path':getattr(e,'path','$')},'expected':'valid IR'}]}
                        else:result=evaluate(ROOT,cid,target,rd/'evaluation')
                        sem=semantic_digest(plan) if plan else hashlib.sha256(content.encode()).hexdigest();cycle=sem in trajectory['seen']
                        feed=None if mode=='B1' else feedback(mode,result,plan);record={'index':index,'content':content,'feedback':feed,'status':result['status'],'semantic_hash':sem,'metrics':metrics,'metrics_unavailable':unavailable,'http_seconds':elapsed,'raw_ir_valid':plan is not None,'messages_sha256':digest(payload['messages']),'options_sha256':digest(payload['options']),'raw_response_sha256':sha(rd/'raw-response.json'),'semantic_changed_from_previous':None if not trajectory['rounds'] else sem!=trajectory['rounds'][-1]['semantic_hash'],'candidate_hashes':{n:hashlib.sha256(s.encode()).hexdigest() for n,s in configs.items()} if plan is not None else {},'path':str(rd)}
                        trajectory['rounds'].append(record);trajectory['seen'].append(sem);trajectory.pop('inflight',None);history.append({'content':content,'feedback':feed});dump(rd/'record.json',record)
                        if result['status']=='pass':trajectory.update(status='pass',stop_reason='verified_pass')
                        elif result['status']=='environment_error':trajectory.update(status='environment_error',stop_reason='tool_environment')
                        elif cycle:trajectory.update(status='fail',stop_reason='stagnated')
                        elif mode=='B1' or index==5:trajectory.update(status='fail',stop_reason='budget_exhausted')
                        save();print(key,index,result['status'],trajectory.get('stop_reason'),flush=True)
                        if trajectory['status']!='pending':break
                    except Exception as e:
                        trajectory.update(status='environment_error',stop_reason='uncertain_call_no_retry',exception=str(e));save();raise
    finally:
        try:restore(session);state['last_restore']={'status':'pass','path':str(session)}
        except Exception as e:state['last_restore']={'status':'environment_error','error':str(e)}
        state['active_pid']=None;save();(session/'active.json').unlink(missing_ok=True);lock.close()
def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('action',choices=['freeze','check','status','run','stop','resume']);p.add_argument('--pilot',action='store_true');p.add_argument('--seconds',type=int,default=1800);p.add_argument('--calls',type=int,default=2);a=p.parse_args()
    if a.action=='freeze':freeze()
    elif a.action=='check':check();print('Frozen hashes verified')
    elif a.action=='stop':(OUT/'STOP').touch();print('Stop requested; wait for current bounded step and restore')
    elif a.action=='status':
        state=json.loads((OUT/'state.json').read_text()) if (OUT/'state.json').exists() else {};print(json.dumps(state,ensure_ascii=False,indent=2))
        active=list(OUT.glob('session-*/active.json'));print('Active markers:',[str(x) for x in active])
        try:
            lock=acquire(ROOT);lock.close();idle=True
        except RuntimeError:idle=False
        safe=idle and not active and state.get('last_restore',{}).get('status')=='pass'
        print('safe_to_power_off:',safe);print('Only power off when safe_to_power_off is True.')
    else:
        if not 0<a.calls<=2 or not 120<=a.seconds<=1800:raise ValueError('Session bounded to2calls/1800seconds')
        if a.action=='resume':(OUT/'STOP').unlink(missing_ok=True)
        state=json.loads((OUT/'state.json').read_text()) if (OUT/'state.json').exists() else {}
        if any(t.get('inflight') for t in state.get('trajectories',{}).values()):raise RuntimeError('Interrupted call requires audit; no automatic generation retry')
        run(a)
if __name__=='__main__':main()
