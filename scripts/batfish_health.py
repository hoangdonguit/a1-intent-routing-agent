"""Pinned Batfish startup and bounded real-query readiness; never calls Qwen/lab."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from a1_intent_routing.batfish import snapshot
from a1_intent_routing.contracts import Topology
from a1_intent_routing.evaluator_health import require_batfish
from a1_intent_routing.run_lock import acquire


def save(path, data):
    path.write_text(json.dumps(data, indent=2, default=str)+'\n')


def pinned_container(config):
    data = json.loads(subprocess.check_output(['docker','inspect','a1-batfish'], text=True, timeout=15))[0]
    image = json.loads(subprocess.check_output(['docker','image','inspect',config['image']], text=True, timeout=15))[0]
    if data['Config']['Image'] != config['image'] or data['Image'] != image['Id']:
        raise RuntimeError('Existing Batfish container/image differs from pinned digest; no recreate/pull')
    bindings = data['HostConfig']['PortBindings'].get('9996/tcp', [])
    if not any(b.get('HostIp') == config['host'] and b.get('HostPort') == str(config['port']) for b in bindings):
        raise RuntimeError('Batfish loopback endpoint differs from config')
    return data


def query(out, config):
    from pybatfish.client.session import Session
    data = pinned_container(config)
    if not data['State']['Running']:
        raise RuntimeError('Pinned Batfish container is stopped')
    bf = Session(host=config['host'], port=config['port'], timeout=10)
    versions = bf.get_component_versions()
    if config['tag'].removeprefix('test-') not in json.dumps(versions):
        raise RuntimeError('Unexpected Batfish version: '+str(versions))
    directory=ROOT/'data/benchmark/dev/dev_static_01'
    public=json.loads((directory/'public.json').read_text())
    topology=Topology.from_dict(json.loads((directory/public['topology']).read_text()))
    reference = ROOT/'data/benchmark/dev/dev_static_01/reference'
    configs = {p.stem:p for p in reference.glob('*.conf')}
    snap = snapshot(topology, configs, out/'snapshot')
    bf.set_network('a1-operational-readiness')
    name = 'health-'+hashlib.sha256(str(out.resolve()).encode()).hexdigest()
    bf.init_snapshot(str(snap), name=name, overwrite=False)
    issues = bf.q.initIssues().answer().frame()
    routes = bf.q.routes().answer().frame()
    save(out/'initIssues.json', json.loads(issues.to_json(orient='records',default_handler=str)))
    save(out/'routes.json', json.loads(routes.to_json(orient='records',default_handler=str)))
    nodes = set(routes.Node.astype(str).str.lower()) if not routes.empty else set()
    if not issues.empty or not {'r1','r2','r3'} <= nodes or '192.168.1.0/24' not in set(routes.Network.astype(str)):
        raise RuntimeError('Reference initIssues/routes readiness assertion failed')
    return {'status':'pass','at':datetime.datetime.now().astimezone().isoformat(),'euid':os.geteuid(),
            'interpreter':sys.executable,'endpoint':f"{config['host']}:{config['port']}", 'versions':versions,
            'image_reference':data['Config']['Image'],'image_id':data['Image'],'container_id':data['Id'],
            'snapshot_name':name,'route_rows':len(routes),'reference':'dev_static_01',
            'scope':'real initIssues+routes; infrastructure readiness, not full lab validation'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--query',action='store_true');p.add_argument('--start',action='store_true');p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.query == a.start:p.error('Choose --query or --start')
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    config=json.loads((ROOT/'configs/batfish.json').read_text())
    try:
        if a.query:
            save(out/'report.json',query(out,config));return 0
        # Startup is explicit; benchmark calls readiness only and never silently restarts.
        with acquire(ROOT):
            data=pinned_container(config);save(out/'container-before.json',data)
            if not data['State']['Running']:
                result=subprocess.run(['docker','start','a1-batfish'],capture_output=True,text=True,timeout=30)
                save(out/'start.json',{'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
                result.check_returncode()
            deadline=time.monotonic()+120;attempt=0
            while True:
                try:
                    report=require_batfish(ROOT,out/f'attempt-{attempt}',timeout=30)
                    save(out/'report.json',{'status':'pass','query':report,'attempts':attempt+1});return 0
                except RuntimeError:
                    if time.monotonic() >= deadline:raise
                    attempt+=1;time.sleep(2)
    except Exception as exc:
        save(out/'report.json',{'status':'environment_error','error':f'{type(exc).__name__}: {exc}', 'euid':os.geteuid()});print(str(exc),file=sys.stderr);return 2


if __name__=='__main__':
    sys.exit(main())
