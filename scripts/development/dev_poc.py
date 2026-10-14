"""Development-stage script (exploratory, not part of the reproducible pipeline).

Produced the Gate-3 development numbers quoted in research/RESEARCH_PROTOCOL.md section 2. Run from the
project root with `PYTHONPATH=.`; the first argument is a pickle cache that is built on first use.
See scripts/README.md.

Gate 3 falsification experiment on the development data (D1 single- and two-fault).
"""
import pickle, sys, time, os
import numpy as np
from pcg import config, experiments as ex, metrics
from pcg import research as rs
from pcg.interventional import (variant_observations, estimate_intervention_params,
                                interventional_posterior, InterventionParams)
from pcg.fusion import effective_prior, size_aware_prior
from dataclasses import replace

cache = sys.argv[1]
t0 = time.time()
def log(m): print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)

def observe(cases):
    out = {}
    for name in sorted({c.program_name for c in cases}):
        own = [c for c in cases if c.program_name == name]
        variants, store = rs.run_variants(own, config.STEP_LIMIT, config.SUBPROCESS_TIMEOUT_S)
        for c in own:
            usable = [(v.line, store.outcomes[v.source]) for v in variants[c.case_id]]
            out[c.case_id] = (variant_observations(c.program.statements, c.spectrum.coverage, c.spectrum.failed,
                                                   c.expected, usable),
                              rs.evidence_for_case(c, variants[c.case_id], store))
    return out

if os.path.exists(cache):
    cases, two, obs1, obs2 = pickle.load(open(cache, "rb"))
else:
    refs = ex.load_references()
    cases, _ = ex.build_first_order_cases(refs)
    two, _ = ex.build_two_fault_cases(refs)
    two = [c for c in two if c.detected]
    log("observing single-fault variants")
    obs1 = observe([c for c in cases if c.detected])
    log("observing two-fault variants")
    obs2 = observe(two)
    pickle.dump((cases, two, obs1, obs2), open(cache, "wb"))
log(f"{len(cases)} valid, {len(two)} two-fault detected")
detected = [c for c in cases if c.detected]
names = sorted({c.program_name for c in cases})
from pcg.research import MutationEvidence
ev = {cid: e for cid, (_, e) in obs1.items()}
for c in cases:
    if c.case_id not in ev:
        n = len(c.program.statements)
        ev[c.case_id] = MutationEvidence(np.zeros(n, int), np.zeros(n, int), np.zeros(n), np.zeros(n), 0, 0)

def iv(case, obs, fold, ip, c=3, use=True):
    grid, w = fold.params.exposure_prior()
    n = len(case.program.statements)
    prior = np.full(n, size_aware_prior(n, fold.fusion.mu))
    return interventional_posterior(prior, case.spectrum.coverage, case.spectrum.failed, obs, ip if use else None,
                                    grid, w, fold.params.leak, c)

def ap(scores, faults):
    order = np.argsort(-scores, kind="stable"); hits = 0; s = 0.0
    fs = set(faults)
    for r, i in enumerate(order, 1):
        if i in fs: hits += 1; s += hits / r
    return s / len(fs)

single, twof = [], []
P = {k: [] for k in ("iv1", "iv_05", "fused", "lr", "size")}; Y = []
ips = {}
for held in names:
    fold = rs.train([c for c in cases if c.program_name != held], [c for c in detected if c.program_name != held], ev, held)
    ip, counts = estimate_intervention_params([(obs1[c.case_id][0], c.faulty_mask) for c in detected if c.program_name != held], held, n_nonrepair=int(sys.argv[2]), n_repair=int(sys.argv[3]), layer=sys.argv[4])
    ips[held] = ip
    for c in (c for c in detected if c.program_name == held):
        o, e = obs1[c.case_id]
        sc = rs.score_case(c, e, fold)
        post = iv(c, o, fold, ip)
        sc["iv"] = post.marginals
        sc["iv_05"] = iv(c, o, fold, replace(ip, tau=0.5)).marginals
        sc["spec3"] = iv(c, o, fold, ip, use=False).marginals
        f = np.flatnonzero(c.faulty_mask).tolist()
        row = {"program": held}
        for m in ("ochiai", "barinel", "metallaxis", "lr_fusion", "pcg_size", "pcg_fused", "spec3", "iv", "iv_05"):
            r = rs.best_fault_metrics(sc[m], f)
            row[m + ".top1"], row[m + ".rr"] = r.top1, r.reciprocal_rank
        single.append(row)
        P["iv1"] += sc["iv"].tolist(); P["iv_05"] += sc["iv_05"].tolist(); P["fused"] += sc["pcg_fused"].tolist()
        P["lr"] += sc["lr_fusion"].tolist(); P["size"] += sc["pcg_size"].tolist(); Y += c.faulty_mask.astype(int).tolist()
    for c in (c for c in two if c.program_name == held):
        o, e = obs2[c.case_id]
        sc = rs.score_case(c, e, fold)
        post = iv(c, o, fold, ip)
        sc["iv"] = post.marginals
        sc["iv_05"] = iv(c, o, fold, replace(ip, tau=0.5)).marginals
        sc["spec3"] = iv(c, o, fold, ip, use=False).marginals
        f = np.flatnonzero(c.faulty_mask).tolist()
        row = {"program": held, "boundary": post.boundary_mass, "efaults": post.expected_faults}
        for m in ("ochiai", "barinel", "metallaxis", "muse", "hybrid_avg", "lr_fusion", "pcg_size", "pcg_fused", "spec3", "iv", "iv_05"):
            mm = metrics.multi_fault_metrics(sc[m], f)
            row[m + ".first_top1"], row[m + ".all_top3"], row[m + ".mean_rank"] = mm["first_top1"], mm["all_top3"], mm["mean_rank"]
            row[m + ".ap"] = ap(sc[m], f)
        twof.append(row)
log("scored")
print("example params:", ips[names[0]].to_dict())
print("\nSINGLE FAULT (n=%d)" % len(single))
for m in ("ochiai", "barinel", "metallaxis", "lr_fusion", "pcg_size", "pcg_fused", "spec3", "iv", "iv_05"):
    print(f"  {m:12s} top1 {np.mean([r[m+'.top1'] for r in single]):.3f}  mrr {np.mean([r[m+'.rr'] for r in single]):.3f}")
Y = np.array(Y)
for k, p in P.items():
    p = np.clip(np.array(p), 1e-6, 1 - 1e-6)
    print(f"  {k:6s} brier {np.mean((p-Y)**2):.4f} logloss {-np.mean(Y*np.log(p)+(1-Y)*np.log(1-p)):.4f}")
print("\nTWO FAULTS (n=%d)" % len(twof))
for m in ("ochiai", "barinel", "metallaxis", "muse", "hybrid_avg", "lr_fusion", "pcg_size", "pcg_fused", "spec3", "iv", "iv_05"):
    print(f"  {m:12s} first_top1 {np.mean([r[m+'.first_top1'] for r in twof]):.3f}  all_top3 {np.mean([r[m+'.all_top3'] for r in twof]):.3f}"
          f"  mean_rank {np.mean([r[m+'.mean_rank'] for r in twof]):.2f}  MAP {np.mean([r[m+'.ap'] for r in twof]):.3f}")
print("  mean boundary mass %.3f, mean expected faults %.2f" % (np.mean([r["boundary"] for r in twof]), np.mean([r["efaults"] for r in twof])))
pickle.dump((single, twof), open(cache + ".rows", "wb"))
