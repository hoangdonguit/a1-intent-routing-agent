"""Final bounded one-call origin-update diagnostic after a rejected full-IR edit.

Contract change is explicit. Not a frozen A2 benchmark or selection/merge of
previous candidates: the parent is the last scope-valid, lab-passing model plan.
"""
import argparse,copy,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import repair_bgp_public_probe as engine
from a1_intent_routing.bgp_hybrid_eval import load_case
from a1_intent_routing.bgp_plan import render,unique_json,semantic_digest
from a1_intent_routing.bgp_origin_update import schema,apply
from a1_intent_routing.bgp_coverage_advisory import build,nonorigin_signature
from a1_intent_routing.bgp_public_precheck import audit,PROFILE
from a1_intent_routing.context import ContextGuard
from a1_intent_routing.ollama_client import OllamaClient,metric_snapshot
from a1_intent_routing.run_lock import acquire
from a1_intent_routing.verifiers import syntax_checker,Evidence
from a1_intent_routing.batfish import verify
from a1_intent_routing.contracts import CaseOracle
SOURCE=ROOT/'runs/bgp-h2-policy-repair-20261121-01'
LAB=ROOT/'runs/bgp-h2-policy-lab-20261121-01'
REJECTED=ROOT/'runs/bgp-coverage-repair-20261121-01'
def prepare(out):
    if out.exists():raise RuntimeError('Preserve existing final update probe')
    public,t,base,d=load_case(ROOT,'dev_ebgp_prefix_02');source=json.loads((SOURCE/'ir.json').read_text());result=json.loads((LAB/'replay/result.json').read_text());advisory=json.loads(build(source,t,result));advisory.pop('instruction')
    rejected=json.loads((REJECTED/'summary.json').read_text())
    if rejected.get('repair_scope_status')!='fail':raise RuntimeError('This contract probe requires the recorded scope rejection')
    original=json.loads((SOURCE/'request.json').read_text());request={k:copy.deepcopy(v) for k,v in original.items() if k!='messages'};request['format']=schema({d['id'] for d in source['devices']})
    request['messages']=[{'role':'system','content':(ROOT/'prompts/bgp-origin-update-v1.txt').read_text()},{'role':'user','content':json.dumps({'public':public,'topology':json.loads((d/public['topology']).read_text()),'base':base,'source_originate':{v['id']:v['originate'] for v in source['devices']},'coverage':advisory,'output_schema':request['format']},ensure_ascii=False)}]
    preflight=ContextGuard(ROOT).measure(request)
    if not preflight['within_budget']:raise RuntimeError('Does not fit unchanged context')
    original_plan=json.loads((SOURCE/'plan.json').read_text());hashes=dict(original_plan['source_files']);hashes.update(json.loads((LAB/'plan.json').read_text())['source_files'])
    for name,h in hashes.items():
        if engine.sha(ROOT/name)!=h:raise RuntimeError('Source provenance drift: '+name)
    paths=[SOURCE/'ir.json',SOURCE/'summary.json',LAB/'replay/result.json',LAB/'summary.json',REJECTED/'summary.json',ROOT/'ops/repair_bgp_origin_update.py',ROOT/'src/a1_intent_routing/bgp_origin_update.py',ROOT/'src/a1_intent_routing/bgp_coverage_advisory.py',ROOT/'prompts/bgp-origin-update-v1.txt']
    hashes.update({str(p.resolve().relative_to(ROOT)):engine.sha(p) for p in paths});out.mkdir(parents=True);engine.dump(out/'request.json',request);engine.dump(out/'preflight.json',preflight)
    engine.dump(out/'plan.json',{'version':'bgp-origin-update-single-probe-v1','case_id':'dev_ebgp_prefix_02','source':str(SOURCE.relative_to(ROOT)),'rejected_full_ir_attempt':str(REJECTED.relative_to(ROOT)),'source_selection':'last accepted parent; rejected proposal never committed; no merging/picking fields from rejected output','max_generations':1,'stop_after_this_probe':True,'contract':'device-ID originate-array updates only; compiler preserves every other field','model_options_unchanged':True,'output_contract_changed':True,'new_method_comparison':False,'source_files':hashes,'request_sha256':engine.sha(out/'request.json'),'model_digest':original_plan['model_digest'],'image_reference':original_plan['image_reference'],'image_id':original_plan['image_id'],'primary_updated':False})
    print('Prepared final one-call update-contract probe;',preflight['prompt_tokens'],'input tokens; no generation')
