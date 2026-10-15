import unittest

from fastbench.metrics import stale_action_steps, recovery_success, recovery_steps
from fastbench.runner import run_episode
from fastbench.toy import OneDTargetEnv, GreedyChunkPolicy, MoveTarget


class FastBenchRunnerTests(unittest.TestCase):
    def _run(self, replan_steps):
        return run_episode(
            env=OneDTargetEnv(start=0.0, target=5.0),
            policy=GreedyChunkPolicy(horizon=8, step_size=1.0),
            instruction="reach the target",
            replan_steps=replan_steps,
            max_env_steps=20,
            intervention=MoveTarget(trigger_step=2, new_target=-2.0),
        )

    def test_short_replan_recovers_quickly(self):
        r = self._run(replan_steps=1)
        self.assertTrue(recovery_success(r))
        self.assertEqual(stale_action_steps(r), 1)
        self.assertIsNotNone(recovery_steps(r))

    def test_longer_chunk_executes_more_stale_actions(self):
        short = self._run(replan_steps=1)
        long = self._run(replan_steps=4)
        self.assertGreater(stale_action_steps(long), stale_action_steps(short))
        self.assertTrue(recovery_success(long))

    def test_intervention_is_applied_once(self):
        r = self._run(replan_steps=4)
        self.assertEqual(len(r.interventions), 1)
        self.assertEqual(r.interventions[0].env_step, 2)
        self.assertEqual(r.interventions[0].details["new_target"], -2.0)

    def test_no_intervention_returns_none_recovery_metrics(self):
        r = run_episode(
            env=OneDTargetEnv(start=0.0, target=2.0),
            policy=GreedyChunkPolicy(horizon=4),
            instruction="reach",
            replan_steps=2,
            max_env_steps=10,
            intervention=None,
        )
        self.assertIsNone(stale_action_steps(r))
        self.assertIsNone(recovery_success(r))

    def test_invalid_replan_steps_rejected(self):
        with self.assertRaises(ValueError):
            run_episode(
                env=OneDTargetEnv(),
                policy=GreedyChunkPolicy(),
                instruction="reach",
                replan_steps=0,
                max_env_steps=5,
            )


if __name__ == "__main__":
    unittest.main()
