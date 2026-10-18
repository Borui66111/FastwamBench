# Gate 13 — the cost of world-model commitment (cross-horizon sweep)

**Question.** A World Action Model plans an action chunk, executes it open-loop for
`replan_steps` (the *commitment horizon* H), then replans. If the world changes while a
chunk is being executed, every remaining action in that chunk was chosen for a world that
no longer exists. This experiment measures the price of that commitment as a function of H.

**Design.** Paired arms, bit-identical until the intervention (verified: `pre_iv_max_l1 = 0`):
- `control` — no intervention.

- `disturb` — at the replan boundary at absolute step 40, teleport the task object
  *away* from its goal (goal-aware, magnitude 0.05 m), then let the model finish the chunk
  and replan normally. The disturbance is guaranteed **not** to satisfy the goal
  (`post_iv_success = False`, guarded + reverted otherwise).

H is swept over [1, 2, 5, 10]; every H divides (40 - 30) so the trigger lands on
a real replan boundary at the same absolute step for all H.
Settings: magnitude=0.05 m, seeds=[1, 2], trials per task/horizon=5, tasks=['libero_spatial:0', 'libero_object:0'].

## Headline (pooled across tasks)

| H | control | disturbed | cost | stale executed | mean steps (ctl→dis) | timeouts (ctl→dis) | contaminated | n |
|---|---|---|---|---|---|---|---|---|
| 1 | 1.00 | 0.70 [0.48,0.85] | **+0.30** | 1 | 142 → 261 | 0 → 7 | 0 | 20 |
| 2 | 1.00 | 0.60 [0.39,0.78] | **+0.40** | 2 | 141 → 269 | 0 → 8 | 0 | 20 |
| 5 | 1.00 | 0.85 [0.64,0.95] | **+0.15** | 5 | 136 → 215 | 0 → 3 | 0 | 20 |
| 10 | 1.00 | 0.75 [0.53,0.89] | **+0.25** | 10 | 135 → 252 | 0 → 5 | 0 | 20 |

`cost` = control_rate − disturb_rate. `stale executed` = actions executed after the world
change but before the next replan (mechanism check: should equal H). `contaminated` =
episodes in which the disturbance accidentally completed the task (must be 0).
`mean steps` and `timeouts` are graded signals: success rate alone hides the cost of
recovery, so a disturbed episode that still succeeds after many extra steps, or that
exhausts the 400-step budget, is reported too.

## Per-task breakdown

### libero_object_t0

| H | control | disturbed | cost | stale executed | mean steps (ctl→dis) | timeouts (ctl→dis) | contaminated | n |
|---|---|---|---|---|---|---|---|---|
| 1 | 1.00 | 0.60 [0.31,0.83] | **+0.40** | 1 | 181 → 346 | 0 → 5 | 0 | 10 |
| 2 | 1.00 | 0.40 [0.17,0.69] | **+0.60** | 2 | 177 → 364 | 0 → 6 | 0 | 10 |
| 5 | 1.00 | 0.90 [0.60,0.98] | **+0.10** | 5 | 171 → 258 | 0 → 1 | 0 | 10 |
| 10 | 1.00 | 0.70 [0.40,0.89] | **+0.30** | 10 | 165 → 331 | 0 → 3 | 0 | 10 |

### libero_spatial_t0

| H | control | disturbed | cost | stale executed | mean steps (ctl→dis) | timeouts (ctl→dis) | contaminated | n |
|---|---|---|---|---|---|---|---|---|
| 1 | 1.00 | 0.80 [0.49,0.94] | **+0.20** | 1 | 104 → 176 | 0 → 2 | 0 | 10 |
| 2 | 1.00 | 0.80 [0.49,0.94] | **+0.20** | 2 | 105 → 175 | 0 → 2 | 0 | 10 |
| 5 | 1.00 | 0.80 [0.49,0.94] | **+0.20** | 5 | 102 → 173 | 0 → 2 | 0 | 10 |
| 10 | 1.00 | 0.80 [0.49,0.94] | **+0.20** | 10 | 104 → 173 | 0 → 2 | 0 | 10 |

## Trend

- **POOLED**: cost by H = H1=+0.30, H2=+0.40, H5=+0.15, H10=+0.25
  - stale executed by H = H1=1, H2=2, H5=5, H10=10
  - mean disturbed steps by H = H1=261, H2=269, H5=215, H10=252
  - timeouts by H (control→disturb) = H1=0→7, H2=0→8, H5=0→3, H10=0→5
  - stale-window max divergence (m) by H = H1=-0.003, H2=0.002, H5=0.018, H10=0.019   ** window length is H; NOT comparable across H **
  - extra steps to succeed, disturbed vs control (successes only, so not inflated by timeouts) = H1=+46, H2=+21, H5=+41, H10=+58
  - cost vs horizon: **non-monotone (no consistent trend)** (strictly increasing: False)
