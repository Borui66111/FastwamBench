# Gate 13B — does commitment cost compound when the world changes repeatedly?

**Short answer: no — but only for strikes that land during the approach.** With 10x more stale
actions and identical total world drift, task success does not worsen with horizon (the one visible
difference runs the other way) and effort differences are inside noise.

**Scope limit, measured after the fact:** in **24 of 24** struck episodes every strike fired *before
the object was first lifted* (first lift at step 54–295; strikes fixed at 40/50/60/70). Stale actions
in the approach phase are merely wasted — the policy re-approaches and nothing is at risk. So this
run does not test the regime where staleness could actually hurt: executing wrong actions *while
carrying the object*. It is evidence that approach-phase staleness is free, not that commitment cost
is absent. See "The strikes never landed during the carry" below.

## Why a single strike was not enough

Gate 13 displaced the object once. A single strike can invalidate at most H actions, once, and
re-acquisition then absorbs it — so a horizon effect had no room to appear. If the cost of
commitment is real, repeated strikes should compound: every strike leaves a fresh H stale actions,
so H=10 accumulates 10x the blind execution of H=1.

## Design

| parameter | value |
|---|---|
| strikes | 4, at absolute steps 40, 50, 60, 70 |
| magnitude | 0.01 m per strike (total drift 0.04 m) |
| drift budget | 0.25 m from the first strike (non-binding here) |
| direction | always away from the goal; never toward it |
| tasks | `libero_spatial` t0, `libero_object` t0 |
| arms | control / disturb, same seed, same initial state |
| n | 6 per cell (2 seeds x 3 trials), 48 episodes |

Magnitude was chosen to be **sub-threshold per strike**: a single 0.02 m displacement is absorbed
at every horizon (20/20), while 0.03 m breaks the object task. Four 0.01 m strikes therefore test
accumulation rather than one large shock.

## Measured staleness

| task | H | stale actions | ratio |
|---|---|---|---|
| spatial | 1 | 3.3 | — |
| spatial | 10 | 32.7 | 9.9x |
| object | 1 | 4.0 | — |
| object | 10 | 40.0 | 10.0x |

The manipulation worked: H=10 executed an order of magnitude more actions against a world that had
already moved. `strike_count` shows a mean of 3.3 (H=1) and 4.0 (H=10) strikes out of 4 requested —
so the H=10 arm landed every strike, and the H=1 arm landed all four in most but not all episodes
(an episode ends early on success, before the later strike steps are reached).

## Result

| task | H | control | disturb | step cost |
|---|---|---|---|---|
| object | 1 | 6/6, 178.7 steps | 5/6, 268.0 | +89.3 |
| object | 10 | 6/6, 164.3 steps | 6/6, 297.3 | +133.0 |
| spatial | 1 | 6/6, 107.5 steps | 6/6, 94.5 | -13.0 |
| spatial | 10 | 6/6, 103.8 steps | 6/6, 137.3 | +33.5 |

- **Success:** object 5/6 (H1) vs 6/6 (H10), Fisher exact p=1.0. Spatial 6/6 vs 6/6. No horizon effect; if anything H=10 is nominally better.
- **Effort:** H10 minus H1 steps, Welch t-test — object t=-0.67, df=9.7, p=0.52 (268.0 vs 297.3 steps); spatial t=-1.04, df=5.9, p=0.34 (94.5 vs 137.3). The point estimates lean the expected way (+133 vs +89; +33.5 vs -13) but with n=6 and sd 29-96 the data cannot separate them from noise.

The strikes do cost something: on the object task they add 89-133 steps of re-approach. They do not
cost success, and the size of that cost does not depend on how long the commitment was.

## Three failure modes found here

All were caught by looking at the data rather than trusting the harness.

1. **Mirrored strikes made the task easier.** The first version alternated strike direction, so odd
   strikes pushed the object *toward* the goal. Struck episodes then finished in 51 steps against
   ~100 for control. Fixed: every strike now moves the object away, with a regression test asserting
   the invariant.
2. **The repeat cap silently blocked the repeats.** The cap was an absolute goal distance (0.25 m),
   but the object starts ~0.1-0.2 m from the goal, so after one strike the cap tripped and later
   strikes were skipped: measured stale was 1.0 instead of 4. Fixed: the cap is now a drift budget
   measured from the object's distance at the first strike. A test pins the new semantics.
3. **A silently dead arm was undetectable.** In `results/gate13_repeat05_canary` the
   `libero_object_t0/H1/disturb` arm recorded `strike_count=0` on every episode, and its step counts
   (186, 164, 222) are byte-identical to the control arm's. That cell is not a disturbed arm — it is
   a second copy of control, and comparing the two would report a clean cost of exactly zero for a
   manipulation that never happened. Every episode completed normally, so an episode count cannot
   detect this. `gate13_analyze.py` now reads `strike_count` and prints an `INTERVENTION NEVER
   FIRED` block for any disturb cell where it is 0 in every episode.

   In both runs that exhibit this, the underlying cause is failure mode 2 at full severity: the
   absolute cap was already exceeded on the object geometry, so even the first strike was skipped
   (spatial, with more room, got 1-3 of 4). It is listed separately because the *detection* gap is
   independent of the cause — an unresolvable manipulation target would produce the same silent
   zero-strike arm, and nothing in the harness would have said so.

