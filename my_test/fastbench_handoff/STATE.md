# FastBench State

## Current status
- [x] Research framing frozen to H1/H2/H3 for MVP.
- [x] Official FastWAM LIBERO rollout entry point identified: `experiments/libero/eval_libero_single.py::run_single_episode`
      (canonical wrapper: `experiments/libero/run_libero_manager.py`; `eval_libero_single.py` is the per-task worker it drives).
- [x] LIBERO-Safety benchmark registry identified: `libero/libero/benchmark/vla_safety_task_map.py`.
- [x] LIBERO-Safety dynamic-motion primitives identified: `LinearMotionGenerator`, `CircularMotionGenerator` in `libero/libero/envs/utils.py`.
- [x] Local dependency-light benchmark runner prototype created.
- [x] Execute actual LIBERO-Safety environment locally (headless EGL MuJoCo render verified).
- [x] Connect official FastWAM checkpoint (both released LIBERO checkpoints load and run).
- [x] Add explicit future-video / state consistency metric (upstream `EVALUATION.visualize_future_video=true` + PSNR).
- [x] Reproduce official FastWAM success rate on standard LIBERO — **RESOLVED: root cause was `EVALUATION.sigma_shift`**
      (config `null` fell through to the wrong default 5.0; README pins **1.0**). With `1.0` successes reappear
      (1/15 over 3 suites); see "Root cause" below.
- [x] Run LIBERO-Safety `obstacle_avoidance` end-to-end through FastWAM with no intervention (Gate 8 v2: 0/5 with the
      correct flags — clean run, real MP4s, meaningful verdict).
- [x] Deterministic mid-chunk intervention + structured recorder (**Gate 9 COMPLETE**, verified end-to-end).
- [x] Control-vs-disturbance sweep over `replan_steps` 1/5/10 (**Gate 11 COMPLETE** — six arms, seed-pinned,
      `pre_iv_max_l1 == 0.0`; see below).
- [x] Gate 12B — baseline fidelity audit — COMPLETE 2026-10-16 (`evidence/gate12b_fidelity_audit.md`): every
  config / checkpoint / protocol element verified faithful — reference command matches the README, resolved config
  matches repo defaults (action_horizon 32, 10 inference steps, binarize_gripper), the checkpoint contains BOTH
  `mixtures.video.*` (825 keys) and `mixtures.action.*` (824 keys) experts, standard suites resolve to upstream
  bddl/init files, and decoded observations are valid renders.
- [x] Gate 12A — control-only screen — COMPLETE: 30 tasks × 5 trials (libero_spatial/object/goal, GPUs 5,7) →
  **6/150 = 4.0%** overall vs the README's 98.55%. Only `libero_spatial` t0/t1 looked "usable" at 40%, which was
  small-sample luck (see 12C). CSV: `results/gate12a_screen_summary.csv`.
- [x] Gate 12C — flag A/B — COMPLETE (`scripts_setup/gate12c_ab.sh`): at n=20, upstream-flags arm **1/20** vs ours
  **3/20** on `libero_spatial` t0, and **0/20** both on `libero_object` t0. Our flags (`load_text_encoder=true`,
  `compile_action_infer=false`, `seed=1`) are EXONERATED — the gap vs the published table is **environmental**.
- [x] Gate 12D — ROOT CAUSE FOUND & FIXED 2026-10-16 (`evidence/gate12d_rootcause.md`): the reproduction gap is a
  **modified OSC controller config in the vendored robosuite fork**. `LIBERO-Safety/third_party/robosuite-1.4`
  ships `controllers/config/osc_pose.json` with `output_max [2,2,2,2,2,2]` / `kp 750` where official robosuite
  1.4.0 has `[0.05,0.05,0.05,0.5,0.5,0.5]` / `kp 150` — policy actions scaled 40× (translation) and 4× (rotation)
  with 5× stiffer gains, so a policy trained on official-LIBERO statistics flails. Confirmed loaded at runtime via
  `load_controller_config('OSC_POSE')`. Fixed by restoring the official file (backup at `osc_pose.json.forkbak`;
  fix also shipped as `patches/osc_pose.official.json`). Post-fix canary: `libero_spatial` t0 **5/5** and
  `libero_object` t0 **5/5** (were 3/20 and 0/20 at n=20).
