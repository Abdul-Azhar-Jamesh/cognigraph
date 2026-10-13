# Probabilistic Constraint Graphs for Uncertainty-Aware Code Verification

**Course:** 22AIE301 Probabilistic Reasoning
**Type:** Project report, version 3.0.0
**Base paper:** Mündler et al., Type-Constrained Code Generation with Language Models (PLDI 2025)
**Every result below is produced by** `python -m pcg all` **and stored in** `results/`.

---

## Abstract

Type-constrained decoding makes language models produce code that compiles, but the base paper's
own results show that 18% to 70% of such code still fails its tests. For those programs the
questions are *where* the fault is and *how sure* one can be. This project treats them as inference
in a Bayesian network built from the program: one latent fault variable per statement, a noisy-OR
factor per test over the statements it executed, and learned likelihood factors for further
evidence. All parameters are estimated from other programs and inference is exact.

A study with a protocol fixed in advance asks whether this model-based combination of evidence can
match a learned black-box combination, whether its probabilities are trustworthy, and whether
either survives the move from injected faults to bugs written by people. On 594 injected faults,
coverage evidence alone gives the accuracy of Ochiai and Barinel (Top-1 0.55 against 0.54). Adding
evidence from single-edit program variants raises Top-1 to 0.96, or 0.73 when the trivially
repairing variant is withheld, on a par with logistic regression over the same inputs. On 31
human-written bugs from QuixBugs, with every parameter estimated on injected faults only, Top-1
rises from 0.38 to 0.51 (95% interval of the difference: -0.05 to +0.30), while pure mutation-based
localisation falls below coverage-based localisation. The model's probabilities beat the base rate
on the human-written bugs and transfer to unseen programs better than the logistic model's;
post-hoc recalibration helps in distribution and fails under the shift. Two pre-registered
hypotheses were refuted, and the fused model is worse than the simple one when a program contains
two faults. No new algorithm is claimed.

---

## 1. Research question and motivation

**Motivation from the base paper.** Mündler et al. constrain a language model's decoding with a
type system and more than halve compilation errors. Their Table 3 also shows the limit of the idea:
with type constraints, pass@1 on HumanEval synthesis lies between 30.2% and 81.8% depending on the
model. Between 18% and 70% of the programs are well-typed and wrong. Their repair task regenerates
non-compiling code and does not say which statement is at fault. Their constraints are hard: a token
is allowed or forbidden, with no degree of belief.

**This project addresses the complement:** for a program that compiles and fails tests, estimate
for each statement the probability that it is faulty, from evidence that is only probabilistic.

**Research question.** Can a model-based (Bayesian) combination of spectrum and mutation evidence
match a learned black-box combination in fault-localisation accuracy; are its probabilities
calibrated and useful for deciding when to trust the result; and do accuracy and calibration
survive the move from injected faults to human-written bugs?

**Why the question is open.** The literature review (`research/LITERATURE_REVIEW.md`) found that:

* combining evidence families clearly helps, and is done by averaging scores or by learning to
  rank; Zou et al. (2021) list the limits of such black-box combination and ask for alternatives;
* Bayesian fault localisation exists (Barinel, 2009) and outputs probabilities, but no study was
  found that measures whether the probabilities of a classical localiser are calibrated;
* results on injected faults do not predict results on real faults (Pearson et al., 2017);
* calibration of confidence is studied for code language models (Spiess et al., 2025) and
  confidence-based filtering for an LLM-based localiser (Kang et al., 2024), not for
  execution-based localisation.

## 2. Related work and the gap

