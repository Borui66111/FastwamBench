# Gate 13 — how to review this experiment

**Claim being tested.** A World Action Model (FastWAM) plans an action chunk and executes
it open-loop for `replan_steps` (the *commitment horizon* H) before replanning. If the
world changes while a chunk is executing, the remaining actions were chosen for a world
that no longer exists. This experiment measures the price of that commitment as a
function of H — using controlled interventions, not task success alone.

## Where the result lives

| artifact | what it is |
|---|---|
| `evidence/gate13_commitment_cost.md` | headline table + trend (generated) |
| `evidence/gate13_commitment_cost.png` | two-panel figure: success vs H, stale vs H (generated) |
| `results/gate13_main/gate13_summary.json` | machine-readable per-(task,H) numbers + `_config` |
| `results/gate13_main/<task>/H<h>/<arm>_s<seed>/records.jsonl` | raw per-step records |

## The five validity checks (and where each is proven)

1. **The disturbance lands AFTER the plan is committed.**
   `eval_libero_single.py`: the chunk is produced at the `_predict_action_chunk` call and
   the world is changed afterwards (`maybe_displace_world`), so the executed actions are
   genuinely stale. `use_action_ensembler: false`, so staleness comes from the chunk.
2. **The disturbance does not itself solve the task.**
   `evidence/gate13_design_checks/probe_goal_deltas.out` (a naive `+x/+y` displacement
   teleports the bowl onto its target and "succeeds" instantly) and
   `validate_goal_aware.out` (the shipped goal-aware disturbance gives
   `post_iv_success = False`). Per-episode `contaminated` must be 0.
3. **The disturb code path is not broken.**
   A 0.0 m no-op disturbance reproduces the control (`noop_validation_summary.json`:
   1/1 success, `obj_move` 0.111 m = the natural grasp-and-place).
4. **The mechanism fires with the right duration.**
   `stale executed == H` in the headline table (1 at H=1, 10 at H=10).
5. **The horizon sweep is not floor-saturated.**
   H=1 must recover from the disturbance; otherwise cost is 1.0 everywhere and the trend
   is an artifact. Calibration (`results/gate13_probe40*`) fixed world_step=40 and
   magnitude=0.05 m, at which H=1 recovers.

## Reproduce end-to-end

```bash
cd /data1/liborui/fastwam_bench
bash scripts_setup/gate13_all.sh        # sweep -> psnr arm -> analyze -> figure -> report
```

No-GPU checks (fast, no model):

```bash
python scripts_setup/gate13_validate_goal_aware.py      # disturbance cannot satisfy the goal
python scripts_setup/test_gate9_intervention.py         # 67 unit checks (trigger + guard)
```

## Honest limitations

- `world_step=40` restricts H to divisors of (40-30)=10, i.e. {1,2,5,10}. The released
  default is H=10, so the sweep spans 1x..10x compression of the published commitment.
- The trigger requires H | (world_step-30); this keeps the absolute intervention step
  identical across H, at the cost of not reaching H=15/30 at this world_step.
- Success is binary and coarse; the mechanism columns (`stale`, `contaminated`) carry the
  argument as much as the success rates do.
