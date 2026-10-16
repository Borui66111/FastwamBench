#!/bin/bash
# Gate 13: paired control-vs-disturbance on a task with USABLE control success.
#
# Both arms run the same task, init states (file order), seed, model config and
# replan horizon, so episode i in `control` and episode i in `disturb` are a
# matched pair: they are bit-identical up to the intervention step. The only
# difference is the one-shot world-state displacement at replan_idx=1.
#
#   SUITE=libero_spatial TASK_ID=0 BODY=akita_black_bowl_1_main \
#   RS=1 TRIALS=10 bash scripts_setup/gate13_paired.sh
#   python scripts_setup/gate13_analyze.py
set -uo pipefail
PY=/data1/liborui/.conda/envs/fastbench/bin/python
ROOT=/data1/liborui/fastwam_bench
cd "$ROOT/FastWAM"
export MUJOCO_GL=egl DIFFSYNTH_MODEL_BASE_PATH=$ROOT/checkpoints DIFFSYNTH_DOWNLOAD_SOURCE=huggingface
export HF_ENDPOINT=https://hf-mirror.com CUDA_DEVICE_ORDER=PCI_BUS_ID
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

SUITE=${SUITE:-libero_spatial}
TASK_ID=${TASK_ID:-0}
BODY=${BODY:-akita_black_bowl_1_main}
DELTA=${DELTA:-[0.06,0.06,0.0]}
RS=${RS:-1}
TRIALS=${TRIALS:-10}
SEED=${SEED:-1}
TAG=${TAG:-${SUITE}_t${TASK_ID}_rs${RS}}
OUTBASE=${OUTBASE:-$ROOT/results/gate13_$TAG}

if [ -z "${GPU:-}" ]; then
  GPU=$(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader,nounits | awk -F, '$2<5000{print $1}' | head -1)
fi
[ -z "$GPU" ] && { echo "NO FREE GPU"; exit 1; }
echo "=== gate13 START $(date) GPU $GPU task=$SUITE/$TASK_ID rs=$RS trials=$TRIALS seed=$SEED ==="

COMMON="task=libero_optional_idm_2cam224_1e-4
  ckpt=$ROOT/checkpoints/fastwam_release/libero_optional_idm_2cam224.pt
  model.load_text_encoder=true
  model.redirect_common_files=false
  model.action_dit_pretrained_path=null
  model.skip_dit_load_from_pretrain=true
  EVALUATION.dataset_stats_path=$ROOT/checkpoints/fastwam_release/libero_optional_idm_2cam224_dataset_stats.json
  EVALUATION.sigma_shift=1.0
  +EVALUATION.action_infer_mode=idm
  EVALUATION.task_suite_name=$SUITE
  EVALUATION.task_id=$TASK_ID
  EVALUATION.num_trials=$TRIALS
  seed=$SEED
  EVALUATION.compile_action_infer=false
  EVALUATION.recorder_state=true
  EVALUATION.intervention_replan_idx=1"

for ARM in control disturb; do
  OUT=${OUTBASE}_${ARM}
  rm -rf "$OUT"
  EXTRA=""
  if [ "$ARM" = "disturb" ]; then
    EXTRA="EVALUATION.intervention_enabled=true
           EVALUATION.intervention_world_enabled=true
           EVALUATION.intervention_world_body=$BODY
           +EVALUATION.intervention_world_delta=$DELTA"
  fi
  echo "--- run $ARM -> $OUT"
  CUDA_VISIBLE_DEVICES=$GPU $PY experiments/libero/eval_libero_single.py \
    $COMMON EVALUATION.replan_steps=$RS \
    EVALUATION.output_dir=$OUT EVALUATION.recorder_path=$OUT/records.jsonl \
    $EXTRA > "$ROOT/logs/gate13_${TAG}_${ARM}.log" 2>&1
  echo "    exit=$?"
done

echo "=== ANALYZE ==="
GATE13_TAG=$TAG $PY "$ROOT/scripts_setup/gate13_analyze.py"
echo "=== gate13 DONE $(date) ==="
