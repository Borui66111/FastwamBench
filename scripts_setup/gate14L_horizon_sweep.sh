#!/usr/bin/env bash
# Gate 14L: does the future-aware pathway's advantage scale with commitment horizon?
#
# The carry-regime null (Gate 14) says the cost of a mid-carry strike is not specific
# to future-conditioned inference. The approach regime is the one place a difference
# appeared (idm 11/12 vs first_frame 5/12 at 400 steps; 12/12 vs 5/12 at 800). n=12
# cannot support a claim, and the effect there could be anything.
#
# Design. In the approach regime the strike lands at env step 40, BEFORE the grasp, so
# the committed chunk spans the approach rather than the carry. Sweep replan_steps over
# {1,2,5,10} for both pathways and both arms.
#
# The prediction worth testing: at H=1 there is no future to condition on
# (num_future_frames = replan_steps // 4 = 0, so keep_frames = 1), and the policy
# re-plans every step from a fresh observation. So the two pathways should be
# informationally equivalent at H=1 and any advantage should appear only as H grows.
# If the advantage is flat across H, the thesis is dead in this regime too.
#
# Always max-steps 800: the 400-step budget times the control arm out, which made the
# 400-step approach numbers uninterpretable (see gate14_i / approach budget arm).
#
# NOTE no --zero-stale here. The stale action IS the mechanism under test; refreshing
# the observation would delete the very thing being measured.
#
#   ./scripts_setup/gate14L_horizon_sweep.sh 3 1 2 5 10
#
# First argument is the GPU, the rest are horizons.
set -u
cd "$(dirname "$0")/.."

PY=/data1/liborui/.conda/envs/fastbench/bin/python
GPU="${1:?usage: $0 <gpu> <horizon>...}"
shift
SEEDS="${SEEDS:-1,2,3,4,5,6}"
TRIALS="${TRIALS:-6}"
MODE="${MODE:-idm}"
# The tag uses a short form; the flag must keep the exact mode name.
TAGMODE="$(echo "$MODE" | sed 's/first_frame/ff/')"
TAGPFX="${TAGPFX:-g14L}"

for H in "$@"; do
    TAG="${TAGPFX}_${TAGMODE}_H${H}"
    echo "=== $TAG (mode=$MODE H=$H seeds=$SEEDS trials=$TRIALS) on GPU $GPU"
    rm -rf "results/gate13_$TAG"
    CUDA_VISIBLE_DEVICES="$GPU" \
        "$PY" scripts_setup/gate13_run.py \
        --tasks libero_object:0 --horizons "$H" --seeds "$SEEDS" --trials "$TRIALS" \
        --arms control,disturb --magnitude 0.01 \
        --world-step 40 --world-repeat-every 10 --world-repeat-count 4 \
        --action-infer-mode "$MODE" --max-steps 800 \
        --tag "$TAG" --ngpu 1 \
        || echo "!!! $TAG exited $?"
done

echo "=== stream done on GPU $GPU mode=$MODE"
