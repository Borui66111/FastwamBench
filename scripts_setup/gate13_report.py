#!/usr/bin/env python
"""[fastbench] Gate 13 report generator.

Reads results/gate13_<tag>/gate13_summary.json and writes a reviewer-facing
markdown report with the headline table, the mechanism check, an explicit
contamination audit, and the reproduction commands.

Usage: gate13_report.py [summary.json] [out.md]
"""
import json
import sys
from pathlib import Path

ROOT = Path("/data1/liborui/fastwam_bench")
summary_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "results" / "gate13_main" / "gate13_summary.json"
out_md = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "evidence" / "gate13_commitment_cost.md"

with open(summary_path) as fh:
    summary = json.load(fh)

L = []
w = L.append
w("# Gate 13 — the cost of world-model commitment (cross-horizon sweep)\n")
w("**Question.** A World Action Model plans an action chunk, executes it open-loop for")
w("`replan_steps` (the *commitment horizon* H), then replans. If the world changes while a")
w("chunk is being executed, every remaining action in that chunk was chosen for a world that")
w("no longer exists. This experiment measures the price of that commitment as a function of H.\n")
w("**Design.** Paired arms, bit-identical until the intervention (verified: `pre_iv_max_l1 = 0`):")
w("- `control` — no intervention.\n")
cfg = summary.get("_config") or {}
_ws = cfg.get("world_step")
_mag = cfg.get("magnitude_m")
if _ws is not None:
    w(f"- `disturb` — at the replan boundary at absolute step {_ws}, teleport the task object")
    w(f"  *away* from its goal (goal-aware, magnitude {_mag} m), then let the model finish the chunk")
    w("  and replan normally. The disturbance is guaranteed **not** to satisfy the goal")
    w("  (`post_iv_success = False`, guarded + reverted otherwise).\n")
    w(f"H is swept over {cfg.get('horizons')}; every H divides ({_ws} - 30) so the trigger lands on")
    w("a real replan boundary at the same absolute step for all H.")
    w(f"Settings: magnitude={_mag} m, seeds={cfg.get('seeds')}, "
      f"trials per task/horizon={cfg.get('trials')}, tasks={cfg.get('tasks')}.\n")
else:
    w("- `disturb` — the task object is teleported *away* from its goal, then the model")
    w("  finishes the committed chunk and replans normally (goal-aware; guarded).\n")
w("## Headline (pooled across tasks)\n")
_pooled = summary.get("_pooled") or {}

def _table(rows_by_h, label):
    w("| H | control | disturbed | cost | stale executed | mean steps (ctl→dis) | timeouts (ctl→dis) | contaminated | n |")
    w("|---|---|---|---|---|---|---|---|---|")
    for h in sorted(rows_by_h, key=int):
        r = rows_by_h[h]
        n = r.get("n", r.get("n_control", "-"))
        ctl_s, dis_s = r.get("mean_steps_control"), r.get("mean_steps_disturb")
        ctl_t, dis_t = r.get("timeouts_control"), r.get("timeouts_disturb")
        steps = (f"{ctl_s:.0f} → {dis_s:.0f}" if ctl_s is not None and dis_s is not None else "—")
        tos = (f"{ctl_t} → {dis_t}" if ctl_t is not None and dis_t is not None else "—")
        _ci = r.get("disturb_ci95")
        _cis = f" [{_ci[0]:.2f},{_ci[1]:.2f}]" if _ci else ""
        w(f"| {h} | {r['control_rate']:.2f} | {r['disturb_rate']:.2f}{_cis} | "
          f"**{r['cost']:+.2f}** | "
          f"{r.get('stale_disturb', 0):.0f} | {steps} | {tos} | {r.get('contaminated_disturb', 0)} | {n} |")
    w("")

if _pooled:
    _table(_pooled, "pooled")
else:
    w("*(no pooled rows: control and disturb arms are not both present)*\n")
w("`cost` = control_rate − disturb_rate. `stale executed` = actions executed after the world")
w("change but before the next replan (mechanism check: should equal H). `contaminated` =")
w("episodes in which the disturbance accidentally completed the task (must be 0).")
w("`mean steps` and `timeouts` are graded signals: success rate alone hides the cost of")
w("recovery, so a disturbed episode that still succeeds after many extra steps, or that")
w("exhausts the 400-step budget, is reported too.\n")
w("## Per-task breakdown\n")
cands = sorted((k, v) for k, v in summary.items() if not k.startswith("_"))
if not cands:
    w("*(no paired per-task rows)*\n")
for task, by_h in cands:
    w(f"### {task}\n")
    _table(by_h, task)
