#!/usr/bin/env python
"""List the movable object bodies in a LIBERO scene (Gate 13 prep).

The Gate 9/11 world-displacement intervention targets a body by name
(`intervention_world_body`, e.g. `akita_black_bowl_1_main`). Before running the
paired Gate 13 experiment on a new suite/task we must know which bodies exist in
that scene and which of them have a free joint (i.e. are actually movable).

Usage:
    python scripts_setup/list_scene_bodies.py <suite> <task_id>

Requires the `fastbench` env and an EGL-capable GPU (a MuJoCo render context is
created), but no model weights are loaded, so it is very light.
"""
import sys

from libero.libero import benchmark

sys.path.insert(0, "/data1/liborui/fastwam_bench/FastWAM")
from experiments.libero.fastbench_intervention import (  # noqa: E402
    _free_joint_of_body,
    list_object_bodies,
)
from experiments.libero.libero_utils import get_libero_env  # noqa: E402


def main() -> int:
    suite_name, task_id = sys.argv[1], int(sys.argv[2])
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1

    suite = benchmark.get_benchmark_dict()[suite_name]()
    task = suite.get_task(task_id)
    env, desc = get_libero_env(task, 256, seed)
    env.reset()

    print(f"suite={suite_name} task_id={task_id}")
    print(f"description: {desc}")
    print(f"level: {getattr(task, 'level', None)}  bddl: {task.bddl_file}")
    print("\nmovable object bodies (free joint present => displaceable):")
    for body in list_object_bodies(env):
        jnt = _free_joint_of_body(env, body)
        mark = "MOVABLE" if jnt is not None else "fixed  "
        print(f"  [{mark}] {body}" + (f"  (joint {jnt})" if jnt is not None else ""))

    env.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
