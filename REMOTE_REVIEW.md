# Remote Review & Cooperation Notes

> Purpose: asynchronous review / coordination between the main server-side worker and remote research support.
>
> **Ownership convention**
> - The main worker on the GPU server remains the primary executor and source of truth for runtime state.
> - This file is advisory: it records research interpretation, validation priorities, and suggested next experiments.
> - Remote-side changes should avoid overwriting active server-side work. Prefer analysis, tests, plotting, docs, and small isolated utilities.
> - When runtime evidence disagrees with this document, update this document rather than forcing the experiment to fit the prior hypothesis.

Last reviewed: 2026-10-16

## 1. Current assessment

The project has moved beyond a toy prototype.

Verified strengths:
- real FastWAM checkpoint execution;
- LIBERO-Safety integrated as the active `libero` package;
- headless MuJoCo / EGL rendering;
- deterministic world-state intervention through free-joint `qpos` displacement;
- structured JSONL recorder with replan / step / intervention / episode-end events;
- deterministic paired control-vs-disturbance runs after pinning the seed;
- intervention unit coverage (45 checks);
- sweep over `replan_steps ∈ {1,5,10}`;
- root-cause analysis of the `sigma_shift` mismatch;
- evidence that the post-intervention action plan changes after the model observes the displaced world.

This means the benchmark mechanism is now real and causally controlled.

## 2. Gate 11 interpretation guardrail

Because the intervention is injected after an action chunk is planned and the policy is only queried again at the next fixed replan boundary:

```
plan chunk from old world
→ intervene
→ execute remaining chunk
→ next replan
→ observe changed world
→ generate new chunk
```

therefore:

```
stale_window == replan_steps
```

is primarily a protocol / harness consequence, not by itself a scientific discovery.

Avoid:
> “FastWAM chooses to continue stale actions for 10 steps.”

Prefer:
> “Under fixed-horizon chunk execution, FastWAM cannot incorporate a world-state change until the next replanning boundary.”

The genuinely informative causal signal is:
1. control and disturbance are identical before intervention;
2. the world alone is changed;
3. the pre-computed chunk remains unchanged;
4. at the first post-intervention replan, the new action plan differs substantially from control.

This supports:
```
world-state change
→ post-observation policy-plan change
```

with pre-intervention equality acting as the causal control.

## 3. What Gate 11 currently supports

Current evidence supports a behavioral H3 probe:

> A plan generated from a pre-intervention world becomes stale after the world changes; under fixed-horizon execution it is fully executed until the next replan, and once the changed world is observed the newly generated plan changes.

Current Gate 11 does **not yet** support:
- recovery-rate claims;
- success-drop claims;
- “WAM is better/worse than VLA” claims;
- “future modeling specifically caused the adaptation” claims.

Reason: the tested obstacle-avoidance task has 0% success in both control and disturbed arms, and no VLA / alternative inference-mode comparison has yet isolated WAM-specific benefit.

## 4. Highest-priority next work: Gate 12

### Gate 12A — find usable baseline tasks

Run a systematic control-only task scan before adding more intervention types.

Target:
```
30% <= control success <= 90%
```

Why:
- 0% gives no recovery signal;
- 100% may be too easy and hide intervention effects;
- mid-range tasks allow measurable degradation and recovery.

Suggested initial scan:
- LIBERO Spatial;
- LIBERO Object;
- LIBERO Goal;
- LIBERO-Safety obstacle_avoidance L0/L1;
- optionally LIBERO-10 if runtime budget allows.

Screening:
```
5 trials/task
```

Then rerun best candidates:
```
10-20 trials/task
```

Suggested output:
| suite | task_id | level | trials | success | mean_steps | notes |
|---|---:|---:|---:|---:|---:|---|

Select 2-3 tasks with reproducible non-zero control success and stable behavior.

### Gate 12B — baseline fidelity

The `sigma_shift=1.0` fix is important and restores non-zero performance, but standard-LIBERO success remains far below the reported upstream level.

Do not block benchmark construction on perfect reproduction, but do not declare baseline fidelity fully solved.

Continue checking:
- exact checkpoint / config pairing;
- task config choice;
- action inference mode;
- horizon / replan interaction;
- image preprocessing;
- init-state protocol;
- upstream commit drift;
- manager path vs per-task worker;
- stochastic settings beyond seed and sigma shift.

