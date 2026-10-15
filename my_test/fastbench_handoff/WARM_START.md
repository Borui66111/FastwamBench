# FastBench Warm Start for a New GPU Server / Coding Agent

_Last updated: 2026-10-08_

## 0. Your role

You are taking over an **active research benchmark implementation**, not starting a new robotics project from scratch.

Your immediate job is to move from a verified dependency-light prototype to the **first real FastWAM + LIBERO-Safety experiment** on this server, while preserving scientific validity and reproducibility.

The handoff is intentionally split into:
- `AGENTS.md`: short, always-on rules;
- this file: detailed execution plan;
- `STATE.md`: what is actually verified now;
- `REQUIREMENTS.md`: research/software contract;
- `INTEGRATION_PLAN.md`: known upstream code paths and hook points.

Do not redesign the benchmark before obtaining the first real rollout evidence unless execution reveals a genuine blocker.

---

# 1. Research objective in one paragraph

FastBench evaluates the **additional world-modeling commitment** made by World Action Models (WAMs). Standard robot benchmarks mostly ask whether a policy completes a task. FastBench adds controlled interventions and diagnostics around three relationships:

- **H1 Action → Future**: does changing the action or physical dynamics appropriately change the represented/predicted consequence?
- **H2 Future ↔ Action**: do the actions actually realize the model's anticipated future, especially near safety constraints?
- **H3 Future ↔ Reality**: when the physical world invalidates a previously planned/imagined future, how long does the policy execute stale actions and can it recover?

The first real implementation target is **H3: Future–Reality Divergence / stale-plan execution**. H1 comes second. Do not start by implementing all proposed suites.

Important: a VLA can run the same behavioral tasks. That is desirable because it provides a control group. WAM-specificity comes from the **hypothesis and additional future-consistency diagnostics**, not from banning VLAs from the benchmark.

---

# 2. What already exists and is verified

## 2.1 Generic FastBench core

A dependency-light prototype already exists in this handoff:

```text
fastbench/
  core.py      # Protocols + record dataclasses
  runner.py    # chunked rollout loop
  metrics.py   # stale-action / recovery metrics
  toy.py       # toy environment/policy/intervention
  demo.py      # deterministic demonstration

tests/
  test_runner.py
```

Important abstractions:

```text
EnvAdapter
  reset() -> observation
  step(action) -> observation, reward, done, info
  snapshot() -> structured state

PolicyAdapter
  reset()
  act(observation, instruction) -> PolicyOutput

Intervention
  should_trigger(env_step, state)
  apply(env) -> event metadata

EpisodeRecord
  steps
  replans
  interventions
  final success / metadata
```

Do not throw this abstraction away. The intended integration is to replace the toy adapters with real LIBERO/FastWAM adapters while keeping benchmark logic largely stable.

## 2.2 Toy contract test

The local prototype was executed successfully. It verified the **definition and control-loop mechanics only**, not robot performance:

- `replan_steps=1`: intervention step 2, first replan after intervention step 3, stale actions = 1, recovery succeeded.
- `replan_steps=4`: intervention step 2, first replan after intervention step 4, stale actions = 2, recovery succeeded later.

All existing prototype tests passed when last run. Re-run them on the new server before integration.

## 2.3 Verified FastWAM code path

Official upstream repository:
`https://github.com/yuantianyuan01/FastWAM`

Verified high-value files:

```text
experiments/libero/eval_libero_single.py
experiments/libero/libero_utils.py
experiments/libero/run_libero_manager.py
configs/sim_libero.yaml
```

The critical rollout is:

```text
run_single_episode(...)
  env.reset()
  env.set_init_state(...)
  if pending_actions empty:
      _predict_action_chunk(...)
      pending_actions = action_chunk[:replan_steps]
  env.step(pending_actions.pop(0))
  repeat
```

The official config currently includes `EVALUATION.replan_steps: 10`.

FastWAM also has an optional future-visualization path that calls joint inference, aligns predicted future frames with realized frames, and computes clip PSNR. We may reuse that later, but **do not make pixel PSNR the sole scientific metric**.

## 2.4 Verified LIBERO-Safety code path

Official upstream repository:
`https://github.com/LIBERO-SAFETY/LIBERO-Safety`

Important files:

