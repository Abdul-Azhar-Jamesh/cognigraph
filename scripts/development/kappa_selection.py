"""Choose the concentration kappa of the hierarchical fault-count prior on the DEVELOPMENT set only (D1).

Rule fixed in research/RESEARCH_PROTOCOL_V5.md before any held-out data were scored: leave-one-program-out on
D1-1 (single faults) and D1-2 (two faults); pick the kappa with the smallest per-statement log loss on the pooled
cases; ties go to the larger kappa. Usage (from the project root):

    PYTHONPATH=. python scripts/development/kappa_selection.py CACHE.pkl OUT.json

``CACHE.pkl`` is the development cache written by ``scripts/development/dev_poc.py`` (cases and variant
observations of D1); ``OUT.json`` receives the table.
"""
import json
import pickle
import sys

import numpy as np

from pcg import config, metrics, v4
from pcg.fusion import size_aware_prior
from pcg.interventional import enumerate_configurations, summarise

GRID = (1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, None)  # None = independent faults (the version 4 model)

cases, two, obs1, obs2 = pickle.load(open(sys.argv[1], "rb"))
observed = {**obs1, **obs2}
detected = [c for c in cases if c.detected]
names = sorted({c.program_name for c in cases})
acc = {(k, s): {"p": [], "y": []} for k in GRID for s in ("D1-1", "D1-2")}
for held in names:
    fold = v4.fit([c for c in cases if c.program_name != held], observed, f"D1 without {held}")
    params, fusion = fold.trained.params, fold.trained.fusion
    grid, weights = params.exposure_prior()
    for label, group in (("D1-1", [c for c in detected if c.program_name == held]),
                         ("D1-2", [c for c in two if c.program_name == held])):
        for c in group:
            n = len(c.program.statements)
            e = enumerate_configurations(np.full(n, size_aware_prior(n, fusion.mu)), c.spectrum.coverage,
                                         c.spectrum.failed, observed[c.case_id][0], fold.iv, grid, weights,
                                         params.leak, config.IV_MAX_FAULTS)
            for k in GRID:
                acc[(k, label)]["p"].extend(summarise(e, kappa=k).marginals.tolist())
                acc[(k, label)]["y"].extend(c.faulty_mask.astype(int).tolist())
rows = []
for k in GRID:
    row = {"kappa": "inf" if k is None else k}
    pool_p, pool_y = [], []
    for s in ("D1-1", "D1-2"):
        p, y = np.array(acc[(k, s)]["p"]), np.array(acc[(k, s)]["y"])
        pool_p.append(p)
        pool_y.append(y)
        row[f"{s}.log_loss"], row[f"{s}.brier"] = metrics.log_loss(p, y), metrics.brier_score(p, y)
    p, y = np.concatenate(pool_p), np.concatenate(pool_y)
    row["pooled.log_loss"], row["pooled.brier"] = metrics.log_loss(p, y), metrics.brier_score(p, y)
    rows.append(row)
best = min(rows, key=lambda r: (round(r["pooled.log_loss"], 6), -(1e18 if r["kappa"] == "inf" else r["kappa"])))
json.dump({"rows": rows, "selected_kappa": best["kappa"]}, open(sys.argv[2], "w"), indent=1)
for r in rows:
    print(f"kappa {str(r['kappa']):>5}  pooled log loss {r['pooled.log_loss']:.4f}  D1-1 {r['D1-1.log_loss']:.4f}  D1-2 {r['D1-2.log_loss']:.4f}  brier {r['pooled.brier']:.4f}")
print("selected kappa:", best["kappa"])
