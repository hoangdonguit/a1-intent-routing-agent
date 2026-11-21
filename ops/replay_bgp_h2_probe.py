"""One unchanged-grader lab replay of the policy-only H2 repair."""
import argparse,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import replay_bgp_public_probe as lab
from a1_intent_routing.bgp_observed_feedback import policy_invariant
from a1_intent_routing.bgp_public_precheck import policy_action
PROBE=ROOT/'runs/bgp-h2-policy-repair-20261121-01'
SOURCE=ROOT/'runs/bgp-public-repair-probe-20261121-02'
def prepare(out):
    if not (PROBE/'summary.json').exists():raise RuntimeError('Wait for the one model call to finish')
    summary=json.loads((PROBE/'summary.json').read_text());spec=json.loads((PROBE/'plan.json').read_text())
    if not summary.get('eligible_for_target_lab'):raise RuntimeError('Candidate did not satisfy policy repair scope/target/syntax; preserve it, do not run lab')
    for name,h in spec['source_files'].items():
        if lab.sha(ROOT/name)!=h:raise RuntimeError('Repair source drift: '+name)
    before=json.loads((SOURCE/'ir.json').read_text());after=json.loads((PROBE/'ir.json').read_text())
    if policy_invariant(before)!=policy_invariant(after):raise RuntimeError('Network decisions changed outside policy repair scope')
    for e in json.loads((PROBE/'feedback.json').read_text())['errors']:
        d=next(v for v in after['devices'] if v['id']==e['device']);p=next(v for v in d['peers'] if v['address']==e['observed']['peer']);prefix=e['property'].split(':',1)[1]
        if policy_action(after,p['export'],prefix)!='deny':raise RuntimeError('The target policy still permits the denied public LAN')
    lab.PROBE=PROBE;lab.prepare(out)
    p=out/'plan.json';plan=json.loads(p.read_text());plan.update(version='bgp-H2-policy-repair-lab-v1',scope='one saved-lineage A2 policy-only candidate; all syntax/scope/lab/Batfish/export checks retained')
    for source in [ROOT/'ops/replay_bgp_h2_probe.py',PROBE/'plan.json',PROBE/'repair-scope.json',PROBE/'feedback.json']:plan['source_files'][str(source.relative_to(ROOT))]=lab.sha(source)
    lab.dump(p,plan)
def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('action',choices=['prepare','run']);p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve()
    if a.action=='prepare':prepare(out)
    else:
        if os.geteuid()!=0:raise RuntimeError('Use bash ops/run_bgp_h2_probe_lab.sh in Terminal')
        lab.run(out)
if __name__=='__main__':main()
