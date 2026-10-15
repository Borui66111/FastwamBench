#!/bin/bash
# Gate 9c (world arm only): one-shot object displacement, recorder ON with env state.
set -uo pipefail
PY=/data1/liborui/.conda/envs/fastbench/bin/python
ROOT=/data1/liborui/fastwam_bench
cd "$ROOT/FastWAM"
export MUJOCO_GL=egl DIFFSYNTH_MODEL_BASE_PATH=$ROOT/checkpoints DIFFSYNTH_DOWNLOAD_SOURCE=huggingface
export HF_ENDPOINT=https://hf-mirror.com CUDA_DEVICE_ORDER=PCI_BUS_ID
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

GPU=$(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader,nounits | awk -F, '$2<5000{print $1}' | head -1)
[ -z "$GPU" ] && { echo "NO FREE GPU"; exit 1; }
echo "=== gate9c START $(date) GPU $GPU ==="

DIST=$ROOT/results/gate9b_world_oa_t0
rm -rf "$DIST"
CUDA_VISIBLE_DEVICES=$GPU $PY experiments/libero/eval_libero_single.py \
  task=libero_optional_idm_2cam224_1e-4 \
  ckpt=$ROOT/checkpoints/fastwam_release/libero_optional_idm_2cam224.pt \
  model.load_text_encoder=true model.redirect_common_files=false \
  model.action_dit_pretrained_path=null model.skip_dit_load_from_pretrain=true \
  EVALUATION.dataset_stats_path=$ROOT/checkpoints/fastwam_release/libero_optional_idm_2cam224_dataset_stats.json \
  EVALUATION.sigma_shift=1.0 +EVALUATION.action_infer_mode=idm \
  EVALUATION.task_suite_name=obstacle_avoidance EVALUATION.task_id=0 \
  EVALUATION.num_trials=2 EVALUATION.replan_steps=10 \
  EVALUATION.compile_action_infer=false EVALUATION.recorder_state=true \
  EVALUATION.output_dir=$DIST EVALUATION.recorder_path=$DIST/records.jsonl \
  EVALUATION.intervention_enabled=true \
  EVALUATION.intervention_world_enabled=true \
  EVALUATION.intervention_world_body=akita_black_bowl_1_main \
  +EVALUATION.intervention_world_delta=[0.06,0.06,0.0] \
  EVALUATION.intervention_replan_idx=1 \
  > "$ROOT/logs/gate9c_world.log" 2>&1
echo "DISTURB_EXIT=$?"

$PY - <<'PYEOF'
import json, os
ROOT="/data1/liborui/fastwam_bench"
d=f"{ROOT}/results/gate9b_world_oa_t0"; rp=os.path.join(d,"records.jsonl")
recs=[json.loads(l) for l in open(rp) if l.strip()]
ev={}
for r in recs: ev[r["event"]]=ev.get(r["event"],0)+1
print("events:",ev)
iv=[r for r in recs if r["event"]=="intervention"]
print(f"WORLD intervention events: {len(iv)}")
for r in iv:
    print("  ", {k:r.get(k) for k in ("episode","replan_idx","body","delta","applied","reason")})
    if r.get("qpos_before"):
        print("    qpos_before[:3]:",[round(x,4) for x in r["qpos_before"][:3]])
        print("    qpos_after [:3]:",[round(x,4) for x in r["qpos_after"][:3]])
st=[r for r in recs if r.get("event")=="step" and r.get("stale")]
print("stale steps:",len(st))
if st:
    print("  stale replan_idx set:",sorted({r["replan_idx"] for r in st}))
for r in [x for x in recs if x["event"]=="episode_end"]:
    print(f"  episode {r['episode']}: success={r['success']} steps={r['steps']} "
          f"stale_action_steps={r.get('stale_action_steps')} world={r.get('world_intervention_enabled')} body={r.get('world_body')}")
PYEOF
echo "=== gate9c DONE $(date) ==="