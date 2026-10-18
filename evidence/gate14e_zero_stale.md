# Gate 14E — stale actions are not what costs the episode

STATUS: **COMPLETE (2026-10-19), NEGATIVE for the stale-execution account.** Removing stale
execution entirely does not recover the episode: 10, 1 and 0 stale actions all give **2/6**, and the
three arms agree **episode for episode**, down to the step count.

## The question 14D left open

Gate 14D dropped the remainder of the chunk after a strike and found no change (2/6 either way,
identical per-episode step counts). That arm still executed **one** action planned before the world
moved. So it could not separate:

- **H1** — the displacement itself damages the episode, and re-planning does not help; or
- **H2** — the damage is carried by the one committed action in flight.

14E discriminates them. The strike is applied **before** the policy query and the observation is
re-read, so the chunk is planned against the mutated world and **zero** stale actions execute.

## The manipulation, and how it is audited

1. `maybe_displace_world` is called before `_predict_action_chunk`, at the same env step (t=100), so
   the query happens after the mutation. The trigger is step-based, so moving the call does not
   change *when* it fires.
2. The observation is re-read with `_get_observations(force_update=True)` — robosuite documents
   `force_update` for exactly this case ("grab observations when directly setting simulation states
   without actually stepping").

Two guards keep the label honest, because "zero stale actions" is worthless if the model is
secretly planning on pre-strike pixels:

- The harness **refuses to record a strike it cannot refresh** — it raises rather than mislabelling.
  This fired on the first canary attempts: `OffScreenRenderEnv` does not re-export
  `_get_observations`; the robosuite env that owns it is `env.env`.
- The refresh is **measured**, not assumed. The intervention record carries
  `obs_pixel_maxdiff` and `obs_pixel_changed_frac` computed against the pre-strike frame:
  **maxdiff 116, 5.28% of pixels changed** at the strike. The model really did see the object move.

Provenance: `zero_stale_strikes` in `episode_end`; `zero_stale`, `obs_refreshed`,
`obs_pixel_maxdiff`, `obs_pixel_changed_frac` in the intervention record. A cell is interpretable
only if `zero_stale_strikes > 0`, `stale_action_steps == 0` and `obs_pixel_changed_frac > 0`.

## Result

`libero_object:0`, H=10, 0.01 m, one strike at t=100, seeds 1–2 × 3 trials, n=6 per arm. All three
arms share the same task, seed, horizon, magnitude, trigger and strike step; only what happens to
the chunk differs.

| arm | stale actions executed | success | mean steps | timeouts |
|---|---|---|---|---|
| full chunk (keep) | 10 | 2/6 | 348.5 | 4 |
| one action, then drop | 1 | 2/6 | 349.0 | 4 |
| **zero stale** | **0** | **2/6** | **348.5** | **4** |

Per episode (`Y` success, `n` failure, parenthesised step count, `s` = stale actions):

```
keep  s1/e0:Y(202,s10) s1/e1:Y(169,s10) s1/e2:n(430,s10) s2/e0:n(430,s10) s2/e1:n(430,s10) s2/e2:n(430,s10)
drop  s1/e0:Y(203,s1)  s1/e1:Y(171,s1)  s1/e2:n(430,s1)  s2/e0:n(430,s1)  s2/e1:n(430,s1)  s2/e2:n(430,s1)
zero  s1/e0:Y(202,s0)  s1/e1:Y(169,s0)  s1/e2:n(430,s0)  s2/e0:n(430,s0)  s2/e1:n(430,s0)  s2/e2:n(430,s0)
```

Every episode lands the same way in all three arms. The step counts differ by at most 2, and the
one-step gap in `drop` is the extra action executed before the discard.

## What this establishes

**H1, not H2.** The number of already-planned actions executed after the world moves has no
detectable effect on the outcome — across a 10× change (10 → 1 → 0), with the observation refresh
verified to have changed the pixels. The failure is not produced by executing actions planned
against a stale world.

That retires the framing this repo was built around. "The cost of world-model commitment", read as
*the cost of replaying a chunk whose premise has expired*, does not describe what the data shows:
the episode fails whether the chunk is replayed, truncated, or never replayed at all.

## Gate 14F — the policy does respond; the response is small

Identical per-episode outcomes across the three arms admit two explanations: the policy does not
react to the displacement at all, or it reacts too little to matter. Those are different claims about
the model and only the first would be alarming, so I measured it instead of inferring it from step
counts.

Method: dump every action chunk (`FASTBENCH_DUMP_CHUNK=<path>`, one JSON line per replan) from two
one-episode runs at the same seed and trial — the keep arm, whose chunk at t=100 is planned from the
**pre**-strike observation, and the zero-stale arm, whose chunk at t=100 is planned from the
**refreshed post**-strike observation. Same task, seed, horizon, magnitude and strike step.

| replan step | max abs chunk difference | reading |
|---|---|---|
| t=30 … t=90 (8 chunks) | **0.00000** | bit-identical — the two runs are the same trajectory before the strike |
| **t=100 (the strike)** | **0.09979** | the plan changes when the model sees the object move |
| t=110 … t=200 (10 chunks) | 0.009 – 0.058 | the difference persists and decays |

Two things follow.

1. **Internal validity.** The eight pre-strike chunks agree to the last bit, so the comparison at
   t=100 is not contaminated by run-to-run variation. This is the same role lag-0 Δ=0 plays in the
   PSNR analysis.
2. **The model is not blind to the strike.** Its plan shifts by up to ≈0.10 in normalized action
   units at the strike replan (mean |Δ| ≈ 0.021). So the failure is not "the model ignores the
   displacement" — it is that a response of this size does not change the episode outcome. Both the
   identical success counts and the identical step counts survive a plan that is measurably, but
   slightly, different.

What this rules out: "the policy produces an unchanged trajectory". What it does not rule out: that
the response is simply too small relative to the placement precision the task requires, or that the
dominant failure is geometric (the object ends up ~1 cm off and the success check is exact) rather
than a control failure.

## What it does not establish

- **Not** that the policy is unaffected by the strike. It is not: the object moves, and the episode
  fails 4/6 times. The displacement is doing the damage; stale execution is not the channel.
- **Not** that the policy ignores the displacement. It does not — and this is now measured rather than
  inferred. Dumping the chunks from the keep arm (planned pre-strike) and the zero-stale arm (planned
  post-strike) at the same seed shows the eight pre-strike chunks are **bit-identical** and the chunk
  at the strike differs by up to **0.0998** (mean |Δ| 0.021). The model sees the move and responds;
  the response is simply not big enough to change the outcome. What remains open is whether that is a
  magnitude problem or a geometric one — the object ends up ~1 cm off and the success check is exact.
- **Not** a claim about the horizon gradient. Gate 13C/13D measured that four strikes cost more than
  one, and H=10 more than H=1. With stale-action count now inert, that gradient has **no mechanistic
  account** and must not be restated as "commitment compounds with horizon".

## Reproduce

```bash
# the arm in this document
python scripts_setup/gate13_run.py --tasks libero_object:0 --horizons 10 --seeds 1,2 --trials 3 \
    --arms disturb --magnitude 0.01 --world-trigger-after-lift 0.02 \
    --world-repeat-every 10 --world-repeat-count 1 --zero-stale --tag g14zero1 --ngpu 2

# the two reference arms, identical schedule
python scripts_setup/gate13_run.py ... --world-repeat-count 1 --tag g14keep1 --ngpu 1
python scripts_setup/gate13_run.py ... --world-repeat-count 1 --drop-stale-after-strike --tag g14drop1 --ngpu 1
```

Data: `results/gate13_g14keep1`, `results/gate13_g14drop1`, `results/gate13_g14zero1`,
`results/gate13_g14ediff` (the pixel-diff canary).