| Line of work | Representative papers | What it establishes | What it leaves open |
|---|---|---|---|
| Constrained decoding | Mündler et al. 2025 (base paper) | Type constraints remove most compile errors | Semantic faults; uncertainty |
| Spectrum-based localisation | Jones and Harrold 2005; Abreu et al. 2007; Xie et al. 2013 | Good formulas cannot be beaten on single faults with spectra alone | Scores are not probabilities |
| Bayesian localisation | Abreu et al. 2009 (Barinel) | Bayesian reasoning over spectra; optimal ranking for single faults | Quality of the probabilities; other evidence |
| Mutation-based localisation | Papadakis and Le Traon 2015; Moon et al. 2014 | Variants carry diagnostic information | Weak on real faults and unmutable statements |
| Artificial versus real faults | Pearson et al. 2017 | Results do not transfer | Bayesian methods were not covered |
| Combination | Pearson et al. 2017; Zou et al. 2021; Rezaalipour and Furia 2024 | Combination wins, in Java and Python | Black-box, linear, no probabilities |
| Calibration | Guo et al. 2017; Spiess et al. 2025 | How to measure and repair calibration; rescaling may not transfer | Not applied to classical localisers |
| Confidence for localisation | Kang et al. 2024 | Vote-based confidence predicts success of an LLM localiser | Not calibrated; needs a paid model |
| Probabilistic program models | Baah et al. 2008; Nath and Domingos 2016; Zeng et al. 2022 (record only) | Much richer probabilistic localisers exist | Outside this project's scope |

**The gap addressed** is therefore not "a probabilistic localiser" (that exists) but: a white-box
probabilistic *fusion* of two evidence families, evaluated against the learned alternative for
ranking, calibration and abstention, in distribution and under a shift to human-written bugs. The
searches behind the statement "not found" are listed in the literature review, section 12; it is a
search-limited statement.

## 3. Mathematical formulation

Full derivations and two worked examples: `docs/MATHEMATICAL_MODEL.md` and
`research/MATHEMATICAL_DESIGN.md`.

**Variables.** `F_i in {0,1}`: statement `i` is faulty (latent). `Theta`: probability that an
executed fault makes a test fail (latent, ten-point grid). `T_j`: test `j` passes or fails
(observed). `A_i`: pylint attaches a behavioural finding to statement `i` (observed). `M_i`: what
the single-edit variants of statement `i` do to the tests, in five levels (observed). `K_i`: whether
all, some or none of the failing tests executed statement `i` (computed from coverage).

**Joint distribution.**

```
P(F, Theta, T, A, M | K) = P(Theta) · Π_i [ P(F_i) P(A_i | F_i) P(M_i | F_i, K_i) ] · Π_j P(T_j | F_{S_j}, Theta)
```

**Test factor (noisy-OR).** `P(T_j = pass | F, Theta) = (1 − λ)(1 − Theta)^{k_j}`, with `k_j` the
number of faulty statements among those test `j` executed.

**Prior.** Version 2: one constant `π`. Version 3: `π_n = min(μ / n, 1/2)` for a program of `n`
statements.

**Mutation factor.** A learned table `P(M_i | F_i)` for statements that every failing test
executed; likelihood ratio exactly 1 otherwise, because a variant of a statement that a failing
test does not execute cannot change that test.

**Inference.** The per-statement factors fold into an effective prior by Bayes' rule in odds form.
The test factors couple the statements (explaining away), so the posterior is computed by exact
enumeration of all fault configurations for each grid point of `Theta`, in log space.

**Estimation.** Counting with add-one smoothing on labelled faults of other programs; the weights
of the `Theta` grid by EM for a mixture of binomials.

**Estimated values** (pooled; each program is analysed with values that exclude it): `π = 0.124`,
`λ = 0.0006`, pooled `θ = 0.635`, `μ = 1`; likelihood ratios of the five mutation levels: 0.78,
0.023, 0.048, 0.27, 162.

## 4. Architecture and implementation

```
program.py ──► execution.py (_runner.py) ──► static_analysis.py ──► dependence.py ──► mbfl.py
                                   │
                                   ▼
                              graph.py   constraint graph ──► Bayesian network
                                   ▼
     estimation.py, fusion.py ─► model.py   exact inference
                                   ▼
                             analysis.py ──► ranking, abstention ──► repair.py
```

About 6,600 lines of Python and 190 automated tests. Dependencies: numpy, networkx, matplotlib,
pylint, pytest. Analysed code runs in a child process under a line tracer with a step limit.
Results folders are emptied at the start of a run and receive a manifest with file hashes only at
the end. The version-2 code paths are untouched: all 22 result files of version 2 are reproduced
bit for bit by version 3.

## 5. Experimental setup and datasets

