"""Gate 14H: does the capped corrective response show up as geometric error?

Gate 14G measured the policy's *action* response and found it plateaus at ~0.11
normalized units while success keeps falling. That leaves two readings:

  (a) GEOMETRIC - the correction is too small, so the object ends up further from
      the basket in proportion to the strike magnitude.
  (b) NON-GEOMETRIC - the object reaches the basket regardless, and the loss is
      in the release (13D found "held above the basket" as the dominant mode).

This reads object/basket geometry straight out of the per-step records, so it
needs no new rollouts. For every episode it reports the object-to-basket xy
distance at the strike, the minimum reached, and the final value, plus final z.

Usage:
  python scripts_setup/gate14h_geometry.py \
      --runs results/gate13_g14gctl results/gate13_g14gm0002 ... \
      --json results/gate14h_geometry.json
"""

import argparse
import glob
import json
import os

import numpy as np
from scipy.stats import mannwhitneyu, spearmanr


def run_meta(run):
    """Magnitude and arm, read from the run's own config.

    Deriving either from the directory name is how Gate 14G's tag ambiguity bit
    (`g14gm002` is 20 mm, `g14gm0002` is 2 mm); the config is authoritative.
    """
    path = os.path.join(run, "run_config.json")
    if not os.path.exists(path):
        return None, None
    cfg = json.load(open(path))
    is_ctl = "control" in cfg.get("arms", []) and "disturb" not in cfg.get("arms", [])
    return (0.0 if is_ctl else float(cfg["magnitude_m"])), is_ctl


def episode_body(steps):
    """The manipulated body, chosen from the data.

    episode_end carries `world_body: "auto"` in the zero-stale arm (the body is
    resolved at intervention time), so it cannot be trusted as a key into
    state.bodies. Pick the body that travels furthest, excluding the floor and
    the goal container.
    """
    if not steps:
        return None
    names = [n for n in steps[0]["state"]["bodies"]
             if n != "floor" and "basket" not in n]
    best, best_d = None, -1.0
    for n in names:
        pts = [np.array(r["state"]["bodies"][n]["pos"], float)
               for r in steps if n in r["state"]["bodies"]]
        if len(pts) < 2:
            continue
        span = float(np.max(np.linalg.norm(np.array(pts) - pts[0], axis=1)))
        if span > best_d:
            best, best_d = n, span
    return best


def episodes(run):
    out = []
    for path in sorted(glob.glob(os.path.join(run, "**", "records.jsonl"),
                                 recursive=True)):
        cell = os.path.basename(os.path.dirname(path))
        seed = int(cell.split("_s")[-1])
        recs = [json.loads(l) for l in open(path) if l.strip()]
        end = {r["episode"]: r for r in recs if r.get("event") == "episode_end"}
        ivs = {}
        for r in recs:
            if r.get("event") == "intervention":
                ivs.setdefault(r["episode"], []).append(r)
        by_ep = {}
        for r in recs:
            if r.get("event") == "step":
                by_ep.setdefault(r["episode"], []).append(r)
        for ep, steps in sorted(by_ep.items()):
            if ep not in end:
                continue
            body = episode_body(steps)
            if body is None:
                continue
            traj = [(r["t"], np.array(r["state"]["bodies"][body]["pos"], float))
                    for r in steps if body in r["state"]["bodies"]]
            if len(traj) < 2:
                continue
            basket = np.array(steps[0]["state"]["bodies"]["basket_1_main"]["pos"],
                              float)
            out.append({
                "seed": seed, "episode": ep, "body": body,
                "success": bool(end[ep]["success"]),
                "steps": int(end[ep]["steps"]),
                "traj": traj, "basket": basket,
                "iv": ivs.get(ep, []),
            })
    return out


