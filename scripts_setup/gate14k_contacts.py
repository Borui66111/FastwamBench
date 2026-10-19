"""Gate 14K: contact state in the last 40 steps of each episode.

Reads runs recorded after the contacts field was added and reports, per episode,
whether the object touched the basket, which finger it touched, and how deep.
"""
import glob
import json
import os
import sys

import numpy as np

WINDOW = 40


def episodes(path):
    """Group records by the episode id each record carries."""
    by, end = {}, {}
    for line in open(path):
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        e = r.get("episode")
        if e is None:
            continue
        if r.get("event") == "episode_end":
            end[e] = r
        elif r.get("event") == "step":
            by.setdefault(e, []).append(r)
    return by, end


def summarise(steps, end):
    if end is None or not steps:
        return None
    tail = steps[-WINDOW:]
    left = right = basket = 0
    pens = []
    for s in tail:
        for c in s.get("state", {}).get("contacts", []) or []:
            pair = f"{c.get('a')}|{c.get('b')}"
            if "leftfinger" in pair:
                left += 1
            if "rightfinger" in pair:
                right += 1
            if "basket" in pair:
                basket += 1
            if isinstance(c.get("dist"), (int, float)):
                pens.append(c["dist"])
    obj = tail[-1].get("state", {}).get("bodies", {}) or {}
    eef = tail[-1].get("state", {}).get("eef", {})
    grip = tail[-1].get("state", {}).get("gripper", {}) or {}
    # The bodies dict is unordered and may start with the floor; key on the
    # manipulated object explicitly or the height column silently reads 0.000.
    okey = next((k for k in obj if "alphabet" in k.lower()), None)
    if okey is None:
        okey = next((k for k in obj if k.lower() not in ("floor", "table")), None)
    ob = obj[okey]["pos"] if okey else [np.nan] * 3
    ep = eef.get("pos", [np.nan] * 3) if eef else [np.nan] * 3
    return {
        "success": bool(end.get("success")),
        "steps": end.get("steps"),
        "z_obj": round(float(ob[2]), 4),
        "width": round(float(grip.get("width", np.nan)), 4),
        "left": left,
        "right": right,
        "basket": basket,
        "min_pen": round(float(min(pens)), 5) if pens else None,
        "dz": round(float(ob[2] - ep[2]), 4),
    }


def main(runs, save=True):
    """save=False when called as a library, so the JSON keeps every run, not just the last."""
    rows = []
    for run in runs:
        for p in sorted(glob.glob(os.path.join(run, "**", "records.jsonl"), recursive=True)):
            by, end = episodes(p)
            for e, steps in by.items():
                r = summarise(steps, end.get(e))
                if r is None:
                    continue
                r["ep"] = f"{os.path.basename(os.path.dirname(p))}:e{e}"
                rows.append(r)
    hdr = f"{'ep':22s} {'succ':5s} {'z_obj':>6s} {'width':>6s} {'L':>4s} {'R':>3s} {'bkt':>4s} {'pen':>8s} {'dz':>7s}"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(f"{r['ep']:22s} {str(r['success']):5s} {r['z_obj']:6.3f} {r['width']:6.3f} "
              f"{r['left']:4d} {r['right']:3d} {r['basket']:4d} "
              f"{str(r['min_pen']):>8s} {r['dz']:7.3f}")
    ok = [r for r in rows if r["success"]]
    no = [r for r in rows if not r["success"]]
    print(f"\n{len(ok)} success / {len(no)} failure")
    for name, grp in (("success", ok), ("failure", no)):
        if not grp:
            continue
        print(f"  {name}: basket contacts {sum(r['basket'] for r in grp)}, "
              f"R-finger {sum(r['right'] for r in grp)}, "
              f"L-finger {sum(r['left'] for r in grp)}")
    if save:
        with open("results/gate14k_contacts.json", "w") as fh:
            json.dump(rows, fh, indent=1)
    return rows


if __name__ == "__main__":
    main(sys.argv[1:] or ["results/gate13_g14k9"])
