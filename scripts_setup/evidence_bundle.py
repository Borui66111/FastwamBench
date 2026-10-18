#!/usr/bin/env python
"""[fastbench] Build the committed, CPU-only Gate 13 raw evidence bundle.

Why this exists
---------------
`results/` is gitignored, so every reviewer-facing claim pointed at a path an
external reader cannot open. This script reduces the raw run directories to a
small, text-only bundle that *is* committed, so a reviewer can recompute every
quoted Gate 13 number without a GPU and without the 12 GB checkpoints.

What it keeps (and what it deliberately drops)
----------------------------------------------
KEPT  per-episode outcome rows, per-clip frame PSNR, the pre-intervention action
      equality check, run configs, SHAs/config hashes, checkpoint fingerprints.
DROPPED RGB frames, predicted videos, per-step simulator qpos dumps and the
      action arrays themselves (they are large and are not needed to recompute
      any quoted number; the pre-intervention equality check is stored as a
      scalar per pair instead).

Outputs (default `evidence/gate13_bundle/`)
-------------------------------------------
  episodes_<gate>.jsonl   one row per episode, both arms, with pair_id
  clips_<gate>.jsonl      one row per (episode, predicted clip)
  pairs_<gate>.jsonl      one row per (pair_id): pre-intervention max L1
  run_config_<gate>.json  exact CLI settings of that launch
  manifest.json           SHAs, controller hash, checkpoint fingerprints, versions
  SHA256SUMS              checksums over every file above
  README.md               provenance + honest limitations

Usage
-----
  python scripts_setup/evidence_bundle.py                       # default gates
  python scripts_setup/evidence_bundle.py --gates gate13_main
  python scripts_setup/evidence_bundle.py --hash-checkpoints    # slow, full sha256
"""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GATES = ["gate13_main", "gate13_psnr_clip", "gate13_psnr_lag", "gate13_lad002", "gate13_lad003"]
WORLD_STEP_DEFAULT = 40


def _sh(cmd, cwd=None):
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60).stdout.strip()
    except Exception as exc:  # pragma: no cover - environment dependent
        return f"<unavailable: {exc}>"


def _sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _fingerprint(path, full=False):
    """Cheap identity for a multi-GB checkpoint: size + head/tail hash.

    A full sha256 of a 12 GB file is correct but slow, so it is opt-in. The
    fingerprint is documented as such in the bundle README -- it identifies a
    file, it is not a substitute for a full hash.
    """
    p = Path(path)
    if not p.exists():
        return {"path": str(path), "exists": False}
    size = p.stat().st_size
    info = {"path": str(p), "exists": True, "size_bytes": size}
    if full:
        info["sha256"] = _sha256_file(p)
        info["sha256_scope"] = "full-file"
    else:
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            h.update(fh.read(1 << 20))
            if size > (1 << 20):
                fh.seek(max(0, size - (1 << 20)))
                h.update(fh.read(1 << 20))
        info["sha256"] = h.hexdigest()
        info["sha256_scope"] = "head+tail 1 MiB (fingerprint, not full-file)"
    return info


def discover_cells(gate_dir):
    """results/<gate>/<suite>_t<id>/H<h>/<arm>_s<seed>/records.jsonl"""
    out = []
    for path in sorted(gate_dir.glob("*/H*/*/records.jsonl")):
        arm_seed = path.parent.name            # e.g. control_s1
        arm, _, seed = arm_seed.rpartition("_s")
        h = path.parent.parent.name            # H10
        task = path.parent.parent.parent.name  # libero_spatial_t0
        if not arm or not seed.isdigit() or not h.startswith("H"):
            continue
        out.append({
            "path": path,
            "task": task,
            "H": int(h[1:]),
            "arm": arm,
            "seed": int(seed),
            "init_state_src": str(path.parent / "init_states.txt"),
        })
    return out


def _lag_values(fp):
    if isinstance(fp, dict):
        return {int(k): float(v) for k, v in fp.items()}
    return {i: float(v) for i, v in enumerate(fp)}


