# Gate 13 — how to review this experiment

## What is claimed, and what is NOT

**Claimed (supported by the data):**
- A mid-chunk world change is **expensive**: success drops 15-60 points, steps to success
  rise 60-100%, and failures are 400-step timeouts.
- The model really does execute **exactly H stale actions** chosen for the pre-change world
  (stale executed = H at H=1,2,5,10; 0/160 contaminated episodes).
- On `libero_spatial`, the end-effector diverges from the moved object during that stale
  window by an amount that **grows with H** (0.002 → 0.011 → 0.043 → 0.045 m).

**NOT claimed (and this report says so explicitly):**
- That a longer commitment costs more *task success*. Pooled cost is +0.30, +0.40, +0.15,
  +0.25 at H=1,2,5,10 — **not monotone**. At n=10 the binomial noise floor is ±0.25, so the
  data neither support nor refute a small H effect. This is a **powered negative result**,
  not evidence of no effect.

## The one-paragraph version

FastWAM commits to a chunk and executes it open-loop, so a world change mid-chunk does make
it act on a stale world — measurably, H actions' worth. But because it replans at the next
boundary and the object is still visible, it recovers, and the recovery cost is dominated by
re-acquiring the object rather than by how many stale actions it ran. So the horizon effect
is real at the action level and invisible at the task level at this sample size.

## Artifacts

| file | what it is |
|---|---|
| `evidence/gate13_commitment_cost.md` | generated report: tables, CIs, interpretation, power note |
| `evidence/gate13_commitment_cost.png` / `.pdf` | 3-panel figure (success / stale / divergence vs H) |
| `results/gate13_main/gate13_summary.json` | machine-readable per-(task,H) numbers + `_config` |
| `results/gate13_main/*/H*/*/records.jsonl` | raw per-episode records (the ground truth) |
| `evidence/gate13_design_checks/` | the four design flaws + raw probe/validation/unit captures |
| `results/gate13_lad00{2,3}/` | magnitude ladder (0.02 / 0.03 m, H=1 vs H=10) |
| `results/gate13_psnr/` | predicted-future-vs-reality PSNR arm |

## Reproduce

```bash
cd /data1/liborui/fastwam_bench
PY=/data1/liborui/.conda/envs/fastbench/bin/python

# main sweep (2 tasks x H{1,2,5,10} x 2 seeds x 2 arms x 5 trials = 32 jobs)
$PY scripts_setup/gate13_run.py --tasks libero_spatial:0,libero_object:0 \
  --horizons 1,2,5,10 --seeds 1,2 --trials 5 --magnitude 0.05 --world-step 40 --tag main

# analyze + artifacts
$PY scripts_setup/gate13_analyze.py results/gate13_main
$PY scripts_setup/gate13_report.py results/gate13_main/gate13_summary.json \
  evidence/gate13_commitment_cost.md
$PY scripts_setup/gate13_figure.py results/gate13_main/gate13_summary.json \
  evidence/gate13_commitment_cost.png
```

## Verify the experiment is valid (do these first)

1. `$PY scripts_setup/test_gate9_intervention.py` → 67 checks pass. Covers the absolute-step
   trigger and the goal-aware guard.
2. `$PY scripts_setup/gate13_validate_goal_aware.py` → no model needed; proves the
   disturbance does NOT satisfy the task goal (the original design flaw).
3. In any `records.jsonl`: `stale` count == H, and `intervention.post_iv_success == false`.
4. Control success is 1.00 in every cell — the environment (after the OSC fix) is healthy.

## Four design flaws that were found and fixed (each had silently invalidated the run)

1. **The disturbance completed the task.** `[+0.06,+0.06,0]` teleported the bowl onto its
   plate (goal = `on(bowl, plate)`, plate at +x/+y), so the episode ended with success at the
   intervention step and `stale` read 1 instead of 10. Now goal-aware: the body is resolved
   from the task's own goal state, displaced *away* from the target, validated against the
   env's success predicate, and reverted if it contaminates.
2. **The disturbance was unrecoverable at every horizon.** At `world_step=60` the object was
   already held aloft, so teleporting it forced a re-grasp no horizon could do; cost
   saturated at 1.0 everywhere. Moved to `world_step=40` (mid-approach).
3. **A falsy-zero bug** (`float(x or 0.10)`) promoted a legitimate 0.0 magnitude to 0.10, so
   the no-op control silently ran a real displacement. The no-op now reproduces control.
4. **The figure crashed** on the `_config` key and its titles claimed "success collapses"
   when the data is flat. Titles are now generated from the data.

## Honest limitations

- Two tasks, one seed pair, 5 trials → n=10 per (task,H). Underpowered for a 0.1 effect
  (~300 episodes/arm would be needed).
- `libero_object` divergence is flat/slightly negative: the arm was already heading toward
  the object's new position, so the misdirection signature is task-dependent.
- The disturbance is a teleport, not a physical push. It is instantaneous and cannot be
  observed before the next replan — which is exactly the point of the design, but it is
  also the strongest possible version of the intervention.
