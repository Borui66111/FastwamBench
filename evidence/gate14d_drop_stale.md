# Gate 14D — the stale remainder does not carry the cost

STATUS: **COMPLETE (2026-10-19). The manipulation worked and the prediction failed.** Dropping 9 of 10
stale actions changed the outcome by nothing: 2/6 either way, with the same two episodes succeeding at
the same step counts. The predictions below were written before the run and are left as written.

## Result

Carry regime, `libero_object:0`, 0.01 m, H=10, **one** strike (grasp-relative, +0.02 m), n=6 per arm,
seeds 1–2 × trials 1–3:

| arm | stale actions executed | dropped | success | episode steps |
|---|---|---|---|---|
| full chunk (`g14keep1`) | 10 | 0 | **2/6** | 202, 169, 430, 430, 430, 430 |
| remainder dropped (`g14drop1`) | 1 | 9 | **2/6** | 203, 171, 430, 430, 430, 430 |

The two arms agree episode for episode, not just in aggregate: the same two episodes succeed, one step
apart, and the four failures all run to the 430-step cap in both. Fisher p=1.0000. Provenance is in the
records — `stale_action_steps` 10 vs 1, `dropped_stale_count` 0 vs 9 — so the manipulation provably
took effect; this is not a silent no-op.

**What that means.** The success cost is not proportional to stale execution. Reducing the number of
already-planned actions that run from ten to one leaves the outcome bit-for-bit unchanged, so the harm
is not done by "replaying a chunk planned against a world that no longer exists". It is done by the
displacement itself, plus at most the single action that was already committed when the strike landed.

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

**Outcome: the second row.** P1 failed, P2 held, P3 was untestable in the direction predicted (the
successful episodes are one step *longer* with the drop, 203 vs 202 and 171 vs 169 — noise, not a cost).
The stale-action attribution is retired; see "Consequences" below.

The second row is the one that would matter most, and it is a real possibility: in the approach
regime, `first_frame` failures at 800 steps ran to the full 830 without terminating, which is not
what "slow but recovering" looks like.

## Run plan (as executed)

```bash
# canary: one episode at H=10, where 9 of 10 actions are dropped
python scripts_setup/gate13_run.py --tasks libero_object:0 --horizons 10 --seeds 1 --trials 1 \
    --arms disturb --magnitude 0.01 --world-trigger-after-lift 0.02 \
    --world-repeat-every 10 --world-repeat-count 4 \
    --drop-stale-after-strike --tag g14dcanary --ngpu 1

# the two arms actually compared: one strike each, H=10, n=6
python scripts_setup/gate13_run.py --tasks libero_object:0 --horizons 10 --seeds 1,2 --trials 3 \
    --arms disturb --magnitude 0.01 --world-trigger-after-lift 0.02 \
    --world-repeat-every 10 --world-repeat-count 1 \
    --drop-stale-after-strike --tag g14drop1 --ngpu 1     # -> results/gate13_g14drop1
python scripts_setup/gate13_run.py --tasks libero_object:0 --horizons 10 --seeds 1,2 --trials 3 \
    --arms disturb --magnitude 0.01 --world-trigger-after-lift 0.02 \
    --world-repeat-every 10 --world-repeat-count 1 \
    --tag g14keep1 --ngpu 1                               # -> results/gate13_g14keep1
```

## Consequences — what has to change elsewhere

1. **README intro.** "a property of fixed-horizon chunk execution" is not supported by this
   manipulation and is being retired. The cost survives when the chunk is dropped, so it is a property
   of the *displacement*, not of replaying a stale plan.
2. **The horizon story.** Four strikes cost more than one (1/6 vs 2/6 at H=10), but one strike at H=10
   now costs the same as the four-strike H=1 cell (2/6). The horizon gradient measured in Gate 13 was
   therefore carried largely by *stale-action count* (4 vs 40) — which this experiment shows is inert.
   That makes the gradient's mechanism unexplained, and it must not be restated as "commitment compounds
   with horizon".
3. **What survives.** The 13D mechanism result is untouched: the grasp is never broken, the object is
   carried to the basket and held above it. That is a statement about *where* episodes fail, and it was
   measured directly, not inferred from stale execution.
4. **What is still unmeasured.** One committed action still runs in the drop arm, so this design cannot
   separate "the displacement alone" from "the displacement plus one in-flight action". A zero-stale
   arm needs the observation refreshed and the chunk re-queried at the strike, which the harness does
   not do today. That is the next experiment, and until it runs the attribution stops at "at most one
   action".

Both arms are disturb-only: the drop cannot affect a control episode (no strike fires, nothing to
discard), so re-running controls would add nothing. The control reference is the 6/6 measured in
`results/gate13_repeat_carry_full`.
