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

**Gate 13B (2026-10-18, COMPLETE) — repeated strikes do not compound.**
Gate 13 struck the world once; one strike can only invalidate H actions once and re-acquisition
absorbs it. Gate 13B repeats the strike 4x (steps 40/50/60/70) at 0.01 m, below the 0.03 m threshold
where a single strike starts to fail episodes. Result: **10x the stale actions with no success cost.**
object H1 4.0 stale / 5-6 success, H10 40.0 stale / 6-6 (Fisher p=1.0); spatial 3.3 vs 32.7 stale,
6-6 both. Effort leans the expected way (+133 vs +89 steps, Welch p=0.52) but n=6 cannot resolve it.
Three failure modes were found and fixed en route: mirrored strikes were *helping* the policy (51 vs
~100 steps); an absolute-distance cap silently allowed only one strike, degenerating the run into the
single-strike test; and the intervention could silently not fire at all (one cell recorded
`strike_count=0` with step counts identical to control, which an episode count cannot detect). The
analyzer now audits all three: incomplete cells, `cost vs horizon` shape (flat / increasing /
decreasing, not a non-decreasing predicate that calls a flat curve "monotone increasing"), and
`INTERVENTION NEVER FIRED` for any disturb cell with zero strikes. **Critical bound found afterwards:**
every strike landed *before* the object was ever lifted (24/24 struck episodes; spatial lifts at
steps 54-84, object at 133-161, strikes fixed at 40/50/60/70), so the staleness measured here was
approach-phase only — invalidating approach actions is usually recoverable, and the harmful
regime (stale carry trajectory after the object is displaced out of the gripper) was never entered.
The analyzer now also reports `STRIKES LANDED BEFORE THE GRASP`. A fourth limit: the strike hook runs
only at chunk boundaries, so a cadence finer than `replan_steps` reduces the strike count at large H
(`--world-repeat-every 5` gave H1 4.0 strikes but H10 2.0) — flagged as `STRIKE COUNT NOT MATCHED`.

**Gate 13C (2026-10-18, COMPLETE) — carry-phase strikes; cost is real, horizon still flat.**
Adds `intervention_world_trigger_after_lift` (CLI `--world-trigger-after-lift 0.02`): latch the
object's resting height, latch `_lift_step` when it rises past the threshold, then strike at
`lift+every`, `+2*every`, ... instead of from an absolute step. `icfg` is rebuilt inside
`run_single_episode`, so the anchor cannot leak between trials. The runner validates that the repeat
interval (not `world_step`) divides H, since the interval is what must land on a chunk boundary.
Full run `results/gate13_repeat_carry_full` (n=6/cell, 0.01 m, 2 tasks x H{1,10} x 2 seeds x 3
trials): **libero_object t0** control 6/6 vs disturb **2/6** at H=1 (Fisher p=0.061) and **1/6** at
H=10 (p=0.015), stale 4.0 -> 40.0; **spatial** flat 6/6 both. Horizon contrast on object is
**2/6 vs 1/6, Fisher p=1.000** — so moving strikes into the carry turns the Gate 13B null into a real
cost, but the cost saturates at the first strike instead of compounding with H. Conclusion: commitment
cost is gated by whether stale actions are *load-bearing*, not by how many there are. Spatial is flat
because its carry window is only ~30 steps (<=3 strikes); object's is ~81 steps (<=8), which is why it
carries the result. Structural note: spatial carry window min/med/max = 3/30/34, object = 71/81/125.
Pilot `results/gate13_repeat_carry2` (spatial, n=3) validated the trigger; `results/gate13_repeat_carry`
is **INVALID** (the key was never mapped out of `cfg.EVALUATION`, so strikes stayed at 40/50/60/70 —
a plumbing test now catches this). Tests: 99 checks.
Naming note: these two are **13B** and **13C** — Gate 14 below is reserved for the WAM-vs-baseline
comparison.

