#!/usr/bin/env bash
# Gate 13 finisher: wait for the main sweep, run the decisive magnitude ladder
# (small displacements, where a longer commitment is NOT masked by the cost of
# re-acquiring the object), then the PSNR arm, then all artifacts.
set -u
cd /data1/liborui/fastwam_bench
PY=/data1/liborui/.conda/envs/fastbench/bin/python
SWEEP_PID=${SWEEP_PID:-371619}
while kill -0 "$SWEEP_PID" 2>/dev/null; do sleep 60; done
echo "[finish] sweep exited at $(date)"
for M in 0.02 0.03; do
  T=$(echo "$M" | tr -d '.')
  $PY scripts_setup/gate13_run.py --tasks libero_spatial:0,libero_object:0 \
    --horizons 1,10 --seeds 1 --trials 5 --arms control,disturb \
    --magnitude $M --world-step 40 --tag lad$T --ngpu 2
done
$PY scripts_setup/gate13_run.py --tasks libero_spatial:0,libero_object:0 \
  --horizons 1,10 --seeds 1 --trials 3 --arms control,disturb \
  --magnitude 0.05 --world-step 40 --psnr --tag psnr --ngpu 2
for D in main lad002 lad003 psnr; do
  [ -d "results/gate13_$D" ] || continue
  $PY scripts_setup/gate13_analyze.py results/gate13_$D > /tmp/g13_$D.txt 2>&1
  cp results/gate13_$D/gate13_summary.json evidence/gate13_${D}_summary.json 2>/dev/null
done
$PY scripts_setup/gate13_figure.py results/gate13_main/gate13_summary.json evidence/gate13_commitment_cost.png
$PY scripts_setup/gate13_report.py results/gate13_main/gate13_summary.json evidence/gate13_commitment_cost.md
echo "[finish] done at $(date)"