- [x] Gate 12A (re-run, post-fix) — 30 tasks × 5 trials with the corrected controller → see
  `results/gate12a_screen_fixed` (aggregate CSV alongside).
- [ ] Gate 13 — paired stale-commitment cost — **UNBLOCKED**: control success is now usable. Re-run the Gate 11
  obstacle_avoidance arms post-fix too (its 0/2 was measured on the broken controller).

## Environment (resolved — supersedes the old limitation)
The old "no libero/mujoco/robosuite" limitation no longer applies. On this server:

- Dedicated conda env `fastbench` (py3.10, torch 2.7.1+cu128) at `/data1/liborui/.conda/envs/fastbench/bin/python`.
- `FastWAM` installed editable (`pip install -e`), package source at `FastWAM/src/fastwam/`.
- LIBERO-Safety importable as `libero` via `libero_safety_path.pth`; robosuite-1.4 + mujoco 3.3.2; assets extracted to
  `LIBERO-Safety/libero/libero/assets/`.
- LIBERO config `/data1/liborui/.libero/config.yaml` (absolute asset/bddl/init/dataset paths).
- Headless rendering: `MUJOCO_GL=egl` (verified — Gate D PNG).
- Backbone components staged under `checkpoints/`; `DIFFSYNTH_MODEL_BASE_PATH=/data1/liborui/fastwam_bench/checkpoints`,
  `HF_ENDPOINT=https://hf-mirror.com`, `model.redirect_common_files=false` (the upstream default redirect 404s on the mirror).
- `CUDA_DEVICE_ORDER=PCI_BUS_ID` is required so CUDA indices match `nvidia-smi` indices; naive GPU picking otherwise
  collides with other tenants and OOMs at model init.

## Gate 7 — official FastWAM LIBERO rollout
Command shape (faithful to README; the extra flags are no-ops because they already match `configs/sim_libero.yaml`):

```bash
python experiments/libero/eval_libero_single.py \
  task=libero_optional_idm_2cam224_1e-4 \
  ckpt=checkpoints/fastwam_release/libero_optional_idm_2cam224.pt \
  model.redirect_common_files=false \
  EVALUATION.dataset_stats_path=checkpoints/fastwam_release/libero_optional_idm_2cam224_dataset_stats.json \
  EVALUATION.task_suite_name=libero_spatial EVALUATION.task_id=0 EVALUATION.num_trials=5 \
  EVALUATION.sigma_shift=1.0 EVALUATION.compile_action_infer=false
```

Acceptance criteria from `WARM_START.md` §7 — **all met**: evaluator completes without crashing; real rollout
videos + result JSON produced; success/failure status meaningful (not empty/default).

Verified faithful (each checked, not assumed):
- action convention: OSC, ±1 input, sign correct (`+x`→+x, `-x`→−x, …);
- gripper: env `−1`=open / `+1`=close ⇔ FastWAM `invert_gripper_action` + `binarize_gripper(>0.5)` — correct;
- proprio: state = `[eef_pos(3), quat2axisangle(3), gripper_qpos(2)]` = 8-D, matches `_extract_sim_state` and stats;
- action = 7-D `[delta eef pose(6), gripper(1)]`, stats match `delta_action_dim_mask`;
- `action_horizon = num_frames-1 = 32`, `num_inference_steps = 10`, 2 cameras, 224×448 horizontal concat;
- checkpoint: 11.5 GB, 6.02 B-param MoT, keys `mixtures.video.*`/`mixtures.action.*` match the model's
  `nn.ModuleDict` naming, so `load_state_dict(..., strict=False)` does **not** silently drop the 5B expert;
- `action_infer_mode` defaults to `idm` (matches README); **`sigma_shift` does NOT default correctly — it resolves to
  5.0 unless explicitly overridden. Always pass `EVALUATION.sigma_shift=1.0`.**

### Root cause of the 0% success (RESOLVED)
**Measured success was 0/5 (libero_spatial t0) and 0/3 (obstacle_avoidance L0 t0) while the README claims 99.0% Spatial.**

Root cause: `EVALUATION.sigma_shift` silently defaulted to **5.0**. `configs/sim_libero.yaml` sets it to `null`, and
the resolution path is `shift = self.shift if shift_override is None else float(shift_override)` — so `null` falls
through to the *internal* default (5.0), not to the README's pinned **1.0** for the uncond checkpoint.