**Gate 13D (2026-10-19, COMPLETE) — the carry cost is a release failure, not a reach failure.**
Classifies every carry-regime episode from the object's own `state.bodies` track
(`scripts_setup/gate13d_mechanism.py`) into PLACED / HELD-ABOVE-BASKET / LOST-FAR /
STILL-DESCENDING / NEVER-LIFTED, then repeats the strike at 0.005 m. **No struck episode in either
magnitude ever failed to pick the object up** — the grasp always survives, so "a 1 cm displacement
knocks the object out of the gripper" is wrong. At 0.01 m the dominant mode is HELD-ABOVE-BASKET
(6 of 9 failures): the robot reaches the basket (xy within 5 cm) and parks 5–9 cm above the
placement height until the budget expires (tail slope +0.0001 m/step vs 0.136 m for a success). Only
1 of 9 failures was still descending at the 400-step cap, so it is not a time-budget artifact.
**No measurable dose-response over 5–20 mm**: `results/gate13_carry_mag005` (n=6/cell) gives control 6/6,
disturb 2/6 at both horizons, stale 3.5 -> 40.0 — the same cost as 0.01 m, i.e. halving the displacement did not
halve the damage; the 0.02 m arm (n=3/cell) is 0/3 vs 3/3. Success 33% -> 25% -> 0% across 5/10/20 mm, but
**every pairwise contrast is n.s. (p >= 0.245)**, so "saturates" is too strong: the honest statement is that
the cost is at or near ceiling by 5 mm and no trend is resolvable at this n. Third independent replication of
the horizon null. **Retracts the 13C mechanism
sentence "once the grasp is broken the episode is lost"** — the grasp is never broken; the stale
carry actions cost the episode by wrecking the *placement*. Not established: *why* the policy stops
short (no grasp/contact state in the records, so that stays an inference). Evidence:
`evidence/gate13d_mechanism.md` + `.png/.pdf`.
Evidence: `evidence/gate13b_repeated_strikes.md` + `.png/.pdf`, `evidence/gate13c_carry_phase.md`.

**Gate 14 (2026-10-19, COMPLETE) — the carry-phase cost is NOT WAM-specific.**
Same checkpoint, task, seeds (1,2), 3 trials/cell, same 0.01 m grasp-relative strike schedule and
horizons (1, 10); the only change is `EVALUATION.action_infer_mode=first_frame` (the non-future
branch of the same network) instead of `idm`. Control: `first_frame` 5/6 @ H1, 6/6 @ H10 (11/12) vs
`idm` 12/12 — clumsier but not broken (p=0.33 pooled). Disturb: `first_frame` **2/6 @ H1, 1/6 @ H10**
— **numerically identical to `idm`'s 2/6 and 1/6** (Fisher p=1.0000 at both horizons). The failure
signature is identical too: 7 of 9 `first_frame` failures never release the object, the two that do
release let go 33/34 steps after the strike, and 12/12 strikes again land after the lift. So the
cost survives removal of future-aware action inference: **it is a property of fixed-horizon chunk
execution, not a world-modeling commitment cost**, and the "WAM" framing of Gates 13/13B/13C/13D was
never tested until now — it fails. Does NOT show the WAM has no world-modeling advantage (the
predicted-future fidelity result comes from the video pathway, which this ablation does not touch),
and does not test a stronger no-video baseline. Also added `--max-steps` (per-suite budget override)
plus 3 plumbing checks (tests now 102). Evidence: `evidence/gate14_wam_specificity.md`; data
`results/gate13_g14ff` vs `results/gate13_repeat_carry_full`; compare with
`scripts_setup/gate14_compare.py`.

  *Correction (same day, after a fair-metric check):* "numerically identical" was the wrong words for
  a null at n=6. Newcombe 95% CI on the between-pathway difference is **[−0.44, +0.44]** at H=1,
  [−0.42, +0.42] at H=10, [−0.34, +0.34] at 800 steps — so the pathways are **not shown to be equal**,
  only shown to be indistinguishable here. What actually refutes specificity is the *within*-pathway
  drop: `first_frame` 11/12 control → 3/12 disturb, **p=0.0028** (H=10 alone p=0.015, H=1 alone
  p=0.24). That argument does not require the two pathways to match. Also added the heatmap
  (`evidence/gate14_matrix.png`) and a curated rollout (`evidence/gate14_rollout.png`, trial 2:
  control success at 222 steps vs disturbed failure at 430 steps, held above the basket).

  *Correction 2 (same day, approach regime at 800 steps):* the approach arm was reported as
  budget-mediated (7/7 failures were 430-step timeouts, "slow, not damaged"). **That reading is
  wrong.** With `--max-steps 800` the control cell becomes **12/12** (the one control timeout
  succeeds at 606) and the disturb cell stays at **5/12** — **p=0.0046**, every failure running the
  full 830 steps. So the pathway difference in the approach regime is real, and its form differs from
  the carry regime: 3 of 7 failures never lift the object (missed grasp) and 4 carry it far from the
  basket, against 42/42 lifts under carry-phase strikes. Net: future-aware action inference is
  **neutral in the carry phase and protective in the approach phase** — in neither regime is it the
  fragile one. Data: `results/gate13_g14ffapproach800`.

