# Gate 13 — definitive world-model measurement (clip-isolated)

This supersedes the earlier "PSNR drop grows with H" numbers, which were artifacts of two
measurement errors (documented at the end).

## Setup

`libero_spatial` task 0. 6 episodes per cell (2 seeds x 3 trials). The world is displaced
by 0.05 m at absolute step 40, which is a replan boundary for both H=5 and H=10. With
`visualize_future_video=true` the model emits a predicted future clip at every replan; PSNR
against the realized frames is scored every 4 env steps (`action_video_freq_ratio`), so
frame index k = lookahead of 4k steps.

Critically, the analysis uses **only the clip planned at step 40** — the one the
displacement lands inside — not the episode average.

## Result

| H | lag (steps) | control PSNR | disturb PSNR | delta |
|---|---|---|---|---|
| 5 | 0 | 39.59 | 39.59 | **0.00** |
| 5 | 4 | 27.90 | 23.48 | **-4.42** |
| 10 | 0 | 39.48 | 39.48 | **0.00** |
| 10 | 4 | 27.83 | 23.44 | **-4.40** |
| 10 | 8 | 27.05 | 23.64 | **-3.41** |

## What this establishes

1. **Internal validity is exact.** At lag 0 the two arms are bit-identical (delta = 0.000),
   because the frame was observed before the displacement. Any non-zero value here would
   have meant the arms differed for an unrelated reason. They do not.

2. **A mid-chunk world change costs the world model ~4.4 dB of prediction fidelity** at the
   first scored lookahead after the change (27.90 -> 23.48 dB, i.e. MSE 105.5 -> 291.8 in
   8-bit units squared, a 2.8x increase; `+186.3` in the canonical table).
   This is the direct, causal measurement of "the model's committed prediction is wrong
   because the world moved."

3. **No horizon dependence was detected** (H=5: -4.42, H=10: -4.40; a 0.02 dB difference,
   n=6/cell). Within the 4-step lookahead, a longer commitment is not measurably worse. A
   0.02 dB difference does **not** establish equivalence: at n=6 the design is underpowered
   to rule out a modest H effect. Across lags, the measured damage is -4.40 dB at 4 steps
   and -3.41 dB at 8 steps (H=10 only). That is a purely descriptive lag-wise statement
   about a single clip planned *before* the intervention; it is not evidence that the model
   "re-observes" or recovers, because no new plan is formed inside that clip.

4. **Prediction fidelity itself collapses with lookahead, with no intervention at all**:
   39.5 dB at lag 0 -> 27.9 dB at lag 4 -> 27.1 dB at lag 8. This is the cleanest
   world-modelling finding in the project and it is a property of the model, not of the
   disturbance.

## What the -4.4 dB measures — and what it does not

The displacement is applied *after* the clip was planned and is unobservable until the next
replan. A predictor whose future was generated before that exogenous change **must**
disagree with the realized rollout even if its learned dynamics are perfect. The -4.4 dB
therefore measures **counterfactual forecast invalidation under an unannounced
intervention**. On its own it is not a measure of prediction incompetence, of
mismatch-detection ability, or of any benefit of world modelling.

Five quantities have to be kept apart; this experiment measures only the first two:

| # | quantity | measured here? |
|---|---|---|
| i | pre-intervention prediction fidelity | yes — lag-0 delta is exactly 0.00 dB by construction, and the control arm's lookahead curve (39.6 → 27.9 → 27.1 dB at 0/4/8 steps) is the no-intervention baseline |
| ii | induced surprise after the change | yes — the -4.4 dB at lag 4 |
| iii | mismatch detection | no — nothing in this run reads the PSNR signal to trigger a replan |
| iv | post-replan prediction / action quality | no — the scored clips are plans made *before* the strike; the first new plan is outside this measurement |
| v | task recovery | no — that is the task-success arm of Gate 13 (and Gates 13B–13D) |

Likewise `stale_action_steps == H` is a **runner contract** (the intervention lands
immediately after planning and replanning is forbidden until the chunk ends), not a learned
property of the model.

## Why the earlier claims were wrong

- *"Divergence grows with H (0.002 -> 0.045 m)"*: the metric took a max over a window whose
  length IS H, so longer horizons reached a larger maximum mechanically. At a fixed lag the
  divergence is flat (+0.0016/+0.0017/+0.0017/+0.0017 m at 1 step for H=1/2/5/10).
- *"PSNR drop is 5x larger at H=10"*: the number of scored frames is derived from
  `replan_steps` (n_frames = replan_steps // 4), so H=1 was scored on one frame (lag 0)
  and H=10 on three (lags 0, 4, 8). Averaging frame k over all clips in the episode then
  diluted the disturbed clips by a factor that itself depends on H (~10x more clips at
  H=1). The clip-isolated measurement above removes both confounds.

## Provenance and how to check this file

Every number above is regenerated on CPU from the committed bundle by
`python scripts_setup/gate13_audit.py` (see `evidence/gate13_canonical.md`, section 3). The
bundle (`evidence/gate13_bundle/`) carries the per-clip `frame_psnr` rows these means come
from, plus `manifest.json` with the repo SHAs, the `osc_pose.json` controller hash and the
checkpoint fingerprints of the exact run. `results/` is gitignored, so this bundle — not
`results/` — is the citable evidence.

## Limits

n=6 per cell, single task. The lag-0 null and the -4.4 dB effect are far larger than any
plausible noise (the null is exactly 0.000), but the claim "no H dependence" rests on a
0.02 dB difference at n=6 and should be read as "no measurable dependence at this power",
not as proof of equality.
