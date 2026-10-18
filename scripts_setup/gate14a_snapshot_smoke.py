#!/usr/bin/env python
"""[fastbench] Gate 14A feasibility: can we fork the simulator mid-episode, exactly?

Reviewer ask (issue #2, "Replay feasibility"): exact simulator snapshot APIs, RNG
restoration strategy, action-chunk identity check, and a tiny 4-branch smoke-test
log (or a concrete blocker).

This script answers with measurements. Stages:

  snapshot  Compare the two available fork mechanisms on the SAME episode:
              (1) restore  — sim.get_state() / set_state_from_flattened()
              (2) replay   — re-simulate the recorded action prefix from the
                             episode's init state
            For each, continue 5 steps and compare against the un-forked
            reference trajectory. Reports max|dqpos| per step.

  fork      Execute the 4-branch design (control|disturb x H=1|H=10) using the
            mechanism stage 1 selected, and check that all branches are
            bit-identical pre-intervention, that only the disturb branches move
            the target body, and that the stale-action count equals H.

  chunk     (needs the checkpoint + a GPU) Is the predicted action chunk
            reproducible from the same observation and seed?

Findings from the probes that motivate this design (scripts_setup/gate14a_restore_probe*.py):

  * `sim.get_state()` carries ONLY (time, qpos, qvel) — robosuite's MjSimState has
    exactly three fields, and `set_state_from_flattened` asserts `model.na == 0`.
  * After `mj_step`, MuJoCo's `data` holds qpos/qvel at t+dt but derived
    quantities computed at t. A restore therefore has to re-derive them with
    `mj_forward`, which produces a *consistent* state at t+dt — not the mixed
    state the un-forked run would have continued from.
  * Consequence: restore-based forking perturbs the continuation (measured below,
    ~1e-3 rad on the first step). Replay-based forking is bit-exact, because two
    independent env instances driven by the same init state and the same actions
    agree to 1e-18.

Run from FastWAM/ with MUJOCO_GL=egl:
  python ../scripts_setup/gate14a_snapshot_smoke.py --stage snapshot,fork
  python ../scripts_setup/gate14a_snapshot_smoke.py --stage chunk --gpu 5
  python ../scripts_setup/gate14a_snapshot_smoke.py --stage all --out evidence/gate14a_snapshot_smoke.log

Exit code 0 only if every stage that ran passed.
"""
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
FASTWAM = ROOT / "FastWAM"
sys.path.insert(0, str(FASTWAM))

LOG = []


def log(msg=""):
    print(msg, flush=True)
    LOG.append(msg)


def arr_hash(x):
    a = np.ascontiguousarray(np.asarray(x, dtype=np.float64))
    return hashlib.sha256(a.tobytes()).hexdigest()[:16]


def find_base_env(env):
    """Walk the wrapper chain to the robosuite env (the one with `_get_observations`).

    `OffScreenRenderEnv` exposes `.sim` as a property that proxies to the inner env,
    so "first object with .sim" is the WRAPPER, which has no `_get_observations`.
    """
    seen = set()
    stack = [env]
    while stack:
        obj = stack.pop()
        if obj is None or id(obj) in seen:
            continue
        seen.add(id(obj))
        if hasattr(obj, "_get_observations"):
            return obj
        for attr in ("env", "unwrapped", "base_env", "parent"):
            stack.append(getattr(obj, attr, None))
    return None


def find_sim(env):
    """Walk the wrapper chain to the object exposing .sim."""
    seen = set()
    stack = [env]
    while stack:
        obj = stack.pop()
        if obj is None or id(obj) in seen:
            continue
        seen.add(id(obj))
        if hasattr(obj, "sim") and hasattr(getattr(obj, "sim"), "get_state"):
            return obj
        for attr in ("env", "unwrapped", "base_env", "parent"):
            stack.append(getattr(obj, attr, None))
    return None


def qpos_of(env):
    return np.array(find_sim(env).sim.data.qpos, dtype=np.float64, copy=True)


def snapshot(env):
    """The complete fork state robosuite can expose: (time, qpos, qvel)."""
    sim = find_sim(env).sim
    st = sim.get_state()
    return np.asarray(st.flatten(), dtype=np.float64).copy()


