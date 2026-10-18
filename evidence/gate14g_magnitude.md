# Gate 14G — the corrective response plateaus while the damage keeps growing

STATUS: **COMPLETE (2026-10-19).** Single strike, zero stale actions, five magnitudes. Success falls
monotonically to 0/6 while the policy's mean corrective response stops growing after 5 mm.

## Question

Gates 14D/14E/14F left one reading open. A 10 mm strike costs the episode, the policy measurably
reacts (max |delta| 0.0998 at the strike), and yet the outcome is unchanged whether the stale chunk is
replayed or never executed. Two explanations survive that pattern:

1. **Magnitude** — 0.10 normalized units is simply too small a correction for the error it faces.
2. **Ceiling** — the policy's correction is *capped*, and the cap does not scale with the error.

These make different predictions about a magnitude sweep. Under (1) the response should keep growing
with displacement; under (2) it should flatten while success keeps falling.

## Design

`libero_object:0`, H=10, one grasp-relative strike (`--world-trigger-after-lift 0.02`,
`--world-repeat-count 1`), **zero-stale arm** (strike applied before the policy query, observation
refreshed — Gate 14E), seeds 1–2, 3 trials each, **n=6 per magnitude**.

Magnitudes: 2, 5, 10, 20, 40 mm. Control: 6/6 (no strike), same seeds and horizon.

Response metric: for each disturb episode, the change in the planned chunk at the strike step relative
to the control episode of the same seed/trial —
`mean_j |chunk_disturb[j] - chunk_control[j]|` over the first 10 actions, plus the max over them.
Both runs are bit-identical before the strike (verified in Gate 14F), so this is a clean paired
comparison.

Reproduce:

```bash
bash scripts_setup/gate14g_sweep.sh 5 ctl 0.002 0.01
bash scripts_setup/gate14g_sweep.sh 7 0.005 0.02 0.04
python scripts_setup/gate14g_response.py --ctl results/gate13_g14gctl \
    --runs results/gate13_g14gm0002 results/gate13_g14gm0005 \
           results/gate13_g14gm001 results/gate13_g14gm002 results/gate13_g14gm004 \
    --dumpdir /tmp --json results/gate14g_response.json
python scripts_setup/gate14g_figure.py     # -> evidence/gate14g_magnitude.png
```

## Result

| magnitude | success | mean \|delta\| | max \|delta\| |
|---|---|---|---|
| 2 mm | **6/6** | 0.0611 | 0.0989 |
| 5 mm | **5/6** | 0.1031 | 0.1735 |
| 10 mm | **2/6** | 0.1125 | 0.2193 |
| 20 mm | **1/6** | 0.1041 | 0.1410 |
| 40 mm | **0/6** | 0.1109 | 0.1758 |

**Success is perfectly monotone in magnitude**: Spearman rho = -1.000 over the five cells
(n=6 each). 2 mm vs 40 mm: 6/6 vs 0/6, Fisher **p=0.0022**. 5 mm vs 40 mm: 5/6 vs 0/6, **p=0.0152**.
2 mm vs 10 mm: 6/6 vs 2/6, p=0.061 (not significant at n=6 — the curve is resolved by its endpoints,
not by every adjacent pair).

**The response plateaus.** Mean |delta| rises **+68.7%** from 2 mm to 5 mm, then **+9.2%** from 5 to
10 mm, and **-1.5%** from 10 to 40 mm — a further **4x** increase in displacement buys no additional
mean correction. Per-episode dots in the figure show the spread; there is a low outlier at 2 mm
(~0.034) that pulls that cell's mean down, so the 2->5 mm jump is partly between-episode variance
rather than a clean within-episode dose-response.

## Interpretation

**Ceiling, not magnitude.** The policy's corrective authority saturates at roughly 0.10–0.11 mean
|delta| (max ~0.14–0.22) once the object is displaced by 5 mm or more. Success keeps falling to 0/6
across the same range. The failure is therefore not "the model did not notice" (14F) and not "the
model replayed stale actions" (14D/14E): it is that the correction the model produces is bounded and
the residual geometric error is not.

This is a statement about *this* policy on *this* task, not about world models in general: a controller
whose correction is capped will fail once the error exceeds the cap, regardless of how it infers
actions.

## Reconciliation with Gate 13D

Gate 13D reported "no measurable dose-response over 5–20 mm" (all pairwise p >= 0.245). That is not
contradicted here — it is explained. 13D used the **repeated-strike** design (4 strikes), whose cells
were already at or near the floor: 2/6 at 5 mm and 0/3 at 20 mm. A design pinned at the floor cannot
show a gradient. The single-strike design starts at 6/6 and has room to fall, which is why the
dose-response is visible.

The 13D claim should therefore be read as scoped to the repeated-strike design: **repeated strikes
saturate the damage**, and within that saturated regime magnitude is not resolvable at n=6. The
underlying magnitude dependence is real, as this gate shows.

## Does establish

- Success decreases monotonically with displacement magnitude across 2–40 mm in the single-strike
  zero-stale design (6/6 -> 0/6, rho = -1.000, endpoints p=0.0022).
- The mean corrective response grows from 2 mm to 5 mm and then stops growing: a 4x further
  displacement produces no additional mean correction (-1.5%).
- Therefore the failure at >=5 mm is not attributable to absent or stale response; the response is
  present and saturated.

## Does not establish

- **Why** the correction is capped (training distribution, action-space smoothing, or the policy's
  limited authority over the object once grasped). The records carry no contact/grasp state.
- That the cap is a property of world-action models in general — one policy, one task, one horizon.
- A precise dose-response threshold: with n=6 per cell, 2 mm vs 10 mm is p=0.061; the curve is
  established by its endpoints, not by every step.
- That magnitude is the only variable. Displacement **direction** was fixed (away from the goal);
  a sideways strike of the same size may cost differently.
