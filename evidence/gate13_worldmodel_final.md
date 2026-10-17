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
   first scored lookahead after the change (27.9 -> 23.5 dB, a 1.9x increase in MSE).
   This is the direct, causal measurement of "the model's committed prediction is wrong
   because the world moved."

3. **The damage does NOT depend on the commitment horizon** (H=5: -4.42, H=10: -4.40; a
   0.02 dB difference). Within the 4-step lookahead, a longer commitment is not
   measurably worse. The damage does decay with lookahead (-4.40 at 4 steps, -3.41 at 8),
   i.e. the world model partially recovers as it re-observes.

4. **Prediction fidelity itself collapses with lookahead, with no intervention at all**:
   39.5 dB at lag 0 -> 27.9 dB at lag 4 -> 27.1 dB at lag 8. This is the cleanest
   world-modelling finding in the project and it is a property of the model, not of the
   disturbance.

## Why the earlier claims were wrong

- *"Divergence grows with H (0.002 -> 0.045 m)"*: the metric took a max over a window whose
  length IS H, so longer horizons reached a larger maximum mechanically. At a fixed lag the
  divergence is flat (+0.0016/+0.0017/+0.0017/+0.0017 m at 1 step for H=1/2/5/10).
- *"PSNR drop is 5x larger at H=10"*: the number of scored frames is derived from
  `replan_steps` (n_frames = replan_steps // 4), so H=1 was scored on one frame (lag 0)
  and H=10 on three (lags 0, 4, 8). Averaging frame k over all clips in the episode then
  diluted the disturbed clips by a factor that itself depends on H (~10x more clips at
  H=1). The clip-isolated measurement above removes both confounds.

## Limits

n=6 per cell, single task. The lag-0 null and the -4.4 dB effect are far larger than any
plausible noise (the null is exactly 0.000), but the claim "no H dependence" rests on a
0.02 dB difference at n=6 and should be read as "no measurable dependence at this power",
not as proof of equality.
