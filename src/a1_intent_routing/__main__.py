"""Run with PYTHONPATH=src python3 -m a1_intent_routing check-inputs PATH..."""
import argparse
import json
from pathlib import Path
import sys

from .contracts import CaseInput, CaseOracle, InputError, Topology, obj, string


def load_json(path: Path):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise InputError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def check_inputs(paths: list[Path], oracle_dir: Path | None = None) -> int:
    files = []
    for path in paths:
        files.extend(sorted(path.rglob("*.input.json")) if path.is_dir() else [path])
    if not files:
        print("error: no *.input.json files found; no input validated", file=sys.stderr)
        return 1
    seen, failures = set(), 0
    for path in files:
        try:
            raw = load_json(path)
            if not isinstance(raw, dict):
                raise InputError("$: expected object")
            topology_ref = string(raw.get("topology"), "$.topology")
            topology_path = path.parent / topology_ref
            try:
                topology = Topology.from_dict(load_json(topology_path))
            except (OSError, ValueError, TypeError) as exc:
                raise InputError(f"$.topology ({topology_path}): {exc}") from exc
            case = CaseInput.from_dict(raw, topology)
            if case.case_id in seen:
                raise InputError(f"$.case_id: duplicate case_id {case.case_id}")
            seen.add(case.case_id)
            if oracle_dir is not None:
                # An explicit evaluator-only option; oracle never enters CaseInput.
                if Path(case.case_id).name != case.case_id or case.case_id in (".", ".."):
                    raise InputError("$.case_id: invalid filename for oracle lookup")
                oracle_path = oracle_dir / f"{case.case_id}.oracle.json"
                try:
                    oracle = CaseOracle.from_dict(load_json(oracle_path), topology)
                    if oracle.case_id != case.case_id:
                        raise InputError("$.case_id: oracle/input mismatch")
                except (OSError, ValueError, TypeError) as exc:
                    raise InputError(f"oracle ({oracle_path}): {exc}") from exc
            print(f"{path}: input_valid (data only; no FRR/intent/lab verification)")
        except (OSError, ValueError, TypeError) as exc:
            failures += 1
            print(f"{path}: {exc}", file=sys.stderr)
    return 1 if failures else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="A1 offline data validation only")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check-inputs")
    check.add_argument("paths", nargs="+", type=Path, help="input JSON files or directories of *.input.json")
    check.add_argument("--oracle-dir", type=Path, help="explicit evaluator-only directory of CASE_ID.oracle.json")
    args = parser.parse_args(argv)
    return check_inputs(args.paths, args.oracle_dir)


if __name__ == "__main__":
    sys.exit(main())
