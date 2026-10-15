# Changelog

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
