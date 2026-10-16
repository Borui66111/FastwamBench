#!/usr/bin/env bash
# Gate 13 finisher: wait for the main sweep to exit, then run the PSNR arm and
# produce the reviewer-facing artifacts. Keeps the whole experiment unattended.
set -u
cd "$(dirname "$0")/.."
PY=/data1/liborui/.conda/envs/fastbench/bin/python
SWEEP_PID="${SWEEP_PID:-0}"
TAG="${TAG:-main}"
HORIZONS="${HORIZONS:-1,2,5,10}"
MAG="${MAG:-0.05}"
WS="${WS:-40}"

if [ "$SWEEP_PID" != "0" ]; then
  echo "waiting for sweep pid $SWEEP_PID ..."
  while kill -0 "$SWEEP_PID" 2>/dev/null; do sleep 60; done
fi
n=$(find "results/gate13_$TAG" -name records.jsonl 2>/dev/null | wc -l)
echo "sweep finished: $n run(s) under results/gate13_$TAG"

echo "=== STAGE 2: predicted-future-vs-reality PSNR arm ==="
$PY scripts_setup/gate13_run.py --tasks libero_spatial:0 --horizons "$HORIZONS" \
    --seeds 1 --trials 2 --arms control,disturb --psnr \
    --magnitude "$MAG" --world-step "$WS" --tag psnr --ngpu 2

echo "=== STAGE 3: analyze + figure + report ==="
$PY scripts_setup/gate13_analyze.py "results/gate13_$TAG"
$PY scripts_setup/gate13_figure.py "results/gate13_$TAG/gate13_summary.json" \
    evidence/gate13_commitment_cost.png
$PY scripts_setup/gate13_report.py "results/gate13_$TAG/gate13_summary.json" \
    evidence/gate13_commitment_cost.md
echo "=== DONE ==="
