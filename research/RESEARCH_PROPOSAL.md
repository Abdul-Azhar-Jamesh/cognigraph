# Research proposal

Written on 13 October 2026, **before** any of the new code or experiments existed. The hypotheses,
metrics and comparisons below are fixed here and are not to be changed after results are seen.
Whatever the experiments show is reported in `docs/EXPERIMENTS.md`, including refutations.

## 1. Honest starting point

Three facts from the literature review limit what can be claimed:

1. Bayesian fault localisation over program spectra has existed since Barinel (2009), and far
   richer probabilistic localisers exist (SmartFL). **No new localisation algorithm will be claimed.**
2. For single faults, good spectrum formulas cannot be beaten on ranking by using spectra alone
   (Barinel's theorem; Xie et al.). Version 2.0.0 confirmed this: parity with Ochiai.
3. Results on injected faults do not predict results on real faults (Pearson et al.).

What the review did *not* find is any study of whether the probabilities of a classical fault
localiser are trustworthy, whether a model-based combination of evidence is as good as a learned
black-box one, and whether either survives the move from injected to human-written faults.
The proposal is therefore a **rigorous engineering and empirical contribution**: a model-based,
dependence-aware fusion of two real evidence families, evaluated for calibration, abstention and
transfer against strong baselines. It is not a claim of a novel algorithm.

## 2. Candidate directions

### Candidate A: model-based fusion of spectrum and mutation evidence (gaps G1, G2, G6)

| Item | Content |
|---|---|
| Research question | Does adding mutation-analysis evidence to the Bayesian network as a learned, coverage-conditioned likelihood improve localisation, and is this model-based fusion as good as a discriminative fusion given the same inputs? |
| State of the art | Hybrids by averaging (Pearson et al.); learning to rank (Zou et al., Rezaalipour and Furia). Both are black-box combinations of scores |
| Evidence for the gap | Zou et al. §6.5 list the limits of black-box linear combination and ask for alternatives; no probabilistic white-box fusion of these two families was found |
| Falsifiable hypothesis | H1: the fused model has higher Top-1 and MRR than the spectrum-only model. H2: it is not worse than logistic fusion by more than 0.02 MRR. H3: conditioning on coverage context lowers the log loss compared with unconditioned fusion |
| Change | One categorical evidence variable per statement summarising its mutants, with a likelihood table learned per coverage context |
| New relative to prior work | The explicit likelihood formulation and the treatment of the structural dependence between mutation and coverage evidence. The use of mutation evidence itself is not new |
| Practical value | A ranking that degrades to spectrum evidence where statements cannot be mutated, and one probability per statement |
| Data, compute | The project's 624 mutants; QuixBugs. About 20 analysis mutants per faulty program; minutes of compute |
| Baselines | Ochiai, Barinel, Metallaxis, MUSE, hybrid average, logistic regression on spectrum features, logistic regression on all features, PCG without the new evidence |
| Metrics, statistics | Top-1, Top-3, MRR; paired differences with bootstrap intervals over programs and a sign-flip test |
| Risks | On injected faults the analysis mutants contain the exact inverse of the injected edit, which inflates every mutation-based method. The naive-Bayes style fusion may be beaten by logistic regression |
| Effort | Medium |
| Refutation | No gain over the spectrum-only model on human-written bugs, or a clear loss to the hybrid average and to logistic fusion on both benchmarks |

### Candidate B: calibration, recalibration and selective localisation under shift (gaps G3, G4, G5, G8)

| Item | Content |
|---|---|
| Research question | Are the fault probabilities calibrated on programs and faults the parameters never saw, including human-written bugs; does a size-aware prior or post-hoc recalibration help; and does the posterior identify the cases where the top-ranked statement is right? |
| State of the art | Calibration is studied for code LLMs (Spiess et al.) and neural classifiers (Guo et al.); confidence-based filtering exists for an LLM localiser (Kang et al.). No calibration study of classical localisers was found |
| Evidence for the gap | Review §12: searches; Barinel and all combination studies report ranking metrics only |
| Falsifiable hypothesis | H4: the size-aware prior lowers Brier score and ECE. H5: confidence from the posterior gives a smaller area under the risk-coverage curve than confidence derived from Ochiai. H6: with parameters estimated only on injected faults, the Brier skill score on human-written bugs stays above zero |
| Change | Prior `mu / n`; a two-parameter recalibration of posterior log-odds fitted on other programs; an abstention rule |
| New | The evaluation itself; the methods are standard |
| Practical value | A user, or a repair tool, can decide when to trust the localiser |
| Data, compute | Same as A; nested leave-one-program-out for recalibration |
| Baselines | Base rate; logistic regression (calibrated by construction on its training distribution); Ochiai mapped to a confidence |
| Metrics | Brier score, skill score against the base rate, log loss, ECE with its table, risk-coverage curve and its area |
| Risks | Only 31 human-written bugs are available: intervals will be wide |
| Effort | Low to medium |
| Refutation | Skill score at or below zero under shift; posterior confidence no better than Ochiai-based confidence |

### Candidate C: dependence-structured exposure, "soft slicing" (gap G10)

Make the exposure rate depend on the structural relation between a statement and the statement
that ended the test (same statement, control ancestor, data ancestor, outside the slice), learned
from data, so that plain coverage and hard slicing are both special cases.

| Item | Content |
|---|---|
| Hypothesis | Recovers the 14-point loss of hard slicing and adds a small gain |
| Evidence | Version 2.0.0: without omission faults, slicing changed 2 of 34 programs, +0.01 Top-1, not significant |
| New | Little: SmartFL and the PPDG model program semantics far more deeply |
| Risk | Expected effect close to zero on programs this small; more parameters |
| Refutation | No gain over coverage scopes |

### Candidate D: exact inference that scales with coverage classes (gap G11)

Group statements with identical coverage and enumerate fault *counts* per group.

| Item | Content |
|---|---|
| Value | Removes the 22-statement limit when many statements share coverage |
| Evidence of need | None in reach: the largest program in either benchmark has 18 statements |
| Risk | Cannot be validated on real data; adds code without changing any result |

### Candidate E: type-checker evidence, following the base paper (gap G9)

Run a Python type checker and feed its diagnostics in as evidence.

| Item | Content |
|---|---|
| Hypothesis | Type diagnostics help localise faults |
| Evidence against | The base paper's own Table 3: type-correct programs still fail tests in 18 to 70% of cases. In version 2.0.0, pylint's behavioural findings flagged no faulty line in 624 mutants |
| Decision | Not as an evidence channel. Instead *measure* how many faults show any compile-time or analyser symptom (E7), which is the quantitative link to the base paper |

## 3. Ranking

| Rank | Candidate | Evidence for gap | Feasibility | Technical depth | Expected contribution | Decision |
|---|---|---|---|---|---|---|
| 1 | A fusion | Strong (explicitly requested in the literature) | High | Medium: likelihood design, dependence treatment | A real second evidence source and a fair model-versus-learner comparison | **Primary** |
| 2 | B calibration and abstention | Strong (nothing found) | High | Medium: nested validation, shift | Makes the value of probabilities measurable | **Complementary 1** |
| 3 | external human-written bugs (part of A and B) | Deficiency, not a gap | Medium | Low | Removes the largest threat to validity | **Required for A and B** |
| 4 | C soft slicing | Weak | Medium | Medium | Likely null | Not selected |
| 5 | D lifted inference | None | Medium | Medium | No effect on results | Not selected |
| 6 | E type-checker channel | Negative | High | Low | Likely null | Replaced by measurement E7 |

Complexity was not a criterion: C and D are the most intricate and are rejected.
Only **one** complementary improvement is selected; the size-aware prior belongs to it.

## 4. Selected work

**Primary (A).** Mutation-analysis evidence as a coverage-conditioned likelihood factor in the
Bayesian network, compared with averaging and with logistic fusion.

**Complementary (B).** Size-aware prior, post-hoc recalibration, selective localisation, all
evaluated out-of-fold and under synthetic-to-real shift.

**Evaluation infrastructure required by both.** Barinel, Metallaxis, MUSE, hybrid average and two
logistic baselines; QuixBugs as an external benchmark; support for nested functions and generators.

## 5. Pre-registered evaluation protocol

### Datasets

| ID | Content | Role |
|---|---|---|
| D1 | The project's benchmark: 594 detected single-fault mutants of 34 programs | In-distribution, leave-one-program-out |
| D2 | QuixBugs: the human-written bug of each program that has JSON tests and whose bug the tests detect (at most 31) | External; parameters come from D1 only ("transfer") |
| D3 | Mutants of the correct QuixBugs programs, at most 15 per program, sampled with the project seed | External programs, injected faults; also the training set for the "in-suite" variant of D2 |

Exclusions are reported with reasons: programs without JSON tests, tests on which the reference
program fails or exceeds the step limit, bugs the tests do not detect, runs that hit the time limit.

### Methods

| Name | Description |
|---|---|
| `ochiai`, `tarantula` | As in version 2.0.0 |
| `barinel` | Candidate-based Bayesian localiser with maximum-likelihood health (paper 2), exhaustive minimal hitting sets up to size 3 |
| `metallaxis`, `muse` | Mutation-based, as defined in paper 3 §III-A |
| `hybrid_avg` | Mean of Ochiai and Metallaxis, in the spirit of paper 3's MCBFL-hybrid-avg (their coverage adjustment of mutants is not reproduced) |
| `lr_spectrum` | Logistic regression on spectrum features |
| `lr_fusion` | Logistic regression on spectrum, mutation and static features |
| `pcg` | Version 2.0.0 model, unchanged |
| `pcg_size` | `pcg` with the size-aware prior |
| `pcg_fused` | `pcg_size` plus mutation evidence with coverage context: **the proposed model** |
| `pcg_fused_nocontext` | Ablation: mutation evidence without context conditioning |
| `pcg_fused_const` | Ablation: mutation evidence with the constant prior |
| `pcg_fused_recal` | `pcg_fused` after recalibration (probabilities only; the ranking cannot change) |

Every trained method uses the same training programs in every fold. No method sees ground truth
of the program it analyses.

### Primary comparisons

| ID | Comparison | Metric | Dataset |
|---|---|---|---|
| P1 | `pcg_fused` versus `pcg_size` | Top-1, MRR | D1, D2 |
| P2 | `pcg_fused` versus `lr_fusion` | Top-1, MRR, Brier score, log loss | D1, D2 |
| P3 | `pcg_fused` versus `hybrid_avg` and versus `metallaxis` | Top-1, MRR | D1, D2 |
| P4 | `pcg_size` versus `pcg` | Brier score, ECE | D1 |
| P5 | `pcg_fused` versus `pcg_fused_nocontext` | log loss, Brier score | D1 |
| P6 | posterior confidence versus Ochiai-based confidence | area under the risk-coverage curve | D1, D2 |

All other numbers are secondary and labelled exploratory. Statistics as in version 2.0.0: the
program is the unit; 95% bootstrap intervals over programs; paired sign-flip test on per-program
mean differences; no multiple-comparison correction, stated wherever p-values appear.

### Known bias and its stress test

On D1 and D3 the analysis mutants are produced by the same operators that injected the fault, so
the exact repair is usually among them. This inflates `metallaxis`, `muse`, `hybrid_avg`,
`lr_fusion` and `pcg_fused` alike. Therefore:

* the comparison that counts for mutation-based methods is D2, where the bugs were written by
  people;
* on D1 a stress test repeats the analysis after removing from the analysis mutants the one whose
  text equals the reference program. This uses ground truth to *remove* information and is
  reported as a stress test, not as a result.

### What would count as failure

| Outcome | Conclusion to be reported |
|---|---|
| `pcg_fused` not better than `pcg_size` on D2 | Mutation evidence does not transfer to human-written bugs in this setting |
| `pcg_fused` clearly worse than `lr_fusion` on ranking and on probabilistic metrics, on D1 and D2 | The generative model adds nothing over a learned combiner |
| Brier skill score at or below zero on D2 | The probabilities are not usable outside the training benchmark |
| Posterior confidence no better than Ochiai-based confidence | The posterior adds no decision value |

## 6. Out of scope

Real LLM evidence (no credentials), BugsInPy and Defects4J (see REFERENCE_VERIFICATION.md), soft
slicing, lifted inference, any change to the repair search. The existing experiments of version
2.0.0 are kept and must reproduce bit for bit.

## 7. Amendments after the first results

The sections above are unchanged from the pre-registered text.

**Post hoc analysis added: two-fault programs.** Hypothesis H3 (conditioning the mutation evidence
on the coverage context lowers the log loss) was refuted on D1, D2 and D3: the ablation without
conditioning had the better probabilities. The proposed explanation is that with exactly one fault,
"not executed by every failing test" is conclusive evidence of innocence, and the unconditioned
table happens to encode it. To test that explanation, the fused models were also run on the 410
two-fault programs of version 2.0.0, where a faulty statement need not be executed by every failing
test. This analysis was not planned, is labelled post hoc wherever it is reported, and does not
change which model is called "proposed": `pcg_fused` remains the pre-registered model, and the
better-performing ablation is reported next to it.

**No other change.** No metric, dataset, exclusion rule or comparison was altered after results
were seen.
