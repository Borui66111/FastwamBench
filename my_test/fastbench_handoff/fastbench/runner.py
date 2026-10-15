from __future__ import annotations

from .core import (
    EnvAdapter,
    PolicyAdapter,
    Intervention,
    EpisodeRecord,
    StepRecord,
    ReplanRecord,
    InterventionRecord,
)


def run_episode(
    *,
    env: EnvAdapter,
    policy: PolicyAdapter,
    instruction: str,
    replan_steps: int,
    max_env_steps: int,
    intervention: Intervention | None = None,
) -> EpisodeRecord:
    """Run one chunked-control episode with an optional controlled intervention.

    Semantics intentionally mirror FastWAM LIBERO evaluation:
    - query policy only when no pending actions remain;
    - execute at most `replan_steps` actions from the predicted action chunk;
    - then observe and query again.

    The intervention is checked immediately before each environment action. This
    creates the important benchmark condition where the physical world can change
    *after* a chunk was planned but *before* all actions in that chunk are executed.
    """
    if replan_steps <= 0:
        raise ValueError("replan_steps must be positive")
    if max_env_steps <= 0:
        raise ValueError("max_env_steps must be positive")

    obs = env.reset()
    policy.reset()
    pending_actions: list = []
    steps: list[StepRecord] = []
    replans: list[ReplanRecord] = []
    interventions: list[InterventionRecord] = []
    replan_id = -1
    chunk_index = 0
    already_intervened = False

    for env_step in range(max_env_steps):
        if not pending_actions:
            out = policy.act(obs, instruction)
            if len(out.action_chunk) == 0:
                raise RuntimeError("policy returned an empty action chunk")
            replan_id += 1
            replans.append(
                ReplanRecord(
                    replan_id=replan_id,
                    env_step=env_step,
                    observation=dict(obs),
                    predicted_future=out.predicted_future,
                    metadata=dict(out.metadata),
                )
            )
            pending_actions = list(out.action_chunk[:replan_steps])
            chunk_index = 0

        intervention_applied = False
        state_before_intervention = env.snapshot()
        if (
            intervention is not None
            and not already_intervened
            and intervention.should_trigger(env_step=env_step, state=state_before_intervention)
        ):
            details = intervention.apply(env)
            interventions.append(
                InterventionRecord(
                    name=intervention.name,
                    env_step=env_step,
                    details=details,
                )
            )
            already_intervened = True
            intervention_applied = True

        observation_before = dict(obs)
        state_before = env.snapshot()
        action = pending_actions.pop(0)
        next_obs, _, done, _ = env.step(action)
        state_after = env.snapshot()

        steps.append(
            StepRecord(
                env_step=env_step,
                replan_id=replan_id,
                chunk_index=chunk_index,
                observation_before=observation_before,
                state_before=state_before,
                action=action,
                state_after=state_after,
                done=bool(done),
                intervention_applied=intervention_applied,
            )
        )
        chunk_index += 1
        obs = next_obs
        if done:
            break

    final_state = env.snapshot()
    success = bool(final_state.get("success", False))
    return EpisodeRecord(
        instruction=instruction,
        success=success,
        final_state=final_state,
        steps=steps,
        replans=replans,
        interventions=interventions,
    )
