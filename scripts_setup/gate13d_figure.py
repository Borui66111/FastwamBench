"""Gate 13D figure -- how carry-phase strikes fail.

Panel A: outcome composition per cell (placed / held above basket / lost far /
         still descending) for the 0.01 m carry run.
Panel B: success rate vs strike magnitude in the carry regime, with control,
         Wilson 95% intervals, horizons pooled.

Reads the JSON emitted by gate13d_mechanism.py.
"""

import argparse
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
    ("STILL-DESCENDING", "#F9A825", "still descending at budget"),
    ("NEVER-LIFTED", "#6A1B9A", "never lifted"),
]


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def load(path):
    with open(path) as f:
        return json.load(f)


def cell_counts(rows, task, H, arm):
    rs = [r for r in rows if r["task"] == task and r["H"] == H and r["arm"] == arm]
    return len(rs), {m: sum(1 for r in rs if r["mode"] == m) for m, _, _ in MODES}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--carry", default="results/gate13d_mechanism_carry.json")
    ap.add_argument("--sweep", default="results/gate13d_mechanism_sweep.json")
    ap.add_argument("--out", default="evidence/gate13d_mechanism")
    args = ap.parse_args()

    carry = load(args.carry)
    carry_rows = carry[list(carry)[0]]
    sweep = load(args.sweep)

    fig, (axA, axB) = plt.subplots(1, 2, figsize=(12.8, 5.2))

    # ---- Panel A: outcome composition, object task, 0.01 m ----
    labels = ["control\nH=1", "disturb\nH=1", "control\nH=10", "disturb\nH=10"]
    keys = [("control", 1), ("disturb", 1), ("control", 10), ("disturb", 10)]
    xs = np.arange(len(keys))
    bottom = np.zeros(len(keys))
    for mode, color, name in MODES:
        vals = np.array([cell_counts(carry_rows, "libero_object_t0", H, arm)[1][mode]
                         for arm, H in keys], dtype=float)
        if vals.sum() == 0:
            continue
        axA.bar(xs, vals, 0.62, bottom=bottom, color=color, label=name,
                edgecolor="white", linewidth=0.8)
        # label any segment tall enough to hold text
        for i, v in enumerate(vals):
            if v >= 1:
                axA.text(i, bottom[i] + v / 2, f"{int(v)}", ha="center", va="center",
                         fontsize=8.6, color="white", fontweight="bold")
        bottom += vals
    for i, (arm, H) in enumerate(keys):
        n, cnt = cell_counts(carry_rows, "libero_object_t0", H, arm)
        axA.text(i, n + 0.1, f"placed {cnt['PLACED']}/{n}", ha="center", va="bottom",
                 fontsize=9.4, fontweight="bold")
    axA.set_xticks(xs)
    axA.set_xticklabels(labels, fontsize=9.5)
    axA.set_ylabel("episodes")
    axA.set_ylim(0, 7.2)
    axA.set_title("A  libero_object, 0.01 m strikes during carry (n=6 per cell)",
                  fontsize=10.5)
    axA.legend(fontsize=8.4, loc="upper center", bbox_to_anchor=(0.5, -0.11),
               ncol=3, frameon=False)
    axA.grid(axis="y", alpha=0.25)
    axA.set_axisbelow(True)

    # ---- Panel B: success vs magnitude, horizons pooled ----
    mags, succ, ns, ctrl = [], [], [], []
    for mag, root in [("0.005", "gate13_carry_mag005"),
                      ("0.01", "gate13_repeat_carry_full"),
                      ("0.02", "gate13_carry_mag02")]:
        if root not in sweep:
            continue
        rows = sweep[root]
        d = [r for r in rows if r["task"] == "libero_object_t0" and r["arm"] == "disturb"]
        c = [r for r in rows if r["task"] == "libero_object_t0" and r["arm"] == "control"]
        if not d:
            continue
        mags.append(float(mag))
        succ.append((sum(r["success"] for r in d), len(d)))
        ns.append(len(d))
        ctrl.append((sum(r["success"] for r in c), len(c)) if c else (0, 0))

    if mags:
        xb = np.arange(len(mags))
        ck = [k for k, _ in ctrl]
        cn = [n for _, n in ctrl]
        cp, clo, chi = zip(*[wilson(k, n) for k, n in zip(ck, cn)])
        sk = [k for k, _ in succ]
        sn = [n for _, n in succ]
        sp, slo, shi = zip(*[wilson(k, n) for k, n in zip(sk, sn)])

        axB.bar(xb - 0.19, cp, 0.36, color="#90A4AE", label="control (no strike)")
        axB.errorbar(xb - 0.19, cp, yerr=[np.array(cp) - np.array(clo),
                                          np.array(chi) - np.array(cp)],
                     fmt="none", ecolor="#37474F", capsize=3.5, lw=1.2)
        axB.bar(xb + 0.19, sp, 0.36, color="#C62828", label="strikes during carry")
        axB.errorbar(xb + 0.19, sp, yerr=[np.array(sp) - np.array(slo),
                                          np.array(shi) - np.array(sp)],
                     fmt="none", ecolor="#5D1919", capsize=3.5, lw=1.2)
        for i in range(len(mags)):
            axB.text(i - 0.19, chi[i] + 0.03, f"{ck[i]}/{cn[i]}", ha="center",
                     fontsize=9, color="#37474F")
            axB.text(i + 0.19, shi[i] + 0.03, f"{sk[i]}/{sn[i]}", ha="center",
                     fontsize=9.2, fontweight="bold", color="#C62828")
        axB.set_xticks(xb)
        axB.set_xticklabels([f"{m*1000:.0f} mm" for m in mags], fontsize=10)
        axB.set_ylim(0, 1.22)
        axB.set_ylabel("success rate")
        axB.set_xlabel("displacement per strike")
        axB.set_title("B  success vs magnitude, carry regime\n"
                      "horizons pooled, n=12 per bar, Wilson 95%", fontsize=10.5)
        axB.legend(fontsize=8.8, loc="upper center", bbox_to_anchor=(0.5, -0.11),
                   ncol=2, frameon=False)
        axB.grid(axis="y", alpha=0.25)
        axB.set_axisbelow(True)

    fig.tight_layout()
    for ext in ("png", "pdf"):
        p = f"{args.out}.{ext}"
        fig.savefig(p, dpi=200, bbox_inches="tight")
        print("wrote", p, os.path.getsize(p), "bytes")


if __name__ == "__main__":
    main()