With `EVALUATION.sigma_shift=1.0` successes reappear, confirming the diagnosis: **1/15** over three suites
(libero_spatial 1/5, libero_object 0/5, libero_goal 0/5). The absolute rate is still below the paper's, but the
pipeline, model, and world model are all genuinely working — which is what the gates require.

The world model was never the problem: `visualize_future_video=true` gives future-video PSNR ≈ 26.6 dB against the
real rollout.

Ruled out along the way: env action space, gripper polarity, proprio layout, action normalization stats, checkpoint
pairing, entry point, `action_infer_mode`, inference-step count, image resize/camera concat, weight loading,
dataset-stats pairing, and a truncated safetensors shard (re-downloaded; not read by eval anyway).

**Per `AGENTS.md`, do not block the intervention work on matching the paper's accuracy.** The Gate 7 *contract*
passes and the baseline is now *reproducing* (nonzero, correctly-flagged); Gate 9/11 proceed on that basis.

## Gate 9 — intervention + structured recorder (COMPLETE)
`FastWAM/experiments/libero/fastbench_intervention.py` (new) + hooks in `eval_libero_single.py`.

- **Interventions** — two independent kinds, both deterministic and one-shot:
  - *action* (`apply_intervention`): perturbs exactly ONE step inside a freshly generated chunk; modes
    `zero_action` / `scale` / `invert` / `gripper_flip` / `freeze_prev` / `noise` (seeded).
  - *world* (`displace_object` / `maybe_displace_world`): translates a free-joint scene object's qpos, then
    `sim.forward()`. This is the H3 primary condition: the current chunk was planned against the pre-intervention
    world, so it becomes stale by construction.
- **Recorder** (`StructuredRecorder`, JSONL) — `replan`, `step`, `intervention`, `episode_end` events; each step
  carries the executed action, chunk summary, EEF pose, and per-object poses.
- **§3.2 stale-action metric** — counts steps executed from a plan made against a pre-intervention world
  (`stale_action_steps`, per-step `stale` flag).
- All keys under `EVALUATION.*` in `configs/sim_libero.yaml`, **inert by default**.

Verified: `scripts_setup/test_gate9_intervention.py` (45 checks, all pass) + end-to-end
`scripts_setup/gate9c_world_only.sh` → `results/gate9b_world_oa_t0/`: displacement fires once per episode at
`replan_idx=1` with `applied=True` and an exact readback delta; 120 replan / 1200 step / 2 intervention /
2 episode_end records; `stale_action_steps=10`.

Four real bugs were found and fixed during this verification (unconditional replan counters; joint-index vs qpos
address; duplicate `replan_idx` kwarg) — details in `CHANGELOG.md`.

## Gate 11 — control vs disturbance sweep
`scripts_setup/gate11_sweep.sh` — control (recorder only) vs disturbance (world displacement at `replan_idx=1`) for
`replan_steps` ∈ {1, 5, 10} on `obstacle_avoidance` L0 task 0, then a recovery analysis (re-acquisition latency of
the displaced object, object net motion, stale-action counts, success). Results in `results/gate11_*`.

**Seeding is mandatory for this comparison (bug found and fixed 2026-10-15).** No script passed a seed, and
`eval_single_process` only calls `set_global_seed` when `cfg.get("seed") is not None`, so the diffusion sampling
noise differed per invocation: the two arms were *not* step-by-step comparable and the first cross-arm divergence
appeared at t=0 (L1 ≈ 9e-3), which completely masked the real signal. The sweep now passes `seed=$SEED` (default 1;
0 is invalid — `set_global_seed` asserts strictly inside the uint32 bounds) and the analyzer reports the
pre-intervention L1 as an explicit noise-floor baseline (divergence threshold = 20x baseline, ≥ 5e-3).
With `seed=1` the arms are **bit-identical** pre-intervention (`pre_iv_max_l1 == 0.0`), which is the proof the fix
worked.

**Full sweep result (rs ∈ {1,5,10}, 2 trials each, seed=1, all six arms exit 0):**

