# Gate 14J — the fingers really do open

STATUS: **COMPLETE (2026-10-19).** Settles the one thing Gate 14-I could not: does the commanded
release reach the actuator?

Gate 14-I read the commanded action and found the gripper commanded open for 74% of the remaining
episode in failures. But the records carried no finger state, and the actuator ramps at 0.01/step, so
"commanded open" could not be distinguished from "physically open". That left two very different
readings: a geometric failure (released, but too high) or a control-path bug (the command never
reaches the fingers).

## Measurement

Added the finger joint positions to the per-step state snapshot (`snapshot_state`, `fastbench_intervention.py`),
so every step now carries `state.gripper = {joints, qpos, width}`, where `width` is the sum of the two
finger joint displacements. Max attainable width on this gripper is 0.080 m.

Single strike, zero-stale arm, H=10, 0.01 m, `libero_object:0`.

| episode | success | width at end | mean width, last 40 | commanded grip, last 40 |
|---|---|---|---|---|
| s1 ep0 | yes | 0.0536 | 0.0644 | −0.20 |
| s1 ep1 | yes | 0.0772 | 0.0559 | +0.35 |
| s1 ep2 | **no** | **0.0782** | **0.0677** | −0.55 |
| s2 ep0 | **no** | **0.0795** | **0.0787** | −1.00 |
| s2 ep1 | **no** | **0.0773** | **0.0772** | −0.90 |

In every failure the fingers reach 0.077–0.080 m, i.e. **essentially fully open**. This is not a
command that fails to arrive: the actuator moves.

Full block, n=9 at 0.01 m (seeds 1–3 × 3 trials, 4 successes / 5 failures):

| group | max width reached | width at episode end |
|---|---|---|
| success (n=4) | 0.0799 | 0.0536 – 0.0772 |
| failure (n=5) | 0.0799 – 0.0803 | **0.0773 – 0.0795** |

Both groups reach full opening at some point (the gripper opens to approach the object), so "max
width" is not the discriminator. What separates them is where the fingers are *at the end*: failures
finish fully open, and the object is still not in the basket.

## What this settles

**It is not a control-path bug.** The release is real. Combined with Gate 14-I, the sequence is:
the policy opens the gripper while the object is still 0.18–0.20 m up, the fingers open, and the
object is left at that height rather than descending into the basket (Gate 14H: 4–11 cm above the
control placement band, 9–13 mm from the basket centre in xy).

So the remaining explanation is geometric: the object is released at a height from which it does not
end up in the basket. Whether it comes to rest on the basket rim or is otherwise supported there
cannot be read from these records — that needs contact state, which is still not recorded.

## Bonus: independent confirmation of the sign convention

Gate 14-I had to take the gripper sign convention from the vendored controller's docstring
(`-1 => open`, `1 => closed`) after two traces appeared to support opposite readings. The physical
width settles it independently: in the control canary, commanding −1.00 moved the width from 0.0625
to 0.0715 m. Open means open.

## Caveats

- n=9 at 0.01 m (4 successes / 5 failures). The binary question ("do the fingers open at all?") needs
  far less power than the rate question, and the separation is 0.077–0.080 against a 0.080 ceiling —
  but the *rate* at which a fully-open gripper still fails to drop the object is not estimated here.
- Width is the sum of two finger joint displacements, so it is a proxy for jaw opening, not a
  measured gap; it saturates at 0.080.
- Recording this field grows every step record slightly. It is only present in runs made after
  2026-10-19; earlier runs must be re-run to gain it.

## Reproduce

```bash
python scripts_setup/gate13_run.py --tasks libero_object:0 --horizons 10 --seeds 1,2 --trials 3 \
  --arms disturb --magnitude 0.01 --world-trigger-after-lift 0.02 --world-repeat-every 10 \
  --world-repeat-count 1 --zero-stale --tag g14j10 --ngpu 1
```

Artifacts: `results/gate13_g14j10` (seeds 1,2), `results/gate13_g14j10b` (seed 3),
`results/gate13_g14jcanary` (control + one disturb, used for the sign-convention check).
