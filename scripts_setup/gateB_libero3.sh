#!/bin/bash
# Gate B step 3: LIBERO runtime deps WITHOUT robomimic (only libero.lifelong.* needs it; envs do not)
set -euo pipefail
PY=/data1/liborui/.conda/envs/fastbench/bin/python
LOG=/data1/liborui/fastwam_bench/logs/gateB_libero.log
PIP="$PY -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple"
echo "=== STEP3 START $(date) ===" | tee -a "$LOG"

$PIP "bddl==1.0.1" "easydict==1.9" "cloudpickle==2.1.0" "future==0.18.2" \
     "gym==0.25.2" "matplotlib" "opencv-python" "imageio[ffmpeg]" \
     "scikit-image" "h5py" "thop" "usd-core" 2>&1 | tail -8 | tee -a "$LOG"

$PY - <<'PY' 2>&1 | tee -a "$LOG"
import importlib
for m in ['libero','robosuite','mujoco','numpy','bddl','easydict','gym','cv2','h5py','imageio','skimage']:
    try:
        mod = importlib.import_module(m)
        print(f'OK   {m:12s}', getattr(mod,'__version__','?'))
    except Exception as e:
        print(f'FAIL {m:12s}', type(e).__name__, str(e)[:160])
PY
echo "=== STEP3 DONE $(date) ===" | tee -a "$LOG"