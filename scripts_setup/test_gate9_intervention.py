"""[fastbench] Gate 9 unit tests: intervention determinism + recorder integrity.

Run:  python scripts_setup/test_gate9_intervention.py
Exits non-zero on any failure.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, "/data1/liborui/fastwam_bench/FastWAM")

from experiments.libero.fastbench_intervention import (  # noqa: E402
    StructuredRecorder,
    apply_intervention,
    apply_world_displacement,
    check_success,
    displace_object,
    goal_away_delta,
    maybe_displace_world,
    resolve_body_name,
    resolve_goal_targets,
    resolve_intervention_cfg,
    resolve_manipulated_body,
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

print("== 15. Gate 13 absolute-step trigger (intervention_world_step) ==")
# The absolute-step form exists so a cross-horizon sweep disturbs the world at
# the SAME env step for every replan horizon. Verify it fires on the step, not
# on the replan index, and that it stays silent at every other step.
scfg = cfg(world_enabled=True, replan_idx=0, world_body="akita_black_bowl_2_main",
           world_delta=[0.1, 0, 0], world_step=60)
check("world_step parsed", scfg.get("world_step") == 60, str(scfg.get("world_step")))
check("silent before target step", maybe_displace_world(env, scfg, 6, step_t=59) is None)
check("silent at a replan that is not the target step",
      maybe_displace_world(env, scfg, 1, step_t=10) is None)
env.sim.data.qpos[16:19] = [1.0, 2.0, 3.0]
swi = maybe_displace_world(env, scfg, 6, step_t=60)
check("fires at target step", isinstance(swi, dict))
check("fires regardless of replan index (6, not the configured 0)",
      isinstance(swi, dict) and swi.get("applied") is True)
check("silent after target step", maybe_displace_world(env, scfg, 7, step_t=61) is None)
# Same absolute step must fire for a different horizon (replan_idx differs).
env.sim.data.qpos[16:19] = [1.0, 2.0, 3.0]
swi2 = maybe_displace_world(env, scfg, 60, step_t=60)
check("fires at the same step under a different horizon", swi2 is not None)
check("no 'replan_idx' key (recorder kwarg collision)",
      "replan_idx" not in swi2, str(sorted(swi2)))
json.dumps(swi2)
check("absolute-step record is JSON-serialisable", True)

print("== 16. Gate 13 goal-aware disturbance cannot satisfy the goal ==")
# Regression for the 2026-10-17 finding: a +x/+y displacement of the task object
# landed it ON the goal and `_check_success()` flipped True at the intervention
# step, so the episode ended before a single stale action executed. The helpers
# resolve the disturbed body from the task's own goal state and displace it AWAY
# from the goal target; a candidate that still satisfies the goal is rejected.


class _M3:
    def __init__(self):
        self.body_names = ["world", "robot0_base", "akita_black_bowl_1_main", "plate_1_main"]
        self._bid = {n: i for i, n in enumerate(self.body_names)}
        self.site_names = ["robot0_grip_site"]
        self.jnt_type = np.zeros(13, dtype=int)
        self.jnt_qposadr = np.array(list(range(9)) + [9, 16, 23, 30])
        self.body_jntadr = np.array([0, 0, 9, 10])
        self.body_jntnum = np.array([0, 0, 1, 1])

    def body_name2id(self, n):
        return self._bid[n]

    def site_name2id(self, n):
        return 0


class _D3:
    def __init__(self):
        self.qpos = np.zeros(37)
        self.body_xpos = np.array([[0, 0, 0], [0, 0, 0], [0.0, 0.0, 1.0], [0.10, 0.0, 1.0]])
        self.body_xquat = np.tile([1.0, 0, 0, 0], (4, 1))
        self.site_xpos = np.zeros((1, 3))
        self.site_xmat = np.eye(3).reshape(1, 9)


class _S3:
    def __init__(self):
        self.model = _M3()
        self.data = _D3()
        self.forward_calls = 0

    def forward(self):
        self.forward_calls += 1


class _E3:
    """bowl free joint=9/qposadr=9, plate free joint=10/qposadr=16."""

    def __init__(self):
        self.sim = _S3()
        self.parsed_problem = {"goal_state": [["on", "akita_black_bowl_1", "plate_1"]]}

    def _check_success(self):
        b = self.sim.data.qpos[9:11]
        p = self.sim.data.qpos[16:18]
        return bool(np.linalg.norm(b - p) < 0.04)


e3 = _E3()
e3.sim.data.qpos[9:11] = [0.0, 0.0]
e3.sim.data.qpos[16:18] = [0.10, 0.0]
check("goal targets parsed from parsed_problem",
      resolve_goal_targets(e3) == [("akita_black_bowl_1", "plate_1")],
      str(resolve_goal_targets(e3)))
check("bddl object name -> sim body name", resolve_body_name(e3, "akita_black_bowl_1") == "akita_black_bowl_1_main")
check("manipulated body auto-resolved from goal state",
      resolve_manipulated_body(e3) == "akita_black_bowl_1_main", str(resolve_manipulated_body(e3)))
check("success is False before the disturbance", check_success(e3) is False)

away = goal_away_delta(e3, "akita_black_bowl_1_main", 0.10)
check("goal-away delta points away from the target (-x here)",
      away is not None and away[0] < -0.09 and abs(away[1]) < 1e-6, str(away))
res, used, post, rej = apply_world_displacement(e3, "akita_black_bowl_1_main", away, 0.10, True)
check("goal-away displacement applied", res.get("applied") is True, str(res.get("reason")))
check("post_iv_success stays False (task NOT completed by the disturbance)", post is False, str(post))
check("no candidate rejected in the clean case", rej == [], str(rej))

# Now feed a deliberately contaminating delta (moves the bowl ONTO the plate).
e3.sim.data.qpos[9:11] = [0.0, 0.0]
e3.sim.data.qpos[16:18] = [0.10, 0.0]
res2, used2, post2, rej2 = apply_world_displacement(e3, "akita_black_bowl_1_main", [0.10, 0.0, 0.0], 0.10, True)
check("contaminating candidate is rejected", len(rej2) >= 1, str(rej2))
check("rejection is recorded with post_iv_success=True", rej2 and rej2[0].get("post_iv_success") is True, str(rej2))
check("fallback candidate is used and is non-contaminating", post2 is False, str(post2))
check("contaminating displacement was reverted", abs(e3.sim.data.qpos[9]) < 0.15, str(e3.sim.data.qpos[9]))
check("success is False after the guarded displacement", check_success(e3) is False)

print("== 17. Gate 13B repeated strikes (compounding world change) ==")
# Rationale: one strike can only invalidate H actions once, and re-acquisition
# absorbs that. Repeating the strike leaves H stale actions PER STRIKE, so any
# horizon effect compounds with strike count instead of being absorbed.
rcfg = cfg(world_enabled=True, replan_idx=0, world_body="akita_black_bowl_2_main",
           world_delta=[0.1, 0, 0], world_step=60, world_repeat_every=10,
           world_repeat_count=3)
check("repeat_every parsed", rcfg.get("world_repeat_every") == 10,
      str(rcfg.get("world_repeat_every")))
check("silent before first strike",
      maybe_displace_world(env, rcfg, 0, step_t=59) is None)
strikes = []
for t in (60, 70, 80, 90, 100, 110):
    env.sim.data.qpos[16:19] = [1.0, 2.0, 3.0]
    r = maybe_displace_world(env, rcfg, t // 10, step_t=t)
    strikes.append((t, r))
fired = [t for t, r in strikes if r is not None]
check("fires on every multiple of the interval within the cap",
      fired == [60, 70, 80], str(fired))
check("count cap stops further strikes", 90 not in fired and 100 not in fired, str(fired))
check("no strike between multiples",
      maybe_displace_world(env, rcfg, 6, step_t=65) is None)
idx = [r.get("strike") for t, r in strikes if r is not None]
check("strike index increments", idx == [0, 1, 2], str(idx))
d0 = [r.get("delta") for t, r in strikes if r is not None][0]
d1 = [r.get("delta") for t, r in strikes if r is not None][1]
check("even strike uses the goal-away direction", d0[0] > 0, str(d0))
# A mirrored strike moves the object back toward the goal and was observed
# making struck episodes FASTER than control (51 steps vs ~100). Every strike
# must therefore push away from the goal, so no strike can help.
check("odd strike also pushes away from the goal (never toward)",
      d1[0] > 0, f"{d0} vs {d1}")
check("all strikes share the same goal-away direction",
      all(r.get("delta")[0] > 0 for t, r in strikes if r is not None),
      str([r.get("delta") for t, r in strikes if r is not None]))
# Drift cap: once the object is already `world_repeat_max_dist` from its goal,
# further strikes stop, so reachability (not staleness) never becomes the
# limiting factor and the horizon comparison stays interpretable.
ccfg = cfg(world_enabled=True, replan_idx=0, world_body="akita_black_bowl_2_main",
           world_delta=[0.1, 0, 0], world_step=60, world_repeat_every=10,
           world_repeat_count=9)
check("repeat_max_dist defaults to 0.25 m",
      abs(resolve_intervention_cfg({"EVALUATION": {"intervention_enabled": True,
                                                   "intervention_world_repeat_every": 10}}
                                   ).get("world_repeat_max_dist") - 0.25) < 1e-9,
      "default should be 0.25 m")
check("repeat_max_dist is configurable",
      abs(resolve_intervention_cfg({"EVALUATION": {"intervention_world_repeat_max_dist": 0.4}}
                                   ).get("world_repeat_max_dist") - 0.4) < 1e-9)
# The cap needs a resolvable goal target, so use the fixture from section 16
# where `parsed_problem` names bowl_1 and its target. A tiny cap must suppress
# the strike; the same config with the default cap must still fire.
# The cap is a DRIFT BUDGET measured from the first strike, not an absolute
# goal distance. This fixture cannot resolve a goal target (so `_goal_distance`
# returns None and the real cap would never fire), so drive the drift directly.
import experiments.libero.fastbench_intervention as _F
_dist = [0.10]
_orig_gd = _F._goal_distance
_F._goal_distance = lambda env, body: _dist[0]
capcfg = cfg(world_enabled=True, replan_idx=0, world_body="akita_black_bowl_1_main",
             world_step=60, world_repeat_every=10, world_repeat_count=9,
             world_repeat_max_dist=0.05)
_first = maybe_displace_world(e3, capcfg, 0, step_t=60)
check("first strike sets the drift anchor and fires",
      _first is not None, "first strike must fire to establish the anchor")
_dist[0] = 0.40
check("object beyond the drift cap is not struck again",
      maybe_displace_world(e3, capcfg, 1, step_t=70) is None,
      "cap branch should suppress the strike")
_F._goal_distance = _orig_gd
capok = cfg(world_enabled=True, replan_idx=0, world_body="akita_black_bowl_1_main",
            world_step=60, world_repeat_every=10, world_repeat_count=9,
            world_repeat_max_dist=0.25)
check("same config strikes when the cap is not binding",
      isinstance(maybe_displace_world(e3, capok, 0, step_t=60), dict))

check("repeat strikes are JSON-serialisable",
      all(json.loads(json.dumps(r)) is not None for t, r in strikes if r is not None))

# ---------------------------------------------------------------------------
# 18. Gate 13C: strikes timed from the detected lift (carry phase)
# ---------------------------------------------------------------------------
_orig_snap = _F.snapshot_state
_z = {"v": 0.90}


def _snap_fake(env, body_names=None):
    return {"bodies": {b: {"pos": [0.0, 0.0, _z["v"]]} for b in (body_names or [])}}


_F.snapshot_state = _snap_fake

liftcfg = cfg(world_enabled=True, replan_idx=0, world_body="akita_black_bowl_1_main",
              world_step=40, world_repeat_every=10, world_repeat_count=4,
              world_trigger_after_lift=0.02)

# object still on the table: nothing fires, at any step
_z["v"] = 0.90
check("lift trigger: no strike before the object is lifted",
      all(maybe_displace_world(e3, liftcfg, 0, step_t=t) is None
          for t in (40, 50, 60, 70, 80)))
check("lift trigger: lift anchor not yet latched", liftcfg.get("_lift_step") is None)

# object rises above the threshold at t=100 -> anchor latched there
_z["v"] = 0.93
check("lift trigger: no strike on the detection step itself",
      maybe_displace_world(e3, liftcfg, 0, step_t=100) is None)
check("lift trigger: lift step latched from the object's own height",
      liftcfg.get("_lift_step") == 100, str(liftcfg.get("_lift_step")))

# first strike is one interval AFTER the lift, then every interval
check("lift trigger: first strike lands at lift+every",
      isinstance(maybe_displace_world(e3, liftcfg, 0, step_t=110), dict))
check("lift trigger: second strike lands at lift+2*every",
      isinstance(maybe_displace_world(e3, liftcfg, 0, step_t=120), dict))

# the anchor must not drift: a later call still measures from the lift
check("lift trigger: anchor stays at the detected lift step",
      liftcfg.get("_lift_step") == 100, str(liftcfg.get("_lift_step")))

# count cap still applies
check("lift trigger: repeat count cap is still honoured",
      maybe_displace_world(e3, liftcfg, 0, step_t=150) is None)

# and the feature is opt-in: without it, absolute timing is unchanged
_z["v"] = 0.93
abs_cfg = cfg(world_enabled=True, replan_idx=0, world_body="akita_black_bowl_1_main",
              world_step=40, world_repeat_every=10, world_repeat_count=4)
check("lift trigger is opt-in: absolute world_step still fires at step 40",
      isinstance(maybe_displace_world(e3, abs_cfg, 0, step_t=40), dict))

_F.snapshot_state = _orig_snap

# The first carry canary silently ignored the flag because the key was read from
# icfg but never mapped out of cfg.EVALUATION. Assert the plumbing, not just the
# behaviour, so a missing mapping can never look like "the trigger does nothing".
_plumb = resolve_intervention_cfg({"EVALUATION": {
    "intervention_enabled": True, "intervention_mode": "world",
    "intervention_world_enabled": True, "intervention_world_body": "akita_black_bowl_1_main",
    "intervention_world_step": 40, "intervention_world_repeat_every": 10,
    "intervention_world_trigger_after_lift": 0.02,
}})
check("lift trigger survives resolve_intervention_cfg (CLI plumbing)",
      _plumb.get("world_trigger_after_lift") == 0.02,
      repr(_plumb.get("world_trigger_after_lift")))
check("lift trigger is absent when not requested",
      resolve_intervention_cfg({"EVALUATION": {
          "intervention_enabled": True, "intervention_mode": "world",
          "intervention_world_enabled": True, "intervention_world_step": 40,
      }}).get("world_trigger_after_lift") is None)

# Gate 14: the action_infer_mode override must survive into the hydra command
# line.  This is the same class of bug as the world_trigger_after_lift drop: the
# flag reaches argparse but never reaches the subprocess.
sys.path.insert(0, "/data1/liborui/fastwam_bench/scripts_setup")
try:
    import gate13_run as _g13
    for _m in ("idm", "first_frame"):
        _ov = _g13.common_overrides("libero_object", 0, 1, 1, 1, _m)
        check(f"action_infer_mode={_m} reaches the command line",
              f"+EVALUATION.action_infer_mode={_m}" in _ov,
              repr([x for x in _ov if "infer_mode" in x]))
    check("action_infer_mode defaults to idm",
          "+EVALUATION.action_infer_mode=idm" in
          _g13.common_overrides("libero_object", 0, 1, 1, 1))
    # Gate 14 budget override: absent by default (so every pre-existing run keeps
    # the upstream per-suite cap), present and correct when asked for.
    _def = _g13.common_overrides("libero_object", 0, 1, 1, 1)
    check("no max_steps override unless requested",
          not any("max_steps" in x for x in _def),
          repr([x for x in _def if "max_steps" in x]))
    _long = _g13.common_overrides("libero_object", 0, 1, 1, 1, "first_frame", 800)
    check("max_steps=800 reaches the command line",
          "+EVALUATION.max_steps=800" in _long,
          repr([x for x in _long if "max_steps" in x]))
    check("max_steps and action_infer_mode coexist",
          "+EVALUATION.action_infer_mode=first_frame" in _long and
          "+EVALUATION.max_steps=800" in _long)
    # Gate 14E: zero-stale is a distinct flag from drop-stale; setting one must
    # not silently enable the other, or the arms become indistinguishable.
    _zs = _g13.common_overrides("libero_object", 0, 3, 1, 10, "idm", None, False, True)
    _ds = _g13.common_overrides("libero_object", 0, 3, 1, 10, "idm", None, True, False)
    check("zero_stale emits its config key",
          "+EVALUATION.intervention_world_zero_stale=true" in _zs)
    check("zero_stale does not emit drop_stale",
          "+EVALUATION.intervention_world_drop_stale=true" not in _zs)
    check("drop_stale does not emit zero_stale",
          "+EVALUATION.intervention_world_zero_stale=true" not in _ds)
    check("neither flag is emitted by default",
          not any("zero_stale" in o or "drop_stale" in o
                  for o in _g13.common_overrides("libero_object", 0, 3, 1, 10)))
    _zs_cfg = resolve_intervention_cfg({"EVALUATION": {
        "intervention_enabled": True, "intervention_mode": "world",
        "intervention_world_enabled": True, "intervention_world_step": 40,
        "intervention_world_zero_stale": True,
    }})
    check("zero_stale survives resolve_intervention_cfg",
          _zs_cfg.get("world_zero_stale") is True, repr(_zs_cfg.get("world_zero_stale")))
    check("zero_stale defaults to False",
          resolve_intervention_cfg({"EVALUATION": {
              "intervention_enabled": True, "intervention_mode": "world",
              "intervention_world_enabled": True, "intervention_world_step": 40,
          }}).get("world_zero_stale") is False)
    # Gate 14D: the drop-stale positive control must be off unless asked for, and
    # must survive resolve_intervention_cfg (the same class of bug as the lift
    # trigger, which reached argparse but never the subprocess).
    check("drop_stale absent by default",
          not any("drop_stale" in x for x in _g13.common_overrides(
              "libero_object", 0, 1, 1, 1)),
          repr([x for x in _g13.common_overrides("libero_object", 0, 1, 1, 1)
                if "drop_stale" in x]))
    check("drop_stale reaches the command line when requested",
          "+EVALUATION.intervention_world_drop_stale=true" in
          _g13.common_overrides("libero_object", 0, 1, 1, 1, "idm", None, True))
    _ds = resolve_intervention_cfg({"EVALUATION": {
        "intervention_enabled": True, "intervention_mode": "world",
        "intervention_world_enabled": True, "intervention_world_step": 40,
        "intervention_world_drop_stale": True,
    }})
    check("drop_stale survives resolve_intervention_cfg",
          _ds.get("world_drop_stale") is True, repr(_ds.get("world_drop_stale")))
    check("drop_stale defaults to False",
          resolve_intervention_cfg({"EVALUATION": {
              "intervention_enabled": True, "intervention_mode": "world",
              "intervention_world_enabled": True, "intervention_world_step": 40,
          }}).get("world_drop_stale") is False)
    # GPU selection must honour CUDA_VISIBLE_DEVICES. Ignoring it silently put
    # two 5B models on one card (the heuristic picks by free memory, and both
    # launches saw the same GPU as free) -> CUDA OOM, rc=1, cell lost.
    _fake = type("R", (), {"stdout": "0, 9000\n5, 15\n7, 15\n"})()
    _orig_run = _g13.subprocess.run
    _orig_env = os.environ.get("CUDA_VISIBLE_DEVICES")
    _g13.subprocess.run = lambda *a, **k: _fake
    try:
        os.environ["CUDA_VISIBLE_DEVICES"] = "7"
        check("free_gpus honours CUDA_VISIBLE_DEVICES", _g13.free_gpus() == [7],
              repr(_g13.free_gpus()))
        os.environ.pop("CUDA_VISIBLE_DEVICES", None)
        check("free_gpus ignores busy cards when unconstrained",
              _g13.free_gpus() == [5, 7], repr(_g13.free_gpus()))
    finally:
        _g13.subprocess.run = _orig_run
        if _orig_env is None:
            os.environ.pop("CUDA_VISIBLE_DEVICES", None)
        else:
            os.environ["CUDA_VISIBLE_DEVICES"] = _orig_env
except Exception as _e:  # pragma: no cover
    check("gate13_run importable for the Gate 14 plumbing check", False, repr(_e))

print()
if FAILS:
    print(f"RESULT: {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("RESULT: ALL GATE 9 CHECKS PASSED")
