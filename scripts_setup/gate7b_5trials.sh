#!/bin/bash
# Gate 7: reproduce unmodified official FastWAM LIBERO rollout
#   suite=libero_spatial task=0 trials=1, optional_idm ckpt, official defaults.
set -uo pipefail
PY=/data1/liborui/.conda/envs/fastbench/bin/python
ROOT=/data1/liborui/fastwam_bench
cd "$ROOT/FastWAM"
export MUJOCO_GL=egl
export DIFFSYNTH_MODEL_BASE_PATH=$ROOT/checkpoints
export DIFFSYNTH_DOWNLOAD_SOURCE=huggingface
export HF_ENDPOINT=https://hf-mirror.com
export CUDA_DEVICE_ORDER=PCI_BUS_ID   # make CUDA index == nvidia-smi index
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
  EVALUATION.task_suite_name=libero_spatial \
  EVALUATION.task_id=0 \
  EVALUATION.num_trials=5 \
  EVALUATION.output_dir=$ROOT/results/gate7_libero_spatial_t0_5trials \
  EVALUATION.compile_action_infer=false \
  2>&1 | tail -80
echo "GATE7_EXIT=$?"
