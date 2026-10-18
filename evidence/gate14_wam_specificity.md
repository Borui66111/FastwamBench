# Gate 14 — is the commitment cost specific to a future-aware world model?

STATUS: **COMPLETE for the carry regime** (2026-10-19), including the
800-step budget replication (section 3b). The approach-regime replication under
`first_frame` is reported in section 3c at 400 steps; its 800-step run
(`results/gate13_g14ffapproach800`) is still in flight. Same checkpoint, same task (`libero_object:0`),
same seeds (1,2), same 3 trials/cell, same grasp-relative strike schedule
(0.01 m, repeat every 10 steps, 4 strikes), same replan horizons (1 and 10).
**The only difference is the action-inference pathway**: `idm` (future-aware, the
WAM pathway) vs `first_frame` (non-future baseline). Data:
`results/gate13_repeat_carry_full` (idm, the Gate 13C/13D run) and
`results/gate13_g14ff` (first_frame).

## 1. Does `first_frame` actually change the controller?

Yes, but the two pathways do not merely differ in competence — they differ in
*direction of error*. On the **undisturbed** episodes:

| pathway | control success | mean steps on success (H1 / H10) |
|---|---|---|
| `first_frame` | 5/6 @ H1, 6/6 @ H10 (11/12) | 251 / 167 |
| `idm` | 6/6 @ H1, 6/6 @ H10 (12/12) | 179 / 164 |

`first_frame` is slightly clumsier at H1 (one control episode burned the full
400-step budget) but the control difference is not significant
(Fisher p=1.00 per cell, p=0.33 pooled). So the comparison is not WAM-good vs
baseline-broken; the baseline is competent.

**The flag demonstrably takes effect** — otherwise the identical disturbed counts
below would be a plumbing no-op rather than a result. Same task, same seed, same
arm produces different behaviour under the two pathways: at H1/seed 1 control the
episode lengths are 430, 240, 419 (`first_frame`) vs 186, 164, 222 (`idm`). The
pathway is doing work; it simply does not change what the disturbance costs.

## 2. The headline: the cost is *not* specific to future-aware inference

| | control | disturb | cost |
|---|---|---|---|
| `idm` (future-aware) | 6/6 @ H1, 6/6 @ H10 | 2/6 @ H1, 1/6 @ H10 | +0.67, +0.83 |
| `first_frame` (non-future) | 5/6 @ H1, 6/6 @ H10 | **2/6 @ H1, 1/6 @ H10** | +0.50, +0.83 |

The disturbed cells show **the same counts**: 2/6 and 1/6 at both horizons.
Fisher on `idm` disturb vs `first_frame` disturb: **p=1.0000 at H=1, p=1.0000 at
H=10** (pooled 3/12 vs 3/12, p=1.000).

**p=1.00 here is not equivalence, and section 4b quantifies why**: at n=6 per cell
the 95% interval on the difference spans roughly ±0.44, so these data are equally
compatible with `first_frame` being substantially worse or substantially better.
The refutation of the specificity hypothesis does **not** rest on that null. It
rests on the *within-pathway* comparison: the specificity hypothesis predicts
that removing future-aware inference should remove the damage, i.e. that
`first_frame` disturb would look like `first_frame` control. It does not —
pooled over horizons, 11/12 control vs 3/12 disturb, **Fisher p=0.0028**
(H=10 alone: 6/6 → 1/6, p=0.015; H=1 alone: 5/6 → 2/6, p=0.24).

**This is a negative result for the WAM-specificity hypothesis, and it is the
most important measurement in Gate 14.** The world-model commitment cost
measured in Gates 13B–13D survives removal of future-aware action inference. A
policy that never conditions its actions on a predicted future is damaged just as
badly by a single 1 cm disturbance.

## 3. The dominant failure mode is also unchanged

`scripts_setup/gate13d_mechanism.py` on the `first_frame` run:

| pathway | H | control modes | disturb modes |
|---|---|---|---|
| `first_frame` | 1 | PLACED×5 | HELD-ABOVE-BASKET 1, HELD-ELSEWHERE 1, LOST-FAR 1, STILL-DESCENDING 1 |
| `first_frame` | 10 | PLACED×6 | HELD-ABOVE-BASKET 4, LOST-FAR 1 |
| `idm` (13D) | 1 | PLACED×6 | HELD-ABOVE-BASKET 3, LOST-FAR 1 |
| `idm` (13D) | 10 | PLACED×6 | HELD-ABOVE-BASKET 3, LOST-FAR 1, STILL-DESCENDING 1 |