- **libero_object_t0**: cost by H = H1=+0.40, H2=+0.60, H5=+0.10, H10=+0.30
  - stale executed by H = H1=1, H2=2, H5=5, H10=10
  - mean disturbed steps by H = H1=346, H2=364, H5=258, H10=331
  - timeouts by H (control→disturb) = H1=0→5, H2=0→6, H5=0→1, H10=0→3
  - stale-window max divergence (m) by H = H1=-0.008, H2=-0.007, H5=-0.007, H10=-0.007   ** window length is H; NOT comparable across H **
  - fixed-lag divergence at k=1 (m) by H = H1=-0.0075, H2=-0.0075, H5=-0.0074, H10=-0.0074   <- fair comparison across H
  - fixed-lag divergence at k=3 (m) by H = H1=-0.0226, H2=-0.0224, H5=-0.0217, H10=-0.0216   <- fair comparison across H
  - fixed-lag divergence at k=5 (m) by H = H1=-0.0370, H2=-0.0367, H5=-0.0352, H10=-0.0347   <- fair comparison across H
  - cost vs horizon: **non-monotone (no consistent trend)** (strictly increasing: False)
- **libero_spatial_t0**: cost by H = H1=+0.20, H2=+0.20, H5=+0.20, H10=+0.20
  - stale executed by H = H1=1, H2=2, H5=5, H10=10
  - mean disturbed steps by H = H1=176, H2=175, H5=173, H10=173
  - timeouts by H (control→disturb) = H1=0→2, H2=0→2, H5=0→2, H10=0→2
  - stale-window max divergence (m) by H = H1=0.002, H2=0.011, H5=0.043, H10=0.045   ** window length is H; NOT comparable across H **
  - fixed-lag divergence at k=1 (m) by H = H1=+0.0016, H2=+0.0020, H5=+0.0017, H10=+0.0017   <- fair comparison across H
  - fixed-lag divergence at k=3 (m) by H = H1=+0.0109, H2=+0.0117, H5=+0.0126, H10=+0.0124   <- fair comparison across H
  - fixed-lag divergence at k=5 (m) by H = H1=+0.0209, H2=+0.0220, H5=+0.0246, H10=+0.0255   <- fair comparison across H
  - cost vs horizon: **FLAT (identical at every H - no horizon trend)** (strictly increasing: False)

## Interpretation

Three things must be kept apart. They behave differently, and only the first is clean.

1. **The commitment is real, and it scales exactly with H (mechanism, unambiguous).**
   The model executes precisely H actions that were chosen for the pre-change world:
   `stale executed` = H for every H tested (1, 2, 5, 10), with 0 contaminated episodes
   out of 160. Control success is 1.00 in all eight cells. So the intervention does
   what it claims: it invalidates committed actions mid-chunk, without solving the task
   for the model and without breaking the control arm.

2. **A mid-chunk world change is expensive (task level, large and consistent).**
   Success falls by 15-60 points depending on task and horizon, mean steps rise by
   60-100% (spatial 104 -> ~173; object ~175 -> 258-364), and timeouts go from 0 to 1-6
   per 10 episodes. The cost is *bimodal*: an episode either recovers almost as fast as
   control, or it exhausts the 400-step budget. Averaging those two populations is what
   makes the raw `mean steps` column look merely 'somewhat worse'.

3. **The success cost is NOT monotone in H at this sample size (a negative result,
   stated as such).** Pooled cost by H is +0.30, +0.40, +0.15, +0.25: not increasing.
   With n=10 per cell the 95% Wilson interval on a rate near 0.7 is roughly +/-0.25, so
   differences of this size are inside binomial noise. The data therefore do NOT
   support the strong claim 'a longer commitment costs more task success'. They support
   only the mechanism claim in (1).

4. **A first attempt at a mechanism metric did NOT survive scrutiny — reported here as
   a withdrawn claim.** Measuring the end-effector/object divergence over the stale
   window gives 0.002 -> 0.011 -> 0.043 -> 0.045 m for H = 1, 2, 5, 10 on
   libero_spatial, which looks like a clean horizon trend. It is an artifact: the window
   is (iv_step, iv_step+H], so a longer H mechanically reaches a larger maximum. At a
   **fixed lag** (1, 2, 3 or 5 steps after the intervention) the divergence is the same
   for every H (+0.0016…+0.0020 m at lag 1; +0.021…+0.026 m at lag 5). The eef moves
   away from the displaced object at an H-independent rate. On libero_object the same
   quantity is negative and equally flat (~-0.007 m at lag 1). So there is **no
   evidence that a longer commitment misdirects the arm further**; what scales with H is
   the number of stale actions executed, nothing more.

