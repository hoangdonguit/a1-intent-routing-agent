"""FRR snapshots and conservative Batfish checks. PyBatfish is optional at import."""
import json,hashlib
from pathlib import Path
import time
import re

from .frr_diagnostics import unresolved_bgp_route_maps
from .bgp_origin_coverage import origination_gaps, VERSION as ORIGIN_COVERAGE_VERSION

ADAPTER_VERSION = 'frr-cumulus-origination-coverage-v5'


def implicit_policy_projection(text):
    """Represent FRR traditional implicit deny in the Cumulus model only.

    Calibrated against immutable 12 dev lab controls from ebgp-lab-v2. No
    oracle is consulted. Unknown inheritance/defaults remain coverage errors.
    Returns append-only snapshot text and a fully recorded projection plan.
    """
    rows = [line.strip().split() for line in text.splitlines()]
    processes = {r[2] for r in rows if len(r) >= 3 and r[:2] == ['router', 'bgp']}
    if not processes:
        return '', {'supported': True, 'implicit_deny': []}
    reasons = []
    if len(processes) != 1 or not all(p.isdecimal() for p in processes):
        reasons.append('multiple/non-numeric BGP processes')
    if any((r[:2] == ['router', 'bgp'] and len(r) != 3) or
           (r[:2] == ['frr', 'defaults'] and r[2:] != ['traditional']) or
           (r[:2] == ['address-family', 'ipv4'] and r != ['address-family', 'ipv4', 'unicast']) or
           (r and r[0] == 'address-family' and r != ['address-family', 'ipv4', 'unicast']) or
           (r[:2] == ['no', 'neighbor']) or
           (r[:3] == ['no', 'bgp', 'ebgp-requires-policy']) or
           (r[:4] == ['no', 'bgp', 'default', 'ipv4-unicast']) or
           (len(r) >= 3 and r[0] == 'neighbor' and r[2] in ('peer-group', 'prefix-list', 'filter-list', 'distribute-list'))
           for r in rows):
        reasons.append('uncalibrated address-family/default/inherited/alternate/retracted policy')
    peers = [r for r in rows if len(r) >= 3 and r[0] == 'neighbor' and r[2] == 'remote-as']
    if any(len(r) != 4 or not r[3].isdecimal() or not re.fullmatch(r'\d+\.\d+\.\d+\.\d+', r[1]) for r in peers):
        reasons.append('uncalibrated neighbor form')
    name = 'A1_FRR_IMPLICIT_DENY'
    if any(name in r for r in rows):
        reasons.append('reserved projection identifier collision')
    if reasons:
        return '', {'supported': False, 'reasons': reasons, 'implicit_deny': []}
    local_as = next(iter(processes))
    maps = {(r[1], r[4]) for r in rows if len(r) == 5 and r[0] == 'neighbor' and r[2] == 'route-map'}
    missing = sorted({(r[1], direction) for r in peers if r[3] != local_as
                      for direction in ('in', 'out') if (r[1], direction) not in maps})
    if not missing:
        return '', {'supported': True, 'implicit_deny': []}
    extra = ['!', f'route-map {name} deny 10', '!', f'router bgp {local_as}',
             ' address-family ipv4 unicast',
             *[f'  neighbor {peer} route-map {name} {direction}' for peer, direction in missing],
             ' exit-address-family', '!']
    return '\n'.join(extra)+'\n', {'supported': True, 'implicit_deny': [
        {'peer': peer, 'direction': direction} for peer, direction in missing],
        'meaning': 'FRR traditional eBGP default deny when directional policy is absent'}


def bgp_policy_coverage(configs):
    """Conservative coverage guard, not a BGP solver or config normalizer.

    The pinned Cumulus model does not enforce FRR traditional default-policy
    requirements. Direct explicit route maps in both directions are calibrated;
    peer-group inheritance and alternate policy mechanisms need their own probe.
    Keep raw queries and disagreements; never turn this guard into a model fail.
    """
    gaps = []
    for device, path in configs.items():
        lines = [line.strip().split() for line in path.read_text().splitlines()]
        peers = {line[1] for line in lines if len(line) >= 4 and line[0] == 'neighbor' and line[2] == 'remote-as'}
        maps = {(line[1], line[4]) for line in lines if len(line) == 5 and line[0] == 'neighbor' and line[2] == 'route-map'}
        for peer in sorted(peers):
            missing = [direction for direction in ('in', 'out') if (peer, direction) not in maps]
            if missing:
                gaps.append({'device': device, 'peer': peer, 'unmodeled_directions': missing})
    return gaps


