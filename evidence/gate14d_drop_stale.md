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
strike is applied, the rest of the executing chunk is discarded, so the controller must re-plan
against the mutated world before it acts again. Zero stale actions are executed.

Per-episode provenance is recorded: `dropped_stale_count` in the `episode_end` record, and
`dropped_stale` (how many actions were thrown away) in each `intervention` record.

## Predictions, written down before running

The claim under test: **the success cost is caused by executing stale actions**, not by the world
change per se.

- **P1 (primary).** Disturb success with stale execution dropped returns to the control level. Concretely:
  carry regime, 0.01 m, `libero_object:0`, H=1 and H=10, 6 episodes/cell — expect ≥5/6 in both
  disturb cells, against the 2/6 and 1/6 measured with stale execution.
- **P2 (mechanism check).** `dropped_stale_count > 0` in every struck episode, and `stale_action_steps`
  == 0. If the drop does not take effect, the run is void, not a negative result.
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
# canary: one episode, confirm dropped_stale_count > 0 and stale_action_steps == 0
python scripts_setup/gate13_run.py --tasks libero_object:0 --horizons 1 --seeds 1 --trials 1 \
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
