#!/usr/bin/env bash
# Gate 13 headline experiment: cost of world-model commitment vs replan horizon.
# Calibrated 2026-10-17: world_step=40 (displacement during approach, before grasp),
# magnitude 0.05 m (H=1 recovers -> the sweep is not floor-saturated).
# The trigger fires at a replan, so every H must divide (world_step - 30) = 10.
set -u
cd "$(dirname "$0")/.."
PY=/data1/liborui/.conda/envs/fastbench/bin/python
TASKS="${TASKS:-libero_spatial:0,libero_object:0}"
HORIZONS="${HORIZONS:-1,2,5,10}"
TRIALS="${TRIALS:-5}"
MAG="${MAG:-0.05}"
WS="${WS:-40}"

echo "=== STAGE 1: paired sweep (control vs disturb) ==="
$PY scripts_setup/gate13_run.py --tasks "$TASKS" --horizons "$HORIZONS" \
    --seeds 1 --trials "$TRIALS" --arms control,disturb \
    --magnitude "$MAG" --world-step "$WS" --tag main --ngpu 2

echo "=== STAGE 2: predicted-future-vs-reality PSNR arm ==="
$PY scripts_setup/gate13_run.py --tasks libero_spatial:0 --horizons "$HORIZONS" \
    --seeds 1 --trials 2 --arms control,disturb --psnr \
    --magnitude "$MAG" --world-step "$WS" --tag psnr --ngpu 2

echo "=== STAGE 3: analyze + figure + report ==="
$PY scripts_setup/gate13_analyze.py results/gate13_main
$PY scripts_setup/gate13_figure.py results/gate13_main/gate13_summary.json \
    evidence/gate13_commitment_cost.png
$PY scripts_setup/gate13_report.py results/gate13_main/gate13_summary.json \
    evidence/gate13_commitment_cost.md
echo "=== DONE ==="
