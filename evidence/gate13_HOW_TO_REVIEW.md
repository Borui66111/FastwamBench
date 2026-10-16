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
| `evidence/gate13_commitment_cost.png` | three-panel figure: success vs H, stale vs H, divergence vs H (generated) |
| `results/gate13_main/gate13_summary.json` | machine-readable per-(task,H) numbers + `_config` |
| `results/gate13_main/<task>/H<h>/<arm>_s<seed>/records.jsonl` | raw per-step records |

## Headline finding (main sweep, 2026-10-17)

The commitment is **real** but its **task-level cost saturates immediately** — the two must be
reported separately, which is why the figure has three panels:

| H | control | disturbed | cost | stale executed | mean steps (ctl→dis) | timeouts | stale-window divergence |
|---|---|---|---|---|---|---|---|
| 1 | 1.00 | 0.80 | +0.20 | 1 | 104 → 176 | 0 → 2 | 0.002 m |
| 2 | 1.00 | 0.80 | +0.20 | 2 | 105 → 175 | 0 → 2 | 0.011 m |
| 5 | 1.00 | 0.80 | +0.20 | 5 | 102 → 173 | 0 → 2 | 0.043 m |
| 10 | 1.00 | 0.80 | +0.20 | 10 | 104 → 173 | 0 → 2 | 0.045 m |

- **Mechanism confirmed:** the model executes exactly H stale actions (panel B), and the
  end-effector diverges from the moved object *during* that window by an amount that grows
  with H (panel C) — the direct signature of acting on a world that no longer exists.
- **Task cost is flat in H:** a disturbed episode is usually still solvable, it just costs
  ~70 extra steps and sometimes exhausts the 400-step budget. That re-acquisition cost is
  set by how hard the displaced object is to re-grasp, which does not depend on H — so the
  horizon effect is *masked* at this displacement, not absent.
- **The decisive follow-up** is the magnitude ladder (`results/gate13_lad002` / `_lad003`,
  H=1 vs H=10 at 0.02 / 0.03 m): at a small displacement H=1 replans away the problem almost
  perfectly (probe: 2/2, 106 steps vs control 102), so the cost of a long commitment is no
  longer hidden behind the re-grasp cost.

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
