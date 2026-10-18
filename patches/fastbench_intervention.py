"""[fastbench] Deterministic mid-chunk action intervention + structured recorder.

Gate 9 deliverable. Two pieces:

1. `apply_intervention` — perturbs ONE action inside a freshly generated action
   chunk, at a configurable offset (`intervention_step_in_chunk`), for exactly one
   replanning event (`intervention_replan_idx`). Everything is seeded / closed-form,
   so a given (seed, mode, scale) yields byte-identical perturbations across runs.
   This is what separates a *mid-chunk* intervention from a replan-boundary one:
   the policy has already committed to the first k actions of the chunk when the
   perturbation lands, so any recovery must come from closed-loop replanning.

2. `StructuredRecorder` — writes one JSONL record per executed environment step
   (plus one per replanning event), capturing the action actually sent to the
   environment, the intervention provenance (mode/scale/before/after), and the
   terminal success flag. This makes every rollout auditable after the fact.

Config keys (all optional, under `EVALUATION:`):
    intervention_enabled:      false
    intervention_mode:         null   # zero_action | noise | scale | invert | freeze_prev | gripper_flip
    intervention_replan_idx:   0      # which chunk to perturb (0-based replan counter)
    intervention_step_in_chunk: 1     # which action within that chunk (0-based)
    intervention_scale:        0.0    # meaning depends on mode
    intervention_seed:         0
    recorder_path:             null   # JSONL destination (file or dir)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional, Sequence

import numpy as np

# Modes that are pure functions of the current action (+ optional previous action).
VALID_MODES = (
    "zero_action",
    "noise",
    "scale",
    "invert",
    "freeze_prev",
    "gripper_flip",
)

_GRIPPER_DIM = -1  # last dim of the 7-DoF LIBERO action


def resolve_intervention_cfg(cfg: Any) -> dict:
    """Pull the intervention/recorder settings out of an OmegaConf eval config."""
    ev = cfg.get("EVALUATION", cfg) if hasattr(cfg, "get") else {}
    mode = ev.get("intervention_mode", None)
    return {
        "enabled": bool(ev.get("intervention_enabled", False)),
        "mode": (str(mode) if mode is not None else None),
        "replan_idx": int(ev.get("intervention_replan_idx", 0)),
        "step_in_chunk": int(ev.get("intervention_step_in_chunk", 1)),
        "scale": float(ev.get("intervention_scale", 0.0)),
        "seed": int(ev.get("intervention_seed", 0)),
        "recorder_path": ev.get("recorder_path", None),
        # [fastbench] Gate 9 primary H3 intervention: world-state displacement.
        "world_enabled": bool(ev.get("intervention_world_enabled", False)),
        "world_body": ev.get("intervention_world_body", None),
        "world_delta": ev.get("intervention_world_delta", None),
        # [fastbench] Gate 13 goal-aware disturbance: when no explicit delta is
        # given, displace the goal object AWAY from its goal target by
        # `world_magnitude` metres, and reject any candidate that would satisfy
        # the env's own goal predicate (see apply_world_displacement).
        "world_auto": bool(ev.get("intervention_world_auto", True)),
        # NOTE: `float(x or 0.10)` promotes a legitimate 0.0 (the no-op control
        # that validates the disturb code path) to 0.10 -- keep 0.0 intact.
        "world_magnitude": float(
            ev.get("intervention_world_magnitude")
            if ev.get("intervention_world_magnitude") is not None
            else 0.10
        ),
        # [fastbench] Gate 13 absolute-step trigger. Triggering purely on a replan
        # index makes the disturbance land at a *different absolute step* for
        # every replan horizon (rs=1 -> t=60, rs=10 -> t=69), which confounds any
        # cross-horizon comparison with the horizon itself. Setting
        # intervention_world_step (or intervention_stale_metric_step) pins the
        # disturbance to one absolute env step regardless of horizon.
        "world_step": ev.get("intervention_world_step", None),
        # [fastbench] Gate 14 repeated-strike mode. A single mid-chunk change can
        # only ever invalidate H actions once, and re-acquisition dominates that
        # one-off cost, so the horizon cannot show through. Repeating the change
        # every `world_repeat_every` steps leaves H stale actions PER STRIKE, so
        # any horizon effect compounds with the strike count instead of being
        # absorbed. The sign alternates so the object oscillates around its
        # original position and stays reachable at every horizon.
        "world_repeat_every": ev.get("intervention_world_repeat_every", None),
        "world_repeat_count": ev.get("intervention_world_repeat_count", None),
        "stale_metric_step": ev.get("intervention_stale_metric_step", None),
        "stale_metric": ev.get("intervention_stale_metric", True),
        "record_state": bool(ev.get("recorder_state", False)),
    }


def _deterministic_noise(shape: Sequence[int], seed: int, salt: int) -> np.ndarray:
    """Seeded standard-normal noise. Same (seed, salt, shape) -> identical array."""
    rng = np.random.default_rng(int(seed) * 1_000_003 + int(salt))
    return rng.standard_normal(tuple(shape)).astype(np.float32)


def apply_intervention(
    pending_actions: list,
    icfg: dict,
    replan_idx: int,
    *,
    prev_action: Optional[Sequence[float]] = None,
    task_key: int = 0,
) -> tuple[bool, Optional[list], Optional[list]]:
    """Perturb `pending_actions[step_in_chunk]` in place if this is the target chunk.

    Returns `(applied, before, after)`. When `applied` is False the chunk is
    untouched and `before`/`after` are None.
    """
    if not icfg.get("enabled") or icfg.get("mode") is None:
        return False, None, None
    if int(replan_idx) != int(icfg["replan_idx"]):
        return False, None, None

    k = int(icfg["step_in_chunk"])
    if k < 0 or k >= len(pending_actions):
        return False, None, None

    mode = icfg["mode"]
    if mode not in VALID_MODES:
        raise ValueError(f"Unknown intervention_mode={mode!r}; expected one of {VALID_MODES}")

    before = [float(x) for x in pending_actions[k]]
    a = np.asarray(pending_actions[k], dtype=np.float32)
    scale = float(icfg["scale"])

    if mode == "zero_action":
        new = np.zeros_like(a)
    elif mode == "noise":
        new = _deterministic_noise(a.shape, icfg["seed"], salt=int(task_key) * 97 + int(replan_idx))
    elif mode == "scale":
        new = a * scale
    elif mode == "invert":
        new = -a
    elif mode == "freeze_prev":
        # Hold the last executed action -> the arm makes no new progress this step.
        if prev_action is None:
            new = np.zeros_like(a)
        else:
            p = np.asarray(prev_action, dtype=np.float32)
            new = p if p.shape == a.shape else np.zeros_like(a)
    elif mode == "gripper_flip":
        new = a.copy()
        new[_GRIPPER_DIM] = -new[_GRIPPER_DIM]
    else:  # pragma: no cover - guarded above
        raise AssertionError(mode)

    after = [float(x) for x in new]
    pending_actions[k] = after
    return True, before, after


class StructuredRecorder:
    """Append-only JSONL recorder for executed steps and replanning events.

    Nothing is written unless `path` is truthy, so this is inert by default.
    """

    def __init__(self, path: Any = None, *, enabled: bool = True):
        self.enabled = bool(enabled and path)
        self.path: Optional[Path] = None
        self._fh = None
        self.records: list[dict] = []
        if self.enabled:
            p = Path(str(path))
            if p.suffix != ".jsonl":
                p = p / "fastbench_records.jsonl"
            p.parent.mkdir(parents=True, exist_ok=True)
            self.path = p
            self._fh = open(p, "a", encoding="utf-8")

    def record(self, **fields: Any) -> None:
        if not self.enabled:
            return
        rec = {k: v for k, v in fields.items()}
        self.records.append(rec)
        if self._fh is not None:
            self._fh.write(json.dumps(rec, default=_json_default) + "\n")
            self._fh.flush()

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, Path):
        return str(obj)
    return str(obj)


def summarize_chunk(action_chunk: Any) -> dict:
    """Compact, JSON-safe statistics for one generated action chunk."""
    a = np.asarray(action_chunk, dtype=np.float32)
    if a.ndim == 1:
        a = a[None, :]
    return {
        "chunk_len": int(a.shape[0]),
        "dim": int(a.shape[1]) if a.ndim > 1 else 0,
        "min": [float(x) for x in a.min(axis=0)],
        "max": [float(x) for x in a.max(axis=0)],
        "mean": [float(x) for x in a.mean(axis=0)],
        "gripper": [float(x) for x in a[:, _GRIPPER_DIM]],
    }


# ---------------------------------------------------------------------------
# [fastbench] Gate 9 — world-state access: snapshots and one-shot displacement.
#
# The H3 probe requires the *world* to change underneath an already-generated
# action chunk (see handoff WARM_START.md §9.2/§9.3). Action perturbation alone
# does not create a stale-plan condition, so the primary intervention mutates a
# movable object's free-joint qpos and calls sim.forward().
# ---------------------------------------------------------------------------

# Bodies that are never treated as manipulable objects.
_NON_OBJECT_PREFIXES = (
    "world", "robot0", "gripper0", "mount0", "table", "camera",
    "fixed_mount", "base", "light",
)


def _base_env(env: Any) -> Any:
    """Descend through LIBERO/robosuite wrappers to the raw robosuite env."""
    cur = env
    for _ in range(6):
        nxt = getattr(cur, "env", None)
        if nxt is None or not hasattr(nxt, "sim"):
            break
        cur = nxt
    return cur


def _sim(env: Any) -> Any:
    s = getattr(env, "sim", None)
    if s is not None:
        return s
    base = _base_env(env)
    return getattr(base, "sim", None)


def list_object_bodies(env: Any) -> list[str]:
    """Body names that look like movable scene objects (not robot/table/camera)."""
    sim = _sim(env)
    if sim is None:
        return []
    names = list(getattr(sim.model, "body_names", []) or [])
    out = []
    for n in names:
        if any(n.startswith(p) for p in _NON_OBJECT_PREFIXES):
            continue
        out.append(n)
    return out


def _free_joint_of_body(env: Any, body: str) -> Optional[int]:
    """Find the 1-DoF free joint index belonging to `body`, if any."""
    sim = _sim(env)
    if sim is None:
        return None
    try:
        bid = sim.model.body_name2id(body)
        jadr = int(sim.model.body_jntadr[bid])
        jnum = int(sim.model.body_jntnum[bid])
    except Exception:
        return None
    for j in range(jadr, jadr + jnum):
        # free joints have type 'free' (mujoco id 0)
        try:
            if int(sim.model.jnt_type[j]) == 0:
                return j
        except Exception:
            return None
    return None


def _qpos_adr(env: Any, jnt: int) -> Optional[int]:
    """qpos address for a joint.

    NOTE: the joint index and the qpos address are NOT interchangeable once
    non-free joints precede it (e.g. LIBERO's 7 arm joints + 2 gripper joints
    occupy qpos 0..8 while bowl_1's free joint is joint 9 but bowl_2's is joint
    10 with qposadr 16). Slicing qpos by the joint index silently reads the
    wrong object, so always resolve the address explicitly.
    """
    sim = _sim(env)
    if sim is None:
        return None
    try:
        return int(sim.model.jnt_qposadr[jnt])
    except Exception:
        return None


def _free_joint_qpos(env: Any, jnt: int) -> Optional[np.ndarray]:
    adr = _qpos_adr(env, jnt)
    if adr is None:
        return None
    sim = _sim(env)
    try:
        return np.asarray(sim.data.qpos[adr : adr + 7], dtype=float).copy()
    except Exception:
        return None


def snapshot_state(env: Any, body_names: Optional[Sequence[str]] = None) -> dict:
    """Machine-readable pose snapshot: EEF + movable objects. Best-effort, JSON-safe."""
    out: dict[str, Any] = {"bodies": {}, "eef": None}
    sim = _sim(env)
    if sim is None:
        return out

    # --- end-effector site ---
    try:
        site_names = list(getattr(sim.model, "site_names", []) or [])
        eef_site = next((s for s in site_names if s.endswith("grip_site")), None)
        if eef_site is not None:
            sid = sim.model.site_name2id(eef_site)
            pos = np.asarray(sim.data.site_xpos[sid], dtype=float).tolist()
            mat = np.asarray(sim.data.site_xmat[sid], dtype=float).reshape(3, 3)
            quat = _mat_to_quat(mat)
            out["eef"] = {"site": eef_site, "pos": pos, "quat": quat}
    except Exception as exc:  # pragma: no cover - defensive
        out["eef_error"] = repr(exc)

    # --- movable objects ---
    bodies = list(body_names) if body_names is not None else list_object_bodies(env)
    for b in bodies:
        try:
            bid = sim.model.body_name2id(b)
            pos = np.asarray(sim.data.body_xpos[bid], dtype=float).tolist()
            quat = np.asarray(sim.data.body_xquat[bid], dtype=float).tolist()
            jnt = _free_joint_of_body(env, b)
            rec = {"pos": pos, "quat": quat, "free_joint": jnt}
            if jnt is not None:
                adr = _qpos_adr(env, jnt)
                rec["qpos_adr"] = adr
                qp = _free_joint_qpos(env, jnt)
                if qp is not None:
                    rec["qpos"] = [float(x) for x in qp]
            out["bodies"][b] = rec
        except Exception as exc:  # pragma: no cover - defensive
            out["bodies"][b] = {"error": repr(exc)}
    return out


# ---------------------------------------------------------------------------
# [fastbench] Goal-aware intervention helpers (Gate 13).
#
# Displacing a task object in an arbitrary direction can ACCIDENTALLY SATISFY the
# goal predicate.  Measured (2026-10-17) for libero_spatial t0: a +x/+y
# displacement of akita_black_bowl_1 lands it on plate_1, `_check_success()`
# flips to True at the intervention step, the episode ends immediately and ZERO
# stale actions execute -- the disturb arm then measures nothing.
#
# These helpers make the disturbance goal-aware:
#   * the disturbed body is resolved from the task's own goal state,
#   * the direction is "away from the goal target", which can only INCREASE the
#     object->goal distance and therefore cannot satisfy `on`/`in`,
#   * the outcome is verified with the env's own predicate and recorded as
#     `post_iv_success`, with a candidate-direction fallback if it ever flips.
# ---------------------------------------------------------------------------

_GOAL_PREDICATES = ("on", "in", "inside")

# Ring of fallback unit directions, tried only if the goal-away direction ever
# contaminates (kept deterministic for reproducibility).
_FALLBACK_DIRS = [
    (-1.0, 0.0), (0.0, -1.0), (1.0, 0.0), (0.0, 1.0),
    (-0.7071, -0.7071), (-0.7071, 0.7071), (0.7071, -0.7071), (0.7071, 0.7071),
]


def _parsed_problem(env: Any) -> Optional[dict]:
    for obj in (env, getattr(env, "env", None)):
        pp = getattr(obj, "parsed_problem", None)
        if isinstance(pp, dict):
            return pp
    return None


def resolve_goal_targets(env: Any) -> list:
    """[(object_name, target_name), ...] from the task's parsed goal state."""
    pp = _parsed_problem(env)
    if not pp:
        return []
    out = []
    for pred in (pp.get("goal_state") or []):
        if len(pred) >= 3 and str(pred[0]).lower() in _GOAL_PREDICATES:
            out.append((str(pred[1]), str(pred[2])))
    return out