def snapshot_name(directory):
    return 'a1-'+hashlib.sha256(str(Path(directory).resolve()).encode()).hexdigest()


def dump(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str)+'\n')


def snapshot(topology,configs,directory,model_default_policy=False):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
    for name in ('configs','hosts','batfish'): (directory/name).mkdir()
    for node in topology.nodes:
        if node.kind=='router':
            # Cumulus wrapper selects the supported FRR grammar. Two explicit lexical
            # normalizations: exit is a delimiter; no shutdown is Active=True,
            # which is independently checked for every interface below.
            original=configs[node.name].read_text()
            converted=[]; changes=[]
            for number,line in enumerate(original.splitlines(),1):
                if line.strip() in ('exit','no shutdown'):
                    changes.append({'line':number,'text':line,'meaning':'context delimiter' if line.strip()=='exit' else 'interface Active=True (checked)'})
                    converted.append('!')
                else: converted.append(line)
            dump(directory/'batfish'/f'{node.name}-normalizations.json',changes)
            extra, projection = implicit_policy_projection(original) if model_default_policy else ('', {'enabled': False})
            dump(directory/'batfish'/f'{node.name}-default-policy-projection.json',projection)
            (directory/'configs'/f'{node.name}.conf').write_text(node.name.lower()+'\n# This file describes the network interfaces\n# ports.conf --\nfrr version 10.7.1\n'+'\n'.join(converted)+'\n'+extra)
        else:
            dump(directory/'hosts'/f'{node.name}.json',{'hostname':node.name.lower(),'hostInterfaces':{
                i.name:{'name':i.name,'prefix':i.ipv4,'gateway':node.gateway} for i in node.interfaces}})
    dump(directory/'batfish/layer1_topology.json',{'edges':[
        {'node1':{'hostname':l.a.node.lower(),'interfaceName':l.a.interface},
         'node2':{'hostname':l.b.node.lower(),'interfaceName':l.b.interface}} for l in topology.links]})
    return directory


def trace_result(rows,expected_path,all_paths=True):
    traces=[t for row in rows for t in row['traces']]
    count=sum(row['count'] for row in rows)
    if count!=len(traces) or not traces:
        return 'environment_error'
    success=[t['disposition']=='ACCEPTED' and (not expected_path or t['path']==[n.lower() for n in expected_path]) for t in traces]
    return 'pass' if (all(success) if all_paths else any(success)) else 'fail'


