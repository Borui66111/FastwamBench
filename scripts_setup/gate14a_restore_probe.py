#!/usr/bin/env python
"""[fastbench] Probe: WHY mid-episode restore diverges, and what closes the gap.

Stage 1 of gate14a_snapshot_smoke.py showed that restoring the flattened MuJoCo
state mid-episode does not reproduce the continuation. This probe isolates the
cause and quantifies it:

  A. numeric deltas  — is the divergence float noise (1e-12) or a real state gap?
  B. controller      — robosuite's OSC controller keeps goal_pos / goal_ori /
                       ori_ref / relative_ori / interpolators OUTSIDE sim state.
                       Restore them too and re-measure.
  C. sticky sim data — sim.data.ctrl, qfrc_applied, xfrc_applied, act, udd_state.
  D. observation     — is the wrapper's obs equal to the raw env obs at restore?

Run from FastWAM/ with MUJOCO_GL=egl.
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "FastWAM"))
sys.path.insert(0, str(ROOT / "scripts_setup"))

from gate14a_snapshot_smoke import (  # noqa: E402
    arr_hash, find_base_env, find_sim, get_flat_state, load_init_states,
    make_env, scripted_actions,
)


def ctrl_state(env):
    """Everything the OSC controller carries between steps."""
    base = find_base_env(env)
    robot = base.robots[0]
    c = robot.controller
    out = {}
    for name in ("goal_pos", "goal_ori", "ori_ref", "relative_ori", "initial_ee_pos",
                 "initial_ee_ori_mat", "initial_joint", "new_update"):
        v = getattr(c, name, None)
        if isinstance(v, np.ndarray):
            out[name] = v.copy()
        elif isinstance(v, (bool, int, float)):
            out[name] = v
    for ip_name in ("interpolator_pos", "interpolator_ori"):
        ip = getattr(c, ip_name, None)
        if ip is None:
            continue
        for attr in ("goal", "start", "step", "interp_step", "name"):
            v = getattr(ip, attr, None)
            if isinstance(v, np.ndarray):
                out[f"{ip_name}.{attr}"] = v.copy()
            elif isinstance(v, (bool, int, float)):
                out[f"{ip_name}.{attr}"] = v
    return out


def restore_ctrl(env, saved):
    base = find_base_env(env)
    c = base.robots[0].controller
    for k, v in saved.items():
        if "." in k:
            ip_name, attr = k.split(".", 1)
            ip = getattr(c, ip_name, None)
            if ip is not None:
                setattr(ip, attr, np.array(v) if isinstance(v, np.ndarray) else v)
        else:
            setattr(c, k, np.array(v) if isinstance(v, np.ndarray) else v)


def sticky(env):
    sim = find_sim(env).sim
    d = {}
    # qacc_warmstart is MuJoCo's solver warm-start cache. It is NOT part of
    # get_state()/set_state_from_flattened, and a stale value changes the FIRST
    # post-restore step even when qpos/qvel are bit-identical.
    for name in ("ctrl", "qfrc_applied", "xfrc_applied", "act",
                 "qacc_warmstart", "mocap_pos", "mocap_quat", "userdata"):
        v = getattr(sim.data, name, None)
        if v is not None:
            d[name] = np.array(v, dtype=float, copy=True)
    return d


def restore_sticky(env, saved):
    sim = find_sim(env).sim
    for k, v in saved.items():
        cur = getattr(sim.data, k, None)
        if cur is not None:
            cur[:] = v


def restore(env, flat, ctrl, stk):
    base = find_sim(env)
    base.sim.set_state_from_flattened(np.asarray(flat, dtype=float))
    restore_sticky(env, stk)
    base.sim.forward()
    restore_ctrl(env, ctrl)


def main():
    env, task, desc = make_env("libero_object", 0, seed=0)
    init = load_init_states(task, 0)
    env.reset()
    obs = env.set_init_state(init)
    acts = scripted_actions(60)
    for i in range(40):
        obs, _, _, _ = env.step(acts[i])

    sim = find_sim(env).sim
    flat = get_flat_state(env)
    ctrl = ctrl_state(env)
    stk = sticky(env)
    qpos0 = np.array(sim.data.qpos, dtype=float, copy=True)
    obs0 = {k: np.array(v, dtype=float, copy=True) if isinstance(v, np.ndarray) else v
            for k, v in obs.items()}

    print(f"snapshot step=40 state_dim={flat.size}")
    print(f"controller fields captured: {sorted(ctrl)}")
    print(f"sticky sim.data fields:     {sorted(stk)}")
    print()

    # reference: keep stepping
    ref = []
    for i in range(40, 45):
        obs, _, _, _ = env.step(acts[i])
        ref.append({"qpos": np.array(sim.data.qpos, dtype=float, copy=True),
                    "obs": {k: np.array(v, dtype=float, copy=True)
                            if isinstance(v, np.ndarray) else v for k, v in obs.items()}})

    def replay(tag, use_ctrl, use_sticky):
        base = find_sim(env)
        base.sim.set_state_from_flattened(np.asarray(flat, dtype=float))
        if use_sticky:
            restore_sticky(env, stk)
        base.sim.forward()
        if use_ctrl:
            restore_ctrl(env, ctrl)
        dq = float(np.abs(np.array(base.sim.data.qpos) - qpos0).max())
        raw = find_base_env(env)._get_observations()
        per_key = {}
        for k in obs0:
            if k not in raw or not isinstance(obs0[k], np.ndarray):
                continue
            a, b = np.asarray(raw[k]), np.asarray(obs0[k])
            if a.shape != b.shape:
                per_key[k] = float("inf")
                continue
            per_key[k] = float(np.abs(a.astype(float) - b.astype(float)).max())
        worst = sorted(per_key.items(), key=lambda kv: -kv[1])[:4]
        print(f"[{tag}] restore |dqpos|={dq:.3e}  worst obs deltas: "
              + ", ".join(f"{k}={v:.3e}" for k, v in worst))
        for j, i in enumerate(range(40, 45)):
            obs, _, _, _ = env.step(acts[i])
            dq = float(np.abs(np.array(base.sim.data.qpos) - ref[j]["qpos"]).max())
            print(f"    step {i}: |dqpos| vs ref = {dq:.3e}")
        print()

    replay("sim state only            ", False, False)
    replay("sim + sticky sim.data     ", False, True)
    replay("sim + controller          ", True, False)
    replay("sim + sticky + controller ", True, True)

    env.close()


if __name__ == "__main__":
    main()
