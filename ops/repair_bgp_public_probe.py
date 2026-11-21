"""One saved-initial A2 diagnostic using public necessary-condition feedback.

Not a new baseline comparison, not continuation/rewrite of the frozen pilot.
Exactly one generation; no root/lab/reset; optional real syntax+Batfish checks.
"""
import argparse,copy,hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from a1_intent_routing.bgp_hybrid_eval import load_case
from a1_intent_routing.bgp_plan import unique_json,render,semantic_digest,digest
from a1_intent_routing.bgp_public_precheck import audit,PROFILE
from a1_intent_routing.bgp_public_feedback import feedback
from a1_intent_routing.context import ContextGuard
from a1_intent_routing.ollama_client import OllamaClient,metric_snapshot
from a1_intent_routing.run_lock import acquire
from a1_intent_routing.verifiers import syntax_checker,Evidence
from a1_intent_routing.batfish import verify
from a1_intent_routing.contracts import CaseOracle
SOURCE=ROOT/'runs/bgp-plan-study-20261120-02/pilot/dev_ebgp_prefix_02--A2/round-0'
CODE=['src/a1_intent_routing/bgp_public_precheck.py','src/a1_intent_routing/bgp_public_feedback.py','src/a1_intent_routing/bgp_plan.py','ops/repair_bgp_public_probe.py']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def prepare(out):
    if out.exists():raise RuntimeError('Preserve existing probe output')
    public,t,base,d=load_case(ROOT,'dev_ebgp_prefix_02');plan=json.loads((SOURCE/'ir.json').read_text());report=audit(plan,public,t,profile=PROFILE)
    if report['status']!='fail':raise RuntimeError('Source must have public proven failures')
    request=json.loads((SOURCE/'payload.json').read_text());raw=json.loads((SOURCE/'raw-response.json').read_text());request=copy.deepcopy(request)
    request['messages'] += [{'role':'assistant','content':raw['message']['content']},{'role':'user','content':feedback('A2',report)}]
    preflight=ContextGuard(ROOT).measure(request)
    if not preflight['within_budget']:raise RuntimeError('Does not fit unchanged context')
    sources=[SOURCE/'ir.json',SOURCE/'payload.json',SOURCE/'raw-response.json',d/'public.json',d/public['topology'],*[d/'base'/(n+'.conf') for n in base],*[ROOT/n for n in CODE]]
    calibration=ROOT/'runs/bgp-public-precheck-20261121-02/summary.json'
    calibrated=json.loads(calibration.read_text())
    if calibrated['profile']!=PROFILE or calibrated['positive_control_non_rejection']!='2/2' or calibrated['in_scope_negative_detection']!='5/5':raise RuntimeError('Public precheck not calibrated')
    for name,h in calibrated['files'].items():
        if sha(ROOT/name)!=h:raise RuntimeError('Calibration code drift: '+name)
    sources += [calibration,ROOT/'configs/one-pass-pilot.json',ROOT/'labs/sixrouter/images.lock.json',*[ROOT/r['path'] for r in calibrated['profile_evidence']]]
    out.mkdir(parents=True);dump(out/'request.json',request);dump(out/'source-precheck.json',report);dump(out/'preflight.json',preflight)
    dump(out/'plan.json',{'version':'bgp-public-A2-single-probe-v1','source':str(SOURCE.relative_to(ROOT)),'case_id':'dev_ebgp_prefix_02','max_generations':1,'image_reference':calibrated['image_reference'],'image_id':calibrated['image_id'],'model_digest':json.loads((ROOT/'configs/one-pass-pilot.json').read_text())['model']['digest'],'source_files':{str(p.resolve().relative_to(ROOT)):sha(p) for p in sources},'request_sha256':sha(out/'request.json'),'source_semantic_hash':semantic_digest(plan),'primary_updated':False,'comparison':'saved-initial diagnostic only; no claim of fair new B1/A1/A2 comparison'})
    print('Prepared one A2 diagnostic; no generation',preflight['prompt_tokens'],'tokens')
