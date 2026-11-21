"""Opt-in necessary conditions from public BGP input; not a routing solver.

No oracle/reference I/O, no plan mutation, no acceptance/full-pass verdict.
Policy diagnostics cover only the exact-prefix ordered IR and a calibrated FRR
traditional profile. Nonconnected origin is a coverage warning, never invalid FRR.
"""
from ipaddress import IPv4Interface
from .bgp_plan import validate,PlanError
VERSION='bgp-public-necessary-v1'
PROFILE='frr-10.7.1-traditional-requires-policy-v1'


def policy_action(plan,policy_id,prefix):
    if policy_id=='none':return 'deny'
    policy=next(p for p in plan['policies'] if p['id']==policy_id)
    for rule in policy['rules']:
        if rule['prefix']==prefix:return rule['action']
    return policy['default']


def audit(plan,public,topology,*,profile):
    checks=[];warnings=[]
    def add(node,prop,expected,observed,ok,ids=()):
        checks.append({'device':node,'property':prop,'expected':expected,'observed':observed,'status':'pass' if ok else 'fail','object_ids':list(ids),'tool':'bgp_public_precheck'})
    def result(status=None):
        return {'tool':'bgp_public_precheck','version':VERSION,'profile':profile,'status':status or ('fail' if any(c['status']=='fail' for c in checks) else 'pass'),'checks':checks,'errors':[c for c in checks if c['status']!='pass'],'warnings':warnings,'coverage':['schema/IDs; fixed public ASNs; required direct eBGP peers and activation; required LAN network declarations anywhere; provably blocked BGP transfer in exact-prefix IR'], 'not_verified':['FRR syntax/daemon','route eligibility and convergence','reachability/path/regression','actual advertised routes','full intent'],'pass_means':'necessary checks only; mandatory syntax/Batfish/lab/export checks still required'}
    nodes={n.name:n for n in topology.nodes};routers={n.name for n in topology.nodes if n.kind=='router'}
    try:validate(plan,routers)
    except (PlanError,TypeError,KeyError) as exc:
        add(None,'ir_schema','valid BGP IR',{'message':str(exc),'path':getattr(exc,'path','$')},False);return result()
    spec=public.get('specification',{});bgp=spec.get('bgp',{})
    if profile!=PROFILE or bgp.get('peering_scope')!='all_inter_as_router_links' or bgp.get('peering_endpoints')!='both_ends' or set(bgp.get('asns',{}))!=routers or bgp.get('required_remote_protocol')!='bgp':
        warnings.append({'property':'precheck_coverage','observed':'Uncalibrated profile or public BGP scope; do not infer defaults/peering obligations'})
        return result('environment_error')
    devices={d['id']:d for d in plan['devices']};expected={n:{} for n in routers};interfaces=topology.interfaces
    for link in topology.links:
        for a,b in ((link.a,link.b),(link.b,link.a)):
            if nodes[a.node].kind=='router' and nodes[b.node].kind=='router' and bgp['asns'][a.node]!=bgp['asns'][b.node]:expected[a.node][str(interfaces[b].ip)]=bgp['asns'][b.node]
    active=[]
    for name in sorted(routers):
        d=devices[name];add(name,'fixed_asn',bgp['asns'][name],d['asn'],d['asn']==bgp['asns'][name],[name])
        peers={p['address']:p for p in d['peers']};own={str(IPv4Interface(i.ipv4).ip) for i in nodes[name].interfaces}
        for address,asn in sorted(expected[name].items()):
            p=peers.get(address);ok=p is not None and p['remote_as']==asn and p['ipv4']
            observed=None if p is None else {k:p[k] for k in ['id','address','remote_as','ipv4']}
            add(name,'required_peer:'+address,{'address':address,'remote_as':asn,'ipv4':True,'source':'public all-inter-AS/both-ends constraint'},observed,ok,[name] if p is None else [name,p['id']])
        for p in d['peers']:
            # Direct numeric peers only in this IR/profile; do not silently invent multihop coverage.
            if p['address'] in own:add(name,'self_neighbor:'+p['address'],'remote router address',p['address'],False,[name,p['id']])
            elif p['address'] not in expected[name]:
                warnings.append({'device':name,'property':'extra_peer_coverage','address':p['address'],'object_ids':[name,p['id']]})
            elif p['ipv4']:
                active.append((name,p))
                if p['import']=='none' or p['export']=='none':warnings.append({'device':name,'property':'missing_directional_policy','peer_id':p['id'],'import':p['import'],'export':p['export'],'effective_missing_direction':'deny in calibrated traditional profile; not independently a per-peer intent failure'})
        connected={str(IPv4Interface(i.ipv4).network) for i in nodes[name].interfaces}
        for prefix in d['originate']:
            if prefix not in connected:warnings.append({'device':name,'property':'nonconnected_origination_coverage','prefix':prefix,'object_ids':[name],'meaning':'not invalid FRR; preserve decision and mandatory Batfish v5 coverage guard'})
    if any(w['property']=='extra_peer_coverage' for w in warnings):
        # Unknown sessions may invalidate the global policy impossibility proof.
        if any(c['status']=='fail' for c in checks):return result()
        return result('environment_error')
    banned=set(bgp.get('deny_export_hosts',[]))
    for host in bgp.get('advertise_hosts',[]):
        if host not in nodes or nodes[host].kind!='host' or not nodes[host].interfaces:
            warnings.append({'property':'host_coverage','host':host});return result('environment_error')
        prefix=str(IPv4Interface(nodes[host].interfaces[0].ipv4).network)
        origins=[n for n in sorted(routers) if prefix in devices[n]['originate']]
        add(None,'required_network:'+prefix,'at least one network declaration; location is a model decision',{'origins':origins},bool(origins),origins)
        if host in banned:continue  # No-export itself still requires actual sender/Batfish/lab evidence.
        # If every eBGP direction denies a required prefix, no inter-AS transfer
        # is possible, even granting every candidate origin route eligibility.
        for direction in ['export','import']:
            allowed=[{'device':n,'peer_id':p['id']} for n,p in active if policy_action(plan,p[direction],prefix)=='permit']
            add(None,'all_'+direction+'_blocked:'+prefix,'some eBGP '+direction+' must permit this public required LAN',{'permitting_bindings':allowed,'active_binding_count':len(active),'reason':'all directions deny under calibrated policy semantics' if not allowed else 'necessary condition satisfied'},bool(allowed),[p['id'] for n,p in active] if not allowed else [])
        # A nonlocal, nonorigin router required to learn this LAN cannot do so
        # if every incoming BGP policy rejects it. One permitted import suffices
        # for this necessary check; path availability remains a tool question.
        for name in sorted(routers):
            connected={str(IPv4Interface(i.ipv4).network) for i in nodes[name].interfaces}
            if prefix in connected or name in origins:continue
            incoming=[p for n,p in active if n==name];permitted=[p['id'] for p in incoming if policy_action(plan,p['import'],prefix)=='permit']
            add(name,'all_local_imports_blocked:'+prefix,'at least one incoming policy permits the public remote LAN',{'permitting_peer_ids':permitted,'active_peer_count':len(incoming)},bool(permitted),[name,*[p['id'] for p in incoming]])
    return result()