The dominant mode is the same in both pathways: the object is carried to the
basket and **never released** (7 of 9 `first_frame` failures never release it;
the two that do release let go 33 and 34 steps after the strike). 12/12 strikes
again land after the lift. The H=1 `first_frame` mix is more scattered (one
episode each of held-above, lost-far, held-elsewhere, still-descending), so this
is a shared dominant mode, not an identical signature. **The behaviour that the
disturbance breaks is not the world-model-specific part of the controller.**

## 3b. Budget caveat — tested, and it does not change the verdict

Every cell above was run at the suite's 400-step budget, and `first_frame` is
slower than `idm` even on success (control H=1: 240–419 steps vs 164–186), so
"less successful" and "slower" are not separable in that table. A
`--max-steps 800` arm was therefore run on the disturb cells of **both**
pathways (n=6/cell, `results/gate13_g14ff800`, `results/gate13_g14idm800`):

| pathway | disturb H=1 @400 | @800 | disturb H=10 @400 | @800 | total @400 | @800 |
|---|---|---|---|---|---|---|
| `idm` | 2/6 | **3/6** | 1/6 | **1/6** | 3/12 | **4/12** |
| `first_frame` | 2/6 | **3/6** | 1/6 | **1/6** | 3/12 | **4/12** |

The longer budget rescues **exactly one episode per pathway** and leaves the
rest stuck at the cap — in both arms every one of the 8 failures runs to 830
steps (12 episodes/arm: 4 successes, 8 non-terminating). `idm` disturb vs
`first_frame` disturb at 800 steps: **4/12 vs 4/12, Fisher p=1.0000**. So the
identity is not a budget artifact — doubling the budget moves both arms by the
same amount. It also shows the carry-regime cost is not simply "runs out of
time" in one pathway only: slow successes exist in both (758 steps for
`first_frame`, 618 for `idm`).

## 3c. The other regime: approach-phase strikes under the non-future pathway

The carry regime is where the *future-aware* model pays. Running the **approach**
schedule (fixed strike at env step 40, pre-grasp, same 0.01 m / every 10 / ×4)
under `first_frame` gives the opposite pattern at the 400-step budget:

| pathway | approach control | approach disturb | Fisher |
|---|---|---|---|
| `idm` (Gate 13B, `results/gate13_repeat_sub`) | 12/12 | 11/12 | p=1.00 |
| `first_frame` (`results/gate13_g14ffapproach`) | 11/12 | **5/12** | **p=0.027** |

Every one of the 7 `first_frame` approach failures is a **430-step timeout** —
the episode does not terminate, it runs out of budget — whereas the `idm`
approach failures are a single 430-step timeout out of 12 and its successes take
204–382 steps. So the pattern is not "the non-future model is more fragile in the
approach phase"; it is that the non-future model is **slow enough that an
approach-phase strike pushes it past the step budget**. A `--max-steps 800`
replication of this arm (`results/gate13_g14ffapproach800`) is running to settle
whether the cost is time or damage; the first 800-step control episode, which
timed out at 400, succeeds at 606 steps, which is consistent with the
time-budget reading.

**This is the honest shape of the Gate 14 result:** in the regime where the
future-aware model is damaged (carry), removing future-aware inference changes
nothing; in the regime where it is *not* damaged (approach), removing it produces
a cost that is budget-mediated rather than a different failure mode.

## 4. What this does and does not establish

**Does establish:**
- A single mid-chunk action displacement costs ~0.5–0.8 success rate in the carry
  regime **regardless of whether the controller uses predicted future frames**.
- The carry-regime cost is a real property of this execution protocol
  (fixed-horizon chunk replay), not an artifact of the WAM. The protocol is what
  loses control of the placement, not the future-aware pathway.
- Therefore **every earlier carry-regime result (13, 13B, 13C, 13D) is a
  statement about the protocol**, and the "WAM" framing in those gates was
  never tested. They now are, and the framing fails.

**Does not establish:**
- That the WAM has *no* world-modelling advantage. Only that a **single mid-chunk
  action displacement in the carry phase** does not measure one. The PSNR
  results (predicted-future fidelity, ≈−4.4 dB at lag ≥ 4) come from the video
  pathway and are not exercised by this ablation.
