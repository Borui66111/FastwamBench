"""Gate 7 probe: validate LIBERO-Safety env action convention vs FastWAM assumptions."""
import warnings, numpy as np, torch
warnings.filterwarnings("ignore")

from libero.libero import benchmark
from libero.libero.envs import OffScreenRenderEnv
from experiments.libero.libero_utils import resolve_task_file_path

suite = benchmark.get_benchmark_dict()["libero_spatial"]()
task = suite.get_task(0)
bddl = resolve_task_file_path(task, "bddl_files", task.bddl_file)
print("bddl:", bddl, "exists:", bddl.exists())
istate = resolve_task_file_path(task, "init_states", task.init_states_file)
print("init_states:", istate, "exists:", istate.exists())
states = torch.load(istate, weights_only=False)
print("n init states:", len(states))

env = OffScreenRenderEnv(
    bddl_file_name=bddl,
    camera_heights=256, camera_widths=256,
    camera_names=["agentview", "robot0_eye_in_hand"],
)
env.seed(0)
obs = env.reset()
obs = env.set_init_state(states[0])

robot = env.robots[0]
ctrl = robot.controller
print("controller:", type(ctrl).__name__)
print("control_freq:", robot.control_freq)
for holder, label in ((env, "env"), (getattr(env, "env", None), "env.env")):
    if holder is not None and hasattr(holder, "action_space"):
        print(f"{label}.action_space:", holder.action_space)
        print(f"{label}.action_low :", np.round(holder.action_space.low, 4))
        print(f"{label}.action_high:", np.round(holder.action_space.high, 4))
        break
else:
    print("no action_space on env / env.env")
for a in ("control_range", "output_max", "output_min", "kp", "input_max", "input_min"):
    if hasattr(ctrl, a):
        print(f"  ctrl.{a}:", getattr(ctrl, a))
print("obs keys:", sorted(obs.keys()))

def eef(o):
    return np.array(o["robot0_eef_pos"])

base = eef(obs)
tests = [
    ("+x", [0.3, 0, 0, 0, 0, 0, -1]),
    ("-x", [-0.3, 0, 0, 0, 0, 0, -1]),
    ("-z", [0, 0, -0.3, 0, 0, 0, -1]),
    ("grip-close(-1)", [0, 0, 0, 0, 0, 0, -1]),
    ("grip-open(+1)", [0, 0, 0, 0, 0, 0, 1]),
]
for name, act in tests:
    o, _, done, info = env.step(np.array(act, dtype=np.float64))
    d = eef(o) - base
    print(f"{name:15s} eef_delta={np.round(d,4)} grip_qpos={np.round(o['robot0_gripper_qpos'],4)} done={done}")
env.close()
