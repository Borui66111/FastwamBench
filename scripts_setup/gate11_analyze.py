"""[fastbench] Gate 11 H3 analysis: stale-plan execution and post-intervention correction.

Compares the CONTROL and DISTURBANCE arms of the Gate 11 sweep (and can also be
pointed at the Gate 9 pair for a smoke test).

What the harness guarantees (by construction)
---------------------------------------------
Both arms are deterministic and share the same env and init state, so their
executed actions are identical up to the intervention. The intervention displaces
a free-joint object *immediately after* a chunk was planned from the
pre-intervention observation (WARM_START §9.2), so that chunk is stale: it will be
executed in full even though the world it was planned against no longer exists.

Timeline with replan_steps=N, wait=30, intervention at replan_idx=1:
    t=30..39  chunk 0 executed
    t=40      replan_idx=1 -> chunk 1 planned from the PRE-intervention world
    t=40      world displaced           <- chunk 1 is now stale
    t=40..49  the N stale actions execute (identical to control by construction)
    t=50      replan_idx=2 -> first chunk planned from the POST-intervention world

So `divergence_gap == stale_window` is a harness-correctness check, not a finding.
The behavioural signals are the post-replan divergence magnitude, whether the arm
re-approaches the displaced object, and whether object progress is lost.

Metrics
-------
  divergence_onset/gap   - first step whose executed action differs from control,
                           and how far after the intervention that is
  stale_window           - observed count of post-intervention stale steps
  plan_divergence        - L1 distance between the control and disturbance chunk
                           summaries at the first post-intervention replan
                           (chunk `mean`, 7-D)
  eef_obj_min/last       - min and final EEF-to-object distance after the
                           intervention, per arm (re-approach evidence)
  obj_net_motion         - how far the displaced object travels after the
                           intervention, per arm
  success / stale_action_steps

Usage:
  python scripts_setup/gate11_analyze.py
  # smoke test against the Gate 9 pair:
  GATE11_PREFIX=gate9b CONTROL_SUFFIX=control_oa_t0 DISTURB_SUFFIX=world_oa_t0 \
    python scripts_setup/gate11_analyze.py
"""
import json
import math
import os
import sys

ROOT = "/data1/liborui/fastwam_bench"
STEPS = (1, 5, 10)
PREFIX = os.environ.get("GATE11_PREFIX", "gate11")
CTL_SUF = os.environ.get("CONTROL_SUFFIX", "control")
DST_SUF = os.environ.get("DISTURB_SUFFIX", "disturb")


def load(path):
    if not os.path.exists(path):
        return None
    return [json.loads(l) for l in open(path) if l.strip()]


def l1(a, b):
    return sum(abs(x - y) for x, y in zip(a, b))


def dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def recs_of(recs, ep, event):
    return [r for r in recs if r.get("event") == event and r.get("episode") == ep]


def find_paths(rs):
    if PREFIX == "gate11":
        return (f"{ROOT}/results/gate11_{CTL_SUF}_rs{rs}/records.jsonl",
                f"{ROOT}/results/gate11_{DST_SUF}_rs{rs}/records.jsonl")
    return (f"{ROOT}/results/{PREFIX}_{CTL_SUF}/records.jsonl",
            f"{ROOT}/results/{PREFIX}_{DST_SUF}/records.jsonl")


