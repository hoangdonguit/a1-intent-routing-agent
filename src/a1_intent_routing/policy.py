"""Protocol-scope checks over candidates already accepted by FRR syntax checker."""
from ipaddress import IPv4Interface,IPv4Network

PROTOCOL_SCOPE_VERSION = "protocol-public-peer-asn-v2"

def check_protocols(topology,configs,allowed,fixed_asns=None):
    connected={n.name:{str(IPv4Interface(i.ipv4).network) for i in n.interfaces} for n in topology.nodes if n.kind=='router'}
    checks=[]
    # Only verify declared numeric peers whose direct physical endpoint is known.
    # This does not infer a missing peer, inheritance or multihop configuration.
    nodes={n.name:n for n in topology.nodes}
    peer_asns={}
    if fixed_asns:
        for link in getattr(topology,'links',()):
            for local,remote in ((link.a,link.b),(link.b,link.a)):
                if nodes[local.node].kind!='router' or nodes[remote.node].kind!='router':continue
                interface=next(i for i in nodes[remote.node].interfaces if i.name==remote.interface)
                address=str(IPv4Interface(interface.ipv4).ip)
                peer_asns.setdefault(local.node,{})[address]=fixed_asns[remote.node]

    for node,path in configs.items():
        violations=[]
        for num,line in enumerate(path.read_text().splitlines(),1):
            w=line.split()
            if w[:2]==['router','ospf'] and 'ospf' not in allowed:violations.append({'line':num,'protocol':'ospf'})
            if w[:2]==['router','bgp'] and 'bgp' not in allowed:violations.append({'line':num,'protocol':'bgp'})
            if w[:2]==['ip','route'] and 'static' not in allowed:
                # A prohibited static route cannot be used to help an OSPF/BGP case.
                violations.append({'line':num,'protocol':'static','statement':line})
        if fixed_asns is not None:
            asns=[]
            for line in path.read_text().splitlines():
                words=line.split()
                if words[:2]==['router','bgp'] and len(words)>2:asns.append(words[2])
                if words[:1]==['neighbor'] and 'local-as' in words:violations.append({'property':'fixed_asn','statement':line})
            if set(asns)!={str(fixed_asns[node])}:violations.append({'property':'fixed_asn','expected':fixed_asns[node],'observed':asns})
        if fixed_asns:
            for number,line in enumerate(path.read_text().splitlines(),1):
                words=line.split()
                if len(words)==4 and words[0]=='neighbor' and words[2]=='remote-as' and words[3].isdecimal():
                    expected=peer_asns.get(node,{}).get(words[1])
                    if expected is not None:
                        observed=int(words[3])
                        checks.append({'device':node,'property':'bgp_peer_asn',
                            'expected':{'peer':words[1],'remote_as':expected,'source':'public topology and fixed_asns'},
                            'observed':{'remote_as':observed,'line':number},'evidence':[str(path)],
                            'status':'pass' if observed==expected else 'fail'})
        checks.append({'device':node,'property':'allowed_protocols','expected':allowed,'observed':violations,'evidence':[str(path)],'status':'fail' if violations else 'pass'})
    return {'tool':'protocol_scope','checker_version':PROTOCOL_SCOPE_VERSION,'coverage':['declared numeric remote-as on known direct physical router links; other peer forms left to mandatory lab'],'status':'fail' if any(c['status']=='fail' for c in checks) else 'pass','checks':checks,'errors':[c for c in checks if c['status']=='fail'],'unsupported':[]}