**NEXT (scoped, not run): seed extension for the equivalence question.** Excluding a 20-point
difference between pathways at 80% power needs ≈93 episodes/arm/horizon (~6 GPU-h/arm). Plan: seeds
3–8 on `libero_object:0`, carry regime, both pathways, H=1 and H=10, 3 trials/seed → 18/cell, then
re-run `gate14_compare.py` with the pooled runs. Until then the doc's claim stays the within-pathway
one.

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
| **PSNR arm, clip-isolated** (`scripts_setup/gate13_psnr_clip.py`, `results/gate13_psnr_clip`) | lag0 delta **exactly 0.00**; damage at 4-step lookahead **−4.42 dB (H=5) vs −4.40 dB (H=10)**, n=6/cell; control PSNR 39.5→27.9→27.1 dB at lag 0/4/8 | prediction degrades sharply with lookahead (robust); a mid-chunk change costs ~4.4 dB; **no measurable H dependence** |

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
`scripts_setup/test_gate9_intervention.py` (99 checks, all pass).

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

## Gate 14D — the stale remainder does not carry the cost (2026-10-19, COMPLETE, NEGATIVE)

Every earlier gate *inferred* that the cost comes from executing the stale remainder of the chunk. 14D
manipulates it: `--drop-stale-after-strike` discards the rest of the executing chunk the moment a strike
lands, so the same world change happens but the already-planned actions mostly do not run. Config key
`EVALUATION.intervention_world_drop_stale`; provenance `dropped_stale_count` per episode and
`dropped_stale` per strike. Pre-registration: `evidence/gate14d_drop_stale.md`.

**Result: 2/6 either way.** Carry regime, `libero_object:0`, 0.01 m, H=10, one strike, n=6/arm
(`g14keep1` vs `g14drop1`). The same two episodes succeed, one step apart (202/169 vs 203/171); the four
failures each run to the 430-step cap. Fisher p=1.0000. The manipulation provably fired:
`stale_action_steps` 10 → 1, `dropped_stale_count` 0 → 9. P1 failed; P2 held.

**Consequences (applied to README/evidence):**
- The "fixed-horizon chunk execution" framing is **retired**. The cost survives with 9 of 10 stale
  actions removed, so it belongs to the displacement, not to replaying a stale plan.
- The horizon gradient is now **unexplained**: 4 strikes → 1/6, 1 strike → 2/6 at H=10, and one strike at
  H=10 equals the four-strike H=1 cell (2/6). Stale-action count was the obvious mechanism and it is inert.
- 13D's mechanism result stands unchanged (grasp never breaks; object held above the basket) — measured
  directly, not inferred from staleness.

**Harness findings from this round (each cost a wasted launch before being caught):**
- Clearing `pending_actions` at the strike crashes with `IndexError` — the step's action is popped
  further down. Hence execute-then-drop, which means one stale action still runs.
- Dropping the chunk desynchronises the repeat-strike grid: replans shift to 101, 111, 121, … where
  `delta_t % 10` is never 0, so a 4-strike drop arm fires exactly **one** strike. Both 14D arms
  therefore use `--world-repeat-count 1`; comparing against the 4-strike data would confound stale
  count with strike count.

