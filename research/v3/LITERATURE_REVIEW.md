# Literature review

Nine papers were read in full: the base paper and eight others. Seven further works were checked
by bibliographic record and abstract only; they are listed separately in section 11 and are never
quoted as if they had been read. Publication records are in
[REFERENCE_VERIFICATION.md](REFERENCE_VERIFICATION.md).

Three kinds of statement are kept apart for every paper:

* **A. Stated limitations**: what the authors themselves say.
* **B. Inferred gaps**: weaknesses that follow from the method or the evidence, in my reading.
* **C. Still open**: whether later work, as far as my searches show, has closed the gap.

"Project" below means this repository at version 2.0.0 (the baseline of
[BASELINE.md](BASELINE.md)).

---

## 1. Base paper: Mündler, He, Wang, Sen, Song, Vechev. Type-Constrained Code Generation with Language Models (PLDI 2025)

| Item | Content |
|---|---|
| Problem | LLMs generate code token by token with no formal guarantee; much of the output does not compile. Constrained decoding existed only for syntax (§1) |
| Contribution | Type-constrained decoding: a *prefix automaton* that accepts exactly the prefixes that can be completed to a well-typed program, plus a *type reachability search* that decides whether a partial expression can still reach a required type (§3). Formalised on a simply typed language `L_B`, extended to a TypeScript subset (§4) |
| Formal model | Algorithm 1: sample a token, keep it only if the completion engine accepts the extended prefix. Definition 1 (prefix language), Definition 2 (prefix property), Lemma 1 (for a prefix automaton the reachable language equals the prefix language), Lemma 2 (derivable types). Typing rules in Figures 5 to 7 |
| Guarantees and assumptions | Sound: an accepted complete program is well-typed. **Incomplete**: the type search is cut off to guarantee termination, so some well-typed programs cannot be generated (§3.2, §3.4). Needs the model's next-token distribution |
| Data | HumanEval (159 instances) and MBPP (384) in TypeScript from MultiPL-E; six open-weight models from 2B to 34B parameters; three tasks: synthesis, translation, repair of non-compiling code (§5.1) |
| Metrics, baselines | Number of compiler errors; pass@1. Baselines: unconstrained decoding, idealised syntax-only constraining |
| Findings | 94% of compilation errors are type errors, 6% syntax errors (§1). Compiler errors in synthesis fall by 74.8% (HumanEval) and 56.0% (MBPP) (Table 2). pass@1 rises on average by 3.5% (synthesis), 5.0% (translation), 37.0% (repair) (§5.2). Median runtime rises by 39.1% and 52.1% (§5.3) |

**A. Stated limitations (§6).** A completion engine must be written by hand for each language.
Commercial APIs do not expose token distributions. Compiler errors remain when a constrained
generation loops until the token or time limit. Only a subset of TypeScript is supported (Tables 5
and 6), and full support is emulated by resampling only the samples that failed to compile (§5.1).

**B. Inferred gaps.**

1. *Well-typed is not correct.* Table 3 shows that after type constraining, pass@1 on HumanEval
   synthesis ranges from 30.2% (Gemma 2 2B) to 81.8% (Qwen2.5 32B). So between about 18% and 70%
   of the generated programs compile and still fail their tests. The method has nothing to say
   about these: it neither localises the semantic fault nor quantifies how likely the program is
   to be wrong.
2. *Repair means regeneration.* The repair task re-generates the function from the compiler
   message. It does not identify which statement is wrong and it is only defined for
   non-compiling code.
3. *Constraints are hard and binary.* A token is either allowed or forbidden. There is no notion
   of degree of belief, and no use of evidence that is only probabilistic, such as test outcomes.

**C. Still open?** The complement of this paper, deciding *where* a compiling program is wrong and
*how sure* one can be, is the subject of fault localisation (papers 2 to 5, 8) and of calibration
research (papers 7, 9). It is not addressed by type constraints.

**Relation to the project.** Already implemented: compiler diagnostics as a hard gate, which is the
post-hoc analogue of the paper's hard constraint. Transferable idea: treat program-analysis
artefacts as *constraints*, hard where they are certain (compilation) and probabilistic where they
are not (tests, analyser warnings). Not transferable: the decoding algorithm itself, which needs
token-level access to a model. Cost of going further in the paper's own direction (a Python type
checker as an evidence channel): low; expected benefit on semantic faults: near zero, for the same
reason as gap 1.

---

## 2. Abreu, Zoeteweij, van Gemund. Spectrum-based Multiple Fault Localization (ASE 2009): "Barinel"

