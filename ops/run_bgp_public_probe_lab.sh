#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PY=runs/batfish-venv/bin/python
OUT=runs/bgp-public-repair-lab-20261121-01
if [[ -f "$OUT/run-started.json" ]]; then
  echo "Lab attempt already started; inspect $OUT/summary.json. No automatic retry."
  exit 2
fi
"$PY" scripts/batfish_health.py --start --out "runs/bgp-public-probe-health-$(date +%s%N)"
if [[ ! -f "$OUT/plan.json" ]]; then
  "$PY" ops/replay_bgp_public_probe.py prepare --out "$OUT"
fi
log="$OUT/terminal-$(date +%s%N).log"
sudo "$PY" ops/replay_bgp_public_probe.py run --out "$OUT" 2>&1 | tee "$log"