**Still unmeasured:** the drop arm executes one committed action, so this cannot separate "displacement
alone" from "displacement + one in-flight action". The zero-stale arm is now built and run (Gate 14E,
below); it shows the in-flight action is not sufficient either.

Tests: 114 `[PASS]` (6 new zero-stale plumbing checks). Patches regenerated and `--check` clean.

## Gate 14E — stale execution is not the channel (2026-10-19, COMPLETE, NEGATIVE)

14D left one committed action in flight, so it could not separate "the displacement damages the
episode" from "the one in-flight action damages it". 14E removes the last one: the strike is applied
**before** the policy query and the observation is re-read with
`_get_observations(force_update=True)`, so the chunk is planned against the mutated world and **zero**
stale actions execute.

Result at H=10, 0.01 m, one strike at t=100, n=6 per arm:

| arm | stale actions | success | mean steps |
|---|---|---|---|
| keep chunk | 10 | 2/6 | 348.5 |
| one action then drop | 1 | 2/6 | 349.0 |
| zero stale | 0 | 2/6 | 348.5 |

**Identical episode for episode**, down to the step counts (202/169/430×4 in every arm). The refresh
is measured, not assumed: `obs_pixel_maxdiff=116`, `obs_pixel_changed_frac=0.0528`.

So the "stale execution / fixed-horizon chunk" framing is **retired**. The displacement costs the
episode; executing actions planned before it does not.

Honesty notes:
- The harness **refuses to record a strike it cannot refresh** (raises). This caught
  `OffScreenRenderEnv` not re-exporting `_get_observations` — the owner is `env.env`.
- `gate13_analyze.py`'s contamination rule (`stale_n <= 0` ⇒ "manipulation never ran") is now
  mode-aware: for a zero-stale episode it instead requires `obs_refreshed is True`. Without that,
  every 14E episode was flagged `bad`, which would have made a reviewer distrust a correct cell.
- **Not measured:** ~~that the policy produces an unchanged trajectory~~ — measured and **falsified**
  (Gate 14F). Chunk dumps at the same seed: the 7 pre-strike chunks are bit-identical across arms
  (internal validity), and the chunk at the strike differs by max 0.0998 / mean 0.021. The model
  reacts; the reaction is too small to change the outcome. Diagnostic:
  `FASTBENCH_DUMP_CHUNK=<path>`, one JSON line per replan.



## Gate 14G — the corrective response plateaus while the damage grows (2026-10-19, COMPLETE)

Resolves the reading 14D/14E/14F left open. Single strike, zero-stale arm, H=10, n=6 per magnitude,
seeds 1-2, magnitudes 2/5/10/20/40 mm, each paired against the control episode of the same seed/trial.

| magnitude | success | mean \|delta\| | max \|delta\| |
|---|---|---|---|
| 2 mm | 6/6 | 0.0611 | 0.0989 |
| 5 mm | 5/6 | 0.1031 | 0.1735 |
| 10 mm | 2/6 | 0.1125 | 0.2193 |
| 20 mm | 1/6 | 0.1041 | 0.1410 |
| 40 mm | 0/6 | 0.1109 | 0.1758 |

Success is monotone in magnitude (rho = -1.000; 2 vs 40 mm **p=0.0022**; 5 vs 40 mm p=0.0152; 2 vs
10 mm p=0.061). The mean corrective response rises **+68.7%** from 2 to 5 mm, then +9.2%, then
**-1.5%** from 10 to 40 mm — a 4x further displacement buys no more correction. So the policy's
correction is **capped**, and the cap does not scale with the error. The failure at >=5 mm is not
"the model did not notice" (14F) nor "it replayed stale actions" (14D/14E); it is bounded authority.

**This reconciles 13D's null.** 13D reported no dose-response over 5-20 mm; that design used 4 strikes
and was already at the floor by 5 mm (2/6), so it had no room to show a gradient. Scoped correctly:
repeated strikes saturate the damage, magnitude still matters underneath. README and the 13D section
now say this rather than the absolute version.

