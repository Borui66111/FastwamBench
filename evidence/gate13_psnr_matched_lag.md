# Gate 13 — PSNR arm at a matched lag (the corrected measurement)

This file supersedes the original "PSNR drop is ~5x larger at H=10" claim. That
claim was measured on an invalid comparison. It is replaced by the matched-lag
experiment below, which **does** show a horizon effect, but a smaller one.

## Why the original comparison was invalid

`eval_libero_single.py:_get_future_frame_capture_steps(cfg)` derives the scored
frame count from `replan_steps`:

```
num_future_frames = replan_steps // action_video_freq_ratio      # ratio = 4
capture_steps     = [i * ratio for i in range(num_future_frames + 1)]
```

so the lookahead the PSNR averages over depends on H:

| H  | frames scored | lags scored (steps ahead of the plan) |
|----|---------------|---------------------------------------|
| 1  | 1             | 0                                     |
| 2  | 1             | 0                                     |
| 5  | 2             | 0, 4                                  |
| 10 | 3             | 0, 4, 8                               |

H=1 was therefore scored as an *instantaneous* reconstruction, H=10 as an average
over 8 steps of lookahead. The "+0.31 dB at H=1 vs +1.47 dB at H=10 (4.7x)"
reading was that artifact. Withdrawn.

## The fix

`EVALUATION.psnr_fixed_lags=[0,4,8]` (new) *requests* the same lags for every H, and
`episode_frame_psnr` (new) records per-frame values.

**Measured limit of the override:** the predicted clip is bounded by the executed chunk,
so the override cannot manufacture frames that were never generated. Verified on the
powered run: H=1 with lags `0,4,8` still yields exactly **one** frame (lag 0). So the
override does not by itself make cross-horizon *means* comparable. What makes the
comparison valid is the per-frame breakdown: lag 4 is frame index 1 for **every** H whose
chunk covers 4 steps (H>=5). Lag 8 needs H>=9.
`episode_frame_psnr` (new) records per-frame PSNR so any lag can be analysed.
Runner: `GATE13_PSNR_LAGS=0,4,8`.

## Corrected result — matched lag 4, same magnitude (0.05 m), same step (40)

`results/gate13_psnr_lag`, n=2 per cell:

| H  | arm     | lag 0 | lag 4 |
|----|---------|-------|-------|
| 5  | control | 37.52 | 25.00 |
| 5  | disturb | 39.39 | 24.36 |
| 10 | control | 37.60 | 25.10 |
| 10 | disturb | 37.62 | 23.58 |

- **Disturbance cost at the matched lag 4: −0.64 dB at H=5 vs −1.52 dB at H=10.**
  Same lags scored, same displacement, same absolute step — so this is a fair
  cross-horizon comparison, and the damage is ~2.4x larger for the longer
  commitment.
- **At lag 0 the disturbance costs nothing** (37.6 vs 37.6 at H=10), as it must:
  the displacement happens after the plan was made.
- **Control fidelity collapses with lookahead with no intervention at all**:
  37.5 dB at lag 0 → 25.0 dB at lag 4. This is the cleanest world-modelling
  result in the project and needs no intervention to demonstrate.

## Confidence

n=2 per cell. The direction is consistent with the thesis and the metric is now
matched, but the magnitude (2.4x) should not be quoted as a point estimate.
Replication to n>=10 per cell is the obvious next step; the earlier "5x" figure
must not be cited.

## Unchanged, unambiguous results from the same runs

- `stale executed == H` exactly (5 and 10 here; 1,2,5,10 in the main sweep).
- 0 contaminated episodes out of 160 in the main sweep.
- Control success 1.00 in every cell of the main sweep.
- Task-level success cost is large but **not monotone** in H at n=10 (powered
  negative result; the magnitude ladder did not rescue it).
