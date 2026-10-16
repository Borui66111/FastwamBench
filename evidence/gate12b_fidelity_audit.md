# Gate 12B — Baseline fidelity audit (why we cannot reproduce the released success rates)

> **RESOLVED 2026-10-16 — see `evidence/gate12d_rootcause.md`.** The cause was not the
> harness at all: the vendored `robosuite-1.4` fork under `LIBERO-Safety/third_party/`
> ships a modif...[truncated]

Date: 2026-10-16
Scope: determine whether the ~0–40% control success we observe on standard LIBERO
suites is a *harness bug* (fixable here) or a *task/environment property*.

## Headline

The upstream FastWAM README claims, for the exact checkpoint we run and the exact
flags it documents:

| Inference mode | Spatial | Goal | Object | Long | Average |
| --- | ---: | ---: | ---: | ---: | ---: |
| IDM | 99.0% | 98.6% | 99.6% | 97.0% | **98.55%** |

Our Gate 12A screen (same ckpt, same documented flags, 5 trials/task, 30 tasks)
measured **6/150 = 4.0%** overall:

| suite | tasks | successes/episodes | rate |
| --- | --- | --- | --- |
| libero_spatial | 10 | 5/50 | 10% (t0 40%, t1 40%, t6 20%, rest 0%) |
| libero_object  | 10 | 0/50 | 0% |
| libero_goal    | 10 | 1/50 | 2% (t3 20%) |

So we are ~25x below the published number. This is the central open problem for the
project: Gate 13's stale-commitment cost can only be *behaviourally* measured if the
control arm actually succeeds.

## What we verified as FAITHFUL (rules these out)

1. **Reference command matches.** `scripts_setup/gate12_screen.sh` reproduces the
   README command (`task=libero_optional_idm_2cam224_1e-4`, the release ckpt,
   `dataset_stats_path`, `EVALUATION.sigma_shift=1.0`, `+EVALUATION.action_infer_mode=idm`).
2. **Resolved config matches the repo defaults** (dumped via `--cfg job`):
   `num_frames: 33` → `action_horizon = 32`; `eval_num_inference_steps: 10`;
   `num_steps_wait: 30`; `replan_steps: 10`; `binarize_gripper: true`;
   `use_action_ensembler: false`; `rand_device: cpu`; 2 cameras at 224.
3. **Checkpoint is complete and correctly loaded.** `torch.load` shows
   `mot.mixtures.video.*` (825 keys) **and** `mot.mixtures.action.*` (824 keys), plus
   `proprio_encoder` — i.e. the action expert is present, not randomly initialised.
   `_load_model_checkpoint` → `model.load_checkpoint` reported no missing keys.
   sha256 `26b4efffded221b9a303ca8f2cddb9999c8b7524e2751c855c74a986242ce8b4`,
   12,041,735,545 bytes.
4. **Task definitions are upstream.** `libero_spatial` t0–t9 resolve to the *original*
   bddl/init filenames (no `_add_*` augmentation), 50 init states per task, used in
   file order; task language strings match upstream LIBERO verbatim.
5. **Observations are real.** Frames decoded from the eval videos (256×512×3 — agentview+wrist
   side by side) are bright, textured renders: mean 121.8 / std 57.1 (success episode),
   mean 122.1 / std 56.9 (failure episode) — not black or garbage.
6. **Failure mode is "runs out of steps", not "crashes":** failed episodes consume the
   full 400-step budget (~168–183 s), successes terminate early (~135–146 s).

## Offline adaptations we are FORCED to make (not optional deviations)

The README command cannot run verbatim on this box because it has no HuggingFace
access and the ActionDiT backbone file was never generated:

- `model.redirect_common_files=false` — otherwise the runtime tries to pull
  `DiffSynth-Studio/Wan-Series-Converted-Safetensors` from HF and dies
  (`RepositoryNotFoundError 401`).
