"""Offline contracts over authored dev data; no routing simulation or lab."""
from copy import deepcopy
from dataclasses import asdict
import contextlib
import io
import json
from pathlib import Path
import unittest

from a1_intent_routing.__main__ import main
from a1_intent_routing.contracts import CaseInput, CaseOracle, InputError, Topology

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text())


class DevCaseTests(unittest.TestCase):
    def setUp(self):
        self.raw = read("topologies/triangle3.json")
        self.topology = Topology.from_dict(self.raw)

    def test_three_cases_and_oracles_load_separately(self):
        cases = sorted((ROOT / "data/dev").glob("*.input.json"))
        self.assertEqual(len(cases), 3)
        groups = set()
        for path in cases:
            case = CaseInput.from_dict(json.loads(path.read_text()), self.topology)
            oracle = CaseOracle.from_dict(read(f"data/oracles/dev/{case.case_id}.oracle.json"), self.topology)
            self.assertEqual(case.case_id, oracle.case_id)
            groups.add(case.task_group)
            self.assertNotIn("routing_checks", asdict(case))
            self.assertNotIn("regression_checks", asdict(case))
            # Every successful forward probe has an explicit reverse probe.
            checks = oracle.checks + oracle.regression_checks
            for check in checks:
                self.assertTrue(any(c.source == check.destination and c.destination == check.source
                                    for c in checks))
        self.assertEqual(groups, {"static", "ospf", "path_regression"})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["check-inputs", str(ROOT / "data/dev"),
                                   "--oracle-dir", str(ROOT / "data/oracles/dev")]), 0)

    def test_invalid_gateway_link_and_subnet(self):
        for mutate in (
            lambda r: r["nodes"][3].update(gateway="192.168.2.1"),
            lambda r: r["links"][0]["b"].update(node="missing"),
            lambda r: r["nodes"][0]["interfaces"][0].update(ipv4="10.1.0.1/30"),
        ):
            raw = deepcopy(self.raw)
            mutate(raw)
            with self.assertRaises(InputError):
                Topology.from_dict(raw)

    def test_nonadjacent_real_path_is_rejected(self):
        case = read("data/dev/dev_path_regression_01.input.json")
        case["constraints"][0]["required_path"] = ["H1", "R1", "H3", "R2", "H2"]
        with self.assertRaisesRegex(InputError, "not adjacent"):
            CaseInput.from_dict(case, self.topology)

    def test_ospf_rib_properties_are_validated(self):
        oracle = read("data/oracles/dev/dev_ospf_01.oracle.json")
        parsed = CaseOracle.from_dict(oracle, self.topology)
        self.assertTrue(parsed.routing_checks)
        for key, bad in (("node", "H1"), ("prefix", "192.168.9.0/24"),
                         ("next_hop", "10.0.23.2"), ("area", "1.0.0.0"),
                         ("protocol", "connected")):
            raw = deepcopy(oracle)
            raw["routing_checks"][0][key] = bad
            with self.subTest(key=key), self.assertRaises(InputError):
                CaseOracle.from_dict(raw, self.topology)

    def test_regression_is_independent_of_new_traffic(self):
        oracle = CaseOracle.from_dict(read("data/oracles/dev/dev_path_regression_01.oracle.json"), self.topology)
        self.assertTrue(oracle.regression_checks)
        for check in oracle.regression_checks:
            self.assertEqual({check.source.node, check.destination.node}, {"H2", "H3"})
            self.assertNotIn("R1", check.required_path)
