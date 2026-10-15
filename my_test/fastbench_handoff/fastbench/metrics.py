from __future__ import annotations

from .core import EpisodeRecord


def first_intervention_step(record: EpisodeRecord) -> int | None:
    if not record.interventions:
        return None
    return min(x.env_step for x in record.interventions)


def first_replan_after_intervention(record: EpisodeRecord) -> int | None:
    t = first_intervention_step(record)
    if t is None:
        return None
    for r in record.replans:
        # Replan at the same step would mean the changed world was observed before
        # generating the new chunk. The interesting stale-action case is later.
        if r.env_step > t:
            return r.env_step
    return None


def stale_action_steps(record: EpisodeRecord) -> int | None:
    """Number of actions executed after the world changed before next policy query.

    This is an environment-grounded metric and applies to WAMs and VLAs alike.
    For WAMs, it becomes particularly meaningful as a proxy for how long a stale
    imagined/action future is trusted.
    """
    t_int = first_intervention_step(record)
    if t_int is None:
        return None
    t_replan = first_replan_after_intervention(record)
    if t_replan is None:
        return sum(1 for s in record.steps if s.env_step >= t_int)
    return sum(1 for s in record.steps if t_int <= s.env_step < t_replan)


def recovery_success(record: EpisodeRecord) -> bool | None:
    """Task succeeds after at least one benchmark intervention."""
    if not record.interventions:
        return None
    return bool(record.success)


def recovery_steps(record: EpisodeRecord) -> int | None:
    """Steps from intervention until task success, if recovery succeeds."""
    t_int = first_intervention_step(record)
    if t_int is None or not record.success:
        return None
    success_steps = [
        s.env_step for s in record.steps
        if s.env_step >= t_int and bool(s.state_after.get("success", False))
    ]
    if not success_steps:
        return None
    return min(success_steps) - t_int + 1


def summarize(record: EpisodeRecord) -> dict:
    return {
        "success": record.success,
        "intervention_step": first_intervention_step(record),
        "first_replan_after_intervention": first_replan_after_intervention(record),
        "stale_action_steps": stale_action_steps(record),
        "recovery_success": recovery_success(record),
        "recovery_steps": recovery_steps(record),
        "num_replans": len(record.replans),
        "num_env_steps": len(record.steps),
    }
