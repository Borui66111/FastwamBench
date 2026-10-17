# Gate 13 — magnitude ladder (complete)

Question the ladder was built to answer: *is the flat, non-monotone success cost in the
main sweep (0.05 m) a real absence of a horizon effect, or is it masked by the cost of
re-acquiring a badly displaced object?* If the latter, then at a **smaller** displacement
— one a short horizon can replan away — the horizon effect should appear.

Setup: same tasks, seeds, absolute intervention step (40), and horizon set as the main
sweep; only the displacement magnitude changes. 5 trials/cell, 2 tasks × H{1,10} ×
{control,disturb} = 20 episodes per magnitude.

## Complete results

### 0.02 m

| task | H | control | disturbed | cost | stale | timeouts |
|---|---|---|---|---|---|---|
| libero_object_t0  | 1  | 1.00 | 1.00 | +0.00 | 1  | 0 → 0 |
| libero_object_t0  | 10 | 1.00 | 1.00 | +0.00 | 10 | 0 → 0 |
| libero_spatial_t0 | 1  | 1.00 | 1.00 | +0.00 | 1  | 0 → 0 |
| libero_spatial_t0 | 10 | 1.00 | 1.00 | +0.00 | 10 | 0 → 0 |
| **pooled**        | 1  | 1.00 | 1.00 | +0.00 | 1  | 0 → 0 |
| **pooled**        | 10 | 1.00 | 1.00 | +0.00 | 10 | 0 → 0 |

20/20 disturbed episodes succeed. Mean steps are essentially control (137–170).

### 0.03 m

| task | H | control | disturbed | cost | stale | timeouts |
|---|---|---|---|---|---|---|
| libero_object_t0  | 1  | 1.00 | **0.20** | +0.80 | 1  | 0 → 4 |
| libero_object_t0  | 10 | 1.00 | **0.60** | +0.40 | 10 | 0 → 2 |
| libero_spatial_t0 | 1  | 1.00 | 1.00 | +0.00 | 1  | 0 → 0 |
| libero_spatial_t0 | 10 | 1.00 | 1.00 | +0.00 | 10 | 0 → 0 |
| **pooled**        | 1  | 1.00 | 0.60 | +0.40 | 1  | 0 → 4 |
| **pooled**        | 10 | 1.00 | 0.80 | +0.20 | 10 | 0 → 2 |

## What this establishes

1. **There is a displacement threshold below which the commitment costs nothing.**
   0.02 m is fully absorbed at *both* horizons on *both* tasks (20/20). So the cost of a
   mid-chunk world change is not a fixed property of the protocol — it is gated by whether
   the displacement exceeds what the next replan can correct. This is the ladder's main,
   well-supported result.

2. **The threshold is task-dependent, not horizon-dependent.** Between 0.02 and 0.03 m the
   object task crosses it (10/10 → 4/10 pooled over H, Fisher exact p = 0.011) while the
   spatial task does not (still 10/10). Object is a small can into a basket (precise
   grasp); spatial is a bowl onto a plate. Sensitivity to perturbation is set by the task's
   manipulation difficulty, and that swamps the horizon term.

3. **The ladder did NOT rescue the horizon claim.** Within the object task at 0.03 m,
   H=1 (1/5) vs H=10 (3/5) gives Fisher p = 0.52 — not significant. The apparent *reverse*
   trend (short horizon worse) is noise. Comparing across magnitudes at the same horizon is
   also non-significant (H=1: 1/5 at 0.03 vs 6/10 at 0.05, p = 0.28), i.e. the object
   task's success is not monotone in displacement either.

## Caveats

- n = 5 per cell per magnitude. The only comparison with adequate separation is 0.02 vs
  0.03 m pooled over horizons (p = 0.011); everything finer is underpowered.
- These runs used the default (horizon-dependent) PSNR capture, so the `psnr` column is
  blank here. The matched-lag PSNR experiment is separate
  (`evidence/gate13_psnr_matched_lag.md`).
- The disturbance direction is goal-aware and therefore depends on the object's pose at
  step 40, which varies slightly across episodes. Direction is recorded per episode in
  `records.jsonl` for anyone who wants to check it.

## Reproduce

```
python scripts_setup/gate13_run.py --tasks libero_spatial:0,libero_object:0 \
  --horizons 1,10 --seeds 1 --trials 5 --arms control,disturb \
  --magnitude 0.02 --world-step 40 --tag lad002 --ngpu 2
python scripts_setup/gate13_run.py ... --magnitude 0.03 --tag lad003 --ngpu 2
python scripts_setup/gate13_analyze.py results/gate13_lad002
python scripts_setup/gate13_analyze.py results/gate13_lad003
```