def resolve_body_name(env: Any, name: str) -> Optional[str]:
    """Map a bddl object/region name onto an actual sim body name."""
    sim = _sim(env)
    if sim is None:
        return None
    try:
        names = list(sim.model.body_names)
    except Exception:
        return None
    base = str(name)
    for suf in ("_contain_region", "_region"):
        if base.endswith(suf):
            base = base[: -len(suf)]
    for cand in (name, base, base + "_main"):
        if cand in names:
            return cand
    for n in names:
        if n == base or n.startswith(base + "_"):
            return n
    return None


def resolve_manipulated_body(env: Any) -> Optional[str]:
    """The body the task's goal predicate is about (i.e. what to disturb)."""
    for obj, _tgt in resolve_goal_targets(env):
        b = resolve_body_name(env, obj)
        if b is not None:
            return b
    return None


def _body_xyz(env: Any, body: str) -> Optional[list]:
    rec = snapshot_state(env, body_names=[body]).get("bodies", {}).get(body, {})
    pos = rec.get("pos")
    return [float(x) for x in pos] if pos else None


def goal_away_delta(env: Any, body: str, magnitude: float) -> Optional[list]:
    """Displacement of `body` directly AWAY from its goal target.

    Increases the object->target distance, so it can never satisfy `on`/`in`.
    Returns [dx, dy, 0.0], or None when the goal target cannot be resolved.
    """
    p = _body_xyz(env, body)
    if p is None:
        return None
    for obj, tgt in resolve_goal_targets(env):
        if resolve_body_name(env, obj) != body:
            continue
        tb = resolve_body_name(env, tgt)
        tp = _body_xyz(env, tb) if tb else None
        if tp is None:
            continue
        v = np.asarray(p[:2], dtype=float) - np.asarray(tp[:2], dtype=float)
        n = float(np.linalg.norm(v))
        if n < 1e-6:
            continue
        u = v / n
        return [float(u[0] * magnitude), float(u[1] * magnitude), 0.0]
    return None


