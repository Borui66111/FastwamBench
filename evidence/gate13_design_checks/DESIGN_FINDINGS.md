# Gate 13 — intervention design findings (2026-10-17)

The headline experiment only measures what it claims to measure if the disturbance is
(a) **applied after the plan is committed** and (b) **not itself a task solution** and
(c) **not so large that no horizon can recover**. This file records the three checks
that established all three, plus the bug they exposed.

## Check 1 — the disturbance is applied AFTER the chunk is planned

`FastWAM/experiments/libero/eval_libero_single.py`:

```
547:  action_chunk, imgs, predicted_future_frames = _predict_action_chunk(...)
575:  pending_actions = [ensembler.get_action(ts)...] / pending_actions = action_chunk[:replan_steps]
614:  world_intervention = maybe_displace_world(env, icfg, current_replan_idx, step_t=t)
```

Line numbers are from the live file. The plan is produced at 547 and the world is
changed at 614, so the displacement always lands **after** the actions for this chunk
were committed. `use_action_ensembler: false` (configs/sim_libero.yaml:27), so
`pending_actions = action_chunk[:replan_steps]` is the pure fixed-horizon path —
staleness comes from the chunk, not from ensembling.

## Check 2 — the disturbance must not satisfy the task (contamination)

First canary used a fixed displacement of `[+0.06, +0.06, 0]` on `akita_black_bowl_1_main`
for `libero_spatial` t0 whose goal is `on(akita_black_bowl_1_main, plate_1)`. The plate
sits at **+x/+y**, so the "disturbance" teleported the bowl onto its target and the task
*instantly succeeded* at the intervention step (episode ended at t=world_step with
`success=True`, `stale_action_steps=1` instead of 10).

Raw evidence: `probe_goal_deltas.out` (the same displacement applied to the same
initial state; the `+0.06,+0.06` candidate is the only one flagged
`post_iv_success=True`, i.e. rejected).

**Fix:** the disturbance is now goal-aware — the manipulated body is resolved from the
task's own `env.parsed_problem` goal state, and the displacement is chosen along the
direction *away* from the goal target. Every candidate direction is validated against
the environment's own `_check_success()`; a candidate that satisfies the goal is
reverted and the next direction is tried. The chosen direction, magnitude, whether it
was goal-aware, and the rejected candidates are all written into the intervention
record, so a reviewer can audit the disturbance rather than trust it.

Raw evidence: `validate_goal_aware.out` (`post_iv_success=False` for both suites),
`test_gate9_intervention.out` (unit checks for the reject/revert/fallback path).

## Check 3 — a no-op disturbance must reproduce the control

An `intervention_world_magnitude=0.0` run must behave exactly like the control: same
success rate, no object displacement beyond the natural grasp-and-place. This is the
guard against "the disturb arm is broken" masquerading as "the model cannot recover".

Result (`noop_validation_summary.json`, `results/gate13_noop/`):

```
H1  disturb  1/1  rate 1.00  stale 1.0  obj_move 0.111
```

`obj_move 0.111` is the natural bowl-to-plate distance (0.117 m), i.e. the episode ran
normally and the model solved the task. **The disturb code path is sound.**

### Bug this check exposed (fixed)

`resolve_intervention_cfg` had `float(ev.get("intervention_world_magnitude", 0.10) or 0.10)`.
The `or 0.10` promoted a legitimate **0.0** to 0.10, so the no-op control was silently
running a 10 cm displacement and reported failure. Fixed to an explicit `None` test.
Same pattern fixed for `world_magnitude` on the resolved-config path.

## Check 4 — the displacement must be recoverable at the shortest horizon

A perturbation is only informative if *some* horizon can recover from it; otherwise the
cost saturates at 1.0 for every H and the sweep measures nothing.

Observed at `world_step=60` (bowl already grasped, z≈0.90): **no** horizon recovers, not
even H=1 (per-step replanning). Displacing a *held* object forces a full re-grasp, which
is a different and much harder problem than adapting a stale plan.

**Design decision:** intervene at `world_step=40` (during the approach, before the grasp)
and calibrate the magnitude downward (0.02–0.05 m) until H=1 recovers. H=1 recovering is
the precondition for the horizon sweep to be meaningful.

## What the headline experiment must show to be valid

1. `stale_action_steps == H` on the disturb arm (mechanism fires with the right duration).
2. `contaminated == 0` (no episode is "solved" by the disturbance).
3. control ≈ 1.0 at every H (the intervention is the only difference).
4. disturb success **decreasing** in H, and cost = control − disturb **increasing** in H.
5. H=1 disturb recovering (near control) — otherwise the floor effect invalidates the trend.
