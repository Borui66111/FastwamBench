#!/usr/bin/env python
"""[fastbench] Gate 13 magnitude calibration: success vs perturbation size.

Usage: gate13_magcal.py results/gate13_mag2_00 results/gate13_mag2_0005 ...
Prints one row per result dir: tag, magnitude, disturb success rate, steps.
Pick the LARGEST magnitude that still succeeds at H=1 as the sweep size.
"""
import json, sys, glob, os

for d in sys.argv[1:]:
    recs = []
    for p in sorted(glob.glob(os.path.join(d, "*", "H*", "*", "records.jsonl"))):
        recs += [json.loads(l) for l in open(p) if l.strip()]
    ends = [r for r in recs if r.get("event") == "episode_end"]
    ivs = [r for r in recs if r.get("event") == "intervention"]
    mag = ivs[0].get("magnitude") if ivs else None
    delta = ivs[0].get("delta") if ivs else None
    ok = sum(1 for e in ends if e.get("success"))
    steps = [e.get("steps") for e in ends]
    print(f"{os.path.basename(d):24s} mag={str(mag):7s} succ={ok}/{len(ends)} "
          f"steps={steps} delta={[round(x,4) for x in delta] if delta else None}")
