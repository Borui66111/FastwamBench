#!/usr/bin/env python
"""[fastbench] Probe 3 — is `set_state_from_flattened` + `forward()` idempotent?

Probe 2 showed derived quantities (actuator_length, qfrc_damper, qacc) changing
after a restore-to-the-same-state even though qpos/qvel compared equal. That is
physically impossible unless the restore itself is not a no-op. This prints the
actual values (not just deltas) around repeated restores of the SAME flat state,
so the failure mode is visible rather than inferred.

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

FIELDS = ("qpos", "qvel", "actuator_length", "qfrc_damper", "qacc", "qacc_warmstart",
          "efc_b", "ncon", "time")


def show(tag, env):
    sim = find_sim(env).sim
    print(f"  {tag}")
    for f in FIELDS:
        v = np.asarray(getattr(sim.data, f, np.array([])), dtype=float)
        head = np.array2string(v[:4], precision=6, suppress_small=False) if v.ndim == 1 else str(v.shape)
        print(f"    {f:<16} shape={str(v.shape):<10} head={head}")


def main():
    env, task, desc = make_env("libero_object", 0, seed=0)
    init = load_init_states(task, 0)
    env.reset()
    env.set_init_state(init)
    acts = scripted_actions(60)
    for i in range(40):
        env.step(acts[i])

    sim = find_sim(env).sim
    flat = get_flat_state(env)
    print(f"flat state_dim={flat.size} nq={sim.model.nq} nv={sim.model.nv} na={sim.model.na}")
    print()

    show("A. live state after 40 steps", env)
    sim.set_state_from_flattened(np.asarray(flat, dtype=float))
    show("B. immediately after set_state_from_flattened (no forward)", env)
    sim.forward()
    show("C. after sim.forward()", env)
    sim.set_state_from_flattened(np.asarray(flat, dtype=float))
    sim.forward()
    show("D. after a SECOND restore+forward of the same flat state", env)
    sim.set_state_from_flattened(np.asarray(flat, dtype=float))
    sim.forward()
    show("E. after a THIRD restore+forward", env)

    # explicit numeric comparison A vs C
    print()
    print("A vs C (live vs restored):")
    a_qpos = np.array(flat[1:1 + sim.model.nq], dtype=float)
    c_qpos = np.array(sim.data.qpos, dtype=float)
    print(f"  flat qpos == sim qpos now : {np.array_equal(a_qpos, c_qpos)} "
          f"max|delta|={np.abs(a_qpos - c_qpos).max():.3e}")

    env.close()


if __name__ == "__main__":
    main()