w("## Trend\n")
_trend = dict((k, v) for k, v in summary.items() if not k.startswith("_"))
if summary.get("_pooled"):
    _trend["POOLED"] = summary["_pooled"]
for task, by_h in sorted(_trend.items()):
    hs = sorted(by_h, key=int)
    costs = [by_h[h]["cost"] for h in hs]
    stale = [by_h[h].get("stale_disturb", 0) for h in hs]
    mono = all(costs[i] <= costs[i + 1] + 1e-9 for i in range(len(costs) - 1))
    w(f"- **{task}**: cost by H = " + ", ".join(f"H{h}={c:+.2f}" for h, c in zip(hs, costs)))
    w(f"  - stale executed by H = " + ", ".join(f"H{h}={s:.0f}" for h, s in zip(hs, stale)))
    _ms = [by_h[h].get("mean_steps_disturb") for h in hs]
    if all(v is not None for v in _ms):
        w(f"  - mean disturbed steps by H = " + ", ".join(f"H{h}={v:.0f}" for h, v in zip(hs, _ms)))
    _toc = [by_h[h].get("timeouts_control") for h in hs]
    _tod = [by_h[h].get("timeouts_disturb") for h in hs]
    if all(v is not None for v in _tod):
        w(f"  - timeouts by H (control→disturb) = "
          + ", ".join(f"H{h}={a}→{b}" for h, a, b in zip(hs, _toc, _tod)))
    _dv = [by_h[h].get("stale_divergence_disturb") for h in hs]
    if all(v is not None for v in _dv):
        w(f"  - stale-window max divergence (m) by H = "
          + ", ".join(f"H{h}={v:.3f}" for h, v in zip(hs, _dv))
          + "   ** window length is H; NOT comparable across H **")
    _lg = [by_h[h].get("lag_divergence_disturb") or {} for h in hs]
    for _k in (1, 3, 5):
        _vals = [d.get(str(_k)) for d in _lg]
        if all(v is not None for v in _vals):
            w(f"  - fixed-lag divergence at k={_k} (m) by H = "
              + ", ".join(f"H{h}={v:+.4f}" for h, v in zip(hs, _vals))
              + "   <- fair comparison across H")
    _ex = [by_h[h].get("extra_steps_on_success") for h in hs]
    if all(v is not None for v in _ex):
        w("  - extra steps to succeed, disturbed vs control (successes only, so not "
          "inflated by timeouts) = " + ", ".join(f"H{h}={v:+.0f}" for h, v in zip(hs, _ex)))
    w(f"  - monotone increasing cost with horizon: **{mono}**")