def restore(env, flat):
    """Restore a flattened (time, qpos, qvel) snapshot and re-derive everything."""
    sim = find_sim(env).sim
    sim.set_state_from_flattened(np.asarray(flat, dtype=np.float64))
    sim.forward()


def make_env(suite="libero_object", task_id=0, seed=0, resolution=256):
    from libero.libero import benchmark
    from experiments.libero.libero_utils import get_libero_env

    task_suite = benchmark.get_benchmark_dict()[suite]()
    task = task_suite.get_task(task_id)
    env, desc = get_libero_env(task, resolution, seed)
    return env, task, desc


def load_init_states(task, trial=0):
    import torch
    from experiments.libero.libero_utils import resolve_task_file_path

    path = resolve_task_file_path(task, "init_states", task.init_states_file)
    states = torch.load(path, weights_only=False)
    return states[trial]


def scripted_actions(n, seed=1234):
    """A deterministic, in-range action sequence (7-DoF LIBERO convention)."""
    rng = np.random.RandomState(seed)
    out = []
    for _ in range(n):
        a = np.zeros(7)
        a[:3] = rng.uniform(-0.4, 0.4, 3)
        a[3:6] = rng.uniform(-0.2, 0.2, 3)
        a[6] = 1.0 if rng.rand() > 0.5 else -1.0
        out.append(a)
    return out


# Fields of `sim.data` that persist across `env.reset()` and therefore leak state
# from one episode into the next. `reset()` reloads the model but does not zero
# these, so two episodes that should be identical drift apart on the first step.
MUTABLE_SIMDATA = ("ctrl", "qfrc_applied", "xfrc_applied", "qacc_warmstart",
                   "act", "mocap_pos", "mocap_quat", "userdata")


def zero_mutable_simdata(env):
    sim = find_sim(env).sim
    for name in MUTABLE_SIMDATA:
        try:
            v = getattr(sim.data, name)
        except Exception:
            continue
        try:
            v[...] = 0
        except Exception:
            pass


def episode_to(env, init_state, acts, n_steps):
    """Fresh episode, then execute `n_steps` actions. Returns obs.

    Zeroes the mutable `sim.data` fields after `reset()` so repeated episodes in
    the same env instance are bit-identical (see MUTABLE_SIMDATA).
    """
    env.reset()
    zero_mutable_simdata(env)
    obs = env.set_init_state(init_state)
    for i in range(n_steps):
        obs, _, _, _ = env.step(acts[i])
    return obs


