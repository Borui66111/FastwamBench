#!/usr/bin/env python
"""[fastbench] Gate 13 PSNR figure: predicted-future fidelity vs commitment horizon.

The world-model signal: PSNR between the model's predicted future video and what
actually happened. Two effects are shown:
  (1) control PSNR falls as H grows (prediction drifts over a longer commitment)
  (2) a mid-chunk world change costs much more PSNR at a long horizon

Usage: gate13_figure_psnr.py results/gate13_psnr/gate13_summary.json out.png
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sp = Path(sys.argv[1] if len(sys.argv) > 1 else "results/gate13_psnr/gate13_summary.json")
out = Path(sys.argv[2] if len(sys.argv) > 2 else "evidence/gate13_psnr.png")

with open(sp) as fh:
    s = json.load(fh)
p = s.get("_pooled") or {}
hs = sorted((int(h) for h in p), key=int)
if not hs:
    raise SystemExit("no pooled rows in summary")

ctl = [p[str(h)].get("psnr_control") for h in hs]
dis = [p[str(h)].get("psnr_disturb") for h in hs]
drop = [p[str(h)].get("psnr_drop") for h in hs]

# raw per-episode values, so n=2 is visible instead of hidden behind a mean
import glob
raw = {}
for rp in glob.glob(str(sp.parent / "*" / "H*" / "*" / "records.jsonl")):
    h = rp.split("/H")[-1].split("/")[0]
    arm = rp.split("/")[-2].split("_")[0]
    vals = []
    for line in open(rp):
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("event") == "episode_end" and r.get("episode_mean_psnr"):
            vals.append(float(r["episode_mean_psnr"]))
    if vals:
        raw.setdefault((h, arm), []).extend(vals)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 3.8))
x = range(len(hs))
w = 0.36
ax1.bar([i - w / 2 for i in x], ctl, w, label="control", color="#4C72B0")
ax1.bar([i + w / 2 for i in x], dis, w, label="disturbed", color="#C44E52")
ax1.set_xticks(list(x))
ax1.set_xticklabels([f"H={h}" for h in hs])
ax1.set_ylabel("predicted-future vs reality PSNR (dB)")
ax1.set_title("(A) prediction fidelity falls with H;\ndisturbance hurts more at H=10 (n=2/cell, indicative)", fontsize=9.5)
ax1.legend(fontsize=8)
ax1.grid(alpha=0.3, axis="y")
for i, (c, d) in enumerate(zip(ctl, dis)):
    if c is not None:
        ax1.text(i - w / 2, c + 0.3, f"{c:.1f}", ha="center", fontsize=7)
    if d is not None:
        ax1.text(i + w / 2, d + 0.3, f"{d:.1f}", ha="center", fontsize=7)
# individual episodes (n is small; show them rather than hiding behind the mean)
for i, h in enumerate(hs):
    for off, arm, col in ((-w / 2, "control", "k"), (w / 2, "disturb", "k")):
        vals = raw.get((str(h), arm)) or []
        ax1.scatter([i + off] * len(vals), vals, s=14, color=col, zorder=5, alpha=0.75)
_note = "/".join(sorted({str(len(v)) for v in raw.values()})) if raw else "?"
ax1.text(0.02, 0.03, f"dots = individual episodes (n={_note}/cell)",
         transform=ax1.transAxes, fontsize=7, style="italic")

ax2.bar([f"H={h}" for h in hs], drop, color="#DD8452", width=0.5)
ax2.set_ylabel("PSNR drop from the disturbance (dB)")
ax2.set_title("(B) drop is ~5x larger at H=10\n(n=2/cell; paired episodes shown)", fontsize=9.5)
ax2.grid(alpha=0.3, axis="y")
for i, d in enumerate(drop):
    if d is not None:
        ax2.text(i, d + 0.03, f"{d:+.2f}", ha="center", fontsize=8)
# paired per-episode drops, so the reader sees this is 2 episodes not 200
for i, h in enumerate(hs):
    _c = raw.get((str(h), "control")) or []
    _d = raw.get((str(h), "disturb")) or []
    _pairs = [a - b for a, b in zip(_c, _d)]
    if _pairs:
        ax2.scatter([i] * len(_pairs), _pairs, s=16, color="k", zorder=5, alpha=0.75)

fig.suptitle("Gate 13 — Future-Reality Divergence measured on the world model "
             "(visualize_future_video=true)", fontsize=10)
fig.tight_layout()
out.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out, dpi=160)
fig.savefig(out.with_suffix(".pdf"))
print(f"wrote {out} and {out.with_suffix('.pdf')}")
