import contextlib
from copy import deepcopy
from dataclasses import asdict
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import importlib.util
import subprocess

from a1_intent_routing.contracts import CaseInput, CaseOracle, InputError, RunRecord, ToolResult, Topology
from a1_intent_routing.__main__ import main


def topology_data():
    return {"topology_id": "fixture", "nodes": [
        {"name": "A", "kind": "host", "interfaces": [{"name": "eth0", "ipv4": "192.0.2.1/30"}]},
        {"name": "B", "kind": "router", "interfaces": [{"name": "eth0", "ipv4": "192.0.2.2/30"}]}],
        "links": [{"a": {"node": "A", "interface": "eth0"}, "b": {"node": "B", "interface": "eth0"}}]}


def check_data():
    return {"source": {"node": "A", "interface": "eth0", "ip": "192.0.2.1"},
            "destination": {"node": "B", "interface": "eth0", "ip": "192.0.2.2"},
            "reachability": True, "required_path": ["A", "B"], "direction": "forward", "ecmp": "all_paths"}


def case_data():
    return {"case_id": "fixture", "task_group": "static", "split": "dev", "intent": "Kết nối A đến B",
            "topology": "topology.json", "constraints": [check_data()]}


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.topology = Topology.from_dict(topology_data())

    def test_input_oracle_are_separate_and_unmeasured_is_null(self):
        case = CaseInput.from_dict(case_data(), self.topology)
        oracle = CaseOracle.from_dict({"case_id": "fixture", "checks": [check_data()], "regression_checks": []}, self.topology)
        self.assertEqual(oracle.checks[0].source.ip, "192.0.2.1")
        raw = asdict(case)
        self.assertNotIn("checks", raw)
        contaminated = case_data() | {"oracle": asdict(oracle)}
        with self.assertRaisesRegex(InputError, "unknown fields"):
            CaseInput.from_dict(contaminated, self.topology)
        record = asdict(RunRecord("fixture", "one_pass"))
        self.assertIsNone(record["input_tokens"])
        self.assertIsNone(record["total_seconds"])

    def test_link_and_subnet_rejected(self):
        for value, fragment in (("198.51.100.2/30", "subnet"), ("nonsense", "IPv4"), ("192.0.2.0/30", "network/broadcast")):
            with self.subTest(value=value):
                raw = topology_data()
                raw["nodes"][1]["interfaces"][0]["ipv4"] = value
                with self.assertRaisesRegex(InputError, fragment):
                    Topology.from_dict(raw)
        raw = topology_data()
        raw["links"][0]["b"]["interface"] = "missing"
        with self.assertRaisesRegex(InputError, "unknown node/interface"):
            Topology.from_dict(raw)

    def test_overlapping_links_and_duplicate_addresses(self):
        raw = topology_data()
        raw["nodes"][1]["interfaces"][0]["ipv4"] = "192.0.2.1/30"
        with self.assertRaisesRegex(InputError, "duplicate address"):
            Topology.from_dict(raw)
        raw = topology_data()
        raw["nodes"] += [
            {"name": "C", "kind": "router", "interfaces": [{"name": "eth0", "ipv4": "192.0.2.5/29"}]},
            {"name": "D", "kind": "router", "interfaces": [{"name": "eth0", "ipv4": "192.0.2.6/29"}]}]
        raw["links"].append({"a": {"node": "C", "interface": "eth0"}, "b": {"node": "D", "interface": "eth0"}})
        with self.assertRaisesRegex(InputError, "overlaps"):
            Topology.from_dict(raw)

    def test_bad_traffic_and_enums(self):
        for key, value, fragment in (("source", {"node": "X", "interface": "eth0", "ip": "192.0.2.1"}, "unknown node"),
                                     ("destination", {"node": "B", "interface": "eth0", "ip": "192.0.2.3"}, "IP must match"),
                                     ("direction", "both", "direction"), ("ecmp", "implicit", "ecmp")):
            raw = case_data()
            raw["constraints"][0][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(InputError, fragment):
                CaseInput.from_dict(raw, self.topology)
        for key in ("split", "task_group"):
            raw = case_data() | {key: "bad"}
            with self.assertRaisesRegex(InputError, key):
                CaseInput.from_dict(raw, self.topology)

    def test_nonadjacent_path(self):
        raw = topology_data()
        raw["nodes"].append({"name": "C", "kind": "router", "interfaces": [{"name": "eth0", "ipv4": "198.51.100.1/32"}]})
        case = case_data()
        case["constraints"][0]["required_path"] = ["A", "C", "B"]
        with self.assertRaisesRegex(InputError, "not adjacent"):
            CaseInput.from_dict(case, Topology.from_dict(raw))

    def test_no_false_pass_and_repair_limits(self):
        with self.assertRaises(InputError):
            ToolResult("missing_verifier", "pass")
        missing = ToolResult("syntax_checker", "environment_error")
        with self.assertRaisesRegex(InputError, "environment errors"):
            RunRecord("fixture", "pass_fail", status="pass", syntax_checks=[missing])
        with self.assertRaises(InputError):
            RunRecord("fixture", "one_pass", attempt_index=1, repair_count=1)
        with self.assertRaises(InputError):
            RunRecord("fixture", "structured_error", attempt_index=6, repair_count=6)
        self.assertEqual(RunRecord("fixture", "structured_error", attempt_index=5, repair_count=5).repair_count, 5)

    def test_cli_valid_invalid_and_duplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "topology.json").write_text(json.dumps(topology_data()))
            case = root / "fixture.input.json"
            case.write_text(json.dumps(case_data()))
            output, errors = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                self.assertEqual(main(["check-inputs", str(root)]), 0)
                self.assertIn("input_valid", output.getvalue())
                self.assertEqual(main(["check-inputs", str(case), str(case)]), 1)
                self.assertIn("duplicate case_id", errors.getvalue())
                case.write_text(json.dumps(case_data() | {"split": "bad"}))
                self.assertEqual(main(["check-inputs", str(case)]), 1)
                self.assertIn(str(case), errors.getvalue())
                self.assertIn("$.split", errors.getvalue())

    def test_cli_empty_missing_malformed_and_oracle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(["check-inputs", str(root)]), 1)
                self.assertEqual(main(["check-inputs", str(root / "absent.json")]), 1)
                case = root / "fixture.input.json"
                case.write_text('{"x": 1, "x": 2}')
                self.assertEqual(main(["check-inputs", str(case)]), 1)
                case.write_text(json.dumps(case_data()))
                self.assertEqual(main(["check-inputs", str(case)]), 1)  # Missing topology.
                (root / "topology.json").write_text(json.dumps(topology_data()))
                oracle = root / "fixture.oracle.json"
                oracle.write_text(json.dumps({"case_id": "wrong", "checks": [check_data()], "regression_checks": []}))
                self.assertEqual(main(["check-inputs", str(case), "--oracle-dir", str(root)]), 1)
                oracle.write_text(json.dumps({"case_id": "fixture", "checks": [check_data()], "regression_checks": []}))
                self.assertEqual(main(["check-inputs", str(case), "--oracle-dir", str(root)]), 0)


class PreflightTests(unittest.TestCase):
    def test_missing_timeout_and_failure_are_reported(self):
        spec = importlib.util.spec_from_file_location("preflight", Path(__file__).resolve().parents[1] / "scripts/preflight.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.object(module.shutil, "which", return_value=None):
            self.assertEqual(module.probe(["absent"])["status"], "missing")
        with patch.object(module.shutil, "which", return_value="/tool"), patch.object(module.subprocess, "run") as run:
            run.side_effect = subprocess.TimeoutExpired(["tool"], 5)
            self.assertEqual(module.probe(["tool"])["status"], "timeout")
            self.assertNotIn("shell", run.call_args.kwargs)
            self.assertEqual(run.call_args.kwargs["timeout"], 5)
            run.side_effect = None
            run.return_value = subprocess.CompletedProcess(["tool"], 1, "", "permission denied")
            self.assertEqual(module.probe(["tool"])["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
