# Phase 1: the baseline before the research extension

Date: 2026-10-13. This records the state of the project (version 2.0.0) before any change of the
research phase, how that state was verified, and how it can be restored.

## 1. Snapshot and how to restore it

| Item | Value |
|---|---|
| Version | 2.0.0 (`pcg/__init__.py`) |
| Version control | None. The folder is not a git repository |
| Recoverable copy | `archive/v2.0.0-baseline/` (90 files, everything except `.venv` and caches); verified identical with `diff -r` |
| Fingerprint of source, tests and dependency files | SHA-256 of the sorted per-file SHA-256 list: `6751ebe89511019fb1c3473b4ef46f2505cb3c8b8e633cd34d89e03cec3dcb83` |
| Results fingerprint | SHA-256 of `results/benchmark/MANIFEST.json`: `141c0a38e97d13e38b098c0bf5e3d610900a7190c1c3645f0c00011ff81f4d83`; the manifest lists a SHA-256 for each of the 22 result files |
| Original third-party project | `archive/original-third-party-backup/` (untouched) |

To restore version 2.0.0, copy `archive/v2.0.0-baseline/` over the project folder.

## 2. Environment

Windows 11 Home 10.0.26200; Python 3.12.3; numpy 2.2.5; networkx 3.5; matplotlib 3.10.5;
pylint 4.1.3; pytest 9.1.1; pgmpy 1.1.2 (one optional cross-check test). Seed `20261013`.

## 3. Verification performed in this phase

The claims about the current state were not taken on trust. Four checks were run.

| Check | Command | Result |
|---|---|---|
| Test suite | `python -m pytest` | 162 passed |
| Reproduction from scratch | `pipeline.run_benchmark` into a separate folder | all 22 files have the same SHA-256 as the stored results (third identical run) |
| Independent recomputation of the Ochiai baseline | standard-library script that reads only `cases.jsonl`, does not import `pcg` | Top-1 0.5380, Top-3 0.9124, MRR 0.7257; 0 of 594 per-case values differ from the stored ones |
| Independent recomputation of the model's posteriors | same script; naive enumeration over all fault configurations and grid points, using `params_lopo.json` | 502 detected cases with at most 9 statements re-derived; 0 disagreements with the stored posterior, Top-1 and reciprocal rank |

The last two checks matter because they do not share code with the project: they would have
exposed an error in the evaluation pipeline, the tie handling or the inference.

What these checks establish: the inference computes the specified model correctly and the
evaluation computes the stated metrics correctly. What they do not establish: that the specified
model is a good description of real faults. That second question is the subject of
[MATHEMATICAL_DESIGN.md](MATHEMATICAL_DESIGN.md), section 2.

## 4. Baseline table

Dataset for every row: the project's own mutation benchmark. 34 reference programs (4 to 16
statements, 7 to 16 tests each), 625 single-edit mutants generated, 1 excluded (time limit), 624
valid, 594 detected by the tests, 30 undetected. Procedure: leave-one-program-out; parameters for a
program are estimated from the other 33. Intervals: 95% bootstrap over programs.

| Metric | Existing value (PCG) | Best baseline (Ochiai) | Evaluated on | Artifact |
|---|---|---|---|---|
| Top-1 | 0.547 [0.494, 0.600] | 0.538 [0.486, 0.592] | 594 detected mutants | `first_order_summary.json` |
| Top-3 | 0.900 [0.861, 0.937] | 0.912 [0.877, 0.947] | 594 | same |
| MRR | 0.726 [0.688, 0.764] | 0.726 [0.690, 0.761] | 594 | same |
| EXAM (lower is better) | 0.243 [0.225, 0.263] | 0.236 [0.219, 0.256] | 594 | same |
| Brier score | 0.0760 | not a probability; base rate 0.1084 | 5,056 statements of 624 valid mutants | `calibration.json` |
| Log loss | 0.2712 | base rate 0.3746 | 5,056 statements | same |
| Expected calibration error (10 bins) | 0.0454 | base rate 0.0015 | 5,056 statements | same |
| P(no fault) for fault-free programs | 0.894 (prior 0.406) | none | 34 reference programs | `fault_free_programs.csv` |
| Two faults: first fault Top-1 | 0.378 [0.300, 0.458] | 0.366 [0.280, 0.454] | 410 detected two-fault programs | `two_fault_summary.json` |
| Repair, top-3 region: plausible / exact | 0.749 / 0.609 | 0.753 / 0.613 (Ochiai-guided) | 594 | `repair_summary.json` |
| Repair: candidates validated | 4.75 | 4.86; unguided 13.38 | 594 | same |

Other methods in the baseline: chance, execution-only count, a simple heuristic, Tarantula, and
three PCG ablations (fixed exposure rate, dependence slicing, static evidence).

Command that regenerates every value: `python -m pcg benchmark` (about 6 minutes).

## 5. Exact current implementation

| Aspect | Current implementation (v2.0.0) | Code |
|---|---|---|
| Random variables | `F_i` fault per statement (latent); `T_j` pass/fail per test (observed); `A_i` pylint flag (observed, optional); `Theta` exposure rate (latent, 10-point grid) | `pcg/model.py` |
| Prior | Independent Bernoulli, the same `pi` for every statement in every program | `pcg/graph.py` |
| Likelihood | Noisy-OR: `P(pass) = (1 - leak)(1 - Theta)^k`, `k` = faulty statements the test executed | `pcg/model.py` |
| Per-statement evidence | Likelihood ratio from a learned 2x2 table, applied to the prior | `pcg/graph.py` |
| Parameter estimation | Counting with add-one smoothing; EM for the weights of the `Theta` grid | `pcg/estimation.py` |
| Inference | Exact enumeration of `2^a` configurations for each grid point (`a` = executed statements, limit 22); Gibbs fallback | `pcg/model.py` |
| Calibration | Measured out-of-fold (Brier, log loss, ECE, reliability table); no recalibration step | `pcg/metrics.py` |
| Ranking | Posterior marginal, ties scored by expectation | `pcg/metrics.py` |
| Repair | Single-edit search on the three most suspicious statements; every candidate compiled and tested | `pcg/repair.py` |

## 6. Known limitations of the baseline

Taken from `docs/LIMITATIONS.md` and `docs/FINAL_AUDIT.md` of version 2.0.0:

1. No ranking advantage over Ochiai.
2. All faults are injected single edits; all programs but one were written for the project.
3. Two design decisions were made after seeing benchmark results; there is no untouched test set.
4. The only real second evidence source (pylint) carried no information; the LLM signal was simulated.
5. The model is over-confident between 0.1 and 0.3 and above 0.6.
6. The prior is the same for every statement regardless of program size.
7. Exact inference is exponential in the number of executed statements.
8. Dependence slicing made results worse.
9. No established Bayesian fault-localisation method (Barinel) and no mutation-based method were among the baselines.

Items 2, 4, 5, 6 and 9 are the ones the research phase addresses; see
[RESEARCH_PROPOSAL.md](RESEARCH_PROPOSAL.md).
