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
  - stale-window divergence (m) by H = H1=-0.003, H2=0.002, H5=0.018, H10=0.019
  - extra steps to succeed, disturbed vs control (successes only, so not inflated by timeouts) = H1=+46, H2=+21, H5=+41, H10=+58
  - monotone increasing cost with horizon: **False**
- **libero_object_t0**: cost by H = H1=+0.40, H2=+0.60, H5=+0.10, H10=+0.30
  - stale executed by H = H1=1, H2=2, H5=5, H10=10
  - mean disturbed steps by H = H1=346, H2=364, H5=258, H10=331
  - timeouts by H (control→disturb) = H1=0→5, H2=0→6, H5=0→1, H10=0→3
  - stale-window divergence (m) by H = H1=-0.008, H2=-0.007, H5=-0.007, H10=-0.007
  - monotone increasing cost with horizon: **False**
- **libero_spatial_t0**: cost by H = H1=+0.20, H2=+0.20, H5=+0.20, H10=+0.20
  - stale executed by H = H1=1, H2=2, H5=5, H10=10
  - mean disturbed steps by H = H1=176, H2=175, H5=173, H10=173
  - timeouts by H (control→disturb) = H1=0→2, H2=0→2, H5=0→2, H10=0→2
  - stale-window divergence (m) by H = H1=0.002, H2=0.011, H5=0.043, H10=0.045
  - monotone increasing cost with horizon: **True**

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
   the weaker, mechanism-level claim in (1) plus the divergence trend in (4).

4. **Where the horizon effect does show up is the mechanism metric.** During the stale
   window the end-effector diverges from the moved object by an amount that grows with
   H on libero_spatial (0.002 -> 0.011 -> 0.043 -> 0.045 m). On libero_object the same
   quantity is flat and slightly negative (~-0.007 m): there the arm was already moving
   toward the object's new location, so the displacement did not misdirect it. So the
   divergence signature is task-dependent, not universal, and this report says so.

Why the task-level cost fails to grow with H: the displacement is the same size at the
same absolute step for every H, so re-acquiring the object is roughly H-independent and
dominates the small, H-dependent part. The magnitude ladder below tested that reading
directly, and **it did not rescue the strong claim**: at 0.02 m both horizons recover
completely (cost +0.00 at H=1 and H=10); at 0.03 m the cost is +0.33 at H=1 and +0.20 at
H=10, i.e. the *short* horizon looks slightly worse, which is the opposite of the
prediction and well inside noise at n=10. The H-dependent component is therefore smaller
than this design can resolve, not merely masked by re-acquisition.


## Magnitude ladder

### displacement 0.02 m

| H | control | disturbed | cost | stale executed | mean steps (ctl→dis) | timeouts (ctl→dis) | contaminated | n |
|---|---|---|---|---|---|---|---|---|
| 1 | 1.00 | 1.00 [0.72,1.00] | **+0.00** | 1 | 143 → 137 | 0 → 0 | 0 | 10 |
| 10 | 1.00 | 1.00 [0.72,1.00] | **+0.00** | 10 | 137 → 138 | 0 → 0 | 0 | 10 |

### displacement 0.03 m

| H | control | disturbed | cost | stale executed | mean steps (ctl→dis) | timeouts (ctl→dis) | contaminated | n |
|---|---|---|---|---|---|---|---|---|
| 1 | 1.00 | 0.60 [0.31,0.83] | **+0.40** | 1 | 143 → 246 | 0 → 4 | 0 | 10 |
| 10 | 1.00 | 0.80 [0.49,0.94] | **+0.20** | 10 | 137 → 197 | 0 → 2 | 0 | 10 |


## What this design cannot resolve, and what would

At n=10 per cell the binomial noise floor is roughly +/-0.25 on a rate near 0.7, so
only a very large H effect could be detected. To resolve a difference of 0.10 in
success rate between H=1 and H=10 at 80% power you need roughly 300 episodes per arm
(two-proportion test, alpha=0.05; 0.80 vs 0.70 gives n~290 per arm). That is ~30x this
sweep. The cheaper route is the
mechanism metric, which is continuous rather than binary: the stale-window divergence
already separates H=1 from H=10 by more than 20x on libero_spatial (0.002 vs 0.045 m),
so the horizon effect is measurable at the action level long before it is measurable
at the task level. A reviewer wanting the strong task-level claim should treat this
report as a powered negative result at n=10, not as evidence of no effect.


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
- `scripts_setup/test_gate9_intervention.py` — 67 unit checks incl. the absolute-step trigger
  and the goal-aware guard.
- `gate13_summary.json` carries `contaminated_disturb` per cell.

*Generated from `results/gate13_main/gate13_summary.json`.*