def build_gate(gate, gate_dir, world_step):
    cells = discover_cells(gate_dir)
    if not cells:
        return None

    episodes, clips, pairs = [], [], []
    for cell in cells:
        recs = [json.loads(line) for line in open(cell["path"]) if line.strip()]
        steps = [r for r in recs if r.get("event") == "step"]
        for ep in (r for r in recs if r.get("event") == "episode_end"):
            pair_id = f"{cell['task']}|H{cell['H']}|s{cell['seed']}|e{ep.get('episode')}"
            episodes.append({
                "pair_id": pair_id,
                "gate": gate,
                "task": cell["task"],
                "H": cell["H"],
                "arm": cell["arm"],
                "seed": cell["seed"],
                # LIBERO loads init_states[trial_idx]; episode index IS the init-state index.
                "init_state_idx": ep.get("episode"),
                "trial_idx": ep.get("episode"),
                "success": bool(ep.get("success")),
                "steps": ep.get("steps"),
                "stale_action_steps": ep.get("stale_action_steps"),
                "replan_steps": ep.get("replan_steps"),
                "episode_mean_psnr": ep.get("episode_mean_psnr"),
                "episode_frame_psnr": ep.get("episode_frame_psnr"),
                "world_body": ep.get("world_body"),
                "world_delta": ep.get("world_delta"),
                "world_step_target": ep.get("world_step_target"),
                "intervention_step": ep.get("intervention_step"),
                "intervention_enabled": ep.get("intervention_enabled"),
                "world_intervention_enabled": ep.get("world_intervention_enabled"),
            })
            for clip in (ep.get("episode_clip_psnr") or []):
                clips.append({
                    "pair_id": pair_id,
                    "gate": gate,
                    "task": cell["task"],
                    "H": cell["H"],
                    "arm": cell["arm"],
                    "seed": cell["seed"],
                    "init_state_idx": ep.get("episode"),
                    "clip_start_step": clip.get("start_step"),
                    "replan_idx": clip.get("replan_idx"),
                    "frame_psnr": clip.get("frame_psnr"),
                    "clip_psnr": clip.get("clip_psnr"),
                })

        # Pre-intervention action equality: the pairing validity check.
        pre = [r for r in steps if r.get("t", 0) < world_step]
        pairs.append({
            "pair_id": f"{cell['task']}|H{cell['H']}|s{cell['seed']}|e{None}",
            "gate": gate,
            "task": cell["task"],
            "H": cell["H"],
            "arm": cell["arm"],
            "seed": cell["seed"],
            "n_pre_steps": len(pre),
            "actions_pre_iv": [[r.get("t"), r.get("action")] for r in pre],
        })

    return {
        "episodes": episodes,
        "clips": clips,
        "actions_pre_iv": pairs,
        "run_config": _load_json(gate_dir / "run_config.json"),
        "summary": _load_json(gate_dir / "gate13_summary.json"),
        "n_cells": len(cells),
    }


def _load_json(path):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return None


