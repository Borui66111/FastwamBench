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

> **CORRECTED 2026-10-21 06:40, while the `idm` half of the sweep was still running.** The two
> paragraphs below originally claimed `replan_steps` also sets the number of future frames the
> world model scores. **That is false.** `_get_num_video_frames()` reads `data.train.num_frames`
> and `action_video_freq_ratio`, neither of which depends on `replan_steps`. At inference
> `replan_steps` does exactly one thing: `pending_actions = action_chunk[:replan_steps]`
> (eval_libero_single.py:744) — the open-loop execution length. See "Correction" at the end.

`replan_steps` (H) drives **only one** thing at inference: how many steps of the predicted
action chunk are executed open-loop before the policy re-plans on a fresh observation. It does
**not** change how many future frames the world model is conditioned on.

~~**H = 1 is the built-in placebo.**~~ **P1 is withdrawn** — see the Correction section. H=1 is
not a placebo: `idm` conditions on the same frames at every H, so the idm-vs-first_frame gap at
H=1 is a real measurement, not a floor.

- H in {1, 2, 5, 10}; both pathways; arms control,disturb
- Approach regime: `--world-step 40 --world-repeat-every 10 --world-repeat-count 4`
- `--max-steps 800` (the 400-step budget times the control arm out, Gate 14 budget arm)
- No `--zero-stale`: the stale action IS part of the mechanism under test
- n = 18 per cell (6 seeds x 3 trials), one 0.01 m strike

## Predictions (falsifiable, written in advance)

~~P1. At H=1, `idm` and `first_frame` disturb success rates are statistically indistinguishable
    (Fisher p > 0.05). This is the placebo; if it fails, the design is confounded by something
    other than future-conditioning and no horizon trend can be trusted.~~

**P1 WITHDRAWN (2026-10-21 06:40, before the idm half finished).** Its premise — that H=1 leaves
`idm` with no future information — is false (see Correction). H=1 is a legitimate data point, not
a placebo floor. P2 and P3 stand unchanged: they are about the *shape* of the gap across H, which
does not depend on the placebo argument. What is lost is the design's internal check against a
constant offset between the two pathways; that offset is now unmeasured, and the analysis must
report the gap at every H rather than only its slope.

P2. The advantage `idm - first_frame` (disturb success) is non-decreasing in H:
    H1 <= H2 <= H5 <= H10, within CI.

P3. The advantage at H=10 exceeds the advantage at H=1 by more than sampling error
    (Fisher p < 0.05 on the interaction, or non-overlapping CIs at n=18).

## What would refute the thesis

A flat advantage -- present at H=1, no larger at H=10 -- kills the commitment story as stated.
That outcome is reported as a negative result, not reframed.

## What this cannot establish

- Whether the effect is due to open-loop execution length, future-frame scoring, or both: **the
  original answer here was wrong.** H moves only execution length; frame scoring is fixed by
  `data.train.num_frames` and is constant across the sweep. So a horizon trend, if found, is
  attributable to open-loop execution length and NOT to any change in future conditioning.
- Anything about the carry regime; this is the approach regime only.
- n=18 per cell gives Wilson CIs of roughly +/-0.20 on a proportion near 0.5. A monotone trend
  across four horizons would be visible; a single step difference of 1-2 episodes would not.

## CORRECTION (added before the sweep finished)

Written while the first_frame half was complete and the idm half was still running, so this is not
fitted to the result. Two premises above are wrong.

1. **P1 is void.** `_get_num_video_frames(cfg)` (eval_libero_single.py:287-288) reads
   `data.train.num_frames` and `action_video_freq_ratio` -- never `replan_steps`. The `idm`
   pathway conditions on the same number of video frames at every horizon. H=1 is therefore NOT a
   zero-future-frame placebo; it is simply the shortest execution commitment. The `replan_steps // 4`
   frame counts at lines 309/330 feed the PSNR and visualisation diagnostics only, and never touch
   action inference. I mistook a diagnostic schedule for the inference path when writing P1.

2. **"H moves them together" is false.** At inference `replan_steps` has exactly one effect:
   `pending_actions = action_chunk[:replan_steps]` (line 744) -- the open-loop execution length.
   Conditioning is held fixed. So this design isolates execution commitment more cleanly than
   claimed here, and the "cannot establish" bullet above is withdrawn.

Consequences, stated before the numbers:
- A nonzero H=1 gap is now EXPECTED and is not a gate failure. P1 as originally framed is
  withdrawn as mis-specified, not reported as failed.
- P2 and P3 stand as written and are the only predictions I will score.
- The symmetry changes: with conditioning fixed, a flat gap is consistent with "future-conditioning
  is what matters and it is horizon-independent", which is a different claim from the one P2/P3 test.
  If the gap is flat, both readings will be stated; I will not pick the flattering one.

## OUTCOME (added after the sweep finished)

Every number recomputed from `records.jsonl` by `scripts_setup/gate14L_horizon.py`; the counts in
the write-up are machine-checked by `scripts_setup/gate14L_verify.py`. Re-run that before quoting.

| H  | idm disturb | ff disturb | gap   | Fisher p |
|----|-------------|------------|-------|----------|
| 1  | 12/18       |  5/18      | +0.39 | 0.0437   |
| 2  | 12/18       | 11/18      | +0.06 | 1.0000   |
| 5  | 17/18       | 12/18      | +0.28 | 0.0877   |
| 10 | 15/18       | 17/18      | -0.11 | 0.6026   |

Pooled over all horizons: idm 56/72 vs ff 45/72 (p=0.0680, not significant).

- **P1 — WITHDRAWN** (mis-specified; H does not control future-frame count).
- **P2 (gap non-decreasing in H) — FAILED.** +0.39, +0.06, +0.28, -0.11: no monotone ordering.
- **P3 (H=10 gap exceeds H=1) — FAILED.** -0.11 vs +0.39, wrong sign.
- **Refutation branch — FIRED.**

The gap is not flat, so the "flat gap = horizon-independent conditioning" branch above does not
apply. It oscillates with no ordering, and no measured quantity explains the H=5 rebound. The
H=1 cell is nominally significant (p=0.0437) but is one of four uncorrected comparisons and does
not clear a multiplicity-corrected threshold; it is not reported as an `idm` advantage.

Detail: `evidence/gate14L_horizon.md`.

