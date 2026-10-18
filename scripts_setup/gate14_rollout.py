"""Curated qualitative rollout: one control success vs one disturbed failure.

The remote-review target asks for "one qualitative control-vs-disturbance
rollout". Every episode already writes an mp4, but 48 of them is not a figure.
This picks one paired episode from the same task/seed/horizon, samples the same
normalised progress points from each video, and lays them out side by side so the
failure mode (carried to the basket and never released) is visible.

Usage:
    python scripts_setup/gate14_rollout.py
"""
import argparse
import glob
import json
import os

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

FRACS = [0.0, 0.25, 0.5, 0.75, 0.97]


def pick(root, trial, want_success):
    """Locate the mp4 for one trial of one cell, asserting the outcome matches."""
    vids = glob.glob(os.path.join(root, "**", "videos", f"*episode=task0_trial{trial}--*.mp4"),
                     recursive=True)
    for v in vids:
        if f"success={want_success}" in os.path.basename(v):
            return v
    raise SystemExit(f"no trial{trial} with success={want_success} under {root}")


def episode_record(root, trial):
    """(success, steps) for that trial, from records.jsonl.

    Keyed on the record's own `episode` field, not on file position: the
    episode_end lines are not guaranteed to be in trial order, and getting this
    wrong pairs a control video with the wrong outcome.
    """
    with open(os.path.join(root, "records.jsonl")) as f:
        eps = [json.loads(l) for l in f if '"episode_end"' in l]
    for rec in eps:
        if rec.get("episode") == trial:
            return rec["success"], rec["steps"]
    raise SystemExit(f"{root}: no episode_end for episode={trial}")


def frames(path):
    cap = cv2.VideoCapture(path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    out = []
    for fr in FRACS:
        cap.set(cv2.CAP_PROP_POS_FRAMES, min(total - 1, int(fr * total)))
        ok, img = cap.read()
        if ok:
            out.append(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    cap.release()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="results/gate13_repeat_carry_full/libero_object_t0/H1")
    ap.add_argument("--trial", type=int, default=0)
    ap.add_argument("--out", default="evidence/gate14_rollout.png")
    args = ap.parse_args()

    rows = []
    for arm, want in (("control_s1", True), ("disturb_s1", False)):
        root = os.path.join(args.root, arm)
        ok, steps = episode_record(root, args.trial)
        assert bool(ok) is want, f"{arm}: expected success={want}, records say {ok}"
        rows.append((arm, ok, steps, frames(pick(root, args.trial, want))))

    fig, axes = plt.subplots(2, len(FRACS), figsize=(13.2, 4.6))
    for r, (arm, ok, steps, imgs) in enumerate(rows):
        for c, img in enumerate(imgs):
            ax = axes[r][c]
            ax.imshow(img)
            ax.set_xticks([])
            ax.set_yticks([])
            if c == 0:
                ax.set_ylabel(f"{arm}\n{'success' if ok else 'FAIL'} "
                              f"({steps} steps)", fontsize=9)
            ax.set_title(f"{int(FRACS[c] * 100)}% of episode", fontsize=8)
    fig.suptitle(f"object:0, H=1, seed 1, trial {args.trial} — identical start, "
                 "grasp-relative strike in the carry phase (bottom row)", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    fig.savefig(args.out, dpi=170)
    print(f"wrote {args.out} ({os.path.getsize(args.out)} B)")
    for arm, ok, steps, _ in rows:
        print(f"  {arm}: success={ok} steps={steps}")


if __name__ == "__main__":
    main()
