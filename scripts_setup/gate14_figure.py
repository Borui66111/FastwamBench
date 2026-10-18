"""Gate 14 figure -- is the carry-phase cost specific to future-aware inference?

Panel A: success per cell for the two action-inference pathways (idm vs
         first_frame), control vs disturb, at both replan horizons, with Wilson
         95% intervals and the raw count printed on every bar.
Panel B: what the failures look like in each pathway (stacked outcome
         composition), so "same cost" is shown to mean "same behaviour".

Reads results/gate13_repeat_carry_full (idm) and results/gate13_g14ff
(first_frame) directly from the episode records -- no hand-entered numbers.
"""

import argparse
import glob
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

MODES = [
    ("PLACED", "#2E7D32", "placed"),
    ("HELD-ABOVE-BASKET", "#C62828", "held above basket"),
    ("LOST-FAR", "#EF6C00", "lost far from basket"),
    ("HELD-ELSEWHERE", "#8D6E63", "held elsewhere"),
    ("STILL-DESCENDING", "#F9A825", "still descending at budget"),
    ("NEVER-LIFTED", "#6A1B9A", "never lifted"),
]
PATHWAYS = [("idm", "future-aware (idm)", "#1565C0"),
            ("ff", "non-future (first_frame)", "#757575")]


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def episodes(root, task="libero_object_t0"):
    """{H: {arm: [episode_end records]}} straight from records.jsonl.

    Layout is <root>/<task>_t<id>/H<n>/<arm>_s<seed>/records.jsonl, so the task
    and horizon both live in the path -- do not assume root's children are H dirs.
    """
    out = {}
    if not os.path.isdir(root):
        return out
    for h_dir in sorted(glob.glob(os.path.join(root, "*", "H*"))):
        # Only the requested task: the idm run also contains libero_spatial_t0,
        # which has no Gate 14 arm and must not be pooled in.
        if task and task not in os.path.basename(os.path.dirname(h_dir)):
            continue
        h = int(os.path.basename(h_dir)[1:])
        for cell in sorted(os.listdir(h_dir)):
            arm = "control" if cell.startswith("control") else "disturb"
            path = os.path.join(h_dir, cell, "records.jsonl")
            if not os.path.exists(path):
                continue
            eps = []
            with open(path) as f:
                for line in f:
                    if '"episode_end"' in line:
                        eps.append(json.loads(line))
            out.setdefault(h, {}).setdefault(arm, []).extend(eps)
    return out