def check_success(env: Any) -> Optional[bool]:
    """The env's own goal predicate evaluated on the CURRENT sim state."""
    for obj in (env, getattr(env, "env", None)):
        if obj is None:
            continue
        fn = getattr(obj, "_check_success", None)
        if callable(fn):
            try:
                return bool(fn())
            except Exception:
                continue
    return None


def apply_world_displacement(
    env: Any,
    body: str,
    primary_delta: Optional[Sequence[float]],
    magnitude: float,
    auto: bool,
) -> tuple:
    """Apply a goal-safe displacement; never leave the task satisfied.

    Tries `primary_delta` first, then (when `auto`) a deterministic ring of
    fallback directions.  A candidate is rejected if the env's own success
    predicate becomes True, and is reverted before the next candidate.

    Returns (result_record, delta_used, post_success, rejected_list).
    """
    cands = []
    if primary_delta:
        cands.append([float(x) for x in primary_delta])
    if auto:
        for cx, cy in _FALLBACK_DIRS:
            cands.append([cx * magnitude, cy * magnitude, 0.0])
    rejected = []
    last = None
    for d in cands:
        res = displace_object(env, body, d)
        if not res.get("applied"):
            rejected.append({"delta": d, "reason": res.get("reason")})
            continue
        post = check_success(env)
        if auto and post:
            rejected.append({"delta": d, "post_iv_success": True})
            displace_object(env, body, [-x for x in d])  # revert
            last = res
            continue
        return res, d, post, rejected
    if last is not None:
        # every candidate contaminated: restore the primary displacement state
        return last, None, check_success(env), rejected
    return {"applied": False, "reason": "no candidate applied"}, None, check_success(env), rejected