Caveat: one low outlier at 2 mm (~0.034) pulls that cell's mean down, so the 2->5 mm jump is partly
between-episode variance; the plateau itself is robust across 5-40 mm.

Artifacts: `evidence/gate14g_magnitude.md`, `evidence/gate14g_magnitude.png`/`.pdf`,
`scripts_setup/gate14g_sweep.sh`, `scripts_setup/gate14g_response.py`,
`scripts_setup/gate14g_figure.py`, `results/gate14g_response.json`.

Plumbing note: the chunk dump now carries the eval seed via `FASTBENCH_RUN_SEED`, set by
`gate13_run.py` per job. `icfg["seed"]` is the *intervention* RNG seed (always 0) — using it silently
collapsed both seeds onto the same dump keys and cost two sweep reruns. Same class of bug as
`cfg["seed"]` (0) and the `_s<N>` directory suffix: read provenance from the artifact that owns it.

## Gate 14H — the cap is in the placement, not the approach (2026-10-19, COMPLETE)

No new GPU runs: measured from the Gate 14G sweep's own records (every step record carries
`state.bodies[...]["pos"]` and `state.eef["pos"]`). `scripts_setup/gate14h_geometry.py` +
`gate14h_figure.py`; evidence in `evidence/gate14h_geometry.md`.

**Result.** Successful episodes end at a *fixed* height regardless of strike: 0.1171 / 0.1193 /
0.1206 / 0.1136 m at 2/5/10/20 mm (control 0.1145). Failures are left above the basket at
0.1735 → 0.1960 → 0.2019 m at 10/20/40 mm. Among failures, z_end vs magnitude rho=+0.728
(p=0.0014, n=16); success vs failure heights 0.1181 vs 0.1825 (MWU p=2.6e-4). xy transport is
fine — min xy distance to the basket is <0.03 m even in the 2/6 and 1/6 cells, and the 10/20 mm
failures end 8.5 / 13.4 mm from the basket centre. So the capped response suffices for transport
and fails at the final descent/release.

**Not a timeout.** All failures hit 430 steps; the height slope over the last 40 steps is median
+0.12 mm/step (range −0.58 to +1.25) and **11/16 are still rising** at the end. Consistent with
Gate 14 §3b's 800-step replication.

**Two modes, as in 13D:** held-high (14/16) and lost-far (2/16 — 5 mm at xy 0.385 m / z 0.034,
40 mm at xy 0.292 m / z 0.038; both had been lifted to z 0.216 / 0.274 first). The lost-far mode
does not scale with magnitude.

**Figure pitfall (fixed):** panel B was first drawn with a linear y axis pinned to the 0.05 m
basket footprint, which put both lost-far episodes outside the plot and stranded a k/n label at
the top border. A vision pass caught it. The axis is now log (0.0008–0.75) so both modes are
visible, and the suptitle was cut back from "the dominant cost is the placement" to a
description of what is plotted.

**Not established:** *why* the descent does not complete (no gripper/contact state in the
records); generality beyond `libero_object:0`; any WAM-vs-baseline claim; the shape of the
gradient at n=6 with two off-mode episodes.

## Gate 14G/H replication to n=9 (2026-10-19)

Seeds 1,2,3 x 3 trials = **9 episodes per magnitude**, tag prefix `g14s9`, original n=6 runs left
intact. All 36 seed-1,2 episodes reproduce the n=6 run **exactly** (same success flag, same step
count), so the harness is deterministic and the n=9 data is the n=6 data plus seed 3.

**What changed: the "plateau" reading was wrong.**

| | n=6 (pilot) | n=9 (authoritative) |
|---|---|---|
| success | 6/6, 5/6, 2/6, 1/6, **0/6** | 9/9, 8/9, 4/9, 1/9, **1/9** |
| mean abs delta | .0611 .1031 .1125 .1041 .1109 | .0556 .0901 .1026 .0998 .1160 |
| reading | "rises 69% then flat" | **response ~ m^0.22; 20x displacement -> 2.09x response** |