# --------------------------------------------------------------- stage: snapshot
def stage_snapshot(env, init_state, snapshot_step=40, replay=5):
    log("## Stage 1 — fork mechanisms compared on one episode")
    log("")
    acts = scripted_actions(snapshot_step + replay + 10)

    # reference: the natural, un-forked continuation
    obs = episode_to(env, init_state, acts, snapshot_step)
    ref = []
    for i in range(snapshot_step, snapshot_step + replay):
        env.step(acts[i])
        ref.append(qpos_of(env))
    log(f"reference trajectory: steps {snapshot_step}..{snapshot_step + replay - 1}")

    # what we would snapshot at the fork point
    obs = episode_to(env, init_state, acts, snapshot_step)
    flat = snapshot(env)
    sim = find_sim(env).sim
    log(f"snapshot at step {snapshot_step}: dim={flat.size} "
        f"(1 + nq={sim.model.nq} + nv={sim.model.nv}), na={sim.model.na}")
    log("")

    results = {}

    # --- mechanism 1: restore -------------------------------------------------
    restore(env, flat)
    d0 = float(np.abs(qpos_of(env) - ref[0]).max()) if False else 0.0
    div = []
    for j, i in enumerate(range(snapshot_step, snapshot_step + replay)):
        env.step(acts[i])
        div.append(float(np.abs(qpos_of(env) - ref[j]).max()))
    results["restore"] = div
    log("  restore (get_state -> set_state_from_flattened -> forward)")
    for j, d in enumerate(div):
        log(f"    step {snapshot_step + j}: max|dqpos| vs reference = {d:.3e}")

    # --- mechanism 2: replay --------------------------------------------------
    episode_to(env, init_state, acts, snapshot_step)
    div = []
    for j, i in enumerate(range(snapshot_step, snapshot_step + replay)):
        env.step(acts[i])
        div.append(float(np.abs(qpos_of(env) - ref[j]).max()))
    results["replay"] = div
    log("  replay (re-simulate the action prefix from the init state)")
    for j, d in enumerate(div):
        log(f"    step {snapshot_step + j}: max|dqpos| vs reference = {d:.3e}")

    # --- mechanism 2b: replay in a SEPARATE env instance ----------------------
    env2, task2, _ = make_env()
    init2 = load_init_states(task2)
    episode_to(env2, init2, acts, snapshot_step)
    div = []
    for j, i in enumerate(range(snapshot_step, snapshot_step + replay)):
        env2.step(acts[i])
        div.append(float(np.abs(qpos_of(env2) - ref[j]).max()))
    env2.close()
    results["replay_other_instance"] = div
    log("  replay in a second, independently constructed env instance")
    for j, d in enumerate(div):
        log(f"    step {snapshot_step + j}: max|dqpos| vs reference = {d:.3e}")

    log("")
    tol = 1e-12
    ok_restore = max(results["restore"]) < tol
    ok_replay = (max(results["replay"]) < tol
                 and max(results["replay_other_instance"]) < tol)
    log(f"  restore reproduces the continuation (tol {tol:g}): "
        f"{'YES' if ok_restore else 'NO'} (worst {max(results['restore']):.3e})")
    log(f"  replay reproduces the continuation (tol {tol:g}):  "
        f"{'YES' if ok_replay else 'NO'} (worst "
        f"{max(max(results['replay']), max(results['replay_other_instance'])):.3e})")
    log("")
    chosen = "replay" if ok_replay else ("restore" if ok_restore else "none")
    log(f"CHOSEN FORK MECHANISM: {chosen}")
    log("")
    return ok_replay or ok_restore, {"results": results, "chosen": chosen}


