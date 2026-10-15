#!/bin/bash
# Gate 9b end-to-end: WORLD-state intervention (H3 stale-plan condition).
# Control (no intervention) vs Disturbance (one-shot object displacement) on
# LIBERO-Safety obstacle_avoidance L0 task 0, recorder ON with env-state capture.
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
echo "=== gate9b START $(date) using GPU $GPU ==="

COMMON="task=libero_optional_idm_2cam224_1e-4
  ckpt=$ROOT/checkpoints/fastwam_release/libero_optional_idm_2cam224.pt
  model.load_text_encoder=true
  model.redirect_common_files=false
  model.action_dit_pretrained_path=null
  model.skip_dit_load_from_pretrain=true
  EVALUATION.dataset_stats_path=$ROOT/checkpoints/fastwam_release/libero_optional_idm_2cam224_dataset_stats.json
  EVALUATION.sigma_shift=1.0
  +EVALUATION.action_infer_mode=idm
  EVALUATION.task_suite_name=obstacle_avoidance
  EVALUATION.task_id=0
  EVALUATION.num_trials=2
  EVALUATION.replan_steps=10
  EVALUATION.compile_action_infer=false
  EVALUATION.recorder_state=true"

# ---------- CONTROL (recorder ON, no intervention) ----------
CTRL=$ROOT/results/gate9b_control_oa_t0
rm -rf "$CTRL"
CUDA_VISIBLE_DEVICES=$GPU $PY experiments/libero/eval_libero_single.py \
  $COMMON EVALUATION.output_dir=$CTRL EVALUATION.recorder_path=$CTRL/records.jsonl \
  > "$ROOT/logs/gate9b_control.log" 2>&1
echo "CONTROL_EXIT=$?"

# ---------- DISTURBANCE (world displacement of the manipulated bowl) ----------
DIST=$ROOT/results/gate9b_world_oa_t0
rm -rf "$DIST"
CUDA_VISIBLE_DEVICES=$GPU $PY experiments/libero/eval_libero_single.py \
  $COMMON EVALUATION.output_dir=$DIST EVALUATION.recorder_path=$DIST/records.jsonl \
  EVALUATION.intervention_enabled=true \
  EVALUATION.intervention_world_enabled=true \
  EVALUATION.intervention_world_body=akita_black_bowl_1_main \
  +EVALUATION.intervention_world_delta=[0.06,0.06,0.0] \
  EVALUATION.intervention_replan_idx=1 \
  > "$ROOT/logs/gate9b_world.log" 2>&1
echo "DISTURB_EXIT=$?"

echo "=== VERIFY ==="
$PY - <<'PYEOF'
import json, glob, os
ROOT = "/data1/liborui/fastwam_bench"
for label, d in (("CONTROL", f"{ROOT}/results/gate9b_control_oa_t0"),
                 ("WORLD",   f"{ROOT}/results/gate9b_world_oa_t0")):
    rp = os.path.join(d, "records.jsonl")
    print(f"--- {label}")
    if not os.path.exists(rp):
        print("   !! recorder MISSING"); continue
    recs = [json.loads(l) for l in open(rp) if l.strip()]
    ev = {}
    for r in recs:
        ev[r["event"]] = ev.get(r["event"], 0) + 1
    print("   events:", ev)
    print("   distinct replan_idx:", sorted({r.get("replan_idx") for r in recs if "replan_idx" in r})[:6], "...")
    print("   distinct step_in_chunk:", sorted({r.get("step_in_chunk") for r in recs if r.get("event") == "step"}))
    iv = [r for r in recs if r["event"] == "intervention"]
    print(f"   WORLD intervention events: {len(iv)}")
    for r in iv:
        print("     ", {k: r[k] for k in ("episode","replan_idx","body","delta","applied","reason")})
        if r.get("qpos_before"):
            print("       qpos_before[:3]:", [round(x,4) for x in r["qpos_before"][:3]])
            print("       qpos_after [:3]:", [round(x,4) for x in r["qpos_after"][:3]])
    stale = [r for r in recs if r.get("event") == "step" and r.get("stale")]
    print(f"   stale steps: {len(stale)}")
    ends = [r for r in recs if r["event"] == "episode_end"]
    for r in ends:
        print(f"   episode {r['episode']}: success={r['success']} steps={r['steps']} "
              f"stale_action_steps={r.get('stale_action_steps')} world={r.get('world_intervention_enabled')}")
    # env-state capture proof
    st = [r for r in recs if r.get("event") == "step" and isinstance(r.get("state"), dict)]
    if st:
        s0 = st[0]["state"]
        print("   state capture OK; eef:", s0.get("eef", {}).get("pos") if s0.get("eef") else None)
        print("     bodies tracked:", list(s0.get("bodies", {}).keys())[:6])
    for p in sorted(glob.glob(f"{d}/*/gpu*_task0_results.json")):
        j = json.load(open(p))
        print("   RESULT:", j["task_suite"], "task", j["task_id"], "=", j["successes"], "/", j["total_episodes"])
PYEOF
echo "=== gate9b DONE $(date) ==="