def mech_counts(mech, run, task, H, arm):
    """Outcome-mode counts for one run/task/horizon/arm.

    gate13d_mechanism.py --json emits {run_name: [per-episode dicts]}, so the
    counts are derived here rather than read from a pre-tallied block.
    """
    counts = {}
    for r in mech.get(run, []):
        if r.get("task") != task or int(r.get("H", -1)) != H or r.get("arm") != arm:
            continue
        counts[r.get("mode") or "UNKNOWN"] = counts.get(r.get("mode") or "UNKNOWN", 0) + 1
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--idm", default="results/gate13_repeat_carry_full")
    ap.add_argument("--ff", default="results/gate13_g14ff")
    ap.add_argument("--mech", default="results/gate14_mechanism.json",
                    help="JSON from gate13d_mechanism.py over BOTH runs")
    ap.add_argument("--out", default="evidence/gate14_wam_specificity.png")
    args = ap.parse_args()

    data = {"idm": episodes(args.idm), "ff": episodes(args.ff)}
    mech = {}
    if os.path.exists(args.mech):
        with open(args.mech) as f:
            mech = json.load(f)

    fig, axes = plt.subplots(1, 2, figsize=(13.2, 5.2))
    ax = axes[0]
    horizons = sorted({h for d in data.values() for h in d})
    width = 0.19
    xs = np.arange(len(horizons))
    for i, (key, label, color) in enumerate(PATHWAYS):
        for j, (arm, hatch) in enumerate([("control", ""), ("disturb", "//")]):
            ks, ns, pos = [], [], []
            for k, h in enumerate(horizons):
                eps = data[key].get(h, {}).get(arm, [])
                n = len(eps)
                succ = sum(int(e["success"]) for e in eps)
                ks.append(succ)
                ns.append(n)
                pos.append(xs[k] + (i * 2 + j - 1.5) * width)
            rates, lo, hi = zip(*[wilson(k, n) for k, n in zip(ks, ns)]) if ns else ([], [], [])
            ax.bar(pos, rates, width, color=color, hatch=hatch, edgecolor="white",
                   alpha=1.0 if arm == "control" else 0.55,
                   label=f"{label}, {arm}")
            ax.errorbar(pos, rates,
                        yerr=[np.maximum(0.0, np.array(rates) - np.array(lo)),
                              np.maximum(0.0, np.array(hi) - np.array(rates))],
                        fmt="none", ecolor="black", lw=1.0, capsize=2)
            for x, k, n, r in zip(pos, ks, ns, rates):
                ax.text(x, min(1.02, r + 0.045), f"{k}/{n}", ha="center",
                        va="bottom", fontsize=8)

    ax.set_xticks(xs)
    ax.set_xticklabels([f"replan horizon H={h}" for h in horizons])
    ax.set_ylim(0, 1.12)
    ax.set_ylabel("task success rate (Wilson 95% CI)")
    # Title states the disturb counts it is actually showing, computed here so
    # it can never go stale relative to the data.
    _t = []
    for h in horizons:
        row = []
        for key in ("idm", "ff"):
            eps = data[key].get(h, {}).get("disturb", [])
            row.append(f"{sum(int(e['success']) for e in eps)}/{len(eps)}")
        _t.append(f"H={h}: " + " vs ".join(row))
    ax.set_title("Disturb-arm success, future-aware vs non-future\n"
                 + " | ".join(_t), fontsize=11)
    ax.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.13),
              ncol=2, framealpha=1.0)
    ax.grid(axis="y", alpha=0.25)

    ax = axes[1]
    labels, bottoms = [], []
    bars = {m: [] for m, _, _ in MODES}
    idm_run = os.path.basename(args.idm.rstrip("/"))
    ff_run = os.path.basename(args.ff.rstrip("/"))
    for (key, label, _), run in zip(PATHWAYS, (idm_run, ff_run)):
        for h in horizons:
            counts = mech_counts(mech, run, "libero_object_t0", h, "disturb")
            n = sum(counts.values())
            labels.append(f"{label.split('(')[1].rstrip(')')}\nH={h}")
            bottoms.append(n)
            for m, _, _ in MODES:
                bars[m].append(counts.get(m, 0))

    x = np.arange(len(labels))
    bottom = np.zeros(len(labels))
    for m, color, lab in MODES:
        vals = np.array(bars[m], dtype=float)
        if vals.sum() == 0:
            continue
        ax.bar(x, vals, 0.6, bottom=bottom, color=color, label=lab,
               edgecolor="white")
        for xi, (v, b) in enumerate(zip(vals, bottom)):
            if v:
                ax.text(xi, b + v / 2, int(v), ha="center", va="center",
                        fontsize=8, color="white")
        bottom += vals
    for xi, n in zip(x, bottoms):
        ax.text(xi, n + 0.08, f"n={int(n)}", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("disturbed episodes (count)")
    ax.set_title("Failure-mode mix in the disturb arm\n"
                 "(one segment per episode)", fontsize=11)
    ax.legend(fontsize=8, loc="center left", bbox_to_anchor=(1.02, 0.5),
              framealpha=1.0)
    ax.set_ylim(0, max(bottoms + [1]) * 1.18)
    ax.grid(axis="y", alpha=0.25)

    fig.tight_layout()
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    fig.savefig(args.out, dpi=170)
    fig.savefig(args.out.replace(".png", ".pdf"))
    print(f"wrote {args.out} ({os.path.getsize(args.out)} B)")
    print(f"wrote {args.out.replace('.png', '.pdf')}")


if __name__ == "__main__":
    main()
