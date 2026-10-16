#!/bin/bash
# Gate 11: control vs disturbance sweep over replan_steps in {1, 5, 10}.
# Control   = recorder ON, no intervention.
# Disturb   = one-shot world-state displacement of the manipulated object at
#             replan_idx=1, i.e. the instant after a chunk was planned against
#             the pre-intervention world (WARM_START §9.2/§9.3).
# Emits a recovery analysis from the recorded per-step env state.
set -uo pipefail
PY=/data1/liborui/.conda/envs/fastbench/bin/python
ROOT=/data1/liborui/fastwam_bench
cd "$ROOT/FastWAM"
export MUJOCO_GL=egl DIFFSYNTH_MODEL_BASE_PATH=$ROOT/checkpoints DIFFSYNTH_DOWNLOAD_SOURCE=huggingface
export HF_ENDPOINT=https://hf-mirror.com CUDA_DEVICE_ORDER=PCI_BUS_ID
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

GPU=$(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader,nounits | awk -F, '$2<5000{print $1}' | head -1)
[ -z "$GPU" ] && { echo "NO FREE GPU"; exit 1; }
echo "=== gate11 START $(date) GPU $GPU ==="

TRIALS=${TRIALS:-2}
# Both arms MUST use the same fixed seed: without it `set_global_seed` is never
# called (eval_libero_single.py: `if cfg.get("seed") is not None`) and the
# diffusion sampling noise differs per invocation, so control and disturbance are
# not comparable step-by-step. With a pinned seed the two arms are bit-identical
# up to the intervention and diverge only because the world changed.
# NOTE: seed must satisfy 0 < seed < 2**32-1 (set_global_seed asserts strictly
# inside the uint32 bounds), so 0 is invalid — default to 1.
SEED=${SEED:-1}
BODY=akita_black_bowl_1_main
DELTA="[0.06,0.06,0.0]"

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
  EVALUATION.num_trials=$TRIALS
  seed=$SEED
  EVALUATION.compile_action_infer=false
  EVALUATION.recorder_state=true
  EVALUATION.intervention_replan_idx=1"

RS_LIST=${RS_LIST:-"1 5 10"}
# Optional tag so a post-fix re-run does NOT clobber the historical Gate 11 results
# (this loop `rm -rf`s its output dir). e.g. OUT_TAG=pf -> results/gate11pf_<arm>_rs<N>
TAG=${OUT_TAG:+${OUT_TAG}_}
for RS in $RS_LIST; do
  for ARM in control disturb; do
    OUT=$ROOT/results/gate11${TAG}_${ARM}_rs${RS}
    rm -rf "$OUT"
    EXTRA=""
    if [ "$ARM" = "disturb" ]; then
      EXTRA="EVALUATION.intervention_enabled=true
             EVALUATION.intervention_world_enabled=true
             EVALUATION.intervention_world_body=$BODY
             +EVALUATION.intervention_world_delta=$DELTA"
    fi
    echo "--- run $ARM replan_steps=$RS -> $OUT"
    CUDA_VISIBLE_DEVICES=$GPU $PY experiments/libero/eval_libero_single.py \
      $COMMON EVALUATION.replan_steps=$RS \
      EVALUATION.output_dir=$OUT EVALUATION.recorder_path=$OUT/records.jsonl \
      $EXTRA > "$ROOT/logs/gate11_${ARM}_rs${RS}.log" 2>&1
    echo "    exit=$?"
  done
done

echo "=== ANALYZE ==="
$PY - <<'PYEOF'
import json, os, glob, math
ROOT = "/data1/liborui/fastwam_bench"

def dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

rows = []
_tag = ("_" + os.environ["OUT_TAG"]) if os.environ.get("OUT_TAG") else ""
for rs in (1, 5, 10):
    for arm in ("control", "disturb"):
        d = f"{ROOT}/results/gate11{_tag}_{arm}_rs{rs}"
        rp = os.path.join(d, "records.jsonl")
        if not os.path.exists(rp):
            rows.append((rs, arm, None, None, None, None, None)); continue
        recs = [json.loads(l) for l in open(rp) if l.strip()]
        ends = [r for r in recs if r["event"] == "episode_end"]
        ivs  = [r for r in recs if r["event"] == "intervention"]
        steps = [r for r in recs if r["event"] == "step" and isinstance(r.get("state"), dict)]
        nsucc = sum(1 for e in ends if e.get("success"))
        stale = sum(e.get("stale_action_steps", 0) for e in ends)
        # --- recovery: re-acquisition latency of the manipulated object ---
        lat = []
        for e in ends:
            ep = e["episode"]
            es = [r for r in steps if r["episode"] == ep]
            body = (ivs[0]["body"] if ivs else None)
            if not body:
                continue
            # intervention step index within the episode
            iv_step = None
            for r in es:
                if r.get("world_intervened"):
                    iv_step = r["t"]; break
            if iv_step is None:
                continue
            hit = None
            best = None
            for r in es:
                if r["t"] <= iv_step:
                    continue
                st = r["state"]
                obj = st.get("bodies", {}).get(body, {}).get("pos")
                eef = (st.get("eef") or {}).get("pos")
                if obj and eef:
                    dd = dist(obj, eef)
                    if best is None or dd < best:
                        best = dd
                    # 0.05 m is unreachable for this gripper/task (observed min
                    # ~0.33 m), so latch on the minimum over the post-iv window.
                    if dd < 0.12:
                        hit = r["t"] - iv_step; break
            lat.append(hit if hit is not None else -1)
        # --- object net motion after the intervention ---
        net = []
        for e in ends:
            ep = e["episode"]
            es = [r for r in steps if r["episode"] == ep]
            body = (ivs[0]["body"] if ivs else None)
            if not body:
                continue
            pre = post = None
            for r in es:
                p = r["state"].get("bodies", {}).get(body, {}).get("pos")
                if p is None: continue
                if not r.get("world_intervened") and pre is None:
                    pre = p
                post = p
            if pre and post:
                net.append(round(dist(pre, post), 4))
        rows.append((rs, arm, nsucc, len(ends), stale, lat, net))

print(f"{'replan_steps':>12} {'arm':>8} {'succ':>5} {'eps':>4} {'stale_steps':>12} {'reacq_latency(t)':>18} {'obj_net_motion':>16}")
for rs, arm, nsucc, neps, stale, lat, net in rows:
    if nsucc is None:
        print(f"{rs:>12} {arm:>8}   MISSING"); continue
    print(f"{rs:>12} {arm:>8} {nsucc:>5} {neps:>4} {stale:>12} {str(lat):>18} {str(net):>16}")
PYEOF
echo "=== gate11 DONE $(date) ==="