# Gate 13 — PSNR at a matched lag (WITHDRAWN, kept as a retraction record)

**Do not cite any number in this file. The authoritative Gate 13 PSNR result is
`evidence/gate13_worldmodel_final.md`.**

This file is kept, not deleted, because it is the second step of a two-stage correction and a
reviewer who saw either earlier draft must be able to check that the claim was fixed rather than
buried.

History of the claim, in order:

| stage | claim | status |
|---|---|---|
| 1 | "a mid-chunk change damages the prediction **4.7x** more at H=10 than H=1" | **withdrawn** — scored frame count was derived from `replan_steps` |
| 2 | "matched lag 4: **−0.64 dB at H=5 vs −1.52 dB at H=10 (≈2.4x)**, so a horizon effect does exist" (this file) | **withdrawn** — per-episode clip averaging diluted disturbed clips by a factor that itself differs ~10x between H=1 and H=10 |
| 3 | "matched lag 4, clip-isolated: **−4.42 dB at H=5 vs −4.40 dB at H=10**, no detected H dependence" | current — `evidence/gate13_worldmodel_final.md` |

Stage 3 also withdraws the interpretation, not just the magnitude: the −4.4 dB is *counterfactual
forecast invalidation* under an unannounced change, so it says nothing about prediction
competence, mismatch detection, or task recovery. See the five-quantity breakdown in
`evidence/gate13_worldmodel_final.md`.

---

## What stage 2 got right

`eval_libero_single.py:_get_future_frame_capture_steps(cfg)` derives the scored frame count from
`replan_steps`:

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

H=1 was therefore scored as an *instantaneous* reconstruction and H=10 as an average over 8 steps
of lookahead. The "4.7x" reading was that artifact.

The fix it introduced is still in the tree and is still correct: `EVALUATION.psnr_fixed_lags=[0,4,8]`
*requests* the same lags for every H, and `episode_frame_psnr` records per-frame values.

**Measured limit of the override:** the predicted clip is bounded by the executed chunk, so the
override cannot manufacture frames that were never generated. H=1 with lags `0,4,8` still yields
exactly **one** frame (lag 0). What makes a cross-horizon comparison valid is the per-frame
breakdown: lag 4 is frame index 1 for every H whose chunk covers 4 steps (H>=5); lag 8 needs H>=9.

## Why stage 2's own numbers were still wrong

The stage-2 table below averaged frame *k* over **every clip in an episode**, so disturbed clips
were diluted by a factor that differs by roughly 10x between H=1 and H=10 — a second, independent
instance of the same failure mode as stage 1: a term in the metric (the averaging denominator)
changed with the variable being swept.

Stage-2 numbers, `results/gate13_psnr_lag`, n=2 per cell — **shown only so the retraction is
checkable, not for citation**:

| H  | arm     | lag 0 | lag 4 |
|----|---------|-------|-------|
| 5  | control | 37.52 | 25.00 |
| 5  | disturb | 39.39 | 24.36 |
| 10 | control | 37.60 | 25.10 |
| 10 | disturb | 37.62 | 23.58 |

Stage 2 read the lag-4 column as "−0.64 dB at H=5 vs −1.52 dB at H=10, ≈2.4x, therefore a horizon
effect". Redone clip-isolated (`results/gate13_psnr_clip`, n=6/cell) the cost is **−4.42 dB at H=5
and −4.40 dB at H=10**: the 2.4x ratio does not survive, and the absolute size roughly triples.

What stage 2 did establish and what still stands:

- **At lag 0 the disturbance costs nothing** (37.62 vs 37.60 at H=10) — as it must, because the
  displacement happens after the plan was made. This is a positive control on the whole arm, and
  stage 3 confirms it exactly (0.00 dB delta).
- **Control fidelity collapses with lookahead with no intervention at all.** Stage 2 saw 37.5 dB at
  lag 0 → 25.0 dB at lag 4 on this small run; stage 3 measures 39.6 → 27.9 → 27.1 dB at lags 0/4/8.
  The absolute values move between runs (different clip sets, n, and clip-isolation), so quote
  stage 3's numbers. The *shape* — accurate at the moment of planning, drifting badly inside one
  committed chunk — is the most robust world-modelling fact in the project and needs no
  intervention to demonstrate. Lead with it.

## Unchanged, unambiguous results from the same runs

- `stale executed == H` exactly (5 and 10 here; 1,2,5,10 in the main sweep).
- 0 contaminated episodes out of 160 in the main sweep.
- Control success 1.00 in every cell of the main sweep.
- Task-level success cost is large but **not monotone** in H at n=10: the data show **no detected
  monotone effect and are underpowered to rule out modest effects** (they are not evidence of no
  effect; the magnitude ladder did not rescue the strong claim either).
