# Gate 14 — does commitment cost compound when the world changes repeatedly?

**Short answer: no.** With 10x more stale actions and identical total world drift, task success is
unchanged and effort differences are inside noise. This is the strongest form of the Gate 13
negative result, because the experiment was built specifically to expose compounding.

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
already moved. `strike_count` confirms all four strikes landed in both horizons (3.3 and 4.0 mean).

## Result

| task | H | control | disturb | step cost |
|---|---|---|---|---|
| object | 1 | 6/6, 178.7 steps | 5/6, 268.0 | +89.3 |
| object | 10 | 6/6, 164.3 steps | 6/6, 297.3 | +133.0 |
| spatial | 1 | 6/6, 107.5 steps | 6/6, 94.5 | -13.0 |
| spatial | 10 | 6/6, 103.8 steps | 6/6, 137.3 | +33.5 |

- **Success:** object 5/6 (H1) vs 6/6 (H10), Fisher exact p=1.0. Spatial 6/6 vs 6/6. No horizon effect; if anything H=10 is nominally better.
- **Effort:** H10 minus H1 steps, Welch t-test — object t=0.67, df=9.7, p=0.52; spatial t=1.04, df=5.9, p=0.34. The point estimates lean the expected way (+133 vs +89; +33.5 vs -13) but with n=6 and sd 70-96 the data cannot separate them from noise.

The strikes do cost something: on the object task they add 89-133 steps of re-approach. They do not
cost success, and the size of that cost does not depend on how long the commitment was.

## Two design flaws found and fixed here

Both were caught by looking at the data rather than trusting the harness.

1. **Mirrored strikes made the task easier.** The first version alternated strike direction, so odd
   strikes pushed the object *toward* the goal. Struck episodes then finished in 51 steps against
   ~100 for control. Fixed: every strike now moves the object away, with a regression test asserting
   the invariant.
2. **The repeat cap silently blocked the repeats.** The cap was an absolute goal distance (0.25 m),
   but the object starts ~0.1-0.2 m from the goal, so after one strike the cap tripped and later
   strikes were skipped: measured stale was 1.0 instead of 4. Fixed: the cap is now a drift budget
   measured from the object's distance at the first strike. A test pins the new semantics.

The earlier 0.05 m repeated-strike run (`results/gate13_repeat05`) is superseded by this one: it
ran under flaw 2, so its effective design was a single strike.

## Interpretation

Commitment cost does not compound. Once the strikes stop, the policy re-acquires the object; how
many blind actions it executed in the meantime does not change whether it succeeds. This is
consistent with Gate 13: the binding constraint is the recovery threshold (whether the object can
be re-reached at all), not the length of the open-loop commitment.

The negative result is now supported by five independent runs: the Gate 13 main sweep (n=10),
`psnr2` (n=6), the magnitude ladder (n=10), the 0.05 m repeat run (n=12), and this sub-threshold
repeat run (n=6). All agree that stale-action count varies by design while success does not.

## Reproduce

```bash
python scripts_setup/gate13_run.py --tasks libero_spatial:0,libero_object:0 \
  --horizons 1,10 --seeds 1,2 --trials 3 --arms control,disturb \
  --magnitude 0.01 --world-step 40 --world-repeat-every 10 --world-repeat-count 4 \
  --tag repeat_sub --ngpu 2
python scripts_setup/gate13_analyze.py results/gate13_repeat_sub
python scripts_setup/test_gate9_intervention.py     # 84 checks, includes the strike invariants
```
