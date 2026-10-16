#!/bin/bash
# Gate 12A: baseline CONTROL-success screen (no intervention).
#
# Purpose: find tasks with a usable control success rate (~30-90%). Gate 11's
# task (obstacle_avoidance L0 task 0) is 0/2 in BOTH arms, so it cannot show
# that a stale commitment COSTS success — that needs a task that can succeed.
#
# Uses run_libero_manager.py: one persistent model worker per GPU, task list
# distributed across GPUs, crashed GPU quarantined + task requeued.
#
# Usage:
#   TASKFILE=scripts_setup/gate12a_canary_tasks.txt TRIALS=2 GPUS=5,7 \
#     bash scripts_setup/gate12_screen.sh
#
# Output: <OUT>/<suite>/gpu<id>_task<id>_results.json  (+ manager_config.yaml,
#         tasks.txt, .worker_pool/). Aggregate with gate12a_aggregate.py.
#
# NOTE: every comparison run must pin seed=N (N>0) or set_global_seed is skipped
# and diffusion noise differs per invocation.
set -uo pipefail
PY=/data1/liborui/.conda/envs/fastbench/bin/python
ROOT=/data1/liborui/fastwam_bench
cd "$ROOT/FastWAM" || exit 1
export MUJOCO_GL=egl DIFFSYNTH_MODEL_BASE_PATH=$ROOT/checkpoints DIFFSYNTH_DOWNLOAD_SOURCE=huggingface
export HF_ENDPOINT=https://hf-mirror.com CUDA_DEVICE_ORDER=PCI_BUS_ID
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

GPUS=${GPUS:-5,7}
NGPU=${NGPU:-2}
TRIALS=${TRIALS:-3}
SEED=${SEED:-1}
OUT=${OUT:-$ROOT/results/gate12a_screen}
TASKFILE=${TASKFILE:-$ROOT/scripts_setup/gate12a_canary_tasks.txt}
mkdir -p "$ROOT/logs" "$OUT"

[ -f "$TASKFILE" ] || { echo "MISSING task file: $TASKFILE"; exit 1; }
echo "=== gate12A screen START $(date) ==="
echo "GPUs=$GPUS ngpu=$NGPU trials=$TRIALS seed=$SEED"
echo "task file: $TASKFILE ($(grep -c . "$TASKFILE") tasks)"
echo "output: $OUT"
echo "task list:"; sed 's/^/    /' "$TASKFILE"

export CUDA_VISIBLE_DEVICES=$GPUS
$PY experiments/libero/run_libero_manager.py \
  task=libero_optional_idm_2cam224_1e-4 \
  ckpt=$ROOT/checkpoints/fastwam_release/libero_optional_idm_2cam224.pt \
  model.load_text_encoder=true \
  model.redirect_common_files=false \
  model.action_dit_pretrained_path=null \
  model.skip_dit_load_from_pretrain=true \
  EVALUATION.dataset_stats_path=$ROOT/checkpoints/fastwam_release/libero_optional_idm_2cam224_dataset_stats.json \
  EVALUATION.sigma_shift=1.0 \
  +EVALUATION.action_infer_mode=idm \
  EVALUATION.num_trials=$TRIALS \
  seed=$SEED \
  EVALUATION.compile_action_infer=false \
  EVALUATION.output_dir=$OUT \
  MULTIRUN.num_gpus=$NGPU \
  MULTIRUN.task_file=$TASKFILE \
  > "$ROOT/logs/gate12a_manager.log" 2>&1
echo "manager exit=$?"
echo "=== gate12A screen DONE $(date) ==="