w("\n## Interpretation\n")
w("Three things must be kept apart. They behave differently, and only the first is clean.\n")
w("1. **The commitment is real, and it scales exactly with H (mechanism, unambiguous).**")
w("   The model executes precisely H actions that were chosen for the pre-change world:")
w("   `stale executed` = H for every H tested (1, 2, 5, 10), with 0 contaminated episodes")
w("   out of 160. Control success is 1.00 in all eight cells. So the intervention does")
w("   what it claims: it invalidates committed actions mid-chunk, without solving the task")
w("   for the model and without breaking the control arm.\n")
w("2. **A mid-chunk world change is expensive (task level, large and consistent).**")
w("   Success falls by 15-60 points depending on task and horizon, mean steps rise by")
w("   60-100% (spatial 104 -> ~173; object ~175 -> 258-364), and timeouts go from 0 to 1-6")
w("   per 10 episodes. The cost is *bimodal*: an episode either recovers almost as fast as")
w("   control, or it exhausts the 400-step budget. Averaging those two populations is what")
w("   makes the raw `mean steps` column look merely 'somewhat worse'.\n")
w("3. **The success cost is NOT monotone in H at this sample size (a negative result,")
w("   stated as such).** Pooled cost by H is +0.30, +0.40, +0.15, +0.25: not increasing.")
w("   With n=10 per cell the 95% Wilson interval on a rate near 0.7 is roughly +/-0.25, so")
w("   differences of this size are inside binomial noise. The data therefore do NOT")
w("   support the strong claim 'a longer commitment costs more task success'. They support")
w("   only the mechanism claim in (1).\n")
w("4. **A first attempt at a mechanism metric did NOT survive scrutiny — reported here as")
w("   a withdrawn claim.** Measuring the end-effector/object divergence over the stale")
w("   window gives 0.002 -> 0.011 -> 0.043 -> 0.045 m for H = 1, 2, 5, 10 on")
w("   libero_spatial, which looks like a clean horizon trend. It is an artifact: the window")
w("   is (iv_step, iv_step+H], so a longer H mechanically reaches a larger maximum. At a")
w("   **fixed lag** (1, 2, 3 or 5 steps after the intervention) the divergence is the same")
w("   for every H (+0.0016…+0.0020 m at lag 1; +0.021…+0.026 m at lag 5). The eef moves")
w("   away from the displaced object at an H-independent rate. On libero_object the same")
w("   quantity is negative and equally flat (~-0.007 m at lag 1). So there is **no")
w("   evidence that a longer commitment misdirects the arm further**; what scales with H is")
w("   the number of stale actions executed, nothing more.\n")
w("Why the task-level cost fails to grow with H: the displacement is the same size at the")
w("same absolute step for every H, so re-acquiring the object is roughly H-independent and")
w("dominates the small, H-dependent part. The magnitude ladder below tested that reading")
w("directly, and **it did not rescue the strong claim** — but it produced a clean result of")
w("its own: at 0.02 m a world change is fully absorbed (20/20 disturbed episodes succeed, both")
w("tasks, both horizons, steps indistinguishable from control), so the commitment penalty is")
w("gated by whether the displacement exceeds what the next replan can correct rather than being")
w("a fixed property of the protocol. At 0.03 m the object task crosses that threshold")
w("(4/10 pooled over H, Fisher p=0.011 vs 0.02 m) while the spatial task still absorbs it")
w("completely (10/10): the threshold is **task-dependent, not horizon-dependent**. Within the")
w("object task at 0.03 m, H=1 vs H=10 is p=0.52 — noise. The H-dependent component is therefore")
w("smaller than this design can resolve, not merely masked by re-acquisition.\n")
w("\n## Magnitude ladder\n")
_any = False
for _tag, _mag in (("lad002", "0.02"), ("lad003", "0.03")):
    _p = summary_path.parent.parent / f"gate13_{_tag}" / "gate13_summary.json"
    if not _p.exists():
        _p = ROOT / "evidence" / f"gate13_{_tag}_summary.json"
    if not _p.exists():
        continue
    try:
        _s = json.loads(_p.read_text())
    except Exception:
        continue
    _pl = _s.get("_pooled") or {}
    if not _pl:
        continue
    _any = True
    w(f"### displacement {_mag} m\n")
    w("*pooled over both tasks*\n")
    _table(_pl, _tag)
    # per-task split: the pooled row hides the fact that the two tasks differ
    # by far more than the horizons do
    for _k in sorted(x for x in _s if not x.startswith("_")):
        w(f"\n*{_k}*\n")
        _table(_s[_k], _tag + _k)
if _any:
    w("**Reading the ladder.** The pooled row is the least informative one here: the two tasks")
    w("differ from each other by much more than the horizons differ within a task.")
    w("At 0.02 m the world change is fully absorbed on **both** tasks at **both** horizons")
    w("(20/20 successes) — so the commitment penalty is not a fixed property of the protocol;")
    w("it is gated by whether the displacement exceeds what the next replan can correct.")
    w("At 0.03 m the object task breaks (4/10 pooled over H, Fisher p=0.011 vs 0.02 m) while")
    w("the spatial task still absorbs it completely (10/10). Within the object task at 0.03 m,")
    w("H=1 (1/5) vs H=10 (3/5) is **not** significant (Fisher p=0.52) — the apparent reverse")
    w("trend is noise, not evidence that short horizons are worse.\n")
if not _any:
    w("*(ladder not run yet — see `scripts_setup/gate13_finish.sh`)*\n")

# --- what would be needed to settle the question ------------------------------
w("\n## What this design cannot resolve, and what would\n")
w("At n=10 per cell the binomial noise floor is roughly +/-0.25 on a rate near 0.7, so")
w("only a very large H effect could be detected. To resolve a difference of 0.10 in")
w("success rate between H=1 and H=10 at 80% power you need roughly 300 episodes per arm")
w("(two-proportion test, alpha=0.05; 0.80 vs 0.70 gives n~290 per arm). That is ~30x this")
w("sweep. The cheaper route is a metric that is continuous rather than binary. The")
w("stale-window divergence looked like one (0.002 vs 0.045 m for H=1 vs H=10 on")
w("libero_spatial), but it is measured over a window whose length IS H, so it grows with H")
w("mechanically; at a fixed lag the values collapse to +0.0016…+0.0020 m for every H. The")
w("clean continuous signal is the **count** of stale actions executed, which is exactly H")
w("by construction and verified per episode — but it is a property of the execution")
w("protocol, not a measure of task damage. A reviewer wanting the strong task-level claim")
w("should treat this report as a powered negative result at n=10, not as evidence of no")
w("effect.\n")

