#!/bin/bash
# Gate 9 end-to-end: deterministic mid-chunk intervention + structured recorder.
# Runs a CONTROL (intervention off) and a DISTURBANCE (intervention on) rollout on
# libero_spatial task 0, both with the structured recorder enabled, then verifies
# the recorder output and the determinism of the perturbation.
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
echo "=== gate9 START $(date) using GPU $GPU ==="

COMMON="task=libero_optional_idm_2cam224_1e-4
  ckpt=$ROOT/checkpoints/fastwam_release/libero_optional_idm_2cam224.pt
  model.load_text_encoder=true
  model.redirect_common_files=false
  model.action_dit_pretrained_path=null
  model.skip_dit_load_from_pretrain=true
  EVALUATION.dataset_stats_path=$ROOT/checkpoints/fastwam_release/libero_optional_idm_2cam224_dataset_stats.json
  EVALUATION.sigma_shift=1.0
  +EVALUATION.action_infer_mode=idm
  EVALUATION.task_suite_name=libero_spatial
  EVALUATION.task_id=0
  EVALUATION.num_trials=3
  EVALUATION.compile_action_infer=false"

# ---------- CONTROL (intervention disabled, recorder ON) ----------
CTRL=$ROOT/results/gate9_control_spatial_t0
rm -rf "$CTRL"
CUDA_VISIBLE_DEVICES=$GPU $PY experiments/libero/eval_libero_single.py \
  $COMMON \
  EVALUATION.output_dir=$CTRL \
  EVALUATION.recorder_path=$CTRL/records.jsonl \
  > "$ROOT/logs/gate9_control.log" 2>&1
echo "CONTROL_EXIT=$?"

# ---------- DISTURBANCE (intervention ON, recorder ON) ----------
DIST=$ROOT/results/gate9_disturb_spatial_t0
rm -rf "$DIST"
CUDA_VISIBLE_DEVICES=$GPU $PY experiments/libero/eval_libero_single.py \
  $COMMON \
  EVALUATION.output_dir=$DIST \
  EVALUATION.recorder_path=$DIST/records.jsonl \
  EVALUATION.intervention_enabled=true \
  EVALUATION.intervention_mode=zero_action \
  EVALUATION.intervention_replan_idx=1 \
  EVALUATION.intervention_step_in_chunk=1 \
  EVALUATION.intervention_seed=0 \
  > "$ROOT/logs/gate9_disturb.log" 2>&1
echo "DISTURB_EXIT=$?"

echo "=== VERIFY ==="
$PY - <<'PYEOF'
import json, glob, os
ROOT = "/data1/liborui/fastwam_bench"
for label, d in (("CONTROL", f"{ROOT}/results/gate9_control_spatial_t0"),
                 ("DISTURB", f"{ROOT}/results/gate9_disturb_spatial_t0")):
    rp = os.path.join(d, "records.jsonl")
    print(f"--- {label}: {rp}")
    if not os.path.exists(rp):
        print("   !! recorder file MISSING"); continue
    recs = [json.loads(l) for l in open(rp) if l.strip()]
    ev = {}
    for r in recs:
        ev[r["event"]] = ev.get(r["event"], 0) + 1
    print("   events:", ev)
    iv = [r for r in recs if r["event"] == "step" and r.get("intervened")]
    print(f"   intervened steps: {len(iv)}")
    for r in iv:
        print(f"     ep={r['episode']} replan={r['replan_idx']} step_in_chunk={r['step_in_chunk']} "
              f"action={[round(x,3) for x in r['action']]}")
    ends = [r for r in recs if r["event"] == "episode_end"]
    print("   episodes:", [(r["episode"], r["success"], r["steps"]) for r in ends])
    for p in sorted(glob.glob(f"{d}/*/gpu*_task0_results.json")):
        j = json.load(open(p))
        print("   RESULT:", j["task_suite"], "task", j["task_id"], "=",
              j["successes"], "/", j["total_episodes"], "succ_eps", j["success_episodes"])
PYEOF
echo "=== gate9 DONE $(date) ==="
