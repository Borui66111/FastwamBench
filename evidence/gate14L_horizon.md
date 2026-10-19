# Gate 14L — the future-aware advantage does not scale with commitment horizon

**Verdict: the predicted dose-response is refuted.** P2 and P3 fail; P1 was withdrawn as
mis-specified before the paired result existed. Every number below is recomputed from
`records.jsonl` by `scripts_setup/gate14L_horizon.py` and `_stats.py`.

Regime: `libero_object:0`, approach-phase strike at env step 40 (repeat every 10, x4, 0.01 m),
800-step budget, no `--zero-stale`, n=18 per cell (seeds 1-6 x 3 trials).
Runs: `results/gate13_g14L_idm_H{1,2,5,10}`, `results/gate13_g14L_ff_H{1,2,5,10}`.

## Results

Success counts, n=18 per cell:

| H  | idm control | idm disturb | ff control | ff disturb | gap (idm-ff) | Fisher p |
|----|-------------|-------------|------------|------------|--------------|----------|
| 1  | 16/18       | 12/18       | 15/18      |  5/18      | +0.39        | 0.0437   |
| 2  | 16/18       | 12/18       | 17/18      | 11/18      | +0.06        | 1.0000   |
| 5  | 17/18       | 17/18       | 18/18      | 12/18      | +0.28        | 0.0877   |
| 10 | 18/18       | 15/18       | 18/18      | 17/18      | -0.11        | 0.6026   |

Pooled disturb over all horizons: idm 56/72 (0.778) vs ff 45/72 (0.625), Fisher **p=0.0680**.

Strike effect within each pathway (control vs disturb, Fisher p):

| H  | idm   | first_frame |
|----|-------|-------------|
| 1  | 0.228 | **0.002**   |
| 2  | 0.228 | **0.041**   |
| 5  | 1.000 | **0.019**   |
| 10 | 0.229 | 1.000       |

## What the numbers say

**The gap is not monotone in H and does not grow with it.** It goes +0.39, +0.06, +0.28, -0.11
across H = 1, 2, 5, 10 — oscillating with no trend, and the pre-registered prediction that it
would increase with commitment is not merely unsupported, it has no ordering at all. P2 fails.

**P3 fails outright.** The H=10 gap is -0.11, opposite in sign to the predicted direction.

**Nothing pooled is significant.** Across all four horizons the two pathways differ by 15
episodes out of 144, p=0.068. The single nominally significant cell (H=1, p=0.0437) is one of
four uncorrected comparisons; a Bonferroni-style threshold for four tests is 0.0125, which it
does not meet. **I will not report this as "idm is better".**

The one pattern that survives scrutiny is inside the first_frame column: the strike reliably
hurts `first_frame` at H=1, 2 and 5 (p = 0.002, 0.041, 0.019) and **does nothing at H=10**
(17/18, p=1.0). `idm` shows no significant strike cost at any horizon. So the honest description
is not "idm's advantage grows with commitment" but "**first_frame's vulnerability to the strike
disappears at the longest horizon**" — which is the opposite end of the axis from where the
thesis put it.

## Why the H-dependence is still not explained

`replan_steps` at inference controls exactly one thing: `pending_actions = action_chunk[:H]`
(eval_libero_single.py:744), the number of actions executed open-loop before replanning. The
number of future frames the IDM conditions on is set by `data.train.num_frames` and
`action_video_freq_ratio`, **not** by H. So H is a pure dose of open-loop execution.

That makes "dilution of a per-chunk advantage by longer open-loop execution" a plausible reading
of the shape, but it is a reading, not a measurement: it predicts a smooth decay, and what we
observe is +0.39, +0.06, +0.28, -0.11. Non-monotone oscillation is not dilution. I have no
mechanism for the H=5 rebound, and I am not going to invent one.

## Against the pre-registration

- **P1 — WITHDRAWN, not tested.** It assumed H=1 leaves `idm` with no future frames. False:
  frame count comes from `data.train.num_frames`, not `replan_steps`. Withdrawn in
  `gate14L_prereg.md` (commit `0029bde`) while the `idm` half of the sweep was still running and
  before any paired idm-vs-ff number existed.
- **P2 (gap non-decreasing in H) — FAILED.** No monotone ordering: +0.39, +0.06, +0.28, -0.11.
- **P3 (H=10 gap > H=1 gap) — FAILED.** -0.11 vs +0.39, wrong sign.
- **Refutation branch — FIRED.**

## Does not establish

- **Any overall advantage for `idm`.** Pooled p=0.068, and the cell-level significance does not
  survive correction for four comparisons.
- **That `idm` and `first_frame` differ only in future-conditioning.** They are different model
  classes (`FastWAMIDM` vs `FastWAM`). This is the main confound and this gate does not resolve
  it; a clean test needs the same class with conditioning ablated.
- **Any mechanism for the non-monotone shape.** No measured quantity explains the H=5 rebound.
- **Generality.** One task (`libero_object:0`), one strike magnitude (0.01 m), one regime
  (approach-phase), one budget (800 steps).
- **That the carry-regime null and this result agree.** They were meant to. They do not
  straightforwardly: the carry regime was flat at all horizons, this is not flat. Treating the
  two as one story would be smoothing over a real discrepancy.

## Honest one-line summary

In the approach regime, at n=18 per cell, the idm-vs-first_frame gap shows no dependence on
commitment horizon (+0.39, +0.06, +0.28, -0.11 over H=1,2,5,10; pooled p=0.068) — refuting the
pre-registered prediction that commitment would amplify the future-aware advantage, and leaving
the observed non-monotone shape unexplained.
