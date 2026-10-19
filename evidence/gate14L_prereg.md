# Gate 14L — pre-registration (written before the sweep completed)

Committed BEFORE the sweep finished, so the predictions cannot be fitted to the result.

## Question

The carry-regime null (Gate 14) showed a mid-carry strike costs success regardless of whether
action inference is future-conditioned. That null was measured at H=1 and H=10 in the CARRY
regime, where contact is rich and a 1 cm error is absorbed by contact dynamics.

The approach regime is different: the strike lands at env step 40, before the first grasp, so
recovery is unconstrained by contact. There, `idm` beat `first_frame` (11/12 vs 5/12, p=0.027).
At n=12 that is suggestive, not established.

Gate 14L asks whether that advantage **scales with commitment horizon**. If it does, the
thesis survives in a corrected form: commitment to a future world pays off exactly when the
policy must act on a world it will not re-observe. If it is flat, the thesis is dead and the
paper becomes the diagnostic result.

## Design

`replan_steps` (H) drives two things at once: how many steps are executed open-loop, and how
many future frames the world model scores (`1 + H//4`). So H is a dose of commitment in the
execution sense and, at the same time, a dose of future-scoring. That confound is intrinsic to
the codebase and is stated here rather than engineered away.

**H = 1 is the built-in placebo.** `keep_frames = 1 + H//4` = 1 at H=1, so the world model
scores zero future frames and `idm` has no future information that `first_frame` lacks. Any
advantage at H=1 is therefore noise, not commitment. The prediction has a floor built in.

- H in {1, 2, 5, 10}; both pathways; arms control,disturb
- Approach regime: `--world-step 40 --world-repeat-every 10 --world-repeat-count 4`
- `--max-steps 800` (the 400-step budget times the control arm out, Gate 14 budget arm)
- No `--zero-stale`: the stale action IS part of the mechanism under test
- n = 18 per cell (6 seeds x 3 trials), one 0.01 m strike

## Predictions (falsifiable, written in advance)

P1. At H=1, `idm` and `first_frame` disturb success rates are statistically indistinguishable
    (Fisher p > 0.05). This is the placebo; if it fails, the design is confounded by something
    other than future-conditioning and no horizon trend can be trusted.

P2. The advantage `idm - first_frame` (disturb success) is non-decreasing in H:
    H1 <= H2 <= H5 <= H10, within CI.

P3. The advantage at H=10 exceeds the advantage at H=1 by more than sampling error
    (Fisher p < 0.05 on the interaction, or non-overlapping CIs at n=18).

## What would refute the thesis

A flat advantage -- present at H=1, no larger at H=10 -- kills the commitment story as stated.
That outcome is reported as a negative result, not reframed.

## What this cannot establish

- Whether the effect is due to open-loop execution length, future-frame scoring, or both: H
  moves them together. A clean decomposition needs an eval flag that separates them, which does
  not currently exist.
- Anything about the carry regime; this is the approach regime only.
- n=18 per cell gives Wilson CIs of roughly +/-0.20 on a proportion near 0.5. A monotone trend
  across four horizons would be visible; a single step difference of 1-2 episodes would not.
