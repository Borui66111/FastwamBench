#!/bin/bash
# [fastbench] Gate 13 end-to-end pipeline (unattended).
#   Stage 1 sweep: headline cross-horizon commitment-cost experiment
#   Stage 2 psnr : same design, with predicted-future video (world-model signal)
# Usage: bash scripts_setup/gate13_all.sh [sweep|psnr|all]
set -uo pipefail
cd /data1/liborui/fastwam_bench
PY=/data1/liborui/.conda/envs/fastbench/bin/python
STAGE=${1:-all}

if [ "$STAGE" = "sweep" ] || [ "$STAGE" = "all" ]; then
  echo "=== STAGE 1: cross-horizon sweep ==="
  $PY scripts_setup/gate13_run.py \
    --tasks libero_spatial:0,libero_object:0 \
    --horizons 1,2,5,10,15,30 \
    --seeds 1 --trials 5 --tag main --ngpu 2
fi

if [ "$STAGE" = "psnr" ] || [ "$STAGE" = "all" ]; then
  echo "=== STAGE 2: predicted-future divergence (video) ==="
  $PY scripts_setup/gate13_run.py \
    --tasks libero_spatial:0 \
    --horizons 5,30 \
    --seeds 1 --trials 3 --tag psnr --ngpu 2 --psnr
fi

echo "=== STAGE 3: analyze + figure + report ==="
$PY scripts_setup/gate13_analyze.py results/gate13_main
$PY scripts_setup/gate13_figure.py results/gate13_main/gate13_summary.json evidence/gate13_commitment_cost.png
$PY scripts_setup/gate13_report.py results/gate13_main/gate13_summary.json evidence/gate13_commitment_cost.md
if [ -f results/gate13_psnr/gate13_summary.json ]; then
  $PY scripts_setup/gate13_analyze.py results/gate13_psnr | tail -20
  $PY scripts_setup/gate13_report.py results/gate13_psnr/gate13_summary.json evidence/gate13_psnr.md
fi
echo "done"
