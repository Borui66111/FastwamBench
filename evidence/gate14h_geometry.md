# Gate 14H — the failure is in the placement, not the approach

STATUS: **COMPLETE (2026-10-19).** No new GPU runs: measured from the records the Gate 14G sweep
already wrote, since every step record carries `state.bodies[...]["pos"]` and `state.eef["pos"]`.

Gate 14G found that the policy's corrective response plateaus at ~0.11 normalized units while success
keeps falling to 0/6. That left two readings: the cap is harmless (the response is enough and the
failure is elsewhere), or the cap is the cause. This gate measures where the object actually ends up.

## Setup

Same runs as Gate 14G: `libero_object:0`, H=10, **one** grasp-relative strike at the detected lift
(+0.02 m), **zero stale actions** (strike applied before the query, observation refreshed), n=6 per
magnitude, seeds 1–2, trials 3. Control is the no-strike arm of the same sweep.

Measured per episode from the recorded trajectories: the object's xy distance to the basket, its
height, and the trend of height over the last 40 steps.

## Result

```
mag_mm   succ   z_end|succ   z_end|fail   d_end|succ   d_end|fail
     2    6/6       0.1171          n/a       0.0135          n/a
     5    5/6       0.1193       0.0340       0.0210       0.4058
    10    2/6       0.1206       0.1735       0.0236       0.0085
    20    1/6       0.1136       0.1960       0.0266       0.0134
    40    0/6          n/a       0.2019          n/a       0.0703
```

control: 6/6, z_end 0.1145, d_end 0.0161.

Three things fall out.

**1. Successful episodes end at a fixed height, whatever the strike.** 0.1171, 0.1193, 0.1206, 0.1136
— a 7 mm spread across a 20× change in magnitude, and indistinguishable from the control's 0.1145.
A successful place has one signature, and the strike does not shift it. So a strike does not degrade
the quality of a success; it converts episodes into a different terminal state.

**2. Failures are left above the basket, and how high scales with the strike.** 0.1735 → 0.1960 →
0.2019 m at 10 / 20 / 40 mm, against a control placement band of 0.096–0.136 m. That is 4–11 cm too
high. Among failures only, z_end vs magnitude gives Spearman **rho=+0.728, p=1.4e-3** (n=16); pooling
successes and failures gives **rho=+0.678, p=3.8e-5** (n=30). Success vs failure heights:
**0.1181 vs 0.1825, Mann-Whitney p=2.6e-4**.

**3. The horizontal part works.** The object's minimum xy distance to the basket is below 0.03 m in
every cell, including 10 and 20 mm where success is 2/6 and 1/6 — those failures are *at the basket
footprint*, 8.5 and 13.4 mm from the centre. This is the same signature Gate 13D found in the
repeated-strike design (held above the basket at z 0.177–0.220), now with a dose-response attached.

So the capped corrective response is **sufficient for transport and insufficient for placement**. The
cap is not harmless; it is specifically a failure to complete the vertical descent and release.

## Not a timeout artefact

Every failure runs to the 430-step cap, so the obvious objection is "more time would fix it". It
would not: fitting height over the last 40 steps gives slopes from **−0.58 to +1.25 mm/step, median
+0.12**, and **11 of 16 failures are still moving UP** at the end. These episodes are not slowly
descending into the basket; several are being lifted away from it. This agrees with the 800-step
replication in Gate 14 §3b, which rescued exactly one episode per pathway and left the rest
non-terminating.

## Two failure modes, as in 13D

- **Held high** — 14 of 16 failures: at the basket footprint in xy, stalled 0.16–0.25 m up.
- **Lost far** — 2 of 16: at 5 mm one episode ends at xy 0.385 m / z 0.034, at 40 mm one at 0.292 m /
  z 0.038. The object is dropped on the table away from the basket (both had reached z_max 0.216 and
  0.274, so they were lifted and then lost).

The "lost far" mode is rare and does not scale with magnitude — it appears at both the smallest and
largest strike. It is a distinct mechanism from the height gradient.

## What this establishes

> A mid-carry strike leaves the object at the basket in xy but too high to be placed. The height at
> which the episode stalls grows monotonically with the strike magnitude (rho=+0.73 among failures),
> while successful episodes always settle at the same height (~0.118 m). The failure is in the final
> descent/release, and it is not a matter of needing more steps: at timeout most failures are still
> rising.

## What it does not establish

- **Why** the descent does not complete. The records carry no gripper command, contact state or
  grasp flag, so "it stops descending" is measured and "because the grasp or the release logic
  fails" is not. Gate 13D's evidence on `action[6]` (gripper command not a discriminator) was for the
  repeated-strike design.
- That this generalises past `libero_object:0`. `libero_spatial` has a ~20–30 step carry and could
  not be tested in the carry regime (Gate 13C).
- Any WAM-vs-baseline claim. This is a single-pathway (`idm`) geometry study.
- Statistical power for the *shape* of the gradient: n=6 per magnitude, and the two "lost far"
  episodes mean the cell means at 5 and 40 mm are not pure samples of the held-high mode.

## Reproduce

```bash
# geometry table + statistics from the existing sweep records (no GPU)
python scripts_setup/gate14h_geometry.py \
    --runs results/gate13_g14gctl results/gate13_g14gm0002 results/gate13_g14gm0005 \
           results/gate13_g14gm001 results/gate13_g14gm002 results/gate13_g14gm004 \
    --json results/gate14h_geometry.json

python scripts_setup/gate14h_figure.py    # -> evidence/gate14h_geometry.{png,pdf}
```

Data: the five magnitude runs plus control from Gate 14G. Figure: `evidence/gate14h_geometry.png`.

Figure caveat: panel B's y axis is logarithmic because two "lost far" episodes sit at 0.29 and 0.38 m;
on a linear axis pinned to the basket footprint they would fall outside the plot and the second
failure mode would be invisible.
