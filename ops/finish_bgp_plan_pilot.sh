#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PY=runs/batfish-venv/bin/python
"$PY" scripts/ollama_local.py start
"$PY" scripts/batfish_health.py --start --out "runs/bgp-plan-study-20261120-02/pre-health-finish-$(date +%s%N)"
"$PY" ops/bgp_plan_study.py check
exec sudo "$PY" ops/finish_bgp_pilot.py --resume
