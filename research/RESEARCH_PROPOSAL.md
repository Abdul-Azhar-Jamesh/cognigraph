# Research proposal, version 4

Written at Gate 1, after the literature audit and before the model was designed. The version 3
proposal is in [v3/RESEARCH_PROPOSAL.md](v3/RESEARCH_PROPOSAL.md). Provisional title, abstract,
contributions and venue assessment are at the end and were added after the experiments; they are
marked as such.

## 1. Starting point

Version 3.0.0 is frozen ([BASELINE_FREEZE.md](BASELINE_FREEZE.md)). Its most informative result is
a failure: with two faults, fusing mutation evidence makes localisation worse than not fusing it.
Its novelty statement needed a correction ([RELATED_WORK_AND_NOVELTY.md](RELATED_WORK_AND_NOVELTY.md),
section 1).

## 2. Candidate directions

Each candidate is described by the same ten points: (1) question, (2) contribution, (3) strongest
existing methods, (4) hypothesis and why it could be true, (5) assumptions, (6) failure modes,
(7) smallest falsifying experiment, (8) data and compute, (9) novelty risk, (10) impact.

### C1. Interventional multi-fault diagnosis

1. Can mutation evidence be used in a Bayesian localiser without assuming a single fault?
2. A noisy-OR model in which a variant is an intervention and a repair flips a failing test only if
   its statement is the sole cause; exact inference for a bounded number of faults.
3. Barinel; FLITSR; MUSE; the Bayesian framework of Kang et al. (single fault); Prosecutor.
4. It beats single-fault fusion and coverage-only multi-fault methods on multi-fault programs,
   because "a repair fixes only some failing tests" is evidence *for* a fault once a second fault
   is allowed, and against it in a single-fault table.
5. Independent exposures per test and fault; at most one repair per statement; coverage unchanged
   by a variant; a restoring variant exists often enough.
6. Fault interaction; no repair among the variants (human-written bugs); maskers on fault-free
   statements; cost of the extra hypotheses when there is one fault.
7. On the 410 existing two-fault programs: abandon if it does not beat the spectrum-only model and
   Barinel on "both faults in the top 3", or loses more than 0.02 single-fault Top-1.
8. Existing variant runs; minutes of CPU.
9. Medium. Closest: Kang et al. (single-fault assumption stated as a limitation), Prosecutor.
10. Academic: removes a stated limitation of Bayesian debugging in a small setting. Practical:
    low until it scales.

### C2. Risk-controlled abstention

1. Can a localiser give a guarantee on the share of wrong answers among those it gives?
2. Conformal thresholds on the top posterior.
3. A conformal-cutoff preprint for spectrum-based localisation; version 3's selective results.
4. A calibrated posterior should need a smaller threshold margin than a score.
5. Exchangeability of programs.
6. Shift between injected and human-written bugs breaks exchangeability; 31 to 150 programs give
   wide guarantees.
7. Empirical coverage of the guarantee on held-out programs.
8. Existing data.
9. High: the preprint exists and reports no gain over a fixed cutoff.
10. Modest.

### C3. Correlated tests

1. Does modelling shared execution paths between tests improve localisation or calibration?
2. A latent path variable per group of tests.
3. Barinel's per-candidate health already absorbs part of it.
4. Tests that run the same statements fail together more than the model expects.
5. Path groups can be derived from coverage.
6. Version 3 found the independent-test model already well calibrated in distribution; the gain
   may be nil.
7. Compare log loss with tests de-duplicated by coverage signature.
8. Existing data.
9. High, and weak prior evidence of benefit.
10. Low.

### C4. Posterior-guided variant execution

1. Can the posterior choose which variant to run next and reach the same answer with fewer runs?
2. Expected-information-gain ordering of variants.
3. Entropy-based test prioritisation for localisation; patch prioritisation in unified debugging.
4. Most variants are uninformative; the model knows which statements are still ambiguous.
5. A posterior that is already good.
6. Depends on C1 working; savings matter only where variant runs are expensive, which small
   functions are not.
