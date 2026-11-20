"""Real pinned-FRR syntax and data-plane checks. Batfish is not implemented."""
from dataclasses import asdict, dataclass, field
from datetime import datetime
from ipaddress import IPv4Address, IPv4Network, IPv4Interface
import json
from pathlib import Path
import re
import subprocess
import time
import uuid

from .packet_capture import CaptureSet,CaptureFailure,analyze_paths
from .frr_diagnostics import observation, unresolved_bgp_route_maps

SYNTAX_CHECKER_VERSION = "frr-10.7.1-loaded-policy-refs-v2"


class EnvironmentFailure(RuntimeError):
    pass


@dataclass
class Finding:
    device: str | None
    property: str
    expected: object
    observed: object
    evidence: list[str]
    status: str = 'pass'

    def __post_init__(self):
        if self.status not in ('pass','fail','environment_error'):
            raise ValueError('Unknown verification status')


@dataclass
class Report:
    tool: str
    checks: list[Finding] = field(default_factory=list)
    coverage: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    elapsed_seconds: float | None = None

    @property
    def status(self):
        states = {c.status for c in self.checks}
        if self.unsupported or 'environment_error' in states or not states or any(c.status=='pass' and not c.evidence for c in self.checks):
            return 'environment_error'
        return 'fail' if 'fail' in states else 'pass'

    def to_dict(self):
        result = asdict(self) | {'status': self.status,
                              'errors': [asdict(c) for c in self.checks if c.status != 'pass']}
        if hasattr(self, 'checker_version'):
            result['checker_version'] = self.checker_version
        return result


