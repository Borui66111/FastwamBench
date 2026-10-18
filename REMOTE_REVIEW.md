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
| carry (strikes after lift) | 6/6 → 2/6 (H1), 1/6 (H10) | 5/6 → **2/6** (H1), 6/6 → **1/6** (H10) | identical (p=1.00) |
| carry, 800-step budget | 4/12 | **4/12** | identical (p=1.00) |
| approach (strike at step 40) | 12/12 → 11/12 | 11/12 → **5/12** | pathway difference, but **7/7 failures are 430-step timeouts** |

So the carry-phase damage is **not** specific to future-aware inference — it is a property of
fixed-horizon chunk execution. The one pathway difference found (approach regime) is budget-mediated
rather than a different failure mode, and its 800-step replication is still running.

Consequences for the review document:
1. The headline claim must be restated as a property of the **execution protocol**, not of the WAM.
2. The predicted-future fidelity result (≈−4.4 dB at lag ≥ 4, flat in horizon) is untouched — it is
   the one measurement that is specific to the video pathway, and it does not support a
   *task-success* claim.
3. Anything written earlier that says "the world model commits to a stale future" should be read as
   "the chunk is replayed while stale", which is protocol-level.

Full write-up: `evidence/gate14_wam_specificity.md`, figure `evidence/gate14_wam_specificity.png`.

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