| Item | Content |
|---|---|
| Problem | Similarity coefficients (Tarantula, Ochiai) do not reason about several simultaneous faults (§II) |
| Contribution | Bayesian reasoning over *diagnosis candidates* (sets of faulty components) generated as minimal hitting sets of the failing runs by the heuristic STACCATO; an *intermittent* component model with health `h_j`; maximum-likelihood estimation of `h_j` per candidate (§III) |
| Formal model | Prior `Pr(d) = p^|d| (1-p)^(M-|d|)`. Per run: `Pr(pass | d) = prod of h_j` over the candidate's components the run executed, `Pr(fail | d) = 1 - prod h_j` (Eq. 5). `h` chosen to maximise `Pr(e | d)` by gradient ascent (§III-C). Worked example: `Pr(e|d1) = 0.185` with `h1 = 0.47, h2 = 0.19`; posteriors 0.839 and 0.161 |
| Assumptions | Components fail independently. No leak: a candidate that does not cover a failing run has probability 0. Candidate list truncated at 100 |
| Guarantee | Theorem: for single faults the ranking is optimal; the proof reduces the score to a monotone function of `n10/n11` (§V-B) |
| Data | Synthetic spectra; Siemens suite, gzip, sed, space; 128 single-fault versions; multiple faults by activating combinations |
| Findings | Single faults: 60% of faults found within 10% of the code, against 52% (Ochiai) and 46% (Tarantula). Multiple faults: better in 27 of 30 settings |

**A. Stated limitations and future work (§VII).** Binary activity only (future: execution counts);
slow gradient ascent; other kinds of spectra not studied.

**B. Inferred gaps.** (1) The output is a ranked list of candidates with posterior probabilities,
but the *quality of those probabilities* is never evaluated: no calibration, no proper scoring
rule. (2) `h_j` is maximised separately for each candidate, which favours candidates that can fit
the data with an extreme `h`; there is no prior over `h`. (3) Only spectrum evidence is used.
(4) All faults are seeded.

**C. Still open?** (4) was answered by Pearson et al. (paper 3): results on seeded faults do not
predict results on real faults. (3) was taken up by combination studies (papers 4, 5) with
non-probabilistic rankers. For (1), my searches found no evaluation of the calibration of Barinel
or any other classical fault localiser (section 12).

**Relation to the project.** The project's model is of this family: noisy-OR with an intermittency
parameter. Differences: exact marginals over all fault sets instead of a candidate list; the
exposure rate is integrated under a learned prior instead of maximised; a leak term; learned
per-statement evidence. Barinel was *not* among the project's baselines. Transferable: Barinel
itself as the established Bayesian baseline (cost: low, it is a few formulas).

---

## 3. Pearson, Campos, Just, Fraser, Abreu, Ernst, Pang, Keller. Evaluating and Improving Fault Localization (ICSE 2017)

| Item | Content |
|---|---|
| Problem | Fault localisation had been evaluated almost only on artificial faults. Do those results hold on real faults? |
| Contribution | Replication of 10 published claims on 2,995 artificial and 310 real faults (Defects4J); a design space of techniques; new hybrid techniques (§VI, §VII) |
| Techniques | SBFL: Tarantula, Ochiai, Op2, Barinel (as the formula `1 - passed/(passed+failed)`), DStar. MBFL: MUSE and Metallaxis (§III-A). Metallaxis scores a mutant by the Ochiai formula over the tests whose outcome it changes and takes the maximum over a statement's mutants; MUSE uses failing-to-passing and passing-to-failing counts and averages |
| Metrics | EXAM score; best, worst and average case for ties; for faults of omission, any of a set of candidate insertion points counts (§II-A) |
| Findings | On artificial faults 7 of 10 earlier claims hold. On real faults every claim is refuted or insignificant (abstract). Metallaxis is best on artificial faults and worse than SBFL on real ones; MUSE does poorly on real faults because almost none can be reversed by one mutant (§V). 10% of real faults sit in statements that cannot be mutated. Hybrid of mutation and coverage (MCBFL-hybrid-avg) puts the fault in the top 5 for 36% / 19% / 23% of faults (best / worst / average case) against 30% / 17% / 18% for DStar (Table VIII) |

**A. Stated limitations (§VIII).** One benchmark (Defects4J); EXAM may not reflect usefulness to
people; results may not carry over to slice-based or model-based techniques.

