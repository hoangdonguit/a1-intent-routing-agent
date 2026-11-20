"""Project-owned six-router lifecycle; refuse simultaneous triangle3. Terminal sudo required."""
import argparse,hashlib,importlib.util,json,os,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from a1_intent_routing.contracts import Topology
from a1_intent_routing.verifiers import syntax_checker,Evidence
spec=importlib.util.spec_from_file_location('six_lifecycle',ROOT/'scripts/lab.py');lab=importlib.util.module_from_spec(spec);spec.loader.exec_module(lab)
lab.LAB=ROOT/'labs/sixrouter';lab.TOPO=lab.LAB/'sixrouter.clab.yml';lab.RUNTIME=ROOT/'runs/sixrouter';lab.NAME='a1-sixrouter'
lab.plan=lambda:json.loads((ROOT/'topologies/sixrouter.json').read_text())
def hashes():
 paths=[ROOT/'topologies/sixrouter.json',*sorted((ROOT/'data/benchmark').rglob('*'))]
 return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
lab.source_hashes=hashes

def prepare(session):
 if lab.owned(session):raise lab.LabError('Six-router lab exists; reset required')
 lock=json.loads((lab.LAB/'images.lock.json').read_text());lab.binary()
 for item in lock['images'].values():
  image=json.loads(session.run(['docker','image','inspect',item['reference']]).stdout)[0]
  if image['Id']!=item['image_id']:raise lab.LabError('Image ID mismatch')
 source=ARGS.configs.resolve()
 topology=Topology.from_dict(lab.plan())
 configs={n.name:source/f'{n.name}.conf' for n in topology.nodes if n.kind=='router'}
 report=syntax_checker(configs,topology,lock,Evidence(session.evidence/'syntax'))
 session.save('syntax.json',report.to_dict())
 if report.status!='pass':raise lab.LabError('Candidate syntax gate failed; lab not deployed')
 for node in configs:
  directory=lab.RUNTIME/'config'/node;directory.mkdir(parents=True,exist_ok=True)
  shutil.copyfile(configs[node],directory/'frr.conf')
  daemons=(ROOT/'labs/triangle3/frr/daemons').read_text().replace('bgpd=no','bgpd=yes').replace('ospfd=no','ospfd=yes')
  (directory/'daemons').write_text(daemons);(directory/'vtysh.conf').write_text('service integrated-vtysh-config\n')
lab.prepare=prepare
original_inspect=lab.inspect
lab.inspect=lambda session:original_inspect(session,candidate_mode=ARGS.action in ('deploy','reset'))
original_deploy=lab.deploy
def deploy_loaded(session):
 original_deploy(session)
 import time
 from a1_intent_routing.verifiers import diagnostic_failed
 for node in (n['name'] for n in lab.plan()['nodes'] if n['kind']=='router'):
  deadline=time.monotonic()+30
  while True:
   result=session.run(['docker','exec',lab.cname(node),'vtysh','-c','show daemons'],check=False)
   if result.returncode==0 and {'mgmtd','zebra','staticd','ospfd','bgpd'}.issubset(set(result.stdout.split())):break
   if time.monotonic()>=deadline:raise lab.LabError('Required FRR daemon readiness timeout on '+node)
   time.sleep(.5)
  result=session.run(['docker','exec',lab.cname(node),'vtysh','-b'],check=False)
  if diagnostic_failed(result):raise lab.LabError('Checked candidate failed to load on '+node)
 lab.inspect(session)
lab.deploy=deploy_loaded
p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['deploy','reset','inspect','destroy']);p.add_argument('--configs',type=Path,default=ROOT/'data/benchmark/dev/dev_ebgp_prefix_01/reference');ARGS=p.parse_args()
# Read-only sequential-lab guard. Never destroy triangle3 or another project's containers here.
import subprocess
if ARGS.action in ('deploy','reset'):
 running=subprocess.check_output(['docker','ps','--format','{{.Names}}'],text=True).splitlines()
 if any(n.startswith('clab-a1-triangle3-') for n in running):raise SystemExit('Destroy triangle3 with its own runner before sixrouter; other labs untouched')
session=lab.Session('six-'+ARGS.action)
try:
 if ARGS.action=='reset':lab.destroy(session);lab.deploy(session)
 else:getattr(lab,ARGS.action)(session)
 session.finish('pass','sixrouter '+ARGS.action+' infrastructure only; candidate properties evaluated separately')
except Exception as exc:session.finish('environment_error',str(exc));sys.exit(2)
