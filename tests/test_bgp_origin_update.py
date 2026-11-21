import unittest
from copy import deepcopy
from a1_intent_routing.bgp_origin_update import apply,VERSION
from a1_intent_routing.bgp_coverage_advisory import nonorigin_signature
from a1_intent_routing.bgp_plan import PlanError
class OriginUpdateTest(unittest.TestCase):
    def setUp(self):
        self.source={'version':'bgp-plan-v1','policies':[{'id':'out','rules':[],'default':'deny'}],'devices':[{'id':'R2','asn':65002,'originate':['10.6.2.0/30','192.168.3.0/24'],'peers':[{'id':'R3','address':'10.6.2.2','remote_as':65003,'ipv4':True,'import':'out','export':'none'}]}]}
    def test_literal_values_only_and_source_is_not_mutated(self):
        original=deepcopy(self.source);patch={'version':VERSION,'updates':[{'device_id':'R2','originate':['198.18.0.0/24']}]};out=apply(self.source,patch)
        self.assertEqual(out['devices'][0]['originate'],['198.18.0.0/24']);self.assertEqual(self.source,original);self.assertEqual(nonorigin_signature(out),nonorigin_signature(original))
    def test_policy_cannot_be_changed_or_filled_by_update(self):
        patch={'version':VERSION,'updates':[{'device_id':'R2','originate':[],'policies':[]}]}
        with self.assertRaises(PlanError):apply(self.source,patch)
    def test_unknown_or_duplicate_device_is_rejected(self):
        for rows in [[{'device_id':'R9','originate':[]}],[{'device_id':'R2','originate':[]},{'device_id':'R2','originate':[]}]]:
            with self.assertRaises(PlanError):apply(self.source,{'version':VERSION,'updates':rows})
    def test_invalid_prefix_is_not_repaired_by_applier(self):
        for prefix in ['192.0.2.1/24','bad','10.0.0.0/24\nrouter bgp 1']:
            with self.assertRaises(PlanError):apply(self.source,{'version':VERSION,'updates':[{'device_id':'R2','originate':[prefix]}]})
    def test_empty_update_is_real_noop_not_implicit_answer(self):
        self.assertEqual(apply(self.source,{'version':VERSION,'updates':[]}),self.source)
    def test_literal_removal_is_allowed_only_when_model_requests_it(self):
        self.assertEqual(apply(self.source,{'version':VERSION,'updates':[{'device_id':'R2','originate':[]}]})['devices'][0]['originate'],[])
if __name__=='__main__':unittest.main()
