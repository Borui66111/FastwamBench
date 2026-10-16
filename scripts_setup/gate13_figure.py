#!/usr/bin/env python
"""[fastbench] Gate 13 figure: cost of world-model commitment vs replan horizon.

Reads results/gate13_<tag>/gate13_summary.json and writes a two-panel figure:
  (A) task success vs commitment horizon H, control vs disturbed
  (B) stale actions actually executed vs H (mechanism check: should be ~identity)

Usage: gate13_figure.py [summary.json] [out.png]
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path("/data1/liborui/fastwam_bench")
summary_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "results" / "gate13" / "gate13_summary.json"
out_png = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "evidence" / "gate13_commitment_cost.png"

with open(summary_path) as fh:
    summary = json.load(fh)


def numeric_hs(by_h):
    """Horizon keys are JSON strings; ignore metadata keys like '_config'."""
    out = []
    for k in by_h:
        try:
            out.append(int(k))
        except (TypeError, ValueError):
            continue
    return sorted(out)


tasks = [(k, v) for k, v in sorted(summary.items()) if numeric_hs(v)]
if not tasks:
    raise SystemExit(f"no horizon data in {summary_path}")

hmax = max(max(numeric_hs(v)) for _, v in tasks)
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
for task, by_h in tasks:
    hs = numeric_hs(by_h)
    ctrl = [by_h[str(h)]["control_rate"] for h in hs]
    dist = [by_h[str(h)]["disturb_rate"] for h in hs]
    stale = [by_h[str(h)].get("stale_disturb", 0) for h in hs]
    ax1.plot(hs, ctrl, "o--", label=f"{task} control")
    ax1.plot(hs, dist, "s-", label=f"{task} disturbed")
    ax2.plot(hs, stale, "^-", label=f"{task} stale executed")

# pooled headline curve (thick black), if the analyzer produced it
_pooled = summary.get("_pooled") or {}
if _pooled:
    ph = sorted(int(h) for h in _pooled)
    ax1.plot(ph, [_pooled[str(h)]["control_rate"] for h in ph], "k--", lw=2, label="POOLED control")
    ax1.plot(ph, [_pooled[str(h)]["disturb_rate"] for h in ph], "k-", lw=2.5, label="POOLED disturbed")
    ax2.plot(ph, [_pooled[str(h)].get("stale_disturb", 0) for h in ph], "k-", lw=2, label="POOLED stale")

ax1.set_xlabel("commitment horizon H (actions per replan)")
ax1.set_ylabel("task success rate")
ax1.set_ylim(-0.05, 1.05)
ax1.set_title("(A) Success collapses as the model commits longer")
ax1.grid(alpha=0.3)
ax1.legend(fontsize=7)

ax2.plot([1, hmax], [1, hmax], "k:", lw=1, label="identity (stale == H)")
ax2.set_xlabel("commitment horizon H")
ax2.set_ylabel("stale actions executed after the world change")
ax2.set_title("(B) Mechanism: stale actions scale with H")
ax2.grid(alpha=0.3)
ax2.legend(fontsize=7)

cfg = summary.get("_config") or {}
_sub = ""
if cfg.get("world_step") is not None:
    _sub = (f"\n[disturbance {cfg.get('magnitude_m')} m at step {cfg.get('world_step')}; "
            f"H={cfg.get('horizons')}; {cfg.get('trials')} trials/task/H]")
fig.suptitle("Gate 13 — a world change mid-chunk costs more the longer the model commits" + _sub,
             fontsize=10)
fig.tight_layout()
out_png.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out_png, dpi=160)
fig.savefig(out_png.with_suffix(".pdf"))
print(f"wrote {out_png} and {out_png.with_suffix('.pdf')}")