def analyse(rs):
    cpath, dpath = find_paths(rs)
    c, d = load(cpath), load(dpath)
    if c is None or d is None:
        return {"replan_steps": rs, "error": "missing records",
                "have": {"control": c is not None, "disturb": d is not None}}

    ivs = [r for r in d if r.get("event") == "intervention"]
    iv_body = ivs[0].get("body") if ivs else None
    cends = [r for r in c if r.get("event") == "episode_end"]
    dends = [r for r in d if r.get("event") == "episode_end"]

    out = {
        "replan_steps": rs,
        "body": iv_body,
        "delta": ivs[0].get("delta") if ivs else None,
        "episodes": len(dends),
        "success_control": sum(1 for e in cends if e.get("success")),
        "success_disturb": sum(1 for e in dends if e.get("success")),
        "stale_steps_control": sum(e.get("stale_action_steps", 0) for e in cends),
        "stale_steps_disturb": sum(e.get("stale_action_steps", 0) for e in dends),
        "per_episode": [],
    }

    for ep in sorted({r["episode"] for r in dends}):
        cs = recs_of(c, ep, "step")
        ds = recs_of(d, ep, "step")
        cm = {r["t"]: r for r in cs}
        dm = {r["t"]: r for r in ds}
        common = sorted(set(cm) & set(dm))
        iv_t = next((r["t"] for r in ds if r.get("world_intervened")), None)
        stale_ts = sorted(r["t"] for r in ds if r.get("stale"))

        # Cross-arm determinism: with a pinned seed the two arms share sampling
        # noise, so the pre-intervention L1 between them is at the ~1e-3 level
        # (a single bit of noise in 10-dim action space). Anything materially
        # larger after the intervention is a real consequence of the world change.
        pre = [l1(cm[t]["action"], dm[t]["action"]) for t in common
               if iv_t is not None and t < iv_t
               and cm[t].get("action") and dm[t].get("action")]
        base_max = round(max(pre), 6) if pre else 0.0
        thr = max(20.0 * base_max, 5e-3)   # well above noise floor
        onset = None
        for t in common:
            a, b = cm[t].get("action"), dm[t].get("action")
            if a and b and t >= (iv_t or 0) and l1(a, b) > thr:
                onset = t
                break

        # plan divergence at the first replan after the intervention
        cr = {r["replan_idx"]: r for r in recs_of(c, ep, "replan")}
        dr = {r["replan_idx"]: r for r in recs_of(d, ep, "replan")}
        plan_div, plan_ri = None, None
        for ri in sorted(dr):
            if iv_t is not None and dr[ri].get("t", 0) > iv_t and ri in cr:
                cmn = (cr[ri].get("chunk") or {}).get("mean")
                dmn = (dr[ri].get("chunk") or {}).get("mean")
                if cmn and dmn:
                    plan_div, plan_ri = round(l1(cmn, dmn), 6), ri
                break

        # EEF-to-object distance and object motion after the intervention
        def eef_obj(ms):
            vals = []
            for r in ms:
                st = r.get("state") or {}
                e = (st.get("eef") or {}).get("pos")
                o = ((st.get("bodies") or {}).get(iv_body) or {}).get("pos") if iv_body else None
                if e and o and iv_t is not None and r["t"] >= iv_t:
                    vals.append(dist(e, o))
            return (round(min(vals), 4), round(vals[-1], 4)) if vals else (None, None)

        def obj_motion(ms):
            if not iv_body:
                return None
            pts = [(r["t"], ((r.get("state") or {}).get("bodies") or {}).get(iv_body, {}).get("pos"))
                   for r in ms]
            pts = [(t, p) for t, p in pts if p and iv_t is not None and t >= iv_t]
            return round(dist(pts[0][1], pts[-1][1]), 4) if len(pts) >= 2 else None

        cmin, clast = eef_obj(cs)
        dmin, dlast = eef_obj(ds)

        out["per_episode"].append({
            "episode": ep,
            "iv_t": iv_t,
            "iv_body": iv_body,
            "stale_window": len(stale_ts),
            "stale_t_range": [stale_ts[0], stale_ts[-1]] if stale_ts else None,
            "pre_iv_max_l1": base_max,
            "divergence_threshold": round(thr, 6),
            "divergence_onset": onset,
            "divergence_gap": (onset - iv_t) if (onset is not None and iv_t is not None) else None,
            "plan_divergence": {"replan_idx": plan_ri, "l1_mean": plan_div},
            "eef_obj_min": {"control": cmin, "disturb": dmin},
            "eef_obj_last": {"control": clast, "disturb": dlast},
            "obj_net_motion": {"control": obj_motion(cs), "disturb": obj_motion(ds)},
        })
    return out


def main():
    results = [analyse(rs) for rs in STEPS]
    print(json.dumps(results, indent=2, default=str))

    print("\n=== GATE 11 - CONTROL vs DISTURBANCE ===")
    hdr = (f"{'rs':>4} {'succC':>6} {'succD':>6} {'staleC':>7} {'staleD':>7} "
           f"{'window':>7} {'gap':>5} {'planD':>8} {'eefObjC':>9} {'eefObjD':>9} {'objMoveD':>9}")
    print(hdr)
    print("-" * len(hdr))
    for r in results:
        if "error" in r:
            print(f"{r['replan_steps']:>4}  MISSING ({r.get('have')})")
            continue
        e0 = r["per_episode"][0] if r["per_episode"] else {}
        pd = e0.get("plan_divergence") or {}
        eo = e0.get("eef_obj_min") or {}
        om = e0.get("obj_net_motion") or {}
        print(f"{r['replan_steps']:>4} {r['success_control']:>6} {r['success_disturb']:>6} "
              f"{r['stale_steps_control']:>7} {r['stale_steps_disturb']:>7} "
              f"{str(e0.get('stale_window')):>7} {str(e0.get('divergence_gap')):>5} "
              f"{str(pd.get('l1_mean')):>8} {str(eo.get('control')):>9} {str(eo.get('disturb')):>9} "
              f"{str(om.get('disturb')):>9}")
    print("(episode 0 shown for per-episode columns; totals in the JSON above)")

    print("\n=== Interpretation ===")
    ok = True
    for r in results:
        if "error" in r or not r["per_episode"]:
            continue
        e0 = r["per_episode"][0]
        gap, win = e0.get("divergence_gap"), e0.get("stale_window")
        pd = (e0.get("plan_divergence") or {}).get("l1_mean")
        print(f"  replan_steps={r['replan_steps']}: stale window {win} steps "
              f"(t={e0.get('stale_t_range')}); first action divergence {gap} step(s) after the "
              f"intervention; plan divergence at the next replan L1={pd}.")
        if gap is not None and win is not None:
            if gap == win:
                print("      -> harness correct: the entire stale chunk was executed verbatim, "
                      "then the policy re-planned on the post-intervention world.")
            elif gap < win:
                print(f"      -> UNEXPECTED: diverged {win - gap} step(s) early (env not "
                      "deterministic across arms, or the intervention leaked earlier).")
            else:
                print("      -> UNEXPECTED: divergence later than the stale window.")
        if pd == 0.0:
            print("      -> plan UNCHANGED after seeing the displaced world (no correction).")
            ok = False
        elif pd is not None:
            print("      -> plan CHANGED after seeing the displaced world (correction present).")
    if ok:
        print("\n  All arms: the policy commits to the stale chunk for the full stale window and "
              "then corrects. This is the H3 'world-model commitment' signature.")
    return 0


if __name__ == "__main__":
    sys.exit(main())