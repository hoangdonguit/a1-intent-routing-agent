import unittest,json,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'ops'))
from bgp_plan_controls import positive
from a1_intent_routing.bgp_hybrid_eval import load_case
from a1_intent_routing.bgp_plan import render
from a1_intent_routing.bgp_public_precheck import audit,policy_action,PROFILE
from a1_intent_routing.bgp_public_feedback import feedback
class PublicPrecheckTest(unittest.TestCase):
    def setUp(self):
        self.public,self.t,self.base,_=load_case(ROOT,'dev_ebgp_prefix_02');self.plan=positive(self.public,self.t)
    def check(self,p=None):return audit(self.plan if p is None else p,self.public,self.t,profile=PROFILE)
    def test_positive_pass_only_means_necessary_conditions(self):
        r=self.check();self.assertEqual(r['status'],'pass');self.assertIn('full intent',r['not_verified'])
    def test_missing_required_peer_is_located_without_adding_it(self):
        p=deepcopy(self.plan);removed=p['devices'][0]['peers'].pop();r=self.check(p)
        self.assertEqual(r['status'],'fail');self.assertTrue(any(e['property']=='required_peer:'+removed['address'] for e in r['errors']));self.assertEqual(len(p['devices'][0]['peers']),1)
    def test_wrong_asn_self_neighbor_and_inactive_peer_fail(self):
        for mutate in [lambda p:p['devices'][0].update(asn=999),lambda p:p['devices'][0]['peers'][0].update(address='192.168.1.1'),lambda p:p['devices'][0]['peers'][0].update(ipv4=False)]:
            p=deepcopy(self.plan);mutate(p);self.assertEqual(self.check(p)['status'],'fail')
    def test_all_exports_missing_fails_before_coverage_but_does_not_fix_them(self):
        p=deepcopy(self.plan)
        for d in p['devices']:
            for peer in d['peers']:peer['export']='none'
        p['devices'][1]['originate'].append('192.168.3.0/24');before=deepcopy(p);r=self.check(p)
        self.assertTrue(any(e['property'].startswith('all_export_blocked:') for e in r['errors']));self.assertTrue(any(w['property']=='nonconnected_origination_coverage' for w in r['warnings']));self.assertEqual(p,before)
    def test_one_missing_export_policy_is_not_independently_failure(self):
        self.plan['devices'][0]['peers'][0]['export']='none';self.assertEqual(self.check()['status'],'pass')
    def test_all_local_imports_blocked_on_nonlocal_router_fails(self):
        for p in self.plan['devices'][0]['peers']:p['import']='none'
        self.assertTrue(any(e['property']=='all_local_imports_blocked:192.168.3.0/24' for e in self.check()['errors']))
    def test_one_allowed_import_is_enough_for_this_necessary_check(self):
        self.plan['devices'][0]['peers'][0]['import']='none';self.assertEqual(self.check()['status'],'pass')
    def test_nonconnected_origin_is_coverage_warning_not_invalid_frr(self):
        self.plan['devices'][1]['originate'].append('192.168.3.0/24');before=render(self.plan,self.base);r=self.check()
        self.assertEqual(r['status'],'pass');self.assertTrue(any(w['property']=='nonconnected_origination_coverage' for w in r['warnings']));self.assertEqual(render(self.plan,self.base),before)
    def test_network_location_is_not_inferred_from_answer(self):
        prefix=self.plan['devices'][5]['originate'].pop();self.plan['devices'][1]['originate'].append(prefix)
        self.assertEqual(self.check()['status'],'pass');self.assertEqual(self.plan['devices'][5]['originate'],[])
    def test_no_network_anywhere_reports_public_requirement(self):
        self.plan['devices'][5]['originate']=[];self.assertTrue(any(e['property']=='required_network:192.168.3.0/24' for e in self.check()['errors']))
    def test_ordered_exact_prefix_policy_matches_rendered_ir_semantics(self):
        p=deepcopy(self.plan);p['policies'][1]['rules']=[{'id':'first','prefix':'192.168.2.0/24','action':'deny'},{'id':'second','prefix':'192.168.2.0/24','action':'permit'}]
        self.assertEqual(policy_action(p,'send','192.168.2.0/24'),'deny');self.assertEqual(policy_action(p,'send','192.168.0.0/16'),'permit');self.assertEqual(policy_action(p,'none','192.168.3.0/24'),'deny')
    def test_leak_is_deliberately_left_to_mandatory_export_verifier(self):
        self.plan['policies'][1]['rules']=[];r=self.check();self.assertEqual(r['status'],'pass');self.assertIn('actual advertised routes',r['not_verified'])
    def test_unknown_profile_is_not_assumed_deny_or_pass(self):
        r=audit(self.plan,self.public,self.t,profile='datacenter');self.assertEqual(r['status'],'environment_error')
        with self.assertRaises(ValueError):feedback('A2',r)
    def test_a1_is_literal_a2_has_ids_b1_never_gets_feedback(self):
        self.plan['devices'][0]['asn']=999;r=self.check();self.assertEqual(feedback('A1',r),'FAIL');a2=json.loads(feedback('A2',r));self.assertIn('R1',a2['errors'][0]['object_ids'])
        with self.assertRaises(ValueError):feedback('B1',r)
    def test_private_fields_are_not_read_or_sent(self):
        self.public['private_oracle']='SECRET_UNRELATED';self.plan['devices'][0]['asn']=999
        self.assertNotIn('SECRET_UNRELATED',json.dumps(self.check()));self.assertNotIn('SECRET_UNRELATED',feedback('A2',self.check()))
if __name__=='__main__':unittest.main()
