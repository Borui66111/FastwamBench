#!/bin/bash
# Gate C: download LIBERO-Safety assets.zip from HF mirror and extract into libero/libero/assets
set -euo pipefail
export HF_ENDPOINT=https://hf-mirror.com
LOG=/data1/liborui/fastwam_bench/logs/gateC_assets.log
DEST=/data1/liborui/fastwam_bench/checkpoints/libero_safety_assets
mkdir -p "$DEST"
echo "=== START $(date) ===" | tee -a "$LOG"

curl -L --fail --retry 5 --retry-delay 5 -C - \
  -o "$DEST/assets.zip" \
  "https://hf-mirror.com/datasets/LIBERO-Safety/libero_safety_assets/resolve/main/assets.zip" \
  2>&1 | tail -5 | tee -a "$LOG"

ls -la "$DEST/assets.zip" | tee -a "$LOG"
echo "=== DONE $(date) ===" | tee -a "$LOG"
