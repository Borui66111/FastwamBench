# Gate 13 design checks — why the disturbance is goal-aware

Raw, re-runnable evidence that the Gate 13 disturbance is valid. All three files were
produced by real runs on this machine; the commands are at the bottom.

## The flaw that was found (and fixed) on 2026-10-17

The first Gate 13 canary fired the world displacement at absolute step 60 and reported

```
control : 2/2 success, stale=0
disturb : 2/2 success, stale=1     <-- wrong
```

`stale` should have been 10 (= H). Investigation of the raw episode records showed both
disturbed episodes ended at **exactly t = 60**, the intervention step: `env.step()` returned
`done = True` on the very first step after the teleport.

Root cause (`probe_goal_deltas.out`): the displacement was a fixed `[+0.06, +0.06, 0]`, and for
`libero_spatial` t0 the goal is `on(akita_black_bowl_1, plate_1)` with the plate at **+x, +y**
relative to the bowl. The teleport therefore *placed the bowl on the plate*:

```
delta [0.06, 0.06, 0] -> post_iv_success = True    CONTAMINATED
delta [0.08, 0.0,  0] -> post_iv_success = True    CONTAMINATED
delta [-0.06,-0.06, 0] -> post_iv_success = False
delta [0.0,  0.0,  0] -> post_iv_success = False
```

A disturbance that satisfies the task is not a disturbance: the episode ends before any stale
action executes, and the "commitment cost" is unmeasurable.

## The fix

`fastbench_intervention.py` now resolves the disturbance from the task's own goal state:

1. `resolve_goal_targets()` parses `env.parsed_problem["goal_state"]`
   (e.g. `[["on", "akita_black_bowl_1", "plate_1"]]`).
2. `resolve_manipulated_body()` maps the goal object onto its sim body
   (`akita_black_bowl_1` -> `akita_black_bowl_1_main`).
3. `goal_away_delta()` returns a displacement pointing **directly away from the goal target**,
   so the object-to-goal distance can only increase and `on`/`in` cannot become true.
4. `apply_world_displacement()` evaluates the env's own `_check_success()` immediately after the
   teleport. If a candidate nevertheless satisfies the goal it is **reverted** and the next
   candidate direction is tried; the outcome is recorded as `post_iv_success` and any rejected
   candidate is kept in the record as `rejected_candidates`.

`validate_goal_aware.out` shows the fixed behaviour with no model in the loop:

```
libero_spatial t0  body=akita_black_bowl_1_main  delta=[-0.0999, -0.0027, 0.0]  post_iv_success=False
libero_object  t0  body=alphabet_soup_1_main     delta=[-0.02,  -0.098,  0.0]  post_iv_success=False
```

The corrected canary then behaved as designed:

```
libero_spatial t0  H=10  control 2/2 (1.00)   disturb 0/2 (0.00)  stale=10  contaminated=0
libero_object  t0  H=10  control 2/2 (1.00)   disturb 1/2 (0.50)  stale=10  contaminated=0
```

`stale=10 == H` confirms the mechanism: after the world change the model still executed the
full remaining chunk that had been planned for the pre-change world.

## Files

| file | what it is |
|---|---|
| `probe_goal_deltas.out` | raw env probe: which displacement directions satisfy the goal (no model) |
| `validate_goal_aware.out` | raw validation of the goal-aware disturbance (no model) |
| `test_gate9_intervention.out` | 67 unit checks, incl. the guard's reject/revert/fallback path |

## Reproduce

```bash
cd /data1/liborui/fastwam_bench
MUJOCO_GL=egl python scripts_setup/gate13_validate_goal_aware.py
PYTHONPATH=FastWAM python scripts_setup/test_gate9_intervention.py
```