def verify(topology,oracle,configs,directory,host='127.0.0.1',public_spec=None,prefix_checks=()):
    out=Path(directory);out.mkdir(parents=True,exist_ok=False);started=time.monotonic()
    report={'tool':'batfish_verifier','adapter_version':ADAPTER_VERSION,'status':'environment_error','checks':[],'unsupported':[],'errors':[],'coverage':[]}
    def check(prop,expected,observed,status,artifact,device=None):
        report['checks'].append(dict(device=device,property=prop,expected=expected,observed=observed,status=status,evidence=[str(artifact)]))
    try:
        from pybatfish.client.session import Session
        from pybatfish.datamodel import HeaderConstraints, PathConstraints
        bf=Session(host=host);bf.set_network('a1-intent-routing')
        snap=snapshot(topology,configs,out/'snapshot',model_default_policy=True)
        report['snapshot_name']=snapshot_name(out)
        report['snapshot_hashes']={str(p.relative_to(snap)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(snap.rglob('*')) if p.is_file()}
        if public_spec and 'bgp' in public_spec:
            plans = {n: implicit_policy_projection(p.read_text())[1] for n,p in configs.items()}
            gaps = {n: plan for n,plan in plans.items() if not plan['supported']}
            dump(out/'bgp-policy-coverage.json', {'adapter_version': ADAPTER_VERSION, 'gaps': gaps, 'plans': plans})
            check('bgp_default_policy_coverage', 'calibrated direct IPv4 traditional policy or implicit directional deny',
                  gaps, 'environment_error' if gaps else 'pass', out/'bgp-policy-coverage.json')
            if gaps:
                report['unsupported'].append('FRR default/inherited/alternate BGP policy semantics not calibrated in Cumulus model')
        if public_spec and 'bgp' in public_spec:
            origin_gaps=origination_gaps(topology,configs)
            artifact=out/'bgp-origination-coverage.json'
            dump(artifact,{'adapter_version':ADAPTER_VERSION,'coverage_version':ORIGIN_COVERAGE_VERSION,'gaps':origin_gaps,
                'calibration':'runs/bgp-semantic-calibration-20261118/replay: original/remove-nonconnected/reference-extra-transit contrasts',
                'meaning':'Nonconnected origination is a model coverage limitation, not a candidate syntax error; raw queries and all failed assertions remain'})
            check('bgp_origination_coverage','calibrated directly connected IPv4 network origination',origin_gaps,
                  'environment_error' if origin_gaps else 'pass',artifact)
            if origin_gaps:report['unsupported'].append('Transit/nonconnected network origination: paired FRR/Batfish disagreement observed; raw model predictions not acceptance evidence')
        reference_gaps = {n: unresolved_bgp_route_maps(p.read_text()) for n,p in configs.items()}
        reference_gaps = {n:gaps for n,gaps in reference_gaps.items() if gaps}
        dump(out/'bgp-policy-references.json', {'adapter_version':ADAPTER_VERSION,'undefined_references':reference_gaps})
        check('bgp_policy_reference_coverage', 'defined route-maps for every direct neighbor attachment',
              reference_gaps, 'environment_error' if reference_gaps else 'pass', out/'bgp-policy-references.json')
        if reference_gaps:
            report['unsupported'].append('Undefined neighbor route-maps: FRR/Batfish disagreement observed; predictions not acceptance evidence')
        bf.init_snapshot(str(snap),name=report['snapshot_name'],overwrite=False)
        def query(name,**kw):
            frame=getattr(bf.q,name)(**kw).answer().frame()
            p=out/f'{name}-{len(list(out.glob("*.json")))}.json'
            p.write_text(frame.to_json(orient='records',default_handler=str,indent=2)+'\n')
            return frame,p
        issues,p=query('initIssues');check('initIssues',[],json.loads(p.read_text()),'pass' if issues.empty else 'environment_error',p)
        warnings,p=query('parseWarning');check('parse_warnings',[],json.loads(p.read_text()),'pass' if warnings.empty else 'environment_error',p)
        props,p=query('interfaceProperties',properties='All_Prefixes,Active')
        observed={(str(row.Interface.hostname).lower(),str(row.Interface.interface)):row for row in props.itertuples()}
        for n in topology.nodes:
            for i in n.interfaces:
                row=observed.get((n.name.lower(),i.name));actual=None if row is None else {'active':bool(row.Active),'prefixes':[str(x) for x in row.All_Prefixes]}
                ok=actual is not None and actual['active'] and set(actual['prefixes'])=={i.ipv4}
                check('interface:'+i.name,{'active':True,'prefix':i.ipv4},actual,'pass' if ok else 'fail',p,n.name)
        expected_addresses={(n.name.lower(),i.name):[i.ipv4] for n in topology.nodes for i in n.interfaces}
        actual_addresses={key:sorted(str(x) for x in row.All_Prefixes) for key,row in observed.items() if len(row.All_Prefixes)}
        check('fixed_interface_addresses',str(sorted(expected_addresses.items())),str(sorted(actual_addresses.items())),'pass' if actual_addresses==expected_addresses else 'fail',p)
        edges,p=query('layer3Edges')
        actual_edges={(str(row.Interface),str(row.Remote_Interface)) for row in edges.itertuples()}
        expected_edges={(f'{a.node.lower()}[{a.interface}]',f'{b.node.lower()}[{b.interface}]') for link in topology.links for a,b in ((link.a,link.b),(link.b,link.a))}
        addresses_valid=all(c['status']=='pass' for c in report['checks'] if c['property'].startswith('interface:'))
        topology_status='pass' if actual_edges==expected_edges else ('environment_error' if addresses_valid else 'fail')
        check('layer3_topology',sorted(expected_edges),sorted(actual_edges),topology_status,p)
        routes,p=query('routes')
        if any(r.area is not None for r in oracle.routing_checks) or public_spec and 'ospf' in public_spec:
            ospf,op=query('ospfInterfaceConfiguration')
            inventory={str(row.Interface):row for row in ospf.itertuples()}
            # Scope matches the existing triangle3 dev OSPF oracle and lab check.
            if topology.topology_id!='triangle3':
                report['unsupported'].append('OSPF interface policy outside triangle3 pending calibration')
            else:
                for node in topology.nodes:
                    if node.kind!='router': continue
                    for iface in node.interfaces:
                        row=inventory.get(f'{node.name.lower()}[{iface.name}]')
                        actual=None if row is None else {'area':int(row.OSPF_Area_Name),'cost':int(row.OSPF_Cost),'passive':bool(row.OSPF_Passive),'enabled':bool(row.OSPF_Enabled)}
                        expected={'area':0,'passive':iface.name=='eth3','enabled':True}
                        if not public_spec:expected['cost']=10
                        elif 'interface_costs' in public_spec.get('ospf',{}):expected['cost']=public_spec['ospf']['interface_costs'][node.name][iface.name]
                        elif 'uniform_link_cost' in public_spec.get('ospf',{}):expected['cost']=public_spec['ospf']['uniform_link_cost']
                        check('ospf_interface:'+iface.name,expected,actual,'pass' if actual is not None and all(actual.get(k)==v for k,v in expected.items()) else 'fail',op,node.name)
        for r in oracle.routing_checks:
            selected=routes[(routes.Node.astype(str).str.lower()==r.node.lower()) & (routes.Network.astype(str)==r.prefix)]
            actual=json.loads(selected.to_json(orient='records',default_handler=str))
            ok=any(str(row.get('Protocol','')).lower()==r.protocol and str(row.get('Next_Hop','')).split()[-1:]==[r.next_hop] for row in actual)
            check('route:'+r.prefix,{'protocol':r.protocol,'next_hop':r.next_hop},actual,'pass' if ok else 'fail',p,r.node)
        for requirement in prefix_checks:
            selected=routes[(routes.Node.astype(str).str.lower()==requirement['node'].lower()) & (routes.Network.astype(str)==requirement['prefix'])]
            observed=json.loads(selected.to_json(orient='records',default_handler=str))
            present=any(row['Protocol']==requirement['protocol'] for row in observed)
            check('prefix:'+requirement['prefix'],requirement,observed,'pass' if present==requirement['present'] else 'fail',p,requirement['node'])
        for idx,c in enumerate((*oracle.checks,*oracle.regression_checks)):
            headers=HeaderConstraints(srcIps=c.source.ip,dstIps=c.destination.ip,ipProtocols=['ICMP'])
            reach,rp=query('reachability',pathConstraints=PathConstraints(startLocation=c.source.node.lower()),headers=headers,actions='SUCCESS')
            observed_reach=not reach.empty
            check(f'traffic:{idx}:reachability',c.reachability,observed_reach,'pass' if observed_reach==c.reachability else 'fail',rp,c.source.node)
            traces,tp=query('traceroute',startLocation=c.source.node.lower(),headers=headers,maxTraces=10000)
            rows=[]
            for row in traces.itertuples():
                rows.append({'count':int(row.TraceCount),'traces':[{'disposition':str(t.disposition),'path':[str(h.node) for h in t.hops]} for t in row.Traces]})
            dump(out/f'trace-{idx}.json',rows)
            if c.reachability:
                check(f'traffic:{idx}:path',list(c.required_path),rows,trace_result(rows,c.required_path,c.ecmp=='all_paths'),tp,c.source.node)
        for c in report['checks']:
            if c['property'].startswith('traffic:'):
                c['property_id']=c['property']
        report['coverage']=['initIssues','parseWarning','interfaces','layer3Edges','routes','reachability','traceroute']
        states=[c['status'] for c in report['checks']]
        report['status']='environment_error' if report['unsupported'] or 'environment_error' in states else ('fail' if 'fail' in states else 'pass')
    except Exception as exc:
        # Keep API/version/parse errors as infrastructure, never a routing failure.
        check('batfish_environment','available calibrated model',f'{type(exc).__name__}: {exc}','environment_error',out/'report.json')
    report['errors']=[c for c in report['checks'] if c['status']!='pass']
    report['elapsed_seconds']=time.monotonic()-started
    dump(out/'report.json',report)
    return report
