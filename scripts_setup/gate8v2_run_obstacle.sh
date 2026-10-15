#!/bin/bash
# Gate 8 (v2): LIBERO-Safety obstacle_avoidance L0 task 0 through FastWAM, no intervention.
# v2 fix: add EVALUATION.sigma_shift=1.0 (README recipe; default 5.0 silently broke rollouts)
#         + EVALUATION.action_infer_mode=idm, 5 trials, fresh output dir, robust GPU pick.
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
echo "=== gate8v2 START $(date) using GPU $GPU ==="

OUT=$ROOT/results/gate8v2_obstacle_avoidance_L0_t0
rm -rf "$OUT"
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
  EVALUATION.task_suite_name=obstacle_avoidance \
  EVALUATION.task_id=0 \
  EVALUATION.num_trials=5 \
  EVALUATION.output_dir=$OUT \
  EVALUATION.compile_action_infer=false > "$ROOT/logs/gate8v2_obstacle.log" 2>&1
echo "GATE8V2_EXIT=$?"
$PY -c "
import json,glob
for p in sorted(glob.glob('$OUT/*/gpu*_task0_results.json')):
    d=json.load(open(p))
    print('RESULT',d['task_suite'],'task',d['task_id'],'=',d['successes'],'/',d['total_episodes'],'succ_eps',d['success_episodes'])
    print('   desc:',d['task_description'][:80])
"
echo "=== gate8v2 DONE $(date) ==="
