#!/usr/bin/env python
"""[fastbench] Gate 13 final figure: world-model damage, clip-isolated.

Panel A: prediction fidelity vs lookahead, control vs disturbed (both horizons).
Panel B: the damage (control - disturb) vs lookahead, per horizon.

Frame index k maps to a lookahead of k * RATIO env steps (RATIO=4).
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RATIO = 4
src = Path(sys.argv[1] if len(sys.argv) > 1 else
           "results/gate13_psnr_clip/psnr_clip_summary.json")
out = Path(sys.argv[2] if len(sys.argv) > 2 else "evidence/gate13_worldmodel.png")
d = json.loads(src.read_text())

plt.rcParams.update({"font.size": 9})
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.6))

for h, col, mk in (("5", "#1f77b4", "o"), ("10", "#d62728", "s")):
    if h not in d:
        continue
    idx = sorted(int(k) for k in d[h])
    xs = [k * RATIO for k in idx]          # <-- lookahead in env steps, not frame index
    ctl = [d[h][str(k)]["control"] for k in idx]
    dis = [d[h][str(k)]["disturb"] for k in idx]
    ax1.plot(xs, ctl, mk + "-", color=col, lw=2, ms=6, label=f"H={h} control")
    ax1.plot(xs, dis, mk + "--", color=col, lw=2, ms=6, mfc="white",
             label=f"H={h} disturbed")
    for j, (x, c, dd) in enumerate(zip(xs, ctl, dis)):
        ax1.annotate(f"{c:.1f}", (x, c), textcoords="offset points", xytext=(0, 8),
                     ha="center", fontsize=7.5, color=col)
        # alternate the vertical offset so adjacent disturbed labels never collide
        ax1.annotate(f"{dd:.1f}", (x, dd), textcoords="offset points",
                     xytext=(0, -14 if j % 2 == 0 else -25),
                     ha="center", fontsize=7.5, color=col)
    # panel B: draw H=5 thick and pale underneath so exact overlap is still visible
    deltas = [d[h][str(k)]["delta"] for k in idx]
    if h == "5":
        ax2.plot(xs, deltas, "-", color="#1f77b4", lw=9, alpha=0.35,
                 solid_capstyle="round", label="H=5 (band)")
        ax2.plot(xs, deltas, "o", color="#1f77b4", ms=13, mfc="none", mew=1.6,
                 label="H=5 (edge)")
    else:
        ax2.plot(xs, deltas, "o-", color=col, lw=2, ms=7, label="H=10")
        for x, dv in zip(xs, deltas):
            ax2.annotate(f"{dv:+.2f}", (x, dv), textcoords="offset points",
                         xytext=(0, 10 if dv > -2 else -16), ha="center",
                         fontsize=8, color=col)

ax1.set_xlabel("lookahead after the world change (env steps)")
ax1.set_ylabel("PSNR of predicted future vs reality (dB)")
ax1.set_title("A. prediction fidelity collapses with lookahead;\nthe world change adds a large further loss", fontsize=9.5)
ax1.set_xticks([0, 4, 8])
ax1.set_xlim(-1.2, 9.2)
ax1.set_ylim(20.5, 42.5)
ax1.grid(alpha=0.3)
ax1.legend(fontsize=7.5, loc="upper right", framealpha=0.95)

ax2.axhline(0, color="0.35", lw=1, ls=":")
ax2.set_xlabel("lookahead after the world change (env steps)")
ax2.set_ylabel("control − disturbed (dB)")
ax2.set_title("B. damage is the same at H=5 and H=10\n(H=5 band is thick/pale; the lines coincide)", fontsize=9.5)
ax2.set_xticks([0, 4, 8])
ax2.set_xlim(-1.2, 9.2)
ax2.set_ylim(-5.6, 1.2)
ax2.grid(alpha=0.3)
ax2.legend(fontsize=8, loc="lower left")

fig.suptitle("Gate 13 — a mid-chunk world change invalidates the committed prediction, "
             "but no more so for a longer commitment\n"
             "libero_spatial t0 · 0.05 m displacement at step 40 · n=6/cell · "
             "the clip the change lands in is scored alone", fontsize=9)
fig.tight_layout(rect=(0, 0, 1, 0.93))
out.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out, dpi=170)
fig.savefig(out.with_suffix(".pdf"))
print(f"wrote {out} and {out.with_suffix('.pdf')}")