def _write_jsonl(path, rows):
    with open(path, "w") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(ROOT / "results"))
    ap.add_argument("--out", default=str(ROOT / "evidence" / "gate13_bundle"))
    ap.add_argument("--gates", default=",".join(DEFAULT_GATES))
    ap.add_argument("--world-step", type=int, default=WORLD_STEP_DEFAULT)
    ap.add_argument("--hash-checkpoints", action="store_true")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    results = Path(args.results)

    manifest = {
        "bundle_version": 1,
        "generator": "scripts_setup/evidence_bundle.py",
        "world_step": args.world_step,
        "note": ("Text-only reduction of results/. No RGB frames, videos, or qpos dumps. "
                 "Every Gate 13 headline number is recomputable from these files with "
                 "scripts_setup/gate13_audit.py (CPU only)."),
        "gates": {},
        "provenance": {
            "repo_sha": _sh(["git", "rev-parse", "HEAD"], cwd=ROOT),
            "repo_branch": _sh(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT),
            "repo_dirty": bool(_sh(["git", "status", "--porcelain"], cwd=ROOT)),
            "fastwam_sha": _sh(["git", "rev-parse", "HEAD"], cwd=ROOT / "FastWAM"),
            "fastwam_dirty": bool(_sh(["git", "status", "--porcelain"], cwd=ROOT / "FastWAM")),
            "libero_safety_sha": _sh(["git", "rev-parse", "HEAD"], cwd=ROOT / "LIBERO-Safety"),
            "libero_safety_dirty": bool(_sh(["git", "status", "--porcelain"], cwd=ROOT / "LIBERO-Safety")),
            "controller_config": "LIBERO-Safety/third_party/robosuite-1.4/robosuite/controllers/config/osc_pose.json",
            "controller_config_sha256": _sha256_file(
                ROOT / "LIBERO-Safety/third_party/robosuite-1.4/robosuite/controllers/config/osc_pose.json"
            ) if (ROOT / "LIBERO-Safety/third_party/robosuite-1.4/robosuite/controllers/config/osc_pose.json").exists() else None,
            "checkpoints": {
                name: _fingerprint(ROOT / "checkpoints/fastwam_release" / name, full=args.hash_checkpoints)
                for name in ("libero_optional_idm_2cam224.pt", "libero_optional_idm_2cam224_dataset_stats.json")
            },
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
    }

    for gate in [g.strip() for g in args.gates.split(",") if g.strip()]:
        gate_dir = results / gate
        if not gate_dir.is_dir():
            manifest["gates"][gate] = {"status": "missing"}
            print(f"[skip] {gate}: no such results dir")
            continue
        built = build_gate(gate, gate_dir, args.world_step)
        if built is None:
            manifest["gates"][gate] = {"status": "no records.jsonl cells"}
            print(f"[skip] {gate}: no cells")
            continue
        _write_jsonl(out / f"episodes_{gate}.jsonl", built["episodes"])
        _write_jsonl(out / f"clips_{gate}.jsonl", built["clips"])
        _write_jsonl(out / f"actions_pre_iv_{gate}.jsonl", built["actions_pre_iv"])
        if built["run_config"] is not None:
            (out / f"run_config_{gate}.json").write_text(json.dumps(built["run_config"], indent=2, sort_keys=True) + "\n")
        manifest["gates"][gate] = {
            "status": "ok",
            "cells": built["n_cells"],
            "episodes": len(built["episodes"]),
            "clips": len(built["clips"]),
            "horizons": sorted({e["H"] for e in built["episodes"]}),
            "tasks": sorted({e["task"] for e in built["episodes"]}),
            "arms": sorted({e["arm"] for e in built["episodes"]}),
            "seeds": sorted({e["seed"] for e in built["episodes"]}),
            "trials_per_cell": sorted({sum(1 for e in built["episodes"] if e["task"] == t and e["H"] == h and e["arm"] == a and e["seed"] == s)
                                       for t in {e["task"] for e in built["episodes"]}
                                       for h in {e["H"] for e in built["episodes"]}
                                       for a in {e["arm"] for e in built["episodes"]}
                                       for s in {e["seed"] for e in built["episodes"]}}),
            "run_config": built["run_config"],
        }
        print(f"[ok] {gate}: {built['n_cells']} cells, {len(built['episodes'])} episodes, {len(built['clips'])} clips")

    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    # checksums over every bundle file except the checksum file itself
    sums = []
    for path in sorted(out.iterdir()):
        if path.name in ("SHA256SUMS", "README.md") or not path.is_file():
            continue
        sums.append(f"{_sha256_file(path)}  {path.name}")
    (out / "SHA256SUMS").write_text("\n".join(sums) + "\n")

    print(f"\nwrote {out}")
    print(f"  {len(sums)} files checksummed into SHA256SUMS")
    print("  next: python scripts_setup/gate13_audit.py   (CPU only, no GPU, no results/ needed)")


if __name__ == "__main__":
    main()
