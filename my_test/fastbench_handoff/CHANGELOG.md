# Changelog

## 2026-10-17 — Gate 13: cross-horizon commitment-cost sweep (headline experiment)

**Goal.** Turn the project thesis into a measured result: a World Action Model plans a chunk,
executes it open-loop for `replan_steps` steps, then replans. If the world changes mid-chunk,
the remaining actions were chosen for a world that no longer exists. Measure that price as a
function of the commitment horizon H — the *Future-Reality Divergence* framing from
`REMOTE_REVIEW.md` (a property of fixed-horizon chunk execution, not a claim about intent).

**New machinery.** `scripts_setup/gate13_run.py` (paired control/disturb sweep over H, `queue.Queue`
GPU pool, resumable), `gate13_analyze.py` (per-H success/cost/stale/contamination/PSNR),
`gate13_figure.py`, `gate13_report.py`, `gate13_all.sh` (unattended 3-stage pipeline),
`gate13_validate_goal_aware.py`.
Harness: a new **absolute-step trigger** `+EVALUATION.intervention_world_step` (fires at step
`t == world_step` regardless of H, so a cross-horizon sweep has no confound) and a
**goal-aware disturbance**.

**Design flaw found and fixed while canarying.** The first canary reported `stale=1` at H=10
because the fixed displacement `[+0.06,+0.06,0]` teleported the bowl *onto the plate* — the goal
is `on(akita_black_bowl_1, plate_1)` and the plate sits at +x/+y — so `_check_success()` returned
True at the intervention step and the episode ended immediately (t=60 = the trigger step).
The disturbance is now resolved from the task's own goal state: the manipulated body is mapped
from the goal object, the displacement points *away* from the goal target, and the result is
validated against the env's own `_check_success()`; a contaminating candidate is reverted and the
next direction is tried. Per-episode `post_iv_success` / `rejected_candidates` are recorded, and
the analyzer prints a `bad` (contaminated) count per cell.

**Corrected canary (H=10, seed 1, 2 trials).**

| task | arm | success | stale executed | contaminated |
|---|---|---|---|---|
| libero_spatial t0 | control | 2/2 | 0 | 0 |
| libero_spatial t0 | disturb | 0/2 | 10 | 0 |
| libero_object t0 | control | 2/2 | 0 | 0 |
| libero_object t0 | disturb | 1/2 | 10 | 0 |

`stale executed == H` is the mechanism claim, verified end-to-end. Also fixed an analyzer bug
where `meta.setdefault` locked in `body=None` from the control arm before the disturb arm could
record the resolved body.

**Evidence.** `evidence/gate13_design_checks/` (raw probe + validation + unit-run outputs).

## 2026-10-16 (evening) — ROOT CAUSE of the 0–4% success gap: wrong OSC action scaling

**Symptom.** 30-task control screen = 6/150 (4%) on standard LIBERO vs the released README's 98.55%, on the same
checkpoint and flags. Gate 12B cleared the harness (config, checkpoint contents, task files, init states,
observations) and Gate 12C cleared our eval flags (1/20 upstream-flags vs 3/20 ours at n=20).

**Finding.** The box runs FastWAM's stack *via the LIBERO-Safety clone*, whose vendored robosuite
(`LIBERO-Safety/third_party/robosuite-1.4`) is a **fork with one functional change**: `controllers/config/osc_pose.json`
sets `output_max [2,2,2,2,2,2]` / `kp 750` where stock robosuite 1.4.0 sets `[0.05,0.05,0.05,0.5,0.5,0.5]` / `kp 150`.
OSC_POSE scales policy actions in [-1,1] into Cartesian commands, so the fork commands **40× more translation** and
**4× more rotation**, with 5× stiffer gains. A policy trained on official-LIBERO statistics flails — exactly the
low-but-nonzero success we saw.

*(How it was found: `pip download robosuite==1.4.0 --no-binary :all:` for the stock sdist, then `diff -rq` against the
fork after stripping CRLF — every other file is byte-identical.)*

**Confirmation.** `robosuite.controllers.controller_factory.load_controller_config('OSC_POSE')` inside the `fastbench`
env returns `output_max [2,2,2,2,2,2]`, `kp 750` — the fork's file is really loaded, not dead code.

**Fix.** `osc_pose.json` restored to the official 1.4.0 values (original preserved at `osc_pose.json.forkbak`; the fix
also ships as `patches/osc_pose.official.json`). Post-fix: `libero_spatial` t0 **5/5** and `libero_object` t0 **5/5**
(previous: 3/20 and 0/20 at n=20); spatial t0–t3 all 5/5.

