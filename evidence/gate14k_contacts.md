# Gate 14K — the object never leaves the hand

STATUS: **COMPLETE (2026-10-19).** n=15 (7 success / 8 failure), seeds 1-5, H=10, one strike, 0.01 m.

Gate 14-I measured the release *command*: failures open the jaw for 72% of post-strike steps.
Gate 14J measured the finger *joints*: they reach 0.077-0.080 of a 0.080 ceiling. Both are true.
Gate 14K measures *contact*, and shows the release never actually happens.

## Measurement

Per episode, over the last 40 step records: which bodies the manipulated object touches, the deepest
penetration, the finger width, and how far the object sits below the eef.

| group | n | object height at end | width at end | basket contacts | left-finger | right-finger | offset below eef |
|---|---|---|---|---|---|---|---|
| success | 7 | 0.112-0.137 m | 0.054-0.066 | 0-12 | 38-717 | 0-58 | -0.006 to -0.058 m |
| failure | 8 | 0.150-0.205 m | 0.054-0.080 | **0** (6 of 8) | 120-200 | **0** | **-0.005 to -0.012 m** |

The offset column is the discriminator. In 6 of 8 failures the object sits a **fixed 5-12 mm below
the eef** — it is still being carried. In the successes that work, the object has fallen 3.8-5.8 cm
below the eef, i.e. it left the hand and dropped into the basket. The two successes that end at
0.136-0.137 m with a 6-7 mm offset are placements: the object was lowered to placement height and is
still held when the episode ends, which the task counts as success.

## What this changes about Gate 14-I

14-I said the policy "commands the release too early and stops commanding descent", and inferred the
object was placed on the basket rim. Contact refutes the rim reading: in 6 of 8 failures the object
touches the basket **zero** times. It never gets close enough.

The ordering result from 14-I stands — failures open the jaw before their last downward command — but
it now reads differently. The jaw opens, the object stays with the hand (pressed into the left finger,
~9 mm penetration, a fixed offset below the eef), and because the hand stops descending, the object is
carried at 0.15-0.21 m until the episode times out. **The release is commanded but not achieved; the
failure is a failure to descend, not a failure to let go.**

## What this does not establish

- **The ~9 mm penetration is large** and near-constant across episodes (-0.0089 to -0.0098), which is
  what an unresolved interpenetration looks like as much as a firm perch. These records cannot
  separate "physically resting on the finger" from "wedged in the finger collision geometry", and the
  intervention teleports the object 10 mm, which is exactly the way to create the latter.
- **Right-finger contact is absent in all 8 failures but also in 5 of 7 successes**, so it is not a
  discriminator; only the offset-below-eef and the end height separate the groups.
- **One failure is a different mode** (object at 0.038 m, 80 basket contacts, no finger contact): the
  object was dropped outside the basket. Six of eight are the carried mode above.
- n=15 across five seeds, single task, single magnitude. The mechanism claim is about what the
  contacts show, not a rate.

## Reproduce

    python scripts_setup/gate13_run.py --tasks libero_object:0 --horizons 10 --seeds 1,2,3 \
      --trials 3 --arms disturb --magnitude 0.01 --world-trigger-after-lift 0.02 \
      --world-repeat-every 10 --world-repeat-count 1 --zero-stale --tag g14k9
    python scripts_setup/gate14k_contacts.py results/gate13_g14k9 results/gate13_g14k9b

Contact recording lives in `snapshot_state` (`fastbench_intervention.py`) and only exists in runs made
after 2026-10-19; every earlier result in this repo lacks the `contacts` field.