def displace_object(env: Any, body: str, delta_xyz: Sequence[float]) -> dict:
    """One-shot deterministic displacement of a free-joint object (WARM_START §9.3).

    Mutates the object's free-joint qpos translation, then sim.forward().
    Returns a JSON-safe record with before/after poses, or {'applied': False,...}.
    """
    sim = _sim(env)
    if sim is None:
        return {"applied": False, "reason": "no sim"}
    jnt = _free_joint_of_body(env, body)
    if jnt is None:
        return {"applied": False, "reason": f"no free joint on body {body!r}"}
    adr = _qpos_adr(env, jnt)
    qp = _free_joint_qpos(env, jnt)
    if adr is None or qp is None:
        return {"applied": False, "reason": f"cannot resolve qpos for {body!r}"}
    before = qp.copy()
    before[:3] = before[:3] + np.asarray(delta_xyz, dtype=float)
    try:
        sim.data.qpos[adr : adr + 7] = before
        sim.forward()
    except Exception as exc:
        return {"applied": False, "reason": f"write failed: {exc!r}"}
    after = _free_joint_qpos(env, jnt)
    if after is None:
        return {"applied": False, "reason": "readback failed"}
    return {
        "applied": True,
        "body": body,
        "free_joint": int(jnt),
        "qpos_adr": int(adr),
        "delta": [float(x) for x in delta_xyz],
        "qpos_before": [float(x) for x in qp],
        "qpos_after": [float(x) for x in after],
    }


