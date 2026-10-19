import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

rows = json.load(open("results/gate14i_release.json"))
ok = [r for r in rows if r["success"]]
no = [r for r in rows if not r["success"]]
mags = sorted({r["magnitude_m"] for r in rows})

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.3))

def strip(ax, key, ylabel, title):
    for i, m in enumerate(mags):
        for grp, col, off, lab in ((ok, "#2e7d32", -0.13, "success"),
                                   (no, "#c0392b", 0.13, "failure")):
            vals = [r[key] for r in grp
                    if r["magnitude_m"] == m and r.get(key) is not None
                    and np.isfinite(r[key])]
            if not vals:
                continue
            x = i + off + np.random.RandomState(0).uniform(-0.04, 0.04, len(vals))
            ax.scatter(x, vals, s=26, color=col, alpha=0.75, zorder=3)
            ax.plot([i + off - 0.09, i + off + 0.09],
                    [np.mean(vals)] * 2, color=col, lw=2.4, zorder=4)
    ax.set_xticks(range(len(mags)))
    ax.set_xticklabels([f"{m*1000:.0f}" for m in mags])
    ax.set_xlabel("strike magnitude (mm)")
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=10)
    # explicit proxies: labelling inside the loop left the failure group out of
    # the legend entirely whenever the first magnitude had no failures (2 mm).
    ax.legend(handles=[
        Line2D([], [], marker="o", ls="", color="#2e7d32", label="success"),
        Line2D([], [], marker="o", ls="", color="#c0392b", label="failure"),
    ], fontsize=8, framealpha=0.9)

def med(grp, key):
    # NaN (not None) is what "never separated" serialises as, so filter on
    # finiteness -- `is not None` alone let NaN through and titled the panel "nan".
    v = [r[key] for r in grp
         if r.get(key) is not None and np.isfinite(r[key])]
    return float(np.median(v)) if v else float("nan")

strip(ax1, "gripper_open_frac", "fraction of post-strike steps\ncommanding the gripper OPEN",
      "A. Failures command the gripper open far more\n"
      f"often (median {med(no,'gripper_open_frac'):.2f} vs "
      f"{med(ok,'gripper_open_frac'):.2f}), not always")
ax1.set_ylim(-0.05, 1.05)

strip(ax2, "release_z", "object height when it leaves the gripper (m)",
      "B. Failures that separate at all separate higher\n"
      f"(median {med(no,'release_z'):.2f} vs {med(ok,'release_z'):.2f} m)")
ax2.set_ylim(0.07, 0.27)

fig.suptitle("Gate 14-I: the release is commanded at the wrong height, before the descent\n"
             "(libero_object:0, H=10, one grasp-relative strike, zero stale actions, "
             "n=9 per magnitude)", fontsize=9)
fig.tight_layout(rect=(0, 0, 1, 0.90))
fig.text(0.5, 0.015, "horizontal bars are group means; each dot is one episode",
         ha="center", fontsize=8, color="0.35")
fig.savefig("evidence/gate14i_release.png", dpi=150)
fig.savefig("evidence/gate14i_release.pdf")
print("wrote evidence/gate14i_release.png")
