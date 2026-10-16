#!/usr/bin/env python
"""[fastbench] Gate 13 analyzer: commitment cost vs replan horizon.

Reads the per-run records.jsonl produced by gate13_run.py and reports, per
horizon H:
  * control vs disturbed success (the commitment cost = control - disturbed)
  * mean stale_action_steps  (mechanism check: should be ~0 for control, ~H for disturb)
  * the absolute step at which the disturbance actually fired (should be 60)
  * net object displacement  (confirms the world really changed)
  * re-acquisition latency   (steps after the disturbance until the end-effector
                              closes back to within the pre-disturbance distance
                              of the manipulated object; -1 = never recovered)

Usage:  python scripts_setup/gate13_analyze.py [results/gate13[_tag]]
"""
from __future__ import annotations

import glob
import json
import math
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path("/data1/liborui/fastwam_bench")
_argv = [a for a in sys.argv[1:] if not a.startswith("--")]
if len(_argv) > 1 and _argv[0] in ("--dir", "--root"):
    _argv = _argv[1:]
OUT_ROOT = Path(_argv[0]) if _argv else ROOT / "results" / "gate13"


def dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def load(rec_path: Path):
    with open(rec_path) as fh:
        return [json.loads(line) for line in fh if line.strip()]


def episode_metrics(recs, body):
    """Per-episode metrics for one run."""
    ends = [r for r in recs if r.get("event") == "episode_end"]
    steps = [r for r in recs if r.get("event") == "step"]
    ivs = [r for r in recs if r.get("event") == "intervention"]
    by_ep = defaultdict(list)
    for r in steps:
        by_ep[r["episode"]].append(r)
    iv_by_ep = defaultdict(list)
    for r in ivs:
        iv_by_ep[r["episode"]].append(r)
    out = []
    for e in ends:
        ep = e["episode"]
        es = sorted(by_ep.get(ep, []), key=lambda r: r["t"])
        iv_step = e.get("intervention_step", -1)
        ivrec = iv_by_ep.get(ep, [{}])[-1]
        # a run is CONTAMINATED if the disturbance itself satisfied the task
        # (episode ends at the intervention step) or if no stale action ever
        # executed, i.e. the manipulation under test never actually ran.
        stale_n = e.get("stale_action_steps", 0)
        post_iv = ivrec.get("post_iv_success")
        contaminated = bool(post_iv) or (iv_step >= 0 and stale_n <= 0)
        # distance series
        pre_dist = None
        lat = -1
        min_after = None
        net = None
        if body:
            first = last = None
            for r in es:
                st = r.get("state") or {}
                obj = (st.get("bodies") or {}).get(body, {}).get("pos")
                eef = (st.get("eef") or {}).get("pos")
                if obj is None or eef is None:
                    continue
                d = dist(obj, eef)
                if first is None:
                    first = obj
                last = obj
                if iv_step >= 0 and r["t"] <= iv_step:
                    pre_dist = d
                elif iv_step >= 0 and r["t"] > iv_step:
                    if min_after is None or d < min_after:
                        min_after = d
                    if lat < 0 and pre_dist is not None and d <= pre_dist:
                        lat = r["t"] - iv_step
            if first is not None and last is not None:
                net = dist(first, last)
        out.append({
            "episode": ep,
            "success": bool(e.get("success")),
            "steps": e.get("steps"),
            "stale_action_steps": stale_n,
            "contaminated": contaminated,
            "post_iv_success": post_iv,
            "delta_used": ivrec.get("delta_used"),
            "intervention_step": iv_step,
            "psnr": e.get("episode_mean_psnr"),
            "reacq_latency": lat,
            "obj_net_motion": net,
            "pre_iv_dist": pre_dist,
            "min_post_iv_dist": min_after,
        })
    return out


