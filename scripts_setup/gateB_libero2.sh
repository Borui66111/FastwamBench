#!/bin/bash
# Gate B step 2: runtime deps for LIBERO-Safety (cmake first so egl_probe builds)
set -euo pipefail
PY=/data1/liborui/.conda/envs/fastbench/bin/python
LOG=/data1/liborui/fastwam_bench/logs/gateB_libero.log
PIP="$PY -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple"
echo "=== STEP2 START $(date) ===" | tee -a "$LOG"

$PIP cmake 2>&1 | tail -3 | tee -a "$LOG"
$PY -c "import cmake,os;print('cmake bin:',os.path.join(os.path.dirname(cmake.__file__),'data','bin'))"

export PATH="$($PY -c "import cmake,os;print(os.path.join(os.path.dirname(cmake.__file__),'data','bin'))"):$PATH"
which cmake && cmake --version | head -1 | tee -a "$LOG"

$PIP "bddl==1.0.1" "easydict==1.9" "cloudpickle==2.1.0" "future==0.18.2" \
     "gym==0.25.2" "matplotlib" "opencv-python" "imageio[ffmpeg]" \
     "scikit-image" "h5py" "thop" "robomimic==0.2.0" 2>&1 | tail -15 | tee -a "$LOG"

$PY - <<'PY' 2>&1 | tee -a "$LOG"
mods = ['libero','robosuite','mujoco','numpy','bddl','easydict','gym','cv2','h5py','imageio','skimage','robomimic']
import importlib
for m in mods:
    try:
        mod = importlib.import_module(m)
        print(f'OK   {m:12s}', getattr(mod,'__version__','?'))
    except Exception as e:
        print(f'FAIL {m:12s}', type(e).__name__, str(e)[:160])
PY
echo "=== STEP2 DONE $(date) ===" | tee -a "$LOG"
