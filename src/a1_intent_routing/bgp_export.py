"""Opt-in export acceptance: sender Adj-RIB-Out AND peer-mapped Batfish policy.

Receiver main-RIB absence is deliberately NOT an export assertion.
"""
from ipaddress import IPv4Interface,IPv4Network
import json,re
from .verifiers import diagnostic_failed,EnvironmentFailure,parse_bgp_summary
VERSION='sender-export-grader-v1'


def advertised_prefixes(raw):
    if not isinstance(raw,dict) or not isinstance(raw.get('advertisedRoutes'),dict) or type(raw.get('totalPrefixCounter')) is not int:
        raise EnvironmentFailure('Unrecognized advertised-routes JSON; empty object is not evidence')
    for prefix in raw['advertisedRoutes']:IPv4Network(prefix)
    if raw['totalPrefixCounter']<len(raw['advertisedRoutes']):raise EnvironmentFailure('Inconsistent advertised route counters')
    return set(raw['advertisedRoutes'])


def bgp_prefixes(raw):
    if not isinstance(raw,dict) or not isinstance(raw.get('routes'),dict):raise EnvironmentFailure('Unrecognized BGP RIB JSON')
    return set(raw['routes'])


def check_exports(topology,spec,evidence,bf):
    report={'tool':'bgp_export_tester','grader_version':VERSION,'checks':[],'errors':[],'unsupported':[],'status':'environment_error'}
    def add(node,prop,expected,observed,status,files):
        report['checks'].append({'device':node,'property':prop,'property_id':node+':'+prop,'expected':expected,'observed':observed,'status':status,'evidence':files})
    def cli(node,command):
        result=evidence.dexec(node,'vtysh','-c',command,check=False);file=evidence.last
        if diagnostic_failed(result):raise EnvironmentFailure('Unsupported FRR diagnostic command: '+command)
        try:return json.loads(result.stdout),file
        except ValueError as exc:raise EnvironmentFailure('FRR diagnostic is not JSON: '+command) from exc
    banned=spec.get('bgp',{}).get('deny_export_hosts',[])
    if not banned:
        file=evidence.save('not-applicable.json',{'deny_export_hosts':[]});add('all','export_scope',[],[],'pass',[file]);report['status']='pass';return report
    try:
        from pybatfish.datamodel.route import BgpRoute
        frame=bf.q.bgpPeerConfiguration().answer().frame();file=evidence.save('bf-peer-bindings.json',json.loads(frame.to_json(orient='records',default_handler=str)))
        bindings=json.loads(frame.to_json(orient='records',default_handler=str));nodes={n.name:n for n in topology.nodes};interfaces=topology.interfaces
        for host in banned:
            prefix=str(IPv4Interface(nodes[host].interfaces[0].ipv4).network)
            origins=set();available=set();source_files=[]
            for node in (n for n in topology.nodes if n.kind=='router'):
                rib,rf=cli(node.name,'show bgp ipv4 unicast json');source_files.append(rf)
                running=evidence.dexec(node.name,'vtysh','-c','show running-config',check=False);source_files.append(evidence.last)
                if diagnostic_failed(running) or 'Current configuration:' not in running.stdout:raise EnvironmentFailure('Running config unavailable')
                if prefix in re.findall(r'^\s*network (\S+)\s*$',running.stdout,re.M):origins.add(node.name)
                if prefix in bgp_prefixes(rib):available.add(node.name)
            add('all','origination_available:'+prefix,True,{'declared_origins':sorted(origins),'bgp_rib_nodes':sorted(available)},'pass' if origins.intersection(available) else 'fail',source_files)
            for link in topology.links:
                for a,b in ((link.a,link.b),(link.b,link.a)):
                    if nodes[a.node].kind!='router' or nodes[b.node].kind!='router':continue
                    if spec['bgp']['asns'][a.node]==spec['bgp']['asns'][b.node]:continue
                    peer=str(interfaces[b].ip);summary,sf=cli(a.node,'show bgp ipv4 unicast summary json');state=parse_bgp_summary(summary)['peers'].get(peer,{}).get('state')
                    if state!='Established':
                        add(a.node,'advertised:'+peer+':'+prefix,False,{'peer_state':state},'fail',[sf]);continue
                    raw,af=cli(a.node,'show bgp ipv4 unicast neighbors '+peer+' advertised-routes json');prefixes=advertised_prefixes(raw)
                    add(a.node,'advertised:'+peer+':'+prefix,False,{'advertised':prefix in prefixes,'total':raw['totalPrefixCounter']},'fail' if prefix in prefixes else 'pass',[af,sf])
                    match=[x for x in bindings if x['Node'].lower()==a.node.lower() and str(x['Remote_IP'])==peer]
                    if len(match)!=1:raise EnvironmentFailure('Cannot uniquely bind sender/peer to Batfish policy')
                    policies=match[0]['Export_Policy']
                    if not isinstance(policies,list) or len(policies)!=1:raise EnvironmentFailure('Only a single bound export policy is calibrated')
                    local=str(interfaces[a].ip)
                    route=BgpRoute(network=prefix,originatorIp=local,originType='igp',protocol='bgp',sourceProtocol='connected',nextHopIp=local,localPreference=100)
                    result=bf.q.testRoutePolicies(nodes=a.node.lower(),policies=policies[0],direction='out',inputRoutes=[route]).answer().frame()
                    rows=json.loads(result.to_json(orient='records',default_handler=str));pf=evidence.save('policy-'+a.node+'-'+peer+'-'+host+'.json',{'binding':match[0],'direction':'out','input_prefix':prefix,'rows':rows})
                    valid=len(rows)==1 and rows[0].get('Node','').lower()==a.node.lower() and rows[0].get('Policy_Name')==policies[0] and rows[0].get('Action') in ('PERMIT','DENY')
                    if not valid:raise EnvironmentFailure('Unrecognized testRoutePolicies result')
                    required=a.node in origins
                    add(a.node,('export_policy:' if required else 'policy_probe:')+peer+':'+prefix,'DENY' if required else 'diagnostic: valid mapped OUT policy result',rows[0]['Action'],'pass' if not required or rows[0]['Action']=='DENY' else 'fail',[file,pf])
        states=[c['status'] for c in report['checks']];report['status']='fail' if 'fail' in states else 'pass'
    except Exception as exc:
        f=evidence.save('export-environment.json',{'error':f'{type(exc).__name__}: {exc}'})
        add('all','export_coverage','validated FRR/API evidence',str(exc),'environment_error',[f]);report['unsupported'].append(str(exc))
    report['errors']=[x for x in report['checks'] if x['status']!='pass'];return report
