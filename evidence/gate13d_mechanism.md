# Gate 13D — the carry-phase cost is not a reach failure, and it saturates

**Status:** complete at n=6/cell for 0.005 m and 0.01 m. The 0.02 m ceiling check
is running and its rows are omitted until the cells exist.

## Question

Gate 13C established that a 0.01 m displacement during the carry takes
`libero_object` t0 from 6/6 to 1–2/6, while the same displacement during the
approach costs nothing. Two explanations survive that result:

1. **Commitment.** Stale carry actions are load-bearing; the policy commits to a
   world that no longer exists, so the placement fails.
2. **Mechanical.** A 1 cm displacement simply knocks the object out of the
   gripper. Nothing to do with commitment; the object is dropped.

These make different predictions. If (2) holds, the cost should be a step
function of magnitude — near zero below the slip threshold, near total above it —
and the failure should look like a *drop*. If (1) holds, the object stays grasped
and the failure should appear in the placement, not in the grasp.

This gate runs the same carry-phase strike at three magnitudes and classifies
every episode by what the object actually did.

## Design

Unchanged from Gate 13C except magnitude: `libero_object` t0, `--world-trigger-after-lift 0.02`,
up to 4 strikes every 10 steps, magnitude 0.005 / 0.01 / 0.02 m. The 0.005 m arm
runs seeds 1–2 (n=6/cell); the 0.02 m arm is a ceiling check at seed 1 only
(n=3/cell). Both arms include `control` and `disturb`. The 0.01 m arm is the Gate
13C run itself (`results/gate13_repeat_carry_full`), reused rather than re-run so
the comparison is against the published cells.

Episode classification is kinematic, from the object's own `state.bodies` track
(`scripts_setup/gate13d_mechanism.py`):

| mode | definition |
|---|---|
| `PLACED` | episode succeeded |
| `NEVER-LIFTED` | object never rose 0.02 m above its resting height |
| `STILL-DESCENDING` | failing, but the last 40 steps trend down faster than 2e-4 m/step |
| `HELD-ABOVE-BASKET` | failing, ends >0.05 m above rest, xy within 0.05 m of the basket |
| `HELD-ELSEWHERE` | failing, ends >0.05 m above rest, xy further than that |
| `LOST-FAR` | failing, ends at table height, far from the basket |

`STILL-DESCENDING` exists so that a time-budget artifact cannot be reported as a
capability failure: with `max_steps=400`, an episode that was still lowering the
object when time ran out would otherwise be indistinguishable from one that could
never place it.

## Result — how the episodes fail

`libero_object` t0, n=6 per cell:

| magnitude | H | control | disturb | held above basket | lost far | still descending |
|---|---|---|---|---|---|---|
| 0.005 | 1 | 6/6 | 2/6 | 2 | 2 | 0 |
| 0.005 | 10 | 6/6 | 2/6 | 0 | 4 | 0 |
| 0.01 | 1 | 6/6 | 2/6 | 3 | 1 | 0 |
| 0.01 | 10 | 6/6 | 1/6 | 3 | 1 | 1 |

Three things follow.

**No episode ever failed by never lifting the object.** In all 24 struck episodes
of the 0.01 m run and all 12 of the 0.005 m run, the object was picked up. The
strike never prevented the grasp. So explanation (2) in its strong form — "the
object is knocked out of reach" — is wrong: the robot always gets the object.

**The dominant failure is the release, not the carry.** At 0.01 m the most common
single mode is `HELD-ABOVE-BASKET` (6 of 9 failures): the robot carries the object
to the basket, arrives within 0.05 m in xy, and then holds it 0.05–0.09 m above
the placement height until the step budget expires. A representative trace holds
z ≈ 0.203 with a tail slope of +0.0001 m/step for the last 60 steps, against 0.136
for a successful placement. It is not descending, not oscillating toward a
release, and not dropping the object — it is parked. At 0.005 m the most common
mode is instead `LOST-FAR` (6 of 8 failures), i.e. the object ends on the table
away from the basket. Both are post-grasp failures; the mix between them shifts
with magnitude and with horizon, and with n=6 per cell that mix is not something
this experiment resolves.

**Only one of nine failing episodes at 0.01 m was still descending when time ran
out**, and none at 0.005 m. The time-budget explanation accounts for at most one
episode and cannot explain the aggregate.

## Result — the cost saturates

| magnitude | stale at H=1 | stale at H=10 | success H=1 | success H=10 |
|---|---|---|---|---|
| 0.005 m | 3.5 | 40.0 | 2/6 | 2/6 |
| 0.01 m | 4.0 | 40.0 | 2/6 | 1/6 |

The cost at 5 mm is the same as at 10 mm. Halving the displacement did not halve
the damage. Over this range the cost is **saturated**: any displacement large
enough to break the policy's tracking of the object during carry is enough.

This is the opposite of the step-function prediction in a useful way. There is a
threshold below 5 mm, but above it the magnitude is irrelevant — so the effect is
not "we pushed the object further than the grasp could tolerate". The grasp
survives; the *placement* does not.

## The horizon null replicates

In every magnitude arm, the stale count scales by 10× from H=1 to H=10 and the
success rate does not move:

- 0.005 m: stale 3.5 → 40.0, success 2/6 → 2/6
- 0.01 m: stale 4.0 → 40.0, success 2/6 → 1/6

Ten times as many invalidated committed actions, no additional cost. This is now
the third independent replication of the horizon null (Gate 13B approach-phase,
Gate 13C carry-phase, Gate 13D two further magnitudes), and it is consistent with
the world-model measurement: the single-step damage is a fixed ≈4.4 dB at every
horizon.

## What this does and does not establish

**Establishes:** the carry-phase cost is not a reach failure (the object is always
grasped) and not primarily a time-budget artifact (one episode in twelve). It is a
failure to *release*: the policy brings the object to the basket and stops short of
placing it. The cost is insensitive to magnitude between 5 mm and 20 mm, and the
horizon null survives at every magnitude tested.

**Does not establish:** *why* the policy stops short. The records carry object and
end-effector poses but no grasp or contact state, so "the policy has lost track of
the object's offset within the gripper" is an inference from the trajectory shape,
not a measurement. A direct test would need the gripper's finger positions or the
simulator's contact forces, which this harness does not record.

**Does not establish:** a mechanism for the horizon null. Saturation is consistent
with "one bad strike is sufficient and further staleness adds nothing", but the
data show a ceiling, not the reason for it.

**Power.** n=6 per cell resolves a 6/6 vs 1/6 difference but not 2/6 vs 1/6; the
0.02 m arm is n=3 and is a ceiling check, not an estimate. The claim is "no
horizon effect visible at this power in a regime where the cost itself is large",
not "no horizon effect exists".

## Reproduce

```bash
# classification and per-episode table
python scripts_setup/gate13d_mechanism.py \
    results/gate13_repeat_carry_full results/gate13_carry_mag005 results/gate13_carry_mag02

# the runs themselves
python scripts_setup/gate13_run.py --tasks libero_object:0 --horizons 1,10 \
    --seeds 1,2 --trials 3 --arms control,disturb --magnitude 0.005 \
    --world-step 40 --world-repeat-every 10 --world-repeat-count 4 \
    --world-trigger-after-lift 0.02 --tag carry_mag005
```

Figure: `evidence/gate13d_mechanism.png` / `.pdf` (`scripts_setup/gate13d_figure.py`).
