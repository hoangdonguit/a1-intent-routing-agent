"""Replay saved IR through opt-in necessary checks; no model, sudo or lab resets."""
import argparse,json,hashlib,sys,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from a1_intent_routing.bgp_hybrid_eval import load_case
from a1_intent_routing.bgp_plan import render,digest
from a1_intent_routing.bgp_public_precheck import audit,PROFILE,VERSION
from a1_intent_routing.bgp_public_feedback import feedback
OLD=ROOT/'runs/bgp-plan-study-20261120-02'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve()
    if out.exists():raise RuntimeError('Preserve existing research output')
    # Require exact pinned image and empirically captured traditional profile.
    lock=json.loads((ROOT/'labs/sixrouter/images.lock.json').read_text())['images']['router']
    image=json.loads(subprocess.check_output(['docker','image','inspect',lock['reference']],text=True,timeout=20))[0]
    if image['Id']!=lock['image_id']:raise RuntimeError('Uncalibrated FRR image')
    state=json.loads((OLD/'state.json').read_text());definition=json.loads((OLD/'definition.json').read_text())
    positive=Path(state['completed']['controls/dev_ebgp_prefix_02--positive']['result']).parent
    proof=[]
    for path in sorted((positive/'syntax').glob('*command.json')):
        row=json.loads(path.read_text())
        if 'show running-config' in row.get('argv',[]) and 'frr defaults traditional' in row.get('stdout',''):
            proof.append({'path':str(path.relative_to(ROOT)),'sha256':sha(path)})
    if len(proof)!=6:raise RuntimeError('Missing six-node traditional-profile running-config calibration')
    out.mkdir(parents=True);rows=[]
    entries=[]
    for entry in definition['controls']:
        plan_path=Path(entry['configs']).parent/'plan.json';entries.append({'label':entry['label'],'case_id':entry['case_id'],'plan':plan_path,'kind':'control','variant':entry['variant'],'legacy_result':state['completed']['controls/'+entry['label']]['result']})
    for key,t in state['trajectories'].items():
        for r in t['rounds']:entries.append({'label':key+'--round-'+str(r['index']),'case_id':key.split('--')[0],'plan':Path(r['path'])/'ir.json','kind':'saved_model','legacy_result':str(Path(r['path'])/'evaluation/result.json')})
    for entry in entries:
        public,topology,base,d=load_case(ROOT,entry['case_id']);plan=json.loads(entry['plan'].read_text());before=digest(plan);configs=render(plan,base)
        report=audit(plan,public,topology,profile=PROFILE);assert digest(plan)==before and render(plan,base)==configs
        # Calibrate against unchanged actual candidate bytes, not just command sets.
        for n,text in configs.items():
            source=entry['plan'].parent/'configs'/(n+'.conf')
            if not source.exists() or source.read_text()!=text:raise RuntimeError('Saved candidate changed: '+str(source))
        dest=out/entry['label'];dest.mkdir();dump(dest/'precheck.json',report)
        if report['status']=='fail':
            (dest/'A1-feedback.txt').write_text(feedback('A1',report));(dest/'A2-feedback.json').write_text(feedback('A2',report)+'\n')
        row={'label':entry['label'],'case_id':entry['case_id'],'kind':entry['kind'],'variant':entry.get('variant'),'status':report['status'],'errors':[{'device':e['device'],'property':e['property'],'object_ids':e['object_ids']} for e in report['errors']],'nonconnected_warning_count':sum(w['property']=='nonconnected_origination_coverage' for w in report['warnings']),'source_ir':str(entry['plan'].relative_to(ROOT)),'source_ir_sha256':sha(entry['plan']),'legacy_result_sha256':sha(entry['legacy_result']),'report':str((dest/'precheck.json').relative_to(ROOT)),'candidate_bytes_preserved':True};rows.append(row);print(entry['label'],report['status'],[e['property'] for e in report['errors']],flush=True)
    assert len(rows)==16
    assert all(r['status']=='pass' for r in rows if r.get('variant')=='positive')
    assert all(r['status']=='fail' for r in rows if r['kind']=='saved_model')
    direct={'wrong-asn','self-neighbor','missing-peer','missing-originate','unattached-policy'}
    assert all(r['status']=='fail' for r in rows if r.get('variant') in direct)
    assert all(r['status']=='pass' for r in rows if r.get('variant') in {'leak','inverted-decision','sender-allows-receiver-denies'})
    versions={name:sha(ROOT/name) for name in ['src/a1_intent_routing/bgp_public_precheck.py','src/a1_intent_routing/bgp_public_feedback.py','src/a1_intent_routing/bgp_plan.py','ops/research_bgp_public_precheck.py']}
    summary={'version':VERSION,'scope':'offline saved-IR research only; necessary checks, never full pass','profile':PROFILE,'image_reference':lock['reference'],'image_id':image['Id'],'profile_evidence':proof,'files':versions,'rows':rows,'positive_control_non_rejection':'2/2','in_scope_negative_detection':'5/5','outside_scope_negative_controls':'3/3 passed precheck, still fail mandatory legacy/export verifier','saved_model_proven_failure':'6/6','feedback_sent_to_model':False,'new_generation_calls':0,'new_lab_evaluations':0,'changed_historical_verdicts':False}
    dump(out/'summary.json',summary);print('Research gates passed; no model effectiveness claim')
if __name__=='__main__':main()
