"""Project-scoped Containerlab lifecycle and real direct-link smoke checks.

No oracle evaluation, model execution, host network configuration or sudo prompt.
"""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / 'labs/triangle3'
TOPO = LAB / 'triangle3.clab.yml'
RUNTIME = ROOT / 'runs/triangle3'
NAME = 'a1-triangle3'
PROJECT = 'a1-intent-routing-agent'


def read(path):
    return json.loads(path.read_text())


def source_hashes():
    paths = [ROOT / 'topologies/triangle3.json']
    for directory in ('data/dev', 'data/oracles/dev', 'reference_configs'):
        paths += [p for p in (ROOT / directory).rglob('*') if p.is_file()]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


class LabError(RuntimeError):
    pass


class Session:
    def __init__(self, action):
        stamp = datetime.now().astimezone().strftime('%Y%m%dT%H%M%S-%f%z')
        self.evidence = RUNTIME / 'evidence' / f'{stamp}-{action}'
        self.evidence.mkdir(parents=True)
        self.index = 0
        self.before = source_hashes()

    def save(self, name, value):
        path = self.evidence / name
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
        # Keep evidence usable by the repository owner after a terminal sudo run.
        owner = ROOT.stat()
        if os.geteuid() == 0:
            os.chown(path, owner.st_uid, owner.st_gid)

    def run(self, argv, timeout=15, check=True):
        self.index += 1
        started = time.monotonic()
        try:
            result = subprocess.run([str(a) for a in argv], cwd=ROOT, text=True,
                                    capture_output=True, timeout=timeout, check=False)
            record = dict(argv=[str(a) for a in argv], returncode=result.returncode,
                          stdout=result.stdout, stderr=result.stderr)
        except (OSError, subprocess.TimeoutExpired) as exc:
            record = dict(argv=[str(a) for a in argv], error=str(exc), returncode=None)
            result = None
        record.update(at=datetime.now().astimezone().isoformat(), seconds=time.monotonic()-started)
        self.save(f'{self.index:03d}-command.json', record)
        if check and (result is None or result.returncode):
            raise LabError(f'Command failed; see {self.evidence}/{self.index:03d}-command.json: {record}')
        return result

    def finish(self, status, detail):
        after = source_hashes()
        unchanged = self.before == after
        self.save('summary.json', dict(at=datetime.now().astimezone().isoformat(), status=status,
                  detail=detail, source_files_unchanged=unchanged,
                  source_hashes_before=self.before, source_hashes_after=after,
                  scope='container/interface/FRR/direct-link smoke only; no intent/oracle verification'))
        print(f'{status}: {detail}\nEvidence: {self.evidence.relative_to(ROOT)}')
        if not unchanged:
            raise LabError('Source input/reference/topology changed during operation')


def plan():
    return read(ROOT / 'topologies/triangle3.json')


def cname(node):
    return f'clab-{NAME}-{node}'


def owned(session, must_exist=False):
    """Refuse collisions, including extra containers bearing this lab name."""
    result = session.run(['docker', 'ps', '-a', '--format', '{{json .}}'])
    expected = {cname(n['name']) for n in plan()['nodes']}
    relevant = [json.loads(line) for line in result.stdout.splitlines()
                if json.loads(line)['Names'].startswith(f'clab-{NAME}-')
                or f'containerlab={NAME}' in json.loads(line).get('Labels', '').split(',')]
    found = set()
    for item in relevant:
        name = item['Names']
        info = json.loads(session.run(['docker', 'inspect', name]).stdout)[0]
        labels = info['Config'].get('Labels') or {}
        if (name not in expected or labels.get('a1.project') != PROJECT
                or labels.get('a1.lab') != plan()['topology_id']
                or labels.get('containerlab') != NAME):
            raise LabError(f'Refusing non-owned/colliding container: {name}')
        found.add(name)
    if must_exist and found != expected:
        raise LabError(f'Expected {len(expected)} owned containers, found {sorted(found)}')
    return found


def binary():
    lock = read(LAB / 'images.lock.json')['containerlab']
    path = ROOT / f'runs/tools/containerlab-{lock["version"]}/containerlab'
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != lock['binary_sha256']:
        raise LabError('Missing/unexpected pinned Containerlab binary; see labs/triangle3/README.md')
    return path


def prepare(session):
    if owned(session):
        raise LabError('Lab exists; use reset to recreate private runtime configs')
    lock = read(LAB / 'images.lock.json')
    binary()
    for item in lock['images'].values():
        image = json.loads(session.run(['docker', 'image', 'inspect', item['reference']]).stdout)[0]
        if image['Id'] != item['image_id']:
            raise LabError('Local image ID differs from images.lock.json')
    image = lock['images']['router']['reference']
    for node in plan()['nodes']:
        if node['kind'] != 'router':
            continue
        directory = RUNTIME / 'config' / node['name']
        directory.mkdir(parents=True, exist_ok=True)
        # Only private runtime copies are overwritten; never bind a source answer.
        shutil.copyfile(ROOT / 'reference_configs/dev_static_01/base' / f'{node["name"]}.conf', directory / 'frr.conf')
        shutil.copyfile(LAB / 'frr/daemons', directory / 'daemons')
        (directory / 'vtysh.conf').write_text('service integrated-vtysh-config\n')
        result = session.run(['docker', 'run', '--rm', '--network', 'none',
                    '--mount', f'type=bind,src={directory},dst=/etc/frr,readonly',
                    '--entrypoint', 'vtysh', image, '-C', '-f', '/etc/frr/frr.conf'], timeout=20)
        if '% Unknown command' in result.stdout + result.stderr:
            raise LabError('FRR dry-run reported unknown command')
    session.save('bootstrap-syntax-scope.json', dict(checked='runtime copies of static base only',
                 note='FRR vtysh dry-run; not complete syntax_checker, reference solution or oracle validation'))