**B. Inferred gaps.** (1) The hybrids combine scores by averaging or taking a maximum, with no
model of how much each source should count. (2) Scores are not probabilities; nothing tells a
user when to trust the top of the list. (3) Model-based (Bayesian) techniques were explicitly not
covered by the artificial-versus-real comparison.

**C. Still open?** (1) Zou et al. (paper 4) replaced averaging by learning to rank, still without a
model. (3) remains open as far as I found: no study compares a Bayesian localiser on artificial
and real faults.

**Relation to the project.** The project's benchmark is exactly the kind this paper warns about.
Transferable: evaluate on faults that were not injected; add mutation-based evidence; add the
hybrid as a baseline; adopt the candidate-location rule for faults of omission.

---

## 4. Zou, Liang, Xiong, Ernst, Zhang. An Empirical Study of Fault Localization Families and Their Combinations (IEEE TSE 2021)

| Item | Content |
|---|---|
| Problem | Techniques from different families had not been compared or combined on real faults |
| Contribution | 11 techniques from 7 families on 357 Defects4J faults; correlation between techniques; combination by learning to rank ("CombineFL"); run-time cost (§3) |
| Method | Each technique's suspiciousness score is a feature; a learning-to-rank model combines them linearly; 10-fold and cross-project validation (§4.3) |
| Findings | SBFL is the best single family: Ochiai places 16 faults (4%) at top 1 and 156 (44%) in the top 10 (Table 8). Techniques from different families are weakly correlated (Finding 2.2). The combination improves top-1, 3, 5, 10 by 200%, 63%, 46% and 31% over the best single technique and EXAM from 0.033 to 0.0173 (Finding 3.2). Stack traces are best on the 25% of faults that crash (Finding 1.3). Cross-project and within-project validation give similar results (Finding 3.1) |

**A. Stated limitations (§6.5).** The combination treats techniques as black boxes and combines
scores linearly; it cannot reuse intermediate computations; a linear combination may not be
optimal; it needs training, and the effect of the training data is unknown. The authors ask for new
ways of combining techniques.

**B. Inferred gaps.** (1) The combined output is a ranking score with no probabilistic meaning and
no measure of confidence. (2) Dependence between sources is handled only implicitly by the learned
weights.

**C. Still open?** Later systems combine more signals (for example SmartFL, section 11, plugs into
CombineFL), but I found none that reports calibrated probabilities for a combined classical
localiser.

**Relation to the project.** Version 2.0.0 fused only one real extra source (pylint), and it
carried no information. Transferable: combine *informative* families, and compare a model-based
combination against a learned black-box one, which is the alternative §6.5 asks for.

---

## 5. Rezaalipour, Furia. An Empirical Study of Fault Localization in Python Programs (Empirical Software Engineering, 2024)

| Item | Content |
|---|---|
| Problem | Do the Java findings of paper 4 hold for Python? |
| Contribution | Conceptual replication with the tool FauxPy: 7 techniques in 4 families on 135 real bugs from 13 projects of BugsInPy; statement, function and module granularity; combinations |
| Findings | SBFL is the most effective family (Finding 1.1); SBFL and MBFL are similar on most bugs, with a weak effect size of -0.18 in favour of SBFL (Finding 1.4); Metallaxis tends to beat MUSE (1.6); MBFL is the best family on "mutable" bugs (3.9) and loses when its operators do not apply to the faulty statement, which happened for nearly half of the bugs (§6.2); combining all techniques is the most effective and the slowest (4.1, 4.3); most Java findings are confirmed (6.1) |

**A. Stated limitations (§5.7, §6.2).** Ranked-list metrics are an idealisation of debugging; one
curated benchmark; MBFL is expensive and blind where operators do not apply.

**B. Inferred gaps.** Same as papers 3 and 4: no probabilities, no confidence; combination by
averaging or learning to rank.

**C. Still open?** Same as paper 4.

**Relation to the project.** Confirms for Python that mutation evidence is complementary to
spectrum evidence and that its weakness is the unmutable statement. Transferable: a fusion model
should fall back to spectrum evidence exactly where mutation evidence is absent, rather than rank
such statements last.

---

## 6. Lin, Koppel, Chen, Solar-Lezama. QuixBugs: A Multi-Lingual Program Repair Benchmark Set Based on the Quixey Challenge (SPLASH Companion 2017)