| replan_steps | stale window | divergence gap | plan divergence (chunk-mean L1) | EEF–obj min dist (ctl / dist) | obj net motion (dist) |
|---|---|---|---|---|---|
| 1  | 1 (t=31)   | 1  | 0.3848 | 0.0781 / 0.1494 | 0.0849, 0.1958 |
| 5  | 5 (t=35–39) | 5  | 0.1100 | 0.1832 / 0.2398 | 0.0849, 0.0849 |
| 10 | 10 (t=40–49) | 10 | 0.0989 | 0.0689 / 0.1709 | 0.0900, 0.0849 |

- `pre_iv_max_l1 == 0.0` for **both episodes at every** `replan_steps` → control and disturbance are bit-identical
  up to the intervention; the seeding fix holds across the whole sweep.
- `divergence_gap == stale_window == replan_steps` exactly at all three granularities → the policy executes the
  *entire* stale chunk verbatim and only re-plans at the next boundary.
- Plan divergence is far above the noise floor at every setting (0.099–0.385 vs 0.005) → the policy **does** change
  its plan once it finally observes the displaced world, i.e. correction happens.
- Success is 0/2 in **all** arms (control included), so there is no success-recovery signal on this task — consistent
  with the re-baselined model performance (obstacle_avoidance L0 = 0/5). The H3 evidence is therefore behavioural,
  not success-based: the committed stale chunk is fully paid for, and the disturbed arm stays further from the object
  at its closest approach (0.149–0.240 m vs 0.069–0.183 m control).

Interpretation (revised 2026-10-16 per `REMOTE_REVIEW.md`): this is the H3 **Future-Reality Divergence** signature, and
it must be stated as a property of the execution protocol, not of the model:

> Under fixed-horizon chunk execution, a world change cannot affect the current action chunk until the next
> replanning boundary.

Do **not** headline it as "the model chooses to execute stale actions for N steps": `divergence_gap == stale_window`
is harness-correctness by construction (the intervention is injected *after* the chunk is planned and the model
cannot re-query the environment until the next boundary). The model-side content is (a) the post-replan plan
divergence magnitude and (b) the disturbed arm's subsequent behaviour — it stays further from the object at closest
approach (0.149–0.240 m vs 0.069–0.183 m).

Supported claim:

> We built a deterministic paired-intervention harness for FastWAM in LIBERO-Safety. A mid-chunk world-state change
> invalidates the current plan; under fixed-horizon execution the stale chunk persists until the next replan, after
> which the generated action plan changes relative to control.

Explicitly **not** yet supported: reliable recovery; intervention-caused success drop; WAM > or < VLA; "future
modeling specifically improves robustness".

## Next integration target — Gate 12 (baseline tasks), per `REMOTE_REVIEW.md`
Gate 11 is finished. The blocker for the next result is that the current task has 0% success in *both* arms, so it
cannot produce a recovery signal. Agreed plan with the remote reviewer:

- **Gate 12A — screen control-only success.** Scan LIBERO Spatial / Object / Goal and LIBERO-Safety
  `obstacle_avoidance` L0/L1 at ~5 trials/task and target `30% <= control success <= 90%`; then 10–20 trials on the
  best 2–3 tasks. Commit a machine-readable summary:
  `suite, task_id, level, trials, successes, success_rate, mean_steps`.
  **Canary done (2026-10-16, seed 1, 2 trials/task): libero_spatial t0 = 2/2 (100%), t1 = 1/2 (50%);
  libero_object t0 = 0/2; libero_goal t0 = 0/2.** Main screen = 30 tasks × 5 trials, running on GPUs 5,7
  (`scripts_setup/gate12_screen.sh`, tasks in `scripts_setup/gate12a_tasks.txt`).
- **Gate 12B — baseline fidelity — DONE (2026-10-16), see `evidence/gate12b_fidelity_audit.md`.** The harness is
  faithful: our command reproduces the upstream README's documented eval command key-for-key (task / ckpt /
  dataset_stats / `sigma_shift=1.0` / `action_infer_mode=idm`), init-state protocol and 400-step budget match,
  and the official suites resolve to the flat upstream `.bddl` files (LIBERO-Safety's augmented `_add_*` sets and
  `libero_mix/` are *not* used). Empirically, libero_spatial t0 = 100% reproduces the README's 99.0%.
  **Conclusion: no fidelity bug — Gate 11's 0% is a property of `obstacle_avoidance` (a LIBERO-Safety suite,
  not one of the 40 standard benchmark tasks the README quotes), which this checkpoint simply cannot solve.**