```text
libero/libero/benchmark/vla_safety_task_map.py
libero/libero/benchmark/__init__.py
libero/libero/envs/bddl_base_domain.py
libero/libero/envs/object_states/base_object_states.py
libero/libero/envs/utils.py
```

Useful first suite:
`obstacle_avoidance`

Each safety suite is organized as 5 tasks × levels L0/L1/L2.

LIBERO-Safety is intentionally drop-in compatible with LIBERO; the Python package name remains `libero`. Therefore only **one** LIBERO checkout/package should be active in the FastBench environment. For FastBench integration, install LIBERO-Safety as the `libero` package rather than having standard LIBERO and LIBERO-Safety both shadowing each other.

Dynamic-motion utilities already exist in `libero/libero/envs/utils.py`, including `LinearMotionGenerator` and `CircularMotionGenerator`. Use existing simulator mechanisms when possible.

---

# 3. Non-negotiable scientific definitions

## 3.1 Recovery

For the H3 MVP, an intervention deliberately invalidates the old plan/world assumption. A recovery is not merely "eventual success". Operationally, an episode is a recovery success only if:

1. a valid intervention occurred during an active episode;
2. the policy subsequently adapted/replanned rather than only completing the old plan by coincidence;
3. the task reached a valid goal state after the intervention;
4. the post-intervention rollout did not violate the benchmark's active safety constraint.

For the earliest prototype, if adaptation cannot yet be detected semantically, use a conservative behavioral definition and label it explicitly. Do not pretend a proxy is a perfect detector.

## 3.2 Stale-action steps

Primary initial definition:

```text
stale_action_steps = number of already-planned actions executed after the intervention
                     and before the first policy re-query/replan.
```

This metric is implementation-grounded and easy to verify from the chunked rollout loop.

Do not redefine it later without versioning the metric.

## 3.3 Future–reality divergence

For models exposing an explicit predicted future, compare the future prediction generated **before the intervention** against the realized post-intervention world.

Prefer environment-grounded state error where possible, e.g. target/object pose error, over only pixel error:

```text
E_FR(h) = distance(predicted task-relevant state at t+h,
                   realized task-relevant state at t+h)
```

If a model does not expose an explicit future, report future-specific metrics as N/A; do not fabricate a pseudo-future from its action chunk.

---

# 4. Server assumptions and first inspection

Preferred first server: one NVIDIA GPU with ~48 GB VRAM (A6000/A40/L40/L40S class is sufficient for initial inference work). A100/H100 is not required for the first benchmark construction.

Before installing anything, capture the machine state:

```bash
mkdir -p ~/fastbench_server_notes
{
  date
  hostname
  uname -a
  nvidia-smi
  python --version || true
  which python || true
  df -h
  free -h
} | tee ~/fastbench_server_notes/server_inventory.txt
```

Record this path in `STATE.md`.

If this is a Spot/preemptible instance, confirm where persistent storage lives **before downloading checkpoints**. Store source code in Git and copy result/config metadata to persistent storage after every experiment batch.

---

# 5. Recommended workspace layout

Use a single parent directory, for example:

```text
/workspace/fastbench-project/
  FastWAM/             # upstream / integration branch
  LIBERO-Safety/       # installed as the active `libero` package
  fastbench-handoff/   # this package / benchmark core
  checkpoints/
  results/
  server_notes/
```

Do not modify upstream repos directly on `main`. Create a project branch before FastBench patches.

Example:

```bash
cd /workspace/fastbench-project/FastWAM
git checkout -b feature/fastbench-h3-mvp
```

Record upstream SHAs:

```bash
for d in FastWAM LIBERO-Safety; do
  echo "=== $d ==="
  git -C /workspace/fastbench-project/$d rev-parse HEAD
  git -C /workspace/fastbench-project/$d status --short
  git -C /workspace/fastbench-project/$d remote -v
 done | tee /workspace/fastbench-project/server_notes/git_state.txt
```

---

# 6. Environment bring-up: exact order

Do **not** start by installing every optional dataset/training dependency. We only need inference + LIBERO evaluation.

## Gate A — FastWAM package

Follow current upstream FastWAM environment requirements unless the server image already provides a compatible torch/CUDA stack. Current upstream reference setup is Python 3.10 and PyTorch 2.7.1 + CUDA 12.8.

Example clean environment:

```bash
conda create -n fastbench python=3.10 -y
conda activate fastbench
pip install -U pip
pip install torch==2.7.1+cu128 torchvision==0.22.1+cu128 \
  --extra-index-url https://download.pytorch.org/whl/cu128
cd /workspace/fastbench-project/FastWAM
pip install -e .
```

Verification:

```bash
python - <<'PY'
import torch
print('torch', torch.__version__)
print('cuda available', torch.cuda.is_available())
print('gpu', torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)
print('bf16', torch.cuda.is_bf16_supported() if torch.cuda.is_available() else None)
PY
```

Do not continue if CUDA is unexpectedly unavailable.

## Gate B — LIBERO-Safety as the active LIBERO package

Install system rendering dependencies as required by the image, then:

```bash
cd /workspace/fastbench-project/LIBERO-Safety
pip install -e .
pip install -r requirements.txt
pip install -r extra_requirements.txt
pip install -e third_party/robosuite-1.4
pip install mujoco==3.3.2
```

Important: `~/.libero/config.yaml` (or `LIBERO_CONFIG_PATH`) must point to **this LIBERO-Safety checkout** for at least:

```text
assets
bddl_files
benchmark_root
datasets
init_states
```

Do not proceed while paths point to an old LIBERO checkout.

## Gate C — assets

Download the LIBERO-Safety assets specified by the official repository and place them under the expected `libero/libero/assets/` location.

Do not infer success because the directory exists. Instantiate and render one task.

## Gate D — headless MuJoCo rendering

Before downloading large FastWAM checkpoints, prove that one LIBERO-Safety environment can reset and produce camera observations.

Set the rendering backend only as required by the server. On NVIDIA headless systems `MUJOCO_GL=egl` is a common choice, but verify rather than blindly forcing it.

The test should establish:

```text
Task object -> BDDL -> OffScreenRenderEnv -> reset/set_init_state -> RGB observation
```

Save one frame to disk and inspect its dimensions/non-zero content.

---

# 7. Mandatory baseline before FastBench modification

This is the most important execution gate.

**First reproduce one unmodified official FastWAM LIBERO rollout.**

Current FastWAM release flow expects a released checkpoint and dataset statistics from the official Hugging Face repository. Put them under a persistent/shared checkpoint directory.

Minimum baseline target:

```text
standard LIBERO suite
1 task
1-2 trials
unmodified FastWAM evaluator
```

Use the official evaluator/config as much as possible. Save:

```text
exact command
stdout/stderr log
checkpoint filename/hash if practical
config dump
result JSON
rollout video
FastWAM git SHA
LIBERO git SHA
```

Acceptance criterion:
- evaluator completes without crashing;
- produces a real rollout video/result;
- success/failure status is meaningful rather than empty/default output.

Only after this gate passes may you add FastBench hooks.

If the official FastWAM evaluator fails on standard LIBERO, fix/reproduce that first. Do **not** debug benchmark interventions and baseline model installation simultaneously.

---

# 8. Switch from standard LIBERO to LIBERO-Safety

After Gate 7 passes, make FastWAM use the LIBERO-Safety checkout as its active `libero` package.

First validate benchmark discovery:

```python
from libero.libero import benchmark
print(benchmark.get_benchmark_dict().keys())
```

Confirm at least:

```text
obstacle_avoidance
human_safety
obstacle_avoidance_human
affordance
reasoning_safety
```

Then instantiate **one** `obstacle_avoidance` task and run it with no FastBench intervention.

Known integration issue to check immediately:
FastWAM's `_get_max_steps(task_suite_name)` was originally written for standard LIBERO suites. LIBERO-Safety names may require adding a max-step mapping. Make the smallest explicit patch; do not silently fall back to an arbitrary value.

Record the chosen max-step policy in config and `STATE.md`.

---

# 9. First FastBench real probe: H3 Future–Reality Divergence

## 9.1 Pick the first task based on manipulability, not aesthetics

Start with one `obstacle_avoidance` task whose intervention target is a **free-joint movable object** or an existing supported dynamic obstacle.

Before coding the intervention, inspect and record:

```text
task name
level
BDDL path
object names
which object is manipulated
which object/target/obstacle can be moved safely
joint type / qpos structure
success predicate
available collision/contact signals
```

This inspection is a hard gate. Do not assume the object name or free-joint status from the natural-language instruction.

## 9.2 Hook location