**Impact.** Gates 8/11/12A's low success on standard tasks is a controller artifact, not a model property. Gate 9's
intervention mechanism stands (45/45 unit tests, `pre_iv_max_l1=0.0`) but its behaviour needs a post-fix re-run.
**Gate 13 is unblocked.** Files: `evidence/gate12d_rootcause.md`; post-fix screen in `results/gate12a_screen_fixed`.

## 2026-10-16 (later) — Gate 12A screen + 12B audit + 12C flag A/B: the reproduction gap

**What happened**
Gate 12A screened control success on 30 standard-LIBERO tasks (libero_spatial / object / goal × 10 tasks,
5 trials each, GPUs 5+7) using the exact command the FastWAM README documents for the released checkpoint.

**Result — we are ~25x below the published number**

| suite | tasks | success | rate |
| --- | --- | --- | --- |
| libero_spatial | 10 | 5/50 | 10% |
| libero_object  | 10 | 0/50 | 0% |
| libero_goal    | 10 | 1/50 | 2% |
| **total** | **30** | **6/150** | **4.0%** |

The README claims 98.55% average for this checkpoint (IDM mode, 40 tasks × 50 episodes).
Only `libero_spatial` t0/t1 cleared the 30% "usable" bar at 5 trials — and Gate 12C showed that was
small-sample luck (true rate 5–15% at n=20).

**Gate 12B (fidelity audit, `evidence/gate12b_fidelity_audit.md`) — everything verifiable is faithful**
- reference command == README; resolved config == repo defaults (`action_horizon` 32, 10 inference steps,
  `num_steps_wait` 30, `replan_steps` 10, `binarize_gripper` true, 2 cameras → 224×448 horizontal concat);
- checkpoint complete: `mot.mixtures.video.*` (825 keys) AND `mot.mixtures.action.*` (824 keys) + `proprio_encoder`;
- standard suites resolve to the ORIGINAL bddl/init filenames (no `_add_*` augmentation), 50 init states,
  file order — same as upstream;
- decoded observations are valid, bright renders (not black/garbage);
- failures are "ran out of the 400-step budget", not crashes.
- Forced offline adaptations (NOT optional deviations): `model.redirect_common_files=false` (else the runtime
  401s trying to fetch Wan2.2 from HF), `model.action_dit_pretrained_path=null` +
  `model.skip_dit_load_from_pretrain=true` (the ActionDiT backbone file was never generated locally).

**Gate 12C (flag A/B, `scripts_setup/gate12c_ab.sh`) — our flags are exonerated**

| task | upstream-flags arm | our-flags arm | README |
| --- | ---: | ---: | ---: |
| libero_spatial t0 | 1/20 (5%) | 3/20 (15%) | 99.0% |
| libero_object t0  | 0/20 (0%) | 0/20 (0%) | 99.6% |

Both arms sit at the floor ⇒ `load_text_encoder=true` / `compile_action_infer=false` / `seed=1` are not the
cause. **The gap is environmental.**

**Leading suspect:** this box runs **LIBERO-Safety** (editable `libero` + a vendored
`robosuite-1.4` fork, `site-packages/__editable__.robosuite-1.4.0.pth`), while FastWAM's README (line 303)
explicitly says to install the **official LIBERO** environment. LIBERO-Safety advertises drop-in
compatibility and its standard-suite bddl/init files are the upstream ones, but the vendored robosuite fork
and the standard-suite assets are unverified variables.

**Next step (needs go-ahead):** rebuild the eval environment against official LIBERO + stock `robosuite==1.4.0`
in a *separate* env and re-run the README command on `libero_spatial` t0 / `libero_object` t0 at 20 trials.
Resolving this is the gate to Gate 13 — the stale-commitment cost cannot be measured behaviourally while the
control arm sits at ~5%.

**New artifacts:** `scripts_setup/gate12_screen.sh`, `gate12a_aggregate.py`, `gate12a_tasks.txt`,
`gate12a_canary_tasks.txt`, `gate12c_ab.sh`, `gate12c_tasks.txt`, `list_scene_bodies.py`,
`gate13_paired.sh`, `gate13_analyze.py`, `evidence/gate12b_fidelity_audit.md`,
`results/gate12a_screen_summary.csv`.