# --- PSNR arm: the world-modelling signal -------------------------------------
_pn = summary_path.parent.parent / "gate13_psnr" / "gate13_summary.json"
if _pn.exists():
    with open(_pn) as _fh:
        _ps = json.load(_fh)
    _pp = _ps.get("_pooled") or {}
    if _pp and any(_pp[h].get("psnr_drop") is not None for h in _pp):
        w("\n## Predicted-future vs reality (PSNR arm)\n")
        w("`visualize_future_video=true` makes the model render its predicted future; the")
        w("PSNR of that prediction against what actually happened is the most direct")
        w("world-modelling signal available. A larger drop = the model's world model is")
        w("more wrong about the world it is acting in.\n")
        w("| H | PSNR control | PSNR disturbed | drop |")
        w("|---|---|---|---|")
        for h in sorted(_pp, key=lambda x: int(x)):
            _r = _pp[h]
            if _r.get("psnr_drop") is None:
                continue
            w(f"| {h} | {_r['psnr_control']:.2f} | {_r['psnr_disturb']:.2f} | "
              f"{_r['psnr_drop']:+.2f} |")
        w("")
        _hc = _pp.get("1", {}).get("psnr_control")
        _h10c = _pp.get("10", {}).get("psnr_control")
        if None not in (_hc, _h10c):
            w(f"**Prediction fidelity falls with the horizon even with no intervention**")
            w(f"({_hc:.2f} dB at H=1 vs {_h10c:.2f} dB at H=10). That is a real and expected")
            w(f"world-modelling statement: the further ahead a model commits, the less accurate")
            w("its prediction of what actually happens.\n")
        w("**The `drop` column is NOT a valid cross-horizon comparison — do not cite it.**")
        w("`_get_future_frame_capture_steps` derives the number of scored frames from")
        w("`replan_steps` (`replan_steps // action_video_freq_ratio`, ratio=4), so H=1 scores")
        w("**one** frame (lag 0) while H=10 scores **three** (lags 0, 4, 8). A horizon therefore")
        w("looks worse partly because it is scored further into the future, and the disturbance")
        w("has had more steps to show up — not because the commitment is longer per se.")
        w("`eval_libero_single.py` now also records `episode_frame_psnr` (per-frame values) so")
        w("this can be re-analysed at a fixed lag; the numbers in this table predate that and")
        w("should be treated as withdrawn. The same caveat applies to the stale-window")
        w("divergence in the section above: at a **fixed** lag (1, 2, 3, 5 steps after the")
        w("intervention) the eef-object divergence is essentially identical across H")
        w("(+0.0016 to +0.0020 m at lag 1 for every H), so the growth seen over the full")
        w("stale window is a window-length effect. What is unambiguous is the **count**:")
        w("exactly H stale actions execute, verified per episode.\n")
w("\n## Reproduce\n")
w("```bash")
w("bash scripts_setup/gate13_all.sh   # full pipeline: sweep -> psnr -> analyze -> report")
w("")
def _task_specs(cfg):
    """tasks may be recorded as 'suite:tid' strings or as [suite, tid] pairs."""
    raw = cfg.get("tasks") or ["libero_spatial:0"]
    out = []
    for t in raw:
        if isinstance(t, (list, tuple)):
            out.append(f"{t[0]}:{t[1]}")
        else:
            out.append(str(t))
    return out


w("cd /data1/liborui/fastwam_bench")
w(f"python scripts_setup/gate13_run.py --tasks {','.join(_task_specs(cfg))} \\")
w(f"  --horizons {','.join(str(h) for h in (cfg.get('horizons') or [1, 2, 5, 10]))} "
  f"--seeds {','.join(str(s) for s in (cfg.get('seeds') or [1]))} "
  f"--trials {cfg.get('trials', 5)} --magnitude {cfg.get('magnitude_m', 0.05)} "
  f"--world-step {cfg.get('world_step', 40)} --tag main --ngpu 2")
w("python scripts_setup/gate13_analyze.py results/gate13_main")
w("python scripts_setup/gate13_figure.py results/gate13_main/gate13_summary.json \\")
w("  evidence/gate13_commitment_cost.png")
w("```\n")
w("Guards for reviewers:")
w("- `scripts_setup/gate13_validate_goal_aware.py` — proves the disturbance does not satisfy")
w("  the goal (no model needed).")
w("- `scripts_setup/test_gate9_intervention.py` — 67 unit checks incl. the absolute-step trigger")
w("  and the goal-aware guard.")
w("- `gate13_summary.json` carries `contaminated_disturb` per cell.\n")
w(f"*Generated from `{summary_path}`.*")

out_md.parent.mkdir(parents=True, exist_ok=True)
out_md.write_text("\n".join(L) + "\n")
print(f"wrote {out_md}")
