#!/bin/bash
# Gate 8: LIBERO-Safety obstacle_avoidance L0 task 0 through FastWAM, no intervention.
set -uo pipefail
PY=/data1/liborui/.conda/envs/fastbench/bin/python
ROOT=/data1/liborui/fastwam_bench
cd "$ROOT/FastWAM"
export MUJOCO_GL=egl
export DIFFSYNTH_MODEL_BASE_PATH=$ROOT/checkpoints
export DIFFSYNTH_DOWNLOAD_SOURCE=huggingface
export HF_ENDPOINT=https://hf-mirror.com
export CUDA_DEVICE_ORDER=PCI_BUS_ID
GPU=$(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader,nounits | sort -t, -k2 -n | head -1 | cut -d, -f1)
echo "using GPU $GPU"
CUDA_VISIBLE_DEVICES=$GPU $PY experiments/libero/eval_libero_single.py \
  task=libero_optional_idm_2cam224_1e-4 \
  ckpt=$ROOT/checkpoints/fastwam_release/libero_optional_idm_2cam224.pt \
  model.load_text_encoder=true \
  model.redirect_common_files=false \
  model.action_dit_pretrained_path=null \
  model.skip_dit_load_from_pretrain=true \
  EVALUATION.dataset_stats_path=$ROOT/checkpoints/fastwam_release/libero_optional_idm_2cam224_dataset_stats.json \
  EVALUATION.task_suite_name=obstacle_avoidance \
  EVALUATION.task_id=0 \
  EVALUATION.num_trials=3 \
  EVALUATION.output_dir=$ROOT/results/gate8_obstacle_avoidance_L0_t0 \
  EVALUATION.compile_action_infer=false \
  2>&1 | tail -40
echo "GATE8_EXIT=$?"
