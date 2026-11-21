import json,sys,unittest
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'ops'))
from bgp_plan_controls import positive
from a1_intent_routing.bgp_hybrid_eval import load_case
from a1_intent_routing.bgp_observed_feedback import build,policy_invariant
class ObservedFeedbackTest(unittest.TestCase):
    def setUp(self):
        self.public,self.t,_,_=load_case(ROOT,'dev_ebgp_prefix_02');self.plan=positive(self.public,self.t);self.plan['policies'][1]['rules']=[];d=next(v for v in self.plan['devices'] if v['id']=='R4');self.report={'tool':'bgp_export_tester','status':'fail','checks':[]};self.w={}
        for p in d['peers']:
            prop='export_policy:'+p['address']+':192.168.2.0/24';self.report['checks'] += [{'device':'R4','property':prop,'status':'fail','observed':'PERMIT'},{'device':'R4','property':'advertised:'+p['address']+':192.168.2.0/24','status':'fail','observed':{'advertised':True}}]
            self.w[('R4',prop)]={'direction':'out','input_prefix':'192.168.2.0/24','binding':{'Node':'r4','Remote_IP':p['address'],'Export_Policy':['IR_send']},'rows':[{'Node':'r4','Policy_Name':'IR_send','Action':'PERMIT','Trace':'UNRELATED_SECRET'}]}
    def call(self,method='A2'):return build(self.plan,self.public,self.t,self.report,self.w,method)
    def test_two_origin_failures_have_stable_policy_and_peer_ids(self):
        r=json.loads(self.call());self.assertEqual(len(r['errors']),2)
        for e in r['errors']:self.assertEqual(e['object_ids'][0],'R4');self.assertIn('send',e['object_ids']);self.assertTrue(e['observed']['advertised'])
        self.assertNotIn('UNRELATED_SECRET',self.call())
    def test_a1_literal_b1_forbidden(self):
        self.assertEqual(self.call('A1'),'FAIL')
        with self.assertRaises(ValueError):self.call('B1')
    def test_policy_permit_without_actual_advertisement_is_insufficient(self):
        self.report['checks'][1]['observed']['advertised']=False
        with self.assertRaisesRegex(ValueError,'alone'):self.call()
    def test_binding_peer_direction_or_policy_mismatch_is_rejected(self):
        for mutate in [lambda w:w.update(direction='in'),lambda w:w['binding'].update(Remote_IP='10.0.0.99'),lambda w:w['binding'].update(Export_Policy=['GUESS']),lambda w:w['rows'][0].update(Policy_Name='GUESS')]:
            original=deepcopy(self.w);mutate(next(iter(self.w.values())))
            with self.assertRaisesRegex(ValueError,'witness mismatch'):self.call()
            self.w=original
    def test_infrastructure_or_unsupported_report_is_not_feedback(self):
        self.report['status']='environment_error'
        with self.assertRaises(ValueError):self.call()
        self.report['status']='fail';self.report['unsupported']=['unknown CLI']
        with self.assertRaises(ValueError):self.call()
    def test_actual_policy_evidence_cannot_be_reused_after_ir_edit(self):
        self.plan['policies'][1]['rules']=[{'id':'block','prefix':'192.168.2.0/24','action':'deny'}]
        with self.assertRaisesRegex(ValueError,'disagree'):self.call()
    def test_missing_witness_is_not_guessed(self):
        self.w={}
        with self.assertRaisesRegex(ValueError,'Missing'):self.call()
    def test_policy_only_scope_allows_bindings_but_rejects_network_edits(self):
        signature=policy_invariant(self.plan);p=deepcopy(self.plan);p['devices'][0]['peers'][0]['export']='none';p['policies'][1]['default']='deny';self.assertEqual(policy_invariant(p),signature)
        p['devices'][0]['originate'].append('203.0.113.0/24');self.assertNotEqual(policy_invariant(p),signature)
        p=deepcopy(self.plan);p['devices'][0]['peers'][0]['address']='192.0.2.1';self.assertNotEqual(policy_invariant(p),signature)
if __name__=='__main__':unittest.main()