def summarise(eps, label):
    rows = []
    for e in eps:
        b = e["basket"]
        ts = [t for t, _ in e["traj"]]
        d = [float(np.linalg.norm(q[:2] - b[:2])) for _, q in e["traj"]]
        strike = e["iv"][0]["t"] if e["iv"] else None
        if strike is not None:
            i = int(np.argmin([abs(t - strike) for t in ts]))
            d_strike = d[i]
            # geometry right after the strike, at the next replan
            j = int(np.argmin([abs(t - (strike + 10)) for t in ts]))
            d_next = d[j]
        else:
            d_strike = d_next = None
        # Is the object still descending when time runs out, or stuck? Fit z over
        # the last 40 steps; a slope near zero means the episode is not merely
        # slow, it has stopped making progress.
        tail = e["traj"][-40:]
        if len(tail) > 5:
            tt = np.array([t for t, _ in tail], float)
            zz = np.array([q[2] for _, q in tail], float)
            z_slope = float(np.polyfit(tt - tt[0], zz, 1)[0])
        else:
            z_slope = None
        rows.append({
            "seed": e["seed"], "episode": e["episode"],
            "success": e["success"], "steps": e["steps"],
            "d_strike": d_strike, "d_next": d_next,
            "d_min": min(d), "d_end": d[-1],
            "z_end": float(e["traj"][-1][1][2]),
            "z_slope_tail": z_slope,
            "z_max": float(max(q[2] for _, q in e["traj"])),
        })
    return {"label": label, "n": len(rows),
            "successes": sum(r["success"] for r in rows), "episodes": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    out = []
    mag_of = {}
    print(f"{'run':>28s}  {'n':>2s} {'succ':>5s} {'d_strike':>9s} "
          f"{'d_next':>7s} {'d_min':>7s} {'d_end':>7s} {'z_end':>7s}")
    for run in args.runs:
        eps = episodes(run)
        mag, is_ctl = run_meta(run)
        label = os.path.basename(run)
        if mag is not None:
            mag_of[label] = mag
        if not eps:
            print(f"{label:>28s}  -- no episodes")
            continue
        s = summarise(eps, label)
        out.append(s)

        def m(key):
            v = [r[key] for r in s["episodes"] if r[key] is not None]
            return f"{np.mean(v):9.4f}" if v else "     n/a"
        print(f"{s['label']:>28s}  {s['n']:2d} {s['successes']:>2d}/{s['n']:<2d} "
              f"{m('d_strike')} {m('d_next'):>7s} {m('d_min'):>7s} "
              f"{m('d_end'):>7s} {m('z_end'):>7s}")

    if args.json:
        with open(args.json, "w") as f:
            json.dump(out, f, indent=1)
        print(f"\nwrote {args.json}")

    # --- outcome split -------------------------------------------------------
    # The aggregate z_end mixes two things: how high a successful place leaves
    # the object, and how many episodes are abandoned in the air. Split them.
    print("\noutcome split (disturb runs only; z_end in metres, xy in metres)")
    print(f"{'mag_mm':>6s} {'succ':>6s} {'z_end|succ':>11s} {'z_end|fail':>11s} "
          f"{'d_end|succ':>11s} {'d_end|fail':>11s}")
    zs, xs = [], []
    ok_z, bad_z = [], []
    for s in out:
        mag = mag_of.get(s["label"])
        if mag is None or mag == 0.0:
            continue
        ok = [e for e in s["episodes"] if e["success"]]
        no = [e for e in s["episodes"] if not e["success"]]
        for e in s["episodes"]:
            zs.append(e["z_end"])
            xs.append(mag)
        ok_z += [e["z_end"] for e in ok]
        bad_z += [e["z_end"] for e in no]

        def avg(v, k):
            return f"{np.mean([e[k] for e in v]):11.4f}" if v else "        n/a"
        print(f"{mag * 1000:6.0f} {len(ok):>2d}/{s['n']:<3d} {avg(ok, 'z_end')} "
              f"{avg(no, 'z_end')} {avg(ok, 'd_end')} {avg(no, 'd_end')}")

    if len(zs) > 2:
        rho, p = spearmanr(xs, zs)
        print(f"\nz_end vs magnitude: Spearman rho={rho:+.3f} p={p:.2e} "
              f"(n={len(zs)})")
    if ok_z and bad_z:
        u, p = mannwhitneyu(ok_z, bad_z, alternative="less")
        print(f"z_end success (n={len(ok_z)}, mean {np.mean(ok_z):.4f}) vs "
              f"failure (n={len(bad_z)}, mean {np.mean(bad_z):.4f}): "
              f"Mann-Whitney U p={p:.2e}")

    # Among failures only: does the height at which the episode stalls scale with
    # the strike? That is the dose-response the success rate cannot show.
    fz, fx = [], []
    for s in out:
        mag = mag_of.get(s["label"])
        if mag is None or mag == 0.0:
            continue
        for e in s["episodes"]:
            if not e["success"]:
                fz.append(e["z_end"])
                fx.append(mag)
    if len(fz) > 3:
        rho, p = spearmanr(fx, fz)
        print(f"among failures: z_end vs magnitude rho={rho:+.3f} p={p:.2e} "
              f"(n={len(fz)})")
    if fz:
        slopes = [e["z_slope_tail"] for s in out
                  for e in s["episodes"] if not e["success"]
                  and e["z_slope_tail"] is not None]
        print(f"failures: tail z-slope {min(slopes)*1000:+.2f} to "
              f"{max(slopes)*1000:+.2f} mm/step (median "
              f"{np.median(slopes)*1000:+.2f}); "
              f"{sum(1 for v in slopes if v > 0)}/{len(slopes)} still rising")


if __name__ == "__main__":
    main()
