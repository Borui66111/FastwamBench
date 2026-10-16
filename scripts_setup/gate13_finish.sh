#!/usr/bin/env bash
# Gate 13 finisher: wait for the main sweep, run the PSNR arm, emit artifacts.
set -u
cd /data1/liborui/fastwam_bench
PY=/data1/liborui/.conda/envs/fastbench/bin/python
SWEEP_PID=${SWEEP_PID:-371619}
TAG=${TAG:-main}
while kill -0 "$SWEEP_PID" 2>/dev/null; do sleep 60; done
echo "[finish] sweep $SWEEP_PID exited at $(date)"
$PY scripts_setup/gate13_run.py --tasks libero_spatial:0,libero_object:0 \
  --horizons 1,2,5,10 --seeds 1,2 --trials 5 --arms control,disturb \
  --magnitude 0.05 --world-step 40 --psnr --tag psnr --ngpu 2
$PY scripts_setup/gate13_analyze.py results/gate13_main > /tmp/g13_an.txt 2>&1
cp results/gate13_main/gate13_summary.json evidence/gate13_commitment_cost_summary.json
$PY scripts_setup/gate13_figure.py results/gate13_main/gate13_summary.json evidence/gate13_commitment_cost.png
$PY scripts_setup/gate13_report.py results/gate13_main/gate13_summary.json evidence/gate13_commitment_cost.md
if [ -d results/gate13_psnr ]; then
  $PY scripts_setup/gate13_analyze.py results/gate13_psnr > evidence/gate13_psnr_arm.txt 2>&1
  cp results/gate13_psnr/gate13_summary.json evidence/gate13_psnr_summary.json 2>/dev/null
fi
echo "[finish] done at $(date)"
