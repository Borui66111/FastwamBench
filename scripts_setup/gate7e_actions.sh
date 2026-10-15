#!/bin/bash
# Gate7e: instrumented 1-trial rollout -> capture denormalized action chunks.
set -uo pipefail
PY=/data1/liborui/.conda/envs/fastbench/bin/python
ROOT=/data1/liborui/fastwam_bench
cd "$ROOT/FastWAM"
export MUJOCO_GL=egl
export DIFFSYNTH_MODEL_BASE_PATH=$ROOT/checkpoints
export DIFFSYNTH_DOWNLOAD_SOURCE=huggingface
export HF_ENDPOINT=https://hf-mirror.com
export CUDA_DEVICE_ORDER=PCI_BUS_ID
export FASTBENCH_DEBUG_ACTIONS=1

# pick a GPU with NO compute processes and the most free memory
nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader | sort -u > /tmp/fb_used_uuid.txt
GPU=$(nvidia-smi --query-gpu=index,uuid,memory.used,memory.total --format=csv,noheader,nounits \
      | awk -F', ' 'NR==FNR{u[$1]=1;next} !($2 in u){printf "%s,%d\n",$1,($4-$3)}' \
        /tmp/fb_used_uuid.txt - | sort -t, -k2 -n | tail -1 | cut -d, -f1)
if [ -z "${GPU:-}" ]; then
  echo "no idle GPU; falling back to max free memory"
  GPU=$(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader,nounits | sort -t, -k2 -n | head -1 | cut -d, -f1)
fi
echo "using GPU $GPU"
nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv,noheader

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
  EVALUATION.num_trials=1 \
  EVALUATION.replan_steps=10 \
  EVALUATION.output_dir=$ROOT/results/gate7e_actions \
  EVALUATION.compile_action_infer=false
echo "GATE7E_EXIT=$?"
