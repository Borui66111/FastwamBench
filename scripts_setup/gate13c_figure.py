"""Gate 13C figure: the same strikes, moved from the approach into the carry.

Left:  object-task success, approach vs carry, at H=1 and H=10.
Right: stale actions in the same four cells -- identical by construction, which is
       the point: the manipulation is the same, only the timing changed.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# libero_object t0, magnitude 0.01 m, 4 strikes. n=6 per cell.
# approach = results/gate13_repeat_sub, carry = results/gate13_repeat_carry_full
succ = {
    "approach": {"H1": (5, 6), "H10": (6, 6)},
    "carry": {"H1": (2, 6), "H10": (1, 6)},
}
stale = {"approach": {"H1": 4.0, "H10": 40.0}, "carry": {"H1": 4.0, "H10": 40.0}}

fig, (ax, bx) = plt.subplots(1, 2, figsize=(11.0, 4.6))
x = np.arange(2)
w = 0.34
C_H1, C_H10 = "#4C78A8", "#E45756"

# ---- Panel A: success rate -------------------------------------------------
for i, (regime, colour) in enumerate([("H1", C_H1), ("H10", C_H10)]):
    vals = [succ[r][regime][0] / succ[r][regime][1] for r in ("approach", "carry")]
    bars = ax.bar(x + (i - 0.5) * w, vals, w, color=colour,
                  label=f"replan horizon H={regime[1:]}")
    for b, r in zip(bars, ("approach", "carry")):
        k, n = succ[r][regime]
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.025,
                f"{k}/{n}", ha="center", fontsize=9.5, fontweight="bold")

ax.set_xticks(x)
ax.set_xticklabels(["strikes during\napproach", "strikes during\ncarry"], fontsize=10)
ax.set_ylabel("task success rate", fontsize=10)
ax.set_ylim(0, 1.12)
ax.set_title("A. When the strike lands decides whether it costs anything",
             fontsize=11, loc="left")
# legend upper-right: the carry bars are short, so that corner is empty
ax.legend(frameon=False, fontsize=9, loc="upper right")
ax.grid(axis="y", alpha=0.25)
ax.set_axisbelow(True)

# ---- Panel B: stale actions ------------------------------------------------
for i, (regime, colour) in enumerate([("H1", C_H1), ("H10", C_H10)]):
    vals = [stale[r][regime] for r in ("approach", "carry")]
    bars = bx.bar(x + (i - 0.5) * w, vals, w, color=colour,
                  label=f"replan horizon H={regime[1:]}")
    for b, v in zip(bars, vals):
        bx.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.0, f"{v:.0f}",
                ha="center", fontsize=9.5, fontweight="bold")

bx.set_xticks(x)
bx.set_xticklabels(["strikes during\napproach", "strikes during\ncarry"], fontsize=10)
bx.set_ylabel("stale actions executed (mean/episode)", fontsize=10)
bx.set_ylim(0, 50)
bx.set_title("B. The manipulation is identical in both regimes", fontsize=11, loc="left")
bx.grid(axis="y", alpha=0.25)
bx.set_axisbelow(True)
bx.legend(frameon=False, fontsize=9, loc="upper right")

# Put the statistics below both panels rather than inside panel B, where the box
# crowded the "40" label and mixed a success quantity into a stale-action axis.
fig.text(0.5, -0.035,
         "libero_object t0, 0.01 m, n=6 per cell.   "
         "For strikes during CARRY, disturbed vs its own control (control = 6/6 in all four "
         "cells):   H=1  2/6 (p=0.061)    H=10  1/6 (p=0.015).   "
         "Horizon contrast, disturbed H=1 vs H=10: 2/6 vs 1/6, Fisher p=1.000.",
         ha="center", fontsize=8.8, color="#333333")

fig.suptitle("Gate 13C - the cost of a stale action depends on whether it was load-bearing, "
             "not on how many there were", fontsize=11.5, y=1.0)
fig.tight_layout(rect=(0, 0, 1, 0.94))
for ext in ("png", "pdf"):
    fig.savefig(f"evidence/gate13c_carry_phase.{ext}", dpi=200, bbox_inches="tight")
print("wrote evidence/gate13c_carry_phase.png and .pdf")
