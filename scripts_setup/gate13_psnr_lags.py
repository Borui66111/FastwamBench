#!/usr/bin/env python
"""[fastbench] Matched-lag PSNR for the Gate 13 world-modelling arm.

episode_mean_psnr averages over a frame set whose size depends on replan_steps
(n_frames = replan_steps // action_video_freq_ratio + 1), so comparing its mean
across horizons is invalid. This script compares the SAME lag instead.

Frame index k in a predicted clip == lag k * action_video_freq_ratio steps ahead.

Usage: gate13_psnr_lags.py results/gate13_psnr_pow [--ratio 4] [--out FILE]
"""
import argparse
import collections
import glob
import json
import math
import os


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - r) / d, (c + r) / d)


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def sem(xs):
    if len(xs) < 2:
        return float("nan")
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1) / len(xs))


def collect(root, mode="clip"):
    """rows[H][arm][frame_index] = [psnr per episode].

    mode="clip"   : use ONLY the clip that the intervention lands in (start_step ==
                    intervention_step). This is the clean comparison: frame 0 of that
                    clip is the pre-displacement observation, identical in both arms,
                    and later frames show the damage. Requires episode_clip_psnr.
    mode="episode": fall back to episode-level frame means. NOTE this mixes clips
                    from before and after the arms diverge, so frame 0 is NOT a null.
    """
    rows = collections.defaultdict(
        lambda: collections.defaultdict(lambda: collections.defaultdict(list)))
    used = {"clip": 0, "episode": 0}
    for p in sorted(glob.glob(os.path.join(root, "*", "H*", "*", "records.jsonl"))):
        try:
            h = int(p.split("/H")[1].split("/")[0])
        except (IndexError, ValueError):
            continue
        arm = p.split("/")[-2].split("_")[0]
        for line in open(p):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("event") != "episode_end":
                continue
            clips = r.get("episode_clip_psnr") or []
            iv = r.get("intervention_step", -1)
            picked = None
            if mode == "clip" and clips:
                if arm == "control":
                    # no intervention: use the clip planned at the same step
                    for c in clips:
                        if c.get("start_step") == iv or c.get("replan_idx") == 1:
                            picked = c
                            break
                    if picked is None and len(clips) > 1:
                        picked = clips[1]
                else:
                    for c in clips:
                        if c.get("start_step") == iv:
                            picked = c
                            break
            if picked is not None:
                used["clip"] += 1
                for k, v in enumerate(picked.get("frame_psnr") or []):
                    rows[h][arm][k].append(float(v))
            else:
                used["episode"] += 1
                for k, v in (r.get("episode_frame_psnr") or {}).items():
                    rows[h][arm][int(k)].append(float(v))
    return rows, used


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--ratio", type=int, default=4,
                    help="action_video_freq_ratio (frames per scored step)")
    ap.add_argument("--mode", default="clip", choices=["clip", "episode"])
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    rows, used = collect(args.root, args.mode)
    if not rows:
        raise SystemExit(f"no records under {args.root}")

    lines = []
    add = lines.append
    add(f"# Matched-lag PSNR — {args.root}\n")
    add("`lag` = steps ahead of the planning step; frame index k scores lag "
        f"k*{args.ratio}. Only lags present for BOTH arms of a horizon are comparable.\n")

    lags = sorted({k * args.ratio for a in rows.values() for k in a.get("control", {})}
                  | {k * args.ratio for a in rows.values() for k in a.get("disturb", {})})

    add("## Per-horizon table (PSNR dB, mean ± SEM)\n")
    add("| H | arm | n | " + " | ".join(f"lag {L}" for L in lags) + " |")
    add("|---|---|---|" + "---|" * len(lags))
    for h in sorted(rows):
        for arm in ("control", "disturb"):
            d = rows[h].get(arm) or {}
            n = len(d.get(0, []))
            cells = []
            for L in lags:
                k = L // args.ratio
                vals = d.get(k) or []
                cells.append(f"{mean(vals):.2f} ± {sem(vals):.2f}" if vals else "—")
            add(f"| {h} | {arm} | {n} | " + " | ".join(cells) + " |")
    add("")

    add("## Disturbance cost at each matched lag (control − disturb)\n")
    add("| lag | " + " | ".join(f"H={h}" for h in sorted(rows)) + " |")
    add("|---|" + "---|" * len(rows))
    for L in lags:
        k = L // args.ratio
        cells = []
        for h in sorted(rows):
            c = rows[h].get("control", {}).get(k) or []
            d = rows[h].get("disturb", {}).get(k) or []
            if c and d:
                cells.append(f"{mean(c) - mean(d):+.2f} dB (n={len(c)}/{len(d)})")
            else:
                cells.append("—")
        add(f"| {L} | " + " | ".join(cells) + " |")
    add("")

    add("## Reading\n")
    add("- **lag 0 must show no cost.** The displacement happens after the plan is made, so "
        "the first predicted frame cannot know about it. A non-zero lag-0 cost means the "
        "comparison is contaminated.")
    add("- **Only equal-lag cells are comparable across H.** A horizon that scores more "
        "frames (because its chunk is longer) will look worse on any mean that includes "
        "far-future frames; that is an artifact, not a finding.")
    add("- Frames beyond a horizon's chunk do not exist: `n_frames = replan_steps // "
        f"{args.ratio} + 1`, so short horizons cannot score large lags at all.")

    text = "\n".join(lines) + "\n"
    print(text)
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(text)
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
