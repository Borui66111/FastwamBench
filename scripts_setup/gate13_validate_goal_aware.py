#!/usr/bin/env python
"""[fastbench] Gate 13 validation: the disturbance must NOT satisfy the task.

Reproduces, without any model, the measurement that motivated the goal-aware
disturbance.  For each (suite, task) it prints the task's own goal predicate,
the auto-resolved manipulated body, the goal-away displacement, and the env's
success predicate before/after the displacement.  `post_iv_success` must be
False: if the disturbance satisfied the goal the episode would end at the
intervention step and zero stale actions would ever execute, which is exactly
the bug this script guards against.

Also replays the naive fixed delta ([+0.06,+0.06,0], the pre-fix default) to
show the contamination directly.

Writes: evidence/gate13_goal_aware_validation.txt
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

os.environ.setdefault("MUJOCO_GL", "egl")
ROOT = Path("/data1/liborui/fastwam_bench")
FW = ROOT / "FastWAM"
sys.path.insert(0, str(FW))
sys.path.insert(0, str(FW / "experiments" / "libero"))

from libero.libero import benchmark  # noqa: E402
from experiments.libero.libero_utils import get_libero_env  # noqa: E402
import experiments.libero.fastbench_intervention as F  # noqa: E402

TASKS = [("libero_spatial", 0), ("libero_object", 0)]
NAIVE_DELTA = [0.06, 0.06, 0.0]
MAG = 0.10


def main() -> int:
    lines = []
    def say(s=""):
        print(s)
        lines.append(s)

    say("GATE 13 goal-aware disturbance validation")
    say("=" * 78)
    say("Naive fixed delta under test: %s" % NAIVE_DELTA)
    say("Goal-away magnitude: %.2f m" % MAG)
    say()
    for suite, tid in TASKS:
        try:
            bs = benchmark.get_benchmark_dict()[suite]()
            task = bs.get_task(tid)
            env, desc = get_libero_env(task, 256, seed=1)
            env.reset()
            say("-" * 78)
            say("%s t%d: %s" % (suite, tid, desc))
            say("goal targets      : %s" % (F.resolve_goal_targets(env),))
            body = F.resolve_manipulated_body(env)
            say("auto-resolved body: %s" % body)
            if not body:
                say("!! could not resolve body")
                continue
            say("success at init   : %s" % F.check_success(env))
            d = F.goal_away_delta(env, body, MAG)
            say("goal-away delta   : %s" % (None if d is None else
                                           [round(x, 5) for x in d]))
            res, used, post, rej = F.apply_world_displacement(env, body, d, MAG, True)
            say("applied           : %s  delta_used=%s" % (
                res.get("applied"), None if used is None else [round(x, 5) for x in used]))
            say("POST_IV_SUCCESS   : %s   (MUST be False)" % post)
            say("rejected cands    : %s" % rej)
            snap = F.snapshot_state(env, body_names=[body])
            say("body pos after    : %s" % [round(x, 4) for x in snap["bodies"][body]["pos"]])
            # replay the naive delta against the live guard
            res2, used2, post2, rej2 = F.apply_world_displacement(
                env, body, NAIVE_DELTA, MAG, True)
            say("naive delta -> delta_used=%s post_iv_success=%s" % (
                None if used2 is None else [round(x, 5) for x in used2], post2))
            say("naive rejected    : %s" % rej2[:2])
            try:
                env.close()
            except Exception:
                pass
        except Exception:
            say("EXCEPTION:")
            say(traceback.format_exc())
    say("=" * 78)
    say("VALIDATION DONE")

    out = ROOT / "evidence" / "gate13_goal_aware_validation.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")
    print("wrote %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
