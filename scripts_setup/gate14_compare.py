#!/usr/bin/env python
"""Gate 14: future-aware (idm) vs non-future (first_frame) inference.

Same checkpoint, task, seed, replan horizon and intervention -- only the action
inference pathway differs.  Everything is recomputed from the per-episode
records (never from a cached summary), so a summary that drifted from the
records cannot contaminate the comparison.

    python scripts_setup/gate14_compare.py \
        --idm results/gate13_repeat_carry_full --ff results/gate13_g14ff
"""
import argparse
import glob
import json
import os
from collections import defaultdict

from scipy.stats import fisher_exact


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return ((c - h) / d, (c + h) / d)


def read_cell(cell_dir):
    """(successes, n, mean_steps_success, timeouts) for one arm/H/seed cell."""
    rec = os.path.join(cell_dir, "records.jsonl")
    if not os.path.exists(rec):
        return None
    s = n = to = 0
    steps_ok = []
    with open(rec) as fh:
        for line in fh:
            if '"episode_end"' not in line:
                continue
            r = json.loads(line)
            n += 1
            if r.get("success"):
                s += 1
                steps_ok.append(int(r.get("steps", 0)))
            elif int(r.get("steps", 0)) >= 400:
                to += 1
    return {
        "succ": s, "n": n, "timeouts": to,
        "mean_steps_success": (sum(steps_ok) / len(steps_ok)) if steps_ok else None,
    }


def collect(root):
    """{(task, H, arm): aggregated cell stats} over all seeds."""
    out = defaultdict(lambda: {"succ": 0, "n": 0, "timeouts": 0, "_st": []})
    for cell in sorted(glob.glob(os.path.join(root, "*", "H*", "*_s*"))):
        task = os.path.basename(os.path.dirname(os.path.dirname(cell)))
        h = int(os.path.basename(os.path.dirname(cell))[1:])
        arm = os.path.basename(cell).rsplit("_s", 1)[0]
        st = read_cell(cell)
        if st is None:
            continue
        a = out[(task, h, arm)]
        a["succ"] += st["succ"]
        a["n"] += st["n"]
        a["timeouts"] += st["timeouts"]
        if st["mean_steps_success"] is not None:
            a["_st"].append((st["mean_steps_success"], st["succ"]))
    for a in out.values():
        a["mean_steps_success"] = (
            sum(m * k for m, k in a["_st"]) / sum(k for _, k in a["_st"])
            if a["_st"] else None)
        a.pop("_st")
    return out


def cmp(a, b):
    """Fisher on a vs b -> (p, delta)."""
    if not a or not b or a["n"] == 0 or b["n"] == 0:
        return (float("nan"), float("nan"))
    p = fisher_exact([[a["succ"], a["n"] - a["succ"]],
                      [b["succ"], b["n"] - b["succ"]]])[1]
    return (p, b["succ"] / b["n"] - a["succ"] / a["n"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--idm", default="results/gate13_repeat_carry_full")
    ap.add_argument("--ff", default="results/gate13_g14ff")
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    A, B = collect(args.idm), collect(args.ff)
    keys = sorted({k for k in list(A) + list(B)}, key=lambda t: (t[0], t[1], t[2]))

    print("=" * 108)
    print("GATE 14 -- future-aware (idm) vs non-future (first_frame) inference")
    print(f"  idm: {args.idm}")
    print(f"  ff : {args.ff}")
    print("=" * 108)
    print(f"{'task':<20}{'H':>3} {'arm':<9}"
          f"{'idm':>10} {'ff':>10} {'p(idm vs ff)':>14}"
          f"{'steps ok idm':>14}{'ff':>8}{'TO idm':>8}{'ff':>5}")
    rows = []
    for (task, h, arm) in keys:
        a, b = A.get((task, h, arm)), B.get((task, h, arm))
        p, d = cmp(a, b)
        fa = f"{a['succ']}/{a['n']}" if a else "-"
        fb = f"{b['succ']}/{b['n']}" if b else "-"
        sa = f"{a['mean_steps_success']:.0f}" if a and a.get("mean_steps_success") else "-"
        sb = f"{b['mean_steps_success']:.0f}" if b and b.get("mean_steps_success") else "-"
        ta = a["timeouts"] if a else "-"
        tb = b["timeouts"] if b else "-"
        ps = f"p={p:.4f}" if p == p else "n/a"
        print(f"{task:<20}{h:>3} {arm:<9}{fa:>10} {fb:>10} {ps:>14}"
              f"{sa:>14}{sb:>8}{str(ta):>8}{str(tb):>5}")
        rows.append({"task": task, "H": h, "arm": arm,
                     "idm": a, "ff": b, "p_idm_vs_ff": None if p != p else p})

    # pooled over horizon (legitimate only because the horizon contrast is null)
    print("\npooled over H (all tasks, all H):")
    pooled = {}
    for arm in ("control", "disturb"):
        a = {"succ": 0, "n": 0}
        b = {"succ": 0, "n": 0}
        for (task, h, ar) in keys:
            if ar != arm:
                continue
            for src, dst in ((A.get((task, h, ar)), a), (B.get((task, h, ar)), b)):
                if src:
                    dst["succ"] += src["succ"]
                    dst["n"] += src["n"]
        p, _ = cmp(a, b)
        lo, hi = wilson(b["succ"], b["n"]) if b["n"] else (0, 0)
        print(f"  {arm:<8} idm {a['succ']}/{a['n']}   ff {b['succ']}/{b['n']}"
              f"   ff 95%CI [{lo:.2f},{hi:.2f}]   p(idm vs ff)="
              f"{('%.4f' % p) if p == p else 'n/a'}")
        pooled[arm] = {"idm": a, "ff": b, "p": None if p != p else p}

    if args.json:
        with open(args.json, "w") as fh:
            json.dump({"idm_root": args.idm, "ff_root": args.ff,
                       "cells": rows, "pooled": pooled}, fh, indent=1,
                      default=lambda o: None)
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
