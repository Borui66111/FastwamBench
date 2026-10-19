# Gate 14-I — the release is commanded early, at the wrong height

STATUS: **COMPLETE (2026-10-19), n=9 per magnitude.** Answers the question Gate 14H left open: *why*
does the descent stop? No new GPU runs — measured from the Gate 14G sweep records, which carry the
executed action, the eef pose and the object pose on every step.

## Sign convention, checked against the controller

`robosuite/models/grippers/panda_gripper.py`, `format_action` docstring: **`-1 => open`, `1 => closed`.**
This matters: reading it the other way round inverts the whole result, and I did read it the other way
first, from two traces that each supported a different convention. The vendored docstring is the
authority.

## Result

Grouped by outcome across all five magnitudes:

| quantity (mean over episodes) | success (n=32) | failure (n=22) |
|---|---|---|
| fraction of post-strike steps commanding **open** | **0.114** | **0.719** |
| gripper command, last 40 steps | +0.55 (closed) | **−1.00 (open)** |
| commanded vertical motion, last 40 steps | **−0.198** (descending) | **+0.020** (not descending) |
| object vertical motion, last 40 steps | −3.9 mm/step | +0.1 mm/step |
| object height at episode end | 0.118 m | 0.190 m |
| object height when it leaves the gripper | 0.108 m (n=19) | 0.178 m (n=9) |

Three things follow.

**1. The failures open the gripper, and they open it early.** Not "the policy forgets to release" —
it commands the gripper open for 72% of the remaining episode, against 11% for successes, which open
only in their final steps.

**2. They open it *before* any sustained descent, not after.** In all 21 failures with a detectable
release, the first open after the grasp precedes that episode's last real downward command; control is
the other way round in 5 of 8, opening at or after the end of its descent. So the failure is not a
descent that stalls and then releases — the release is commanded first, while the object is still high.

**3. So the release happens at the wrong height.** Among the episodes where the object does leave the
gripper, successes separate at 0.108 m and failures at 0.178 m: **7 cm too high**, consistent with
Gate 14H's 4–11 cm stall. And 13 of 22 failures never separate at all.

The control strategy is: keep the gripper closed, lower the object to 0.10–0.13 m, then open briefly.
The disturbed policy inverts the order — open, while still high, without lowering first.

## The single 40 mm success is an incidental drop-in

Inspected directly, not inferred. Seed 3 episode 1 at 40 mm: the gripper is **closed throughout**
(`open_frac` = 0.00), the object rides with the eef from z=0.039 up to **0.263 m**, drifts out of the
fingers (`|eef−object|` grows 0.013 → 0.042), is carried to the basket at 0.26 m, and then falls
0.263 → 0.117 m in the last few steps, landing in the basket.

So the 1/9 at 40 mm is not a recovered placement: it is a slipped object that happened to fall in.
The 40 mm cell is better read as 0/9 by placement and 1/9 by luck. This is the only success in the
sweep whose release height (0.24 m) sits outside the success cluster.

## What this establishes, and what it does not

**Establishes.** The stall is not the arm failing to move a held object, and not a slip: the eef and
the object move together (group means −3.55 and −3.81 mm/step in successes, +0.12 and +0.11 in
failures). It is a *sequencing* failure — the release is commanded before the descent.

**Does not establish.** Whether the fingers physically open. The records carry the commanded action
but not the finger qpos, and the actuator ramps at 0.01/step, so a commanded open takes many steps to
complete. In 13 of 22 failures the object stays 1.5–2.4 cm from the eef to the end, which is
consistent with the fingers still cradling it — so "the object is released and left on the rim" is a
plausible reading, not a measured one.

**Also not established:** why the policy inverts the order. That is a policy question these records
cannot answer.

## Reproduce

```bash
python scripts_setup/gate14i_release.py \
  --runs results/gate13_g14s9ctl results/gate13_g14s9m0002 results/gate13_g14s9m0005 \
         results/gate13_g14s9m001 results/gate13_g14s9m002 results/gate13_g14s9m004 \
  --json results/gate14i_release.json
python scripts_setup/gate14i_figure.py     # -> evidence/gate14i_release.png/.pdf
```

Figure: `evidence/gate14i_release.png`. Panel A: gripper-open fraction by outcome and magnitude.
Panel B: separation height. Both with per-episode points; bars are group means.

## Caveats

- The separation threshold is `|eef − object| > 5 cm`. Successes leave the object in a small basket
  near the gripper, so only 19 of 32 successes register a separation at all; the metric is a proxy for
  "left the gripper", not a contact measurement.
- `open_frac` is measured over post-trigger steps, which have different lengths for successes (they
  end early) and failures (they run to the cap). It is a rate, so it is comparable, but the underlying
  windows differ.
- n=9 per magnitude, single task, single checkpoint.
