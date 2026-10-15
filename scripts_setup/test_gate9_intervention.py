"""[fastbench] Gate 9 unit tests: intervention determinism + recorder integrity.

Run:  python scripts_setup/test_gate9_intervention.py
Exits non-zero on any failure.
"""
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, "/data1/liborui/fastwam_bench/FastWAM")

from experiments.libero.fastbench_intervention import (  # noqa: E402
    StructuredRecorder,
    apply_intervention,
    displace_object,
    maybe_displace_world,
    resolve_intervention_cfg,
    snapshot_state,
    summarize_chunk,
)

FAILS = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def make_chunk(n=10, d=7, seed=0):
    rng = np.random.default_rng(seed)
    return rng.uniform(-1, 1, size=(n, d)).tolist()


def cfg(**kw):
    base = {
        "enabled": True,
        "mode": "zero_action",
        "replan_idx": 0,
        "step_in_chunk": 1,
        "scale": 0.0,
        "seed": 0,
        "recorder_path": None,
    }
    base.update(kw)
    return base


print("== 1. disabled by default is a no-op ==")
c = make_chunk()
orig = [list(r) for r in c]
applied, b, a = apply_intervention(c, cfg(enabled=False), 0)
check("disabled -> not applied", applied is False)
check("disabled -> chunk unchanged", c == orig)

print("== 2. wrong replan index is untouched ==")
c = make_chunk()
orig = [list(r) for r in c]
applied, _, _ = apply_intervention(c, cfg(replan_idx=0), 3)
check("replan_idx=3 vs target 0 -> not applied", applied is False)
check("wrong replan -> chunk unchanged", c == orig)

print("== 3. only the target step changes; rest of chunk preserved ==")
c = make_chunk()
orig = [list(r) for r in c]
applied, before, after = apply_intervention(c, cfg(mode="zero_action", step_in_chunk=2), 0)
check("target replan -> applied", applied is True)
check("before matches original step", before == orig[2])
check("zero_action -> zeros", after == [0.0] * 7, str(after))
check("step 2 changed", c[2] != orig[2])
check("steps 0,1,3.. unchanged", all(c[i] == orig[i] for i in [0, 1, 3, 4, 5, 6, 7, 8, 9]))

print("== 4. out-of-range step_in_chunk is a safe no-op ==")
c = make_chunk(n=3)
orig = [list(r) for r in c]
applied, _, _ = apply_intervention(c, cfg(step_in_chunk=9), 0)
check("oob step -> not applied", applied is False)
check("oob step -> unchanged", c == orig)

print("== 5. mode semantics ==")
base = make_chunk(n=5)
for mode, expect in (
    ("zero_action", lambda r: [0.0] * 7),
    ("scale", lambda r: [x * 0.5 for x in r]),
    ("invert", lambda r: [-x for x in r]),
    ("gripper_flip", lambda r: r[:6] + [-r[6]]),
):
    c = [list(r) for r in base]
    sc = 0.5 if mode == "scale" else 0.0
    _, before, after = apply_intervention(c, cfg(mode=mode, scale=sc, step_in_chunk=0), 0)
    want = expect(before)
    check(f"{mode} semantics", np.allclose(after, want, atol=1e-6), f"{after} != {want}")

print("== 6. freeze_prev uses the previous action ==")
c = make_chunk(n=5)
prev = [0.1] * 7
_, _, after = apply_intervention(c, cfg(mode="freeze_prev", step_in_chunk=0), 0, prev_action=prev)
check("freeze_prev -> previous action", np.allclose(after, prev))

print("== 7. determinism: identical seed -> identical perturbation ==")
runs = []
for _ in range(3):
    c = make_chunk(n=5)
    _, _, after = apply_intervention(c, cfg(mode="noise", seed=1234, step_in_chunk=1), 0, task_key=7)
    runs.append(after)
check("3 runs byte-identical", runs[0] == runs[1] == runs[2])
c = make_chunk(n=5)
_, _, other = apply_intervention(c, cfg(mode="noise", seed=9999, step_in_chunk=1), 0, task_key=7)
check("different seed -> different perturbation", other != runs[0])

print("== 8. resolve_intervention_cfg reads an OmegaConf-like mapping ==")


class _FakeCfg:
    def __init__(self, d):
        self._d = d

    def get(self, k, default=None):
        return self._d.get(k, default)


ic = resolve_intervention_cfg(_FakeCfg({"EVALUATION": {"intervention_enabled": True, "intervention_mode": "scale", "intervention_scale": 0.25, "intervention_replan_idx": 2}}))
check("enabled parsed", ic["enabled"] is True)
check("mode parsed", ic["mode"] == "scale")
check("scale parsed", ic["scale"] == 0.25)
check("replan parsed", ic["replan_idx"] == 2)
check("defaults for absent keys", ic["step_in_chunk"] == 1 and ic["seed"] == 0)

print("== 9. StructuredRecorder writes valid JSONL ==")
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "rec.jsonl"
    rec = StructuredRecorder(p)
    check("recorder enabled", rec.enabled is True)
    rec.record(event="step", episode=0, t=1, action=[0.1] * 7)
    rec.record(event="episode_end", episode=0, success=True)
    rec.close()
    lines = p.read_text().strip().splitlines()
    check("2 records written", len(lines) == 2)
    parsed = [json.loads(x) for x in lines]
    check("record round-trips", parsed[1]["success"] is True)
    check("event field present", parsed[0]["event"] == "step")

