#!/bin/bash
# Gate A step 2: torch 2.7.1+cu128 + FastWAM editable install into existing fastbench env
set -euo pipefail
PY=/data1/liborui/.conda/envs/fastbench/bin/python
LOG=/data1/liborui/fastwam_bench/logs/gateA_env.log
echo "=== STEP2 START $(date) ===" | tee -a "$LOG"

$PY -m pip install -U pip -i https://pypi.tuna.tsinghua.edu.cn/simple 2>&1 | tail -3 | tee -a "$LOG"

$PY -m pip install "torch==2.7.1+cu128" "torchvision==0.22.1+cu128" \
  --extra-index-url https://download.pytorch.org/whl/cu128 \
  -i https://pypi.tuna.tsinghua.edu.cn/simple 2>&1 | tail -25 | tee -a "$LOG"

cd /data1/liborui/fastwam_bench/FastWAM
$PY -m pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple 2>&1 | tail -30 | tee -a "$LOG"

$PY - <<'PY' 2>&1 | tee -a "$LOG"
import torch
print('torch', torch.__version__)
print('cuda available', torch.cuda.is_available())
print('n_gpu', torch.cuda.device_count())
print('gpu0', torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)
print('bf16', torch.cuda.is_bf16_supported() if torch.cuda.is_available() else None)
PY

echo "=== STEP2 DONE $(date) ===" | tee -a "$LOG"