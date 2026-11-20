import unittest
from copy import deepcopy
from a1_intent_routing.bgp_plan import validate,render,semantic_digest,PlanError
from a1_intent_routing.bgp_plan_feedback import feedback,messages,repeated


def plan():
    return {'version':'bgp-plan-v1','policies':[{'id':'allow','rules':[],'default':'permit'},{'id':'out','rules':[{'id':'ban','prefix':'198.51.100.0/24','action':'deny'}],'default':'permit'}],'devices':[{'id':'R1','asn':64512,'originate':['203.0.113.0/24'],'peers':[{'id':'peer','address':'192.0.2.2','remote_as':64513,'ipv4':True,'import':'allow','export':'out'}]}]}
BASE={'R1':'hostname R1\ninterface eth1\n ip address 192.0.2.1/30\n no shutdown\nexit\n'}
class BgpPlanTest(unittest.TestCase):
    def test_base_is_preserved_and_direct_deny_lowering_is_correct(self):
        p=plan();text=render(p,BASE)['R1'];self.assertTrue(text.startswith(BASE['R1']))
        self.assertIn('ip prefix-list IR_out_ban seq 10 permit 198.51.100.0/24',text);self.assertIn('route-map IR_out deny 10',text)
        self.assertIn('route-map IR_out permit 65000',text);self.assertLess(text.index('route-map IR_out'),text.index('router bgp'))
        self.assertLess(text.index('remote-as'),text.index('address-family'))

    def test_wrong_network_decisions_are_not_rescued(self):
        p=plan();p['devices'][0].update(asn=666,originate=['198.18.0.0/24']);p['devices'][0]['peers'][0].update(address='192.0.2.1',remote_as=777)
        text=render(p,BASE)['R1'];self.assertIn('router bgp 666',text);self.assertIn('192.0.2.1 remote-as 777',text);self.assertIn('network 198.18.0.0/24',text)
        p['devices'][0]['peers']=[];self.assertNotIn('neighbor ',render(p,BASE)['R1'])

    def test_unattached_and_inverted_policy_stay_that_way(self):
        p=plan();p['devices'][0]['peers'][0]['export']='none';p['policies'][1]['rules'][0]['action']='permit'
        text=render(p,BASE)['R1'];self.assertNotIn('IR_out out',text);self.assertIn('route-map IR_out permit 10',text)

    def test_schema_and_refs_reject_ambiguous_or_injected_values(self):
        for mutate in [lambda p:p.update(oracle={}),lambda p:p['devices'].append(deepcopy(p['devices'][0])),lambda p:p['devices'][0]['peers'][0].update({'export':'undefined'}),lambda p:p['devices'][0]['peers'][0].update(address='1.2.3.4\nrouter ospf'),lambda p:p['policies'][1]['rules'][0].update(id='x\nexit')]:
            p=plan();mutate(p)
            with self.assertRaises(PlanError):validate(p,BASE)

    def test_semantic_cycle_detects_id_and_format_only_changes(self):
        p=plan();q=deepcopy(p);q['policies'][1]['id']='renamed';q['policies'][1]['rules'][0]['id']='different';q['devices'][0]['peers'][0].update(id='other',export='renamed')
        self.assertEqual(semantic_digest(p),semantic_digest(q));self.assertTrue(repeated(q,{semantic_digest(p)}))

    def test_a1_history_has_only_literal_fail_and_no_tool_details(self):
        initial=[{'role':'system','content':'schema'},{'role':'user','content':'public'}];history=[{'content':'my plan','feedback':'secret error'}]*3
        m=messages(initial,history,'A1');self.assertEqual(6,len(m));self.assertEqual(['FAIL','FAIL'],[x['content'] for x in m if x['role']=='user'][1:]);self.assertNotIn('secret',str(m));self.assertEqual('FAIL',feedback('A1',{'errors':[{'expected':'secret'}]}))

    def test_renderer_does_not_mutate_inputs(self):
        p=plan();before=deepcopy(p);render(p,BASE);self.assertEqual(before,p)
