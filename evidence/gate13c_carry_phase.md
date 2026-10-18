# Gate 13C — strikes during the carry, not during the approach

**Question.** Gate 13B concluded that commitment cost does not compound with the replan horizon,
but its strikes all landed *before* the robot had picked anything up. This gate moves the strikes
into the carry phase, where the committed actions are actually doing work and stale ones are
harmful rather than merely wasted.

**Short answer.** Moving the strikes into the carry changes *whether* staleness costs anything, but
not *whether the cost scales with horizon*.

- **Object task, carry-phase strikes:** the intervention now bites — control 6/6 vs disturb 2/6 at
  H=1 (Fisher p=0.061) and 1/6 at H=10 (p=0.015). In the approach regime the same total drift cost
  exactly nothing.
- **But the horizon does not matter:** 2/6 vs 1/6, Fisher **p=1.000**. Forty stale actions do not
  fail more than four.

So commitment cost is gated by whether the stale actions are *load-bearing*, not by how many of them
there are. That is a sharper claim than Gate 13B could make, because it now has a regime where the
cost is real and still shows no horizon scaling.

Status: full run, 2 tasks x H in {1,10} x 2 seeds x 3 trials, n=6 per cell, 0.01 m strikes every 10
steps from the detected lift. Spatial is flat at both horizons; the object task carries the result.

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

## Result (`results/gate13_repeat_carry_full`, n=6 per cell)

Magnitude 0.01 m, strikes every 10 steps from the detected lift, count 4.

**libero_object t0 — the intervention now bites**

| H | control | disturb | cost | stale | steps | timeouts | Fisher vs control |
|---|---|---|---|---|---|---|---|
| 1 | 6/6 | 2/6 (0.33) | +0.67 | 4.0 | 343.0 | 4 | p=0.061 |
| 10 | 6/6 | 1/6 (0.17) | +0.83 | 40.0 | 400.3 | 5 | p=0.015 |

Horizon comparison, disturb H=1 vs H=10: **2/6 vs 1/6, Fisher p=1.000.** Ten times the stale
actions, one episode of difference.

**libero_spatial t0 — flat, and the carry window is why**

| H | control | disturb | cost | stale | steps |
|---|---|---|---|---|---|
| 1 | 6/6 | 6/6 | +0.00 | 2.0 | 106.3 |
| 10 | 6/6 | 6/6 | +0.00 | 13.2 | 102.2 |

Spatial's carry window is only ~30 steps, so at most 2-3 strikes fit and the displaced object stays
inside the gripper's reach. It is a weak version of the manipulation, not evidence of a horizon
effect.

**Pooled**

| H | control | disturb | cost | Fisher |
|---|---|---|---|---|
| 1 | 12/12 | 8/12 (0.67) | +0.33 | p=0.093 |
| 10 | 12/12 | 7/12 (0.58) | +0.42 | p=0.037 |

## The comparison that matters

| regime | strikes land | object disturb success | stale H1 -> H10 | horizon effect |
|---|---|---|---|---|
| approach (Gate 13B) | steps 40-70, pre-lift | 5/6 -> 6/6 | 4 -> 40 | none (p=1.0) |
| carry (this gate) | lift+10, post-lift | 2/6 -> 1/6 | 4 -> 40 | none (p=1.0) |

Same magnitude, same task, same stale count. The only change is *when* the strike lands, and it
moves the object task from "no cost at all" to "two-thirds of episodes fail". The horizon term is
flat in both.

That is the mechanism: a stale action only costs something if it was doing work. Approach actions
are recoverable by re-aiming; a carry action is holding the object. But once the grasp is broken the
episode is lost regardless of how many committed actions were invalidated, so the cost saturates at
the first strike instead of compounding with H.

The pilot (`results/gate13_repeat_carry2`) was spatial-only at n=3 and was flat, consistent with the
full run's spatial cells. It is kept as the run that validated the trigger, not as evidence.

## What this does and does not establish

- **Establishes:** the Gate 13B null was an artifact of *when* the strikes landed, not of the model.
  The same displacement, moved into the carry, takes the object task from 6/6 to 2/6 (H=1) and 1/6
  (H=10). So stale committed actions do cost real task success — but only when they are
  load-bearing.
- **Establishes:** even with a real cost on the table, the horizon term stays flat (2/6 vs 1/6,
  p=1.000). Forty stale actions fail no more often than four. The cost saturates at the first strike.
- **Does not establish:** that no horizon effect exists anywhere. n=6 cannot resolve 0.33 vs 0.17;
  a 0.16 difference needs roughly 150 episodes per arm. The claim is only that no horizon effect is
  visible at this power, in a regime where the cost itself is clearly visible.
- **Does not establish:** a mechanism for the saturation. "The grasp breaks on the first strike" is
  the natural reading of 2/6 -> 1/6, but the records do not label grasp state, so it is an
  inference, not a measurement.
- **Structural limit:** LIBERO spatial's carry window is ~30 steps, so at most 2-3 strikes fit at
  H=10 and the task never shows a cost. The object task's window is ~81 steps and does admit up to
  8, which is why it carries the result.

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
