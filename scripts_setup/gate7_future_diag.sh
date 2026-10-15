#!/bin/bash
# Gate7 diagnostic: visualize imagined future video (is the backbone sound?)
set -uo pipefail
PY=/data1/liborui/.conda/envs/fastbench/bin/python
ROOT=/data1/liborui/fastwam_bench
cd "$ROOT/FastWAM"
export MUJOCO_GL=egl DIFFSYNTH_MODEL_BASE_PATH=$ROOT/checkpoints
export HF_ENDPOINT=https://hf-mirror.com CUDA_DEVICE_ORDER=PCI_BUS_ID
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

# pick a GPU with >=35 GiB free
GPU=""
for i in $(seq 0 7); do
  free=$(nvidia-smi -i $i --query-gpu=memory.free --format=csv,noheader,nounits)
  if [ "$free" -ge 35000 ]; then GPU=$i; break; fi
done
if [ -z "$GPU" ]; then echo "NO FREE GPU"; exit 3; fi
echo "using GPU $GPU (free>=35GiB)"

CUDA_VISIBLE_DEVICES=$GPU $PY experiments/libero/eval_libero_single.py \
  task=libero_optional_idm_2cam224_1e-4 \
  ckpt=$ROOT/checkpoints/fastwam_release/libero_optional_idm_2cam224.pt \
  model.redirect_common_files=false \
  EVALUATION.dataset_stats_path=$ROOT/checkpoints/fastwam_release/libero_optional_idm_2cam224_dataset_stats.json \
  EVALUATION.task_suite_name=libero_spatial EVALUATION.task_id=0 \
  EVALUATION.num_trials=1 EVALUATION.sigma_shift=1.0 \
  EVALUATION.visualize_future_video=true \
  EVALUATION.output_dir=$ROOT/results/gate7_future_diag \
  EVALUATION.compile_action_infer=false \
  > $ROOT/logs/gate7_future_diag.log 2>&1
echo "EXIT=$?"