| Item | Content |
|---|---|
| Content | 40 classic algorithms in Python and Java, each with a bug on a single line, from the Quixey Challenge (2011 to 2013), in which programmers had one minute to fix the bug |
| Tests | Passing and failing test cases; JSON test cases for most programs, hardcoded ones for programs with graph inputs |
| Defect classes (Table 1) | 14 classes; the largest are variable swap (6), incorrect variable (5), incorrect comparison operator (5), missing or added `+1` (4), missing function call (4), missing line (4) |
| Stated properties | The bugs were written as puzzles for people, by authors who were not thinking of repair tools, which the paper argues lowers the risk of experimenter bias (§2). Correct versions come from the original challenge |

**A. Stated limitations.** Correct versions were not a goal of the authors; graph test cases are
hardcoded.

**B. Inferred limits as a fault-localisation benchmark.** 40 tiny programs; the bugs are
hand-written teaching bugs, not defects from real projects; nine programs need object inputs.

**Relation to the project.** It answers the baseline's weakness "self-written programs with
injected faults" at low cost: Python, MIT licence, single-file programs of the size the exact
inference can handle. It is not a substitute for BugsInPy or Defects4J.

---

## 7. Spiess, Gros, Pai, Pradel, Rabin, Alipour, Jha, Devanbu, Ahmed. Calibration and Correctness of Language Models for Code (ICSE 2025)

| Item | Content |
|---|---|
| Problem | Is a code model's confidence a reliable sign that its output is correct? |
| Tasks, data | Function synthesis (HumanEval, MBPP), line completion (DyPyBench), program repair (Defects4J single-line bugs, ManySStubs4J); GPT-3.5, Codex, CodeGen2 (§III) |
| Measures | Intrinsic (token probabilities) and reflective (verbalised, true/false logit) confidence; Brier score, skill score against the base rate, ECE (Eqs. 4 to 7) |
| Findings | Raw confidence is poorly calibrated for test-passing correctness: ECE between 0.09 and 0.73; best raw skill about 0.05 (§IV-A). Platt scaling brings mean ECE from 0.32 to 0.03 but skill stays small and is absent for repair (§IV-B). Rescaling needs more than 64 labelled points. A rescaling fitted on one task can fail badly on another: skill fell from 0.12 to -1.28 (§IV-B) |
| Use | Calibrated confidence allows graded review effort (§I, §II-B) |

**A. Stated limitations (§VI).** Small datasets; few models and prompts; repair restricted to
pre-localised single-line bugs.

**B. Inferred gaps.** Confidence is per whole output. The paper lists pointing out the
uncertain *parts* of the code as future work: which region is doubtful is not addressed.

**C. Still open?** Partly addressed for LLM-based localisers by paper 8. Not addressed for
execution-based localisation, as far as I found.

**Relation to the project.** Methodological template: report Brier, skill against the base rate and
ECE together; test rescaling; test whether calibration survives a change of data. The warning that
ECE alone can look good for an uninformative predictor applies directly to the baseline table of
version 2.0.0 (the base-rate predictor has ECE 0.0015).

---

## 8. Kang, An, Yoo. A Quantitative and Qualitative Evaluation of LLM-Based Explainable Fault Localization (FSE 2024): "AutoFL"

| Item | Content |
|---|---|
| Approach | An LLM navigates the repository through function calls starting from a failing test and names the faulty *method*; repeated five times; the final ranking aggregates the runs (§3) |
| Confidence | The highest aggregated score, i.e. how consistently the runs agree (Eq. 2) |
| Data | 798 bugs: 353 from Defects4J and 445 from BugsInPy (§4.2.1) |
| Findings | Method-level acc@1 up to 233.3% above baselines (abstract). Confidence correlates with Precision@1: Spearman 0.57 (Defects4J) and 0.52 (BugsInPy) (§5.2). Thresholding confidence predicts correct localisation with a precision-recall AUC of 0.785, rising to 0.812 and 0.827 when test or repair results are added (§6) |

**A. Stated limitations (§7).** Possible training-data leakage; variable cost and timing of a
remote model; developer study on one project.

**B. Inferred gaps.** Confidence is a vote share, not a probability; its calibration is not
measured. Method granularity only. Needs a paid model.

**C. Still open?** Whether a classical, execution-based localiser can provide a confidence that is
both calibrated and useful for abstention.

**Relation to the project.** Establishes that "confidence that predicts localisation success" is a
recognised goal. Transferable: evaluate the project's posteriors the same way (does confidence
separate right from wrong answers?) and compare with confidences derived from Ochiai.

---

## 9. Guo, Pleiss, Sun, Weinberger. On Calibration of Modern Neural Networks (ICML 2017)

