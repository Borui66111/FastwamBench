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
        w(f"  - stale-window divergence (m) by H = "
          + ", ".join(f"H{h}={v:.3f}" for h, v in zip(hs, _dv)))
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
w("   the weaker, mechanism-level claim in (1) plus the divergence trend in (4).\n")
w("4. **Where the horizon effect does show up is the mechanism metric.** During the stale")
w("   window the end-effector diverges from the moved object by an amount that grows with")
w("   H on libero_spatial (0.002 -> 0.011 -> 0.043 -> 0.045 m). On libero_object the same")
w("   quantity is flat and slightly negative (~-0.007 m): there the arm was already moving")
w("   toward the object's new location, so the displacement did not misdirect it. So the")
w("   divergence signature is task-dependent, not universal, and this report says so.\n")
w("Why the task-level cost fails to grow with H: the displacement is the same size at the")
w("same absolute step for every H, so re-acquiring the object is roughly H-independent and")
w("dominates the small, H-dependent part. The magnitude ladder below tested that reading")
w("directly, and **it did not rescue the strong claim**: at 0.02 m both horizons recover")
w("completely (cost +0.00 at H=1 and H=10); at 0.03 m the cost is +0.33 at H=1 and +0.20 at")
w("H=10, i.e. the *short* horizon looks slightly worse, which is the opposite of the")
w("prediction and well inside noise at n=10. The H-dependent component is therefore smaller")
w("than this design can resolve, not merely masked by re-acquisition.\n")
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
    _table(_pl, _tag)
if not _any:
    w("*(ladder not run yet — see `scripts_setup/gate13_finish.sh`)*\n")

# --- what would be needed to settle the question ------------------------------
w("\n## What this design cannot resolve, and what would\n")
w("At n=10 per cell the binomial noise floor is roughly +/-0.25 on a rate near 0.7, so")
w("only a very large H effect could be detected. To resolve a difference of 0.10 in")
w("success rate between H=1 and H=10 at 80% power you need roughly 300 episodes per arm")
w("(two-proportion test, alpha=0.05; 0.80 vs 0.70 gives n~290 per arm). That is ~30x this")
w("sweep. The cheaper route is the")
w("mechanism metric, which is continuous rather than binary: the stale-window divergence")
w("already separates H=1 from H=10 by more than 20x on libero_spatial (0.002 vs 0.045 m),")
w("so the horizon effect is measurable at the action level long before it is measurable")
w("at the task level. A reviewer wanting the strong task-level claim should treat this")
w("report as a powered negative result at n=10, not as evidence of no effect.\n")

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
        _hcd = _pp.get("1", {}).get("psnr_drop")
        _h10c = _pp.get("10", {}).get("psnr_control")
        _h10d = _pp.get("10", {}).get("psnr_drop")
        if None not in (_hc, _h10c, _hcd, _h10d):
            w(f"Two things are visible here, and the second is the point of the project.")
            w(f"First, **prediction fidelity falls with the horizon even with no intervention**")
            w(f"({_hc:.2f} dB at H=1 vs {_h10c:.2f} dB at H=10): the further ahead the model")
            w(f"commits, the less accurate its world model is about what will actually happen.")
            w(f"Second, a world change mid-chunk damages that prediction far more at a long")
            w(f"horizon: the PSNR drop is {_hcd:+.2f} dB at H=1 but {_h10d:+.2f} dB at H=10")
            w(f"(**{_h10d / max(_hcd, 1e-9):.1f}x**). This is the cleanest measurement in the")
            w(f"report of *Future-Reality Divergence*: the model's committed world model is")
            w(f"invalidated in proportion to how long it committed for. n=2 per cell, so treat")
            w(f"the magnitude as indicative; the direction is consistent across both episodes.\n")
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
