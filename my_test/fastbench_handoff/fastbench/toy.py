from __future__ import annotations

from dataclasses import dataclass

from .core import PolicyOutput


class OneDTargetEnv:
    """Tiny deterministic environment for E2E benchmark contract tests.

    State:
      agent_position x
      target_position target

    Action:
      scalar delta added to x, clipped to [-1, 1].

    This is NOT a robotics benchmark. It only verifies FastBench runner semantics.
    """

    def __init__(self, *, start: float = 0.0, target: float = 5.0, tolerance: float = 0.05):
        self.start = float(start)
        self.initial_target = float(target)
        self.tolerance = float(tolerance)
        self.x = self.start
        self.target = self.initial_target
        self.success = False

    def _obs(self):
        return {"x": self.x, "target": self.target}

    def reset(self):
        self.x = self.start
        self.target = self.initial_target
        self.success = False
        return self._obs()

    def step(self, action):
        delta = max(-1.0, min(1.0, float(action)))
        self.x += delta
        self.success = abs(self.x - self.target) <= self.tolerance
        return self._obs(), float(self.success), self.success, {}

    def snapshot(self):
        return {"x": self.x, "target": self.target, "success": self.success}

    def move_target(self, new_target: float):
        old = self.target
        self.target = float(new_target)
        self.success = abs(self.x - self.target) <= self.tolerance
        return {"old_target": old, "new_target": self.target}


class GreedyChunkPolicy:
    """Plans an open-loop action chunk toward the target visible at query time."""

    def __init__(self, *, horizon: int = 8, step_size: float = 1.0):
        self.horizon = int(horizon)
        self.step_size = float(step_size)
        self.query_count = 0

    def reset(self):
        self.query_count = 0

    def act(self, observation, instruction):
        self.query_count += 1
        x = float(observation["x"])
        target = float(observation["target"])
        remaining = target - x
        direction = 1.0 if remaining >= 0 else -1.0
        actions = []
        simulated = x
        for _ in range(self.horizon):
            d = target - simulated
            if abs(d) < 1e-9:
                a = 0.0
            else:
                a = direction * min(self.step_size, abs(d))
            actions.append(a)
            simulated += a
        return PolicyOutput(
            action_chunk=actions,
            predicted_future={"planned_target": target, "planned_final_x": simulated},
            metadata={"query_count": self.query_count},
        )


@dataclass
class MoveTarget:
    trigger_step: int
    new_target: float
    name: str = "move_target"

    def should_trigger(self, *, env_step, state):
        return env_step == self.trigger_step

    def apply(self, env):
        return env.move_target(self.new_target)
