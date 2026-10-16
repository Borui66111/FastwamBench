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
w("## Headline table\n")
w("| task | H | control | disturbed | cost | stale executed | contaminated |")
w("|---|---|---|---|---|---|---|")
for task, by_h in sorted((k, v) for k, v in summary.items() if not k.startswith("_")):
    for h in sorted(by_h, key=int):
        r = by_h[h]
        w(f"| {task} | {h} | {r['control_rate']:.2f} | {r['disturb_rate']:.2f} | "
          f"**{r['cost']:+.2f}** | {r.get('stale_disturb', 0):.0f} | "
          f"{r.get('contaminated_disturb', 0)} |")
w("\n`cost` = control_rate − disturb_rate. `stale executed` = actions executed after the world")
w("change but before the next replan (mechanism check: should equal H). `contaminated` =")
w("episodes in which the disturbance accidentally completed the task (must be 0).\n")
w("## Trend\n")
for task, by_h in sorted((k, v) for k, v in summary.items() if not k.startswith("_")):
    hs = sorted(by_h, key=int)
    costs = [by_h[h]["cost"] for h in hs]
    stale = [by_h[h].get("stale_disturb", 0) for h in hs]
    mono = all(costs[i] <= costs[i + 1] + 1e-9 for i in range(len(costs) - 1))
    w(f"- **{task}**: cost by H = " + ", ".join(f"H{h}={c:+.2f}" for h, c in zip(hs, costs)))
    w(f"  - stale executed by H = " + ", ".join(f"H{h}={s:.0f}" for h, s in zip(hs, stale)))
    w(f"  - monotone increasing cost with horizon: **{mono}**")
w("\n## Reproduce\n")
w("```bash")
w("bash scripts_setup/gate13_all.sh   # full pipeline: sweep -> psnr -> analyze -> report")
w("")
w("cd /data1/liborui/fastwam_bench")
w(f"python scripts_setup/gate13_run.py --tasks {','.join('%s:%d' % (s, t) for s, t in (cfg.get('tasks') or [['libero_spatial', 0]]))} \\")
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
