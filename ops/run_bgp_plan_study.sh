#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PY=runs/batfish-venv/bin/python
action="${1:-calibrate}"
case "$action" in
  stop|status) exec sudo "$PY" ops/bgp_plan_study.py "$action" ;;
  calibrate|pilot|resume) ;;
  *) echo 'Usage: bash ops/run_bgp_plan_study.sh calibrate|pilot|resume|stop|status'; exit 2 ;;
esac
"$PY" scripts/ollama_local.py start
"$PY" scripts/batfish_health.py --start --out "runs/bgp-plan-study-20261120/pre-health-$(date +%s%N)"
if [[ ! -f runs/bgp-plan-study-20261120/manifest.json ]]; then
  "$PY" ops/bgp_plan_study.py freeze
fi
"$PY" ops/bgp_plan_study.py check
mkdir -p runs/bgp-plan-study-20261120/launch
log="runs/bgp-plan-study-20261120/launch/$(date +%s%N).log"
if [[ "$action" == calibrate ]]; then
  sudo "$PY" ops/bgp_plan_study.py resume --seconds 1800 --calls 2 2>&1 | tee "$log"
else
  sudo "$PY" ops/bgp_plan_study.py resume --pilot --seconds 1800 --calls 2 2>&1 | tee "$log"
fi
