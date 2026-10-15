"""Gate 7 probe 2: clean per-command sign test with reset between commands."""
import warnings, numpy as np, torch
warnings.filterwarnings("ignore")
from libero.libero import benchmark
from libero.libero.envs import OffScreenRenderEnv
from experiments.libero.libero_utils import resolve_task_file_path

suite = benchmark.get_benchmark_dict()["libero_spatial"]()
task = suite.get_task(0)
bddl = resolve_task_file_path(task, "bddl_files", task.bddl_file)
istate = resolve_task_file_path(task, "init_states", task.init_states_file)
states = torch.load(istate, weights_only=False)

env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=256, camera_widths=256,
                         camera_names=["agentview", "robot0_eye_in_hand"])
env.seed(0)
robot = env.robots[0]
ctrl = robot.controller
print("ctrl:", type(ctrl).__name__, "output_max:", ctrl.output_max, "output_min:", ctrl.output_min)
print("input_max:", ctrl.input_max, "input_min:", ctrl.input_min)
print("control_range:", getattr(ctrl, "control_range", None))
print("position_limits:", getattr(ctrl, "position_limits", None))

def run(cmd, n=1):
    obs = env.reset()
    obs = env.set_init_state(states[0])
    for _ in range(3):
        obs, _, _, _ = env.step(np.zeros(7))
    p0 = np.array(obs["robot0_eef_pos"]); g0 = np.array(obs["robot0_gripper_qpos"])
    for _ in range(n):
        obs, _, _, _ = env.step(np.array(cmd, dtype=np.float64))
    p1 = np.array(obs["robot0_eef_pos"]); g1 = np.array(obs["robot0_gripper_qpos"])
    return p1 - p0, g1 - g0

for name, cmd in [("+x", [1,0,0,0,0,0,0]), ("-x", [-1,0,0,0,0,0,0]),
                  ("+y", [0,1,0,0,0,0,0]), ("-y", [0,-1,0,0,0,0,0]),
                  ("+z", [0,0,1,0,0,0,0]), ("-z", [0,0,-1,0,0,0,0]),
                  ("grip -1", [0,0,0,0,0,0,-1]), ("grip +1", [0,0,0,0,0,0,1])]:
    dp, dg = run(cmd, n=5)
    print(f"{name:9s} 5 steps -> eef_delta={np.round(dp,4)}  grip_qpos_delta={np.round(dg,4)} grip_qpos={np.round(g0 if False else 0,4)}")
env.close()
