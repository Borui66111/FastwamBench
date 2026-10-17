#!/usr/bin/env python
"""[fastbench] Gate 13 figure: what a mid-chunk world change actually costs.

Three panels, because success rate alone is misleading here:
  (A) task success vs commitment horizon H, control vs disturbed  (+/- 1 SEM)
  (B) stale actions actually executed vs H (mechanism: identity y = H)
  (C) divergence accumulated DURING the stale window vs H (mechanism: monotone)

Usage: gate13_figure.py [summary.json] [out.png]
"""
import json
import math
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
_pooled = summary.get("_pooled") or {}
ph = sorted(int(h) for h in _pooled) if _pooled else []

fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15, 4.4))

# ---- (A) success: per-task thin, pooled thick, SEM whiskers on the pooled arm
for i, (task, by_h) in enumerate(tasks):
    hs = numeric_hs(by_h)
    col = f"C{i}"
    ax1.plot(hs, [by_h[str(h)]["control_rate"] for h in hs], "o--", color=col, alpha=0.45,
             lw=1, label=f"{task} control")
    ax1.plot(hs, [by_h[str(h)]["disturb_rate"] for h in hs], "s-", color=col, alpha=0.45,
             lw=1, label=f"{task} disturbed")
if _pooled:
    ph = sorted(int(h) for h in _pooled)
    ax1.plot(ph, [_pooled[str(h)]["control_rate"] for h in ph], "k--", lw=2, label="POOLED control")
    _r = [_pooled[str(h)]["disturb_rate"] for h in ph]
    ax1.plot(ph, _r, "k-", lw=2.5, label="POOLED disturbed")
    _n = [_pooled[str(h)].get("n_disturb") or 1 for h in ph]
    _se = [math.sqrt(max(p * (1 - p), 1e-9) / max(n, 1)) for p, n in zip(_r, _n)]
    ax1.errorbar(ph, _r, yerr=_se, fmt="none", ecolor="k", capsize=3, lw=1.2, zorder=6)
    ax1.set_ylim(-0.05, 1.18)
ax1.set_xticks(sorted({h for _, v in tasks for h in numeric_hs(v)} | set(ph)))
ax1.set_xlabel("commitment horizon H (actions per replan)")
ax1.set_ylabel("task success rate  (whiskers = ±1 SEM)")
ax1.set_title("A. success does not fall monotonically with H", fontsize=9.5)
ax1.grid(alpha=0.3)
ax1.legend(fontsize=7, loc="center right")

# ---- (B) mechanism: stale actions == H exactly (identity drawn on top, visible)
hmax = max(max(numeric_hs(v)) for _, v in tasks)
ax2.plot([0.6, hmax + 0.4], [0.6, hmax + 0.4], color="0.45", ls=(0, (2, 2)), lw=1.6,
         zorder=5, label="identity (stale == H)")
if _pooled:
    ax2.plot(ph, [_pooled[str(h)].get("stale_disturb", 0) for h in ph], "ko-", lw=2, ms=6,
             zorder=4, label="POOLED stale")
ax2.set_xlabel("commitment horizon H")
ax2.set_ylabel("stale actions executed after the world change")
ax2.set_title("(B) mechanism: the stale window is exactly H")
ax2.set_xticks(sorted({h for _, v in tasks for h in numeric_hs(v)} | set(ph)))
ax2.grid(alpha=0.3)
ax2.legend(fontsize=7, loc="upper left")

# ---- (C) fixed-lag divergence: the fair comparison across H -------------------
# The max-over-stale-window metric grows with H purely because the window is H long.
# Plotting the SAME lag after the intervention for every H removes that artifact.
_LAGK = (1, 2, 3, 5)
for i, (task, by_h) in enumerate(tasks):
    hs = numeric_hs(by_h)
    for _k in _LAGK:
        _v = [(by_h[str(h)].get("lag_divergence_disturb") or {}).get(str(_k)) for h in hs]
        if all(x is not None for x in _v):
            ax3.plot(hs, _v, "-", color=f"C{i}", alpha=0.35 + 0.12 * _LAGK.index(_k),
                     lw=1.3, ms=4, marker="o",
                     label=f"{task} k={_k}")
ax3.set_xlabel("commitment horizon H")
ax3.set_ylabel("eef→object divergence at fixed lag k (m)")
ax3.set_title("(C) at a FIXED lag, divergence does not grow with H", fontsize=9.5)
ax3.set_xticks(sorted({h for _, v in tasks for h in numeric_hs(v)} | set(ph)))
ax3.grid(alpha=0.3)
ax3.legend(fontsize=6, loc="best", framealpha=0.92, ncol=2)

cfg = summary.get("_config") or {}
_sub = ""
if cfg.get("world_step") is not None:
    _sub = (f"\n[disturbance {cfg.get('magnitude_m')} m at step {cfg.get('world_step')}; "
            f"H={cfg.get('horizons')}; {cfg.get('trials')} trials/task/H]")
fig.suptitle("Gate 13 — a world change mid-chunk: exactly H stale actions execute (B), "
             "the task cost is not monotone in H (A), and divergence does not grow with H (C)" + _sub,
             fontsize=10)
fig.tight_layout()
out_png.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out_png, dpi=160)
fig.savefig(out_png.with_suffix(".pdf"))
print(f"wrote {out_png} and {out_png.with_suffix('.pdf')}")
