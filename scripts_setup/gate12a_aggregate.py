#!/usr/bin/env python
"""Gate 12A aggregator: baseline control-success screen -> CSV + table.

Reads every <OUT>/<suite>/gpu<id>_task<id>_results.json written by
eval_libero_single.py and emits a per-task table plus a CSV.

Level: LIBERO-Safety suites pack 5 base tasks x 3 levels into a flat task_id
space (id = level*5 + k), so level = task_id // 5 for those suites; the standard
LIBERO suites are single-level (level 0).
"""
import csv
import glob
import json
import os
import sys

ROOT = "/data1/liborui/fastwam_bench"
OUT = sys.argv[1] if len(sys.argv) > 1 else f"{ROOT}/results/gate12a_screen"
# Derive the CSV name from OUT so a second screen (e.g. post-fix) does not
# silently overwrite the first one's summary.
CSV_PATH = sys.argv[2] if len(sys.argv) > 2 else f"{OUT.rstrip('/')}_summary.csv"

# suites that are 5 base tasks x 3 levels
SAFETY = {
    "obstacle_avoidance", "obstacle_avoidance_human", "affordance",
    "human_safety", "reasoning_safety",
}


def level_of(suite: str, task_id: int) -> int:
    return task_id // 5 if suite in SAFETY else 0


rows = []
for path in sorted(glob.glob(os.path.join(OUT, "*", "gpu*_task*_results.json"))):
    try:
        d = json.load(open(path))
    except Exception as e:  # noqa: BLE001
        print(f"SKIP {path}: {e}")
        continue
    suite = d.get("task_suite") or os.path.basename(os.path.dirname(path))
    tid = int(d.get("task_id", -1))
    tot = int(d.get("total_episodes", 0) or 0)
    suc = int(d.get("successes", 0) or 0)
    rows.append({
        "suite": suite,
        "task_id": tid,
        "level": level_of(suite, tid),
        "successes": suc,
        "trials": tot,
        "success_rate": round(suc / tot, 4) if tot else 0.0,
        "duration_s": round(float(d.get("duration", 0) or 0), 1),
        "description": (d.get("task_description") or "")[:70],
    })

rows.sort(key=lambda r: (-r["success_rate"], r["suite"], r["task_id"]))

with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=[
        "suite", "task_id", "level", "successes", "trials", "success_rate",
        "duration_s", "description"])
    w.writeheader()
    w.writerows(rows)

hdr = f"{'suite':>24} {'tid':>4} {'L':>2} {'succ':>5} {'n':>3} {'rate':>7} {'dur_s':>8}"
print(hdr)
print("-" * len(hdr))
for r in rows:
    print(f"{r['suite']:>24} {r['task_id']:>4} {r['level']:>2} "
          f"{r['successes']:>5} {r['trials']:>3} {r['success_rate']:>7.2f} "
          f"{r['duration_s']:>8.1f}")

usable = [r for r in rows if 0.3 <= r["success_rate"] <= 0.9]
print(f"\n{len(rows)} tasks screened; CSV -> {CSV_PATH}")
print(f"USABLE (0.30 <= rate <= 0.90): {len(usable)}")
for r in usable:
    print(f"   {r['suite']} t{r['task_id']} (L{r['level']}): "
          f"{r['successes']}/{r['trials']} = {r['success_rate']:.2f}")
