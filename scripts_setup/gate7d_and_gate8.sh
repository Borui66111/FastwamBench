#!/bin/bash
# Gate 7 evidence + last config hypothesis (explicit sigma_shift=1.0), then Gate 8.
set -uo pipefail
PY=/data1/liborui/.conda/envs/fastbench/bin/python
ROOT=/data1/liborui/fastwam_bench
EV=$ROOT/results/gate7_evidence
mkdir -p "$EV"

echo "=== GATE 7 EVIDENCE ===" | tee "$EV/evidence.txt"
{ echo "date: $(date)"; echo; echo "--- FastWAM git ---";
  git -C $ROOT/FastWAM rev-parse HEAD; git -C $ROOT/FastWAM status --porcelain | head;
  echo; echo "--- LIBERO-Safety git ---";
  git -C $ROOT/LIBERO-Safety rev-parse HEAD; git -C $ROOT/LIBERO-Safety status --porcelain | head;
  echo; echo "--- ckpt ---";
  ls -la $ROOT/checkpoints/fastwam_release/;
  echo; echo "--- python env ---";
  $PY -c "import torch;print('torch',torch.__version__,'cuda',torch.cuda.is_available())";
  $PY -c "import mujoco,robosuite,libero;print('mujoco',mujoco.__version__,'robosuite',robosuite.__version__)";
} >> "$EV/evidence.txt" 2>&1

cd "$ROOT/FastWAM"
export MUJOCO_GL=egl DIFFSYNTH_MODEL_BASE_PATH=$ROOT/checkpoints
export DIFFSYNTH_DOWNLOAD_SOURCE=huggingface HF_ENDPOINT=https://hf-mirror.com
export CUDA_DEVICE_ORDER=PCI_BUS_ID
GPU=$(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader,nounits | sort -t, -k2 -n | head -1 | cut -d, -f1)
echo "using GPU $GPU" | tee -a "$EV/evidence.txt"

echo "=== Gate7d: optional_idm, explicit sigma_shift=1.0, 5 trials ==="
CUDA_VISIBLE_DEVICES=$GPU $PY experiments/libero/eval_libero_single.py \
  task=libero_optional_idm_2cam224_1e-4 \
  ckpt=$ROOT/checkpoints/fastwam_release/libero_optional_idm_2cam224.pt \
  model.load_text_encoder=true model.redirect_common_files=false \
  model.action_dit_pretrained_path=null model.skip_dit_load_from_pretrain=true \
  EVALUATION.dataset_stats_path=$ROOT/checkpoints/fastwam_release/libero_optional_idm_2cam224_dataset_stats.json \
  EVALUATION.task_suite_name=libero_spatial EVALUATION.task_id=0 \
  EVALUATION.num_trials=5 EVALUATION.sigma_shift=1.0 \
  EVALUATION.output_dir=$ROOT/results/gate7d_optional_idm_shift1 \
  EVALUATION.compile_action_infer=false \
  > $ROOT/logs/gate7d_shift1.log 2>&1
echo "Gate7d exit=$?" | tee -a "$EV/evidence.txt"
grep -E "successes|total_episodes|Task 0 completed" $ROOT/results/gate7d_optional_idm_shift1/libero_spatial/*.json 2>/dev/null | tee -a "$EV/evidence.txt"

echo "=== Gate 8: LIBERO-Safety obstacle_avoidance task0, 3 trials, no intervention ==="
CUDA_VISIBLE_DEVICES=$GPU $PY experiments/libero/eval_libero_single.py \
  task=libero_optional_idm_2cam224_1e-4 \
  ckpt=$ROOT/checkpoints/fastwam_release/libero_optional_idm_2cam224.pt \
  model.load_text_encoder=true model.redirect_common_files=false \
  model.action_dit_pretrained_path=null model.skip_dit_load_from_pretrain=true \
  EVALUATION.dataset_stats_path=$ROOT/checkpoints/fastwam_release/libero_optional_idm_2cam224_dataset_stats.json \
  EVALUATION.task_suite_name=obstacle_avoidance EVALUATION.task_id=0 \
  EVALUATION.num_trials=3 EVALUATION.sigma_shift=1.0 \
  EVALUATION.output_dir=$ROOT/results/gate8_obstacle_avoidance_L0_t0 \
  EVALUATION.compile_action_infer=false \
  > $ROOT/logs/gate8_obstacle.log 2>&1
echo "Gate8 exit=$?" | tee -a "$EV/evidence.txt"
cat $ROOT/results/gate8_obstacle_avoidance_L0_t0/obstacle_avoidance/*.json 2>/dev/null | tee -a "$EV/evidence.txt"
echo "=== ALL DONE ==="