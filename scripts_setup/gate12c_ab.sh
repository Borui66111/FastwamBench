#!/bin/bash
# Gate 12C: reproduce the upstream README's EXACT published command (lines 103-113)
# and A/B it against the flag set used by our Gate 11/12A harness, at 20 trials on
# the same two tasks, to determine whether our extra flags / seed pin cause the
# success-rate gap (we observe ~0-40% vs the README's 98.55%).
#
#   Arm A  upstream : task, ckpt, dataset_stats, sigma_shift=1.0, +action_infer_mode=idm
#   Arm B  ours     : Arm A + model.{load_text_encoder,redirect_common_files,
#                     action_dit_pretrained_path,skip_dit_load_from_pretrain}
#                     + seed=1 + EVALUATION.compile_action_infer=false
#
# Same task list, same trials, same seed handling for the noise -> the only
# difference is the flag set.
set -uo pipefail

PY=/data1/liborui/.conda/envs/fastbench/bin/python
ROOT=/data1/liborui/fastwam_bench
cd "$ROOT/FastWAM"

export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl
export DIFFSYNTH_MODEL_BASE_PATH="$ROOT/checkpoints"
export DIFFSYNTH_DOWNLOAD_SOURCE=huggingface
export HF_ENDPOINT=https://hf-mirror.com
export CUDA_DEVICE_ORDER=PCI_BUS_ID
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export TOKENIZERS_PARALLELISM=false

TRIALS=${TRIALS:-20}
TASKFILE=${TASKFILE:-$ROOT/scripts_setup/gate12c_tasks.txt}
GPU=${GPU:-5}
ARM=${ARM:-upstream}
OUT=${OUT:-$ROOT/results/gate12c_$ARM}

export CUDA_VISIBLE_DEVICES=$GPU

CKPT="$ROOT/checkpoints/fastwam_release/libero_optional_idm_2cam224.pt"
STATS="$ROOT/checkpoints/fastwam_release/libero_optional_idm_2cam224_dataset_stats.json"

BASE=(
  "task=libero_optional_idm_2cam224_1e-4"
  "ckpt=$CKPT"
  "EVALUATION.dataset_stats_path=$STATS"
  "EVALUATION.sigma_shift=1.0"
  "+EVALUATION.action_infer_mode=idm"
  "EVALUATION.num_trials=$TRIALS"
  "EVALUATION.output_dir=$OUT"
  "MULTIRUN.num_gpus=1"
  "MULTIRUN.task_file=$TASKFILE"
)

# Forced by the offline environment: the README default downloads the Wan2.2
# backbone and ActionDiT from HuggingFace. Both arms get these identical, so
# they cancel out of the comparison.
FORCED=(
  "model.redirect_common_files=false"
  "model.action_dit_pretrained_path=null"
  "model.skip_dit_load_from_pretrain=true"
)

EXTRA=()
if [ "$ARM" = "ours" ]; then
  EXTRA=(
    "model.load_text_encoder=true"
    "EVALUATION.compile_action_infer=false"
    "seed=1"
  )
fi

echo "[gate12c] arm=$ARM gpu=$GPU trials=$TRIALS taskfile=$TASKFILE"
echo "[gate12c] out=$OUT"
$PY experiments/libero/run_libero_manager.py "${BASE[@]}" "${FORCED[@]}" "${EXTRA[@]}"
echo "[gate12c] arm=$ARM exit=$?"