print("== 10. recorder is inert when path is None ==")
rec = StructuredRecorder(None)
check("disabled without path", rec.enabled is False)
rec.record(event="step")  # must not raise
rec.close()
check("no path -> no file attribute", rec.path is None)

print("== 11. summarize_chunk is JSON-safe ==")
s = summarize_chunk(np.asarray(make_chunk(n=4)))
json.dumps(s)
check("chunk_len", s["chunk_len"] == 4)
check("dim", s["dim"] == 7)
check("gripper len", len(s["gripper"]) == 4)

print("== 12. world displacement uses the qpos ADDRESS, not the joint index ==")
# Reproduces the real LIBERO layout: 7 arm joints + 2 gripper joints occupy
# qpos 0..8, then free joints whose *joint index* != *qpos address* (bowl_1 is
# joint 9 / qposadr 9, bowl_2 is joint 10 / qposadr 16). Slicing qpos by the
# joint index silently corrupts the wrong object -- regression guard for that.
class _FakeModel:
    def __init__(self):
        self.body_names = ["world", "robot0_base", "akita_black_bowl_1_main", "akita_black_bowl_2_main"]
        self.site_names = ["gripper0_grip_site"]
        self.nq = 23
        self._bid = {n: i for i, n in enumerate(self.body_names)}
        self.body_jntadr = np.array([0, 0, 9, 10])
        self.body_jntnum = np.array([0, 0, 1, 1])
        self.jnt_type = np.array([3, 3, 3, 3, 3, 3, 3, 3, 3, 0, 0])  # 0 == free
        self.jnt_qposadr = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 16])
        self._sid = {n: i for i, n in enumerate(self.site_names)}

    def body_name2id(self, n):
        return self._bid[n]

    def site_name2id(self, n):
        return self._sid[n]


class _FakeData:
    def __init__(self):
        self.qpos = np.zeros(23)
        self.body_xpos = np.zeros((4, 3))
        self.body_xquat = np.zeros((4, 4))
        self.site_xpos = np.zeros((1, 3))
        self.site_xmat = np.eye(3).reshape(1, 9)


class _FakeSim:
    def __init__(self):
        self.model = _FakeModel()
        self.data = _FakeData()
        self.forward_calls = 0

    def forward(self):
        self.forward_calls += 1


class _FakeEnv:
    def __init__(self):
        self.sim = _FakeSim()


env = _FakeEnv()
env.sim.data.qpos[16:19] = [1.0, 2.0, 3.0]   # bowl_2 real qpos
env.sim.data.qpos[9:12] = [9.0, 9.0, 9.0]    # bowl_1 real qpos
env.sim.data.qpos[10:13] = [0.0, 0.0, 0.0]   # decoy at the naive joint-index offset
res = displace_object(env, "akita_black_bowl_2_main", [0.5, 0.0, 0.0])
check("displacement applied", res["applied"] is True, str(res.get("reason")))
check("qpos_adr resolved to 16 (not joint index 10)", res["qpos_adr"] == 16, str(res.get("qpos_adr")))
check("bowl_2 x moved by the delta", abs(env.sim.data.qpos[16] - 1.5) < 1e-6, str(env.sim.data.qpos[16]))
check("bowl_1 qpos untouched", abs(env.sim.data.qpos[9] - 9.0) < 1e-6)
check("no stray write at joint-index offset 10", abs(env.sim.data.qpos[10]) < 1e-9)
check("sim.forward() called", env.sim.forward_calls == 1)

print("== 13. maybe_displace_world gating + recorder-key collision ==")
wcfg = cfg(world_enabled=False, world_body="akita_black_bowl_2_main", world_delta=[0.1, 0, 0])
check("world disabled -> None", maybe_displace_world(env, wcfg, 1) is None)
wcfg = cfg(world_enabled=True, replan_idx=1, world_body="akita_black_bowl_2_main", world_delta=[0.1, 0, 0])
check("replan mismatch -> None", maybe_displace_world(env, wcfg, 3) is None)
env.sim.data.qpos[16:19] = [1.0, 2.0, 3.0]
wi = maybe_displace_world(env, wcfg, 1)
check("target replan -> record", isinstance(wi, dict))
# The loop passes replan_idx= explicitly to recorder.record(**wi); a duplicate
# key here raises TypeError at runtime, so it must never be present.
check("no 'replan_idx' key (avoids duplicate recorder kwarg)", "replan_idx" not in wi, str(sorted(wi)))
json.dumps(wi)
check("record is JSON-serialisable", True)
check("world delta applied", abs(env.sim.data.qpos[16] - 1.1) < 1e-6, str(env.sim.data.qpos[16]))

print("== 14. snapshot_state is JSON-safe and exposes the qpos address ==")
snap = snapshot_state(env, body_names=["akita_black_bowl_2_main"])
json.dumps(snap)
check("snapshot has bodies", "akita_black_bowl_2_main" in snap["bodies"])
check("snapshot reports qpos_adr", snap["bodies"]["akita_black_bowl_2_main"]["qpos_adr"] == 16)
check("snapshot reports free_joint", snap["bodies"]["akita_black_bowl_2_main"]["free_joint"] == 10)
check("snapshot eef present", snap["eef"] is not None)

print()
if FAILS:
    print(f"RESULT: {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("RESULT: ALL GATE 9 CHECKS PASSED")
