# Gate 14 at a glance

Every count below is recomputed from `results/*/records.jsonl` and every test is run by
`scripts_setup/gate14_summary.py`, so no number here is transcribed by hand. Regenerate with:

```
python scripts_setup/gate14_summary.py --write
```

The headline: a mid-carry displacement costs success, and the cost survives every
manipulation that removes the two obvious explanations (future-aware inference, stale
execution). What is left is a shallow corrective response that releases the object too
high. See `evidence/gate14_wam_specificity.md`, `gate14e_zero_stale.md`,
`gate14g_magnitude.md`, `gate14h_geometry.md`, `gate14i_release.md`, `gate14j_fingers.md`.

| gate | manipulation | result | test | source |
|---|---|---|---|---|
| 14 carry | idm vs first_frame, H=1, 0.01 m, 4 strikes | idm 2/6 vs first_frame 2/6 | p=1.0000 | `results/gate13_g14ff` |
| 14 carry | idm vs first_frame, H=10, 0.01 m, 4 strikes | idm 1/6 vs first_frame 1/6 | p=1.0000 | `results/gate13_g14ff` |
| 14 carry ctrl | same, control arm (comparability check) | idm 6/6 vs first_frame 5/6 | p=1.0000 | `results/gate13_g14ff` |
| 14 budget | same at 800 steps, pooled over H | idm 4/12 vs first_frame 4/12 | p=1.0000 | `results/gate13_g14ff800` |
| 14 approach | strike at step 40, first_frame: control vs disturb | control 11/12 vs disturb 5/12 | p=0.0272 | `results/gate13_g14ffapproach` |
| 14 approach@800 | same, 800-step budget | control 12/12 vs disturb 5/12 | p=0.0046 | `results/gate13_g14ffapproach800` |
| 14D | one strike, H=10: full chunk vs 9 of 10 dropped | keep 2/6 vs drop 2/6 | p=1.0000 | `results/gate13_g14drop1` |
| 14E | one strike, H=10: full chunk vs zero stale (re-query) | keep 2/6 vs zero 2/6 | p=1.0000 | `results/gate13_g14zero1` |
| 14G | single strike, zero stale, 2/5/10/20/40 mm, n=9 each | success 9/9 8/9 4/9 1/9 1/9 | Spearman rho=-0.975, p=0.0048 | `results/gate14g_response.json` |
| 14H | object height at episode end, success vs failure | 0.118 m vs 0.190 m | Mann-Whitney p=1.4e-6 | `results/gate14h_geometry_n9.json` |
| 14-I | gripper commanded open after the strike, success vs failure | 0.114 vs 0.719 | descriptive | `results/gate14i_release.json` |

Note: gates 14D/14E use n=6 (one strike, single cell). Gate 14G/14H/14-I use n=9 per
magnitude. Per-cell tests on n=6 are underpowered; the pooled tests carry the claims.
