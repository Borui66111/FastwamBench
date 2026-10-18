# Remote Review

Last updated: 2026-10-16

This file is the remote-side handoff to the main GPU/server worker. Runtime evidence on the server is the source of truth.

## Current status

FastBench has passed the prototype stage. The repo now has:

- real FastWAM execution with released checkpoints;
- LIBERO-Safety integrated and headless MuJoCo/EGL working;
- deterministic mid-chunk world-state intervention;
- structured step/replan/intervention recording;
- paired control-vs-disturbance runs with pinned seeds;
- Gate 11 sweep for `replan_steps ∈ {1,5,10}`;
- verified diagnosis of the `sigma_shift` mismatch.

## Interpretation guardrail

For Gate 11, because the intervention is injected **after the chunk is planned** and the model cannot query the environment again until the next fixed replan boundary:

```
stale_window == replan_steps
```

is mainly a property of the execution protocol / harness.

Do **not** headline this as:

> FastWAM chooses to execute stale actions for N steps.

Use:

> Under fixed-horizon chunk execution, a world change cannot affect the current action chunk until the next replanning boundary.

The stronger causal result is:

1. control and disturbance are identical before intervention;
2. only world state is changed;
3. the current chunk remains unchanged;
4. at the first post-intervention replan, the new action plan differs from control.

This supports a controlled H3 **Future-Reality Divergence** probe.

## Claims currently supported

> We built a deterministic paired-intervention harness for FastWAM in LIBERO-Safety. A mid-chunk world-state change invalidates the current plan; under fixed-horizon execution the stale chunk persists until the next replan, after which the generated action plan changes relative to control.

## Claims not yet supported

Do not yet claim:

- reliable recovery;
- intervention-caused success drop;
- WAM > or < VLA;
- future modeling specifically improves robustness.

The current obstacle-avoidance task has 0% success in both control and disturbed arms, so it cannot provide a recovery signal.

## Next priority: Gate 12

### Gate 12A — find usable baseline tasks

Before adding more intervention types, scan control-only task success.

Target tasks with roughly:

```
30% <= control success <= 90%
```

Suggested first pass:

- LIBERO Spatial
- LIBERO Object
- LIBERO Goal
- LIBERO-Safety obstacle_avoidance L0/L1

Use about 5 trials/task for screening, then 10-20 trials for the best 2-3 tasks.

Commit a machine-readable summary:

```
suite, task_id, level, trials, successes, success_rate, mean_steps
```

### Gate 12B — baseline fidelity

The `EVALUATION.sigma_shift=1.0` fix restored non-zero performance, but standard-LIBERO performance is still far below the upstream reported level.

Continue checking in parallel:

- checkpoint/config pairing;
- inference mode;
- image preprocessing;
- init-state protocol;
- action horizon / replanning;
- manager path vs per-task worker;
- upstream commit drift;
- remaining stochastic/config differences.

Do not block benchmark construction on perfect reproduction, but do not call baseline fidelity fully solved.

## Gate 13 — first real recovery result

Once a task has reliable control success, run paired:

```
control
vs
disturbance
```

with the same task, init state, seed, model config, and replan horizon.

Measure:

- Control Success Rate
- Disturbed Success Rate
- Success Drop
- Recovery Rate
- Recovery Latency
- Stale Action Steps
- Post-intervention Plan Divergence
- Safety violation / collision where available

Recommended paired recovery metric:

```
RecoveryRate =
successful disturbed episodes
/
disturbed episodes whose paired control succeeds
```

Recovery should mean successful adaptation after the old plan becomes invalid, not merely “the action changed.”

## Gate 14 — make the result WAM-specific

Preferred clean comparison, if technically supported:

```
same FastWAM checkpoint
same task / seed / intervention / replan horizon

future-aware / IDM inference
vs
non-future / first-frame inference
```

This is preferable to immediately comparing unrelated models because most factors remain controlled.

If this comparison is not clean, use one strong VLA baseline under the exact same paired protocol.

Only after Gate 14 should we make WAM-specific robustness/failure claims.

**Result (2026-10-19): the WAM-specificity claim fails, in the regime that mattered.**

The comparison was run exactly as specified above — same checkpoint, task, seeds, intervention and
horizons, with `EVALUATION.action_infer_mode` switched between `idm` (future-aware) and
`first_frame` (non-future). It needed no new checkpoint: the switch is one config key.

