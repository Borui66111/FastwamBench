# FastBench Agent Instructions

## Mission
Build and validate **FastBench**, an evaluation benchmark for World Action Models (WAMs) on top of LIBERO / LIBERO-Safety. The current MVP focuses on controlled interventions that test whether a WAM's action/future/reality relationships remain coherent, rather than only whether the task eventually succeeds.

## Read before editing
Read these files in order:
1. `WARM_START.md` — current handoff and exact execution plan.
2. `STATE.md` — current verified state and open blockers.
3. `REQUIREMENTS.md` — scientific/software requirements that must not drift.
4. `INTEGRATION_PLAN.md` — verified FastWAM/LIBERO-Safety hook points.

Do not infer project state from old chat context when these files disagree; update these files when new execution evidence changes the state.

## Non-negotiable research rules
- Do **not** assume WAMs are better than VLAs. VLA baselines are controls.
- Separate **behavioral metrics** (all policies can be scored) from **future-specific metrics** (only models exposing future representations).
- Do not compare raw latent vectors across unrelated architectures.
- Do not call a toy/unit-test result a robotics result.
- Distinguish `Observed`, `Inferred`, and `Unknown` in investigation notes.
- Preserve exact seeds, configs, checkpoint paths, git SHAs, and result files for every reported experiment.

## Engineering rules
- Start from one concrete rollout and trace it end-to-end before broad refactors.
- First reproduce an **unmodified official FastWAM LIBERO rollout**. Do not add FastBench hooks before that baseline runs successfully.
- Keep upstream changes minimal. Prefer FastBench wrappers/adapters over invasive edits.
- The primary FastWAM hook is `experiments/libero/eval_libero_single.py::run_single_episode`.
- The LIBERO-Safety task registry is `libero/libero/benchmark/vla_safety_task_map.py`.
- For free-joint object intervention, modify joint qpos and call simulator forward; do not treat `body_xpos` as the primary writable state.
- Save results after every episode so Spot/preemptible interruption is recoverable.

## Verification gates
A change is not complete until it has been executed through its real interface.
For each major milestone, record:
- exact command;
- environment/GPU details;
- pass/fail output;
- result artifact paths;
- any deviation from the expected plan.

Run existing prototype tests after touching generic FastBench logic:
```bash
python -m unittest discover -s tests -v
```

## Documentation
Every notable code/config change must update:
- `STATE.md` — current status, evidence, blockers, next step;
- `CHANGELOG.md` — Issue → Reason → Fix → Verification.

Do not overwrite prior evidence; append or clearly supersede it.
