#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PY=runs/batfish-venv/bin/python
OUT=runs/bgp-h2-policy-lab-20261121-01
if [[ -f "$OUT/run-started.json" ]]; then
  echo "Lab attempt already started; inspect $OUT/summary.json. No automatic retry."
  exit 2
fi
if [[ ! -f "$OUT/plan.json" ]]; then
  "$PY" ops/replay_bgp_h2_probe.py prepare --out "$OUT"
fi
"$PY" scripts/batfish_health.py --start --out "runs/bgp-h2-lab-health-$(date +%s%N)"
log="$OUT/terminal-$(date +%s%N).log"
sudo "$PY" ops/replay_bgp_h2_probe.py run --out "$OUT" 2>&1 | tee "$log"