- `model.action_dit_pretrained_path=null` + `model.skip_dit_load_from_pretrain=true` —
  `checkpoints/ActionDiT_linear_interp_Wan22_alphascale_1024hdim.pt` does not exist
  locally, so the pretrain-init path must be skipped; the release checkpoint supplies
  those weights instead.

`DIFFSYNTH_MODEL_BASE_PATH` points at `checkpoints/` (Wan2.2-TI2V-5B present, complete).

## Remaining suspect: the LIBERO environment is NOT the official one

FastWAM's README is explicit (line 303):

> Before running the `LIBERO` benchmark, install the **official LIBERO environment**
> first from the LIBERO repository.

This box instead has **LIBERO-Safety** (`libero` 0.1.0, editable) with its own
**vendored robosuite fork** — and that vendored copy is the *only* robosuite on disk:

```
site-packages/__editable__.libero-0.1.0.pth      -> LIBERO-Safety
site-packages/__editable__.robosuite-1.4.0.pth   -> LIBERO-Safety/third_party/robosuite-1.4
site-packages/libero_safety_path.pth             -> LIBERO-Safety
```

So both the benchmark registry *and* the physics/controller stack come from
LIBERO-Safety, not from the official LIBERO that produced the 98.55% table.
LIBERO-Safety advertises "drop-in compatible" and its standard-suite bddl/init files
are the upstream ones, but the vendored robosuite fork is an unverified variable.

## Discriminating experiment (Gate 12C) — RESULT

`scripts_setup/gate12c_ab.sh` ran the same two tasks (`libero_spatial` t0,
`libero_object` t0) at 20 trials each, on two GPUs, differing ONLY in the
non-forced flags. Both arms carry the identical forced-offline flags.

| task | Arm A (upstream flags) | Arm B (ours) | README claim |
| --- | ---: | ---: | ---: |
| libero_spatial t0 | **1/20 (5%)** | **3/20 (15%)** | 99.0% |
| libero_object t0  | **0/20 (0%)** | **0/20 (0%)** | 99.6% |

**Conclusion: our flag set is exonerated.** `load_text_encoder=true`,
`EVALUATION.compile_action_infer=false` and `seed=1` do not explain the gap —
both arms sit at the floor, 1–2 orders of magnitude below the published numbers
(and the two arms are statistically indistinguishable at n=20). The Gate 12A
`libero_spatial` t0 = 2/5 (40%) reading was small-sample luck; at n=20 the true
rate is ~5–15%.

Therefore the gap is **environmental**, not a flag/config/protocol error. Every
other element has been verified faithful (see above), leaving the LIBERO stack
itself as the suspect.

## Next step to resolve it

Rebuild the evaluation environment against the *official* LIBERO exactly as
FastWAM's README prescribes (line 303), in a **separate** env so the current
working setup is not disturbed:

1. fresh env: python 3.10, `torch==2.7.1+cu128`, `pip install -e .` (FastWAM),
   `mujoco==3.3.2`;
2. official `Lifelong-Robot-Learning/LIBERO` + stock `robosuite==1.4.0`
   (instead of LIBERO-Safety's vendored fork);
3. re-run the README command on `libero_spatial` t0 / `libero_object` t0 at 20 trials.

Outcome interpretation:
- If the official stack reaches ~99% → LIBERO-Safety's fork (standard-suite assets,
  regenerated init states, or vendored robosuite) is the cause; the FastWAM numbers
  are reproducible and only the eval environment needs fixing.
- If it also sits at ~5% → the gap is not the LIBERO fork; next suspects would be
  the release checkpoint's provenance or the evaluation protocol upstream used to
  produce the table (which is not fully documented in the README).

This requires package installs and ~GBs of download, so it needs an explicit go-ahead.

## Consequence for the plan

Gate 12A's stated goal ("find a task with 30–90% control success") is currently
satisfied only by `libero_spatial` t0/t1 at 40% — an unusually weak substrate, and
the absolute rate is not trustworthy until the reproduction gap is resolved.
Resolving Gate 12C is therefore the gate to Gate 13.
