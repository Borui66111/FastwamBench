# Requirements

## Research goal
Evaluate the additional world-modeling commitment of World Action Models through controlled interventions, rather than only task success.

Initial benchmark questions:

- H1 Action-conditioned consequence: does changing an action / dynamics appropriately change the represented future?
- H2 Future-action consistency: does the action actually realize the model's anticipated safe/goal-directed future?
- H3 Future-reality consistency and recovery: when reality invalidates a previous plan, how long is stale action executed and does the policy recover?

## MVP software requirement
Implement one instrumented rollout that can:

- query a chunked policy;
- execute a configurable prefix (`replan_steps`);
- apply one deterministic mid-rollout intervention;
- record state/action/replan/intervention evidence;
- compute recovery and stale-action metrics;
- later swap toy environment/policy for LIBERO-Safety/FastWAM adapters without changing benchmark logic.

## Constraints
- Do not assume WAM is better than VLA.
- VLA baselines must be runnable through the same behavioral interface.
- Future-specific metrics are optional when a model does not expose a future representation.
- Cross-model primary metrics should be environment-grounded, not raw latent similarity.
