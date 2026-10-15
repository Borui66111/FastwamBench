# FastWAM + LIBERO-Safety Integration Plan

## 1. Verified upstream execution path

### FastWAM
Official file:
`experiments/libero/eval_libero_single.py`

Relevant functions:
- `get_libero_env(...)` in `experiments/libero/libero_utils.py`
  - input: LIBERO benchmark `Task`
  - resolves BDDL path
  - constructs `OffScreenRenderEnv`
- `_predict_action_chunk(...)`
  - input: current LIBERO observation + task language
  - preprocesses agentview/wrist images and robot proprioception
  - calls `model.infer_action(...)` or `model.infer_joint(...)`
  - returns denormalized action chunk and optionally predicted future frames
- `run_single_episode(...)`
  - resets environment / initial state
  - if `pending_actions` is empty: queries one action chunk
  - executes `action_chunk[:replan_steps]`
  - repeats until success or max steps
  - if future visualization is enabled, captures aligned real frames and predicted frames

This is the primary hook point for FastBench.

## 2. LIBERO-Safety task path

Official registry:
`libero/libero/benchmark/vla_safety_task_map.py`

Useful MVP suite:
`obstacle_avoidance`

Each level L0/L1/L2 contains five task names. The benchmark wrapper converts each entry into a `Task` with:
- language
- problem folder
- BDDL filename
- init-state filename
- level / level_id

FastWAM's `get_libero_env` is already compatible with the same LIBERO Task -> BDDL -> OffScreenRenderEnv pattern, so the lowest-risk integration is to install LIBERO-Safety as the `libero` package used by FastWAM evaluation.

## 3. First intervention hook

Insert intervention evaluation immediately before:

```python
obs, _, done, _ = env.step(pending_actions.pop(0))
```

in `run_single_episode()`.

Conceptual patch:

```python
if fastbench_intervention is not None:
    event = fastbench_intervention.maybe_apply(
        env=env,
        env_step=t,
        observation=obs,
        replan_idx=current_replan_idx,
        remaining_actions=len(pending_actions),
    )
    if event:
        fastbench_recorder.record_intervention(event)

action = pending_actions.pop(0)
state_before = snapshot_libero_state(env)
obs, _, done, info = env.step(action)
state_after = snapshot_libero_state(env)
fastbench_recorder.record_step(...)
```

Why here: the action chunk has already been produced from the old world, so changing the world here creates a true stale-plan / future-reality-divergence condition.

## 4. State evidence to log

Do not rely only on images.

At minimum:
- robot EEF position / quaternion
- gripper qpos
- manipulated object positions / quaternions
- obstacle positions / quaternions
- contacts / collision flag where available
- current replan id
- index within action chunk
- exact executed 7D action
- intervention type / parameters / trigger time
- task success

LIBERO exposes object positions through object-state accessors backed by MuJoCo `sim.data.body_xpos` / `body_xquat`.

## 5. Moving an object in real LIBERO

Do not write directly to `body_xpos` as the default approach: body world poses are derived from generalized coordinates.
For a free-joint object, modify its joint qpos (position + quaternion), then forward the simulator.

Expected integration shape (must be verified against the concrete object/joint in the selected task):

```python
obj = base_env.get_object(object_name)
joint = obj.joints[0]
qpos = np.asarray(base_env.sim.data.get_joint_qpos(joint)).copy()
qpos[:3] += displacement_xyz
base_env.sim.data.set_joint_qpos(joint, qpos)
base_env.sim.forward()
```

For articulated / fixture objects the mechanism differs, so the MVP should deliberately choose a free-joint movable object or an already-supported dynamic obstacle.

LIBERO-Safety also contains `LinearMotionGenerator` and `CircularMotionGenerator`; these are preferable for continuous dynamic obstacles once the one-shot displacement probe works.

## 6. MVP experiment

### Research probe
Future-Reality Divergence / stale-plan execution.

### Base task
Start with one `obstacle_avoidance` task, one level only.

### Conditions
A. Control: no intervention.
B. Disturbance: at a deterministic rollout step after a chunk is planned, translate a movable target/obstacle by a fixed displacement.

### Sweep
`replan_steps in {1, 5, 10}` initially.

### Primary behavioral metrics
- native task success
- intervention-conditioned recovery success
- stale-action steps
- time/steps to recovery
- collision/safety violation if task exposes it

### WAM-specific metric (second step)
Enable explicit future output (`visualize_future_video=true` / `infer_joint`) on a compatible FastWAM checkpoint/mode and record:
- predicted future frames at each replan
- aligned post-action real frames
- future-reality divergence before vs after intervention

Do not make PSNR the only metric; add object-state / geometry distance where possible.

## 7. VLA control

The same behavioral intervention must later be runnable with a VLA policy adapter.
This lets us test whether WAM future modeling improves recovery instead of assuming it.
Future-specific metrics are reported as N/A for a policy that exposes no future.

## 8. What is not yet verified

- exact object name / free-joint availability for the chosen `obstacle_avoidance` task;
- exact safety/collision checker exposed by that task;
- whether FastWAM official evaluator accepts LIBERO-Safety suites without extending `_get_max_steps`;
- actual checkpoint compatibility / GPU memory in the server environment;
- intervention timing based on semantic phase vs fixed timestep.

These are the first server-side integration checks, not reasons to redesign the benchmark.