def require_root():
    if os.geteuid() != 0:
        raise LabError('Containerlab needs root for veth/netns. Run in terminal: sudo python3 scripts/lab.py deploy (or reset/destroy). No password is read by this script.')


def destroy(session):
    require_root()
    present = owned(session)
    if present:
        session.run([binary(), 'destroy', '-t', TOPO, '--timeout', '60s'], timeout=120)
    if owned(session):
        raise LabError('Owned containers remain after destroy')


def deploy(session):
    require_root()
    prepare(session)
    session.run([binary(), 'deploy', '-t', TOPO, '--skip-labdir-acl',
                 '--timeout', '90s', '--max-workers', '3'], timeout=180)
    inspect(session)


def inspect(session, candidate_mode=False):
    owned(session, must_exist=True)
    topology = plan()
    for node in topology['nodes']:
        name = cname(node['name'])
        info = json.loads(session.run(['docker', 'inspect', name]).stdout)[0]
        if not info['State']['Running'] or info['HostConfig']['NetworkMode'] != 'none':
            raise LabError(f'{name}: not running or management network unexpectedly attached')
        for iface in node['interfaces']:
            output = session.run(['docker', 'exec', name, 'ip', '-o', '-4', 'address', 'show', 'dev', iface['name']]).stdout
            if (not candidate_mode or node['kind']=='host') and f'inet {iface["ipv4"]} ' not in output:
                raise LabError(f'{name}:{iface["name"]} IP mismatch: {output}')
            link = session.run(['docker', 'exec', name, 'ip', 'link', 'show', 'dev', iface['name']]).stdout
            if not candidate_mode and not ('UP' in link and 'LOWER_UP' in link):
                raise LabError(f'{name}:{iface["name"]} link is not up')
        routes = session.run(['docker', 'exec', name, 'ip', '-4', 'route']).stdout
        forward = session.run(['docker', 'exec', name, 'cat', '/proc/sys/net/ipv4/ip_forward']).stdout.strip()
        if (not candidate_mode or node['kind']=='host') and forward != ('1' if node['kind'] == 'router' else '0'):
            raise LabError(f'{name}: forwarding mismatch')
        if node['kind'] == 'host':
            if f'default via {node["gateway"]} dev eth0' not in routes:
                raise LabError(f'{name}: missing host gateway')
        else:
            if not candidate_mode and 'default ' in routes:
                raise LabError(f'{name}: unexpected default route')
            deadline = time.monotonic() + 30
            while True:
                version = session.run(['docker', 'exec', name, 'vtysh', '-c', 'show version'], check=False)
                if version is not None and version.returncode == 0 and '10.7.1' in version.stdout:
                    break
                if time.monotonic() >= deadline:
                    raise LabError(f'{name}: FRR readiness timeout')
                time.sleep(1)
            daemons = session.run(['docker', 'exec', name, 'vtysh', '-c', 'show daemons']).stdout
            if not {'zebra', 'staticd', 'mgmtd'}.issubset(set(daemons.split())):
                raise LabError(f'{name}: missing bootstrap FRR daemons: {daemons}')
            session.run(['docker', 'exec', name, 'vtysh', '-c', 'show ip route'])
            session.run(['docker', 'logs', '--tail', '100', name])
    if candidate_mode:
        session.save('candidate-infrastructure.json', {'containers_running':True,'physical_interfaces_exist':True,'frr_daemons_ready':True,'candidate_ip_link_forwarding_and_routing':'deferred to property evaluator; not infrastructure errors'})
        return
    interfaces = {(n['name'], i['name']): i['ipv4'].split('/')[0]
                  for n in topology['nodes'] for i in n['interfaces']}
    count = 0
    for link in topology['links']:
        for a, b in ((link['a'], link['b']), (link['b'], link['a'])):
            session.run(['docker', 'exec', cname(a['node']), 'ping', '-I', a['interface'],
                         '-c', '2', '-W', '2', interfaces[(b['node'], b['interface'])]], timeout=10)
            count += 1
    session.save('direct-link-smoke.json', dict(nodes=len(topology['nodes']),links=len(topology['links']),directional_probes=count,
                 passed=True, intent_evaluated=False, management_network='none'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare','deploy','inspect','reset','destroy'])
    args = parser.parse_args(argv)
    session = Session(args.action)
    try:
        if args.action == 'reset':
            destroy(session)
            deploy(session)
        else:
            globals()[args.action](session)
        session.finish('pass', args.action + ' completed within stated smoke/lifecycle scope')
        return 0
    except (LabError, OSError, ValueError) as exc:
        session.finish('environment_error', str(exc))
        return 1


if __name__ == '__main__':
    sys.exit(main())
