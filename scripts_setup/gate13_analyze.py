#!/usr/bin/env python
"""[fastbench] Gate 13 analysis: paired control vs disturbance -> recovery metrics.

Reads `results/gate13_<TAG>_{control,disturb}/records.jsonl` and reports, per
matched episode pair (same init state, same seed => identical up to the
intervention):

  Control SR            successes / episodes               (control arm)
  Disturbed SR          successes / episodes               (disturb arm)
  Success Drop          Control SR - Disturbed SR
  Recovery Rate         (# pairs where control AND disturb succeed)
                        / (# pairs where control succeeds)
  Recovery Latency      steps from the intervention until the EEF re-acquires the
                        displaced object (min EEF-object distance < 0.12 m) in the
                        disturb arm, over pairs whose control succeeds
  Stale Action Steps    post-intervention steps executed verbatim from the stale
                        chunk (harness invariant: == replan_steps)
  Plan Divergence (L1)  L1 between control/disturb chunk means at the first
                        post-intervention replan (0 => no correction)

Usage:
  GATE13_TAG=libero_spatial_t0_rs1 python scripts_setup/gate13_analyze.py
"""
import json
import math
import os
import sys

ROOT = "/data1/liborui/fastwam_bench"
TAG = os.environ.get("GATE13_TAG", "libero_spatial_t0_rs1")
RECLAIM_M = 0.12          # EEF-to-object distance counted as (re-)acquisition


def load(path):
    if not os.path.exists(path):
        return None
    return [json.loads(l) for l in open(path) if l.strip()]


def l1(a, b):
    return sum(abs(x - y) for x, y in zip(a, b))


def dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def by_ep(recs, event):
    out = {}
    for r in recs:
        if r.get("event") == event:
            out.setdefault(r.get("episode"), []).append(r)
    return out


def analyse():
    cpath = f"{ROOT}/results/gate13_{TAG}_control/records.jsonl"
    dpath = f"{ROOT}/results/gate13_{TAG}_disturb/records.jsonl"
    c, d = load(cpath), load(dpath)
    if c is None or d is None:
        print(json.dumps({"tag": TAG, "error": "missing records",
                          "have": {"control": c is not None, "disturb": d is not None}}, indent=2))
        return 1

    ivs = [r for r in d if r.get("event") == "intervention"]
    body = ivs[0].get("body") if ivs else None
    cends = by_ep(c, "episode_end")
    dends = by_ep(d, "episode_end")
    csteps = by_ep(c, "step")
    dsteps = by_ep(d, "step")
    creplans = by_ep(c, "replan")
    dreplans = by_ep(d, "replan")

    eps = sorted(set(cends) & set(dends))
    pairs = []
    for ep in eps:
        csucc = bool(cends[ep][0].get("success"))
        dsucc = bool(dends[ep][0].get("success"))
        ds = dsteps.get(ep, [])
        iv_t = next((r["t"] for r in ds if r.get("world_intervened")), None)
        stale_ts = sorted(r["t"] for r in ds if r.get("stale"))

        # recovery latency: first post-intervention step with EEF within RECLAIM_M
        lat = None
        best = None
        for r in ds:
            if iv_t is None or r["t"] <= iv_t:
                continue
            st = r.get("state") or {}
            e = (st.get("eef") or {}).get("pos")
            o = ((st.get("bodies") or {}).get(body) or {}).get("pos") if body else None
            if e and o:
                dd = dist(e, o)
                best = dd if best is None else min(best, dd)
                if dd < RECLAIM_M:
                    lat = r["t"] - iv_t
                    break

        # plan divergence at the first post-intervention replan
        plan_div = None
        for ri, dr in sorted(dreplans.get(ep, []) and {r["replan_idx"]: r for r in dreplans[ep]}.items()):
            if iv_t is not None and dr.get("t", 0) > iv_t:
                cr = {r["replan_idx"]: r for r in creplans.get(ep, [])}
                if ri in cr:
                    cmn = (cr[ri].get("chunk") or {}).get("mean")
                    dmn = (dr.get("chunk") or {}).get("mean")
                    if cmn and dmn:
                        plan_div = round(l1(cmn, dmn), 6)
                break

        pairs.append({
            "episode": ep, "iv_t": iv_t,
            "control_success": csucc, "disturb_success": dsucc,
            "stale_steps": len(stale_ts),
            "recovery_latency": lat, "min_eef_obj": round(best, 4) if best is not None else None,
            "plan_divergence_l1": plan_div,
        })

    n = len(pairs)
    csuccess = sum(p["control_success"] for p in pairs)
    dsuccess = sum(p["disturb_success"] for p in pairs)
    denom = sum(1 for p in pairs if p["control_success"])
    numer = sum(1 for p in pairs if p["control_success"] and p["disturb_success"])
    lats = [p["recovery_latency"] for p in pairs if p["control_success"] and p["recovery_latency"] is not None]

    summary = {
        "tag": TAG, "body": body, "episodes": n,
        "control_success": csuccess, "control_sr": round(csuccess / n, 4) if n else None,
        "disturb_success": dsuccess, "disturb_sr": round(dsuccess / n, 4) if n else None,
        "success_drop": round((csuccess - dsuccess) / n, 4) if n else None,
        "recovery_rate": round(numer / denom, 4) if denom else None,
        "recovery_rate_note": f"{numer}/{denom} disturbed episodes whose paired control succeeds",
        "recovery_latency_mean": round(sum(lats) / len(lats), 2) if lats else None,
        "recovery_latency_all": lats,
        "stale_steps_total": sum(p["stale_steps"] for p in pairs),
        "plan_divergence_nonzero": sum(1 for p in pairs if p["plan_divergence_l1"]),
        "pairs": pairs,
    }
    print(json.dumps(summary, indent=2, default=str))

    print(f"\n=== GATE 13 — {TAG} (body={body}) ===")
    hdr = f"{'ep':>3} {'ctlSR':>6} {'dstSR':>6} {'stale':>6} {'recov_lat':>10} {'minEEF-obj':>11} {'planL1':>9}"
    print(hdr); print("-" * len(hdr))
    for p in pairs:
        print(f"{p['episode']:>3} {int(p['control_success']):>6} {int(p['disturb_success']):>6} "
              f"{p['stale_steps']:>6} {str(p['recovery_latency']):>10} {str(p['min_eef_obj']):>11} "
              f"{str(p['plan_divergence_l1']):>9}")
    print(f"\nControl SR {csuccess}/{n}   Disturbed SR {dsuccess}/{n}   "
          f"Success Drop {summary['success_drop']}   Recovery Rate {summary['recovery_rate']}   "
          f"Recovery Latency {summary['recovery_latency_mean']}")
    return 0


if __name__ == "__main__":
    sys.exit(analyse())
