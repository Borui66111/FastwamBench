# fastwam_bench

A controlled-intervention harness for measuring the **world-modeling commitment** of a World Action
Model (WAM). The target model is **FastWAM**; the environment is **LIBERO-Safety**.

The core question this repo answers: *when the world changes underneath a World Action Model, does the
model behave like one — i.e. does its risk/planning actually depend on the world state — or does it just
execute an open-loop action chunk?*

---

## What this is

A WAM predicts future world states and actions jointly. That commitment is only meaningful if the model's
behaviour degrades in a specific way when the world it planned against stops being true. We test that
directly, rather than inferring it from task success alone (task success is far too coarse, especially at
the model's current absolute performance level).

**The intervention.** At a chosen replan boundary we deterministically displace a task object's world
state (via MuJoCo `qpos`, moved by a fixed delta). Nothing else changes. Two arms are then compared:

- **control** — recorder only, world untouched;
- **disturb** — the same run with a one-shot world-state displacement injected at `replan_idx=1`.

**Metrics.** For each arm we record, per step: executed action, replan index, step-in-chunk, and the full
env state (EEF position/quaternion, object poses). From those we derive the **stale window** (how many
steps of the pre-intervention plan get executed verbatim after the world has already changed), the
**first divergence** between arms, the **plan divergence** at the first post-intervention replan, and the
EEF-to-object distance trajectory.

---

## Layout

```
scripts_setup/          all runnable scripts (bring-up, gates, analysis) + unit tests
  gateA_env*.sh         environment bring-up (conda env, torch, editable install)
  gateB_libero*.sh      LIBERO-Safety install as the active `libero` package
  gateC_assets_download.sh   fetch + extract LIBERO-Safety assets
  gateD_render.py       headless render smoke test
  gate7*                reproduce the official FastWAM LIBERO rollout
  gate8*.sh             LIBERO-Safety obstacle_avoidance, no intervention
  gate9*                deterministic mid-chunk intervention + structured recorder
  gate11_sweep.sh       control-vs-disturbance sweep over replan_steps
  gate11_analyze.py     H3 divergence analysis (step-level, noise-floor aware)
  gate12_screen.sh      Gate 12A: baseline control-success screen (multi-GPU manager)
  gate12a_tasks.txt     Gate 12A task list (30 tasks: spatial/object/goal, 10 each)
  gate12a_aggregate.py  Gate 12A: results -> CSV + usable-task table (0.30 <= SR <= 0.90)
  gate12b_fidelity_audit.md   (in evidence/) command-parity + protocol audit vs the upstream README
  gate13_run.py         Gate 13: cross-horizon commitment-cost sweep (paired control/disturb)
  gate13_analyze.py     Gate 13: per-H success, stale window, divergence, PSNR, contamination
  gate13_figure.py      Gate 13: 3-panel figure (success | stale==H | stale-window divergence)
  gate13_report.py      Gate 13: reviewer-facing markdown report
  gate13_all.sh         Gate 13: one-command pipeline
  gate13_finish.sh      Gate 13: unattended finisher (waits for sweep -> ladder -> psnr -> report)
  gate13_validate_goal_aware.py  Gate 13: no-GPU proof the disturbance cannot satisfy the goal
  gate13_magcal.py      Gate 13: magnitude calibration summary across runs
  gate13b_figure_repeat.py      Gate 13B: repeated-strike figure (stale ratio | step cost)
  sync_patches.sh       export live FastWAM/ edits into tracked patches/
  test_gate9_intervention.py   unit tests (84 checks) for the intervention mechanism + goal-aware guard
patches/                our changes to the upstream FastWAM tree (it is NOT vendored here)
evidence/               curated text results + a compressed bundle of the raw Gate 11 records
my_test/fastbench_handoff/   the onboarding brief + live STATE.md / CHANGELOG.md
server_notes/           host/GPU inventory captured during bring-up
PUSH.md                 how to push this repo to a remote
REMOTE_REVIEW.md        the remote collaborator's brief: status, interpretation guardrails, Gate 12-14 plan
```

**Nothing upstream is vendored.** `FastWAM/` and `LIBERO-Safety/` are separate clones and are gitignored.
Our modifications to FastWAM are exported as a patch in `patches/`.

---

## Quickstart

Everything below assumes the fastbench project root as the working directory.

### 1. Upstream checkouts (not tracked here)

```bash
git clone https://github.com/yuantianyuan01/FastWAM         FastWAM
git clone https://githubfast.com/LIBERO-SAFETY/LIBERO-Safety LIBERO-Safety   # mirror host; github.com was blocked here
```

Our changes against FastWAM `7faa711` (recorded in `patches/BASE_COMMIT.txt`):

```bash
git -C FastWAM apply ../patches/0001-fastbench-harness.patch
```

That patch touches only three files, all marked `[fastbench]`:

- `configs/sim_libero.yaml` — Gate 9 recorder/intervention keys;
- `experiments/libero/eval_libero_single.py` — replan/step counters, world-intervention call site, step-level recording;
- `experiments/libero/libero_utils.py` — level-aware task-file resolution (`<suite>/L<level>/`).

It also adds one new file, copied for convenience to `patches/fastbench_intervention.py`
(the canonical location is `FastWAM/experiments/libero/fastbench_intervention.py`).

### 2. Environment

```bash
bash scripts_setup/gateA_env.sh      # conda env `fastbench` (py3.10) + torch 2.7.1+cu128 + pip install -e FastWAM
bash scripts_setup/gateB_libero.sh   # LIBERO-Safety as the active `libero` package
bash scripts_setup/gateC_assets_download.sh
python scripts_setup/gateD_render.py # headless EGL render smoke test
```

Checkpoints (FastWAM release ckpt + Wan2.2-TI2V-5B base) and the LIBERO-Safety assets are large downloads
and are not tracked; the `gateA`/`gateC` scripts plus `verify_wan_components.py` show exactly how they were
fetched and verified.

### 3. Run a gate

```bash
# official FastWAM LIBERO rollout
bash scripts_setup/gate7f_readme_flags.sh

# intervention sweep (control vs disturbance, replan_steps 1/5/10)
TRIALS=2 RS_LIST="1 5 10" bash scripts_setup/gate11_sweep.sh
python scripts_setup/gate11_analyze.py

# Gate 12A: baseline control-success screen (which tasks can actually succeed?)
TASKFILE=scripts_setup/gate12a_tasks.txt TRIALS=5 GPUS=5,7 NGPU=2 \
  bash scripts_setup/gate12_screen.sh
python scripts_setup/gate12a_aggregate.py

# Gate 13: the headline experiment — cost of world-model commitment vs replan horizon
bash scripts_setup/gate13_all.sh          # sweep -> magnitude ladder -> psnr -> report
# or just the sweep:
python scripts_setup/gate13_run.py --tasks libero_spatial:0,libero_object:0 \
  --horizons 1,2,5,10 --seeds 1 --trials 5 --magnitude 0.05 --world-step 40 --tag main
```

---

## Gate 13 — what a mid-chunk world change actually costs (the headline result)

`replan_steps` **is** the commitment horizon H: the eval executes `action_chunk[:replan_steps]`
open-loop before replanning. The released config ships H=10. Gate 13 sweeps H over {1,2,5,10}
with a paired `control` / `disturb` design — the disturbance teleports the task object
**away from its goal** (goal-aware: the body is resolved from the task's own goal state and every
candidate displacement is validated against the env's own `_check_success()`, so it can never
accidentally solve the task) at the same absolute step for every H.

**Result (libero_spatial t0, n=10/cell, 0.05 m at step 40):**

| H | control | disturbed | cost | stale executed | stale-window divergence | extra steps on success |
|---|---|---|---|---|---|---|
| 1 | 1.00 | 0.80 | +0.20 | 1 | 0.002 m | +9 |
| 2 | 1.00 | 0.80 | +0.20 | 2 | 0.011 m | +6 |
| 5 | 1.00 | 0.80 | +0.20 | 5 | 0.043 m | +7 |
| 10 | 1.00 | 0.80 | +0.20 | 10 | 0.045 m | +4 |

Two things must be reported separately, and they behave differently:

1. **The commitment is real and scales exactly with H.** The model executes precisely H actions
   chosen for the pre-change world (`stale executed` = H for every H, 0 contaminated episodes out
   of 160). This is a property of the fixed-horizon execution protocol, verified per episode.
   An earlier claim that the end-effector *diverges further* at longer H did not survive a fair
   test: the divergence was measured over a window of length H, so it grew mechanically. At a
   fixed lag after the intervention it is the same for every H (+0.0016..+0.0020 m at k=1).
2. **The task-level cost is bimodal, not graded.** A disturbed episode either recovers about as
   fast as control (+4..+9 steps, and *not* monotone in H) or it fails outright by exhausting the
   400-step budget. Because the displacement has the same size at the same absolute step for every
   H, the difficulty of re-acquiring the object is roughly H-independent — so at this displacement
   the success cost saturates and *masks* the horizon effect rather than showing it is absent.

The magnitude ladder (0.02 / 0.03 m, H=1 vs H=10, `evidence/gate13_magnitude_ladder.md`) tested that
reading and **did not rescue the strong claim**, but it did produce a clean result of its own:

- At **0.02 m the world change is fully absorbed**: 20/20 disturbed episodes succeed, both tasks,
  both horizons, steps indistinguishable from control. So the commitment penalty is not a fixed
  property of the protocol — it is gated by whether the displacement exceeds what the next replan
  can correct.
- At **0.03 m the object task crosses that threshold** (10/10 → 4/10 pooled over H, Fisher exact
  p=0.011) while the spatial task still absorbs it completely (10/10). The threshold is
  **task-dependent, not horizon-dependent**: a small can into a basket is fragile; a bowl onto a
  plate is not.
- Within the object task at 0.03 m, H=1 (1/5) vs H=10 (3/5) is p=0.52 — the apparent *reverse*
  trend is noise. So the H-dependent component is smaller than this design can resolve, not merely
  masked. Resolving a 0.10 success difference at 80% power needs ~300 episodes per arm.

**The world model's own prediction (PSNR arm) — the one place the horizon effect survives.**
With `visualize_future_video=true` the model renders its predicted future and the eval scores it
against reality. Two facts:

- *Prediction fidelity collapses with lookahead, with no intervention at all*: **39.6 dB at lag 0 →
  27.9 dB at lag 4 → 27.1 dB at lag 8**. The model is accurate at the moment of planning and drifts
  badly within a single committed chunk.
- *A mid-chunk world change costs a fixed amount, and the amount does NOT scale with H*: −4.42 dB at
  H=5 vs −4.40 dB at H=10 (lag 4, clip-isolated, `results/gate13_psnr_clip`, n=6/cell). The lag-0
  delta is exactly 0.00 dB in both arms, which is the internal validity check for the measurement.

**Method note (a claim that was withdrawn).** The first reading of this arm reported a 4.7x
effect at H=10 vs H=1. That comparison was invalid: `_get_future_frame_capture_steps` derives the
scored frame count from `replan_steps`, so H=1 was scored only at lag 0 and H=10 at lags 0/4/8.
`episode_frame_psnr` records per-frame PSNR, which is what makes a matched-lag comparison valid
(lag 4 = frame index 1 for every H whose chunk covers 4 steps). `EVALUATION.psnr_fixed_lags`
requests fixed lags but cannot exceed the clip, which is bounded by the executed chunk — verified:
H=1 still yields one frame even when lags 0,4,8 are requested. See
`evidence/gate13_psnr_matched_lag.md`.

Reviewer entry points: `evidence/gate13_HOW_TO_REVIEW.md` (claim → artifact → command, with what is
and is not claimed), `evidence/gate13_commitment_cost.md` + `.png` (generated),
`evidence/gate13_psnr.png` (world-model signal), and
`evidence/gate13_design_checks/DESIGN_FINDINGS.md` (the four design flaws that were found and
fixed, with raw captures).

---

## Gate 13B — does the cost compound when the world changes repeatedly?

Gate 13 changed the world once. One strike can only invalidate H actions once, and re-acquisition
absorbs it — so a horizon effect has no room to show. Gate 13B repeats the strike four times (absolute
steps 40/50/60/70) at **0.01 m**, below the 0.03 m threshold where Gate 13 showed a single strike
starts to fail episodes. Each strike leaves H fresh stale actions, so if staleness were the cost
driver the effect would now compound instead of being absorbed.

Three design corrections were required and are part of the result:

1. **A strike must never move the object toward the goal.** The first version mirrored alternate
   strikes; the data showed struck episodes finishing in 51 steps vs ~100 for control — the odd
   strike was *helping*. Every strike now displaces along the goal-away direction only.
2. **The safety cap must be a drift budget, not an absolute goal distance.** Capping absolute
   distance silently allowed exactly one strike per episode, which turned the repeat run back into
   the Gate 13 single-strike test (stale = H, identical cost). The cap now bounds total drift
   measured from the first strike, so all four strikes land.
3. **A silently dead arm must be detected.** A disturb cell can record zero strikes and then produce
   step counts identical to control — a clean-looking cost of exactly 0.00 for a manipulation that
   never happened. Every episode still completes, so nothing about success reveals it. The analyzer
   now prints `INTERVENTION NEVER FIRED` for any disturb cell with `strike_count=0` throughout, and
   `INCOMPLETE CELLS` when a cell has fewer episodes than `run_config.json` requested.

**Result (n=6/cell, 0.01 m, 4 strikes, `evidence/gate13b_repeated_strikes.md`):**

| task | H | stale actions | ratio | control | disturbed | step cost | Welch p |
|---|---|---|---|---|---|---|---|
| libero_object t0 | 1 | 4.0 | — | 6/6, 178.7 | 5/6, 268.0 | +89.3 | 0.52 |
| libero_object t0 | 10 | 40.0 | 10.0x | 6/6, 164.3 | 6/6, 297.3 | +133.0 | |
| libero_spatial t0 | 1 | 3.3 | — | 6/6, 107.5 | 6/6, 94.5 | -13.0 | 0.34 |
| libero_spatial t0 | 10 | 32.7 | 9.9x | 6/6, 103.8 | 6/6, 137.3 | +33.5 | |

**10x the stale actions produces no measurable success cost** (object 5/6 vs 6/6, Fisher p=1.0;
spatial 6/6 vs 6/6). Effort leans the expected way on both tasks (+133 vs +89, +33.5 vs −13) but with
n=6 and sd 29–96 it cannot be separated from noise. `strike_count` in the records shows a mean of 3.3
(spatial H=1) and 4.0 (everything else). The shortfall is **early success, not a dropped strike**: two
spatial H=1 episodes succeeded at step 57, before the strikes scheduled at steps 60 and 70 — so those
strikes were never due. The drift budget is not binding at 0.01 m.

**But every one of these strikes landed before the object was ever lifted.** Reconstructing per-episode
lift time from `state.bodies` in the raw records: **24 of 24 struck episodes had all strikes land
pre-grasp** (spatial lifts at steps 54–114, object at 121–295; strikes are fixed at 40/50/60/70). So
the stale actions here were all *approach* actions, and invalidating an approach action is
recoverable by construction — the robot simply re-approaches. The regime where a stale action is
actively harmful (committing to a carry trajectory after the object has been displaced out of the
gripper) was never entered.

So the cost of a world change is set by **whether the next replan can recover at all**, not by how
many actions were committed to the old world. Staleness is a real, exactly-countable property of the
protocol that does not by itself predict failure. This is a bounded result: it holds for
approach-phase staleness. Testing the harmful regime needs a strike triggered on grasp detection
rather than at a fixed step. `gate13_analyze.py` reports this automatically as
`STRIKES LANDED BEFORE THE GRASP`.

---

## Three footguns that MUST be handled (all three were silent)

These are the three things that will waste your day if you don't know them:

1. **`EVALUATION.sigma_shift=1.0`.** The config default is `null`, which falls through to an internal
   default of `5.0`. The official README pins `1.0`. With the wrong value, rollouts silently fail at
   ~0% success — the model is fine, the sampler is not. (This is what caused an entire "0% success"
   investigation early on; see `my_test/fastbench_handoff/CHANGELOG.md`.)

2. **`seed=<N>` (top-level, `N>0`).** The eval only calls `set_global_seed` when `cfg.get("seed") is not
   None`. With no seed, diffusion sampling noise differs on every invocation, so two runs of the *same*
   configuration are different trajectories from step 0 — which makes any cross-run or cross-arm
   comparison meaningless. `seed=0` is rejected (`set_global_seed` asserts strictly inside the uint32
   bounds). **Any comparison run must pin the seed**; the Gate 11 sweep does, and the analyzer reports the
   pre-intervention divergence as an explicit noise floor.

3. **The vendored robosuite OSC config.** `LIBERO-Safety/third_party/robosuite-1.4/robosuite/controllers/
   config/osc_pose.json` is **modified** relative to stock robosuite 1.4.0: `output_max` is
   `[2,2,2,2,2,2]` / `kp 750` instead of the official `[0.05,0.05,0.05,0.5,0.5,0.5]` / `kp 150`. The
   `OSC_POSE` controller maps policy actions in `[-1,1]` to Cartesian deltas, so the fork scales
   translation **40x** too large. The released FastWAM checkpoint was trained on official LIBERO demos,
   so on this fork it flails: 6/150 (4%) instead of ~99%. **Restore the official values before any
   LIBERO run** — `patches/osc_pose.official.json` is a drop-in replacement (backup: `osc_pose.json.forkbak`).
   With it restored, `libero_spatial` t0–t3 all score 5/5. Full write-up: `evidence/gate12d_rootcause.md`.

Also worth knowing: the eval **skips any task that already has a result JSON** in the output dir, so a
re-run silently does nothing unless you use a fresh `output_dir`.

---

## Results

`evidence/gate11_analysis.txt` is the full analysis. Headline finding (obstacle_avoidance L0 task 0,
2 trials, `seed=1`, six arms all completed):

| replan_steps | stale window | divergence gap | plan divergence (chunk-mean L1) | EEF-obj min dist (ctl / dist) |
|---|---|---|---|---|
| 1  | 1  (t=31)    | 1  | 0.3848 | 0.0781 / 0.1494 |
| 5  | 5  (t=35-39) | 5  | 0.1100 | 0.1832 / 0.2398 |
| 10 | 10 (t=40-49) | 10 | 0.0989 | 0.0689 / 0.1709 |

- `pre_iv_max_l1 == 0.0` for both episodes at every setting — the arms are bit-identical up to the
  intervention, confirming the seeding fix held across the whole sweep.
- `divergence_gap == stale_window == replan_steps` exactly at all three granularities: the policy
  executes the **entire** stale chunk verbatim and only re-plans at the next boundary.
- Plan divergence is 0.099-0.385 against a 0.005 noise floor — the plan genuinely changes once the
  displaced world is finally observed.
- Success is 0/2 in all arms including control, so this task yields no success-recovery signal; the
  evidence is behavioural, not success-based.

**Conclusion (H3, "Future-Reality Divergence"):** under fixed-horizon chunk execution, a world change cannot
affect the current action chunk until the next replanning boundary. The chunk planned against the old world is
executed unchanged, the full stale window is paid, and at the first post-intervention replan the newly generated
plan differs from control (0.099-0.385 vs a 0.005 noise floor).

This is deliberately **not** stated as *"the model chooses to execute stale actions for N steps."* Because the
intervention is injected **after** the chunk has been planned and the model cannot re-query the environment until
the next boundary, `divergence_gap == stale_window == replan_steps` follows from the execution protocol — it is a
harness-correctness property, not a model property. The model-side content is (a) the magnitude of the post-replan
plan divergence and (b) the disturbed arm's behaviour afterwards (it stays further from the object at closest
approach, 0.149-0.240 m vs 0.069-0.183 m).

What this result does **not** support yet: reliable recovery, an intervention-caused success drop, or any
WAM-vs-VLA claim. The current task is 0% success in both arms, so it cannot yield a recovery signal — see
`REMOTE_REVIEW.md` for the Gate 12-14 plan that fixes this.

---

## Provenance

- FastWAM: `github.com/yuantianyuan01/FastWAM` @ `7faa711`
- LIBERO-Safety: `githubfast.com/LIBERO-SAFETY/LIBERO-Safety` @ `19ec8df2` (the host recorded in the local clone's
  remote — a mirror, used because github.com was blocked on this machine)
- FastWAM weights: `yuanty/fastwam` (release checkpoint), base model `Wan-AI/Wan2.2-TI2V-5B`
- Upstream components remain under their own licenses; this repo contains only our harness, patches,
  and results.
