"""One model-chosen origin-only adaptation after real lab/export PASS."""
import argparse,contextlib,copy,io,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import repair_bgp_public_probe as engine
from a1_intent_routing.bgp_hybrid_eval import load_case
from a1_intent_routing.bgp_plan import render,semantic_digest
from a1_intent_routing.bgp_public_precheck import audit,PROFILE
from a1_intent_routing.bgp_coverage_advisory import build,nonorigin_signature
from a1_intent_routing.context import ContextGuard
SOURCE=ROOT/'runs/bgp-h2-policy-repair-20261121-01'
LAB=ROOT/'runs/bgp-h2-policy-lab-20261121-01'
def prepare(out):
    if out.exists():raise RuntimeError('Preserve existing coverage probe')
    result=json.loads((LAB/'replay/result.json').read_text());lab_summary=json.loads((LAB/'summary.json').read_text())
    if lab_summary.get('restore')!='pass':raise RuntimeError('Source restore incomplete')
    public,t,base,d=load_case(ROOT,'dev_ebgp_prefix_02');plan=json.loads((SOURCE/'ir.json').read_text());message=build(plan,t,result)
    for n,text in render(plan,base).items():
        if (SOURCE/'configs'/(n+'.conf')).read_text()!=text:raise RuntimeError('Source IR/config mismatch')
    request=copy.deepcopy(json.loads((SOURCE/'request.json').read_text()));response=json.loads((SOURCE/'raw-response.json').read_text())
    # Frozen history2: initial public messages + latest previous pair + current pair.
    request['messages']=request['messages'][:2]+request['messages'][-2:]+[{'role':'assistant','content':response['message']['content']},{'role':'user','content':message}]
    preflight=ContextGuard(ROOT).measure(request)
    if not preflight['within_budget']:raise RuntimeError('Does not fit fixed context; no budget change or truncation')
    original=json.loads((SOURCE/'plan.json').read_text());labplan=json.loads((LAB/'plan.json').read_text());hashes=dict(original['source_files']);hashes.update(labplan['source_files'])
    for name,h in hashes.items():
        if engine.sha(ROOT/name)!=h:raise RuntimeError('Source provenance drift: '+name)
    paths=[SOURCE/'ir.json',SOURCE/'request.json',SOURCE/'raw-response.json',SOURCE/'summary.json',LAB/'replay/result.json',LAB/'summary.json',LAB/'plan.json',ROOT/'ops/repair_bgp_coverage_probe.py',ROOT/'src/a1_intent_routing/bgp_coverage_advisory.py']
    hashes.update({str(p.resolve().relative_to(ROOT)):engine.sha(p) for p in paths});out.mkdir(parents=True)
    engine.dump(out/'request.json',request);engine.dump(out/'feedback.json',json.loads(message));engine.dump(out/'source-precheck.json',audit(plan,public,t,profile=PROFILE));engine.dump(out/'preflight.json',preflight)
    engine.dump(out/'plan.json',{'version':'bgp-coverage-origin-only-probe-v1','case_id':'dev_ebgp_prefix_02','max_generations':1,'source':str(SOURCE.relative_to(ROOT)),'repair_index_in_diagnostic_lineage':3,'repair_scope':'originate arrays only; policies and all other network choices immutable','feedback_eligibility':'all real functional tools PASS, only known origination coverage exception remains; not a network failure','source_final_verdict':result['status'],'source_semantic_hash':semantic_digest(plan),'source_files':hashes,'request_sha256':engine.sha(out/'request.json'),'model_digest':original['model_digest'],'image_reference':original['image_reference'],'image_id':original['image_id'],'primary_updated':False,'new_method_comparison':False})
    print('Prepared one origin-only coverage adaptation;',preflight['prompt_tokens'],'input tokens; no generation')
def run(out):
    with contextlib.redirect_stdout(io.StringIO()):engine.run(out)
    p=out/'summary.json';summary=json.loads(p.read_text());p.rename(out/'offline-stage-summary.json');summary['source_public_errors']=summary.pop('source_target_errors',[]);summary['removed_public_errors']=summary.pop('removed_target_errors',[]);eligible=False
    if summary.get('raw_ir_valid'):
        before=json.loads((SOURCE/'ir.json').read_text());after=json.loads((out/'ir.json').read_text());scope=nonorigin_signature(before)==nonorigin_signature(after);summary['repair_scope_status']='pass' if scope else 'fail';summary['origination_changes']=[{'device':d['id'],'before':next(x['originate'] for x in before['devices'] if x['id']==d['id']),'after':d['originate']} for d in after['devices'] if sorted(d['originate'])!=sorted(next(x['originate'] for x in before['devices'] if x['id']==d['id']))]
        eligible=scope and summary.get('precheck_status')=='pass' and summary.get('rendered_syntax_status')=='pass' and summary.get('batfish_status')=='pass';engine.dump(out/'repair-scope.json',{'status':summary['repair_scope_status'],'before_nonorigin_hash':nonorigin_signature(before),'after_nonorigin_hash':nonorigin_signature(after),'candidate_auto_corrected':False})
    summary['eligible_for_full_lab']=eligible;summary['full_verified_pass']=False;summary['lab']='not_run';engine.dump(out/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False),flush=True)
def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('action',choices=['prepare','run']);p.add_argument('--out',type=Path,required=True);a=p.parse_args();(prepare if a.action=='prepare' else run)(a.out.resolve())
if __name__=='__main__':main()
