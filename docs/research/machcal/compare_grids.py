"""Cell-by-cell comparison of two kernel grids (old.json new.json): max |ln ratio| of width, depth and normalised
enthalpy per kernel, status changes, and cells over 1e-3. Usage: python compare_grids.py OLD NEW"""
import json, math, sys, collections
old, new = (json.load(open(p)) for p in sys.argv[1:3])
key = lambda r: (r[0], r[1], r[2])
o = {key(r): r for r in old}; n = {key(r): r for r in new}
assert set(o) == set(n), (len(o), len(n))
stats = collections.defaultdict(lambda: {"cells": 0, "maxW": 0.0, "maxD": 0.0, "maxdH": 0.0, "statusDiff": 0, "exactEqual": 0})
over = []
for k in o:
    a, b = o[k], n[k]
    s = stats[k[1]]; s["cells"] += 1
    s["exactEqual"] += a[3:] == b[3:]
    if a[5] != b[5]:
        s["statusDiff"] += 1; over.append(("status", k, a[3:], b[3:])); continue
    for idx, name in ((3, "maxW"), (4, "maxD"), (6, "maxdH")):
        if a[idx] and b[idx]:
            d = abs(math.log(b[idx] / a[idx])); s[name] = max(s[name], d)
            if d > 1e-3:
                over.append((name, k, a[3:], b[3:]))
        elif bool(a[idx]) != bool(b[idx]):
            over.append(("null/zero", k, a[3:], b[3:]))
print(json.dumps({"cellsCompared": len(o), "perKernel": stats, "nCellsOver1e-3": len(over), "examples": over[:20]},
                 indent=1, default=list))