Deliverable: short table of “verified identical / still uncertain” factors.

## 5. Gate 13 — first real recovery experiment

Once a baseline task succeeds reliably:

```
control world
→ success possible

disturbed world
→ intervention after chunk planning
→ measure whether model recovers
```

Core metrics:
- Control Success Rate
- Disturbed Success Rate
- Success Drop
- Recovery Rate
- Recovery Latency
- Stale Action Steps
- Post-intervention Plan Divergence
- Safety Violation / Collision if available

Recommended recovery definition:

> Recovery = after an intervention invalidates the currently executing plan, the policy subsequently produces a post-intervention plan that leads the rollout back to a valid task-completing trajectory without violating the active safety constraint.

Paired reporting:
```
RecoveryRate =
successful disturbed episodes
/
disturbed episodes whose control counterpart succeeds
```

## 6. Gate 14 — make the result WAM-specific

Preferred comparison if supported cleanly by the released checkpoint/config:

```
same FastWAM checkpoint
same task
same init state
same seed
same intervention
same replan horizon

first_frame inference
vs
IDM / future-aware inference
```

This controls weights, data, embodiment, simulator, task, and intervention while changing how future information is used at inference.

If this comparison is not technically clean, use:
```
FastWAM
vs
one strong VLA baseline
```
under the exact same paired intervention protocol.

Only after this should we make WAM-specific robustness/failure claims.

## 7. Difficulty scaling for first H3 suite

Do not add many unrelated perturbations yet.

Freeze one H3 suite first with three severities, e.g. target/object displacement:

### L0
- early intervention;
- large visible displacement;
- far from contact phase.

### L1
- medium displacement;
- later intervention;
- during approach / transport.

### L2
- smaller but task-critical displacement;
- near contact / placement / safety boundary.

Keep each level parameterized and reproducible.

## 8. Presentation-quality result target

A strong first package:
```
2-3 tasks
× 3 disturbance levels
× 2 inference/model conditions
× 10-20 paired seeds
```

with:
1. success / recovery heatmap;
2. stale-window / replanning-horizon curve;
3. plan-divergence plot;
4. one qualitative rollout strip (control vs disturbed);
5. paired control-success / disturbed-recovery table.

## 9. Suggested division of labor

### Main server-side worker
- environment and checkpoint execution;
- long GPU sweeps;
- runtime debugging;
- task screening;
- evidence capture;
- raw JSONL / result JSON / videos.

### Remote support
- inspect new commits/results;
- review metric validity;
- detect confounds / protocol artifacts;
- analysis and plotting utilities;
- benchmark-spec/schema design;
- paper/presentation interpretation;
- lightweight tests that do not require GPU;
- code review of intervention/recorder/analyzer logic.

Avoid remote edits to files actively being changed on the server unless coordinated.

## 10. Evidence discipline

For every headline result preserve:
- upstream FastWAM commit;
- LIBERO-Safety commit;
- FastwamBench commit;
- checkpoint filename/hash if practical;
- exact config overrides;
- task/suite/level/task_id;
- seed;
- replan_steps;
- intervention type / target / magnitude / trigger;
- number of trials;
- raw per-episode records.

Every aggregate figure should be reproducible from machine-readable results.

## 11. Immediate recommended action

Next server-side action:
```
Gate 12A:
systematically scan control success
→ rank tasks
→ select 2-3 viable tasks
```

in parallel with:
```
Gate 12B:
continue baseline-fidelity diagnosis
```

Do **not** spend the next iteration inventing another intervention.

Once a task with real control success is found, immediately run paired H3 disturbance and compute recovery.

## 12. Current research claim ladder

### Already supportable
> We built a deterministic paired-intervention harness for FastWAM in LIBERO-Safety. Control and disturbed rollouts are identical before intervention. A mid-chunk world-state displacement invalidates the current plan; under fixed-horizon execution the stale chunk persists until the next replan, after which the generated action plan changes relative to control.

### Not yet supportable
> FastWAM reliably recovers from world-state changes.

> WAMs are more robust than VLAs.

> Explicit future modeling improves recovery.

> FastBench exposes a WAM-specific advantage over standard VLA evaluation.

## 13. Coordination template

When a major gate finishes, update the review thread with:

```
STATUS:
EVIDENCE:
INTERPRETATION:
OPEN QUESTION:
NEXT ACTION:
```

Fresh runtime evidence always overrides this review.
