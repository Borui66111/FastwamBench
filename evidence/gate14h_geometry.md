# Gate 14H — the failure is in the placement, not the approach

STATUS: **COMPLETE (2026-10-19), n=9 per magnitude.** Measured from the records the Gate 14G sweep
already wrote — every step record carries `state.bodies[...]["pos"]` and `state.eef["pos"]`, so this
gate needed no GPU time.

Gate 14G found that the policy's corrective response grows only as ~m^0.22 while success collapses to
1/9. That left two readings: the shallow response is harmless (the failure is elsewhere), or it is the
cause. This gate measures where the object actually ends up.

## Setup

Same runs as Gate 14G: `libero_object:0`, H=10, **one** grasp-relative strike at the detected lift
(+0.02 m), **zero stale actions**, n=9 per magnitude (seeds 1,2,3 × 3 trials). Control is the
no-strike arm of the same sweep.

Per episode, from the recorded trajectories: the object's xy distance to the basket, its height, the
minimum xy distance reached, and the trend of height over the last 40 steps.

## Result

```
mag_mm   succ   z_end|succ   z_end|fail   d_end|succ   d_end|fail
     2    9/9       0.1142          n/a       0.0154          n/a
     5    8/9       0.1244       0.0340       0.0205       0.4058
    10    4/9       0.1276       0.1799       0.0165       0.0088
    20    1/9       0.1136       0.2023       0.0266       0.0130
    40    1/9       0.1165       0.2028       0.0077       0.0639
```

control: 9/9, z_end 0.1145, d_end 0.0161.

Three things fall out.

**1. Successful episodes end at a fixed height, whatever the strike.** 0.1142, 0.1244, 0.1276, 0.1136,
0.1165 m — a 14 mm spread across a 20× change in magnitude, centred on the control's 0.1145. A
successful place has one signature and the strike does not shift it, including the single success at
40 mm (0.1165, inside the control band). So a strike does not degrade the quality of a success; it
converts episodes into a different terminal state.

**2. Failures are left above the basket, and how high scales with the strike.** 0.1799 → 0.2023 →
0.2028 m at 10 / 20 / 40 mm, against a control placement band of 0.096–0.136 m: 4–11 cm too high.
Among failures only, z_end vs magnitude gives Spearman **rho=+0.606, p=0.0028** (n=22); pooling
successes and failures gives **rho=+0.651, p=1.3e-6** (n=45). Success vs failure heights:
**0.1202 vs 0.1898, Mann-Whitney p=1.4e-6**.

**3. The horizontal part works.** The object's minimum xy distance to the basket is below 0.03 m in
every cell, including 10 and 20 mm where success is 4/9 and 1/9 — those failures end **8.8 and 13.0 mm
from the basket centre**, i.e. inside the footprint. This is the signature Gate 13D found in the
repeated-strike design (held above the basket at z 0.177–0.220), now with a dose-response attached.

So the shallow corrective response is **sufficient for transport and insufficient for placement**. It
is not harmless: it is specifically a failure to complete the vertical descent and release.

## Not a timeout artefact

Every failure runs to the 430-step cap, so the obvious objection is "more time would fix it". It
would not: fitting height over the last 40 steps gives slopes from **−0.99 to +1.25 mm/step, median
+0.12**, and **14 of 22 failures are still moving UP** at the end. These episodes are not slowly
descending into the basket; many are being lifted away from it. This agrees with the 800-step
replication in Gate 14 §3b, which rescued exactly one episode per pathway and left the rest
non-terminating.

## Two failure modes, as in 13D

- **Held high** — 20 of 22 failures: at the basket footprint in xy (minimum distance 0.0002–0.016 m),
  stalled 0.16–0.25 m up.
- **Lost far** — 2 of 22: 5 mm seed 1 episode 0 ends at xy 0.385 m / z 0.034; 40 mm seed 1 episode 1
  ends at xy 0.292 m / z 0.038. The object is dropped away from the basket and near the table.

The "lost far" mode is rare and does not scale with magnitude — it appears at both the smallest and
largest strike. It is a distinct mechanism from the height gradient, and it is why the 5 mm and 40 mm
failure-cell means are not pure samples of the held-high mode.

## What this establishes

> A mid-carry strike leaves the object at the basket in xy but too high to be placed. The height at
> which the episode stalls grows with the strike magnitude (rho=+0.61 among failures), while
> successful episodes always settle at the same height (~0.115–0.128 m). The failure is in the final
> descent/release, and it is not a matter of needing more steps: at timeout most failures are still
> rising.

## What it does not establish

- **Why** the descent does not complete. The records carry no gripper command, contact state or grasp
  flag, so "it stops descending" is measured and "because the release logic fails" is not.
- That this generalises past `libero_object:0`. `libero_spatial` has a ~20–30 step carry and could
  not be tested in the carry regime (Gate 13C).
- Any WAM-vs-baseline claim. This is a single-pathway (`idm`) geometry study.
- The shape of the gradient: n=9 per magnitude, and two off-mode episodes mean the 5 and 40 mm
  failure-cell means mix two mechanisms.

## Reproduce

```bash
# geometry table + statistics from the existing sweep records (no GPU)
python scripts_setup/gate14h_geometry.py \
    --runs results/gate13_g14s9ctl results/gate13_g14s9m0002 results/gate13_g14s9m0005 \
           results/gate13_g14s9m001 results/gate13_g14s9m002 results/gate13_g14s9m004 \
    --json results/gate14h_geometry_n9.json

python scripts_setup/gate14h_figure.py \
    --json results/gate14h_geometry_n9.json --out evidence/gate14h_geometry.png
```

The n=6 pilot table is kept as `results/gate14h_geometry_n6.json`.

Figure caveat: panel B's y axis is logarithmic because two "lost far" episodes sit at 0.29 and 0.41 m;
on a linear axis pinned to the basket footprint they would fall outside the plot and the second
failure mode would be invisible.