7. Runs needed to reach the final Top-1, against random order.
8. Existing data.
9. Medium.
10. Practical if scaled; not testable convincingly here.

### C5. Calibration study across methods on a larger human-written benchmark

1. Are fault probabilities from any method trustworthy on human-written bugs and with several
   faults?
2. An empirical study, pre-registered, with HumanEvalFix added.
3. None found for classical localisers.
4. Model-based probabilities degrade more gracefully than learned ones (seen on 31 bugs in
   version 3).
5. Benchmarks of small functions are informative.
6. Small programs; hand-inserted bugs are not project bugs.
7. Brier skill against the base rate on HumanEvalFix.
8. HumanEvalFix (one file); minutes of CPU.
9. Low risk, low mathematical novelty.
10. Useful as evidence; a workshop-level study alone.

### C6. Language-model evidence

No API access on this machine; HumanEval is a likely part of every model's training data. Not
feasible honestly. Future work.

### C7. Repository-scale approximate inference

Strong systems exist (SmartFL, Prosecutor); BugsInPy and Defects4J cannot be run with this tool
chain. Not feasible.

## 3. Ranking

Scores 1 (poor) to 5 (good). "Risk" is scored so that higher is better (less risk). Weights:
novelty and scientific value count double, because the aim is a research contribution, not a
feature; ease is deliberately not a criterion.

| Candidate | Novelty (x2) | Scientific value (x2) | Feasibility | Evaluation quality possible | Implementation risk | Relevance | Total (of 40) |
|---|---|---|---|---|---|---|---|
| C1 Interventional multi-fault | 4 | 4 | 4 | 3 | 3 | 5 | **31** |
| C5 Calibration study | 2 | 3 | 5 | 3 | 5 | 4 | 27 |
| C4 Posterior-guided variants | 3 | 3 | 3 | 2 | 3 | 4 | 24 |
| C2 Risk-controlled abstention | 2 | 2 | 4 | 3 | 4 | 3 | 22 |
| C3 Correlated tests | 2 | 2 | 4 | 3 | 4 | 3 | 22 |
| C7 Repository scale | 2 | 4 | 1 | 1 | 1 | 5 | 20 |
| C6 Language-model evidence | 2 | 3 | 1 | 1 | 2 | 4 | 18 |

The scores are judgements. The ranking is robust to moderate changes: C1 stays first unless its
novelty is scored 2, which is what a reviewer who equates it with Barinel plus MUSE would do.

## 4. Selection

**Primary: C1.** It is the only candidate that answers a limitation stated by the closest prior
work and at the same time addresses this project's worst result.

**Complementary: C5** (the evaluation C1 needs anyway: a larger human-written benchmark and
calibration with an unknown number of faults) and **bounded-cardinality inference** (part of C1;
removes the 22-statement limit; not claimed as new).

Why this combination: C1 alone on the project's own programs would be a result on data the model
was designed on. C5 supplies held-out programs and the part of the evaluation that can embarrass
the model (human-written bugs, where mutation evidence is known to be weak).

Not selected: C2 and C3 have the weakest evidence that they would matter; C4 depends on C1 and
cannot be evaluated convincingly on small functions; C6 and C7 are infeasible here.

## 5. Gates

| Gate | Evidence required to continue | Outcome |
|---|---|---|
| 1 Literature and opportunity | A gap with an author-stated part | Met: this document, the gap matrix |
| 2 Design and protocol | Mathematical design; pre-registered protocol | Met: MATHEMATICAL_DESIGN.md, RESEARCH_PROTOCOL.md |
| 3 Proof of concept | Falsification experiment on development data | Criterion (a) met, criterion (b) missed by 0.002; continued with the 0.02 margin kept as hypothesis H2 (protocol section 2) |
| 4 Full evaluation | Held-out sets, baselines, ablations | RESULTS.md |
| 5 Audit | Reproduction, checks of claims | FINAL_RESEARCH_AUDIT.md |

## 6. Provisional paper outline (added after the experiments)

See [RESULTS.md](RESULTS.md), section "Paper outline", which is written from the measured results.
