# Final research audit, version 4

Date 2026-10-14. Results and interpretation: [RESULTS.md](RESULTS.md). Nothing is committed or pushed.

## 1. Checks executed

| Check | How | Result |
|---|---|---|
| Unit and mathematical tests | `python -m pytest` (`docs/TEST_LOG.txt`) | **221 passed**, 0 failed, 1 pgmpy deprecation warning (190 old + 31 new cases from 16 new test functions) |
| New inference vs brute force | `tests/test_v4.py`: both variant layers against explicit enumeration of configurations, exposure rates, repair choices and sole causes; no-variant case against version 2 exact inference; closed forms of the sole-cause probability; calibration of posteriors simulated from the model; estimation recovers generating parameters | pass |
| Reported numbers vs saved files | 77 independent recomputations (plain numpy, not the project's code) of means, paired differences, Brier scores and skill from `per_case.csv` and `probabilities.jsonl` | **0 mismatches** |
| Version 2 and 3 results unchanged by the new code | `python -m pcg all` re-run | `results/benchmark` fingerprint `141c0a38...` identical; `results/research` 22 of 24 files identical, the other two differ only in seconds |
| **Reproducibility of version 4** | second complete `python -m pcg v4` into a separate folder (7,568 s, machine otherwise idle), manifests compared | **26 of 29 files bit-identical; the other three (`cost.json`, `summary.json`, `SUMMARY.md`) differ only in wall-clock seconds**; `summary.json` is equal once its cost block is removed; counts of cases, variants and runs are equal |
| Ground-truth leakage | `test_scoring_receives_no_ground_truth`; every learned quantity fitted on D1 only; HumanEval problems named like a development program excluded (7) | pass |
| Figures | all 8 figures of `results/v4/figures` and the synthetic figure inspected | content matches the tables; cosmetic only: legend of `fig3` covers part of the HumanEval panel |

Artifact locations: `results/v4/` (raw, derived, figures, tables), `results/v4_synthetic/`, `results/v4_sensitivity/`,
`results/demo_v4/`; scratch copy of the second run was outside the project and is not kept.

## 2. Findings of the audit

1. **Metric flaw (found here, not fixed in code).** The pre-registered average precision with mid-ranks can exceed 1 when faults tie
   (1.0 to 5.1% of cases, maximum 1.5), and favours coverage-only methods (4.5% of their cases against 1.4% for IV). It was
   left unchanged so that the code stays consistent with the saved results and with the reproduction. A tie-corrected
   sensitivity analysis (`results/v4_sensitivity`) changes the picture in favour of the proposed model (beats spectrum-only,
   FLITSR\*, v3 fused and logistic fusion; still not MUSE). Because the correction favours the proposed method and was made
   after seeing the results, the pre-registered numbers are the confirmatory ones.
2. **Two analysis defects.** The breakdown "all faults have a restoring variant" is undefined for multi-fault sets (section 18 of
   `results/v4/SUMMARY.md` shows 0.00 and one meaningless case with AP 1.33); it is not used anywhere. Two demonstration
   selection rules could not match and were corrected (`demo_v4.py`).
3. **Three failed attempts of the main run** (command line too long, duplicate HumanEval function names, and a ground-truth-free
   crash in feature construction that was the same duplicate-name cause) happened before any result was written; they are
   protocol deviations D5 and D6.

## 3. Verdict per criterion

| Criterion | Verdict | Evidence |
|---|---|---|
| Baseline preserved and reproduced | PASS | tag `v3.0.0`, fingerprints, 22/24 and 26/29 |
| Literature audited, gap stated honestly | PASS WITH LIMITATIONS | corrected a missed prior work; about 20 searches; several sources read only as abstracts (REFERENCE_VERIFICATION) |
| Mathematical design before coding, with checks | PASS | MATHEMATICAL_DESIGN.md, amendments A1-A6, brute-force tests |
| Pre-registered protocol, no tuning on held-out data | PASS WITH LIMITATIONS | six deviations recorded; the model was shaped on D1; the 0.02 criterion was missed on D1 and continued |
| Strong baselines, equal information | PASS WITH LIMITATIONS | Ochiai, Tarantula, Barinel, FLITSR(\*), Metallaxis, MUSE, hybrid, logistic; FLITSR is a re-implementation; no SmartFL, Prosecutor |
| Realistic benchmarks | PASS WITH LIMITATIONS | 31 + 146 hand-inserted bugs, 3,622 held-out programs; small functions, constructed multi-fault programs |
| The proposed model beats existing methods | **FAIL** | H1 supported only against the project's own v3 fusion (and logistic fusion on E2); not against MUSE, FLITSR\*, spectrum-only |
| Probabilities usable | **FAIL** as pre-registered (H5); PASS WITH LIMITATIONS for the comparison with v3 and logistic fusion | negative skill against the base rate at three faults |
| Negative results retained | PASS | RESULTS.md section 2 and 3 |
| Reproducible | PASS | bit-identical apart from timings |
| Real LLM evidence | NOT DONE | no API access; not claimed |
| Project-scale validity | NOT DONE | exact inference limited to about 30 statements; 85 s for one 28-statement case |

## 4. Scorecard (subjective; before = given scores, after = this audit)

| Dimension | Before | After | Evidence |
|---|---|---|---|
| Mathematical correctness | 8 | 9 | new layer verified against brute force and simulation; closed forms |
| Statistical validity | 7 | 8 | pre-registered, program-clustered intervals, Holm, held-out data; the tie flaw lowers it |
| Implementation quality | 8 | 8 | 221 tests; three crashes in late stages show a weaker pipeline test |
| Experimental rigour | 7 | 8 | 3,622 held-out cases, ablations, synthetic study; no natural multi-fault data |
| Reproducibility | 8 | 9 | v4 bit-identical apart from seconds |
| Technical depth | 7 | 8 | exact interventional layer, mixture estimation, bounded-cardinality inference |
| Originality | 4 | 5 | closest prior work (Kang et al. 2023; Prosecutor 2026) shares much of the idea; the multi-fault interventional likelihood was not found elsewhere (search-limited) |
| Practical usefulness | 4 | 4 | small single functions only |
| Academic suitability | 8 | 8 | |
| Demonstration quality | 8 | 8 | `demo-v4` shows a success, a cost and a failure; the old review guide still describes version 3 |
| Potential for improvement | 6 | 6 | |

## 5. Unresolved issues

1. H1 is only partly supported; H5 not supported; with three faults the pre-registered MAP does not favour IV and all-faults-in-top-3 is lower than coverage-only methods.
2. The average-precision tie flaw remains in `pcg/metrics.py` (documented; a corrected function exists in `pcg/v4_sensitivity.py`).
3. `results/v4/SUMMARY.md` section 18 first table and the `fig3` legend placement are known defects; derived files were not regenerated so that the manifest stays valid.
4. No comparison with SmartFL or Prosecutor; no LLM evidence; no naturally co-occurring faults; functions of at most 28 statements.
5. `docs/REVIEW_GUIDE.md` and `docs/FINAL_AUDIT.md` describe version 3; version 4 is documented in `research/` and the README only.
6. Working tree is uncommitted: research documents moved to `research/v3/`, new modules, new result folders, and timing-only changes in `results/research`, `results/demo`.

## 6. Readiness

Reproducible, tested and honestly documented as a small empirical modelling study. Not ready for a research-conference submission (needs real project bugs, a modern competitor, and a better result at three faults). Reasonable as a university project and as evidence of careful probabilistic modelling. No acceptance prediction is made.
