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
  test_gate9_intervention.py   unit tests (45 checks) for the intervention mechanism
patches/                our changes to the upstream FastWAM tree (it is NOT vendored here)
evidence/               curated text/JSON results backing the conclusions
my_test/fastbench_handoff/   the onboarding brief + live STATE.md / CHANGELOG.md
server_notes/           host/GPU inventory captured during bring-up
```

**Nothing upstream is vendored.** `FastWAM/` and `LIBERO-Safety/` are separate clones and are gitignored.
Our modifications to FastWAM are exported as a patch in `patches/`.

---

## Quickstart

Everything below assumes the fastbench project root as the working directory.

### 1. Upstream checkouts (not tracked here)

```bash
git clone https://github.com/yuantianyuan01/FastWAM         FastWAM
git clone https://githubfast.com/LIBERO-SAFETY/LIBERO-Safety LIBERO-Safety
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
```

---

## Two flags that MUST be passed (both were silent footguns)

These are the two things that will waste your day if you don't know them:

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

**Conclusion (H3, "world-model commitment"):** the model commits to a plan built on a world that no longer
exists, pays the full stale window for it, and corrects only at the next replanning boundary.

---

## Provenance

- FastWAM: `github.com/yuantianyuan01/FastWAM` @ `7faa711`
- LIBERO-Safety: `githubfast.com/LIBERO-SAFETY/LIBERO-Safety` @ `19ec8df2`
- FastWAM weights: `yuanty/fastwam` (release checkpoint), base model `Wan-AI/Wan2.2-TI2V-5B`
- Upstream components remain under their own licenses; this repo contains only our harness, patches,
  and results.