The first intervention hook belongs in FastWAM:

```text
experiments/libero/eval_libero_single.py::run_single_episode
```

Place the intervention immediately before execution of an already-generated pending action:

```python
# action chunk was generated using the old world
if intervention.should_trigger(...):
    intervention.apply(env)

state_before = snapshot(...)
action = pending_actions.pop(0)
obs, _, done, info = env.step(action)
state_after = snapshot(...)
record(...)
```

Scientific reason: the action chunk must already exist before the world changes; otherwise the model simply plans from the new world and there is no stale-plan condition.

## 9.3 First intervention type

Use a **single one-shot deterministic displacement** before continuous motion.

For a free-joint object, expected pattern:

```python
obj = base_env.get_object(object_name)
joint = obj.joints[0]
qpos = np.asarray(base_env.sim.data.get_joint_qpos(joint)).copy()
qpos[:3] += displacement_xyz
base_env.sim.data.set_joint_qpos(joint, qpos)
base_env.sim.forward()
```

Verify the actual joint qpos shape before mutating it. For articulated fixtures, use the correct articulation interface instead of this free-joint pattern.

Do not write directly to `body_xpos` as the primary state mutation method.

## 9.4 Timing

Initial timing can be a deterministic simulator step for engineering validation.

However, for scientific results, prefer an intervention relative to **post-warmup execution** and record both:

```text
global env step
step since first policy action
replan index
index within current chunk
remaining pending actions
```

This lets us later separate "early vs late" disturbance from arbitrary initialization/no-op time.

## 9.5 Sweep

First sweep:

```text
Control: no intervention
Disturbance: one fixed displacement
replan_steps ∈ {1, 5, 10}
```

Run 2 trials first as smoke tests. Then 5. Only scale to 20/50 after the records look correct.

---

# 10. Episode evidence schema

Do not save only videos and success flags. Every episode must emit a machine-readable record.

Minimum metadata:

```text
run_id
timestamp
git SHAs
host/GPU
model/checkpoint
benchmark suite/task/level
seed
replan_steps
intervention config
```

Per replan:

```text
replan_idx
env_step
observation timestamp
full predicted action chunk
number of actions scheduled for execution
optional predicted future representation/frame refs
```

Per executed simulator step:

```text
env_step
replan_idx
chunk_action_idx
7D executed action
robot EEF pos/quaternion
gripper state
manipulated-object pose
target/obstacle pose
contact/collision evidence
success predicate state
intervention flag/event id
```

Episode summary:

```text
native task success
intervention applied?
intervention step
first replan after intervention
stale_action_steps
recovery success
recovery latency/steps
safety violation
termination reason
```

Use JSONL/JSON + optional NumPy files for large arrays. Keep videos as qualitative evidence, not the sole data source.

---

# 11. Initial metrics and exact interpretation

For the first real H3 result, report:

```text
Task Success Rate
Recovery Success Rate
Stale Action Steps
Recovery Latency
Safety Violation / Collision Rate (only if reliably observable)
```

Later, for explicit-future models:

```text
Future–Reality Error
```

Important validity rule:
`stale_action_steps` should be directly derived from the recorded rollout/replan boundary, not estimated from video.

A provisional recovery metric must be labeled provisional until the environment-specific success/safety predicates are fully verified.

---

# 12. Future-specific FastWAM path: second milestone, not first

Once the behavioral H3 rollout works, enable FastWAM's explicit future path where checkpoint/config support it.

The official evaluator already contains logic for:

```text
infer_joint(...)
predicted future frames
aligned realized frames
clip PSNR
```

Reuse the capture alignment instead of rewriting it.

Then add task-relevant simulator-state comparisons where possible. Example for a moved target:

```text
predicted target/endpoint location versus realized target/endpoint location
```

Do not report raw pixel PSNR alone as "world understanding".

---

# 13. Second research probe after H3 works: H1 Action-conditioned Causality

Do not implement H1 until H3 has at least one verified real rollout and result schema.

H1 asks:

```text
same relevant state/goal + different action intervention
-> should imply different consequence/future
```

The first H1 implementation should be the cleanest possible controlled counterfactual, not a broad task taxonomy.

Keep H1 metrics separate from H3 metrics. H1 is not "recovery".

---

# 14. What NOT to do yet

Do not:

- train FastWAM from scratch;
- build the full 2-suite × 5-task × 3-level matrix before one real task works;
- integrate five policy families simultaneously;
- create a new simulator;
- recreate LIBERO-Safety's unreleased data-generation pipeline;
- claim WAM > VLA before a VLA control is run;
- use only videos/screenshots as evidence;
- compare latent-space cosine values across unrelated model architectures;
- silently change metric definitions to fit observed results.

---

# 15. Failure triage order

When something fails, classify the first incorrect boundary:

```text
Task/BDDL cannot instantiate
  -> environment/task setup problem

Env renders but wrong object/state
  -> config/init-state/assets problem

Policy cannot infer
  -> FastWAM/checkpoint/preprocessing problem

Policy output shape/value invalid
  -> adapter/normalization/action-convention problem

Env step fails
  -> action convention/controller/simulator problem

Intervention not visible in simulator
  -> state mutation/joint selection/sim.forward problem

Raw trajectory correct but metric wrong
  -> recorder/evaluator problem

Internal result correct but report/plot wrong
  -> aggregation/reporting problem
```

Always freeze one task + one seed + one run while tracing a failure.

---

# 16. Required progress reports to the user

The user is new to this software stack. Do not report only code changes. After each gate, explain in plain language:

```text
What component now works?
What exact command proved it?
What artifact was produced?
What is still unverified?
What is the next single blocker?
```

For code explanations, map:

```text
file/function -> input -> transformation -> output -> scientific meaning
```

Avoid repository-wide tours unless needed.

---

# 17. Definition of Done for the first presentable result

The first presentable FastBench result exists when all of the following are true:

```text
1. Official FastWAM baseline runs on this server.
2. One LIBERO-Safety obstacle_avoidance task runs with no intervention.
3. One verified mid-rollout world intervention is applied after an action chunk is planned.
4. Episode JSON records state/action/replan/intervention evidence.
5. replan_steps = 1, 5, 10 are executed under the same task/intervention protocol.
6. At least 5 valid trials per condition exist (prefer 10+ before presentation claims).
7. Metrics are automatically aggregated.
8. At least one qualitative rollout/video clearly shows the disturbance and response.
9. All commands/configs/checkpoints/seeds/git SHAs needed to reproduce the figure are saved.
10. `STATE.md` explicitly separates observed results from interpretation.
```

The first plots should be simple and defensible:

```text
Recovery Rate vs replan_steps
Stale Action Steps vs replan_steps
(optional) Safety Violation Rate vs replan_steps
one qualitative rollout strip
```

Do not force a WAM superiority story. If longer/shorter chunking or explicit imagination does not help, report that honestly.

---

# 18. First-session checklist for the new agent

At the beginning of the new server session, do exactly this sequence:

```text
A. Read AGENTS.md, STATE.md, REQUIREMENTS.md, INTEGRATION_PLAN.md.
B. Inventory server/GPU/storage and save the output.
C. Run prototype unit tests unchanged.
D. Clone/check FastWAM and LIBERO-Safety; record exact SHAs.
E. Create clean Python 3.10 environment and verify CUDA.
F. Install LIBERO-Safety as the active `libero` package; verify config paths.
G. Render one LIBERO-Safety task offscreen.
H. Download/use released FastWAM checkpoint + dataset stats.
I. Reproduce one unmodified official FastWAM LIBERO rollout.
J. Run one LIBERO-Safety task through FastWAM without intervention.
K. Inspect the chosen object's actual joint/state representation.
L. Implement one deterministic mid-chunk intervention + structured recorder.
M. Execute control vs disturbance at replan_steps 1/5/10.
N. Review records/videos for correctness before scaling trials.
O. Update STATE.md and CHANGELOG.md with execution evidence.
```

Do not skip from D directly to L.

---

# 19. Expected agent output after the first serious work session

Return a concise status with:

```text
STATUS: PASS / BLOCKED

Server:
  GPU / CUDA / disk

Verified:
  prototype tests
  LIBERO-Safety render
  FastWAM baseline
  FastWAM + LIBERO-Safety baseline
  intervention

Artifacts:
  logs
  result JSON
  rollout video
  config
  branch/commit

Observed first result:
  only direct measured facts

Blockers:
  exact error + first failing boundary

Next action:
  one concrete next step
```

Never report a benchmark conclusion from installation success or from the toy prototype.
