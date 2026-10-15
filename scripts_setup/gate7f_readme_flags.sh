#!/bin/bash
# Gate7f: faithful README eval flags (sigma_shift=1.0 + action_infer_mode=idm)
# across 3 suites x task0 x 5 trials, fresh output dirs (avoid result-skip).
set -uo pipefail
PY=/data1/liborui/.conda/envs/fastbench/bin/python
ROOT=/data1/liborui/fastwam_bench
cd "$ROOT/FastWAM"
export MUJOCO_GL=egl
export DIFFSYNTH_MODEL_BASE_PATH=$ROOT/checkpoints
export DIFFSYNTH_DOWNLOAD_SOURCE=huggingface
export HF_ENDPOINT=https://hf-mirror.com
export CUDA_DEVICE_ORDER=PCI_BUS_ID
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
GPU=$(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader,nounits | awk -F, '$2<5000{print $1}' | head -1)
if [ -z "$GPU" ]; then echo "NO FREE GPU"; exit 1; fi
echo "=== gate7f START $(date) using GPU $GPU ==="

for SUITE in libero_spatial libero_object libero_goal; do
  OUT=$ROOT/results/gate7f_${SUITE}_t0
  rm -rf "$OUT"
  echo "--- suite=$SUITE task=0 trials=5 -> $OUT"
  CUDA_VISIBLE_DEVICES=$GPU $PY experiments/libero/eval_libero_single.py \
    task=libero_optional_idm_2cam224_1e-4 \
    ckpt=$ROOT/checkpoints/fastwam_release/libero_optional_idm_2cam224.pt \
    model.load_text_encoder=true \
    model.redirect_common_files=false \
    model.action_dit_pretrained_path=null \
    model.skip_dit_load_from_pretrain=true \
    EVALUATION.dataset_stats_path=$ROOT/checkpoints/fastwam_release/libero_optional_idm_2cam224_dataset_stats.json \
    EVALUATION.sigma_shift=1.0 \
    +EVALUATION.action_infer_mode=idm \
    EVALUATION.task_suite_name=$SUITE \
    EVALUATION.task_id=0 \
    EVALUATION.num_trials=5 \
    EVALUATION.output_dir=$OUT \
    EVALUATION.compile_action_infer=false \
    > "$ROOT/logs/gate7f_${SUITE}.log" 2>&1
  echo "  exit=$?"
  $PY -c "
import json,glob,sys
for p in glob.glob('$OUT/*/gpu*_task0_results.json'):
    d=json.load(open(p))
    print('  RESULT', p.split('/')[-2], 'success_rate=', d.get('success_rate'), 'n=', d.get('total_episodes'))
" 2>/dev/null
done
echo "=== gate7f DONE $(date) ==="