`results/gate13_repeat05_canary` is invalid on two counts (failure modes 1 and 2) and is not cited
anywhere; it is retained only as the capture that exposed them.

The earlier 0.05 m run (`results/gate13_repeat05`) is also superseded, but its two tasks fail in
*different* ways — verified per episode from `records.jsonl`, not from the summary:

| cell | strikes per episode | stale (mean) | outcome |
|---|---|---|---|
| object H1 | 0,0,0,0,0,0 | 0.0 | 6/6 success — 0 strikes, cap fully binding |
| object H10 | 0,0,0,0,0,0 | 0.0 | 6/6 success — 0 strikes, cap fully binding |
| spatial H1 | 1,3,2,1,3,2 | 2.0 | 0/6, every episode 430 steps, 6 timeouts |
| spatial H10 | 1,3,2,1,3,2 | 20.0 | 0/6, every episode 430 steps, 6 timeouts |

At 0.05 m the displacement is above the recovery threshold: the spatial task is destroyed at *both*
horizons, so the cost is +1.00 at H1 and +1.00 at H10 — flat, but flat at the ceiling, where no
compounding could ever be visible. The object task never fired at all. Neither task is a
single-strike replication; an earlier version of this document claimed that, and it was wrong.

Two further defects in the same run: only 1-3 of the 4 strikes landed even in the spatial cells (the
absolute-distance cap, mode 2), and `libero_object_t0/H1/control` has 3 episodes instead of 6.
`gate13_analyze.py` now reports all three conditions on this run (`INTERVENTION NEVER FIRED`,
`INCOMPLETE CELLS`, and `cost vs horizon: FLAT`).

## The strikes never landed during the carry

> **Follow-up:** this limitation was tested in Gate 13C
> (`evidence/gate13c_carry_phase.md`) by timing the strikes from the detected lift. Moving them into
> the carry makes the cost real on the object task — 6/6 -> 2/6 at H=1 and 1/6 at H=10 — while the
> horizon term stays flat (p=1.000). So the null below is about *approach-phase* staleness, and
> Gate 13C supplies the missing regime.

This is the most important qualification in this document, and it was found after the result was
first written up. The strike times are absolute (steps 40/50/60/70). The object is not lifted until
much later. Reconstructing per-episode lift time from `state.bodies` in the raw records:

  task            H   episodes   strikes before first lift   lift step range
  libero_object   1     6                6/6                   121 - 295
  libero_object   10    6                6/6                   121 - 295
  libero_spatial  1     6                6/6                    54 - 114
  libero_spatial  10    6                6/6                    54 - 114

**24 of 24 struck episodes had every strike land before the object was ever lifted.** A representative
spatial episode: the bowl sits at z = 0.8984 from t=30 through t=70 (all four strikes), first rising
to 0.9214 at t=80, while the gripper closes from 0.376 m to 0.049 m away.

So every stale action in this experiment was an *approach* action. Invalidating an approach action is
usually recoverable: the robot re-approaches from wherever it is. **But not always, and the exception
is diagnostic.** The single object H=1 failure in this run never lifted the object at all
(`lift=None` in the per-step records) — the displacement left it out of reach and the episode burned
the 430-step cap without a grasp. That is a *reach* failure, not a stale-carry failure, and it is the
only way an approach-phase strike can lose an episode here. The regime where a stale action is
actively harmful — committing to a carry trajectory after the object has been displaced out of the
gripper — was never entered.

This does not weaken the measurement, it bounds it. What the data shows is that 10x more stale
approach actions cost nothing, which is a real and useful fact about this harness. It does not show
that commitment cost never compounds; that question needs a strike that fires on grasp detection
rather than at a fixed step, which is a small code change (trigger on object lift) rather than a flag.
`gate13_analyze.py` now reports this automatically as `STRIKES LANDED BEFORE THE GRASP`.

## A fourth design limit: strikes cannot land inside a chunk

The hook that applies a strike runs only at chunk boundaries — the comment at its call site says
"after the chunk exists but before any of its actions run". So the strike cadence is quantised by
`replan_steps`, and a cadence finer than the replan period does not do what it looks like it does.

`results/gate13_repeat_fast` (object t0, `--world-repeat-every 5`, 0.01 m, n=3/cell) was run to test
exactly this: strikes at 40/45/50/55 so that the H=10 chunk spanning 40-49 would be invalidated
twice mid-execution. That is not what happened:

| H | strikes | stale actions | success | steps |
|---|---|---|---|---|
| 1 | 4.00 | 4.0 | 1/3 | 373.7 |
| 10 | 2.00 | 20.0 | 2/3 | 255.0 |

H=10 received **fewer** strikes, because only t=40 and t=50 are chunk boundaries for it — t=45 and
t=55 are mid-chunk and are never visited by the hook. The comparison is therefore confounded by
strike count, and it is discarded. `gate13_analyze.py` now prints `STRIKE COUNT NOT MATCHED ACROSS
HORIZONS` and records `_completeness.strike_count_unmatched_across_H` whenever the mean strike count
drops with H, so this failure cannot be silently re-introduced.

