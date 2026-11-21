"""Feedback from actual sender advertisements + mapped OUT-policy evidence.

A known export failure can be repairable while the aggregate verdict remains a
coverage environment_error. Never treat the coverage advisory itself as FAIL.
"""
from ipaddress import IPv4Interface
import json
from .bgp_public_precheck import policy_action
VERSION='bgp-observed-export-feedback-v1'
def policy_invariant(plan):
    return sorted((d['id'],d['asn'],tuple(sorted(d['originate'])),tuple(sorted((p['id'],p['address'],p['remote_as'],p['ipv4']) for p in d['peers']))) for d in plan['devices'])
def build(plan,public,topology,report,witnesses,method='A2'):
    if report.get('status')!='fail' or report.get('tool')!='bgp_export_tester' or report.get('unsupported'):raise ValueError('Need a supported observed export failure')
    nodes={n.name:n for n in topology.nodes};denied={str(IPv4Interface(nodes[h].interfaces[0].ipv4).network) for h in public['specification']['bgp']['deny_export_hosts']}
    checks=report['checks'];errors=[]
    for c in checks:
        parts=c['property'].split(':')
        if len(parts)!=3 or parts[0]!='export_policy' or c['status']!='fail' or c['observed']!='PERMIT' or parts[2] not in denied:continue
        peer,prefix=parts[1:];device=c['device'];d=next(x for x in plan['devices'] if x['id']==device)
        if prefix not in d['originate']:raise ValueError('Origin evidence does not match candidate')
        p=next(x for x in d['peers'] if x['address']==peer)
        advertised=next((x for x in checks if x['device']==device and x['property']=='advertised:'+peer+':'+prefix),None)
        if advertised is None or advertised['status']!='fail' or advertised['observed'].get('advertised') is not True:raise ValueError('Policy PERMIT alone is not actual advertisement evidence')
        w=witnesses.get((device,c['property']))
        if not isinstance(w,dict):raise ValueError('Missing peer-bound policy evidence')
        if policy_action(plan,p['export'],prefix)!='permit':raise ValueError('IR policy and observed policy evidence disagree')
        binding=w['binding'];rows=w['rows'];expected='IR_'+p['export']
        if w['direction']!='out' or w['input_prefix']!=prefix or binding['Node'].lower()!=device.lower() or str(binding['Remote_IP'])!=peer or binding['Export_Policy']!=[expected] or len(rows)!=1 or rows[0]['Node'].lower()!=device.lower() or rows[0]['Policy_Name']!=expected or rows[0]['Action']!='PERMIT':raise ValueError('Peer-bound OUT witness mismatch; never guess policy mapping')
        errors.append({'device':device,'property':'deny_export:'+prefix,'expected':{'advertised':False,'source':'public deny_export_hosts'},'observed':{'advertised':True,'peer':peer,'bound_out_policy':rows[0]['Policy_Name'],'policy_action':'PERMIT'},'object_ids':[device,p['id'],p['export']]})
    if not errors:raise ValueError('No proven origin export failure; no generation eligible')
    if method=='A1':return 'FAIL'
    if method!='A2':raise ValueError('B1 receives no repair feedback')
    return json.dumps({'status':'fail','feedback_version':VERSION,'instruction':'Correct the observed export violations while preserving all public intent constraints and the reachability and convergence already satisfied. This diagnostic permits policy definitions and peer import/export bindings to change only. Keep device/peer IDs, ASNs, peer addresses, activation and originate statements unchanged. Return the complete IR JSON only.','errors':errors[:6]},ensure_ascii=False,separators=(',',':'))
