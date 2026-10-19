"""Gate 14H figure: the object reaches the basket footprint but stalls above it.

Panel A - final object height vs strike magnitude, split by outcome, against the
          control placement band. The vertical failure grows; the horizontal one
          does not.
Panel B - minimum xy distance to the basket over the episode: the object gets to
          the basket at every magnitude, including where success is 0/6.

Reads results/gate14h_geometry.json (written by gate14h_geometry.py).
"""

import argparse
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

MAG = None  # magnitudes are read from each row; kept for backward compatibility


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="results/gate14h_geometry.json")
    ap.add_argument("--out", default="evidence/gate14h_geometry.png")
    args = ap.parse_args()

    data = json.load(open(args.json))
    # magnitude comes from the record itself, not from the directory name
    rows = [(round(r["magnitude_m"] * 1000), r) for r in data
            if r.get("magnitude_m") is not None]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.6))

    # control placement band: the z at which successful episodes settle
    ctl = [e["z_end"] for m, r in rows if m == 0 for e in r["episodes"]]
    if ctl:
        ax1.axhspan(min(ctl), max(ctl), color="#2e8b57", alpha=0.12, zorder=0,
                    label=f"control placement ({min(ctl):.3f}-{max(ctl):.3f} m)")

    for ok, colour, marker, lab in ((True, "#2e8b57", "o", "success"),
                                    (False, "#c0392b", "x", "failure")):
        xs, ys = [], []
        for m, r in rows:
            if m == 0:
                continue
            for e in r["episodes"]:
                if e["success"] == ok:
                    xs.append(m)
                    ys.append(e["z_end"])
        if xs:
            # jitter so overlapping episodes are countable
            rng = np.random.default_rng(0)
            ax1.scatter(np.array(xs) * (1 + rng.uniform(-0.05, 0.05, len(xs))),
                        ys, s=42, c=colour, marker=marker, zorder=3,
                        label=f"{lab} (n={len(xs)})")

    ax1.set_xscale("log")
    ax1.set_xticks([2, 5, 10, 20, 40])
    ax1.set_xticklabels(["2", "5", "10", "20", "40"])
    ax1.set_xlabel("strike magnitude (mm, log scale)")
    ax1.set_ylabel("final object height z (m)")
    ax1.set_title("A. Most failures stall ABOVE the basket,\nand the stall height "
                  "grows with the strike", fontsize=10)
    ax1.legend(fontsize=8, loc="upper left", framealpha=0.95)
    ax1.grid(alpha=0.3, zorder=0)

    # Panel B: log y. Two "lost far" episodes sit at 0.29 and 0.38 m; on a linear
    # axis pinned to the basket footprint they fall off the plot entirely, which
    # would hide the second failure mode rather than show it.
    for m, r in rows:
        if m == 0:
            continue
        d = [e["d_min"] for e in r["episodes"]]
        ax2.scatter([m] * len(d), d, s=34, c="#1f6fb2", alpha=0.75, zorder=3)
        ax2.annotate(f"{r['successes']}/{r['n']}", (m, 0.62),
                     xycoords=("data", "axes fraction"),
                     ha="center", va="center", fontsize=8.5,
                     bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none",
                               alpha=0.85))
    ax2.axhline(0.05, ls="--", lw=1.0, c="#888",
                label="0.05 m (inside basket footprint)")
    ax2.set_xscale("log")
    ax2.set_yscale("log")
    ax2.set_xticks([2, 5, 10, 20, 40])
    ax2.set_xticklabels(["2", "5", "10", "20", "40"])
    ax2.set_xlabel("strike magnitude (mm, log scale)")
    ax2.set_ylabel("min xy distance to basket (m, log scale)")
    ax2.set_title("B. The object usually reaches the basket footprint;\n"
                  "the exceptions are the 'lost far' episodes", fontsize=10)
    ax2.legend(fontsize=8, loc="lower left", framealpha=0.95)
    ax2.grid(alpha=0.3, zorder=0, which="both")
    ax2.set_ylim(0.0008, 0.75)

    # Metadata in the title is computed, never typed: a hardcoded "n=6, seeds 1-2"
    # survived one replication and contradicted the plotted 9/9 labels.
    nmax = max((r["n"] for _, r in rows), default=0)
    seeds = sorted({e["seed"] for _, r in rows for e in r["episodes"]})
    seed_s = ",".join(str(s) for s in seeds)
    fig.suptitle("Gate 14H: failures are mainly in the final placement, while the "
                 "approach usually\nreaches the basket footprint "
                 "(libero_object:0, H=10, one grasp-relative strike, zero stale "
                 f"actions, n={nmax} per magnitude, seeds {seed_s})", fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    fig.savefig(args.out, dpi=150)
    fig.savefig(args.out.replace(".png", ".pdf"))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