- That `first_frame` is the right baseline for *all* claims. It removes
  future-conditioned action inference but keeps the rest of the architecture
  (`first_frame_cond_mask` conditions on the first predicted frame rather than
  the whole predicted clip — see `fastwam_optional_idm.py:101`). A stronger
  baseline (e.g. a policy with no video branch at all) is untested.
- That the approach-regime cost under `first_frame` is damage rather than
  slowness: it is 7/7 timeouts at 400 steps, and the 800-step replication is
  still running. Until it lands, the approach row of section 3c is a
  budget-mediated result, not a robustness claim.

## 5. Consequence for the paper claim

The honest headline is now:

> A single mid-chunk action displacement breaks an episode only when it lands in
> the carry phase — and it breaks it identically for a future-aware and a
> non-future controller, by leaving the object held above the basket or carried
> away from it. **The cost is a property of fixed-horizon chunk execution, not a
> world-modeling commitment cost.**

That is a weaker claim than "world-model commitment costs 0.8 success", and it is
the one the data support.

## Reproduce

```bash
python scripts_setup/gate13_run.py --tasks libero_object:0 --horizons 1,10 \
    --seeds 1,2 --trials 3 --arms control,disturb --magnitude 0.01 \
    --world-trigger-after-lift 0.02 --world-repeat-every 10 --world-repeat-count 4 \
    --action-infer-mode first_frame --tag g14ff --ngpu 2

python scripts_setup/gate14_compare.py \
    --idm results/gate13_repeat_carry_full --ff results/gate13_g14ff \
    --json results/gate14_compare.json

python scripts_setup/gate13d_mechanism.py results/gate13_g14ff

# every cell of this document, rendered from records.jsonl in one view
python scripts_setup/gate14_heatmap.py      # -> evidence/gate14_matrix.png + results/gate14_matrix.json
```

![Gate 14 matrix](gate14_matrix.png)

The heatmap is generated from the per-episode records rather than from the tables above, so it is an
independent read of the same data. It also makes the per-horizon split of the pooled `@800` numbers
visible (3/6 at H=1 and 1/6 at H=10 in each pathway, summing to the 4/12 quoted in section 3b) —
useful because the pooled figure alone hides that the H=10 cells are the weaker ones.

## 4b. What `p=1.00` does and does not buy

The between-pathway comparisons are nulls, and a null at n=6 is a weak statement.
Quantifying it (Newcombe hybrid-score 95% interval for the difference of two
independent proportions):

| comparison | difference | 95% CI | reading |
|---|---|---|---|
| carry H=1, `idm` 2/6 vs `first_frame` 2/6 | 0.00 | **[−0.44, +0.44]** | no detectable difference; anything up to ±44 points still fits |
| carry H=10, 1/6 vs 1/6 | 0.00 | **[−0.42, +0.42]** | same |
| carry @800, 4/12 vs 4/12 | 0.00 | **[−0.34, +0.34]** | tighter, still wide |
| approach, `idm` 11/12 vs `first_frame` 5/12 | **+0.50** | **[+0.12, +0.73]** | the only between-pathway contrast that excludes zero |

So the honest claim is **not** "the two pathways are equally damaged" — that would
require an equivalence test with a pre-declared margin, and at this n no margin
tighter than ~±0.35 is even testable. The claim is:

> Under the specificity hypothesis, removing future-aware action inference should
> have removed the damage. It did not: the non-future pathway still drops from
> 11/12 to 3/12 (p=0.0028), with the same failure mode.

That is a refutation of the hypothesis, and it does not depend on the two
pathways being *equal* — only on the baseline being damaged at all. The
difference between the pathways could be as large as 44 points in either
direction and the refutation would stand.

**What would settle the equality question:** to exclude a 20-point difference
between pathways at 80% power around p≈0.3–0.5 needs ≈93 episodes per arm. At
~4 min/episode that is ~6 GPU-hours per arm per horizon; the seed extension in
`STATE.md` is scoped for that, not run yet.

## Power

n=6 per cell. A real difference of the size Gate 13 found (6/6 → 2/6) would have
been visible; differences smaller than about 1 in 6 successes per cell are not
excluded, which section 4b makes explicit rather than leaving to the reader. The
pooled disturb comparison is not evidence of a WAM advantage either way — with
3/12 vs 3/12 there is nothing to prefer.