def run(out):
    spec=json.loads((out/'plan.json').read_text())
    for name,h in spec['source_files'].items():
        if sha(ROOT/name)!=h:raise RuntimeError('Frozen source changed: '+name)
    if sha(out/'request.json')!=spec['request_sha256']:raise RuntimeError('Request drift')
    if (out/'call-started.json').exists():raise RuntimeError('Probe already started; never retry')
    import subprocess
    image=json.loads(subprocess.check_output(['docker','image','inspect',spec['image_reference']],text=True,timeout=20))[0]
    if image['Id']!=spec['image_id']:raise RuntimeError('FRR profile image drift')
    client=OllamaClient();request=json.loads((out/'request.json').read_text());tags,_=client.request('/api/tags');model=next(m for m in tags['models'] if m['name']==request['model'])
    if model['digest'].removeprefix('sha256:')!=spec['model_digest']:raise RuntimeError('Model digest drift')
    public,t,base,d=load_case(ROOT,spec['case_id']);preflight=ContextGuard(ROOT).measure(request)
    if not preflight['within_budget']:raise RuntimeError('Context drift')
    with acquire(ROOT):
        dump(out/'call-started.json',{'time':time.time(),'max_calls':1,'purpose':spec['version']});start=time.monotonic()
        summary={'version':spec['version'],'status':'environment_error','gate':'unfinished','new_generation_calls':1,'full_verified_pass':False,'lab':'not_run','primary_updated':False}
        try:
            response,http=client.chat_once(request,900,out/'raw-response.json');metrics,unavailable=metric_snapshot(response);summary.update(metrics=metrics,unavailable=unavailable,http_seconds=http)
            loaded,_=client.request('/api/ps');dump(out/'loaded-models.json',loaded)
            active=next((m for m in loaded.get('models',[]) if m.get('digest')==model['digest']),None)
            if active is None or active.get('context_length')!=request['options']['num_ctx']:raise RuntimeError('Loaded model/context drift')
            content=response.get('message',{}).get('content','')
            try:
                plan=unique_json(content);configs=render(plan,base)
            except (ValueError,KeyError,TypeError) as exc:
                summary.update(status='fail',gate='raw_ir_schema',raw_ir_valid=False,error=str(exc));return
            summary.update(raw_ir_valid=True,semantic_changed=semantic_digest(plan)!=spec['source_semantic_hash']);dump(out/'ir.json',plan)
            target=out/'configs';target.mkdir()
            for name,text in configs.items():(target/(name+'.conf')).write_text(text)
            report=audit(plan,public,t,profile=PROFILE);dump(out/'precheck.json',report);summary['precheck_status']=report['status'];summary['precheck_errors']=[{'device':e['device'],'property':e['property']} for e in report['errors']]
            summary['source_target_errors']=[e['property'] for e in json.loads((out/'source-precheck.json').read_text())['errors']];summary['removed_target_errors']=[p for p in summary['source_target_errors'] if p not in [e['property'] for e in report['errors']]]
            if report['status']!='pass':summary.update(status=report['status'],gate='public_precheck');return
            paths={n:target/(n+'.conf') for n in base};syntax=syntax_checker(paths,t,json.loads((ROOT/'labs/sixrouter/images.lock.json').read_text()),Evidence(out/'syntax')).to_dict();dump(out/'syntax.json',syntax);summary['rendered_syntax_status']=syntax['status']
            if syntax['status']!='pass':summary.update(status=syntax['status'],gate='syntax');return
            oracle_raw=json.loads((d/'oracle.json').read_text());oracle=CaseOracle.from_dict({k:v for k,v in oracle_raw.items() if k!='prefix_checks'},t)
            bf=verify(t,oracle,paths,out/'batfish',public_spec=public['specification'],prefix_checks=oracle_raw.get('prefix_checks',[]));dump(out/'batfish.json',bf);summary['batfish_status']=bf['status'];summary['batfish_error_properties']=sorted({e['property'] for e in bf.get('errors',[])})
            summary.update(status='fail' if bf['status']=='fail' else 'environment_error',gate='batfish' if bf['status']!='pass' else 'lab_not_run')
        except Exception as exc:summary.update(status='environment_error',gate='probe_environment',error=f'{type(exc).__name__}: {exc}')
        finally:
            summary['measured_probe_seconds']=time.monotonic()-start;dump(out/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False),flush=True)
def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('action',choices=['prepare','run']);p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve()
    (prepare if a.action=='prepare' else run)(out)
if __name__=='__main__':main()