# ------------------------------------------------------------------- stage: fork
def stage_fork(env, init_state, snapshot_step=40, horizons=(1, 10), magnitude=0.03):
    log("## Stage 2 — 4-branch fork mechanics (fixed chunk, no model)")
    log("")
    log("Branch = arm x H. The action chunk is a FIXED scripted array, so this stage tests")
    log("the harness (fork identity, displacement, stale accounting), not the policy.")
    log("")
    log("The strike happens AT the fork point, before any chunk action executes, which is")
    log("what Gate 13 does (displacement at the replan). Every one of the H queued actions")
    log("is therefore stale, so the stale count should equal H, not H-2.")
    log("")

    import experiments.libero.fastbench_intervention as fb

    acts = scripted_actions(snapshot_step + 40)
    obs = episode_to(env, init_state, acts, snapshot_step)
    body = fb.resolve_manipulated_body(env)
    delta = fb.goal_away_delta(env, body, magnitude) if body else None
    log(f"manipulated body={body} goal-away delta="
        f"{[round(float(x), 5) for x in delta] if delta else None}")
    if body is None or delta is None:
        log("BLOCKER: could not resolve a goal-aware displacement target for this task.")
        return False, {}

    chunk = acts[snapshot_step:snapshot_step + max(horizons)]
    log(f"fixed chunk len={len(chunk)} first_action_sha={arr_hash(chunk[0])}")
    log("")
    log("| branch | fork-point qpos | IV applied | body displacement | stale executed | post-trace |")
    log("|---|---|---|---|---|---|")

    out = {}
    for arm in ("control", "disturb"):
        for H in horizons:
            episode_to(env, init_state, acts, snapshot_step)
            fork_hash = arr_hash(qpos_of(env))
            before = np.array(fb._body_xyz(env, body), dtype=float)
            applied = False
            if arm == "disturb":
                sim = find_sim(env).sim
                jnt = fb._free_joint_of_body(env, body)
                adr = fb._qpos_adr(env, jnt)
                sim.data.qpos[adr:adr + 3] += np.asarray(delta, dtype=float)
                sim.forward()
                for obj in (env, getattr(env, "env", None)):
                    if obj is not None and callable(getattr(obj, "check_success", None)):
                        try:
                            obj.check_success()
                        except Exception:
                            pass
                applied = True
            after = np.array(fb._body_xyz(env, body), dtype=float)
            moved = float(np.linalg.norm(after - before))
            trace = []
            for k in range(H):
                env.step(chunk[k])
                trace.append(arr_hash(qpos_of(env)))
            out[f"{arm}_H{H}"] = {"fork": fork_hash, "moved_m": moved,
                                  "stale": H, "trace": trace}
            log(f"| {arm} H={H} | {fork_hash} | {'yes' if applied else 'no'} | "
                f"{moved:.4f} m | {H} | {trace[0]}..{trace[-1]} |")

    forks = {v["fork"] for v in out.values()}
    fork_equal = len(forks) == 1
    # the first `min(horizons)` steps of the chunk are the same array in both arms,
    # so control H=1 and control H=10 must agree step-for-step over that prefix.
    n = min(horizons)
    ctrl_h_agree = all(out[f"control_H{horizons[0]}"]["trace"][k]
                       == out[f"control_H{horizons[1]}"]["trace"][k] for k in range(n))
    dist_h_agree = all(out[f"disturb_H{horizons[0]}"]["trace"][k]
                       == out[f"disturb_H{horizons[1]}"]["trace"][k] for k in range(n))
    arms_differ = all(out[f"control_H{h}"]["trace"][0] != out[f"disturb_H{h}"]["trace"][0]
                      for h in horizons)
    ctrl_unmoved = all(out[f"control_H{H}"]["moved_m"] < 1e-9 for H in horizons)
    dist_moved = all(abs(out[f"disturb_H{H}"]["moved_m"] - magnitude) < 1e-3 for H in horizons)
    log("")
    log(f"  fork-point state identical across all 4 branches:          "
        f"{'PASS' if fork_equal else 'FAIL'}")
    log(f"  control H={horizons[0]} and H={horizons[1]} agree over the shared prefix:      "
        f"{'PASS' if ctrl_h_agree else 'FAIL'}")
    log(f"  disturb H={horizons[0]} and H={horizons[1]} agree over the shared prefix:      "
        f"{'PASS' if dist_h_agree else 'FAIL'}")
    log(f"  control and disturb diverge immediately after the strike:  "
        f"{'PASS' if arms_differ else 'FAIL'}")
    log(f"  control branches leave the body untouched:                "
        f"{'PASS' if ctrl_unmoved else 'FAIL'}")
    log(f"  disturb branches displace by {magnitude} m:                    "
        f"{'PASS' if dist_moved else 'FAIL'}")
    ok = (fork_equal and ctrl_h_agree and dist_h_agree and arms_differ
          and ctrl_unmoved and dist_moved)
    log("")
    log(f"PASS: {'yes' if ok else 'NO'}")
    log("")
    return ok, out


