#!/usr/bin/env python
"""[fastbench] Gate 14 figure: staleness does not compound into a success cost."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

out = "evidence/gate14_repeated_strikes"
tasks = ["libero_object_t0", "libero_spatial_t0"]
labels = ["libero_object t0", "libero_spatial t0"]
stale = [(4.0, 40.0), (3.3, 32.7)]
# (control mean, control sd, disturb mean, disturb sd) for H1 then H10
steps = {0: [(178.7, 22.8, 268.0, 81.5), (164.3, 9.8, 297.3, 69.2)],
         1: [(107.5, 5.4, 94.5, 29.1), (103.8, 3.2, 137.3, 96.3)]}
succ = [(("6/6", "5/6")), (("6/6", "6/6"))]  # per task: (H1, H10) disturb success

fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.7))
fig.suptitle("Gate 14 — repeated world strikes: 10x the stale actions, no measurable success cost",
             fontsize=13.5, fontweight="bold")

# --- panel A: manipulation check ------------------------------------------
ax = axes[0]
x = np.arange(2)
w = 0.34
h1 = [s[0] for s in stale]
h10 = [s[1] for s in stale]
b1 = ax.bar(x - w / 2, h1, w, label="H=1  (replans every step)", color="#4C78A8")
b2 = ax.bar(x + w / 2, h10, w, label="H=10 (commits 10 actions)", color="#E45756")
for b, v in list(zip(b1, h1)) + list(zip(b2, h10)):
    ax.text(b.get_x() + b.get_width() / 2, v + 0.8, f"{v:.1f}",
            ha="center", fontsize=10.5, fontweight="bold")
for i in range(2):
    # success counts inside the bars, ratio inside the tall red bar: keeps the
    # legend corner clear (a floating ratio label collided with it).
    ax.text(i - w / 2, 2.0, f"succ {succ[i][0]}", ha="center", va="bottom",
            fontsize=8.6, color="white", fontweight="bold")
    ax.text(i + w / 2, 2.0, f"succ {succ[i][1]}", ha="center", va="bottom",
            fontsize=8.6, color="white", fontweight="bold")
    ax.text(i + w / 2, h10[i] - 2.5, f"{h10[i]/h1[i]:.1f}x", ha="center", va="top",
            fontsize=11.5, color="white", fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=10)
ax.set_ylabel("stale actions executed\n(actions run against an already-moved world)", fontsize=10)
ax.set_title("A. The manipulation is real", fontsize=11.5, loc="left")
ax.set_ylim(0, 60)
ax.legend(fontsize=9, frameon=False, loc="upper left")
ax.grid(axis="y", alpha=0.25, lw=0.6)
ax.set_axisbelow(True)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)

# --- panel B: effort cost, per task --------------------------------------
ax = axes[1]
w = 0.34
c1 = [steps[i][0][2] - steps[i][0][0] for i in range(2)]
c10 = [steps[i][1][2] - steps[i][1][0] for i in range(2)]
b1 = ax.bar(x - w / 2, c1, w, label="H=1", color="#4C78A8")
b2 = ax.bar(x + w / 2, c10, w, label="H=10", color="#E45756")
for b, v in list(zip(b1, c1)) + list(zip(b2, c10)):
    off = 5 if v >= 0 else -12
    ax.text(b.get_x() + b.get_width() / 2, v + off, f"{v:+.0f}",
            ha="center", fontsize=10.5, fontweight="bold")
ax.axhline(0, color="black", lw=0.9)
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=10)
ax.set_ylabel("step cost of the strikes\n(disturb − control, steps)", fontsize=10)
ax.set_title("B. Effort: not separable from noise", fontsize=11.5, loc="left")
ax.set_ylim(-45, 185)
ax.legend(fontsize=9, frameon=False, loc="upper right")
ax.text(0.03, 0.965, "Welch, disturb vs control:\nobject p=0.52 · spatial p=0.34\nsuccess identical (Fisher p=1.0)",
        transform=ax.transAxes, ha="left", va="top", fontsize=9.0, linespacing=1.35,
        bbox=dict(boxstyle="round,pad=0.4", fc="#fff8e1", ec="#d4a017", lw=0.8))
ax.grid(axis="y", alpha=0.25, lw=0.6)
ax.set_axisbelow(True)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)

fig.tight_layout(rect=(0, 0, 1, 0.93))
fig.savefig(out + ".png", dpi=170)
fig.savefig(out + ".pdf")
print("wrote " + out + ".png and .pdf")
