"""Development-stage script (exploratory, not part of the reproducible pipeline).

Produced the Gate-3 development numbers quoted in research/RESEARCH_PROTOCOL.md section 2. Run from the
project root with `PYTHONPATH=.`; the first argument is a pickle cache that is built on first use.
See scripts/README.md.
"""
import pickle, sys, numpy as np
from collections import Counter
cases, two, obs1, obs2 = pickle.load(open(sys.argv[1], "rb"))
det = [c for c in cases if c.detected]
def cat(o):
    t = len(o.flips); f = int(o.flips.sum())
    fl = "noF" if t == 0 else ("all" if f == t else ("some" if f else "none"))
    br = "noP" if o.n_passing == 0 else ("b0" if o.n_breaks == 0 else ("ball" if o.n_breaks == o.n_passing else "bsome"))
    return fl, br
F, I = Counter(), Counter()
nvar_f = []; anyrep = 0
for c in det:
    o = obs1[c.case_id][0]; m = c.faulty_mask
    k = 0; rep = False
    for v in o:
        (F if m[v.column] else I)[cat(v)] += 1
        if m[v.column]:
            k += 1; rep |= cat(v) == ("all", "b0") or cat(v) == ("all", "noP")
    nvar_f.append(k); anyrep += rep
print("faulty-statement variants:", sum(F.values()), "per case mean", np.mean(nvar_f), "cases with clean repair", anyrep, "/", len(det))
for k, v in sorted(F.items(), key=lambda x: -x[1]): print("  F", k, v, round(v / sum(F.values()), 3))
print("innocent variants:", sum(I.values()))
for k, v in sorted(I.items(), key=lambda x: -x[1]): print("  I", k, v, round(v / sum(I.values()), 4))