At n=6 the 20 mm dip looked like a plateau; at n=9 the 40 mm mean is 13% above the 10 mm mean, so
"flat" is not supportable. Both readings agree that the response grows far more slowly than the
damage, but "flat" and "sublinear" are different claims and only the second survives more data. The
14G doc records the correction and keeps the n=6 JSON as `results/gate14g_response_n6.json`.

Also: **40 mm is 1/9, not 0/9.** The largest displacement is near-impossible, not impossible — the
README no longer says 0/6.

**14H at n=9:** success heights 0.1142 / 0.1244 / 0.1276 / 0.1136 / 0.1165 (control 0.1126; success
mean 0.1202 vs control, MWU p=0.29);
failure heights 0.1799 / 0.2023 / 0.2028 at 10/20/40 mm; among failures rho=+0.606 (p=0.0028);
success vs failure 0.1202 vs 0.1898 (MWU p=1.4e-6); 14/22 failures still rising at timeout.
22 failures = 20 held-high + 2 lost-far (5 mm seed1 ep0, 40 mm seed1 ep1).

**Figure-metadata pitfall (fixed twice):** both figure suptitles carried typed metadata ("n=6,
seeds 1-2") that survived the replication and contradicted the plotted 9/9 labels. Vision audit
caught it both times. `gate14g_figure.py` now reads `n` and `seeds` from the response JSON (the
response script records `seeds` per row) and `gate14h_figure.py` reads `n`/`seeds` from the geometry
JSON. Rule: metadata in a figure title is computed from the data, never typed.

**Script changes:** `gate14g_sweep.sh` takes `SEEDS`, `TRIALS`, `TAGPFX` env overrides;
`gate14h_geometry.py` writes `magnitude_m` into each row so consumers never map a directory name back
to a magnitude.

## Gate 14-I — the release is commanded before the descent (2026-10-19, COMPLETE)

Answers the question 14H left open. No GPU: read from the Gate 14G sweep records, which carry the
executed action, eef pose and object pose every step.

**Sign convention (checked, not assumed):** `robosuite/models/grippers/panda_gripper.py`
`format_action` docstring: **-1 => open, 1 => closed**. I read it the other way first from two
traces that each seemed to support the opposite; the vendored docstring is the authority. Reading it
backwards inverts the entire result.

**Result (n=9/magnitude, grouped by outcome):**
- gripper commanded open: **0.741** of post-strike steps for failures vs **0.114** for successes
- last 40 steps: grip +0.55 (closed) for successes vs -1.00 (open) for failures
- commanded dz last 40: **-0.198** (descending) vs **+0.020** (not descending)
- object height at end: 0.119 m vs 0.205 m
- separation height: 0.108 m (n=19) vs 0.178 m (n=9) — 7 cm too high

**Ordering (the key claim, verified):** in **21/21** failures with a detectable release, the first open
after the grasp precedes that episode's last real downward command; control is the other way round in
5/8. So the release is commanded *before* the descent, not after a stall.

**The 40 mm "1/9 success" is an incidental drop-in** (inspected directly): gripper closed throughout,
object rides to 0.263 m, slips out, falls to 0.117 m into the basket. Read the cell as 0/9 by
placement, 1/9 by luck.

**Not established:** whether the fingers physically open (no finger qpos recorded; actuator ramps at
0.01/step). 13/22 failures keep the object 1.5-2.4 cm from the eef to the end, consistent with the
fingers still cradling it. Also not established: why the policy inverts the order.

**Artifacts:** `evidence/gate14i_release.md`, `evidence/gate14i_release.png`/`.pdf`,
`scripts_setup/gate14i_release.py`, `scripts_setup/gate14i_figure.py`,
`results/gate14i_release.json`.

**Figure pitfalls hit:** `release_z` serialises as NaN for "never separated", so `is not None` let NaN
through and titled a panel "nan" — filter on finiteness. The legend advertised a gray "mean" bar that
was never drawn — replaced with a footnote. Suptitle "Gate 14I" renders as "Gate 141"; write "14-I".
