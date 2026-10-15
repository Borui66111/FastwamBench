from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence


class EnvAdapter(Protocol):
    """Minimal environment contract needed by FastBench."""

    def reset(self) -> dict[str, Any]: ...
    def step(self, action: Any) -> tuple[dict[str, Any], float, bool, dict[str, Any]]: ...
    def snapshot(self) -> dict[str, Any]: ...


class PolicyAdapter(Protocol):
    """Common behavioral interface for WAM or VLA policies."""

    def reset(self) -> None: ...
    def act(self, observation: dict[str, Any], instruction: str) -> "PolicyOutput": ...


class Intervention(Protocol):
    """Controlled benchmark manipulation of the physical world."""

    name: str

    def should_trigger(self, *, env_step: int, state: dict[str, Any]) -> bool: ...
    def apply(self, env: EnvAdapter) -> dict[str, Any]: ...


@dataclass
class PolicyOutput:
    action_chunk: Sequence[Any]
    # Optional WAM-specific outputs. VLAs may leave these None.
    predicted_future: Any | None = None
    future_representation: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepRecord:
    env_step: int
    replan_id: int
    chunk_index: int
    observation_before: dict[str, Any]
    state_before: dict[str, Any]
    action: Any
    state_after: dict[str, Any]
    done: bool
    intervention_applied: bool = False


@dataclass
class ReplanRecord:
    replan_id: int
    env_step: int
    observation: dict[str, Any]
    predicted_future: Any | None
    metadata: dict[str, Any]


@dataclass
class InterventionRecord:
    name: str
    env_step: int
    details: dict[str, Any]


@dataclass
class EpisodeRecord:
    instruction: str
    success: bool
    final_state: dict[str, Any]
    steps: list[StepRecord]
    replans: list[ReplanRecord]
    interventions: list[InterventionRecord]
