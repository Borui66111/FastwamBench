"""Verify every count in evidence/gate14L_horizon.md against the records."""
import sys, re
sys.path.insert(0, "scripts_setup")
from gate14L_horizon import cell, tag_for
from scipy.stats import fisher_exact

HS = [1, 2, 5, 10]
doc = open("evidence/gate14L_horizon.md").read()
bad = 0

def p2(k1, n1, k2, n2):
    return fisher_exact([[k1, n1 - k1], [k2, n2 - k2]])[1]

def hcol(line):
    """The H value in the FIRST column of a markdown table row."""
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return cells[0] if cells else ""

rows = {}
for H in HS:
    for m in ("idm", "first_frame"):
        for arm in ("control", "disturb"):
            rows[(H, m, arm)] = cell(tag_for("g14L", m), arm, H)

docrows = [l for l in doc.splitlines() if l.startswith("|")]

for H in HS:
    a, b = rows[(H, "idm", "control")], rows[(H, "idm", "disturb")]
    c, d = rows[(H, "first_frame", "control")], rows[(H, "first_frame", "disturb")]
    gap = b[0] / b[1] - d[0] / d[1]
    pv = p2(b[0], b[1], d[0], d[1])
    want = [f"{a[0]}/{a[1]}", f"{b[0]}/{b[1]}", f"{c[0]}/{c[1]}", f"{d[0]}/{d[1]}",
            f"{gap:+.2f}", f"{pv:.4f}"]
    cands = [l for l in docrows if hcol(l) == str(H) and "/" in l]
    if not cands:
        print(f"MISSING main row H={H} want {want}")
        bad += 1
        continue
    got = cands[0]
    nums = re.findall(r"[-+]?\d\.\d{4}|[-+]?\d\.\d\d|\d+/\d+", got)
    if nums[:4] != want[:4] or abs(float(nums[4]) - gap) > 0.005 \
       or abs(float(nums[5]) - pv) > 0.00005:
        print(f"MISMATCH main row H={H}\n  doc: {got}\n  want {want}\n  got {nums}")
        bad += 1

# Strike table: find the header whose second/third columns are idm / first_frame,
# NOT the main results table (whose header starts with H and has 7 columns).
strike_hdr = None
for i, l in enumerate(docrows):
    cells = [c.strip() for c in l.strip().strip("|").split("|")]
    if cells[:3] == ["H", "idm", "first_frame"]:
        strike_hdr = i
        break
if strike_hdr is None:
    print("MISSING strike table header")
    bad += 1
else:
    for H in HS:
        got = docrows[strike_hdr + 2 + HS.index(H)]  # +2 skips header + separator
        vals = re.findall(r"\d\.\d{3}", got)
        want = [round(p2(rows[(H, m, "control")][0], rows[(H, m, "control")][1],
                        rows[(H, m, "disturb")][0], rows[(H, m, "disturb")][1]), 3)
                for m in ("idm", "first_frame")]
        if len(vals) != 2 or not all(abs(float(v) - w) < 0.0005 for v, w in zip(vals, want)):
            print(f"MISMATCH strike row H={H}: doc {vals} want {want}")
            bad += 1

ki = sum(rows[(H, "idm", "disturb")][0] for H in HS)
ni = sum(rows[(H, "idm", "disturb")][1] for H in HS)
kf = sum(rows[(H, "first_frame", "disturb")][0] for H in HS)
nf = sum(rows[(H, "first_frame", "disturb")][1] for H in HS)
pp = p2(ki, ni, kf, nf)
if f"{ki}/{ni}" not in doc or f"{kf}/{nf}" not in doc or f"p={pp:.4f}" not in doc:
    print(f"pooled mismatch: expect idm {ki}/{ni} ff {kf}/{nf} p={pp:.4f}")
    bad += 1

tot = sum(v[1] for v in rows.values())
print(f"total episodes read: {tot} (16 cells x 18 = 288)")
if tot != 288:
    bad += 1
print(f"pooled idm {ki}/{ni} ff {kf}/{nf} p={pp:.4f}")
print("VERIFY:", "OK" if bad == 0 else f"{bad} PROBLEM(S)")