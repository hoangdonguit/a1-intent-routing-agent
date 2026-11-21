"""Full unchanged-grader lab check only after origin-only scope + Batfish PASS."""
import argparse,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import replay_bgp_public_probe as lab
from a1_intent_routing.bgp_coverage_advisory import nonorigin_signature
PROBE=ROOT/'runs/bgp-coverage-repair-20261121-01'
SOURCE=ROOT/'runs/bgp-h2-policy-repair-20261121-01'
def prepare(out):
    if not (PROBE/'summary.json').exists():raise RuntimeError('Wait for coverage adaptation to finish')
    summary=json.loads((PROBE/'summary.json').read_text())
    if not summary.get('eligible_for_full_lab'):raise RuntimeError('Scope or offline verification incomplete; no lab yet')
    for name in ['precheck.json','syntax.json','batfish.json']:
        if json.loads((PROBE/name).read_text())['status']!='pass':raise RuntimeError('Mandatory offline report not PASS: '+name)
    spec=json.loads((PROBE/'plan.json').read_text())
    for name,h in spec['source_files'].items():
        if lab.sha(ROOT/name)!=h:raise RuntimeError('Adaptation source drift: '+name)
    if nonorigin_signature(json.loads((SOURCE/'ir.json').read_text()))!=nonorigin_signature(json.loads((PROBE/'ir.json').read_text())):raise RuntimeError('Policies/peers/ASNs changed outside originate-only scope')
    lab.PROBE=PROBE;lab.prepare(out);p=out/'plan.json';plan=json.loads(p.read_text());plan.update(version='bgp-origin-coverage-full-lab-v1',scope='one model-chosen origin-only candidate; unchanged full grader, no fallback or snapshot rewrite')
    for source in [ROOT/'ops/replay_bgp_coverage_probe.py',PROBE/'plan.json',PROBE/'repair-scope.json',PROBE/'feedback.json',PROBE/'batfish.json']:plan['source_files'][str(source.relative_to(ROOT))]=lab.sha(source)
    lab.dump(p,plan)
def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('action',choices=['prepare','run']);p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve()
    if a.action=='prepare':prepare(out)
    else:
        if os.geteuid()!=0:raise RuntimeError('Use bash ops/run_bgp_coverage_probe_lab.sh in Terminal')
        lab.run(out)
if __name__=='__main__':main()
