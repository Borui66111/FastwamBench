# Gate 13C — strikes during the carry, not during the approach

**Question.** Gate 13B concluded that commitment cost does not compound with the replan horizon,
but its strikes all landed *before* the robot had picked anything up. This gate moves the strikes
into the carry phase, where the committed actions are actually doing work and stale ones are
harmful rather than merely wasted.

**Short answer.** The trigger now lands every strike during the carry, staleness rises ~7x with
horizon (1.7 -> 12.3 stale actions), and the task cost is still **+0.00 at both horizons**. The
carry regime agrees with the approach regime.

Status: canary (1 task, 1 seed, 3 trials, n=3/cell). A 2-task n=6/cell run is in flight; numbers
below are replaced when it lands. n=3 only excludes a *large* cost.

---

## Why the old design could not test this

Gate 13B scheduled strikes at absolute env steps 40/50/60/70. Reconstructing the lift time of every
episode from `state.bodies` in the raw records showed that **24 of 24 struck episodes had all
strikes land before the object was first lifted**:

| task | lift step range | strike steps | strikes that landed after the lift |
|---|---|---|---|
| libero_spatial t0 | 54-84 | 40/50/60/70 | 0 of 24 |
| libero_object t0 | 133-161 | 40/50/60/70 | 0 of 24 |

So in Gate 13B, a stale action was always a stale *approach* action: the robot re-aims and nothing
is at risk. That is the wrong regime for the H3 claim, and it is the most likely reason the cost was
flat.

An absolute step cannot fix this, because the carry phase starts at a different step in every
episode:

| task | lift (range) | carry window (end - lift) | strikes that fit at H=10 |
|---|---|---|---|
| libero_spatial t0 | 54-84 | 3 / **30** / 34 (min/med/max) | 1-3 |
| libero_object t0 | 133-161 | 71 / **81** / 125 | up to 8 |

This matters for the design: the spatial carry window is too short to accumulate strikes, but the
object task's is long enough to test real compounding during the carry. That is why the full run
below covers both tasks rather than spatial alone.

## The fix: time the strikes from the detected lift

New config key `intervention_world_trigger_after_lift` (CLI `--world-trigger-after-lift 0.02`):

1. On each episode, latch the object's resting height `_body_z0` on the first call.
2. When the object's height exceeds `_body_z0 + threshold`, latch `_lift_step`.
3. Schedule strikes at `_lift_step + every`, `+2*every`, ... instead of from an absolute step.

The anchor is latched once per episode and never drifts, so a later call still measures from the
lift. `icfg` is rebuilt inside `run_single_episode`, so no state leaks between trials.

Two plumbing details that matter, both now covered by tests:

- The runner must reject a horizon that does not divide the repeat interval. With lift-relative
  timing the interval — not `world_step` — has to sit on a chunk boundary, or the strike is never
  reached.
- The key must be mapped out of `cfg.EVALUATION` inside `resolve_intervention_cfg`. The first carry
  canary (`results/gate13_repeat_carry`) silently ignored the flag for exactly this reason: strikes
  stayed at [40, 50, 60, 70] and every one landed pre-grasp. **That run is invalid and is not
  cited.** A plumbing assertion now fails loudly if the mapping is missing.

## Result (canary, `results/gate13_repeat_carry2`)

libero_spatial t0, magnitude 0.01 m, strikes every 10 steps from the lift, count 4:

| H | success | stale actions | iv_step | steps | cost |
|---|---|---|---|---|---|
| 1 | 3/3 | 1.7 | 97 | 103.3 | +0.00 |
| 10 | 3/3 | 12.3 | 97 | 101.3 | +0.00 |

Per episode, every strike is post-lift:

```
ep  succ  steps  lift  strike steps   post-lift
0   True     98    78  [89]                 1
1   True    101    80  [91, 101]            2
2   True    111    81  [92, 102]            2
```

Only 1-2 strikes land, because the carry window is ~20-30 steps and H=10 requires the repeat
interval to be a multiple of 10. That caps the achievable staleness contrast at ~7x rather than the
10x of Gate 13B. Staleness still differs clearly (1.7 vs 12.3) and the outcome does not move.

## What this does and does not establish

- **Establishes:** the negative result is not an artifact of striking during the approach. Move the
  strikes into the carry, where stale actions are actively wrong, and the cost is still zero at
  n=3/cell.
- **Does not establish:** that no magnitude produces a horizon effect. At 0.01 m the robot simply
  re-grips; a larger displacement during the carry would likely drop the object and fail at *both*
  horizons, which is a ceiling rather than a trend.
- **Structural limit:** in LIBERO spatial the carry phase is ~30 steps, so at most 2-3 strikes fit at
  H=10. The object task's carry phase is ~81 steps and does admit up to 8, which is what the full
  run measures.

## Reproduce

```
PY=/data1/liborui/.conda/envs/fastbench/bin/python
$PY scripts_setup/test_gate9_intervention.py          # 96 checks
$PY scripts_setup/gate13_run.py \
  --tasks libero_spatial:0,libero_object:0 --horizons 1,10 --seeds 1,2 --trials 3 \
  --arms control,disturb --magnitude 0.01 --world-step 40 \
  --world-repeat-every 10 --world-repeat-count 4 \
  --world-trigger-after-lift 0.02 --tag repeat_carry_full --ngpu 2
$PY scripts_setup/gate13_analyze.py results/gate13_repeat_carry_full
```

The analyzer prints a phase audit (`STRIKES ALL LANDED BEFORE THE GRASP`) whenever a run intended to
test the carry fails to reach it, so this mistake cannot recur silently.
