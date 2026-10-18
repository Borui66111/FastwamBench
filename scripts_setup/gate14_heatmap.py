"""Success/recovery heatmap across every Gate 13/14 cell.

The remote-review target asks for a "success / recovery heatmap". This builds it
directly from the per-episode records, so no cell can be transcribed by hand:
rows are (task, regime, magnitude, pathway), columns are
(control H=1, disturb H=1, control H=10, disturb H=10), and every cell is
annotated k/n. A cell whose arm was never run stays blank and hatched.

Usage:
    python scripts_setup/gate14_heatmap.py            # writes evidence/gate14_matrix.png
"""
import argparse
import glob
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np

# (row label, results dir)
ROWS = [
    ("object | carry 5 mm | idm",        "results/gate13_carry_mag005"),
    ("object | carry 10 mm | idm",       "results/gate13_repeat_carry_full"),
    ("object | carry 20 mm | idm",       "results/gate13_carry_mag02"),
    ("object | approach 10 mm | idm",    "results/gate13_repeat_sub"),
    ("object | carry 10 mm | first_frame",    "results/gate13_g14ff"),
    ("object | carry 10 mm @800 | first_frame", "results/gate13_g14ff800"),
    ("object | carry 10 mm @800 | idm",        "results/gate13_g14idm800"),
    ("object | approach 10 mm | first_frame",  "results/gate13_g14ffapproach"),
    ("spatial | carry 10 mm | idm",      "results/gate13_repeat_carry_full"),
    ("spatial | approach 10 mm | idm",   "results/gate13_repeat_sub"),
]
TASKS = ["libero_object_t0", "libero_spatial_t0"]
COLS = [(1, "control"), (1, "disturb"), (10, "control"), (10, "disturb")]


def cell(root, task, h, arm):
    """(successes, n) for one cell, or None when the arm was never run."""
    paths = glob.glob(os.path.join(root, task, f"H{h}", f"{arm}_s*", "records.jsonl"))
    if not paths:
        return None
    k = n = 0
    for p in paths:
        with open(p) as f:
            for line in f:
                if '"episode_end"' in line:
                    n += 1
                    k += int(json.loads(line)["success"])
    return (k, n) if n else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="evidence/gate14_matrix.png")
    ap.add_argument("--json", default="results/gate14_matrix.json")
    args = ap.parse_args()

    grid, text = [], []
    for label, root in ROWS:
        task = TASKS[0] if label.startswith("object") else TASKS[1]
        vals, txt = [], []
        for h, arm in COLS:
            c = cell(root, task, h, arm)
            vals.append(np.nan if c is None else c[0] / c[1])
            txt.append("--" if c is None else f"{c[0]}/{c[1]}")
        grid.append(vals)
        text.append(txt)
    grid = np.array(grid, dtype=float)

    fig, ax = plt.subplots(figsize=(7.6, 5.4))
    cmap = plt.get_cmap("RdYlGn").copy()
    cmap.set_bad("#e8e8e8")
    im = ax.imshow(np.ma.masked_invalid(grid), cmap=cmap, vmin=0.0, vmax=1.0,
                   aspect="auto")
    for i in range(len(ROWS)):
        for j in range(len(COLS)):
            # Black text with a white halo: legible on every fill in the map,
            # instead of guessing a foreground colour per cell.
            ax.text(j, i, text[i][j], ha="center", va="center",
                    fontsize=9, color="black", zorder=3,
                    path_effects=[pe.withStroke(linewidth=2.6, foreground="white")])
    ax.set_xticks(range(len(COLS)))
    ax.set_xticklabels([f"{a}\nH={h}" for h, a in COLS], fontsize=9)
    ax.set_yticks(range(len(ROWS)))
    ax.set_yticklabels([r[0] for r in ROWS], fontsize=8)
    ax.set_title("Success rate by task, regime, magnitude and pathway\n"
                 "(cell = successes/episodes; grey = arm not run)", fontsize=10)
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02, label="success rate")
    fig.tight_layout()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    fig.savefig(args.out, dpi=180)
    fig.savefig(args.out.replace(".png", ".pdf"))
    print(f"wrote {args.out} ({os.path.getsize(args.out)} B)")

    os.makedirs(os.path.dirname(args.json), exist_ok=True)
    with open(args.json, "w") as f:
        json.dump({ROWS[i][0]: {f"{a}_H{h}": text[i][j]
                                for j, (h, a) in enumerate(COLS)}
                   for i in range(len(ROWS))}, f, indent=1)
    print(f"wrote {args.json}")
    for i, (label, _) in enumerate(ROWS):
        print(f"  {label:42s} " + "  ".join(text[i]))


if __name__ == "__main__":
    main()
