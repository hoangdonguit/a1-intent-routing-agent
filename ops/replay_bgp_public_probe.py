"""Source-hashed one-candidate lab diagnosis; never generates or rewrites configs."""
import argparse,hashlib,json,os,sys,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from a1_intent_routing.bgp_hybrid_eval import evaluate,load_case
from a1_intent_routing.bgp_plan import render
from a1_intent_routing.bgp_public_precheck import audit,PROFILE
from a1_intent_routing.run_lock import acquire
from bgp_plan_study import restore
PROBE=ROOT/'runs/bgp-public-repair-probe-20261121-02'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def prepare(out):
    if out.exists():raise RuntimeError('Preserve existing lab plan/output')
    summary=json.loads((PROBE/'summary.json').read_text());public,t,base,d=load_case(ROOT,'dev_ebgp_prefix_02');plan=json.loads((PROBE/'ir.json').read_text())
    if summary.get('precheck_status')!='pass' or summary.get('rendered_syntax_status')!='pass':raise RuntimeError('Candidate not ready for lab syntax/public gates')
    if audit(plan,public,t,profile=PROFILE)['status']!='pass':raise RuntimeError('Public check drift')
    for n,text in render(plan,base).items():
        if (PROBE/'configs'/(n+'.conf')).read_text()!=text:raise RuntimeError('Rendered candidate drift')
    paths=[*sorted((PROBE/'configs').glob('*.conf')),PROBE/'ir.json',PROBE/'raw-response.json',PROBE/'summary.json',PROBE/'syntax.json',d/'public.json',d/'oracle.json',d/public['topology'],ROOT/'labs/sixrouter/images.lock.json',ROOT/'configs/batfish.json']
    paths += list((ROOT/'src/a1_intent_routing').glob('*.py'))
    paths += [ROOT/'ops/replay_bgp_public_probe.py',ROOT/'ops/bgp_plan_study.py',ROOT/'scripts/lab.py',ROOT/'scripts/six_lab.py',ROOT/'scripts/batfish_health.py']
    out.mkdir(parents=True);dump(out/'plan.json',{'version':'bgp-public-probe-lab-v1','case_id':'dev_ebgp_prefix_02','configs':str(PROBE/'configs'),'source_files':{str(p.resolve().relative_to(ROOT)):sha(p) for p in paths},'new_generation_calls':0,'scope':'one dev candidate diagnostic, historical/pilot unchanged','grader':'bgp-hybrid-export-v1; original syntax/scope/lab/Batfish/export checks retained'})
    print('Prepared one model candidate; no generation, no lab started')
def run(out):
    if os.geteuid()!=0:raise RuntimeError('Run bash ops/run_bgp_public_probe_lab.sh in Terminal')
    plan=json.loads((out/'plan.json').read_text())
    for name,h in plan['source_files'].items():
        if sha(ROOT/name)!=h:raise RuntimeError('Frozen lab source changed: '+name)
    if (out/'run-started.json').exists():raise RuntimeError('Lab attempt already started; retain results, do not silently retry')
    with acquire(ROOT):
        dump(out/'run-started.json',{'time':time.time(),'pid':os.getpid(),'new_generation_calls':0});summary={'version':plan['version'],'status':'environment_error','lab_evaluations':0,'new_generation_calls':0,'primary_updated':False}
        try:
            subprocess.run([sys.executable,str(ROOT/'scripts/batfish_health.py'),'--query','--out',str(out/'health')],check=True,timeout=180)
            result=evaluate(ROOT,plan['case_id'],plan['configs'],out/'replay');summary.update(status=result['status'],lab_evaluations=1,result=str(out/'replay/result.json'),tools={r['tool']:r['status'] for r in result['reports']},disagreements=len(result.get('disagreements',[])))
        except Exception as exc:summary['error']=f'{type(exc).__name__}: {exc}'
        finally:
            try:restore(out/'final-restore');summary['restore']='pass'
            except Exception as exc:summary['restore']='environment_error';summary['restore_error']=str(exc)
            dump(out/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False),flush=True)
def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('action',choices=['prepare','run']);p.add_argument('--out',type=Path,required=True);a=p.parse_args();(prepare if a.action=='prepare' else run)(a.out.resolve())
if __name__=='__main__':main()