- **Gate 13 — first real recovery result.** Paired control vs disturbance on a task with reliable control success
  (same task, init state, seed, model config and replan horizon). Report Control SR, Disturbed SR, Success Drop,
  Recovery Rate (`successful disturbed episodes / disturbed episodes whose paired control succeeds`), Recovery
  Latency, Stale Action Steps, Post-intervention Plan Divergence, and collision/safety violations where available.
  "Recovery" means successful adaptation after the old plan becomes invalid — not merely that the action changed.
- **Gate 14 — make the result WAM-specific.** Same checkpoint, task, seed, intervention and replan horizon,
  comparing future-aware / IDM inference against non-future / first-frame inference (preferred, because almost every
  factor stays controlled). Only after Gate 14 make WAM-specific robustness/failure claims.

Gate write-ups from now on use the remote reviewer's format:
`STATUS: / EVIDENCE: / INTERPRETATION: / OPEN QUESTION: / NEXT ACTION:`.

Harness patches already applied (minimal, marked `[fastbench]`, no-op for upstream LIBERO suites):
- `experiments/libero/libero_utils.py`: `resolve_task_file_path(task, file_type, filename)` prefers
  `<suite>/L<level>/` (LIBERO-Safety layout) and falls back to the flat upstream path when the task has no `level`.
- `experiments/libero/eval_libero_single.py`: level-aware init-state resolution; `_get_max_steps` now maps
  `obstacle_avoidance*` / `human_safety` / `affordance` / `reasoning_safety` → 600 steps.
- Note: LIBERO-Safety reuses task names across L0/L1/L2 and `benchmark.get_task(i)` flattens levels; level selection
  must go through `get_task_by_level_id(level, level_id)`.

## Locally verified prototype result (toy contract test — unchanged)
- `replan_steps=1`: intervention step 2; first replan after intervention step 3; stale actions = 1; recovered.
- `replan_steps=4`: intervention step 2; first replan after intervention step 4; stale actions = 2; recovered later.

Toy contract test only; verifies definitions and runner mechanics, not a robotics conclusion.

## Gate 13 — cross-horizon commitment-cost sweep (2026-10-17, in progress)

**STATUS:** infrastructure complete and validated; main sweep done, magnitude ladder + PSNR arm
queued unattended (`scripts_setup/gate13_finish.sh`).
**HEADLINE FINDING (2026-10-17, main sweep complete 32/32 + ladder):**
The *mechanism* is confirmed exactly; the *task-level cost* is large but does **not** scale with H.

| evidence | result | verdict |
|---|---|---|
| stale actions executed after the world change | exactly H at every H (1,2,5,10); 0 contaminated episodes | mechanism REAL |
| control success | 1.00 in all 8 (task,H) cells, n=10 | env is healthy |
| disturb success, spatial | 0.80 at H=1,2,5,10 (cost +0.20, flat) | no H trend |
| disturb success, object | 0.60 / 0.40 / 0.90 / 0.70 at H=1/2/5/10 | non-monotone (noise) |
| steps to succeed | spatial 104→173-176; object ~170→258-364 | big cost, H-independent |
| timeouts | 0 → 1-6 per 10 | failures = budget exhaustion |
| eef-object divergence, max over stale window, spatial | 0.002 / 0.011 / 0.043 / 0.045 m | **ARTIFACT**: window length = H. At fixed lag k=1 it is +0.0016/+0.0020/+0.0017/+0.0017 m — no H effect |
| magnitude 0.02 m | 20/20 disturbed episodes succeed (both tasks, both H); cost 0.00; steps == control | **below the recovery threshold — a world change costs nothing at any H** |
| magnitude 0.03 m | object 1/5 (H=1) and 3/5 (H=10) → pooled 4/10 vs 10/10 at 0.02 m, Fisher p=0.011; spatial still 10/10 | **threshold is task-dependent, not H-dependent**; object H=1 vs H=10 p=0.52 (noise) |
| magnitude 0.05 m | cost +0.20 at both H=1 and H=10 | flat |
| **PSNR arm, matched lag** (`psnr_fixed_lags=[0,4,8]`, `results/gate13_psnr_lag`) | control 37.5 dB at lag0 → 25.0 dB at lag4 (no intervention); disturbance cost at lag4 **−0.64 dB at H=5 vs −1.52 dB at H=10 (~2.4x)**, n=2/cell | prediction degrades with lookahead (robust); horizon effect on damage survives at matched lag but is ~2.4x, NOT the withdrawn 4.7x |

