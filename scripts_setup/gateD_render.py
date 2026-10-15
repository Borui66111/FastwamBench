#!/usr/bin/env python
"""Gate D: prove LIBERO-Safety envs run headless on this host.

Renders suite=obstacle_avoidance level=0 task 0 at the init state and after a
few no-op steps, and writes a side-by-side PNG (agentview | wrist).
Run with the fastbench python and MUJOCO_GL=egl.
"""
import os
import pathlib
import warnings

warnings.filterwarnings("ignore")
os.environ.setdefault("MUJOCO_GL", "egl")

import numpy as np
from PIL import Image, ImageDraw

from libero.libero import benchmark, get_libero_path
from libero.libero.envs import OffScreenRenderEnv

SUITE = "obstacle_avoidance"
LEVEL = 0
LEVEL_ID = 0
OUT = pathlib.Path("/data1/liborui/fastwam_bench/results/gateD_render")
OUT.mkdir(parents=True, exist_ok=True)


def main() -> int:
    bm = benchmark.get_benchmark_dict()[SUITE]()
    task = bm.get_task_by_level_id(LEVEL, LEVEL_ID)
    assert task is not None
    bddl = pathlib.Path(get_libero_path("bddl_files")) / task.problem_folder / f"L{task.level}" / task.bddl_file
    init_states = bm.get_task_init_states_by_level_id(LEVEL, LEVEL_ID)
    print(f"task      : {task.name}")
    print(f"language  : {task.language}")
    print(f"bddl      : {bddl}  exists={bddl.exists()}")
    print(f"init      : {len(init_states)} states, dim={len(init_states[0])}")

    env = OffScreenRenderEnv(bddl_file_name=str(bddl), camera_heights=256, camera_widths=256)
    env.seed(0)
    env.reset()
    obs = env.set_init_state(init_states[0])

    def frame(o):
        a = np.ascontiguousarray(o["agentview_image"][::-1, ::-1])
        w = np.ascontiguousarray(o["robot0_eye_in_hand_image"][::-1, ::-1])
        return a, w

    a0, w0 = frame(obs)
    for _ in range(10):
        obs, _, _, _ = env.step([0.0] * 7)
    a1, w1 = frame(obs)

    row0 = np.concatenate([a0, w0], axis=1)
    row1 = np.concatenate([a1, w1], axis=1)
    grid = np.concatenate([row0, row1], axis=0)
    img = Image.fromarray(grid.astype(np.uint8))
    d = ImageDraw.Draw(img)
    d.text((6, 6), "init", fill=(255, 255, 0))
    d.text((6, 262), "after 10 noop", fill=(255, 255, 0))
    p = OUT / f"{SUITE}_L{LEVEL}_{LEVEL_ID}.png"
    img.save(p)

    # object/joint introspection for later intervention work
    print("\n-- sim introspection --")
    print("nq/nv      :", env.sim.model.nq, env.sim.model.nv)
    names = [env.sim.model.joint_id2name(j) for j in range(env.sim.model.njnt)]
    print("joints[:15]:", names[:15])
    print("n bodies   :", env.sim.model.nbody)
    body_names = [env.sim.model.body_id2name(b) for b in range(env.sim.model.nbody)]
    interesting = [b for b in body_names if any(k in b for k in ("bowl", "plate", "stove", "bottle", "perfume"))]
    print("safety bodies:", interesting)
    for b in interesting:
        bid = env.sim.model.body_name2id(b)
        print(f"   {b:45s} pos={np.round(env.sim.data.body_xpos[bid], 4)}")
    env.close()
    print(f"\nPNG written: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
