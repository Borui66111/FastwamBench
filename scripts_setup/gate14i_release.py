"""Gate 14I: does the policy ever enter the release phase?

Gate 14H showed the object reaches the basket in xy and stalls 4-11 cm above it.
That left two mechanisms: the policy stops commanding the descent, or it
commands it and the object does not follow. The step records carry the executed
7-D action and the eef/body poses, so this is answerable without new runs.

Action layout (robosuite OSC): [dx, dy, dz, drx, dry, drz, gripper].
Gripper sign convention, from the vendored controller itself
(`robosuite/models/grippers/panda_gripper.py`, format_action docstring):
**-1 => open, +1 => closed.** Verified empirically: in the 40 mm success trace
the command goes -1 -> +1 exactly as the fingers close on the object.

The physical finger state is NOT recorded, and the actuator ramps at 0.01 per
step, so a commanded open does not mean an instantaneous release. Claims here
are about the *command* and about the object's own motion, not about finger
width.

Two metrics, both chosen to be robust:

  gripper_open_frac   fraction of post-trigger steps commanding the gripper
                      open (action[6] < 0).
  cmd_dz_last40       mean commanded vertical motion over the final 40 steps,
                      compared against the object's own slope over that window.
                      Together these separate "did not command descent" from
                      "commanded descent, object did not follow".
"""

import argparse
import glob
import json
import os

import numpy as np


def load(run):
    """Episodes grouped by their own `episode` field.

    Taking one episode per file silently drops the rest: each records.jsonl
    holds every trial of that job.
    """
    out = []
    for path in sorted(glob.glob(os.path.join(run, "**", "records.jsonl"),
                                 recursive=True)):
        recs = [json.loads(l) for l in open(path)]
        by = {}
        for r in recs:
            if r.get("event") == "step":
                by.setdefault(r["episode"], []).append(r)
        for r in recs:
            if r.get("event") == "episode_end":
                ep = r["episode"]
                cell = os.path.basename(os.path.dirname(path))
                seed = int(cell.rsplit("_s", 1)[1])
                out.append({
                    "seed": seed, "episode": ep,
                    "success": bool(r["success"]), "steps": int(r["steps"]),
                    "steps_recs": by.get(ep, []),
                    "cell": cell,
                })
    return out


def body_name(step_recs):
    """The manipulated object, found in the records rather than assumed.

    world_body is 'auto' in these runs, and the body name differs per task.
    """
    for k in step_recs[0]["state"]["bodies"]:
        if k.startswith(("alphabet", "cream_cheese", "salad", "tomato",
                         "butter", "milk", "orange", "pudding")):
            return k
    raise SystemExit("no manipulated body found in state.bodies")