class Evidence:
    def __init__(self, root, lab_name='a1-triangle3'):
        self.lab_name = lab_name
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.index = 0
        self.last = None

    def save(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
        return str(path)

    def run(self, argv, timeout=15, check=True):
        self.index += 1
        path = self.root / f'{self.index:04d}-command.json'
        self.last = str(path)
        start = time.monotonic()
        try:
            r = subprocess.run([str(a) for a in argv], text=True, capture_output=True,
                               timeout=timeout, check=False)
            record = dict(returncode=r.returncode, stdout=r.stdout, stderr=r.stderr)
        except (OSError, subprocess.TimeoutExpired) as exc:
            def decode(v):
                return v.decode(errors='replace') if isinstance(v, bytes) else v
            record = dict(returncode=None, error=str(exc),
                          stdout=decode(getattr(exc, 'stdout', None)),
                          stderr=decode(getattr(exc, 'stderr', None)))
            r = None
        self.save(path.name, record | dict(argv=[str(a) for a in argv],
                  at=datetime.now().astimezone().isoformat(), seconds=time.monotonic()-start))
        if r is None or (check and r.returncode):
            raise EnvironmentFailure(f'Command failed: {path}')
        return r

    def dexec(self, node, *argv, **kwargs):
        return self.run(['docker', 'exec', f'clab-{self.lab_name}-{node}', *argv], **kwargs)



def parse_interface_state(rows):
    if not isinstance(rows,list):raise EnvironmentFailure('Unsupported ip address JSON shape')
    result={}
    for row in rows:
        if not isinstance(row,dict) or not isinstance(row.get('ifname'),str) or not isinstance(row.get('addr_info'),list):
            raise EnvironmentFailure('Unsupported interface/address record')
        prefixes=[]
        for address in row['addr_info']:
            if address.get('family')=='inet':
                prefixes.append(str(IPv4Interface(str(address['local'])+'/'+str(address['prefixlen']))))
        flags=row.get('flags')
        if not isinstance(flags,list):raise EnvironmentFailure('Unsupported interface flags shape')
        result[row['ifname']]={'prefixes':sorted(prefixes),'up':'UP' in flags and 'LOWER_UP' in flags}
    return result



def parse_bgp_summary(raw):
    if not isinstance(raw,dict):raise EnvironmentFailure('Unsupported FRR BGP summary shape')
    body=raw.get('ipv4Unicast',raw)
    if not isinstance(body,dict) or not isinstance(body.get('peers'),dict) or type(body.get('as')) is not int:
        raise EnvironmentFailure('Unsupported FRR BGP IPv4 summary/ASN shape')
    for peer in body['peers'].values():
        if not isinstance(peer,dict) or not isinstance(peer.get('state'),str):
            raise EnvironmentFailure('Unsupported FRR BGP peer shape')
    return body


def resolve_empty_bgp_summary(raw, running, daemons, all_summary):
    """Resolve only the recorded no-active-IPv4-peer case, never arbitrary {}.

    ASN comes from loaded default-VRF config, not from an empty FRR summary.
    Unknown shapes, absent daemons and other causes remain coverage errors.
    """
    if raw != {}:
        return parse_bgp_summary(raw)
    if 'bgpd' not in daemons.split() or all_summary != {}:
        raise EnvironmentFailure('Empty BGP summary without corroborating daemon/all-AF evidence')
    blocks = re.findall(r'^router bgp (\d+)\n(.*?)(?=^exit$|^router |^end$|\Z)', running, re.M | re.S)
    if len(blocks) != 1:
        raise EnvironmentFailure('Empty BGP summary without one loaded default-VRF instance')
    asn, body = blocks[0]
    if not re.search(r'^ no bgp default ipv4-unicast$', body, re.M):
        raise EnvironmentFailure('Empty BGP summary cause unresolved')
    af = re.findall(r'^ address-family ipv4 unicast\n(.*?)^ exit-address-family$', body, re.M | re.S)
    if len(af) != 1 or re.search(r'^\s+neighbor \S+ activate$', af[0], re.M):
        raise EnvironmentFailure('Empty BGP summary cause unresolved')
    return {'as': int(asn), 'peers': {}, 'source': 'loaded_config_no_active_ipv4_peers'}


def prefix_check_ready(ribs,check):
    if not isinstance(ribs.get(check['node']),dict):raise EnvironmentFailure('Unsupported FRR route table shape')
    entries=ribs[check['node']].get(check['prefix'],[])
    if not isinstance(entries,list):raise EnvironmentFailure('Unsupported FRR route entries shape')
    return any(entry.get('protocol')==check['protocol'] and entry.get('selected') is True for entry in entries)


def diagnostic_failed(result):
    """Parse diagnostics emitted by FRR, never inspect candidate text for syntax."""
    output = result.stdout + result.stderr
    lines = output.splitlines()
    for i, line in enumerate(lines):
        # Exact informational note observed on idempotent mgmtd loads in 10.7.1.
        if (line.strip() == '% Configuration applied with notes:' and i+1 < len(lines)
                and lines[i+1].strip() == 'No changes found to be committed!'):
            continue
        if line.lstrip().startswith('%') or '% Unknown command' in line:
            return True
    return result.returncode != 0 or 'processing failure:' in output


def syntax_checker(configs, topology, lock, evidence):
    start = time.monotonic()
    report = Report('syntax_checker')
    report.checker_version = SYNTAX_CHECKER_VERSION
    routers = {n.name for n in topology.nodes if n.kind == 'router'}
    if set(configs) != routers:
        report.checks.append(Finding(None, 'complete_router_set', sorted(routers), sorted(configs), [evidence.save('router-set.json',{'required':sorted(routers),'observed':sorted(configs)})], 'fail'))
        return report
    image = lock['images']['router']['reference']
    names = []
    try:
        local = json.loads(evidence.run(['docker','image','inspect',image]).stdout)[0]
        if local['Id'] != lock['images']['router']['image_id']:
            raise EnvironmentFailure('Pinned image ID mismatch')
        for node in sorted(routers):
            router = next(n for n in topology.nodes if n.name == node)
            name = f'a1-syntax-{uuid.uuid4().hex[:16]}'
            names.append(name)
            config = Path(configs[node]).resolve()
            shell_config = evidence.root / 'vtysh.conf'
            shell_config.write_text('service integrated-vtysh-config\n')
            r = evidence.run(['docker','run','--rm','--network','none', '--entrypoint','vtysh',
                 '--mount',f'type=bind,src={config},dst=/etc/frr/frr.conf,readonly',
                 '--mount',f'type=bind,src={shell_config},dst=/etc/frr/vtysh.conf,readonly',
                 image,'-C','-f','/etc/frr/frr.conf'], timeout=20, check=False)
            ok = not diagnostic_failed(r)
            parser_environment = r.returncode in (125,126,127) or any(text in r.stdout+r.stderr for text in ("Can't open configuration file",'No such file or directory','Permission denied'))
            report.checks.append(Finding(node,'vtysh_parser','accepted by FRR 10.7.1',
                     observation(r,config.read_text(),router),[evidence.last], 'environment_error' if parser_environment else ('pass' if ok else 'fail')))
            if not ok:
                continue
            # Empty config initially. Load the candidate only after all scoped daemons are ready.
            evidence.run(['docker','run','-d','--name',name,'--network','none',
                 '--cap-add','NET_ADMIN','--cap-add','NET_RAW','--cap-add','SYS_ADMIN',
                 '--label','a1.role=syntax-checker','--entrypoint','/bin/sh',image,'-c',
                 'sed -i "s/^ospfd=no/ospfd=yes/; s/^bgpd=no/bgpd=yes/; s/^vtysh_enable=yes/vtysh_enable=no/" /etc/frr/daemons; '
                 'printf "! isolated syntax environment\\n" > /etc/frr/frr.conf; '
                 'printf "service integrated-vtysh-config\\n" > /etc/frr/vtysh.conf; '
                 'exec /usr/lib/frr/docker-start'], timeout=20)
            deadline = time.monotonic()+20
            while True:
                r = evidence.run(['docker','exec',name,'vtysh','-c','show daemons'], check=False)
                if r.returncode == 0 and {'zebra','staticd','mgmtd','ospfd','bgpd'}.issubset(set(r.stdout.split())):
                    break
                if time.monotonic() >= deadline:
                    raise EnvironmentFailure(f'{node}: isolated daemon readiness timeout')
                time.sleep(.3)
            # Materialize interfaces in this isolated namespace so zebra/bgpd see
            # candidate addresses, including invalid self-neighbors, during load.
            for interface in router.interfaces:
                evidence.run(['docker','exec',name,'ip','link','add',interface.name,'type','dummy'])
                evidence.run(['docker','exec',name,'ip','addr','add',interface.ipv4,'dev',interface.name])
                evidence.run(['docker','exec',name,'ip','link','set',interface.name,'up'])
            evidence.run(['docker','cp',str(config),f'{name}:/tmp/candidate.conf'])
            r = evidence.run(['docker','exec',name,'vtysh','-f','/tmp/candidate.conf'],check=False)
            output = r.stdout+r.stderr
            # A numbered OSPF process requires daemon instance mode. This lab
            # intentionally runs the default instance; FRR's explicit rejection
            # is a candidate incompatibility, not an unavailable daemon.
            instance_rejected = '% OSPF is not running in instance mode' in output
            unsupported = r.returncode in (125,126,127) or (not instance_rejected and any(
                s in output for s in ('is not running','failed to connect','not connected')))
            ok = not diagnostic_failed(r) and not unsupported
            state = 'environment_error' if unsupported else ('pass' if ok else 'fail')
            report.checks.append(Finding(node,'daemon_load',['mgmtd','zebra','staticd','ospfd','bgpd'],
                    observation(r,config.read_text(),router),[evidence.last],state))
            if unsupported:
                report.unsupported.append(f'{node}: requested daemon unavailable')
            running = evidence.run(['docker','exec',name,'vtysh','-c','show running-config'],check=False)
            if ok:
                available = running.returncode == 0 and 'Current configuration:' in running.stdout
                missing = unresolved_bgp_route_maps(running.stdout) if available else None
                report.checks.append(Finding(node,'bgp_policy_references',
                    'all neighbor route-map references resolve after complete load',
                    {'undefined_route_maps':missing,'returncode':running.returncode},[evidence.last],
                    'environment_error' if not available else ('fail' if missing else 'pass')))

            evidence.run(['docker','logs',name],check=False)
        report.coverage = ['FRR 10.7.1 integrated VTYSH parser on every router',
                           'isolated load with fixed topology addresses: mgmtd/zebra/staticd/ospfd/bgpd; no real links or routing correctness',
                           'direct BGP route-map references resolve in final FRR running-config']
    except (EnvironmentFailure, OSError, ValueError) as exc:
        report.checks.append(Finding(None,'syntax_environment','available',str(exc),[evidence.last] if evidence.last else [],'environment_error'))
    finally:
        for name in names:
            try:
                r = evidence.run(['docker','rm','-f',name],check=False)
            except EnvironmentFailure as exc:
                report.checks.append(Finding(name,'syntax_cleanup','removed',str(exc),[evidence.last],'environment_error'))
                continue
            if r.returncode and 'No such container' not in r.stderr:
                report.checks.append(Finding(name,'syntax_cleanup','removed',r.stderr,[evidence.last],'environment_error'))
        report.elapsed_seconds = time.monotonic()-start
        report.artifacts = [evidence.save('syntax-result.json',report.to_dict())]
        evidence.save('syntax-result.json',report.to_dict())
    return report


def parse_traceroute(text, ip_nodes, source, destination_ip):
    """Require one numeric IP at every TTL; stars/unknown addresses are incomplete evidence."""
    nodes = [source]
    reached = False
    for line in text.splitlines():
        if not re.match(r'^\s*\d+\s+',line):
            continue
        addresses = re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b',line)
        if len(set(addresses)) != 1 or '*' in line:
            raise EnvironmentFailure('Incomplete/ambiguous traceroute TTL: '+line)
        address = addresses[0]
        if address not in ip_nodes:
            raise EnvironmentFailure('Traceroute address outside topology: '+address)
        # Do not collapse router loops or a repeated hop.
        nodes.append(ip_nodes[address])
        if address == destination_ip:
            reached = True
            break
    if not reached:
        raise EnvironmentFailure('Traceroute did not reach destination')
    return nodes


def selected_fib(routes, address):
    candidates = [r for r in routes if IPv4Address(address) in IPv4Network(r.get('dst','default').replace('default','0.0.0.0/0'))]
    return max(candidates,key=lambda r:IPv4Network(r.get('dst','default').replace('default','0.0.0.0/0')).prefixlen) if candidates else None


def ecmp_present(fibs, address):
    # Inspect all routers conservatively, including off-path alternatives.
    for routes in fibs.values():
        route = selected_fib(routes,address)
        if route and len(route.get('nexthops',[])) > 1:
            return True
    return False


def parse_ping(result):
    m = re.search(r'(\d+) packets transmitted,\s*(\d+)(?: packets)? received', result.stdout)
    if not m or result.returncode not in (0,1):
        raise EnvironmentFailure('Ping execution/format unavailable')
    return {'sent':int(m[1]),'received':int(m[2]),'reachable':int(m[2])>0}


def routing_check_ready(ribs, check):
    return any(r.get('protocol')==check.protocol and r.get('selected')
               and any(h.get('ip')==check.next_hop and h.get('active') for h in r.get('nexthops',[]))
               for r in ribs.get(check.node,{}).get(check.prefix,[]))


def parse_ospf_neighbors(raw):
    if not isinstance(raw,dict) or not isinstance(raw.get('neighbors'),dict):
        raise EnvironmentFailure('Unsupported FRR OSPF neighbor JSON shape')
    entries=[]
    for group in raw['neighbors'].values():
        if not isinstance(group,list):
            raise EnvironmentFailure('Unsupported OSPF neighbor group')
        for neighbor in group:
            if not isinstance(neighbor,dict) or 'nbrState' not in neighbor or 'ifaceAddress' not in neighbor:
                raise EnvironmentFailure('Incomplete OSPF neighbor metadata')
            entries.append(neighbor)
    return entries


def lab_ping_tester(oracle, topology, evidence, ospf=False, regression_only=False, timeout=60, ospf_spec=None, bgp_spec=None, prefix_checks=()):
    start=time.monotonic(); report=Report('lab_ping_tester')
    routers=[n.name for n in topology.nodes if n.kind=='router']
    ips={i.ipv4.split('/')[0]:n.name for n in topology.nodes for i in n.interfaces}
    try:
        # Candidate IP/admin/forwarding violations are routing/input violations,
        # not infrastructure errors. Docker/API/shape failures still raise separately.
        fixed_failed=False
        for node in (n for n in topology.nodes if n.kind=='router'):
            state=parse_interface_state(json.loads(evidence.dexec(node.name,'ip','-j','-4','address','show').stdout));artifact=evidence.last
            expected_addresses={i.name:[i.ipv4] for i in node.interfaces}
            actual_addresses={name:value['prefixes'] for name,value in state.items() if value['prefixes'] and not (name=='lo' and value['prefixes']==['127.0.0.1/8'])}
            status='pass' if expected_addresses==actual_addresses else 'fail';fixed_failed |= status=='fail'
            report.checks.append(Finding(node.name,'fixed_interface_addresses',expected_addresses,actual_addresses,[artifact],status))
            for iface in node.interfaces:
                actual=state.get(iface.name,{})
                status='pass' if actual.get('up') is True else 'fail';fixed_failed |= status=='fail'
                report.checks.append(Finding(node.name,'interface_up.'+iface.name,True,actual.get('up'),[artifact],status))
            forward=evidence.dexec(node.name,'cat','/proc/sys/net/ipv4/ip_forward').stdout.strip()
            status='pass' if forward=='1' else 'fail';fixed_failed |= status=='fail'
            report.checks.append(Finding(node.name,'ipv4_forwarding','1',forward,[evidence.last],status))
        # Required convergence is bounded; a timeout never becomes pass.
        convergence_timeout=False
        deadline=time.monotonic()+timeout
        previous=None; stable=0
        while True:
            fibs={n:json.loads(evidence.dexec(n,'ip','-j','-4','route','show').stdout) for n in routers}
            neighbors={}; ready=True
            if ospf:
                for node in routers:
                    neighbors[node]=json.loads(evidence.dexec(node,'vtysh','-c','show ip ospf neighbor json').stdout)
                    entries=parse_ospf_neighbors(neighbors[node])
                    ready &= len(entries)==2 and all(str(e['nbrState']).startswith('Full') for e in entries)
            if bgp_spec:
                for node in routers:
                    summary=json.loads(evidence.dexec(node,'vtysh','-c','show bgp ipv4 unicast summary json').stdout)
                    if summary == {}:
                        summary_evidence = [evidence.last]
                        running = evidence.dexec(node,'vtysh','-c','show running-config').stdout
                        summary_evidence.append(evidence.last)
                        daemons = evidence.dexec(node,'vtysh','-c','show daemons').stdout
                        summary_evidence.append(evidence.last)
                        all_summary = json.loads(evidence.dexec(node,'vtysh','-c','show bgp all summary json').stdout)
                        summary_evidence.append(evidence.last)
                        summary = resolve_empty_bgp_summary(summary,running,daemons,all_summary)
                        if not any(c.device==node and c.property=='bgp_ipv4_activation' for c in report.checks):
                            report.checks.append(Finding(node,'bgp_ipv4_activation','active IPv4 unicast peers',
                                summary,summary_evidence,'fail'))
                    parsed_summary=parse_bgp_summary(summary)
                    peers=parsed_summary['peers']
                    expected=sum(1 for l in topology.links if l.a.node==node and l.b.node in routers or l.b.node==node and l.a.node in routers)
                    ready &= len(peers)==expected and all(p.get('state')=='Established' for p in peers.values()) and parsed_summary['as']==bgp_spec['asns'][node]
                    neighbors[node]=summary
            if ospf or bgp_spec:
                converging_ribs={n:json.loads(evidence.dexec(n,'vtysh','-c','show ip route json').stdout) for n in routers}
                ready &= all(routing_check_ready(converging_ribs,check) for check in oracle.routing_checks)
                ready &= all(prefix_check_ready(converging_ribs,check) for check in prefix_checks if check['present'])
            snapshot=json.dumps(fibs,sort_keys=True)
            stable=stable+1 if snapshot==previous and ready else 0
            if stable>=2:
                break
            if time.monotonic()>=deadline:
                convergence_timeout=True;break
            previous=snapshot; time.sleep(1)
        fib_file=evidence.save('converged-kernel-fib.json',fibs)
        neighbor_file=evidence.save('converged-neighbors.json',neighbors)
        report.checks.append(Finding(None,'convergence','stable RIB; OSPF Full when required',
                                    {'neighbors':neighbors,'stable_kernel_fib':snapshot==previous,'protocol_ready':ready,'timeout':convergence_timeout},[fib_file,neighbor_file],'fail' if convergence_timeout else 'pass'))
        if bgp_spec:
            address=topology.interfaces
            for node in routers:
                summary=parse_bgp_summary(neighbors[node])
                report.checks.append(Finding(node,'bgp_local_as',bgp_spec['asns'][node],summary['as'],[neighbor_file],'pass' if summary['as']==bgp_spec['asns'][node] else 'fail'))
                for link in topology.links:
                    for a,b in ((link.a,link.b),(link.b,link.a)):
                        if a.node!=node or b.node not in routers:continue
                        ip=str(address[b].ip);peer=summary['peers'].get(ip,{})
                        expected={'state':'Established','localAs':bgp_spec['asns'][node],'remoteAs':bgp_spec['asns'][b.node]}
                        observed={k:peer.get(k) for k in expected}
                        report.checks.append(Finding(node,'bgp_peer.'+ip,expected,observed,[neighbor_file],'pass' if expected==observed else 'fail'))
        ribs={}; rib_files={}
        for node in routers:
            ribs[node]=json.loads(evidence.dexec(node,'vtysh','-c','show ip route json').stdout)
            rib_files[node]=evidence.last
            evidence.dexec(node,'vtysh','-c','show running-config')
            if ospf:
                interfaces=json.loads(evidence.dexec(node,'vtysh','-c','show ip ospf interface json').stdout)
                interface_file=evidence.save(f'{node}-ospf-interface.json',interfaces)
                values=interfaces.get('interfaces')
                if not isinstance(values,dict):
                    raise EnvironmentFailure('Unsupported FRR OSPF interface JSON shape')
                for iface in next(n.interfaces for n in topology.nodes if n.name==node):
                    state=values.get(iface.name,{})
                    # This pilot's public OSPF intent specifies single area 0 and cost 10.
                    expected={'area':'0.0.0.0','passive':iface.name=='eth3'}
                    if ospf_spec is None:expected['cost']=10
                    elif 'interface_costs' in ospf_spec:expected['cost']=ospf_spec['interface_costs'][node][iface.name]
                    elif 'uniform_link_cost' in ospf_spec:expected['cost']=ospf_spec['uniform_link_cost']
                    observed={'area':state.get('area'),'cost':state.get('cost'),
                              'passive':state.get('timerPassiveIface',False)}
                    good=state.get('ospfEnabled') is True and all(observed.get(k)==v for k,v in expected.items())
                    report.checks.append(Finding(node,'ospf_interface.'+iface.name,expected,observed,
                                                [interface_file],'pass' if good else 'fail'))
        for check in oracle.routing_checks:
            routes=ribs[check.node].get(check.prefix,[])
            good=routing_check_ready(ribs,check)
            report.checks.append(Finding(check.node,'rib',asdict(check),routes,[rib_files[check.node]], 'pass' if good else 'fail'))
            if check.area is not None:
                interfaces=json.loads(evidence.dexec(check.node,'vtysh','-c','show ip ospf interface json').stdout)
                # Validate parsed FRR area metadata, not config strings.
                values=interfaces.get('interfaces',interfaces)
                matches=[v for v in values.values() if isinstance(v,dict) and v.get('area')==check.area]
                good=bool(matches)
                report.checks.append(Finding(check.node,'ospf_area',check.area,interfaces,[evidence.last],'pass' if good else 'fail'))
        for requirement in prefix_checks:
            entries=ribs[requirement['node']].get(requirement['prefix'],[])
            present=any(entry.get('protocol')==requirement['protocol'] and entry.get('selected',False) for entry in entries)
            report.checks.append(Finding(requirement['node'],'prefix:'+requirement['prefix'],requirement,entries,
                [rib_files[requirement['node']]],'pass' if present==requirement['present'] else 'fail'))
        traffic=[('regression',c) for c in oracle.regression_checks]
        if not regression_only:
            traffic=[('intent',c) for c in oracle.checks]+traffic
        for index,(group,check) in enumerate(traffic):
            device=check.source.node
            capture=CaptureSet(evidence,topology,check,index).start()
            try:
                ping=evidence.dexec(device,'ping','-I',check.source.interface,'-t','64','-c','2','-W','2',check.destination.ip,timeout=8,check=False)
                ping_file=evidence.last;parsed=parse_ping(ping)
            finally:capture.stop()
            observations=analyze_paths(capture.results(),check.source.node,check.destination.node,topology)
            packet_files=capture.artifacts();packet_file=evidence.save(f'packet-paths-{index}.json',observations)
            if parsed['reachable'] and not observations['delivered']:
                raise CaptureFailure('Echo replies observed but receiver capture missed the requests; capture evidence unavailable')
            if observations['received_probes']>2:
                raise CaptureFailure('Unexpected concurrent echo requests in the isolated test flow')
            good=observations['delivered']==check.reachability
            if not check.reachability:
                report.unsupported.append(f'{device}: finite capture cannot prove absence of every forwarding path')
                report.checks.append(Finding(device,f'{group}.negative_reachability','proof of no forwarding path',
                                            'finite traffic probes are insufficient',[ping_file,packet_file],'environment_error'))
            report.checks.append(Finding(device,f'{group}.reachability',check.reachability,
                {'directed_delivery':observations['delivered'],'received_probes':observations['received_probes'],'round_trip_ping':parsed},
                [ping_file,packet_file,*packet_files],'pass' if good else 'fail'))
            if not check.required_path and ecmp_present(fibs,check.destination.ip):
                report.unsupported.append(f'{device}: multipath reachability needs all required branch evidence')
                report.checks.append(Finding(device,f'{group}.ecmp',check.ecmp,'multipath detected',
                                            [fib_file,ping_file,packet_file],'environment_error'))
            if check.required_path:
                trace=evidence.dexec(device,'traceroute','-I','-n','-q','1','-m','8','-w','1',
                     '-s',check.source.ip,'-i',check.source.interface,check.destination.ip,timeout=15,check=False)
                trace_file=evidence.last
                diagnostic={'raw':trace.stdout,'role':'diagnostic; reply-route dependence is not forward-path evidence'}
                try:diagnostic['parsed_path']=parse_traceroute(trace.stdout,ips,device,check.destination.ip)
                except EnvironmentFailure as exc:diagnostic['unavailable']=str(exc)
                evidence.save(f'traceroute-diagnostic-{index}.json',diagnostic)
                if not observations['delivered']:
                    report.checks.append(Finding(device,f'{group}.path',list(check.required_path),
                                 {'directed_delivery':False,'captured_paths':observations['paths']},[trace_file,packet_file,*packet_files],'fail'))
                    continue
                if ecmp_present(fibs,check.destination.ip):
                    report.unsupported.append(f'{device}->{check.destination.node}: {check.ecmp} under multipath FIB needs exhaustive data-plane coverage')
                    report.checks.append(Finding(device,f'{group}.ecmp',check.ecmp,'multipath detected',
                                                [trace_file,fib_file,packet_file],'environment_error'))
                    continue
                if observations['evidence_gap'] or not observations['paths']:
                    report.checks.append(Finding(device,f'{group}.path',list(check.required_path),observations,
                                         [trace_file,packet_file,*packet_files],'environment_error'))
                    continue
                matches=[path==list(check.required_path) for path in observations['paths']]
                good=all(matches) if check.ecmp=='all_paths' else any(matches)
                unique=[]
                for path in observations['paths']:
                    if path not in unique:unique.append(path)
                observed=unique[0] if len(unique)==1 else unique
                report.checks.append(Finding(device,f'{group}.path',list(check.required_path),observed,
                                     [trace_file,packet_file,*packet_files],'pass' if good else 'fail'))
        report.coverage=['Directed IPv4 echo-request delivery captured at receiver in owned namespaces',
                         'Passive ingress TTL/path evidence independent of echo reply routes; ICMP traceroute retained diagnostic',
                         'kernel FIB / FRR RIB; single-path all_paths or any_path only',
                         'regression separate from intent','OSPF Full/area/RIB and BGP Established/ASN/prefix when requested']
        if not oracle.regression_checks:
            report.checks.append(Finding(None,'regression_inventory',0,0,[evidence.save('regression-inventory.json',{'required':0})]))
    except (EnvironmentFailure,CaptureFailure,OSError,ValueError,TypeError) as exc:
        report.checks.append(Finding(None,'lab_environment','complete evidence',str(exc),[evidence.last] if evidence.last else [],'environment_error'))
    report.elapsed_seconds=time.monotonic()-start
    report.artifacts=[str(evidence.root/'lab-result.json')]
    evidence.save('lab-result.json',report.to_dict())
    return report
