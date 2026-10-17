#!/usr/bin/env python
"""[fastbench] Gate 13: world-model damage measured on the intervention clip only.

Why this file exists
--------------------
`episode_mean_psnr` averages frame k over EVERY clip in an episode. Only the clip
planned at the intervention step is damaged, so the episode mean dilutes the effect
by 1/n_clips, and n_clips ~ total_steps/H differs by ~10x between H=1 and H=10.
Any cross-horizon comparison built on that number is confounded by the dilution
factor, not by the horizon.

The fix: score the clip planned at `start_step == WORLD_STEP` only, in BOTH arms.
Control and disturb share that clip's planning step and pre-plan world state, so the
only difference is the displacement applied right after planning.

Output: per (H, lag) control / disturb PSNR and their difference.
"""
import glob
import json
import sys
from collections import defaultdict

WORLD_STEP = int(sys.argv[2]) if len(sys.argv) > 2 else 40
root = sys.argv[1] if len(sys.argv) > 1 else "results/gate13_psnr_clip"

# (H, arm) -> list of frame_psnr dicts for the intervention clip, one per episode
rows = defaultdict(list)

for path in sorted(glob.glob(f"{root}/*/H*/*/records.jsonl")):
    parts = path.split("/")
    h = int(parts[-3][1:])
    arm = parts[-2].split("_")[0]
    recs = [json.loads(line) for line in open(path) if line.strip()]
    for ep in (r for r in recs if r.get("event") == "episode_end"):
        clips = ep.get("episode_clip_psnr") or []
        hit = [c for c in clips if c.get("start_step") == WORLD_STEP]
        if hit:
            rows[(h, arm)].append(hit[0]["frame_psnr"])

print(f"intervention clip = the clip planned at start_step {WORLD_STEP}\n")

hdr = f"{'H':>3} {'lag':>4} {'control':>9} {'disturb':>9} {'delta':>8} {'n':>6}"
print(hdr)
print("-" * len(hdr))

def _lag_values(fp):
    """frame_psnr is a list (index = frame index); older runs used a dict."""
    if isinstance(fp, dict):
        return {int(k): v for k, v in fp.items()}
    return {i: v for i, v in enumerate(fp)}


lags = sorted({lag for v in rows.values() for fp in v for lag in _lag_values(fp)})
summary = {}
for h in sorted({k[0] for k in rows}):
    for lag in lags:
        c = [_lag_values(fp)[lag] for fp in rows.get((h, "control"), []) if lag in _lag_values(fp)]
        d = [_lag_values(fp)[lag] for fp in rows.get((h, "disturb"), []) if lag in _lag_values(fp)]
        if not c or not d:
            continue
        cm, dm = sum(c) / len(c), sum(d) / len(d)
        print(f"{h:>3} {lag:>4} {cm:>9.2f} {dm:>9.2f} {dm - cm:>+8.2f} "
              f"{len(c):>3}/{len(d):<3}")
        summary.setdefault(str(h), {})[str(lag)] = {
            "control": cm, "disturb": dm, "delta": dm - cm,
            "n_control": len(c), "n_disturb": len(d),
        }

out = root.rstrip("/") + "/psnr_clip_summary.json"
with open(out, "w") as fh:
    json.dump(summary, fh, indent=2)
print(f"\nwrote {out}")
print("\nInterpretation guide:")
print("  lag 0 : both arms observe the SAME frame at planning time -> delta must be ~0.")
print("          A non-zero delta here means the arms differ before the intervention.")
print("  lag>0 : the prediction was made before the displacement, so a negative delta")
print("          is the world-model error caused by the world changing mid-chunk.")
