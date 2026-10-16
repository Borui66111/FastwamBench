# Gate 12D — Root cause of the 0–4% "reproduction gap": wrong OSC action scaling

Date: 2026-10-16

## Symptom

30-task control screen (Gate 12A): 6/150 = **4%** success on standard LIBERO
suites, against the released README's **98.55%** on the same checkpoint and
flags. Gate 12B verified the harness faithful in every other respect
(config, checkpoint contents, task files, init states, observations).

## Finding

Stock robosuite **1.4.0** (downloaded as an sdist via
`pip download robosuite==1.4.0 --no-binary :all:`) was diffed against the
**vendored fork** at
`LIBERO-Safety/third_party/robosuite-1.4/robosuite`.

After normalising the sdist's CRLF line endings, there is exactly **one**
functional difference in the entire package:

```
controllers/config/osc_pose.json

  official 1.4.0     output_max [0.05, 0.05, 0.05, 0.5, 0.5, 0.5]   kp 150
  LIBERO-Safety fork output_max [2, 2, 2, 2, 2, 2]                 kp 750
```

`OSC_POSE` maps a policy action in `[-1, 1]` onto Cartesian translation,
rotation, and gripper commands. The fork's file scales translation **40×**
(2.0 m vs 0.05 m per step), rotation **4×** (2.0 vs 0.5 rad), and stiffens the
gains **5×**. A policy trained on official-LIBERO action statistics therefore
commands wildly oversized motions — it flails and rarely succeeds.

## Runtime confirmation

`robosuite.controllers.controller_factory.load_controller_config()` executed
inside the `fastbench` env returns:

```
output_max [2, 2, 2, 2, 2, 2]   kp 750
```

i.e. the environment really does load the fork's file — this is not a
dead-code difference. (raw output: `/tmp/ctrl.out`)

## Fix

`osc_pose.json` restored to the official 1.4.0 values; the original is
preserved at `osc_pose.json.forkbak`. Post-fix, the vendored fork's Python and
config tree is functionally identical to stock 1.4.0 (only a trailing newline
differs; JSON-compare equal).

## Evidence

| run | tasks | success | rate |
|---|---|---|---|
| pre-fix, 20 trials (spatial t0 / object t0) | 2 | 3/20, 0/20 | 15%, 0% |
| **post-fix, 5 trials (same two tasks)** | 2 | **5/5, 5/5** | **100%** |
| pre-fix 30-task screen (`results/gate12a_screen`) | 30 | 6/150 | **4%** |
| **post-fix 30-task screen (`results/gate12a_screen_fixed`)** | 30 | **148/150** | **99%** |

148/150 = 99.0% against the released README's claimed 98.55% average — the
reproduction gap is closed. The two residual failures are ordinary policy
stochasticity (seeded runs differ only in diffusion noise; 5 trials/task is a
small sample).

## Implication

- The 0–4% success in Gates 8 / 11 / 12A on standard tasks is an **artifact of
  this controller mismatch**, not a property of the model.
- Gate 11's `obstacle_avoidance` 0/2 must be re-run post-fix before any
  behavioural claim is made.
- Gate 9's intervention **mechanism** (45/45 unit tests; `pre_iv_max_l1 = 0.0`)
  is unaffected, but its behavioural results also sit on the broken controller.
- **Gate 13 (paired stale-commitment cost) is now unblocked** — control success
  is usable.

## Lesson

LIBERO-Safety is advertised as "drop-in compatible" with LIBERO, but ships a
modified OSC controller config. Always diff a vendored/forked simulator
against the stock release before trusting downstream numbers from it.

## Verification of the fix

Re-diffed the whole vendored package against the official 1.4.0 sdist with CRLF
normalised: the only remaining difference under `robosuite/**` is a trailing
newline in `osc_pose.json` (JSON-equal: `output_max=[0.05,0.05,0.05,0.5,0.5,0.5]`,
`kp=150`). No other functional difference exists. A few non-Python assets differ
(one mesh `IKE170031`, two 4k textures, an empty `renderers/config` dir) — none
are loaded by LIBERO's manipulation tasks.

## Reversibility

One file, backed up in place:

    cp .../controllers/config/osc_pose.json.forkbak .../controllers/config/osc_pose.json

The official content is also committed as `patches/osc_pose.official.json`.