Why the task-level cost fails to grow with H: the displacement is the same size at the
same absolute step for every H, so re-acquiring the object is roughly H-independent and
dominates the small, H-dependent part. The magnitude ladder below tested that reading
directly, and **it did not rescue the strong claim** — but it produced a clean result of
its own: at 0.02 m a world change is fully absorbed (20/20 disturbed episodes succeed, both
tasks, both horizons, steps indistinguishable from control), so the commitment penalty is
gated by whether the displacement exceeds what the next replan can correct rather than being
a fixed property of the protocol. At 0.03 m the object task crosses that threshold
(4/10 pooled over H, Fisher p=0.011 vs 0.02 m) while the spatial task still absorbs it
completely (10/10): the threshold is **task-dependent, not horizon-dependent**. Within the
object task at 0.03 m, H=1 vs H=10 is p=0.52 — noise. The H-dependent component is therefore
smaller than this design can resolve, not merely masked by re-acquisition.


## Magnitude ladder

### displacement 0.02 m

*pooled over both tasks*

| H | control | disturbed | cost | stale executed | mean steps (ctl→dis) | timeouts (ctl→dis) | contaminated | n |
|---|---|---|---|---|---|---|---|---|
| 1 | 1.00 | 1.00 [0.72,1.00] | **+0.00** | 1 | 143 → 137 | 0 → 0 | 0 | 10 |
| 10 | 1.00 | 1.00 [0.72,1.00] | **+0.00** | 10 | 137 → 138 | 0 → 0 | 0 | 10 |


*libero_object_t0*

| H | control | disturbed | cost | stale executed | mean steps (ctl→dis) | timeouts (ctl→dis) | contaminated | n |
|---|---|---|---|---|---|---|---|---|
| 1 | 1.00 | 1.00 [0.57,1.00] | **+0.00** | 1 | 182 → 168 | 0 → 0 | 0 | 5 |
| 10 | 1.00 | 1.00 [0.57,1.00] | **+0.00** | 10 | 170 → 170 | 0 → 0 | 0 | 5 |


*libero_spatial_t0*

| H | control | disturbed | cost | stale executed | mean steps (ctl→dis) | timeouts (ctl→dis) | contaminated | n |
|---|---|---|---|---|---|---|---|---|
| 1 | 1.00 | 1.00 [0.57,1.00] | **+0.00** | 1 | 104 → 106 | 0 → 0 | 0 | 5 |
| 10 | 1.00 | 1.00 [0.57,1.00] | **+0.00** | 10 | 104 → 105 | 0 → 0 | 0 | 5 |

### displacement 0.03 m

*pooled over both tasks*

| H | control | disturbed | cost | stale executed | mean steps (ctl→dis) | timeouts (ctl→dis) | contaminated | n |
|---|---|---|---|---|---|---|---|---|
| 1 | 1.00 | 0.60 [0.31,0.83] | **+0.40** | 1 | 143 → 246 | 0 → 4 | 0 | 10 |
| 10 | 1.00 | 0.80 [0.49,0.94] | **+0.20** | 10 | 137 → 197 | 0 → 2 | 0 | 10 |


*libero_object_t0*

| H | control | disturbed | cost | stale executed | mean steps (ctl→dis) | timeouts (ctl→dis) | contaminated | n |
|---|---|---|---|---|---|---|---|---|
| 1 | 1.00 | 0.20 [0.04,0.62] | **+0.80** | 1 | 182 → 382 | 0 → 4 | 0 | 5 |
| 10 | 1.00 | 0.60 [0.23,0.88] | **+0.40** | 10 | 170 → 288 | 0 → 2 | 0 | 5 |


*libero_spatial_t0*

| H | control | disturbed | cost | stale executed | mean steps (ctl→dis) | timeouts (ctl→dis) | contaminated | n |
|---|---|---|---|---|---|---|---|---|
| 1 | 1.00 | 1.00 [0.57,1.00] | **+0.00** | 1 | 104 → 110 | 0 → 0 | 0 | 5 |
| 10 | 1.00 | 1.00 [0.57,1.00] | **+0.00** | 10 | 104 → 107 | 0 → 0 | 0 | 5 |

