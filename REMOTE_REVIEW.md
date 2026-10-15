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
