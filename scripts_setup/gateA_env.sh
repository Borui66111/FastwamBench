#!/bin/bash
# Gate A: create fastbench env (python 3.10) + torch 2.7.1+cu128 + install FastWAM editable
set -euo pipefail
source /opt/anaconda3/etc/profile.d/conda.sh

LOG=/data1/liborui/fastwam_bench/logs/gateA_env.log
echo "=== START $(date) ===" | tee -a "$LOG"

if ! conda env list | awk '{print $1}' | grep -qx fastbench; then
  conda create -n fastbench python=3.10 -y 2>&1 | tee -a "$LOG"
fi

conda activate fastbench
echo "python: $(which python) $(python --version 2>&1)" | tee -a "$LOG"

python -m pip install -U pip -i https://pypi.tuna.tsinghua.edu.cn/simple 2>&1 | tail -3 | tee -a "$LOG"

# torch 2.7.1 + cu128 (official pytorch index; tsinghua mirror does not carry +cu128 local versions)
python -m pip install "torch==2.7.1+cu128" "torchvision==0.22.1+cu128" \
  --extra-index-url https://download.pytorch.org/whl/cu128 \
  -i https://pypi.tuna.tsinghua.edu.cn/simple 2>&1 | tail -20 | tee -a "$LOG"

cd /data1/liborui/fastwam_bench/FastWAM
python -m pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple 2>&1 | tail -25 | tee -a "$LOG"

python - <<'PY' 2>&1 | tee -a "$LOG"
import torch
print('torch', torch.__version__)
print('cuda available', torch.cuda.is_available())
print('gpu', torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)
print('bf16', torch.cuda.is_bf16_supported() if torch.cuda.is_available() else None)
PY

echo "=== DONE $(date) ===" | tee -a "$LOG"