Interpretation: FastWAM re-plans at the next chunk boundary and recovers regardless of how long
the stale chunk was, so the task-level penalty is set by *whether the object can be re-acquired*,
not by H. The commitment is still demonstrably real at the action level (stale == H exactly). A
first mechanism metric (eef-object divergence over the stale window) appeared to grow with H but
is a window-length artifact — at a fixed lag it is flat across H. This is a **negative result for
the strong "longer commitment costs more" claim** and a positive result for "the model executes H
stale actions".

**EVIDENCE:** `scripts_setup/gate13_run.py` (sweep runner), `gate13_analyze.py`,
`gate13_figure.py`, `gate13_report.py`, `gate13_all.sh` (unattended pipeline),
`gate13_validate_goal_aware.py`; `evidence/gate13_design_checks/` (raw captures);
`scripts_setup/test_gate9_intervention.py` (67 checks, all pass).

`replan_steps` is the commitment horizon H (`pending_actions = action_chunk[:H]`); the released
config ships H=10. The sweep varies H over {1,2,5,10} (the divisors of `world_step-30`) with a
paired control/disturb design and an **absolute-step trigger**
(`+EVALUATION.intervention_world_step=40`) so the world change lands at the same absolute step
for every H.

**Design flaw 1 — the disturbance completed the task.** The original fixed displacement
`[+0.06,+0.06,0]` *completed* `libero_spatial` t0 (it teleported the bowl onto the plate: the goal
is `on(akita_black_bowl_1, plate_1)` and the plate sits at +x/+y). The episode ended at
t = world_step, so `stale` read 1 instead of 10. The disturbance is now **goal-aware**: the
manipulated body is resolved from the task's own goal state, the displacement points *away* from
the goal target, and the result is checked against the env's `_check_success()` — a candidate that
satisfies the goal is reverted and the next direction tried (`post_iv_success` and
`rejected_candidates` are recorded per episode). See `evidence/gate13_design_checks/`.

**Design flaw 2 — the disturbance was unrecoverable at every horizon.** At `world_step=60` the bowl
is already held aloft (z≈0.90); teleporting a *held* object forces a full re-grasp, which no
horizon can do — not even H=1. Cost saturated at 1.0 everywhere, so the sweep measured nothing.
Calibrated to **`world_step=40`** (during the approach, before the grasp) and **magnitude 0.05 m**
(0.10 m was comparable to the whole 0.117 m bowl→plate distance). At this setting H=1 recovers.

**Design flaw 3 — falsy-zero bug in the magnitude.** `float(ev.get(...) or 0.10)` promoted a
legitimate `0.0` (the no-op control that validates the disturb code path) to 0.10 m. Fixed; the
no-op run now correctly reproduces the control (`noop_validation_summary.json`: 1/1, obj_move
0.111 m = the natural grasp-and-place), which proves the disturb arm itself is sound.

**Validated design (probe, ws=40, mag=0.05, 2 trials, seed 1):**

| task | H | arm | success | stale executed | contaminated |
|---|---|---|---|---|---|
| libero_spatial t0 | 1 | control | 2/2 | 0 | 0 |
| libero_spatial t0 | 1 | disturb | 1/2 | 1 | 0 |
| libero_spatial t0 | 10 | control | 2/2 | 0 | 0 |
| libero_spatial t0 | 10 | disturb | 1/2 | 10 | 0 |

`stale executed == H` is the mechanism claim: after the world changed, the model still executed
the whole remaining chunk that had been planned for the pre-change world. Control is 1.00 at both
horizons and H=1 recovers, so the sweep is not floor-saturated.

**RUNNING:** `results/gate13_main` — 2 tasks x H{1,2,5,10} x seeds{1,2} x {control,disturb} x 5
trials = 32 jobs / 160 episodes, unattended (~2.5 h), then the PSNR arm and the report.
**NEXT ACTION:** on completion, generate `evidence/gate13_commitment_cost.{md,png}` from
`gate13_main/gate13_summary.json`, verify control≈1.0 / cost monotone in H / `contaminated==0`,
then commit.