| ID | Content | Size | Role |
|---|---|---|---|
| D1 | The project's benchmark: 34 small programs, single-edit mutants from ten operators | 624 valid, 594 detected | In distribution, leave-one-program-out |
| D2 | QuixBugs (Lin et al., 2017): one human-written single-line bug per program | 31 programs, all detected | External; all parameters from D1 |
| D3 | 15 sampled mutants of each correct QuixBugs program | 402 valid, 382 detected | External programs, injected faults; parameters from D1 |

Every learned quantity (model parameters, mutation tables, regression weights, recalibration map)
is fitted without the program under analysis. For QuixBugs, a test is kept only if the benchmark's
correct program reproduces the benchmark's expected output (231 of 242 tests). Nine QuixBugs
programs that need object-graph inputs are excluded. BugsInPy and Defects4J were examined and not
used (`research/REFERENCE_VERIFICATION.md`).

## 6. Baselines and metrics

| Baseline | Why it is included |
|---|---|
| Ochiai, Tarantula | The standard spectrum formulas |
| Barinel | The established Bayesian localiser; the closest prior model |
| Metallaxis, MUSE | The standard mutation-based formulas |
| Hybrid average | The simple way of combining the two families (after Pearson et al.) |
| Logistic regression, spectrum features | A learned, calibrated model on the same evidence as the spectrum-only model |
| Logistic regression, all features | The learned black-box fusion: the main competitor |
| PCG v2; ablations of the fused model | To attribute effects to components |

Ranking metrics: Top-1, Top-3, mean reciprocal rank (MRR), with ties scored by expectation.
Probability metrics: Brier score, skill against the base rate `1/n`, log loss, expected calibration
error (ECE). Decision metric: area under the risk-coverage curve (AURC). Uncertainty: 95% bootstrap
intervals over programs; paired sign-flip permutation test on per-program means; no correction for
multiple comparisons.

## 7. Results

### 7.1 Ranking (Top-1 and MRR, 95% intervals)

| Method | D1 Top-1 | D1 stress Top-1 | D2 Top-1 | D2 MRR |
|---|---|---|---|---|
| Ochiai | 0.538 [0.486, 0.592] | 0.538 | 0.376 [0.260, 0.509] | 0.565 [0.474, 0.665] |
| Barinel | 0.538 [0.488, 0.591] | | 0.381 [0.266, 0.512] | 0.570 [0.479, 0.669] |
| Metallaxis | 0.748 [0.679, 0.815] | 0.549 | 0.305 [0.182, 0.441] | 0.501 [0.399, 0.609] |
| Hybrid average | 0.780 [0.717, 0.840] | 0.602 | 0.309 [0.185, 0.444] | 0.513 [0.414, 0.620] |
| Logistic fusion | 0.959 [0.940, 0.976] | 0.771 | 0.575 [0.403, 0.742] | 0.699 [0.572, 0.819] |
| PCG v2 | 0.547 [0.494, 0.600] | | 0.381 [0.266, 0.512] | 0.562 [0.465, 0.663] |
| **PCG fused** | 0.957 [0.934, 0.975] | 0.729 | 0.511 [0.339, 0.672] | 0.666 [0.543, 0.782] |
| PCG fused, no context | 0.958 [0.937, 0.976] | | 0.575 [0.414, 0.737] | 0.706 [0.584, 0.822] |

"D1 stress" removes from the mutation analysis the variant that restores the reference program. D1
without the stress test is inflated for all mutation-based methods: for 492 of 594 injected faults
the exact repair is among the variants, against 5 of 31 human-written bugs.

Paired differences on D2: fused minus spectrum-only, Top-1 +0.130 [-0.050, +0.301] (p = 0.16), MRR
+0.104 [-0.013, +0.220] (p = 0.09); fused minus logistic fusion, MRR -0.033 [-0.113, +0.032]; fused
minus Metallaxis, MRR +0.165 [+0.013, +0.312]. With parameters from mutants of the other QuixBugs
programs: fused minus spectrum-only MRR +0.123 [+0.014, +0.232] (p = 0.04).

### 7.2 Probabilities