## 2026-10-16 — repo published for remote collaboration; Gate 11 interpretation corrected

**Issue**
The harness, patches and Gate 11 evidence existed only on the GPU server, so a remote collaborator had nothing to
review. Separately, the Gate 11 write-up used a framing ("the model commits to a plan built on a world that no longer
exists") that overstates what the experiment shows: the stale window is a property of the execution protocol, not of
the model.

**Reason**
Gate 12–14 (baseline task screening, first recovery result, WAM-specific comparison) will be split between the server
worker (GPU runs, raw evidence) and the remote side (review, metric validity, plotting), which needs a shared source
of truth rather than chat history.

**Fix**
- Initialised `/data1/liborui/fastwam_bench` as a standalone git repo and pushed it to
  `https://github.com/Borui66111/FastwamBench` (public): 55 tracked files, ~720 KB. The ~83 GB of downloaded payloads
  (65 GB checkpoints, LIBERO-Safety assets, rollouts) are gitignored and re-fetched by the setup scripts.
- Added `README.md`, `.gitignore`, `PUSH.md` (remote/push procedure) and `evidence/` (gate7 + gate11 analysis text).
- Exported the FastWAM modifications as `patches/0001-fastbench-harness.patch` (3 modified files + the new
  `fastbench_intervention.py`) against base commit `7faa711`, so no upstream tree needs vendoring.
- Bundled the raw Gate 11 records as `evidence/gate11_records.tar.gz` (6 × `records.jsonl`, 44 MB → 3.8 MB).
- **Interpretation guardrail adopted** (raised by the remote reviewer). Gate 11 is a *Future-Reality Divergence*
  probe, not evidence that "the model chooses to execute stale actions for N steps": the intervention is injected
  *after* the chunk is planned and the model cannot re-query the environment until the next boundary, so
  `divergence_gap == stale_window == replan_steps` is a harness-correctness check by construction. README.md and
  STATE.md reworded accordingly, and the claims that are *not* yet supported (recovery, success drop, WAM-vs-VLA,
  "future modeling improves robustness") are now listed explicitly.
- Recorded the next plan (Gate 12A screening / 12B fidelity / 13 recovery / 14 WAM-specific) in STATE.md, and adopted
  the reviewer's per-gate format: `STATUS / EVIDENCE / INTERPRETATION / OPEN QUESTION / NEXT ACTION`.

**Verification**
- Remote `main` matches the local commit, and all three remote branches (`main`, `remote-review`,
  `chatgpt-write-test`) point at the same commit — no divergent work to reconcile.
- Secret scan across every tracked directory before the first commit: no tokens, keys or credentials.
- `patches/0001-fastbench-harness.patch` is byte-identical to the live `git -C FastWAM diff`, and
  `patches/fastbench_intervention.py` matches the live file (16,194 bytes) — the committed patch is current, not stale.
- The `.gitignore` excludes exactly the payload dirs (`git check-ignore` verified); largest tracked file is 40 KB.
- Note: git does **not** support trailing comments on `.gitignore` pattern lines — the first attempt silently failed
  to ignore `checkpoints/` and started hashing 83 GB. Comments now sit on their own lines.

## 2026-10-08 — New-server warm-start handoff

**Issue**
The project is moving from a disconnected/original server and a dependency-light prototype to a new GPU server. A fresh coding agent would otherwise need to reconstruct research intent, upstream code paths, metric definitions, installation order, and validation gates from chat history.

**Reason**
FastBench spans research design, FastWAM inference, LIBERO-Safety/MuJoCo simulation, intervention mechanics, evidence logging, and benchmark metrics. Missing context at handoff can produce scientifically invalid shortcuts (e.g. modifying the world before the action chunk is planned, conflating toy tests with real results, or reporting only task success).

**Fix**
Added:
- `AGENTS.md`: concise always-on research/engineering rules;
- `WARM_START.md`: detailed server setup, execution gates, code hook points, evidence schema, metrics, failure triage, and definition of done;
- self-contained copies of the current `STATE.md`, `REQUIREMENTS.md`, `INTEGRATION_PLAN.md`, prototype code/tests, and toy results.

**Verification**
- Cross-checked FastWAM upstream environment/evaluation path and current released checkpoint workflow.
- Cross-checked LIBERO-Safety installation/drop-in package behavior and benchmark registry structure.
- Reconciled handoff against existing FastBench prototype APIs and verified state documents.
- Handoff design follows a short always-loaded `AGENTS.md` plus detailed task/state docs to reduce agent rediscovery and instruction overload.

## 2026-10-15 — New-server bring-up: env, official FastWAM rollout, LIBERO-Safety harness

**Issue**
The warm-start handoff assumed no `libero`/`mujoco`/`robosuite` and blocked GitHub. The new server needed a working
FastWAM × LIBERO-Safety stack, an executed official rollout, and a first LIBERO-Safety rollout through FastWAM.

**Reason**
Gate 7 (baseline before any FastBench hooks) requires a *running* official evaluator; Gate 8 requires the
LIBERO-Safety level layout to be reachable through FastWAM's harness.

**Fix**
- Created conda env `fastbench` (py3.10, torch 2.7.1+cu128) and installed FastWAM editable; `libero` resolves to the
  LIBERO-Safety package via `libero_safety_path.pth`; assets extracted; `wand`/ImageMagick and headless EGL verified.
- Staged backbone + release checkpoints under `checkpoints/` and pointed DiffSynth at them with
  `DIFFSYNTH_MODEL_BASE_PATH` + `model.redirect_common_files=false` (the default HF redirect 404s on the mirror).
- Patched FastWAM's harness minimally for LIBERO-Safety (all marked `[fastbench]`, no-op for upstream suites):
  level-aware `resolve_task_file_path()` in `libero_utils.py`; level-aware init states and 600-step budgets for the
  safety suites in `eval_libero_single.py`.
- Ran the official recipe on `libero_spatial` task 0 (optional_idm, 5 trials) and on LIBERO-Safety
  `obstacle_avoidance` L0 task 0 (3 trials), plus an uncond-checkpoint run with `sigma_shift=5.0`.

**Verification**
- Gate 7 contract **passes**: evaluator completes, real rollout MP4s + result JSON written, meaningful verdicts.
- Gate 8 harness **works**: `obstacle_avoidance` L0 task 0 runs to completion through FastWAM with no intervention
  (630 steps/episode, MP4s saved).
- I/O fidelity independently verified: OSC action signs, gripper polarity, 8-D proprio layout, 7-D action layout,
  normalization stats, checkpoint↔model key naming (so `strict=False` drops nothing), `action_horizon=32`,
  `num_inference_steps=10`, `action_infer_mode=idm` default, camera concat/resize.
- World model confirmed sound: `visualize_future_video=true` → future-video PSNR ≈ 26.6 dB vs the real rollout.
- **Regression/open issue: measured success is 0/5 (libero_spatial t0) and 0/3 (obstacle_avoidance L0 t0) versus the
  README's claimed 99.0% Spatial.** 0/5 at p=0.99 is ~1e-9, so this is systematic. Because imagined futures track
  reality well, the fault is localised to action generation/conditioning rather than the dynamics backbone.
  Leading remaining causes: hand-assembled Wan2.2 VAE/umt5 components, or `instruction_type` seen/unseen.
  Not written up as a benchmark result until resolved.

## 2026-10-15 (later) — Gate 11 methodology bug: unseeded arms are not comparable

**Issue**
The Gate 11 control-vs-disturbance comparison was invalid as first written. `eval_single_process` calls
`set_global_seed` only `if cfg.get("seed") is not None`, and no gate script passed a seed, so the diffusion
sampler drew different noise in each invocation. The control and disturbance runs were therefore *different
trajectories from t=0* (cross-arm L1 ≈ 9e-3 at the very first step), not one trajectory with a single injected
world change. Every downstream step-by-step metric (divergence onset, EEF distance, object motion) was measuring
sampling noise as much as the intervention.

**Fix**
- `gate11_sweep.sh` now passes top-level `seed=$SEED`, default 1, to both arms. Note `seed=0` is rejected by
  `set_global_seed`, which asserts `0 < seed < 2**32-1` strictly.
- `gate11_analyze.py` measures the pre-intervention cross-arm L1 as an explicit noise floor and flags divergence
  only above `max(20x baseline, 5e-3)`, reporting the baseline in its output instead of assuming bit-equality.
- The embedded recovery analysis latched on an unreachable 0.05 m re-acquisition threshold (observed minimum is
  ~0.17-0.33 m for this gripper); it now latches at 0.12 m and the standalone analyzer reports min/final distance.

**Verification**
Canary (rs=10, 1 trial, seed=1): `pre_iv_max_l1 == 0.0` — the arms are bit-identical for all 40 steps before the
intervention and diverge exactly at the first post-intervention replan (gap = stale window = 10 steps). The fix is
confirmed, and the result is the clean H3 signature: the policy executes the full stale chunk verbatim and corrects
only at the next replanning boundary (plan chunk-mean L1 = 0.0989).

**Full sweep outcome** (`results/gate11_analysis.txt`, rs ∈ {1,5,10}, 2 trials each, seed=1, six arms all exit 0):
`pre_iv_max_l1 == 0.0` for both episodes at every setting; `divergence_gap == stale_window == replan_steps`
(1/5/10) exactly; plan divergence at the first post-intervention replan 0.385 / 0.110 / 0.099 — all far above the
0.005 noise floor, so the plan genuinely changes once the displaced world is observed. Success is 0/2 in every arm
including control, so this task yields no success-recovery signal (consistent with obstacle_avoidance L0 = 0/5); the
H3 evidence is behavioural — the stale chunk is paid in full and the disturbed arm stays further from the object at
closest approach (0.149–0.240 m vs 0.069–0.183 m control).

## 2026-10-15 — Root-cause of the 0% success regression + Gate 9 intervention/recorder

**Issue**
The 0% success above was systematic (0/5 at p=0.99 is ~1e-9). Two further unknowns blocked the project's actual
subject matter: there was no way to inject a controlled disturbance, and no structured evidence log to measure
recovery from one.

**Reason**
FastBench evaluates the *world-modeling commitment* of World Action Models through controlled interventions, not
task success alone (WARM_START §9). Without a deterministic intervention and a machine-readable trace, no H3 claim
is testable.

**Fix**
- **0% success ROOT-CAUSED**: `EVALUATION.sigma_shift` silently defaulted to `5.0`; the README pins **`1.0`** for the
  uncond checkpoint. Shift resolution is `shift = self.shift if shift_override is None else float(shift_override)`,
  so the config's `null` fell through to the wrong default. With `1.0` successes reappear (1/15 over 3 suites).
  Every eval invocation must now pass `EVALUATION.sigma_shift=1.0`.
- Added `FastWAM/experiments/libero/fastbench_intervention.py`: `apply_intervention` (mid-chunk action perturbation),
  `displace_object` / `maybe_displace_world` (one-shot **world-state** displacement of a free-joint object),
  `snapshot_state` (EEF + per-object pose), `StructuredRecorder` (JSONL), `summarize_chunk`, `resolve_intervention_cfg`.
- Wired into `eval_libero_single.py`: recorder init, per-replan intervention hook, per-step state capture, terminal
  episode record, and the §3.2 **stale-action metric** (steps executed from a plan made against a pre-intervention
  world).
- Config keys added under `EVALUATION.*` in `configs/sim_libero.yaml`; all inert by default.

**Verification**
- `scripts_setup/test_gate9_intervention.py` — 45 unit checks, all pass (determinism, mode semantics, recorder
  round-trip, qpos-address correctness, gating).
- Gate 9 end-to-end (`scripts_setup/gate9c_world_only.sh`, `results/gate9b_world_oa_t0/`): the displacement fires
  exactly once per episode at `replan_idx=1` with `applied=True` and an exact readback delta
  (`[-0.2703,-0.1434,0.9289] -> [-0.2103,-0.0834,0.9289]` for delta `[0.06,0.06,0.0]`); recorder wrote
  120 replan / 1200 step / 2 intervention / 2 episode_end events; `stale_action_steps=10` per episode.
- Control arm clean: `replan_idx` spans 0..5 and `step_in_chunk` 0..9, 0 world events, 0 stale steps.

**Bugs found and fixed during Gate 9 verification**
1. `current_replan_idx` was incremented *inside* `if predicted_future_frames is not None`, so with future-video off
   it stayed `-1` and the intervention could never match its target replan (`intervened steps: 0`). Now unconditional.
2. Same defect in `current_replan_step` (always `0`).
3. `displace_object` sliced `qpos[jnt:jnt+7]` using the *joint index* instead of the *qpos address*. They differ once
   non-free joints precede the object (bowl_1 is joint 9/qposadr 9, bowl_2 is joint 10/**qposadr 16**), so the write
   silently corrupted the wrong object. Now resolved via `jnt_qposadr`.
4. `maybe_displace_world` returned a `replan_idx` key that collided with the explicit `recorder.record(replan_idx=…)`
   kwarg → `TypeError` killed the whole run after one replan.
Each has a regression test in `test_gate9_intervention.py`.
