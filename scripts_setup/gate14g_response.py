"""Gate 14G: does the policy's response scale with the displacement?

Pairs each zero-stale disturb episode with the control episode of the same
index (same seed/trial) and measures how far the action chunk at the strike
moves, against how often the episode still succeeds. That separates two
readings of the Gate 14E/F null:

  * magnitude problem  -> chunk response stays small even as the object is
    displaced further, i.e. the model under-reacts;
  * geometric problem  -> chunk response grows with displacement, but success
    stays low because the placement check is exact and ~1 cm is enough to miss.

Arm identity is read from the episode records (`zero_stale_strikes`), not from
the run tag: tags are cosmetic and the analyzer must not depend on them.

Usage:
    python scripts_setup/gate14g_response.py --ctl results/gate13_g14gctl \
        --runs results/gate13_g14g*  [--json out.json]
"""
import argparse
import glob
import json
import os

import numpy as np


def episodes(root):
    """[{episode, success, steps, strike_t, zero_stale}] for one run dir."""
    out = []
    for path in sorted(glob.glob(os.path.join(root, "**", "records.jsonl"),
                                 recursive=True)):
        strike_t, zs = None, 0
        for line in open(path):
            if '"intervention"' not in line and '"episode_end"' not in line:
                continue
            rec = json.loads(line)
            if rec.get("event") == "intervention" and strike_t is None:
                strike_t = int(rec["t"])
            elif rec.get("event") == "episode_end":
                out.append({
                    "episode": int(rec["episode"]),
                    "success": bool(rec["success"]),
                    "steps": int(rec["steps"]),
                    "strike_t": strike_t,
                    "zero_stale": int(rec.get("zero_stale_strikes") or 0),
                })
    return out


def chunks(path):
    """{(episode, t): chunk array} from a FASTBENCH_DUMP_CHUNK file."""
    out = {}
    if not os.path.exists(path):
        return out
    for line in open(path):
        rec = json.loads(line)
        out[(int(rec["episode"]), int(rec["t"]))] = np.asarray(rec["chunk"],
                                                             dtype=float)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ctl", required=True, help="control run dir (reference)")
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--dumpdir", default="/tmp")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    ctl_chunks = chunks(os.path.join(args.dumpdir,
                                     f"chunks_{os.path.basename(args.ctl)}.jsonl"))
    if not ctl_chunks:
        print(f"no control chunks for {args.ctl} -- was FASTBENCH_DUMP_CHUNK set?")
        return 1
    ctl_eps = episodes(args.ctl)
    print(f"control: {sum(e['success'] for e in ctl_eps)}/{len(ctl_eps)} success, "
          f"{len(ctl_chunks)} chunks dumped")

    rows = []
    for run in sorted(args.runs):
        if os.path.abspath(run) == os.path.abspath(args.ctl):
            continue
        tag = os.path.basename(run)
        with open(os.path.join(run, "run_config.json")) as f:
            mag = float(json.load(f)["magnitude_m"])
        eps = episodes(run)
        if not eps:
            print(f"{tag}: no episodes yet, skipped")
            continue
        run_chunks = chunks(os.path.join(args.dumpdir, f"chunks_{tag}.jsonl"))

        deltas = []
        for e in eps:
            if e["strike_t"] is None:
                continue
            key = (e["episode"], e["strike_t"])
            if key in run_chunks and key in ctl_chunks:
                deltas.append(float(np.abs(run_chunks[key]
                                           - ctl_chunks[key]).max()))
        succ = sum(e["success"] for e in eps)
        rows.append({
            "tag": tag,
            "magnitude_m": mag,
            "n": len(eps),
            "success": succ,
            "zero_stale_episodes": sum(1 for e in eps if e["zero_stale"] > 0),
            "paired": len(deltas),
            "chunk_delta_mean": float(np.mean(deltas)) if deltas else None,
            "chunk_delta_max": float(np.max(deltas)) if deltas else None,
        })

    rows.sort(key=lambda r: r["magnitude_m"])
    print(f"\n{'magnitude':>10} {'succ':>7} {'zero-stale':>11} {'paired':>7} "
          f"{'mean|d|':>9} {'max|d|':>9}")
    for r in rows:
        md = f"{r['chunk_delta_mean']:.5f}" if r["chunk_delta_mean"] is not None else "n/a"
        mx = f"{r['chunk_delta_max']:.5f}" if r["chunk_delta_max"] is not None else "n/a"
        print(f"{r['magnitude_m']*1000:>8.1f}mm {r['success']:>3}/{r['n']:<3} "
              f"{r['zero_stale_episodes']:>11} {r['paired']:>7} {md:>9} {mx:>9}")

    if args.json:
        with open(args.json, "w") as f:
            json.dump(rows, f, indent=2)
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
