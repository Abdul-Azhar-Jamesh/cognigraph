"""Development-stage script (exploratory, not part of the reproducible pipeline).

Produced the Gate-3 development numbers quoted in research/RESEARCH_PROTOCOL.md section 2. Run from the
project root with `PYTHONPATH=.`; the first argument is a pickle cache that is built on first use.
See scripts/README.md.
"""
import pickle, sys, numpy as np
from collections import Counter
from pcg import research as rs
from pcg.interventional import *
from pcg.fusion import size_aware_prior
cases, two, obs1, obs2 = pickle.load(open(sys.argv[1], "rb"))
det = [c for c in cases if c.detected]
ev = {cid: e for cid, (_, e) in obs1.items()}
from pcg.research import MutationEvidence
for c in cases:
    if c.case_id not in ev:
        n = len(c.program.statements); ev[c.case_id] = MutationEvidence(np.zeros(n, int), np.zeros(n, int), np.zeros(n), np.zeros(n), 0, 0)
fold = rs.train(cases, det, ev, "pooled")
ip, _ = estimate_intervention_params([(obs1[c.case_id][0], c.faulty_mask) for c in det], "pooled", 5, 1, "exclusive")
def cat(o):
    t = len(o.flips); f = int(o.flips.sum())
    return f"{f}/{t}f {o.n_breaks}/{o.n_passing}b"
kinds = Counter(); shown = 0
for c in det:
    o, e = obs1[c.case_id]
    grid, w = fold.params.exposure_prior(); n = len(c.program.statements)
    post = interventional_posterior(np.full(n, size_aware_prior(n, fold.fusion.mu)), c.spectrum.coverage, c.spectrum.failed, o, ip, grid, w, fold.params.leak, 3)
    f = int(np.flatnonzero(c.faulty_mask)[0]); top = int(np.argmax(post.marginals)); sc_f = rs.score_case(c, e, fold)["pcg_fused"]
    if post.marginals[f] < post.marginals.max() - 1e-12:
        lev_f, lev_t = e.levels[f], e.levels[top]
        kinds[(int(lev_f), int(lev_t), "fusedOK" if sc_f[f] >= sc_f.max() - 1e-12 else "fusedMiss", round(post.expected_faults))] += 1
        if shown < 7:
            shown += 1
            print(c.case_id, "fault", f, "p=%.3f" % post.marginals[f], [cat(v) for v in o if v.column == f])
            print("    top", top, "p=%.3f" % post.marginals[top], [cat(v) for v in o if v.column == top], "E#=%.2f" % post.expected_faults)
print("misses by (level fault, level top):", sorted(kinds.items(), key=lambda x: -x[1]))
