#!/bin/bash
# Keep the published (tracked) copy of the FastWAM harness patch in sync with the
# live tree. FastWAM/ is gitignored, so patches/ is the only copy remote
# collaborators see -- run this after editing the live file, before committing.
#
#   bash scripts_setup/sync_patches.sh          # live -> patches (default)
#   bash scripts_setup/sync_patches.sh --check  # diff only, no write
set -uo pipefail
ROOT=/data1/liborui/fastwam_bench
LIVE=$ROOT/FastWAM/experiments/libero/fastbench_intervention.py
PUB=$ROOT/patches/fastbench_intervention.py

[ -f "$LIVE" ] || { echo "MISSING live file: $LIVE"; exit 1; }

if [ "${1:-}" = "--check" ]; then
  if diff -q "$LIVE" "$PUB" >/dev/null 2>&1; then
    echo "IN SYNC"
    exit 0
  fi
  echo "OUT OF SYNC (live vs patches/):"
  diff "$PUB" "$LIVE" | head -40
  exit 2
fi

cp "$LIVE" "$PUB"
echo "synced: live -> patches/  ($(wc -l < "$PUB") lines)"
