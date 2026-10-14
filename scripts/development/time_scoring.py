"""Time the scoring of cases of different size (backs the cost statements in research/RESULTS.md and the manuscript).

Usage (project root, machine otherwise idle): ``PYTHONPATH=. python scripts/development/time_scoring.py STAGE_CACHE.pkl OUT.json``
where STAGE_CACHE.pkl was written by ``run_v4(stage_cache=...)``. Scores, with the transfer-condition parameters of D1, the case with the
largest number of statements times variants of each HumanEval set, and 30 seeded random cases; one call each, wall-clock seconds.
"""
import json
import pickle
import sys
import time

import numpy as np

from pcg import config, experiments as ex, v4

cache = pickle.load(open(sys.argv[1], "rb"))
e_sets, e_observed = cache["e"][0], cache["e_observed"][0]
references = ex.load_references()
d1, _ = ex.build_first_order_cases(references)
observed, _ = v4.observe([c for c in d1 if c.detected], config.STEP_LIMIT, config.SUBPROCESS_TIMEOUT_S, lambda m: None)
fitted = v4.fit(d1, observed, "all of D1")


def seconds(case):
    start = time.time()
    v4.score(case, e_observed, fitted, ablations=False)
    return time.time() - start


rows = []
detected = [c for s in ("E1", "E2", "E3") for c in e_sets[s] if c.detected]
largest = max(detected, key=lambda c: len(c.program.statements) * len(e_observed[c.case_id][0]))
rows.append({"case": largest.case_id, "statements": len(largest.program.statements), "variants": len(e_observed[largest.case_id][0]),
             "failing_tests": int(largest.spectrum.n_failed), "seconds": round(seconds(largest), 1), "kind": "largest by statements x variants"})
rng = np.random.default_rng(config.SEED)
for index in rng.permutation(len(detected))[:30]:
    c = detected[int(index)]
    rows.append({"case": c.case_id, "statements": len(c.program.statements), "variants": len(e_observed[c.case_id][0]),
                 "failing_tests": int(c.spectrum.n_failed), "seconds": round(seconds(c), 2), "kind": "random"})
random_seconds = [r["seconds"] for r in rows if r["kind"] == "random"]
summary = {"largest": rows[0], "random_median_seconds": float(np.median(random_seconds)), "random_max_seconds": float(max(random_seconds)), "cases": rows}
json.dump(summary, open(sys.argv[2], "w"), indent=1)
print(json.dumps({k: v for k, v in summary.items() if k != "cases"}, indent=1))