def main() -> int:
    runs = sorted(glob.glob(str(OUT_ROOT / "*" / "H*" / "*" / "records.jsonl")))
    if not runs:
        print(f"no runs under {OUT_ROOT}")
        return 1

    # (suite, tid) -> H -> arm -> list of per-episode dicts
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    meta = {}
    pat = re.compile(r"(?P<suite>.+)_t(?P<tid>\d+)/H(?P<h>\d+)/(?P<arm>[a-z]+)_s(?P<seed>\d+)")
    for rp in runs:
        rel = str(Path(rp).relative_to(OUT_ROOT))
        m = pat.search(rel)
        if not m:
            continue
        suite, tid, h, arm, seed = (m["suite"], int(m["tid"]), int(m["h"]),
                                    m["arm"], int(m["seed"]))
        recs = load(Path(rp))
        body = None
        # prefer the body the intervention actually resolved/displaced
        for e in recs:
            if e.get("event") == "intervention" and e.get("body") and e.get("applied"):
                body = e["body"]
                break
        if body is None:
            for e in recs:
                if e.get("event") == "episode_end" and e.get("world_body"):
                    body = e["world_body"]
                    break
        eps = episode_metrics(recs, body)
        data[(suite, tid)][h][arm].extend(eps)
        m = meta.setdefault((suite, tid), {"body": None})
        if body and not m.get("body"):
            m["body"] = body
        # sanity: intervention actually fired where configured
        fired = [e["intervention_step"] for e in eps if e["intervention_step"] >= 0]
        if arm == "disturb":
            meta[(suite, tid)].setdefault("fired_steps", set()).update(fired)

    summary = {}
    print("=" * 100)
    print("GATE 13 - cost of world-model commitment vs replan horizon")
    print("=" * 100)
    for (suite, tid), per_h in sorted(data.items()):
        print(f"\n### {suite} t{tid}   (manipulated body: {meta[(suite, tid)].get('body')})")
        hdr = (f"{'H':>4} {'arm':>8} {'succ':>9} {'rate':>7} {'stale':>6} "
               f"{'iv_step':>8} {'reacq':>6} {'obj_move':>9} {'bad':>4} {'psnr':>7} "
               f"{'steps':>9} {'TO':>4}")
        print(hdr)
        print("-" * len(hdr))
        rows = {}
        for h in sorted(per_h):
            for arm in ("control", "disturb"):
                eps = per_h[h].get(arm, [])
                if not eps:
                    continue
                n = len(eps)
                s = sum(1 for e in eps if e["success"])
                stale = sum(e["stale_action_steps"] for e in eps) / n
                bad = sum(1 for e in eps if e.get("contaminated"))
                ivs = [e["intervention_step"] for e in eps if e["intervention_step"] >= 0]
                iv = sum(ivs) / len(ivs) if ivs else -1
                lat = [e["reacq_latency"] for e in eps if e["reacq_latency"] >= 0]
                lat_s = sum(lat) / len(lat) if lat else -1
                mv = [e["obj_net_motion"] for e in eps if e["obj_net_motion"] is not None]
                mv_s = sum(mv) / len(mv) if mv else float("nan")
                ps = [e["psnr"] for e in eps if e.get("psnr") is not None]
                ps_s = sum(ps) / len(ps) if ps else float("nan")
                # graded signals: success alone is coarse.  A failed disturbed
                # episode is almost always a 400-step timeout, and a recovered one
                # still costs extra steps, so report both.
                stp = [e["steps"] for e in eps if e.get("steps") is not None]
                stp_s = sum(stp) / len(stp) if stp else float("nan")
                to = sum(1 for s in stp if s >= 400)
                print(f"{h:>4} {arm:>8} {s:>4}/{n:<4} {s/n:>7.2f} {stale:>6.1f} "
                      f"{iv:>8.0f} {lat_s:>6.1f} {mv_s:>9.3f} {bad:>4} {ps_s:>7.2f} "
                      f"{stp_s:>9.1f} {to:>4}")
                rows[arm] = {"n": n, "succ": s, "rate": s / n, "stale": stale,
                             "iv_step": iv, "reacq": lat_s, "obj_move": mv_s,
                             "contaminated": bad, "psnr": ps_s,
                             "mean_steps": stp_s, "timeouts": to}
            if "control" in rows and "disturb" in rows:
                d = rows["control"]["rate"] - rows["disturb"]["rate"]
                print(f"{h:>4} {'DELTA':>8} {'':>9} {d:>7.2f}")
                summary.setdefault(f"{suite}_t{tid}", {})[h] = {
                    "control_rate": rows["control"]["rate"],
                    "disturb_rate": rows["disturb"]["rate"],
                    "cost": d,
                    "stale_disturb": rows["disturb"]["stale"],
                    "contaminated_disturb": rows["disturb"].get("contaminated", 0),
                    "psnr_control": rows["control"].get("psnr"),
                    "psnr_disturb": rows["disturb"].get("psnr"),
                    "n": rows["control"]["n"],
                    "mean_steps_control": rows["control"].get("mean_steps"),
                    "mean_steps_disturb": rows["disturb"].get("mean_steps"),
                    "timeouts_control": rows["control"].get("timeouts"),
                    "timeouts_disturb": rows["disturb"].get("timeouts"),
                }
        # trend
        hh = sorted(k for k in summary.get(f"{suite}_t{tid}", {}))
        if len(hh) >= 2:
            costs = [summary[f"{suite}_t{tid}"][h]["cost"] for h in hh]
            stale = [summary[f"{suite}_t{tid}"][h]["stale_disturb"] for h in hh]
            print(f"\n  cost by H: " + ", ".join(f"H{h}={c:+.2f}" for h, c in zip(hh, costs)))
            print(f"  stale by H: " + ", ".join(f"H{h}={s:.0f}" for h, s in zip(hh, stale)))
            mono = all(costs[i] <= costs[i + 1] + 1e-9 for i in range(len(costs) - 1))
            print(f"  monotone increasing cost with horizon: {mono}")

    # pooled across tasks: this is the headline curve (one line, not one per task)
    pooled = {}
    for _key, per_h in data.items():
        for h, arms in per_h.items():
            for arm, eps in arms.items():
                pooled.setdefault(h, {}).setdefault(arm, []).extend(eps)
    if pooled:
        print("\n### POOLED across tasks (headline)")
        summary["_pooled"] = {}
        for h in sorted(pooled):
            c = pooled[h].get("control", [])
            d = pooled[h].get("disturb", [])
            if not c or not d:
                continue
            cr = sum(1 for e in c if e["success"]) / len(c)
            dr = sum(1 for e in d if e["success"]) / len(d)
            _cs = [e["steps"] for e in c if e.get("steps") is not None]
            _ds = [e["steps"] for e in d if e.get("steps") is not None]
            summary["_pooled"][h] = {
                "control_rate": cr,
                "disturb_rate": dr,
                "cost": cr - dr,
                "stale_disturb": sum(e["stale_action_steps"] for e in d) / len(d),
                "contaminated_disturb": sum(1 for e in d if e.get("contaminated")),
                "n_control": len(c),
                "n_disturb": len(d),
                "mean_steps_control": sum(_cs) / len(_cs) if _cs else None,
                "mean_steps_disturb": sum(_ds) / len(_ds) if _ds else None,
                "timeouts_control": sum(1 for s in _cs if s >= 400),
                "timeouts_disturb": sum(1 for s in _ds if s >= 400),
            }
            print(f"  H{h:>3}  control {cr:.2f} (n={len(c)})  disturb {dr:.2f} (n={len(d)})"
                  f"  cost {cr - dr:+.2f}")

    # carry the exact run settings so the report cannot drift from what ran
    cfgp = OUT_ROOT / "run_config.json"
    if cfgp.exists():
        try:
            summary["_config"] = json.loads(cfgp.read_text())
        except Exception as exc:  # pragma: no cover
            print(f"  (could not read run_config.json: {exc})")
    outp = OUT_ROOT / "gate13_summary.json"
    with open(outp, "w") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
    print(f"\nwrote {outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
