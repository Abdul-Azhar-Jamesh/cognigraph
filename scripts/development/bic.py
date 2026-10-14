"""Development-stage script (exploratory, not part of the reproducible pipeline).

Produced the Gate-3 development numbers quoted in research/RESEARCH_PROTOCOL.md section 2. Run from the
project root with `PYTHONPATH=.`; the first argument is a pickle cache that is built on first use.
See scripts/README.md.
"""
import pickle, sys, numpy as np
from pcg.interventional import *
cases, two, obs1, obs2 = pickle.load(open(sys.argv[1], "rb"))
det = [c for c in cases if c.detected]
tr = [(obs1[c.case_id][0], c.faulty_mask) for c in det]
for K in range(2, 8):
    p, c = estimate_intervention_params(tr, "x", n_nonrepair=K, n_repair=1)
    print("K", K, "BIC nonrepair %.0f" % c["bic_nonrepair"], [(round(a, 3), round(b, 3), round(d, 3)) for a, b, d in zip(p.kappa, p.psi, p.eta)])
for K in (3, 5, 7):
    for R in (1, 2, 3):
        p, c = estimate_intervention_params(tr, "x", n_nonrepair=K, n_repair=R)
        print("K", K, "R", R, "BIC repair %.0f" % c["bic_repair"], "alpha %.3f" % p.alpha, [(round(a, 3), round(b, 3), round(d, 3)) for a, b, d in zip(p.rho, p.gamma, p.beta)])
