# Gate 14D — positive control for the mechanism (pre-registered)

STATUS: **designed and plumbed, canary pending.** No results in this file yet, on purpose: the
predictions below were written before the run.

## The gap this closes

Gates 13/13B/13C/13D/14 all share one inferential step. The intervention displaces the object, and
the controller then executes the remainder of a chunk that was planned against the old world. The
success drop is *attributed* to those stale actions — but nothing so far has removed stale execution
while keeping the world change. That is an inference, not a manipulation, and Gate 14 showed the cost
is not specific to a future-aware model, which makes the attribution more load-bearing, not less.

## The manipulation

`--drop-stale-after-strike` (harness: `EVALUATION.intervention_world_drop_stale=true`).

Same task, seeds, horizons, magnitude, trigger and strike schedule. The only difference: the moment a
strike is applied, the rest of the executing chunk is discarded, so the controller re-plans against the
mutated world instead of riding out the chunk.

**The exact semantics, which are weaker than "zero stale actions":** the strike fires after the chunk
is generated but before any of its actions run. Rather than clear the queue at that instant (which
crashed the canary — the loop pops this step's action immediately afterwards), the harness lets the
**one action already committed at the strike instant execute**, then drops everything after it. So
stale execution goes from *H actions to 1*, not to 0.

Consequence for the design: at **H=1 the remainder is empty and the control is a no-op by
construction** (1 → 1). **H=10 is the informative cell** (10 → 1). A drop-stale arm run at H=1 must
therefore not be read as a test of the hypothesis.

**A second design constraint, found by the canary.** Strikes are only checked at replan boundaries, and
`world_repeat_every=10` matches them against `delta_t % 10 == 0`. Dropping the chunk empties the queue
one step after the strike, so the replan cadence shifts to 100, 101, 111, 121, … — where `delta_t % 10`
is 1, 11, 21, never 0. **The repeat grid is never re-hit: a 4-strike drop arm fires exactly one strike.**
Comparing it to a 4-strike full-chunk arm would confound stale execution with strike count, so the
14D arms both use `--world-repeat-count 1` (one strike each) and the existing 4-strike data stays the
Gate 13 headline. The canary confirmed this: `strike_count=1`, `dropped_stale=9`, `stale_action_steps=1`.

Per-episode provenance is recorded: `dropped_stale_count` in the `episode_end` record, and
`dropped_stale` (how many actions were thrown away) in each `intervention` record.

## Predictions, written down before running

The claim under test: **the success cost is caused by executing stale actions**, not by the world
change per se.

- **P1 (primary).** Disturb success with the stale remainder dropped returns toward the control level.
  Concretely: carry regime, 0.01 m, `libero_object:0`, **H=10**, **one strike** (`--world-repeat-count
  1`), 6 episodes/cell, drop vs no-drop — expect drop ≥ 5/6 against no-drop. At H=1 there is nothing to
  drop, so that cell is reported as a no-op control rather than as evidence either way.
- **P2 (mechanism check).** `dropped_stale_count > 0` in every struck episode at H=10, and
  `stale_action_steps` == 1 (one committed action still runs). If the drop does not take effect, the
  run is void, not a negative result.
- **P3 (secondary).** Episodes get *longer* rather than shorter — extra re-planning costs inference
  time, and the model now re-plans at strike boundaries it previously rode through.

## What each outcome would mean

| outcome | reading |
|---|---|
| P1 holds (disturb ≈ control) | stale execution is **causal**; the "fixed-horizon chunk execution" framing in the README is directly supported rather than inferred |
| P1 fails (disturb still ~2/6) | the world change alone damages the episode even when the controller immediately re-plans; the stale-action attribution is **wrong or incomplete**, and every "stale execution" sentence in README/STATE/evidence must be rewritten |
| P2 fails | harness bug; nothing is learned |

The second row is the one that would matter most, and it is a real possibility: in the approach
regime, `first_frame` failures at 800 steps ran to the full 830 without terminating, which is not
what "slow but recovering" looks like.

## Run plan

```bash
# canary: one episode at H=10, where 9 of 10 actions are dropped
python scripts_setup/gate13_run.py --tasks libero_object:0 --horizons 10 --seeds 1 --trials 1 \
    --arms disturb --magnitude 0.01 --world-trigger-after-lift 0.02 \
    --world-repeat-every 10 --world-repeat-count 4 \
    --drop-stale-after-strike --tag g14dcanary --ngpu 1

# full: same cells as the Gate 14 carry comparison, so the numbers are directly comparable
python scripts_setup/gate13_run.py --tasks libero_object:0 --horizons 1,10 --seeds 1,2 --trials 3 \
    --arms control,disturb --magnitude 0.01 --world-trigger-after-lift 0.02 \
    --world-repeat-every 10 --world-repeat-count 4 \
    --drop-stale-after-strike --tag g14ddrop --ngpu 2
```

Controls are included in the full run even though the drop cannot affect them: they are the reference
the disturb cells are compared against, and re-measuring them costs little.
