# Gate 14 at a glance

Every count below is recomputed from `results/*/records.jsonl` and every test is run by
`scripts_setup/gate14_summary.py`, so no number here is transcribed by hand. Regenerate with:

```
python scripts_setup/gate14_summary.py --write
```

The headline: a mid-carry displacement costs success, and the cost survives every
manipulation that removes the two obvious explanations (future-aware inference, stale
execution). What is left is a shallow corrective response that commands the release and
then stops descending, leaving the object carried. Gate 14L then asks whether the
future-aware advantage scales with commitment in the approach regime, and finds it does
not. See
`evidence/gate14_wam_specificity.md`, `gate14e_zero_stale.md`,
`gate14g_magnitude.md`, `gate14h_geometry.md`, `gate14i_release.md`, `gate14j_fingers.md`,
`gate14k_contacts.md`, `gate14L_horizon.md`.

| gate | manipulation | result | test | source |
|---|---|---|---|---|
| 14 carry | idm vs first_frame, H=1, 0.01 m, 4 strikes | idm 2/6 vs first_frame 2/6 | p=1.0000 | `results/gate13_g14ff` |
| 14 carry | idm vs first_frame, H=10, 0.01 m, 4 strikes | idm 1/6 vs first_frame 1/6 | p=1.0000 | `results/gate13_g14ff` |
| 14 carry ctrl | control arm, H=1 (comparability check) | idm 6/6 vs first_frame 5/6 | p=1.0000 | `results/gate13_g14ff` |
| 14 budget | same at 800 steps, pooled over H | idm 4/12 vs first_frame 4/12 | p=1.0000 | `results/gate13_g14ff800` |
| 14 approach | strike at step 40, first_frame: control vs disturb | control 11/12 vs disturb 5/12 | p=0.0272 | `results/gate13_g14ffapproach` |
| 14 approach@800 | same, 800-step budget | control 12/12 vs disturb 5/12 | p=0.0046 | `results/gate13_g14ffapproach800` |
| 14D | one strike, H=10: full chunk vs 9 of 10 dropped | keep 2/6 vs drop 2/6 | p=1.0000 | `results/gate13_g14drop1` |
| 14E | one strike, H=10: full chunk vs zero stale (re-query) | keep 2/6 vs zero 2/6 | p=1.0000 | `results/gate13_g14zero1` |
| 14G | single strike, zero stale, 2/5/10/20/40 mm, n=9 each | success 9/9 8/9 4/9 1/9 1/9 | Spearman rho=-0.975, p=0.0048 | `results/gate14g_response.json` |
| 14H | object height at episode end, success vs failure | 0.118 m vs 0.190 m | Mann-Whitney p=1.4e-6 | `results/gate14h_geometry_n9.json` |
| 14-I | gripper commanded open after the strike, success vs failure | 0.114 vs 0.719 | descriptive | `results/gate14i_release.json` |

## State measurements (14J, 14K)

These answer 'what did the actuator and the contacts do', so there is no success-rate
comparison to test. Numbers below are recomputed from the records.

- **14J** (n=9: 4 success / 5 failure): finger width at the last step is
  **0.0773-0.0795 m** in failures against a 0.080 m ceiling, so the release command
  reaches the actuator. Width is not the discriminator - both groups reach the
  ceiling at some point, because the gripper opens to approach. See
  `evidence/gate14j_fingers.md`.
- **14K** (n=15: 7 success / 8 failure): in **7 of 8** failures the object records **zero basket contacts** in the last 40
  steps, and **7 of 8** show left-finger contact only with the right
  finger never touching it. The object is carried, not placed. See
  `evidence/gate14k_contacts.md`.

## Gate 14L — horizon scaling (approach regime, n=18 per cell)

Strike at env step 40 (pre-grasp), 800-step budget, no `--zero-stale`.
H controls only `pending_actions = action_chunk[:H]`; conditioning is fixed.

| H | idm disturb | ff disturb | gap (idm-ff) | Fisher p |
|---|---|---|---|---|
| 1 | 12/18 | 5/18 | +0.39 | 0.0437 |
| 2 | 12/18 | 11/18 | +0.06 | 1.0000 |
| 5 | 17/18 | 12/18 | +0.28 | 0.0877 |
| 10 | 15/18 | 17/18 | -0.11 | 0.6026 |

Pooled over horizons: idm 56/72 vs first_frame 45/72, Fisher p=0.0680.

The gap has no monotone ordering (+0.39, +0.06, +0.28, -0.11) and the pooled test is
not significant, so the pre-registered prediction that commitment would amplify the
future-aware advantage is **refuted**. See `evidence/gate14L_horizon.md`.

Note: gates 14D/14E use n=6 (one strike, single cell). Gate 14G/14H/14-I use n=9 per
magnitude. Per-cell tests on n=6 are underpowered; the pooled tests carry the claims.