| Method | D1 Brier | D1 ECE | D2 Brier | D2 skill | D2 log loss | D3 Brier |
|---|---|---|---|---|---|---|
| Base rate 1/n | 0.1069 | 0.000 | 0.1121 | 0.000 | 0.380 | 0.1078 |
| Logistic fusion | 0.0141 | 0.009 | 0.0918 | +0.181 | 0.410 | 0.0288 |
| PCG v2 | 0.0739 | 0.053 | 0.0973 | +0.132 | 0.335 | 0.0933 |
| **PCG fused** | 0.0145 | 0.045 | 0.0872 | +0.222 | 0.316 | 0.0200 |
| PCG fused, recalibrated | 0.0095 | 0.005 | 0.0878 | +0.217 | 0.413 | 0.0169 |

Paired Brier difference, fused minus logistic fusion: D1 +0.0004 [-0.0025, +0.0036]; D2 -0.0046
[-0.0224, +0.0122]; D3 -0.0088 [-0.0135, -0.0048].

### 7.3 Selective localisation

Answering only the most confident cases, AURC on D1: largest posterior 0.251, Ochiai gap 0.312,
largest Ochiai score 0.362; difference posterior minus gap -0.061 [-0.106, -0.030]. On D2: 0.374,
0.424, 0.574; posterior minus gap -0.050 [-0.161, +0.015].

Figures: `results/research/fig_fusion_ranking.png`, `fig_fusion_reliability.png`,
`fig_risk_coverage.png`.

## 8. Ablation and sensitivity

| Component or setting | Effect |
|---|---|
| Latent exposure rate (version 2) | Top-3 0.845 to 0.900; log loss 0.406 to 0.271 |
| Mutation evidence | D1 Top-1 +0.409; stress test +0.182; D2 +0.130 (interval includes 0) |
| Coverage-context conditioning of the mutation factor | **Harmful**: Brier +0.0055 (D1), +0.0076 (D2), +0.0041 (D3), all intervals above 0 |
| Size-aware prior | Brier +0.0003 overall; ECE 0.047 to 0.033 for programs of 9 to 16 statements, 0.060 to 0.077 for 4 to 5 |
| Recalibration | D1: ECE 0.045 to 0.005; D2: log loss 0.316 to 0.413 |
| Exact-repair variant removed | Fused Top-1 0.957 to 0.729; logistic fusion 0.959 to 0.771; Metallaxis 0.748 to 0.549 |
| Where parameters come from (D2) | From D1: fused Top-1 0.511; from QuixBugs mutants: 0.551 |
| Hand-set parameters (version 2, 29 settings) | Top-1 between 0.483 and 0.557 |
| Static evidence (version 2) | Top-1 +0.008; pylint never flags the faulty line |
| Dependence slicing (version 2) | Top-1 -0.141; blind to deleted statements |
| By fault category (D1, MRR) | Fusion gains most for boundary faults (0.459 to 1.000) and least for arithmetic ones (0.751 to 0.878) |

## 9. Negative results

1. **Coverage-context conditioning (hypothesis H3) was refuted.** It was designed to avoid counting
   coverage twice. Ignoring it gives better probabilities on every dataset and better ranking on
   human-written bugs. The pre-registered model keeps the conditioning and is reported as such.
2. **The size-aware prior (H4) made no overall difference.**
3. **The explanation offered for (1) was tested and failed too.** Conditioning was expected to help
   when a program has two faults. On 410 two-fault programs the unconditioned variant is better
   there as well.
4. **The fused model is harmful with two faults.** Both faults are in the top three for 19.8% of
   programs against 35.9% for the model without mutation evidence. The mutation tables are learned
   from single faults, where "no variant fixes a failing test" means innocence; with a second fault
   that inference is false.
5. **Mutation-only localisation does worse than coverage-only localisation on human-written bugs**
   (Top-1 0.305 against 0.376), as Pearson et al. found on Defects4J.
6. **The simple hybrid average also does worse than Ochiai on human-written bugs** (0.309).
7. **Recalibration fitted on injected faults does not transfer** to human-written bugs.
8. **Logistic fusion beats the model-based fusion in the stress test** (Top-1 0.771 against 0.729,
   interval of the difference excludes 0).
