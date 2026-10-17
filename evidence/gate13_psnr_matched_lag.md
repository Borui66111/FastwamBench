# Gate 13 — PSNR arm at a matched lag (the honest version)

Status: **supersedes the "PSNR drop is ~5x larger at H=10" claim, which is withdrawn.**

## Why the original comparison was invalid

`eval_libero_single.py:_get_future_frame_capture_steps(cfg)` computes

```
num_future_frames = replan_steps // action_video_freq_ratio      # ratio = 4
capture_steps     = [i * ratio for i in range(num_future_frames + 1)]
```

so the number of future frames scored — and therefore the lookahead the PSNR is
averaged over — is a function of `replan_steps`, i.e. of H:

| H  | frames scored | lags scored (steps ahead of the plan) |
|----|---------------|---------------------------------------|
| 1  | 1             | 0                                     |
| 2  | 1             | 0                                     |
| 5  | 2             | 0, 4                                  |
| 10 | 3             | 0, 4, 8                               |

At H=1 the PSNR is an *instantaneous* reconstruction score. At H=10 it is an
average over 0, 4 and 8 steps of lookahead. Comparing those means across H
penalises the long horizon for being scored further into the future — which is
not the same thing as the model being more damaged by the disturbance. The
original report's "+0.31 dB at H=1 vs +1.47 dB at H=10 (4.7x)" is therefore
withdrawn.

## What the per-frame data actually shows

`eval_libero_single.py` now records `episode_frame_psnr` (per-frame PSNR inside
each predicted clip, index 0 = lag 0). Re-run: `results/gate13_psnr2` (20
episodes, 11 carrying per-frame values). Mean PSNR by lag:

| H  | arm      | n | lag 0 | lag 4 | lag 8 |
|----|----------|---|-------|-------|-------|
| 1  | disturb  | 1 | 37.37 | n/a   | n/a   |
| 10 | control  | 6 | 37.31 | 25.09 | 23.79 |
| 10 | disturb  | 4 | 37.46 | 23.88 | 22.65 |

Three conclusions, in order of confidence:

1. **Prediction fidelity collapses with lookahead, in the control arm, with no
   intervention at all**: 37.3 dB at lag 0 → 25.1 dB at lag 4 → 23.8 dB at lag 8.
   The model's world model is accurate at the moment of planning and drifts badly
   within a single committed chunk. This is the strongest and cleanest
   world-modelling result in the project, and it needs no intervention to show.
2. **Within H=10, the disturbance does not degrade the lag-0 prediction**
   (37.46 disturb vs 37.31 control) — as expected, the disturbance happens after
   the plan. It shows up at longer lags: −1.21 dB at lag 4 and −1.14 dB at lag 8.
3. **A cross-horizon damage comparison is not available from this data.** H=1
   never scores beyond lag 0, so there is no matched-lag pair for H=1 vs H=10.
   Claiming a horizon effect in damage would require capturing the same lags for
   every H (e.g. always capturing lags 0, 4, 8 regardless of H). That is a
   one-line change to `_get_future_frame_capture_steps` and is left as the next
   step rather than claimed.

## Consequence for the write-up

- Supported: "a committed chunk's predicted future degrades sharply with
  lookahead (37 → 24 dB across 8 steps)"; "a mid-chunk world change leaves the
  immediate prediction intact but costs ~1.2 dB at lags 4–8".
- Not supported: "a world change damages the prediction more at longer H".
- Unchanged: `stale executed == H` exactly, 0/160 contaminated episodes, control
  success 1.00 in all eight cells, large bimodal task cost, non-monotone success
  cost (powered negative result at n=10).
