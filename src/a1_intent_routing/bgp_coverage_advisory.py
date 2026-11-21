"""Opt-in coverage-directed adaptation, never a claim of invalid FRR routing."""
from copy import deepcopy
from ipaddress import IPv4Interface
import json
from .bgp_plan import digest
VERSION='bgp-origination-coverage-advisory-v1'
def nonorigin_signature(plan):
    x=deepcopy(plan)
    for d in x['devices']:
        d['originate']=[];d['peers']=sorted(d['peers'],key=lambda p:p['id'])
    x['devices']=sorted(x['devices'],key=lambda d:d['id']);x['policies']=sorted(x['policies'],key=lambda p:p['id'])
    return digest(x)
def build(plan,topology,result,method='A2'):
    reports={r['tool']:r for r in result.get('reports',[])}
    required=['syntax_checker','protocol_scope','lab_ping_tester','bgp_export_tester']
    if result.get('status')!='environment_error' or any(reports.get(t,{}).get('status')!='pass' for t in required):raise ValueError('Require all functional tools pass and aggregate coverage error')
    bf=reports.get('batfish_verifier',{});env=[e for e in bf.get('errors',[]) if e.get('status')=='environment_error']
    if bf.get('status')!='environment_error' or len(env)!=1 or env[0]['property']!='bgp_origination_coverage':raise ValueError('Not a coverage-only exception; never ask model to fix outage/parser error')
    unsupported=bf.get('unsupported',[])
    if len(unsupported)!=1 or not unsupported[0].startswith('Transit/nonconnected network origination:'):raise ValueError('Other unsupported features need independent calibration')
    devices={d['id']:d for d in plan['devices']};nodes={n.name:n for n in topology.nodes};advisories=[]
    for gap in env[0]['observed']:
        name=gap['device'];prefix=gap['prefix'];connected={str(IPv4Interface(i.ipv4).network) for i in nodes[name].interfaces}
        if prefix not in devices[name]['originate'] or prefix in connected or gap['statement'].split()!=['network',prefix] or set(gap['public_connected_prefixes'])!=connected:raise ValueError('Coverage observation does not match source plan/public topology')
        advisories.append({'device':name,'property':'bgp_origination_coverage','observed_statement':gap['statement'],'prefix':prefix,'calibrated_origination_form':'exact public connected IPv4 prefix','meaning':'This is not invalid FRR: the pinned verifier has uncalibrated semantics for this origin form. Original verdict remains environment_error.','object_ids':[name]})
    if not advisories:raise ValueError('No coverage advisory')
    if method=='A1':return 'FAIL'
    if method!='A2':raise ValueError('B1 gets no generation feedback')
    return json.dumps({'status':'unverified_coverage','feedback_version':VERSION,'instruction':'Stage changed: adapt the plan to a semantically equivalent configuration within the verifier calibrated coverage, preserving all public intent constraints and the lab/export behavior already verified. The previous policy-only scope no longer applies. For this response ONLY originate arrays may change. Keep every device/peer ID, ASN, address, activation, import/export binding and complete policy definition unchanged. Preserve the required LAN advertisements. Do not interpret a coverage advisory as an invalid routing statement. Return complete IR JSON only.','functional_checks':'syntax, scope, full lab and sender-export passed; no new intent failure is asserted','coverage_advisories':advisories},ensure_ascii=False,separators=(',',':'))
