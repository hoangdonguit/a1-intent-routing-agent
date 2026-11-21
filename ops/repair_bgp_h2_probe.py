"""One policy-only A2 repair from verified H2 export failures, no history retry."""
import argparse,copy,contextlib,io,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import repair_bgp_public_probe as engine
from a1_intent_routing.bgp_hybrid_eval import load_case
from a1_intent_routing.bgp_plan import render,semantic_digest
from a1_intent_routing.bgp_public_precheck import audit,PROFILE,policy_action
from a1_intent_routing.bgp_observed_feedback import build,policy_invariant
from a1_intent_routing.context import ContextGuard
SOURCE=ROOT/'runs/bgp-public-repair-probe-20261121-02'
LAB=ROOT/'runs/bgp-public-repair-lab-20261121-01'
def prepare(out):
    if out.exists():raise RuntimeError('Preserve existing policy repair output')
    summary=json.loads((LAB/'summary.json').read_text());result=json.loads((LAB/'replay/result.json').read_text())
    if summary.get('restore')!='pass':raise RuntimeError('Source lab restore incomplete')
    lab=next(r for r in result['reports'] if r['tool']=='lab_ping_tester');protected=[c for c in lab['checks'] if c['property']=='convergence' or 'reachability' in c['property']]
    if len(protected)!=3 or any(c['status']!='pass' for c in protected):raise RuntimeError('Source no longer has protected reachability and convergence')
    public,t,base,d=load_case(ROOT,'dev_ebgp_prefix_02');plan=json.loads((SOURCE/'ir.json').read_text());export=next(r for r in result['reports'] if r['tool']=='bgp_export_tester');witnesses={};evidence=[]
    for c in export['checks']:
        if c['property'].startswith('export_policy:') and c['status']=='fail':
            path=Path(c['evidence'][-1]);witnesses[(c['device'],c['property'])]=json.loads(path.read_text());evidence+=list(map(Path,c['evidence']))
    message=build(plan,public,t,export,witnesses)
    for c in export['checks']:
        if c['property'].startswith('advertised:') and c['status']=='fail':evidence+=list(map(Path,c['evidence']))
    for n,text in render(plan,base).items():
        if (SOURCE/'configs'/(n+'.conf')).read_text()!=text:raise RuntimeError('Source config/IR mismatch')
    request=copy.deepcopy(json.loads((SOURCE/'request.json').read_text()));response=json.loads((SOURCE/'raw-response.json').read_text());request['messages'] += [{'role':'assistant','content':response['message']['content']},{'role':'user','content':message}]
    preflight=ContextGuard(ROOT).measure(request)
    if not preflight['within_budget']:raise RuntimeError('Does not fit unchanged context; do not truncate public input or change settings')
    original=json.loads((SOURCE/'plan.json').read_text());labplan=json.loads((LAB/'plan.json').read_text())
    for name,h in labplan['source_files'].items():
        if engine.sha(ROOT/name)!=h:raise RuntimeError('Source lab provenance drift: '+name)
    files=[SOURCE/'ir.json',SOURCE/'request.json',SOURCE/'raw-response.json',LAB/'replay/result.json',LAB/'summary.json',*evidence,ROOT/'ops/repair_bgp_h2_probe.py',ROOT/'src/a1_intent_routing/bgp_observed_feedback.py']
    hashes=dict(original['source_files']);hashes.update(labplan['source_files']);hashes.update({str(p.resolve().relative_to(ROOT)):engine.sha(p) for p in files})
    out.mkdir(parents=True);engine.dump(out/'request.json',request);engine.dump(out/'source-precheck.json',audit(plan,public,t,profile=PROFILE));engine.dump(out/'feedback.json',json.loads(message));engine.dump(out/'preflight.json',preflight)
    engine.dump(out/'plan.json',{'version':'bgp-H2-policy-only-repair-v1','case_id':'dev_ebgp_prefix_02','source':str(SOURCE.relative_to(ROOT)),'max_generations':1,'repair_index_in_diagnostic_lineage':2,'repair_scope':'policies and peer import/export only; reject other changes without fixing them','feedback_eligibility':'actual origin advertisement plus matching peer-bound OUT policy PERMIT; coverage is not itself a model failure','source_final_verdict':result['status'],'source_semantic_hash':semantic_digest(plan),'source_files':hashes,'request_sha256':engine.sha(out/'request.json'),'model_digest':original['model_digest'],'image_reference':original['image_reference'],'image_id':original['image_id'],'primary_updated':False,'new_method_comparison':False})
    print('Prepared one policy-only A2 repair;',preflight['prompt_tokens'],'input tokens; no generation')
def run(out):
    # Reuse the frozen single-call executor, suppressing its intermediate summary.
    # Source public precheck is already PASS; target failures live in feedback.json.
    with contextlib.redirect_stdout(io.StringIO()):engine.run(out)
    stage=out/'summary.json';summary=json.loads(stage.read_text());stage.rename(out/'offline-stage-summary.json');summary['source_public_errors']=summary.pop('source_target_errors',[]);summary['removed_public_errors']=summary.pop('removed_target_errors',[])
    eligible=False
    if summary.get('raw_ir_valid'):
        before=json.loads((SOURCE/'ir.json').read_text());after=json.loads((out/'ir.json').read_text());scope=policy_invariant(before)==policy_invariant(after);summary['repair_scope_status']='pass' if scope else 'fail';targets=[]
        for e in json.loads((out/'feedback.json').read_text())['errors']:
            device=e['device'];peer=e['observed']['peer'];prefix=e['property'].split(':',1)[1];d=next(v for v in after['devices'] if v['id']==device);p=next((v for v in d['peers'] if v['address']==peer),None)
            targets.append({'device':device,'peer':peer,'prefix':prefix,'ir_policy_action':None if p is None else policy_action(after,p['export'],prefix),'meaning':'IR policy prediction only; actual advertisements still require lab'})
        summary['target_policy_predictions']=targets;eligible=scope and all(t['ir_policy_action']=='deny' for t in targets) and summary.get('precheck_status')=='pass' and summary.get('rendered_syntax_status')=='pass'
        engine.dump(out/'repair-scope.json',{'status':summary['repair_scope_status'],'before':policy_invariant(before),'after':policy_invariant(after),'candidate_auto_corrected':False})
    summary['eligible_for_target_lab']=eligible;summary['full_verified_pass']=False;summary['lab']='not_run';engine.dump(out/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False),flush=True)
def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('action',choices=['prepare','run']);p.add_argument('--out',type=Path,required=True);a=p.parse_args();(prepare if a.action=='prepare' else run)(a.out.resolve())
if __name__=='__main__':main()