| regime | `idm` control → disturb | `first_frame` control → disturb | verdict |
|---|---|---|---|
| carry (strikes after lift) | 6/6 → 2/6 (H1), 1/6 (H10) | 5/6 → **2/6** (H1), 6/6 → **1/6** (H10) | same counts (p=1.00); CI ±0.44, so "not equal", "no detectable difference" |
| carry, 800-step budget | 4/12 | **4/12** | same counts (p=1.00), CI ±0.34 |
| approach (strike at step 40) | 12/12 → 11/12 | 11/12 → **5/12** (400 steps), **12/12 → 5/12** (800 steps, p=0.0046) | pathway difference is **real, not budget-mediated**; failures are missed grasps (3) and lost objects (4) |

So the carry-phase damage is **not** specific to future-aware inference. The one pathway difference
found (approach regime) is real: doubling the step budget leaves the disturb cell at 5/12 while the
control cell becomes 12/12 (p=0.0046), and the failures change form (3 missed grasps, 4 objects lost)
rather than merely taking longer.

**Gate 14D then removes the protocol explanation too.** Same single strike, same H=10, dropping 9 of the
10 already-planned actions: **2/6 either way**, the same two episodes succeeding one step apart
(202/169 vs 203/171), four failures each at the 430-step cap, p=1.0000 — with `stale_action_steps`
10 → 1 and `dropped_stale_count` 0 → 9 proving the manipulation fired. The cost is therefore a property
of the **displacement**, not of the execution protocol that replays a stale plan.

Consequences for the review document:
1. The headline must **not** be restated as a property of the execution protocol — 14D tested that and
   it failed. The supportable claim is narrower: a mid-chunk world displacement in a contact-rich phase
   costs success, and the cost is not proportional to how many already-planned actions are replayed.
2. The horizon gradient (4 strikes 1/6 vs 1 strike 2/6 at H=10; one strike at H=10 equal to the
   four-strike H=1 cell) is **unexplained**. Stale-action count was the natural candidate and it is inert.
3. The predicted-future fidelity result (≈−4.4 dB at lag ≥ 4, flat in horizon) is untouched — it is
   the one measurement that is specific to the video pathway, and it does not support a
   *task-success* claim.
4. Anything written earlier that says "the world model commits to a stale future" should be read as
   "the chunk is replayed while stale" — and that replay is now shown **not** to be what costs the
   episode.

Full write-ups: `evidence/gate14_wam_specificity.md`, `evidence/gate14d_drop_stale.md`; figures
`evidence/gate14_wam_specificity.png`, `evidence/gate14_matrix.png`.

## First presentable benchmark target

A strong first result package is enough at:

```
2-3 tasks
× 3 disturbance levels
× 2 inference/model conditions
× 10-20 paired seeds
```

with:

1. success / recovery heatmap;
2. replanning-horizon vs stale-execution plot;
3. plan-divergence plot;
4. one qualitative control-vs-disturbance rollout;
5. paired control-success / disturbed-recovery table.

**Coverage against that target (2026-10-19):**

| element | target | have | status |
|---|---|---|---|
| tasks | 2–3 | 2 (`libero_object:0`, `libero_spatial:0`) | met |
| disturbance levels | 3 | 3 magnitudes (5/10/20 mm) + 2 regimes (approach / carry) | met |
| inference conditions | 2 | 2 (`idm`, `first_frame`) | met |
| paired seeds | 10–20 | 6 per cell (2 seeds × 3 trials) | **short** — per-cell tests underpowered, pooled tests significant |
| (1) success/recovery heatmap | required | `evidence/gate14_matrix.png` (`scripts_setup/gate14_heatmap.py`) | met |
| (2) horizon vs stale execution | required | `evidence/gate13_commitment_cost.png` | met |
| (3) plan divergence | required | `evidence/gate13_psnr_*.png` (≈−4.4 dB) | met |
| (4) qualitative rollout | 1 | `evidence/gate14_rollout.png` (`scripts_setup/gate14_rollout.py`, trial 2: control success 222 steps vs disturbed 430-step failure) | met |
| (5) paired control/disturb table | required | `results/gate13_summary.json` + README tables | met |

## Coordination

Main server worker owns:

- GPU runs;
- environment/runtime debugging;
- task screening;
- raw evidence and videos.

Remote side can contribute:

- code/result review;
- metric validity checks;
- confound detection;
- plotting/analysis utilities;
- lightweight tests;
- benchmark-spec design;
- research/presentation interpretation.

For each completed gate, please record:

```
STATUS:
EVIDENCE:
INTERPRETATION:
OPEN QUESTION:
NEXT ACTION:
```

Fresh runtime evidence overrides this note.