| Item | Content |
|---|---|
| Contribution | Shows modern classifiers are miscalibrated; defines the expected calibration error with binning (§2); compares post-hoc methods; proposes temperature scaling, a one-parameter variant of Platt scaling fitted on held-out data (§4.2) |
| Findings | ECE typically 4 to 10% before calibration (§5); temperature scaling is usually the most effective method despite having one parameter; it does not change the ranking of classes |

**A. Stated limitations.** Why accuracy and calibration diverge is left open; results depend on
the binning scheme.

**Relation to the project.** Provides the standard recalibration method and metric. Transferable:
a one- or two-parameter recalibration of the posterior log-odds, fitted on other programs. Because
such a map is monotone, it cannot change a ranking: it can only fix probabilities.

---

## 10. Synthesis across the papers

| Theme | What the literature establishes | Consequence for the project |
|---|---|---|
| Type and compiler constraints | Remove most compile errors; leave 18 to 70% of programs functionally wrong (paper 1) | The project's niche is the residual, semantic fault |
| Bayesian spectrum reasoning | Exists since 2009 and is optimal in ranking for single faults (paper 2) | Parity with good coefficients is expected; novelty cannot be claimed for the model |
| Artificial versus real faults | Results do not transfer (paper 3) | A benchmark of injected faults alone cannot support general claims |
| Combination of families | Clearly beneficial; done by averaging or learning to rank, as black boxes (papers 3, 4, 5) | A model-based, white-box combination is an open alternative the authors of paper 4 ask for |
| Mutation evidence | Complementary to spectra; weak where statements cannot be mutated (papers 3, 5) | Fusion must degrade gracefully to spectrum evidence |
| Calibration | Essential for using confidence; rescaling works in-distribution and can fail under shift (papers 7, 9) | Calibration must be measured on data the parameters did not see, including a different benchmark |
| Confidence for localisation | Useful for filtering results (paper 8), but only vote-based and for LLMs | Posterior-based abstention for a classical localiser is untested |

## 11. Works checked by record only (not read in full)

| Work | Why it matters | Status |
|---|---|---|
| Zeng et al., "Fault Localization via Efficient Probabilistic Modeling of Program Semantics" (ICSE 2022; extended as SmartFL, IEEE TSE 2025) | The strongest probabilistic localiser: models correctness of values along the execution trace. Far richer than a coverage-level model | Abstract and records only |
| Baah, Podgurski, Harrold, "The Probabilistic Program Dependence Graph and Its Application to Fault Diagnosis" (ISSTA 2008; IEEE TSE 2010) | A probabilistic graph over the program dependence graph: the closest earlier work to the *name* of this project | Record only |
| Nath, Domingos, "Learning Tractable Probabilistic Models for Fault Localization" (AAAI 2016) | A joint probabilistic model over per-line fault indicators, trained on other buggy programs | Abstract only |
| Landsberg, Barr, "Doric: Foundations for Statistical Fault Localisation" (arXiv 2018) | Argues scores should be probabilities and defines a likelihood-based measure | Abstract only; peer-reviewed venue not verified |
| Papadakis, Le Traon, "Metallaxis-FL" (STVR 2015) | Original mutation-based technique | Record only; the definition used here is the one given in paper 3, §III-A |
| Moon et al., "Ask the Mutants" (MUSE, ICST 2014) | Original MUSE | Record only; definition from paper 3 |
| Xie, Chen, Kuo, Xu, "A Theoretical Analysis of the Risk Evaluation Formulas for SBFL" (TOSEM 2013) | Proves that the best formulas cannot be beaten for single faults | Abstract and record only |

The existence of SmartFL, the PPDG and the tractable models of Nath and Domingos means that
*probabilistic graphical models for fault localisation are not new*, and that this project's
coverage-level model is not the state of the art in localisation accuracy.

## 12. Searches behind the "still open" statements

A gap is called open only relative to these searches (13 October 2026); this is not a proof of
absence.

| Query | Result |
|---|---|
| calibration of fault localization suspiciousness scores, calibrated confidence, abstain | No study measuring calibration of statement-level fault probabilities for classical localisers |
| "expected calibration error" OR "reliability diagram" OR "Brier score" with "fault localization" | Calibration studies for defect prediction, code LLMs and code review, none for fault localisation scores |
| probabilistic fault localisation (SmartFL, Doric, tractable models, PPDG) | Several probabilistic models; evaluations report ranking metrics |

Found and relevant: AutoFL (paper 8) uses confidence for filtering, for an LLM and without
calibration metrics; a 2025 preprint studies calibration of just-in-time defect prediction, a
different task.