Consequence for the design: the only way to increase invalidation *within* a chunk with this hook is
to increase the horizon, not the cadence. A genuinely mid-chunk strike would require moving the hook
out of the replan branch, which is a harness change this gate does not make. The identifiability
limit is therefore stated rather than engineered around: this gate can vary how many committed
actions a strike invalidates, but not how many times a single chunk is interrupted.

## Interpretation

Commitment cost does not compound. Once the strikes stop, the policy re-acquires the object; how
many blind actions it executed in the meantime does not change whether it succeeds. This is
consistent with Gate 13: the binding constraint is the recovery threshold (whether the object can
be re-reached at all), not the length of the open-loop commitment.

The negative result is supported by five independent runs in which the stale-action count genuinely
varies by design (verified against each `gate13_summary.json`, `stale_disturb`):

| run | magnitude | n/cell | stale at H1 -> H10 |
|---|---|---|---|
| `gate13_main` | 0.05 m | 10 | 1.0 / 2.0 / 5.0 / 10.0 (H=1,2,5,10) |
| `gate13_psnr2` | 0.05 m | 6 | 1.0 -> 10.0 |
| `gate13_lad002` | 0.02 m | 5 | 1.0 -> 10.0 |
| `gate13_lad003` | 0.03 m | 5 | 1.0 -> 10.0 |
| `gate13_repeat_sub` | 0.01 m x4 | 6 | 3.3 -> 32.7 |

The claim these five support is narrower than "success does not vary" — success does fluctuate run to
run. What holds in every one of them is that the success cost **never increases with H**: it is
either flat or it moves the wrong way for a compounding mechanism.

| run | success cost at H1 -> H10 | shape |
|---|---|---|
| `gate13_main` spatial | +0.20 -> +0.20 (H=1,2,5,10 all equal) | flat |
| `gate13_main` object | +0.40 / +0.60 / +0.10 / +0.30 | non-monotone |
| `gate13_psnr2` spatial | +0.33 -> +0.33 | flat |
| `gate13_lad002` both | +0.00 -> +0.00 | flat |
| `gate13_lad003` object | +0.80 -> +0.40 | decreases |
| `gate13_repeat_sub` object | +0.17 -> +0.00 | decreases |

Not one of them shows the monotone rise that compounding commitment cost would require. The visible
run-to-run spread is binomial noise at these n (0.03 m object: Fisher p=0.52 for H1 vs H10).

`results/gate13_repeat05` is deliberately **not** counted among them. It is not excluded because its
numbers disagree — the spatial cells alone show stale 2.0 -> 20.0 with a flat cost of +1.00 at both
horizons, which is consistent with everything above. It is excluded because that flat cost is at the
**ceiling** (0/6 success at both H, every episode hitting the 430-step limit), so the run cannot
distinguish "no compounding" from "total failure everywhere", and because its object task never fired
the intervention at all (strikes 0, 6/6 success) and one control cell is incomplete (3/6). Three
independent defects; it is retained only as the capture that exposed failure modes 2 and 3.

One consequence worth stating: the 0.05 m spatial result is a *ceiling confirmation* of the negative
result rather than evidence against it. Going from four 0.01 m strikes (total drift 0.04 m) to 1-3
strikes of 0.05 m (total drift 0.05-0.15 m) moves the spatial task from 6/6 at both horizons to 0/6
at both horizons — the cost goes from 0.00 to 1.00 without ever becoming horizon-dependent.

Across the whole ladder the pattern is the same, and the cost tracks total drift rather than horizon:

| per-strike magnitude | strikes | spatial cost | object cost |
|---|---|---|---|
| 0.02 m | 1 | 0.00 (flat) | 0.00 (flat) |
| 0.03 m | 1 | 0.00 (flat) | 0.80 / 0.40 (decreasing) |
| 0.05 m | 1 | 0.20 (flat) | 0.10-0.60 (non-monotone) |
| 0.05 m | 1-3 | 1.00 (flat, at ceiling) | not fired |
| 0.01 m | 4 | 0.00 (flat) | 0.17 / 0.00 (decreasing) |

A single 0.05 m strike costs 0.2 on spatial; repeated 0.05 m strikes destroy it outright. So
accumulated drift matters, and it matters in the same way at every horizon — which is precisely the
claim: damage scales with how far the world moved, not with how long the policy had committed to the
old one.

## Reproduce

```bash
python scripts_setup/gate13_run.py --tasks libero_spatial:0,libero_object:0 \
  --horizons 1,10 --seeds 1,2 --trials 3 --arms control,disturb \
  --magnitude 0.01 --world-step 40 --world-repeat-every 10 --world-repeat-count 4 \
  --tag repeat_sub --ngpu 2
python scripts_setup/gate13_analyze.py results/gate13_repeat_sub
python scripts_setup/test_gate9_intervention.py     # 96 checks, includes the strike invariants
```
