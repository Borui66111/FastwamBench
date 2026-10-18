#!/usr/bin/env python
"""[fastbench] Probe 2 — which sim.data field does a state restore fail to reproduce?

Probe 1 established: `set_state_from_flattened(flat)` + `sim.forward()` restores
qpos exactly (|dqpos| = 0) yet the NEXT `mj_step` diverges by ~1e-3 rad.

Two candidate causes, and this probe separates them:

  (a) the restore is lossy — some `sim.data` field is left stale by
      `set_state_from_flattened` + `forward()`. Diagnosed by diffing EVERY
      numeric `sim.data` field immediately before and immediately after a
      restore-to-the-same-state. Anything non-zero is a field the restore
      does not reproduce.

  (b) the simulator itself is not reproducible across process/env instances —
      which would make Gate 14A impossible regardless of restore quality.
      Diagnosed by building a SECOND env and replaying the identical action
      sequence from the identical init state, then comparing qpos at each step.

Run from FastWAM/ with MUJOCO_GL=egl.
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "FastWAM"))
sys.path.insert(0, str(ROOT / "scripts_setup"))

from gate14a_snapshot_smoke import (  # noqa: E402
    find_sim, get_flat_state, load_init_states, make_env, scripted_actions,
)


def simdata_fields(env):
    """Every numeric array on sim.data, keyed by name."""
    sim = find_sim(env).sim
    out = {}
    for name in dir(sim.data):
        if name.startswith("_"):
            continue
        try:
            v = getattr(sim.data, name)
        except Exception:
            continue
        if isinstance(v, np.ndarray) and v.dtype.kind in "fiu":
            out[name] = np.array(v, copy=True)
        elif isinstance(v, (int, float, np.floating, np.integer)):
            out[name] = np.array(v, copy=True)
    return out


def diff_fields(a, b, tol=0.0):
    rows = []
    for k in sorted(set(a) & set(b)):
        try:
            x, y = np.asarray(a[k], dtype=float), np.asarray(b[k], dtype=float)
        except Exception:
            continue
        if x.shape != y.shape:
            rows.append((k, float("inf"), "shape"))
            continue
        d = float(np.abs(x - y).max()) if x.size else 0.0
        if d > tol:
            rows.append((k, d, str(x.shape)))
    return sorted(rows, key=lambda r: -r[1])


def main():
    env, task, desc = make_env("libero_object", 0, seed=0)
    init = load_init_states(task, 0)
    env.reset()
    obs = env.set_init_state(init)
    acts = scripted_actions(80)
    for i in range(40):
        obs, _, _, _ = env.step(acts[i])

    flat = get_flat_state(env)
    before = simdata_fields(env)

    # --- (a) restore-to-same-state, then diff every sim.data field ----------
    sim = find_sim(env).sim
    sim.set_state_from_flattened(np.asarray(flat, dtype=float))
    after_raw = simdata_fields(env)          # before forward()
    sim.forward()
    after_fwd = simdata_fields(env)          # after forward()

    print("## (a) sim.data fields changed by the restore itself")
    print("    [set_state_from_flattened, BEFORE forward()]")
    for k, d, sh in diff_fields(before, after_raw):
        print(f"      {k:<20} max|delta|={d:.3e}  shape={sh}")
    print("    [same, AFTER forward()]  <- what the next mj_step will actually see")
    for k, d, sh in diff_fields(before, after_fwd):
        print(f"      {k:<20} max|delta|={d:.3e}  shape={sh}")
    print()

    # --- (b) cross-instance reproducibility of the simulator itself ---------
    print("## (b) simulator reproducibility: replay the same actions in a fresh env")
    env2, task2, _ = make_env("libero_object", 0, seed=0)
    init2 = load_init_states(task2, 0)
    env2.reset()
    env2.set_init_state(init2)
    sim2 = find_sim(env2).sim
    for i in range(40):
        env2.step(acts[i])
    d_restart = float(np.abs(np.array(sim2.data.qpos) - np.array(before["qpos"])).max())
    print(f"    qpos after 40 identical steps in a 2nd env: max|delta|={d_restart:.3e}")
    for i in range(40, 45):
        env.step(acts[i])
        env2.step(acts[i])
        d = float(np.abs(np.array(find_sim(env).sim.data.qpos)
                         - np.array(sim2.data.qpos)).max())
        print(f"    step {i}: max|dqpos| between env1 and env2 = {d:.3e}")

    env.close()
    env2.close()


if __name__ == "__main__":
    main()