9. From version 2: dependence slicing hurts; static analysis carries no information; a fixed
   exposure rate gives probabilities worse than the base rate.

## 10. Limitations and threats to validity

Details in `docs/LIMITATIONS.md`. The most important:

* **Circular mutation evidence on injected faults.** Mitigated by the stress test and by D2, not
  removed.
* **Only 31 human-written bugs**, from a programming challenge, not from software projects. Most
  comparisons on D2 are not significant.
* **Single-fault assumption** of the mutation tables (negative result 4).
* **The dependence between mutation and coverage evidence is not understood** (negative results 1
  and 3).
* **Small programs, exact inference** limited to about 22 executed statements.
* **No state-of-the-art localiser** in the comparison; logistic regression stands in for
  learning-to-rank combination.
* **No real LLM evidence.**
* **Cost:** mutation analysis executes about 23 variants per faulty program.
* **D1 was seen before the research hypotheses were written;** D2 and D3 were not.

## 11. Reproducibility

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
git clone --depth 1 https://github.com/jkoppel/QuixBugs.git ..\QuixBugs
python -m pytest
python -m pcg all
```

Seed 20261013. Version-2 results: three identical runs (all 22 file hashes). Research results: two
runs compared (`docs/FINAL_AUDIT.md`). Environment, artefacts and troubleshooting:
`docs/REPRODUCIBILITY.md`.

## 12. Claims supported by the evidence

**Claimed.**

1. A noisy-OR Bayesian network over statement faults, with exact inference and estimated
   parameters, localises single faults from coverage as well as Ochiai and Barinel on three
   datasets, and not better.
2. Mutation evidence can be added to that network as a learned likelihood factor without changing
   inference, and the resulting ranking is on a par with logistic regression on the same inputs for
   injected faults.
3. On injected faults the fused model's probabilities are as accurate as the logistic model's by
   Brier score and less well calibrated; on unseen programs with injected faults they are more
   accurate.
4. With parameters estimated only on injected faults, the model's probabilities remain better than
   the base rate on 31 human-written bugs.
5. The posterior identifies the cases in which the top-ranked statement is correct better than
   Ochiai-derived confidence does, on injected faults.

**Suggested by the data, not established** (31 bugs): that mutation evidence improves localisation
of human-written bugs within this model; that the fused model's probabilities are more robust than
the logistic model's on human-written bugs; that posterior confidence beats the Ochiai gap there.

**Not claimed.** A new algorithm; an advantage over learned fusion in ranking; validity for several
simultaneous faults, for real software projects, for larger programs or for language-model
evidence.

## 13. Conclusion and future work

The project now answers its question with evidence. A Bayesian network over statement faults is a
workable frame for combining evidence: it matches a learned combiner on ranking and its
probabilities degrade more gracefully on unseen programs. It is not a better localiser, its most
principled refinement did not survive testing, and it fails when its single-fault training
assumption is broken.

Future work, in order of value: (1) learn the mutation tables on multi-fault programs, or make the
table depend on the number of failing tests left unexplained; (2) evaluate on a real-project
benchmark such as BugsInPy, which needs approximate inference; (3) collect real LLM confidence and
fit its likelihood; (4) model the dependence between tests and between evidence sources explicitly
instead of by conditioning rules.

## References

† = bibliographic record checked during this project; ‡ = also read in full. Details and sources:
`research/REFERENCE_VERIFICATION.md`.

1. ‡ Abreu, R., Zoeteweij, P., van Gemund, A. J. C. (2009). Spectrum-based multiple fault
   localization. *ASE 2009*, pp. 88-99.
2. † Abreu, R., Zoeteweij, P., van Gemund, A. J. C. (2007). On the accuracy of spectrum-based fault
   localization. *TAICPART-MUTATION 2007*, pp. 89-98.
3. † Baah, G. K., Podgurski, A., Harrold, M. J. (2008). The probabilistic program dependence graph
   and its application to fault diagnosis. *ISSTA 2008*, pp. 189-200.
4. Brier, G. W. (1950). Verification of forecasts expressed in terms of probability. *Monthly
   Weather Review*, 78(1), 1-3.
5. Dempster, A. P., Laird, N. M., Rubin, D. B. (1977). Maximum likelihood from incomplete data via
   the EM algorithm. *JRSS B*, 39(1), 1-38.
6. Efron, B. (1979). Bootstrap methods: another look at the jackknife. *Annals of Statistics*, 7(1),
   1-26.
7. ‡ Guo, C., Pleiss, G., Sun, Y., Weinberger, K. Q. (2017). On calibration of modern neural
   networks. *ICML 2017*, PMLR 70.
8. Jones, J. A., Harrold, M. J. (2005). Empirical evaluation of the Tarantula automatic
   fault-localization technique. *ASE 2005*.
9. ‡ Kang, S., An, G., Yoo, S. (2024). A quantitative and qualitative evaluation of LLM-based
   explainable fault localization. *FSE 2024*. doi:10.1145/3660771.
10. Kschischang, F. R., Frey, B. J., Loeliger, H.-A. (2001). Factor graphs and the sum-product
    algorithm. *IEEE Trans. Information Theory*, 47(2), 498-519.
11. ‡ Lin, D., Koppel, J., Chen, A., Solar-Lezama, A. (2017). QuixBugs: a multi-lingual program
    repair benchmark set based on the Quixey Challenge. *SPLASH Companion 2017*.
    doi:10.1145/3135932.3135941.
12. Moon, S., Kim, Y., Kim, M., Yoo, S. (2014). Ask the mutants: mutating faulty programs for fault
    localization. *ICST 2014*. (Not verified; cited via reference 16.)
13. ‡ Mündler, N., He, J., Wang, H., Sen, K., Song, D., Vechev, M. (2025). Type-constrained code
    generation with language models. *Proc. ACM Program. Lang.* (PLDI). doi:10.1145/3729274.
14. † Nath, A., Domingos, P. (2016). Learning tractable probabilistic models for fault localization.
    *AAAI 2016*. doi:10.1609/aaai.v30i1.10175.
15. † Papadakis, M., Le Traon, Y. (2015). Metallaxis-FL: mutation-based fault localization.
    *Software Testing, Verification and Reliability*, 25, 605-628. doi:10.1002/stvr.1509.
16. ‡ Pearson, S., Campos, J., Just, R., Fraser, G., Abreu, R., Ernst, M. D., Pang, D., Keller, B.
    (2017). Evaluating and improving fault localization. *ICSE 2017*, pp. 609-620.
    doi:10.1109/ICSE.2017.62.
17. Pearl, J. (1988). *Probabilistic Reasoning in Intelligent Systems*. Morgan Kaufmann.
18. ‡ Rezaalipour, M., Furia, C. A. (2024). An empirical study of fault localization in Python
    programs. *Empirical Software Engineering*, 29(4), article 92.
19. ‡ Spiess, C., Gros, D., Pai, K. S., Pradel, M., Rabin, M. R. I., Alipour, A., Jha, S., Devanbu,
    P., Ahmed, T. (2025). Calibration and correctness of language models for code. *ICSE 2025*.
    arXiv:2402.02047.
20. † Xie, X., Chen, T. Y., Kuo, F.-C., Xu, B. (2013). A theoretical analysis of the risk evaluation
    formulas for spectrum-based fault localization. *ACM TOSEM*, 22(4), article 31.
21. † Zeng, M., Wu, Y., Ye, Z., Xiong, Y., Zhang, X., Zhang, L. (2022). Fault localization via
    efficient probabilistic modeling of program semantics. *ICSE 2022*.
22. ‡ Zou, D., Liang, J., Xiong, Y., Ernst, M. D., Zhang, L. (2021). An empirical study of fault
    localization families and their combinations. *IEEE TSE*, 47(2), 332-347.
    doi:10.1109/TSE.2019.2892102.

Unmarked entries are standard works cited from memory of their bibliographic details; check volume
and pages before formal submission.

Software: Python 3.12.3; numpy 2.2.5; networkx 3.5; matplotlib 3.10.5; pylint 4.1.3; pytest 9.1.1;
pgmpy 1.1.2 (cross-check only). Benchmark: QuixBugs, commit 4257f44 (MIT licence).
