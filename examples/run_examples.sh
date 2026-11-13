#!/usr/bin/env bash
# Run all bundled scenarios and the ramp-metering comparison.
# Outputs land in examples/output/<scenario>/.
# Requires: python3 with numpy, matplotlib, PyYAML (see requirements.txt).
set -euo pipefail
cd "$(dirname "$0")/.."

OUT=examples/output

echo "=== 1/5 freeway_free_flow ==="
python3 -m traffic_flow simulate --scenario scenarios/freeway_free_flow.json --out "$OUT/freeway_free_flow"

echo "=== 2/5 rush_hour_bottleneck ==="
python3 -m traffic_flow simulate --scenario scenarios/rush_hour_bottleneck.json --out "$OUT/rush_hour_bottleneck"

echo "=== 3/5 stop_and_go_wave ==="
python3 -m traffic_flow simulate --scenario scenarios/stop_and_go_wave.json --out "$OUT/stop_and_go_wave"

echo "=== 4/5 ramp_metering_off ==="
python3 -m traffic_flow simulate --scenario scenarios/ramp_metering_off.json --out "$OUT/ramp_metering_off"

echo "=== 5/5 ramp_metering_on ==="
python3 -m traffic_flow simulate --scenario scenarios/ramp_metering_on.json --out "$OUT/ramp_metering_on"

echo "=== comparison: ramp metering off vs on ==="
python3 -m traffic_flow compare --a "$OUT/ramp_metering_off" --b "$OUT/ramp_metering_on" --out "$OUT/ramp_metering_comparison"

echo
echo "All scenarios done. See $OUT/<scenario>/report.md and dashboard.html."