**Reading the ladder.** The pooled row is the least informative one here: the two tasks
differ from each other by much more than the horizons differ within a task.
At 0.02 m the world change is fully absorbed on **both** tasks at **both** horizons
(20/20 successes) — so the commitment penalty is not a fixed property of the protocol;
it is gated by whether the displacement exceeds what the next replan can correct.
At 0.03 m the object task breaks (4/10 pooled over H, Fisher p=0.011 vs 0.02 m) while
the spatial task still absorbs it completely (10/10). Within the object task at 0.03 m,
H=1 (1/5) vs H=10 (3/5) is **not** significant (Fisher p=0.52) — the apparent reverse
trend is noise, not evidence that short horizons are worse.


## What this design cannot resolve, and what would

At n=10 per cell the binomial noise floor is roughly +/-0.25 on a rate near 0.7, so
only a very large H effect could be detected. To resolve a difference of 0.10 in
success rate between H=1 and H=10 at 80% power you need roughly 300 episodes per arm
(two-proportion test, alpha=0.05; 0.80 vs 0.70 gives n~290 per arm). That is ~30x this
sweep. The cheaper route is a metric that is continuous rather than binary. The
stale-window divergence looked like one (0.002 vs 0.045 m for H=1 vs H=10 on
libero_spatial), but it is measured over a window whose length IS H, so it grows with H
mechanically; at a fixed lag the values collapse to +0.0016…+0.0020 m for every H. The
clean continuous signal is the **count** of stale actions executed, which is exactly H
by construction and verified per episode — but it is a property of the execution
protocol, not a measure of task damage. A reviewer wanting the strong task-level claim
should treat this report as a powered negative result at n=10, not as evidence of no
effect.


## Predicted-future vs reality (PSNR arm)

`visualize_future_video=true` makes the model render its predicted future; the
PSNR of that prediction against what actually happened is the most direct
world-modelling signal available. A larger drop = the model's world model is
more wrong about the world it is acting in.

| H | PSNR control | PSNR disturbed | drop |
|---|---|---|---|
| 1 | 37.43 | 37.12 | +0.31 |
| 10 | 29.35 | 27.88 | +1.47 |

**Do not read a horizon trend out of this table.** The per-H averages are not
comparable: the scored frame set grows with `replan_steps`, so a longer horizon is
scored further into the future. The valid, clip-isolated measurement is in
`evidence/gate13_worldmodel_final.md` and `evidence/gate13_worldmodel.png`; it shows
fidelity falling with *lookahead* (39.6 -> 27.9 -> 27.1 dB at 0/4/8 steps) and a
~4.4 dB cost from the world change that is **the same at H=5 and H=10**.

**The `drop` column is NOT a valid cross-horizon comparison — do not cite it.**
`_get_future_frame_capture_steps` derives the number of scored frames from
`replan_steps` (`replan_steps // action_video_freq_ratio`, ratio=4), so H=1 scores
**one** frame (lag 0) while H=10 scores **three** (lags 0, 4, 8). A horizon therefore
looks worse partly because it is scored further into the future, and the disturbance
has had more steps to show up — not because the commitment is longer per se.
`eval_libero_single.py` now also records `episode_frame_psnr` (per-frame values) so
this can be re-analysed at a fixed lag; the numbers in this table predate that and
should be treated as withdrawn. The same caveat applies to the stale-window
divergence in the section above: at a **fixed** lag (1, 2, 3, 5 steps after the
intervention) the eef-object divergence is essentially identical across H
(+0.0016 to +0.0020 m at lag 1 for every H), so the growth seen over the full
stale window is a window-length effect. What is unambiguous is the **count**:
exactly H stale actions execute, verified per episode.


## Reproduce

```bash
bash scripts_setup/gate13_all.sh   # full pipeline: sweep -> psnr -> analyze -> report

cd /data1/liborui/fastwam_bench
python scripts_setup/gate13_run.py --tasks libero_spatial:0,libero_object:0 \
  --horizons 1,2,5,10 --seeds 1,2 --trials 5 --magnitude 0.05 --world-step 40 --tag main --ngpu 2
python scripts_setup/gate13_analyze.py results/gate13_main
python scripts_setup/gate13_figure.py results/gate13_main/gate13_summary.json \
  evidence/gate13_commitment_cost.png
```

Guards for reviewers:
- `scripts_setup/gate13_validate_goal_aware.py` — proves the disturbance does not satisfy
  the goal (no model needed).
- `scripts_setup/test_gate9_intervention.py` — 99 unit checks incl. the absolute-step trigger
  and the goal-aware guard.
- `gate13_summary.json` carries `contaminated_disturb` per cell.

*Generated from `results/gate13_main/gate13_summary.json`.*