def maybe_displace_world(env: Any, icfg: dict, replan_idx: int, step_t: Optional[int] = None) -> Optional[dict]:
    """[fastbench] Gate 9 primary H3 intervention: one-shot world-state change.

    Called immediately AFTER an action chunk has been generated but BEFORE any of
    its actions execute (handoff WARM_START.md §9.2), so the chunk is guaranteed
    to have been planned against the pre-intervention world.

    Trigger is EITHER `intervention_replan_idx` (matched against `replan_idx`) OR
    the absolute-step form `intervention_world_step` (matched against `step_t`).
    The absolute form is preferred for cross-horizon comparisons: it fires the
    disturbance at the same env step for every replan horizon, so the disturbance
    is not entangled with the horizon.

    Returns a JSON-safe record, or None if no world intervention is configured /
    this is not the target replan.
    """
    body = icfg.get("world_body")
    if not icfg.get("enabled") or not icfg.get("world_enabled") or not body:
        return None
    if str(body) == "auto":
        body = resolve_manipulated_body(env)
        if not body:
            return {"kind": "world_displacement", "applied": False,
                    "reason": "auto: could not resolve manipulated body from goal state"}
    wstep = icfg.get("world_step")
    repeat_every = icfg.get("world_repeat_every")
    strike_idx = 0
    if wstep is not None:
        if step_t is None:
            return None
        if repeat_every:
            every = max(1, int(repeat_every))
            delta_t = int(step_t) - int(wstep)
            if delta_t < 0 or delta_t % every != 0:
                return None
            strike_idx = delta_t // every
            cap = icfg.get("world_repeat_count")
            if cap is not None and strike_idx >= int(cap):
                return None
        elif int(step_t) != int(wstep):
            return None
    elif replan_idx != int(icfg.get("replan_idx", 0)):
        return None
    auto = bool(icfg.get("world_auto", True))
    # NOTE: `float(x or 0.10)` would silently promote a legitimate 0.0 magnitude
    # (the no-op control that validates the disturb code path) to 0.10.
    _mag = icfg.get("world_magnitude")
    magnitude = float(_mag) if _mag is not None else 0.10
    primary = icfg.get("world_delta")
    if not primary:
        primary = goal_away_delta(env, body, magnitude) if auto else [0.0, 0.0, 0.0]
    if repeat_every and strike_idx % 2 == 1 and primary:
        # odd strike: mirror the displacement so the object oscillates rather
        # than drifting out of the workspace as the strikes accumulate.
        primary = [-float(primary[0]), -float(primary[1]), float(primary[2])]
    snap_before = snapshot_state(env, body_names=[body])
    pre_success = check_success(env)
    res, delta_used, post_success, rejected = apply_world_displacement(
        env, body, primary, magnitude, auto
    )
    snap_after = snapshot_state(env, body_names=[body])
    return {
        "kind": "world_displacement",
        "mode": "displace",
        "strike": int(strike_idx),
        "repeat_every": (int(repeat_every) if repeat_every else None),
        "body": body,
        "auto": bool(auto),
        "magnitude": float(magnitude),
        "delta": [float(x) for x in (delta_used or [0.0, 0.0, 0.0])],
        "applied": bool(res.get("applied")),
        "reason": res.get("reason"),
        "pre_iv_success": pre_success,
        "post_iv_success": post_success,
        "rejected_candidates": rejected,
        "qpos_before": res.get("qpos_before"),
        "qpos_after": res.get("qpos_after"),
        "snapshot_before": snap_before,
        "snapshot_after": snap_after,
        "before": res.get("qpos_before"),
        "after": res.get("qpos_after"),
    }