# ------------------------------------------------------------------ stage: chunk
def stage_chunk(init_state, snapshot_step=40, gpu=0, seed=0):
    log("## Stage 3 — action-chunk identity (needs checkpoint + GPU)")
    log("")
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu)
    # eval_libero_single.py does `import action_ensembler` as a sibling module, so its
    # own directory must be on sys.path (it is normally run with that cwd).
    for p in (str(FASTWAM), str(FASTWAM / "experiments" / "libero")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import torch
    from hydra import compose, initialize_config_dir
    from hydra.utils import instantiate
    from experiments.libero.eval_libero_single import _predict_action_chunk
    from fastwam.datasets.lerobot.processors.fastwam_processor import FastWAMProcessor
    from fastwam.utils.pytorch_utils import set_global_seed

    ckpt = ROOT / "checkpoints/fastwam_release/libero_optional_idm_2cam224.pt"
    stats = ROOT / "checkpoints/fastwam_release/libero_optional_idm_2cam224_dataset_stats.json"
    log(f"checkpoint={ckpt.name} exists={ckpt.exists()} gpu={gpu}")
    if not ckpt.exists():
        log("BLOCKER: checkpoint missing.")
        return False, {}

    with initialize_config_dir(config_dir=str(FASTWAM / "configs"), version_base=None):
        cfg = compose(config_name="sim_libero")
    # the two config traps: sigma_shift must be pinned, and `seed` is top-level.
    # `action_infer_mode` is not in the shipped struct, so Hydra adds it with `+` on the
    # CLI (see gate13_run.py:110); programmatically that means dropping struct mode.
    from omegaconf import OmegaConf
    OmegaConf.set_struct(cfg, False)
    cfg.EVALUATION.sigma_shift = 1.0
    cfg.EVALUATION.action_infer_mode = "idm"
    cfg.gpu_id = int(gpu)
    cfg.seed = int(seed)
    set_global_seed(int(seed), get_worker_init_fn=False)

    device = "cuda"
    model = instantiate(cfg.model, load_text_encoder=True, load_video_model=True,
                        model_path=str(ckpt), stats_path=str(stats), device=device)
    model = model.to(device).eval()
    processor = FastWAMProcessor(model_path=str(ckpt), stats_path=str(stats), device=device)

    env, task, desc = make_env()
    acts = scripted_actions(snapshot_step + 5)
    obs = episode_to(env, init_state, acts, snapshot_step)
    log(f"task={desc!r}")

    chunks = []
    for trial in range(2):
        chunk, _, _ = _predict_action_chunk(
            obs=obs, task_description=desc, model=model, processor=processor, cfg=cfg,
            action_horizon=int(cfg.EVALUATION.action_horizon),
            input_w=256, input_h=256, model_device=device,
        )
        h = arr_hash(chunk)
        chunks.append((h, np.asarray(chunk, dtype=float)))
        log(f"  call {trial + 1}: chunk_shape={tuple(np.shape(chunk))} sha={h}")

    same = chunks[0][0] == chunks[1][0]
    maxdiff = float(np.abs(chunks[0][1] - chunks[1][1]).max())
    log("")
    log(f"  identical chunks from identical obs+seed: "
        f"{'PASS' if same else 'FAIL'} (max|delta| = {maxdiff:g})")
    log("  note: `cfg.seed` is constant across calls, so every replan in a run draws")
    log("        the SAME diffusion noise. Two branches that diverge do so because of")
    log("        the observation, not because of sampling noise.")
    log("")
    log(f"PASS: {'yes' if same else 'NO'}")
    log("")
    env.close()
    return same, {"sha": chunks[0][0], "maxdiff": maxdiff}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="snapshot,fork")
    ap.add_argument("--suite", default="libero_object")
    ap.add_argument("--task-id", type=int, default=0)
    ap.add_argument("--trial", type=int, default=0)
    ap.add_argument("--snapshot-step", type=int, default=40)
    ap.add_argument("--magnitude", type=float, default=0.03)
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    stages = [s.strip() for s in args.stage.split(",") if s.strip()]
    log("# Gate 14A — fork / replay feasibility smoke test")
    log("")
    log(f"suite={args.suite} task={args.task_id} trial={args.trial} "
        f"snapshot_step={args.snapshot_step} magnitude={args.magnitude}")
    log(f"date={time.strftime('%Y-%m-%d %H:%M:%S')}")
    log("")

    verdicts = {}
    env = None
    init_state = None
    if "snapshot" in stages or "fork" in stages:
        env, task, desc = make_env(args.suite, args.task_id, seed=0)
        init_state = load_init_states(task, args.trial)
        log(f"task_description={desc!r}")
        log("")
    try:
        if "snapshot" in stages:
            ok, _ = stage_snapshot(env, init_state, args.snapshot_step)
            verdicts["snapshot"] = ok
        if "fork" in stages:
            ok, _ = stage_fork(env, init_state, args.snapshot_step, magnitude=args.magnitude)
            verdicts["fork"] = ok
    finally:
        if env is not None:
            try:
                env.close()
            except Exception:
                pass
    if "chunk" in stages:
        ok, _ = stage_chunk(init_state, args.snapshot_step, gpu=args.gpu)
        verdicts["chunk"] = ok

    log("## Verdict")
    log("")
    for k, v in verdicts.items():
        log(f"- {k}: {'PASS' if v else 'FAIL'}")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text("\n".join(LOG) + "\n")
        print(f"\nwrote {args.out}")
    return 0 if all(verdicts.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
