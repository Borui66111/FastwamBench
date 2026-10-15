#!/bin/bash
# Gate B: install LIBERO-Safety as the active `libero` package (no clobbering of FastWAM pins)
set -euo pipefail
PY=/data1/liborui/.conda/envs/fastbench/bin/python
LOG=/data1/liborui/fastwam_bench/logs/gateB_libero.log
PIP="$PY -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple"
echo "=== START $(date) ===" | tee -a "$LOG"

# 1) libero package itself (setup.py has no install_requires)
cd /data1/liborui/fastwam_bench/LIBERO-Safety
$PIP -e . 2>&1 | tail -5 | tee -a "$LOG"

# 2) robosuite 1.4 fork (required by LIBERO)
$PIP -e third_party/robosuite-1.4 2>&1 | tail -5 | tee -a "$LOG"

# 3) mujoco pinned by upstream instructions
$PIP "mujoco==3.3.2" 2>&1 | tail -3 | tee -a "$LOG"

# 4) runtime deps that LIBERO envs actually need at import/rollout time.
#    Deliberately NOT installing requirements.txt wholesale: it pins
#    transformers==4.21.1 / hydra-core==1.2.0 / numpy<2, which would clobber
#    FastWAM's required transformers==4.49.0 / hydra-core==1.3.2 / numpy==2.2.6.
$PIP "bddl==1.0.1" "easydict==1.9" "cloudpickle==2.1.0" "future==0.18.2" \
     "gym==0.25.2" "matplotlib" "opencv-python" "imageio[ffmpeg]" "usd-core" \
     "scikit-image" "h5py" "thop" "robomimic==0.2.0" 2>&1 | tail -12 | tee -a "$LOG"

$PY - <<'PY' 2>&1 | tee -a "$LOG"
import libero, robosuite, mujoco, numpy, bddl
print('libero  ', libero.__file__)
print('robosuite', robosuite.__version__, robosuite.__file__)
print('mujoco  ', mujoco.__version__)
print('numpy   ', numpy.__version__)
PY
echo "=== DONE $(date) ===" | tee -a "$LOG"
