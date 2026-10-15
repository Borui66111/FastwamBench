"""[fastbench] Gate 9 §9.1 hard gate: inspect the target task's objects/joints.

Prints, for the configured task: object body names, joint types, qpos structure,
success predicate availability, and proves a one-shot displacement round-trips.

Run:
  MUJOCO_GL=egl DIFFSYNTH_MODEL_BASE_PATH=... python scripts_setup/gate9_probe_objects.py
"""
import os
import sys

sys.path.insert(0, "/data1/liborui/fastwam_bench/FastWAM")

import numpy as np  # noqa: E402

from experiments.libero.fastbench_intervention import (  # noqa: E402
    displace_object,
    list_object_bodies,
    snapshot_state,
)
from experiments.libero.libero_utils import get_libero_env  # noqa: E402

SUITE = os.environ.get("FB_SUITE", "obstacle_avoidance")
TASK_ID = int(os.environ.get("FB_TASK_ID", "0"))
LEVEL = int(os.environ.get("FB_LEVEL", "0"))

print(f"=== task inspection: suite={SUITE} level={LEVEL} task_id={TASK_ID} ===")

from libero.libero import benchmark  # noqa: E402

bench = benchmark.get_benchmark_dict()[SUITE]()
task = bench.get_task_by_level_id(LEVEL, TASK_ID)
print("language     :", task.language)
print("bddl_file    :", getattr(task, "bddl_file", None))
_init = getattr(task, "initial_states", None)
print("init_states  :", None if _init is None else np.asarray(_init).shape)

env, desc = get_libero_env(task, 224, seed=0)
print("description  :", desc)

base = env
while getattr(base, "env", None) is not None and hasattr(base.env, "sim"):
    base = base.env
sim = base.sim
print("sim model nq :", sim.model.nq, " nbody:", sim.model.nbody, " njnt:", sim.model.njnt)

print("\n-- all bodies --")
for i, n in enumerate(sim.model.body_names):
    jadr, jnum = int(sim.model.body_jntadr[i]), int(sim.model.body_jntnum[i])
    types = [int(sim.model.jnt_type[j]) for j in range(jadr, jadr + jnum)]
    print(f"  [{i:3d}] {n:45s} jntnum={jnum} types={types}")

print("\n-- movable object candidates (free joint, type 0) --")
objs = list_object_bodies(env)
free = []
for b in objs:
    jadr = int(sim.model.body_jntadr[sim.model.body_name2id(b)])
    jnum = int(sim.model.body_jntnum[sim.model.body_name2id(b)])
    ts = [int(sim.model.jnt_type[j]) for j in range(jadr, jadr + jnum)]
    if 0 in ts:
        free.append(b)
        print(f"  FREE-JOINT OBJECT: {b}  (jnt types={ts})")
if not free:
    print("  (none found)")

print("\n-- joint names for free objects --")
for b in free:
    bid = sim.model.body_name2id(b)
    jadr = int(sim.model.body_jntadr[bid])
    for j in range(jadr, jadr + int(sim.model.body_jntnum[bid])):
        print(f"  {b}: joint[{j}] name={sim.model.joint_id2name(j)!r} type={int(sim.model.jnt_type[j])} qposadr={int(sim.model.jnt_qposadr[j])}")

print("\n-- success predicate available? --")
for attr in ("check_success", "_check_success"):
    for target, label in ((env, "wrapper"), (base, "base")):
        if hasattr(target, attr):
            print(f"  {label}.{attr}: present")
print("  current success:", env.check_success())

print("\n-- snapshot before --")
snap0 = snapshot_state(env, body_names=free[:3])
print("  eef:", None if snap0["eef"] is None else {k: (np.round(v, 4).tolist() if k == "pos" else v) for k, v in snap0["eef"].items() if k != "quat"})
for b, r in snap0["bodies"].items():
    print(f"  {b}: pos={np.round(r.get('pos', []), 4).tolist()} qpos={None if 'qpos' not in r else np.round(r['qpos'], 4).tolist()}")

if free:
    target = free[0]
    delta = [0.05, 0.0, 0.0]
    res = displace_object(env, target, delta)
    print(f"\n-- displacement test on {target} delta={delta} --")
    print("  applied:", res.get("applied"), "reason:", res.get("reason"))
    if res.get("applied"):
        b0 = np.asarray(res["qpos_before"][:3])
        b1 = np.asarray(res["qpos_after"][:3])
        print("  qpos_before[:3]:", np.round(b0, 4).tolist())
        print("  qpos_after [:3]:", np.round(b1, 4).tolist())
        print("  actual delta   :", np.round(b1 - b0, 4).tolist())
        snap1 = snapshot_state(env, body_names=[target])
        print("  body pos after :", np.round(snap1["bodies"][target]["pos"], 4).tolist())
        ok = np.allclose(b1 - b0, delta, atol=1e-4)
        print("  ROUND-TRIP OK  :", ok)

print("\n=== inspection done ===")
