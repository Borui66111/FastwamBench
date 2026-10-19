# Gate 14G — the corrective response grows sublinearly while success collapses

STATUS: **COMPLETE (2026-10-19), n=9 per magnitude.** Supersedes the n=6 pilot of the same design,
which read the response as a plateau after 5 mm; the wider replication does not support that reading.
The pilot's numbers are kept below so the change is auditable.

## Question

Gate 14D/14E/14F showed the success cost is not carried by stale execution, and 14F showed the model
does respond to the strike (plan changes by up to 0.0998 at the strike step). So the cost has to be in
*how much* it responds. This gate measures the size of the response as a function of the size of the
displacement.

## Setup

`libero_object:0`, H=10, **one** grasp-relative strike at the detected lift (+0.02 m), **zero stale
actions** (strike applied before the policy query, observation refreshed), **n=9 per magnitude**
(seeds 1,2,3 × 3 trials), 5 magnitudes plus a no-strike control.

The response is the change in the planned action chunk at the strike step, comparing the zero-stale
run (planned from the post-strike observation) with the control run at the same seed, trial, and
replan step. Both arms dump every chunk.

**Reproducibility check.** All 36 seed-1,2 episodes reproduce the n=6 pilot **exactly** — same success
flag, same step count — so the harness is deterministic and the n=9 data is the n=6 data plus seed 3.

## Result

```
 magnitude    succ  zero-stale  paired   mean|d|      95% CI (bootstrap)   max|d|
     2.0mm   9/9             9       9   0.0556   [0.0405, 0.0715]        0.0989
     5.0mm   8/9             9       9   0.0901   [0.0707, 0.1148]        0.1735
    10.0mm   4/9             9       9   0.1026   [0.0849, 0.1331]        0.2193
    20.0mm   1/9             9       9   0.0998   [0.0863, 0.1147]        0.1410
    40.0mm   1/9             9       9   0.1160   [0.0904, 0.1422]        0.1758
```

control: 9/9.

**Success collapses.** 9/9 → 8/9 → 4/9 → 1/9 → 1/9. Spearman **rho=−0.975, p=0.0048**; 2 vs 40 mm
Fisher **p=4.1e-4**; 2 vs 10 mm **p=0.029**. Note 40 mm is **1/9, not 0/9** — the largest displacement
is not impossible, it is close to it.

**The response grows sublinearly.** A 20× increase in displacement (2→40 mm) buys a **2.09×** increase
in the mean response, i.e. the response scales as roughly **m^0.22**. From 5 mm to 40 mm — 8× the
displacement — the response grows only **1.29×**.

**So the two curves are qualitatively different.** Success is a near-step function of magnitude; the
corrective response is a shallow power law. Between 10 and 40 mm the displacement quadruples, the
response grows 13%, and success falls from 4/9 to 1/9.

## Correction to the n=6 pilot

The n=6 run gave 6/6, 5/6, 2/6, 1/6, 0/6 with means 0.0611, 0.1031, 0.1125, 0.1041, 0.1109, which I
read as "+69% from 2→5 mm, then flat to 40 mm" and titled a figure "the MEAN corrective response
plateaus after 5 mm". At n=9 the 20 mm dip is within noise and the 40 mm mean is 13% above the 10 mm
mean, so **"plateau" is not supportable**. The honest statement is a power law with exponent ≈0.22,
and the figures now say that. The n=6 JSON is kept as `results/gate14g_response_n6.json`; the
authoritative file is `results/gate14g_response.json`.

The two readings agree on the substantive point — the response grows far more slowly than the damage
— but "flat" and "sublinear" are different claims and only the second survives more data.

## Why this is not a measurement artefact

- **Pre-strike internal validity.** In the paired chunk dumps the pre-strike plans are bit-identical
  across arms (Gate 14F: max|d| = 0.00000 for 7 consecutive replans), so the difference at the strike
  is the response and nothing else.
- **The comparison is within-episode.** Each disturbed episode is paired with the control episode of
  the same seed and trial, not with a pooled control mean.
- **Per-episode spread is shown, not hidden.** The 95% intervals above are bootstrap over episodes;
  they overlap from 5 mm upward, which is exactly why "flat" was tempting and why the power-law fit
  is the better summary.

## What this establishes

> The policy's corrective response to a mid-carry displacement grows roughly as the 0.22 power of the
> displacement, while task success collapses over the same range. The response is real (it is not a
> failure to notice the strike) but far too shallow to absorb the disturbance.

## What it does not establish

- **Why** the response is so shallow. Gate 14H localises the consequence to the final descent/release
  (the object reaches the basket in xy and stalls above it), but the shallowness itself is not
  explained by these records.
- Any WAM-vs-baseline claim: this is the `idm` pathway only.
- The exact functional form. Five magnitudes with n=9 support "sublinear, exponent ≈0.2–0.3"; they do
  not distinguish a power law from a saturating exponential.
- Generality beyond `libero_object:0`.

## Reproduce

```bash
# n=9 replication (seeds 1,2,3), tag prefix keeps the n=6 runs intact
SEEDS=1,2,3 TRIALS=3 TAGPFX=g14s9 bash scripts_setup/gate14g_sweep.sh 5 ctl 0.002 0.01
SEEDS=1,2,3 TRIALS=3 TAGPFX=g14s9 bash scripts_setup/gate14g_sweep.sh 7 0.005 0.02 0.04

python scripts_setup/gate14g_response.py \
    --ctl results/gate13_g14s9ctl \
    --runs results/gate13_g14s9m0002 results/gate13_g14s9m0005 \
           results/gate13_g14s9m001 results/gate13_g14s9m002 results/gate13_g14s9m004 \
    --dumpdir /tmp --json results/gate14g_response.json

python scripts_setup/gate14g_figure.py    # -> evidence/gate14g_magnitude.{png,pdf}
```
