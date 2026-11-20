import unittest
from a1_intent_routing.bgp_export import advertised_prefixes,bgp_prefixes
from a1_intent_routing.verifiers import EnvironmentFailure

class SenderEvidenceTest(unittest.TestCase):
    def test_empty_object_is_not_an_advertisement_proof(self):
        for data in [{},{'advertisedRoutes':{}},{'advertisedRoutes':{'192.0.2.0/24':{}},'totalPrefixCounter':0}]:
            with self.assertRaises(EnvironmentFailure):advertised_prefixes(data)
        self.assertEqual(set(),advertised_prefixes({'advertisedRoutes':{},'totalPrefixCounter':0}))
        self.assertEqual({'192.0.2.0/24'},advertised_prefixes({'advertisedRoutes':{'192.0.2.0/24':{}},'totalPrefixCounter':1}))

    def test_bgp_rib_requires_recognized_shape(self):
        with self.assertRaises(EnvironmentFailure):bgp_prefixes({})
        self.assertEqual(set(),bgp_prefixes({'routes':{}}))