def _mat_to_quat(mat: np.ndarray) -> list[float]:
    """3x3 rotation matrix -> (x, y, z, w) quaternion (numpy-only)."""
    m = np.asarray(mat, dtype=float).reshape(3, 3)
    tr = m[0, 0] + m[1, 1] + m[2, 2]
    if tr > 0:
        s = np.sqrt(tr + 1.0) * 2.0
        w = 0.25 * s
        x = (m[2, 1] - m[1, 2]) / s
        y = (m[0, 2] - m[2, 0]) / s
        z = (m[1, 0] - m[0, 1]) / s
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = np.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2.0
        w = (m[2, 1] - m[1, 2]) / s
        x = 0.25 * s
        y = (m[0, 1] + m[1, 0]) / s
        z = (m[0, 2] + m[2, 0]) / s
    elif m[1, 1] > m[2, 2]:
        s = np.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2.0
        w = (m[0, 2] - m[2, 0]) / s
        x = (m[0, 1] + m[1, 0]) / s
        y = 0.25 * s
        z = (m[1, 2] + m[2, 1]) / s
    else:
        s = np.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2.0
        w = (m[1, 0] - m[0, 1]) / s
        x = (m[0, 2] + m[2, 0]) / s
        y = (m[1, 2] + m[2, 1]) / s
        z = 0.25 * s
    return [float(x), float(y), float(z), float(w)]
