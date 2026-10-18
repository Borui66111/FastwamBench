"""Gate 13D -- mechanism of carry-phase failure.

Question: when a strike lands during the carry, *how* does the episode fail?

Three candidates, all distinguishable from the object's own trajectory:
  A. the object is knocked away before the grasp   -> never lifted
  B. the robot carries it to the wrong place       -> lifted, ends far from basket
  C. the robot never releases it                   -> lifted, ends held above basket,
                                                      z flat at the 400-step budget
  D. it was still descending when time ran out     -> would have placed with more steps

This matters because only B and C are carry failures; D would make the whole
result a time-budget artifact, and A would make it an approach failure.

Usage:
  python scripts_setup/gate13d_mechanism.py [--json out.json] RUN_DIR [RUN_DIR ...]

Each RUN_DIR is a gate13 run directory containing <task>/H<n>/<arm>_s<seed>/records.jsonl
"""

import argparse
import glob
import json
import os
import sys

import numpy as np

# A failure counts as "still descending" only if the tail trend is meaningfully
# negative; 2e-4 m/step is ~1% of the object's diameter per step.
SLOPE_FLAT = 2e-4
HELD_ABOVE = 0.05      # metres above the resting height that count as "held"
FAR_FROM_BASKET = 0.05  # metres of xy offset that count as "not at the basket"


def episodes(path):
    """Group step records into episodes by the `episode` field."""
    eps, cur = [], None
    for line in open(path):
        r = json.loads(line)
        e = r.get("event")
        if e == "step":
            idx = r.get("episode", 0)
            if cur is None or cur["idx"] != idx:
                if cur is not None:
                    eps.append(cur)
                cur = {"idx": idx, "steps": [], "ivs": [], "end": None}
            cur["steps"].append(r)
        elif e == "intervention":
            if cur is not None and cur["idx"] == r.get("episode", 0):
                cur["ivs"].append(r)
        elif e == "episode_end":
            if cur is not None:
                cur["end"] = r
                eps.append(cur)
                cur = None
    if cur is not None and cur["steps"]:
        eps.append(cur)
    return eps


def pos(step, name):
    bd = (step.get("state") or {}).get("bodies") or {}
    v = bd.get(name)
    if v is None:
        return None
    p = v.get("pos") if isinstance(v, dict) else v
    return np.array(p, dtype=float) if p is not None and len(p) >= 3 else None


def classify(ep, body_hint=None):
    st = ep["steps"]
    ivs = ep["ivs"]
    body = ivs[0]["body"] if ivs else body_hint
    if not body or len(st) < 45:
        return None
    zs = [pos(s, body) for s in st]
    zs = [q for q in zs if q is not None]
    if len(zs) < 45:
        return None

    z0 = float(min(q[2] for q in zs[:10]))
    zmax = float(max(q[2] for q in zs))
    zend = float(zs[-1][2])
    lifted = zmax > z0 + 0.02
    lift_step = None
    if lifted:
        for k, q in enumerate(zs):
            if q[2] > z0 + 0.02:
                lift_step = k
                break

    y = np.array([q[2] for q in zs[-40:]])
    slope = float(np.polyfit(np.arange(len(y)), y, 1)[0])

    bk = [pos(s, "basket_1_main") for s in st]
    bk = [q for q in bk if q is not None]
    dbask = float(np.linalg.norm(zs[-1][:2] - bk[-1][:2])) if bk else float("nan")

    succ = bool((ep["end"] or {}).get("success"))

    if succ:
        mode = "PLACED"
    elif not lifted:
        mode = "NEVER-LIFTED"
    elif slope < -SLOPE_FLAT:
        mode = "STILL-DESCENDING"
    elif zend > z0 + HELD_ABOVE and dbask <= FAR_FROM_BASKET:
        mode = "HELD-ABOVE-BASKET"
    elif zend > z0 + HELD_ABOVE:
        mode = "HELD-ELSEWHERE"
    else:
        mode = "LOST-FAR"

    return {
        "episode": ep["idx"],
        "success": succ,
        "lifted": lifted,
        "lift_step": lift_step,
        "z0": round(z0, 4),
        "zmax": round(zmax, 4),
        "zend": round(zend, 4),
        "tail_slope": round(slope, 6),
        "d_basket_end": None if np.isnan(dbask) else round(dbask, 4),
        "n_strikes": len(ivs),
        "strike_steps": [iv["t"] for iv in ivs if iv.get("t") is not None],
        "steps": len(st),
        "mode": mode,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    out = {}
    for root in args.runs:
        # Control episodes carry no intervention record, so the manipulated body
        # has to come from somewhere else. Derive it PER TASK from that task's
        # disturb episodes (a global hint would apply libero_object's body to
        # libero_spatial and silently drop every spatial control episode).
        body_hints = {}
        for p in sorted(glob.glob(os.path.join(root, "*", "H*", "*", "records.jsonl"))):
            task = p.split(os.sep)[-4]
            if task in body_hints:
                continue
            for ep in episodes(p):
                if ep["ivs"] and ep["ivs"][0].get("body"):
                    body_hints[task] = ep["ivs"][0]["body"]
                    break

        rows = []
        for p in sorted(glob.glob(os.path.join(root, "*", "H*", "*", "records.jsonl"))):
            parts = p.split(os.sep)
            task, H, arm = parts[-4], parts[-3], parts[-2].rsplit("_s", 1)[0]
            for ep in episodes(p):
                rec = classify(ep, body_hints.get(task))
                if rec is None:
                    continue
                rec.update({"task": task, "H": int(H[1:]), "arm": arm,
                            "seed": parts[-2].rsplit("_s", 1)[-1]})
                rows.append(rec)
        out[os.path.basename(os.path.normpath(root))] = rows

        print("=" * 84)
        print(os.path.basename(os.path.normpath(root)))
        print(f"  {'task':<18} {'H':>3} {'arm':<8} {'n':>2} {'succ':>6}  modes")
        cells = {}
        for r in rows:
            cells.setdefault((r["task"], r["H"], r["arm"]), []).append(r)
        for (task, H, arm), rs in sorted(cells.items()):
            n = len(rs)
            s = sum(r["success"] for r in rs)
            modes = {}
            for r in rs:
                modes[r["mode"]] = modes.get(r["mode"], 0) + 1
            ms = " ".join(f"{k}={v}" for k, v in sorted(modes.items()))
            print(f"  {task:<18} {H:>3} {arm:<8} {n:>2} {s:>3}/{n:<3}  {ms}")
        # Strike-phase audit: did every strike land after the object was lifted?
        d = [r for r in rows if r["arm"] == "disturb" and r["n_strikes"]]
        post = [r for r in d if r["lift_step"] is not None
                and min(r["strike_steps"]) >= r["lift_step"]]
        print(f"  strike phase: {len(post)}/{len(d)} struck episodes had every "
              f"strike AFTER the lift")
        if len(post) < len(d):
            bad = [r for r in d if r not in post]
            print(f"  !! {len(bad)} struck episodes had a strike before the lift: "
                  + ", ".join(f"{r['task']} H{r['H']} ep{r['episode']} "
                              f"lift={r['lift_step']} strikes={r['strike_steps']}"
                              for r in bad[:4]))

    if args.json:
        with open(args.json, "w") as f:
            json.dump(out, f, indent=2)
        print(f"wrote {args.json}")


if __name__ == "__main__":
    main()
