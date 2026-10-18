#!/usr/bin/env bash
# Gate 14G: displacement magnitude -> chunk response magnitude.
#
# For each displacement size, run the zero-stale arm (strike applied BEFORE the
# policy query, observation refreshed) and dump every action chunk. The control
# run supplies the undisplaced plan at the same replan step and seed, so the
# chunk difference at the strike is the model's measured response to that
# displacement.
#
# Why zero-stale: it removes stale execution as a confound, so the chunk at the
# strike is planned from the post-strike observation and nothing else.
#
#   ./scripts_setup/gate14g_sweep.sh 5 ctl 0.002 0.01
#   ./scripts_setup/gate14g_sweep.sh 7 0.005 0.02 0.04
#
# First argument is the GPU, the rest are magnitudes ("ctl" = control arm).
set -u
cd "$(dirname "$0")/.."

PY=/data1/liborui/.conda/envs/fastbench/bin/python
GPU="${1:?usage: $0 <gpu> <ctl|magnitude>...}"
shift

for M in "$@"; do
    if [ "$M" = "ctl" ]; then
        TAG=g14gctl
        ARMS=control
        MAG=0.01
        ZS=""
    else
        TAG="g14gm$(echo "$M" | sed 's/[^0-9]//g')"
        ARMS=disturb
        MAG="$M"
        ZS="--zero-stale"
    fi

    echo "=== $TAG (arms=$ARMS magnitude=$MAG) on GPU $GPU"
    rm -rf "results/gate13_$TAG"
    FASTBENCH_DUMP_CHUNK="/tmp/chunks_$TAG.jsonl" CUDA_VISIBLE_DEVICES="$GPU" \
        "$PY" scripts_setup/gate13_run.py \
        --tasks libero_object:0 --horizons 10 --seeds 1,2 --trials 3 \
        --arms "$ARMS" --magnitude "$MAG" \
        --world-trigger-after-lift 0.02 --world-repeat-every 10 --world-repeat-count 1 \
        $ZS --tag "$TAG" --ngpu 1 \
        || echo "!!! $TAG exited $?"
done

echo "=== stream done on GPU $GPU"
