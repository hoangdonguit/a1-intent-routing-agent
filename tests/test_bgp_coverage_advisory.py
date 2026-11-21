import unittest,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'ops'))
from bgp_plan_controls import positive
from a1_intent_routing.bgp_hybrid_eval import load_case
from a1_intent_routing.bgp_coverage_advisory import build,nonorigin_signature
from ipaddress import IPv4Interface
class CoverageAdvisoryTest(unittest.TestCase):
    def setUp(self):
        self.public,self.t,_,_=load_case(ROOT,'dev_ebgp_prefix_02');self.plan=positive(self.public,self.t);r2=next(d for d in self.plan['devices'] if d['id']=='R2');r2['originate'].append('192.168.3.0/24');n=next(n for n in self.t.nodes if n.name=='R2')
        gap={'device':'R2','prefix':'192.168.3.0/24','statement':'network 192.168.3.0/24','public_connected_prefixes':[str(IPv4Interface(i.ipv4).network) for i in n.interfaces]}
        self.bf={'tool':'batfish_verifier','status':'environment_error','unsupported':['Transit/nonconnected network origination: calibrated gap'],'errors':[{'status':'environment_error','property':'bgp_origination_coverage','observed':[gap]}]}
        self.result={'status':'environment_error','reports':[{'tool':tool,'status':'pass'} for tool in ['syntax_checker','protocol_scope','lab_ping_tester','bgp_export_tester']]+[self.bf]}
    def test_coverage_is_advisory_not_invalid_network(self):
        before=deepcopy(self.plan);text=build(self.plan,self.t,self.result);self.assertIn('unverified_coverage',text);self.assertIn('not invalid FRR',text);self.assertNotIn('Remove network',text);self.assertEqual(self.plan,before)
    def test_known_lab_or_export_failure_cannot_be_skipped(self):
        for tool in ['lab_ping_tester','bgp_export_tester']:
            r=deepcopy(self.result);next(x for x in r['reports'] if x['tool']==tool)['status']='fail'
            with self.assertRaisesRegex(ValueError,'functional'):build(self.plan,self.t,r)
    def test_parser_or_transport_error_is_never_feedback(self):
        self.bf['errors'].append({'status':'environment_error','property':'initIssues'})
        with self.assertRaisesRegex(ValueError,'coverage-only'):build(self.plan,self.t,self.result)
    def test_unknown_unsupported_feature_is_not_treated_as_origin_gap(self):
        self.bf['unsupported'].append('unsupported feature')
        with self.assertRaisesRegex(ValueError,'Other unsupported'):build(self.plan,self.t,self.result)
    def test_mismatched_gap_or_topology_is_rejected(self):
        self.bf['errors'][0]['observed'][0]['prefix']='203.0.113.0/24'
        with self.assertRaisesRegex(ValueError,'does not match'):build(self.plan,self.t,self.result)
    def test_scope_allows_origin_only_and_preserves_policy_rule_order(self):
        sig=nonorigin_signature(self.plan);p=deepcopy(self.plan);p['devices'][1]['originate']=[];self.assertEqual(nonorigin_signature(p),sig)
        p['devices'][0]['peers'][0]['export']='none';self.assertNotEqual(nonorigin_signature(p),sig)
        p=deepcopy(self.plan);p['policies'][1]['default']='deny';self.assertNotEqual(nonorigin_signature(p),sig)
        p=deepcopy(self.plan);p['devices'].reverse();p['policies'].reverse();self.assertEqual(nonorigin_signature(p),sig)
    def test_a1_literal_and_b1_forbidden(self):
        self.assertEqual(build(self.plan,self.t,self.result,'A1'),'FAIL')
        with self.assertRaises(ValueError):build(self.plan,self.t,self.result,'B1')
if __name__=='__main__':unittest.main()