def run(out):
    import subprocess
    spec=json.loads((out/'plan.json').read_text())
    for name,h in spec['source_files'].items():
        if engine.sha(ROOT/name)!=h:raise RuntimeError('Frozen source changed: '+name)
    if engine.sha(out/'request.json')!=spec['request_sha256']:raise RuntimeError('Request drift')
    if (out/'call-started.json').exists():raise RuntimeError('Already started; no retry')
    image=json.loads(subprocess.check_output(['docker','image','inspect',spec['image_reference']],text=True,timeout=20))[0]
    if image['Id']!=spec['image_id']:raise RuntimeError('FRR image drift')
    request=json.loads((out/'request.json').read_text());client=OllamaClient();tags,_=client.request('/api/tags');model=next(m for m in tags['models'] if m['name']==request['model'])
    if model['digest'].removeprefix('sha256:')!=spec['model_digest']:raise RuntimeError('Model digest drift')
    if not ContextGuard(ROOT).measure(request)['within_budget']:raise RuntimeError('Context drift')
    public,t,base,d=load_case(ROOT,spec['case_id']);source=json.loads((SOURCE/'ir.json').read_text())
    with acquire(ROOT):
        engine.dump(out/'call-started.json',{'time':time.time(),'max_calls':1});start=time.monotonic();summary={'version':spec['version'],'status':'environment_error','gate':'unfinished','new_generation_calls':1,'full_verified_pass':False,'lab':'not_run','primary_updated':False,'eligible_for_full_lab':False}
        try:
            response,http=client.chat_once(request,900,out/'raw-response.json');metrics,unavailable=metric_snapshot(response);summary.update(metrics=metrics,unavailable=unavailable,http_seconds=http)
            loaded,_=client.request('/api/ps');engine.dump(out/'loaded-models.json',loaded);active=next((m for m in loaded.get('models',[]) if m.get('digest')==model['digest']),None)
            if active is None or active.get('context_length')!=request['options']['num_ctx']:raise RuntimeError('Loaded model/context drift')
            try:patch=unique_json(response.get('message',{}).get('content',''));candidate=apply(source,patch)
            except (ValueError,KeyError,TypeError) as exc:summary.update(status='fail',gate='raw_update_schema',raw_update_schema_valid=False,error=str(exc));return
            engine.dump(out/'update.json',patch);engine.dump(out/'ir.json',candidate);summary.update(raw_update_schema_valid=True,materialized_ir_valid=True,semantic_changed=semantic_digest(source)!=semantic_digest(candidate),repair_scope_status='pass' if nonorigin_signature(source)==nonorigin_signature(candidate) else 'fail')
            if summary['repair_scope_status']!='pass':raise RuntimeError('Update applier changed protected fields')
            engine.dump(out/'repair-scope.json',{'status':'pass','source_nonorigin_hash':nonorigin_signature(source),'candidate_nonorigin_hash':nonorigin_signature(candidate),'only_literal_model_updates_applied':True})
            target=out/'configs';target.mkdir()
            for name,text in render(candidate,base).items():(target/(name+'.conf')).write_text(text)
            report=audit(candidate,public,t,profile=PROFILE);engine.dump(out/'precheck.json',report);summary['precheck_status']=report['status']
            if report['status']!='pass':summary.update(status=report['status'],gate='public_precheck');return
            paths={n:target/(n+'.conf') for n in base};syntax=syntax_checker(paths,t,json.loads((ROOT/'labs/sixrouter/images.lock.json').read_text()),Evidence(out/'syntax')).to_dict();engine.dump(out/'syntax.json',syntax);summary['rendered_syntax_status']=syntax['status']
            if syntax['status']!='pass':summary.update(status=syntax['status'],gate='syntax');return
            raw=json.loads((d/'oracle.json').read_text());oracle=CaseOracle.from_dict({k:v for k,v in raw.items() if k!='prefix_checks'},t);bf=verify(t,oracle,paths,out/'batfish',public_spec=public['specification'],prefix_checks=raw.get('prefix_checks',[]));engine.dump(out/'batfish.json',bf);summary.update(batfish_status=bf['status'],batfish_error_properties=sorted({e['property'] for e in bf.get('errors',[])}),eligible_for_full_lab=bf['status']=='pass',status='fail' if bf['status']=='fail' else 'environment_error',gate='lab_not_run' if bf['status']=='pass' else 'batfish')
        except Exception as exc:summary.update(status='environment_error',gate='probe_environment',error=f'{type(exc).__name__}: {exc}')
        finally:summary['measured_probe_seconds']=time.monotonic()-start;engine.dump(out/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False),flush=True)
def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('action',choices=['prepare','run']);p.add_argument('--out',type=Path,required=True);a=p.parse_args();(prepare if a.action=='prepare' else run)(a.out.resolve())
if __name__=='__main__':main()
