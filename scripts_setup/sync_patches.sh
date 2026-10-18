#!/bin/bash
# Keep the published (tracked) copies of the FastWAM harness in sync with the
# live tree. FastWAM/ is gitignored, so patches/ is the only copy remote
# collaborators see -- run this after editing live files, before committing.
#
#   bash scripts_setup/sync_patches.sh          # live -> patches (default)
#   bash scripts_setup/sync_patches.sh --check  # diff only, no write
set -uo pipefail
ROOT=/data1/liborui/fastwam_bench
BASE=$(cat "$ROOT/patches/BASE_COMMIT.txt")
LIVE=$ROOT/FastWAM/experiments/libero/fastbench_intervention.py
PUB=$ROOT/patches/fastbench_intervention.py
CORE=$ROOT/patches/0002-eval-harness-psnr-strikes.patch

[ -f "$LIVE" ] || { echo "MISSING live file: $LIVE"; exit 1; }

# Regenerate the patch for the two UPSTREAM-modified files. These are the ones
# that carry the PSNR instrumentation, per-clip records, strike provenance and
# the robot-init fix; without this they exist only in the untracked tree and a
# reviewer cannot reproduce anything.
gen_core() {
  ( cd "$ROOT/FastWAM" && git diff "$BASE" -- \
      experiments/libero/eval_libero_single.py \
      experiments/libero/libero_utils.py )
}

if [ "${1:-}" = "--check" ]; then
  rc=0
  if diff -q "$LIVE" "$PUB" >/dev/null 2>&1; then
    echo "IN SYNC  patches/fastbench_intervention.py"
  else
    echo "OUT OF SYNC  patches/fastbench_intervention.py"
    diff "$PUB" "$LIVE" | head -30
    rc=2
  fi
  gen_core > /tmp/_core.patch
  if diff -q /tmp/_core.patch "$CORE" >/dev/null 2>&1; then
    echo "IN SYNC  patches/0002-eval-harness-psnr-strikes.patch"
  else
    echo "OUT OF SYNC  patches/0002-eval-harness-psnr-strikes.patch"
    diff "$CORE" /tmp/_core.patch | head -30
    rc=2
  fi
  exit $rc
fi

cp "$LIVE" "$PUB"
gen_core > "$CORE"
echo "synced: live -> patches/fastbench_intervention.py ($(wc -l < "$PUB") lines)"
echo "synced: git diff -> patches/0002-eval-harness-psnr-strikes.patch ($(wc -l < "$CORE") lines)"
