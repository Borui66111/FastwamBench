import json

from .metrics import summarize
from .runner import run_episode
from .toy import OneDTargetEnv, GreedyChunkPolicy, MoveTarget


def run_case(replan_steps: int):
    env = OneDTargetEnv(start=0.0, target=5.0)
    policy = GreedyChunkPolicy(horizon=8, step_size=1.0)
    intervention = MoveTarget(trigger_step=2, new_target=-2.0)
    record = run_episode(
        env=env,
        policy=policy,
        instruction="reach the target",
        replan_steps=replan_steps,
        max_env_steps=20,
        intervention=intervention,
    )
    return record, summarize(record)


def main():
    results = {}
    for k in (1, 4):
        _, summary = run_case(k)
        results[f"replan_steps_{k}"] = summary
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
