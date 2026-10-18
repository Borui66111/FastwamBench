"""Gate 14F: compare the action chunk planned before vs after a mid-carry strike.

The keep arm plans its chunk at the strike step from the PRE-strike observation;
the zero-stale arm plans from the refreshed POST-strike observation. Same seed,
same trial, so every replan before the strike must be bit-identical -- that is
the internal-validity check -- and the chunk at the strike measures how much the
model's plan actually moves when it sees the object displaced.

Usage:
    python scripts_setup/gate14f_chunkdiff.py \
        evidence/gate14f_chunks_keep.jsonl evidence/gate14f_chunks_zero.jsonl

Each input is one JSON object per replan: {"t", "replan_idx", "chunk": [[7 floats], ...]}
written by eval_libero_single.py when FASTBENCH_DUMP_CHUNK is set.
"""
import json
import sys

import numpy as np


def load(path):
    out = {}
    with open(path) as f:
        for line in f:
            rec = json.loads(line)
            out[int(rec["t"])] = np.asarray(rec["chunk"], dtype=float)
    return out


def main(keep_path, zero_path, strike_step=100):
    keep, zero = load(keep_path), load(zero_path)
    common = sorted(set(keep) & set(zero))
    if not common:
        print("no common replan steps -- were these run at the same horizon?")
        return 1

    print(f"{'t':>5} {'max|d|':>9} {'mean|d|':>9}  verdict")
    pre_max, post = [], []
    for t in common:
        d = np.abs(keep[t] - zero[t])
        identical = float(d.max()) < 1e-9
        if t < strike_step:
            pre_max.append(float(d.max()))
        else:
            post.append((t, float(d.max()), float(d.mean())))
        print(f"{t:>5} {d.max():>9.5f} {d.mean():>9.5f}  "
              f"{'IDENTICAL' if identical else 'differs'}")

    print()
    print(f"pre-strike replans: {len(pre_max)}  "
          f"max|d| over all = {max(pre_max) if pre_max else float('nan'):.6f}")
    if post:
        strike = [p for p in post if p[0] == strike_step]
        print(f"strike replan t={strike_step}: "
              + (f"max|d| = {strike[0][1]:.5f}, mean|d| = {strike[0][2]:.5f}"
                 if strike else "not present in these dumps"))
        print(f"post-strike replans: {len(post)}  "
              f"max|d| range {min(p[1] for p in post):.5f} - {max(p[1] for p in post):.5f}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
