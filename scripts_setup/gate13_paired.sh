#!/bin/bash
# Gate 13 (thin wrapper). The full cross-horizon sweep lives in gate13_run.py;
# this keeps the old one-shot entry point working for a single (task, horizon).
#
#   SUITE=libero_spatial TASK_ID=0 RS=10 TRIALS=5 SEED=1 \
#     bash scripts_setup/gate13_paired.sh
#
# Prefer the sweep directly:
#   python scripts_setup/gate13_run.py --horizons 1,2,5,10,15,30 --seeds 1,2
set -uo pipefail
ROOT=/data1/liborui/fastwam_bench
PY=/data1/liborui/.conda/envs/fastbench/bin/python

SUITE=${SUITE:-libero_spatial}
TASK_ID=${TASK_ID:-0}
RS=${RS:-10}
TRIALS=${TRIALS:-5}
SEED=${SEED:-1}

exec "$PY" "$ROOT/scripts_setup/gate13_run.py" \
  --tasks "${SUITE}:${TASK_ID}" \
  --horizons "$RS" \
  --seeds "$SEED" \
  --trials "$TRIALS" \
  --tag "${TAG:-single}"