def analyse(ep):
    st = ep["steps_recs"]
    if len(st) < 45:
        return None
    body = body_name(st)
    grip = np.array([r["action"][6] for r in st], dtype=float)
    dz = np.array([r["action"][2] for r in st], dtype=float)
    oz = np.array([r["state"]["bodies"][body]["pos"][2] for r in st], dtype=float)
    ez = np.array([r["state"]["eef"]["pos"][2] for r in st], dtype=float)
    ts = np.array([r["t"] for r in st], dtype=float)

    # Trigger: the first strike if any, else the lift (object leaves the table).
    strike_t = next((r["t"] for r in st if r.get("intervention")), None)
    if strike_t is None:
        lift = np.where(oz > oz[:10].mean() + 0.02)[0]
        trigger_t = float(ts[lift[0]]) if len(lift) else float(ts[0])
    else:
        trigger_t = float(strike_t)

    post = ts >= trigger_t
    tail = slice(max(0, len(st) - 40), len(st))
    eef_end = np.array(st[-1]["state"]["eef"]["pos"], dtype=float)
    obj_end = np.array(st[-1]["state"]["bodies"][body]["pos"], dtype=float)

    # Release height: the object's height at the moment it separates from the
    # eef (|eef-obj| first exceeds 5 cm after the trigger). This is physical,
    # not a command: a controlled placement separates just above the basket rim
    # (~0.14-0.16 m), while a carried-then-dropped object separates much higher.
    sep_idx = None
    for i in range(len(st)):
        if ts[i] < trigger_t:
            continue
        e = np.array(st[i]["state"]["eef"]["pos"], dtype=float)
        o = np.array(st[i]["state"]["bodies"][body]["pos"], dtype=float)
        if np.linalg.norm(e - o) > 0.05:
            sep_idx = i
            break
    release_z = float(oz[sep_idx]) if sep_idx is not None else float("nan")
    # gripper commanded open at the moment of separation: a real release
    release_grip = float(grip[sep_idx]) if sep_idx is not None else float("nan")
    # was the gripper already open while the object was still attached?
    carried_open = float(np.mean([1.0 if (grip[i] > 0 and np.linalg.norm(
        np.array(st[i]["state"]["eef"]["pos"]) -
        np.array(st[i]["state"]["bodies"][body]["pos"])) < 0.05) else 0.0
        for i in range(len(st)) if ts[i] >= trigger_t]))

    return {
        "seed": ep["seed"], "episode": ep["episode"],
        "success": ep["success"], "steps": ep["steps"],
        "trigger_t": trigger_t,
        "gripper_open_frac": float((grip[post] < 0).mean()),  # -1 = open
        "gripper_max_post": float(grip[post].max()),
        "gripper_min_post": float(grip[post].min()),
        "gripper_last40": float(grip[tail].mean()),
        "cmd_dz_last40": float(dz[tail].mean()),
        "obj_slope_mm": float(np.polyfit(range(len(oz[tail])), oz[tail], 1)[0] * 1000),
        "eef_slope_mm": float(np.polyfit(range(len(ez[tail])), ez[tail], 1)[0] * 1000),
        "obj_z_end": float(oz[-1]),
        "d_eef_obj": float(np.linalg.norm(eef_end - obj_end)),
        "release_z": release_z,
        "release_grip": release_grip,
        "carried_open": carried_open,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--json")
    args = ap.parse_args()

    rows = []
    print(f"{'run':>24s} {'succ':>5s} {'open_frac':>9s} {'grip_l40':>8s} "
          f"{'cmd_dz':>7s} {'obj_mm':>7s} {'d_eef_obj':>9s}")
    for run in args.runs:
        with open(os.path.join(run, "run_config.json")) as f:
            mag = float(json.load(f)["magnitude_m"])
        for ep in load(run):
            a = analyse(ep)
            if a is None:
                continue
            a["magnitude_m"] = mag
            a["run"] = os.path.basename(run)
            rows.append(a)
        sub = [r for r in rows if r["run"] == os.path.basename(run)]
        ok = [r for r in sub if r["success"]]
        no = [r for r in sub if not r["success"]]
        def m(rs, k):
            return f"{np.mean([r[k] for r in rs]):+.3f}" if rs else "  n/a"
        print(f"{os.path.basename(run):>24s} {len(ok):>2d}/{len(sub):<2d} "
              f"{m(ok,'gripper_open_frac'):>9s} {m(ok,'gripper_last40'):>8s} "
              f"{m(ok,'cmd_dz_last40'):>7s} {m(ok,'obj_slope_mm'):>7s} "
              f"{m(ok,'d_eef_obj'):>9s}")
        if no:
            print(f"{'  (failures)':>24s} {len(no):>2d}/{len(sub):<2d} "
                  f"{m(no,'gripper_open_frac'):>9s} {m(no,'gripper_last40'):>8s} "
                  f"{m(no,'cmd_dz_last40'):>7s} {m(no,'obj_slope_mm'):>7s} "
                  f"{m(no,'d_eef_obj'):>9s}")

    if args.json:
        with open(args.json, "w") as f:
            json.dump(rows, f, indent=1)
        print(f"\nwrote {args.json}")

    ok = [r for r in rows if r["success"]]
    no = [r for r in rows if not r["success"]]
    print("\n--- does the release phase ever happen? ---")
    print(f"successes n={len(ok)}: gripper commanded open for "
          f"{np.mean([r['gripper_open_frac'] for r in ok]):.3f} of post-trigger steps")
    print(f"failures  n={len(no)}: gripper commanded open for "
          f"{np.mean([r['gripper_open_frac'] for r in no]):.3f} of post-trigger steps")
    # -1 = open, so "never opens" is min command >= 0
    never_open = sum(1 for r in no if r["gripper_min_post"] >= 0.0)
    print(f"failures that NEVER command the gripper open after the trigger: "
          f"{never_open}/{len(no)}")

    print("\n--- commanded vs actual vertical motion (last 40 steps) ---")
    for label, rs in (("success", ok), ("failure", no)):
        if not rs:
            continue
        print(f"{label:8s} cmd_dz={np.mean([r['cmd_dz_last40'] for r in rs]):+.3f} "
              f"obj_slope={np.mean([r['obj_slope_mm'] for r in rs]):+.2f} mm/step "
              f"eef_slope={np.mean([r['eef_slope_mm'] for r in rs]):+.2f} mm/step "
              f"|eef-obj|={np.mean([r['d_eef_obj'] for r in rs]):.4f} m")

    print("\n--- release geometry (object height when it leaves the gripper) ---")
    for label, rs in (("success", ok), ("failure", no)):
        if not rs:
            continue
        rz = [r["release_z"] for r in rs if not np.isnan(r["release_z"])]
        rg = [r["release_grip"] for r in rs if not np.isnan(r["release_grip"])]
        co = [r["carried_open"] for r in rs]
        if rz:
            print(f"{label:8s} n={len(rz):2d} release_z={np.mean(rz):.3f} m "
                  f"(range {min(rz):.3f}-{max(rz):.3f}), "
                  f"grip at release={np.mean(rg):+.2f}, "
                  f"carried-with-gripper-open={np.mean(co):.3f}")

    # A success that separates high and was carried with the gripper open is a
    # drop-in, not a placement. Count them rather than letting them pass as
    # evidence of recovery.
    dropins = [r for r in ok if r["release_z"] > 0.20]
    print(f"\nsuccesses that separate above 0.20 m (drop-ins, not placements): "
          f"{len(dropins)}/{len(ok)}")
    for r in dropins:
        print(f"  {r['run']} seed{r['seed']} ep{r['episode']}: "
              f"release_z={r['release_z']:.3f} grip={r['release_grip']:+.2f} "
              f"carried_open={r['carried_open']:.2f}")


if __name__ == "__main__":
    main()
