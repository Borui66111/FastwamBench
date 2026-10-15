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


def maybe_displace_world(env: Any, icfg: dict, replan_idx: int) -> Optional[dict]:
    """[fastbench] Gate 9 primary H3 intervention: one-shot world-state change.

    Called immediately AFTER an action chunk has been generated but BEFORE any of
    its actions execute (handoff WARM_START.md §9.2), so the chunk is guaranteed
    to have been planned against the pre-intervention world.

    Returns a JSON-safe record, or None if no world intervention is configured /
    this is not the target replan.
    """
    body = icfg.get("world_body")
    if not icfg.get("enabled") or not icfg.get("world_enabled") or not body:
        return None
    if replan_idx != int(icfg.get("replan_idx", 0)):
        return None
    delta = icfg.get("world_delta") or [0.0, 0.0, 0.0]
    snap_before = snapshot_state(env, body_names=[body])
    res = displace_object(env, body, delta)
    snap_after = snapshot_state(env, body_names=[body])
    return {
        "kind": "world_displacement",
        "mode": "displace",
        "body": body,
        "delta": [float(x) for x in delta],
        "applied": bool(res.get("applied")),
        "reason": res.get("reason"),
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
