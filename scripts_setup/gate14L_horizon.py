"""Gate 14L: does the future-aware pathway's advantage scale with commitment horizon?

Reads the horizon sweep (results/gate13_g14L_<mode>_H<h>) and reports, per cell,
the success count for both arms, then tests the interaction that the thesis
predicts: the idm-vs-first_frame gap on the disturb arm should be ~0 at H=1 (no
future frames to condition on) and grow with H.

Prints counts, Wilson intervals and Fisher p-values. No number is typed; every
value comes from records.jsonl.

    python scripts_setup/gate14L_horizon.py 1 2 5 10
"""
import glob
import json
import os
import sys

from scipy.stats import fisher_exact


def wilson(k, n):
    if n == 0:
        return (float("nan"), float("nan"))
    z = 1.96
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (c - h, c + h)


MODE_TAG = {"idm": "idm", "first_frame": "ff"}


def tag_for(prefix, mode):
    """Runs are tagged '<prefix>_idm' / '<prefix>_ff'; never glob the bare prefix, or
    the two pathways pool together."""
    return f"{prefix}_{MODE_TAG.get(mode, mode)}"


def cell(tag_prefix, arm, H):
    """Success count and episodes for one (run prefix, arm, horizon).

    The horizon is read from the path's /H<n>/ segment, so one prefix can cover
    several horizons (the canary puts H1 and H10 under a single tag)."""
    k = n = 0
    for p in glob.glob(f"results/gate13_{tag_prefix}*/**/records.jsonl", recursive=True):
        if f"/H{H}/" not in p or f"/{arm}_s" not in p:
            continue
        for line in open(p):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("event") == "episode_end":
                n += 1
                k += 1 if r.get("success") else 0
    return k, n


def main(horizons, modes=("idm", "first_frame"), prefix="g14L"):
    print(f"{'H':>3} {'mode':<12} {'arm':<9} {'succ':>7} {'95% CI':>15}")
    table = {}
    for H in horizons:
        for m in modes:
            for arm in ("control", "disturb"):
                k, n = cell(tag_for(prefix, m), arm, H)
                lo, hi = wilson(k, n)
                table[(H, m, arm)] = (k, n)
                print(f"{H:>3} {m:<12} {arm:<9} {k:>3}/{n:<3} [{lo:.2f},{hi:.2f}]")
    print()
    print("Gap (disturb): idm - first_frame, with Fisher p on the 2x2.")
    print("The thesis predicts this gap is ~0 at H=1 and grows with H.")
    for H in horizons:
        a = table.get((H, "idm", "disturb"), (0, 0))
        b = table.get((H, "first_frame", "disturb"), (0, 0))
        if a[1] == 0 or b[1] == 0:
            print(f"  H={H}: incomplete")
            continue
        p = fisher_exact([[a[0], a[1] - a[0]], [b[0], b[1] - b[0]]]).pvalue
        gap = a[0] / a[1] - b[0] / b[1]
        lo_a, hi_a = wilson(*a)
        lo_b, hi_b = wilson(*b)
        print(f"  H={H:>2}: idm {a[0]}/{a[1]} ({a[0]/a[1]:.2f}) vs ff {b[0]}/{b[1]} "
              f"({b[0]/b[1]:.2f})  gap {gap:+.2f}  p={p:.4f}  "
              f"CIs [{lo_a:.2f},{hi_a:.2f}] vs [{lo_b:.2f},{hi_b:.2f}]")
    print()
    print("Control comparability (should be high and similar for both pathways):")
    for H in horizons:
        for m in modes:
            k, n = table.get((H, m, "control"), (0, 0))
            if n:
                print(f"  H={H:>2} {m:<12} control {k}/{n}")


if __name__ == "__main__":
    args = sys.argv[1:]
    prefix = "g14L"
    if args and args[0].startswith("--prefix="):
        prefix = args[0].split("=", 1)[1]
        args = args[1:]
    hs = [int(x) for x in args] or [1, 2, 5, 10]
    main(hs, prefix=prefix)
