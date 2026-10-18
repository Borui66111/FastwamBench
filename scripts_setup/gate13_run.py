#!/usr/bin/env python
"""[fastbench] Gate 13 orchestrator: cross-horizon "commitment cost" sweep.

THE QUESTION
------------
A World Action Model does not emit one action at a time; it predicts a future
video *and* an action chunk, then the harness commits to the first
`replan_steps` actions of that chunk before looking at the world again. That
commitment is the model's wager about the future. We ask what it COSTS when the
wager is wrong: displace the manipulated object right after a chunk is planned
and measure how badly the episode degrades as a function of the commitment
horizon H = replan_steps.

DESIGN
------
* Paired arms, same task / init-state / seed / model config:
    control  - no disturbance
    disturb  - one-shot displacement of the manipulated body by DELTA, fired at
               the first replan at absolute step WORLD_STEP.
  The two arms are bit-identical until WORLD_STEP, so the only difference is the
  displacement -> the cost is causal, not confounded.
* H swept over {1, 2, 5, 10, 15, 30}; H=10 is the released config (sim_libero.yaml)
  and H=30 is essentially the full 32-action chunk (maximal commitment).
* WORLD_STEP is chosen so that it is a chunk boundary for EVERY H in the sweep
  (see --world-step), otherwise the disturbance would land mid-chunk for some
  horizons and at a boundary for others.

OUTPUT
------
results/gate13[_TAG]/<suite>_t<tid>/H<H>/<arm>_s<seed>/{records.jsonl, ...}
Then scripts_setup/gate13_analyze.py aggregates.

USAGE
-----
    python scripts_setup/gate13_run.py --dry-run
    GATE13_TAG=pf python scripts_setup/gate13_run.py
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path("/data1/liborui/fastwam_bench")
PY = "/data1/liborui/.conda/envs/fastbench/bin/python"
FASTWAM = ROOT / "FastWAM"
CKPT = ROOT / "checkpoints" / "fastwam_release" / "libero_optional_idm_2cam224.pt"
STATS = ROOT / "checkpoints" / "fastwam_release" / "libero_optional_idm_2cam224_dataset_stats.json"

# Disturbance fires at this absolute env step. num_steps_wait=30, and chunks are
# planned at t = 30 + k*H, so (WORLD_STEP - 30) must be divisible by every H.
WORLD_STEP = 60

# [fastbench] Goal-aware disturbance: "auto" resolves the manipulated body from
# the task's own goal state and displaces it AWAY from its goal target, so the
# disturbance can never satisfy the task itself.  An explicit BODY/DELTA can
# still be forced for ablation, but the auto path is the default because an
# arbitrary delta measurably contaminates (libero_spatial t0: +x/+y lands the
# bowl on the plate -> success at the intervention step -> 0 stale actions).
BODY = "auto"
DELTA = None            # None => goal-away direction, magnitude WORLD_MAG
WORLD_MAG = "0.10"      # metres


def free_gpus(min_free_mib: int = 5000):
    out = subprocess.run(
        ["nvidia-smi", "--query-gpu=index,memory.used", "--format=csv,noheader,nounits"],
        capture_output=True, text=True, check=True,
    ).stdout
    gpus = []
    for line in out.strip().splitlines():
        idx, used = [s.strip() for s in line.split(",")]
        if int(used) < min_free_mib:
            gpus.append(int(idx))
    return gpus


def common_overrides(suite: str, tid: int, trials: int, seed: int, h: int) -> list[str]:
    return [
        "task=libero_optional_idm_2cam224_1e-4",
        f"ckpt={CKPT}",
        "model.load_text_encoder=true",
        "model.redirect_common_files=false",
        "model.action_dit_pretrained_path=null",
        "model.skip_dit_load_from_pretrain=true",
        f"EVALUATION.dataset_stats_path={STATS}",
        "EVALUATION.sigma_shift=1.0",
        "+EVALUATION.action_infer_mode=idm",
        f"EVALUATION.task_suite_name={suite}",
        f"EVALUATION.task_id={tid}",
        f"EVALUATION.num_trials={trials}",
        f"seed={seed}",
        "EVALUATION.compile_action_infer=false",
        "EVALUATION.recorder_state=true",
        f"EVALUATION.replan_steps={h}",
    ]


def build_jobs(args):
    jobs = []
    for suite, tid in args.tasks:
        for h in args.horizons:
            for seed in args.seeds:
                for arm in args.arm_list:
                    out = (args.out_root / f"{suite}_t{tid}" / f"H{h}" / f"{arm}_s{seed}")
                    jobs.append({
                        "suite": suite, "tid": tid, "h": h, "arm": arm,
                        "seed": seed, "trials": args.trials, "out": out,
                        "psnr": args.psnr,
                    })
    return jobs


def already_done(job) -> bool:
    rec = job["out"] / "records.jsonl"
    if not rec.exists():
        return False
    try:
        ends = 0
        with open(rec) as fh:
            for line in fh:
                if '"episode_end"' in line:
                    ends += 1
        return ends >= job["trials"]
    except Exception:
        return False


def run_job(job, gpu: int, args) -> tuple[str, int]:
    out: Path = job["out"]
    out.mkdir(parents=True, exist_ok=True)
    log = args.log_dir / f"{job['suite']}_t{job['tid']}_H{job['h']}_{job['arm']}_s{job['seed']}.log"
    cmd = [PY, "experiments/libero/eval_libero_single.py"]
    cmd += common_overrides(job["suite"], job["tid"], job["trials"], job["seed"], job["h"])
    cmd += [f"EVALUATION.output_dir={out}", f"EVALUATION.recorder_path={out/'records.jsonl'}"]
    if job["psnr"]:
        cmd.append("EVALUATION.visualize_future_video=true")
        # [fastbench] score the SAME lookahead lags for every H, otherwise the
        # number of scored frames is tied to replan_steps and cross-H PSNR is
        # not comparable (see evidence/gate13_psnr_matched_lag.md).
        _fl = os.environ.get("GATE13_PSNR_LAGS", "").strip()
        if _fl:
            cmd.append(f"+EVALUATION.psnr_fixed_lags=[{_fl}]")
    if job["arm"] == "disturb":
        cmd += [
            "EVALUATION.intervention_enabled=true",
            "EVALUATION.intervention_world_enabled=true",
            f"EVALUATION.intervention_world_body={args.world_body}",
            "+EVALUATION.intervention_world_auto=true",
            f"+EVALUATION.intervention_world_magnitude={args.magnitude}",
            f"+EVALUATION.intervention_world_step={args.world_step}",
            # Gate 13B: repeated strikes. Only emitted when requested so the
            # Gate 13 one-shot runs stay bit-identical.
            *([f"+EVALUATION.intervention_world_repeat_every={args.world_repeat_every}"]
              if args.world_repeat_every else []),
            *([f"+EVALUATION.intervention_world_repeat_count={args.world_repeat_count}"]
              if args.world_repeat_count else []),
            # Gate 13C: time the strikes from the detected lift instead of an
            # absolute step, so they land inside the carry phase.
            *([f"+EVALUATION.intervention_world_trigger_after_lift={args.world_trigger_after_lift}"]
              if args.world_trigger_after_lift is not None else []),
        ]
        if DELTA:
            cmd.append(f"+EVALUATION.intervention_world_delta={DELTA}")
    env = dict(os.environ)
    env.update({
        "MUJOCO_GL": "egl",
        "DIFFSYNTH_MODEL_BASE_PATH": str(ROOT / "checkpoints"),
        "DIFFSYNTH_DOWNLOAD_SOURCE": "huggingface",
        "HF_ENDPOINT": "https://hf-mirror.com",
        "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
        "CUDA_VISIBLE_DEVICES": str(gpu),
        "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
        # keep logs readable: tqdm progress bars otherwise write ~100 MB per job
        "TQDM_DISABLE": "1",
    })
    t0 = time.time()
    with open(log, "w") as fh:
        rc = subprocess.call(cmd, cwd=str(FASTWAM), env=env, stdout=fh, stderr=subprocess.STDOUT)
    dt = time.time() - t0
    return (f"GPU{gpu} {job['suite']} t{job['tid']} H{job['h']:>2} {job['arm']:>8} s{job['seed']} "
            f"-> rc={rc} in {dt/60:.1f} min"), rc


def run_job_queued(job, gpu_q: "queue.Queue[int]", args) -> tuple[str, int]:
    """Take a GPU out of the pool for the duration of one job, then return it."""
    gpu = gpu_q.get()
    try:
        return run_job(job, gpu, args)
    finally:
        gpu_q.put(gpu)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="libero_spatial:0,libero_spatial:1",
                    help="comma list suite:task_id")
    ap.add_argument("--horizons", default="1,2,5,10,15,30",
                    help="replan horizons; each must divide (world_step-30)")
    ap.add_argument("--seeds", default="1,2")
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--world-step", type=int, default=WORLD_STEP)
    ap.add_argument("--tag", default=os.environ.get("GATE13_TAG", ""))
    ap.add_argument("--ngpu", type=int, default=2)
    ap.add_argument("--world-body", default=os.environ.get("GATE13_BODY", BODY),
                    help="'auto' resolves the body from the task goal (default)")
    ap.add_argument("--world-repeat-every", type=int, default=None,
                    help="repeat the world change every N steps (Gate 13B compounding mode)")
    ap.add_argument("--world-repeat-count", type=int, default=None,
                    help="max number of strikes in repeat mode")
    ap.add_argument("--world-trigger-after-lift", type=float, default=None,
                    help="Gate 13C: detect the lift (object z rises by this many metres) "
                         "and time the strikes from there, so they land during the carry")
    ap.add_argument("--magnitude", default=os.environ.get("GATE13_MAG", WORLD_MAG),
                    help="disturbance magnitude in metres (goal-aware default)")
    ap.add_argument("--psnr", action="store_true", help="also render predicted future video")
    ap.add_argument("--arms", default="control,disturb",
                    help="comma-separated arms to run (default both)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="re-run even if complete")
    args = ap.parse_args()

    args.tasks = [tuple(p.split(":")) for p in args.tasks.split(",")]
    args.tasks = [(s, int(t)) for s, t in args.tasks]
    args.horizons = [int(x) for x in args.horizons.split(",")]
    args.seeds = [int(x) for x in args.seeds.split(",")]
    args.arm_list = [a.strip() for a in args.arms.split(",") if a.strip()]
    name = f"gate13{('_' + args.tag) if args.tag else ''}"
    args.out_root = ROOT / "results" / name
    args.log_dir = ROOT / "logs"
    args.log_dir.mkdir(parents=True, exist_ok=True)
    # Record the exact settings so downstream analysis/report text can never drift
    # from what actually ran (an earlier report hardcoded stale values).
    args.out_root.mkdir(parents=True, exist_ok=True)
    with open(args.out_root / "run_config.json", "w") as fh:
        json.dump({
            "tag": args.tag,
            "tasks": [[s, t] for s, t in args.tasks],
            "horizons": args.horizons,
            "seeds": args.seeds,
            "trials": args.trials,
            "arms": args.arm_list,
            "magnitude_m": float(args.magnitude),
            "world_step": args.world_step,
            "world_repeat_every": args.world_repeat_every,
            "world_repeat_count": args.world_repeat_count,
            "world_trigger_after_lift": args.world_trigger_after_lift,
            "world_body": args.world_body,
            "psnr": bool(args.psnr),
            "num_steps_wait": 30,
        }, fh, indent=2, sort_keys=True)

    if args.world_trigger_after_lift is not None:
        # Gate 13C: strikes are timed from the detected lift, so what has to sit
        # on a chunk boundary is the repeat interval, not world_step.
        every = int(args.world_repeat_every or 0)
        if every <= 0:
            print("ERROR: --world-trigger-after-lift requires --world-repeat-every")
            return 2
        bad = [h for h in args.horizons if every % h != 0]
        if bad:
            print(f"ERROR: horizons {bad} do not divide repeat interval {every}; "
                  f"strikes would land mid-chunk and never fire.")
            return 2
    else:
        # every H must divide (WORLD_STEP - num_steps_wait) so the disturbance lands
        # exactly on a chunk boundary for all horizons
        span = args.world_step - 30
        bad = [h for h in args.horizons if span % h != 0]
        if bad:
            print(f"ERROR: horizons {bad} do not divide span={span}; the disturbance "
                  f"would land mid-chunk. Pick divisors of {span}.")
            return 2

    jobs = build_jobs(args)
    if not args.force:
        jobs = [j for j in jobs if not already_done(j)]
    print(f"gate13: {len(jobs)} job(s) to run -> {args.out_root}")
    if args.world_trigger_after_lift is not None:
        print(f"  strikes timed from the detected lift (+{args.world_trigger_after_lift} m), "
              f"every {args.world_repeat_every} steps, count {args.world_repeat_count}")
    else:
        print(f"  world_step={args.world_step} (chunk boundary for all H: "
              f"{[h for h in args.horizons]})")
    if args.dry_run:
        for j in jobs:
            print(f"  {j['suite']} t{j['tid']} H{j['h']:>2} {j['arm']:>8} s{j['seed']} "
                  f"trials={j['trials']} psnr={j['psnr']} -> {j['out']}")
        return 0

    gpus = free_gpus()[: args.ngpu]
    if not gpus:
        print("no free GPU")
        return 1
    print(f"  using GPUs {gpus}")
    results = []
    gpu_q: "queue.Queue[int]" = queue.Queue()
    for g in gpus:
        gpu_q.put(g)
    with ThreadPoolExecutor(max_workers=len(gpus)) as ex:
        # Pull from a queue rather than assigning by submission order: a queued
        # job is handed out only when its own worker frees up, so two jobs can
        # never share one GPU (the earlier index-based mapping could collide
        # whenever jobs outnumbered GPUs).
        futs = {}
        for j in jobs:
            futs[ex.submit(run_job_queued, j, gpu_q, args)] = j
        for f in as_completed(futs):
            msg, rc = f.result()
            results.append(rc)
            print(msg, flush=True)

    print(f"\n{sum(1 for r in results if r == 0)}/{len(results)} jobs exited 0")
    print("=== ANALYZE ===")
    subprocess.call([PY, str(ROOT / "scripts_setup" / "gate13_analyze.py"), str(args.out_root)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
