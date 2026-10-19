"""Gate 14G figure: success falls monotonically while the corrective response saturates.

Two panels sharing the x axis (displacement magnitude, mm):
  A - success rate with Wilson intervals, per-episode counts printed
  B - how far the re-planned chunk moves (mean and max |delta|), per magnitude
The point of the pair is the contrast: the outcome keeps degrading past the
point where the policy has stopped responding harder.
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import rankdata

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(HERE, "results", "gate14g_response.json")
OUT = os.path.join(HERE, "evidence", "gate14g_magnitude")


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def main():
    rows = json.load(open(RES))
    mm = np.array([r["magnitude_m"] for r in rows]) * 1000.0
    succ = np.array([r["success"] for r in rows])
    n = np.array([r["n"] for r in rows])
    dmean = np.array([r["chunk_delta_mean"] for r in rows])
    dmax = np.array([r["chunk_delta_max"] for r in rows])
    lo = np.array([wilson(k, m)[0] for k, m in zip(succ, n)])
    hi = np.array([wilson(k, m)[1] for k, m in zip(succ, n)])
    # computed, not typed: a hardcoded -1.000 stops being true the moment one
    # episode at the largest magnitude succeeds
    rho = float(np.corrcoef(rankdata(mm), rankdata(succ / n))[0, 1])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.4))

    # Wilson bounds can land a hair on the wrong side of the point estimate at
    # k=0 and k=n; clip so yerr is never negative.
    p = succ / n
    yerr = np.vstack([np.maximum(0.0, p - lo), np.maximum(0.0, hi - p)])
    ax1.errorbar(mm, p, yerr=yerr, fmt="o-",
                 color="#c0392b", capsize=4, lw=1.8, ms=7, zorder=3)
    for x, k, m, h in zip(mm, succ, n, hi):
        ax1.annotate(f"{k}/{m}", (x, h), textcoords="offset points",
                     xytext=(0, 6), ha="center", va="bottom", fontsize=9,
                     bbox=dict(boxstyle="round,pad=0.15", fc="white",
                               ec="none", alpha=0.85))
    ax1.set_xscale("log")
    ax1.set_xticks(mm)
    ax1.set_xticklabels([f"{v:g}" for v in mm])
    ax1.set_xlabel("displacement magnitude (mm, log scale)")
    ax1.set_ylabel("success rate")
    ax1.set_ylim(-0.06, 1.12)
    ax1.set_title("A. Single strike, zero stale actions: success falls\n"
                  f"({' -> '.join(f'{s}/{n}' for s, n in zip(succ, n))}, "
                  f"Spearman rho = {rho:.3f})", fontsize=10)
    ax1.grid(alpha=0.3, zorder=0)

    ax2.plot(mm, dmean, "o-", color="#1f6fb2", lw=1.8, ms=7, label="mean |delta|",
             zorder=3)
    ax2.plot(mm, dmax, "s--", color="#7fb3d5", lw=1.2, ms=5, label="max |delta|")
    # per-episode values: a mean with no spread invites over-reading
    for i, r in enumerate(rows):
        per = r.get("chunk_delta_per_episode") or []
        jit = np.linspace(-0.035, 0.035, len(per)) if len(per) > 1 else [0.0]
        ax2.scatter(np.full(len(per), mm[i]) * (1 + np.array(jit)),
                    per, s=16, color="#1f6fb2", alpha=0.35, zorder=2,
                    label="per-episode" if i == 0 else None)
    ax2.set_xscale("log")
    ax2.set_xticks(mm)
    ax2.set_xticklabels([f"{v:g}" for v in mm])
    ax2.set_xlabel("displacement magnitude (mm, log scale)")
    ax2.set_ylabel("change in planned chunk\n(normalized action units)")
    # Sublinear growth, quantified: the log-log slope is the exponent. At n=6 this
    # read as a plateau after 5 mm; at n=9 the 20 mm dip is noise and the honest
    # statement is a power law, not a plateau.
    slope = float(np.polyfit(np.log(mm), np.log(dmean), 1)[0])
    ratio = dmean[-1] / dmean[0]
    ax2.set_title(f"B. The corrective response grows SUBLINEARLY:\n"
                  f"{mm[-1] / mm[0]:.0f}x displacement -> {ratio:.2f}x response "
                  f"(response ~ m^{slope:.2f})", fontsize=10)
    ax2.legend(fontsize=9, framealpha=0.9)
    ax2.grid(alpha=0.3)
    ax2.set_ylim(0, max(dmax) * 1.18)

    nmax = max(n)
    seeds = sorted({s for r in rows for s in (r.get("seeds") or [])})
    seed_s = ",".join(str(s) for s in seeds) if seeds else "?"
    fig.suptitle("Gate 14G: success collapses while the corrective response grows "
                 "only sublinearly\n"
                 "(libero_object:0, H=10, one grasp-relative strike, "
                 f"n={nmax} episodes per magnitude, seeds {seed_s})", fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    for ext in ("png", "pdf"):
        fig.savefig(f"{OUT}.{ext}", dpi=170)
    print(f"wrote {OUT}.png")


if __name__ == "__main__":
    main()
