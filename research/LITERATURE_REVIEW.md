# Literature review, version 4

This review audits and extends the version 3 review ([v3/LITERATURE_REVIEW.md](v3/LITERATURE_REVIEW.md)),
which stays as written. Bibliographic checks are in [REFERENCE_VERIFICATION.md](REFERENCE_VERIFICATION.md).

**How far each source was read** is stated for every entry, because it limits what may be claimed
about it:

* **full**: the paper itself was read (version 3 round).
* **sections**: the full text was obtained and specific sections were read.
* **abstract**: only the abstract or the publisher's page was read. Nothing beyond the abstract is
  asserted.
* **record**: only the bibliographic record was confirmed.

Three kinds of statements are kept apart: **A** a limitation the authors state, **B** a gap I infer,
**C** something I could not find addressed anywhere (a search-limited claim).

## 1. Audit of the version 3 review

| Version 3 claim | Still holds? | What changed |
|---|---|---|
| G1: no white-box probabilistic combination of spectrum and mutation evidence | **Weakened.** | Kang, Choi and Yoo (ISSTA 2023) give a Bayesian framework that covers spectrum formulas, a MUSE-like mutation formula and patch-based updating. I missed it in version 3. Version 3's fusion is therefore closer to prior work than its documents say. What that paper does not do is evaluate the posteriors as probabilities or handle several faults |
| G2: evidence dependent on coverage | Closed by version 3 itself: the proposed conditioning was refuted | |
| G3: calibration of fault probabilities not studied | Holds for classical localisers. A preprint (ConformalFL) now studies calibrated *inspection cutoffs*, a different question | |
| G4: calibration under shift from injected to human-written bugs | Holds; version 3 gave a first small measurement (31 bugs) | |
| G5: confidence for abstention | Holds for non-LLM localisers | |
| G10: richer dependence models exist | Holds, and more strongly: Prosecutor (OOPSLA 2026) adds counterfactual predicate flips to a Bayesian error-propagation model | |
| G11: exact inference does not scale | Holds | |
| "Model-based fusion compared with learned fusion was not found" | Holds as a study; but see G1 | |

Consequence: the novelty statement of version 3 ("no earlier model-based combination found") must
be corrected in the project's documents. It is corrected in RELATED_WORK_AND_NOVELTY.md.

## 2. Sources by area

### A. Spectrum-based localisation and its limits

1. **Pearson et al., ICSE 2017** (full). Results on artificial faults do not predict results on
   real faults; hybrids are score combinations. *A.*
2. **Xie et al., TOSEM 2013** (record). Theoretical ranking of spectrum formulas for single faults.
3. **Widyasari et al., EMSE 2022** (abstract). On BugsInPy, real Python faults are harder for
   spectrum formulas than Defects4J faults, and rankings of formulas from artificial-fault studies
   do not carry over. *A.*
4. **Rezaalipour and Furia, EMSE 2024** (full). Seven techniques on 135 BugsInPy faults;
   combinations win in Python too.

### B. Bayesian and probabilistic diagnosis

5. **Abreu, Zoeteweij and van Gemund, Barinel, ASE 2009** (full). Bayesian reasoning over
   multiple-fault candidates from minimal hitting sets; per-candidate health by maximum likelihood.
   Coverage only. Posteriors are never evaluated as probabilities. *B.*
6. **Kang, Choi and Yoo, "A Bayesian Framework for Automated Debugging", ISSTA 2023** (sections:
   3.3, 3.5, 7). Debugging as inference of the posterior over fault location and repair action.
   Under a single-fault assumption the framework recovers maximal spectrum formulas and, in an
   appendix, a mutation formula similar to MUSE; it re-derives the patch-based update of unified
   debugging. **Stated limitation (A):** the single-fault assumption is called a major limitation;
   reasoning over sets of faults needs `O(2^n)` combinations, and whether Barinel's candidate
   heuristic scales to debugging in general is left open.
7. **Zeng et al., SmartFL, ICSE 2022; journal version TSE 2025** (abstract). Probabilistic model
   of whether program *values* are correct, on a factor graph from static and dynamic analysis.
   Defects4J: 21% Top-1 at statement level in the conference version, 14% on Defects4J 2.0 in the
   journal version. Java.
8. **Baradaran, Huang, Raghothaman and Le, Prosecutor, OOPSLA 2026** (abstract). Bayesian inference
   on an error-propagation graph, refined by *counterfactual experiments that flip branch
   predicates at run time*. 470 Defects4J bugs; 40% of faults in the top 3. This is the closest
   work in spirit to treating program changes as interventions inside a Bayesian localiser. From
   the abstract: interventions are predicate flips, not mutants; multiple faults and calibration
   are not mentioned.
9. **Küçük, Henderson and Podgurski, UniVal, ICSE 2021** (abstract). Causal-inference estimates of
   the failure-causing effect of statements from predicate outcomes and variable values; argues
   that spectrum scores measure correlation and suffer confounding.
10. **Heckerman, Quickscore, UAI 1989** (abstract). Exact inference in the bipartite noisy-OR
    network for diagnosing multiple diseases; exponential only in the number of positive findings.
    The same network shape as this project's test layer.
11. **Heckerman and Shwe, UAI 1993** (abstract). On clinical cases with several disorders, the
    noisy-OR model agrees best with the reference diagnoses; simpler Bayes models over- or
    under-estimate posteriors.
12. **Orvalho et al., CFaults, arXiv 2407.09337** (abstract). Logic-based model-based diagnosis of
    C programs with multiple test cases and multiple faults (MaxSAT). Not probabilistic.

### C. Mutation evidence and learned combination

13. **Papadakis and Le Traon, Metallaxis, STVR 2015** and **Moon et al., MUSE, ICST 2014**
    (record). The two standard mutation-based scores.
14. **Zou et al., TSE 2021** (full). Families of techniques are complementary; learning-to-rank
    combination is black-box (authors' own caveat, *A*).
15. **Lou et al., ProFL, ISSTA 2020** (abstract). Patch-execution results of a repair tool
    re-rank fault localisation; 161 of 395 Defects4J bugs at Top-1. Evidence of the same kind as
    this project's variants, used by ranking rules.
16. **Xing, Chen, Xin and Xie, Internetware 2025** (abstract). The intuition of mutation-based
    localisation, that mutants can correct faults, has been validated only on simulated faults and
    probably does not hold for real-world faults. *A.* This is the injected-to-human shift that
    version 3 measured (5 of 31 QuixBugs bugs have a restoring variant).
17. **Liu et al., FLIMs, arXiv 2511.23302** (abstract; preprint). Mutants in fault-free code that
    failing tests kill mislead mutation-based localisation; an LLM-based filter. The "masker"
    variants of this project's model are the same phenomenon, modelled as a mixture component.

### D. Multiple faults

18. **DiGiuseppe and Jones, ISSTA 2011** (record). Influence of multiple faults on coverage-based
    localisation.
19. **Callaghan and Fischer, FLITSR, ISSTA 2023** (sections: algorithm). Spectrum-based multi-fault
    method: iteratively remove failing tests explained by the top element, keep a minimal basis.
    Outperforms base metrics, including Barinel, on multi-fault Defects4J versions.
20. **An et al., SSBSE 2021 (challenge track)** and **Callaghan and Fischer, arXiv 2403.19171** (abstract).
    Real multi-fault versions exist in Defects4J (311 found by transplanting tests) and BugsInPy.
    So naturally co-occurring faults are available as data, in tool chains this project cannot run.
21. Higher-order mutants for multi-fault localisation (IEEE Trans. Reliability 2022; IST 2024) and
    a statistical mutation-based method for deep-learning programs (Xie, Deng et al.) (search
    results only). Heuristic or statistical scores; no posterior over fault sets found.

### E. Calibration, abstention, decisions

22. **Guo et al., ICML 2017** (full) and **Spiess et al., ICSE 2025** (full). Measuring
    calibration; rescaling fitted on one task can fail on another.
23. **Kang, An and Yoo, AutoFL, FSE 2024** (full). Confidence of an LLM localiser correlates with
    correctness.
24. **ConformalFL, Research Square preprint** (search summary only; authors not confirmed; not peer
    reviewed). Conformal inspection cutoffs for spectrum-based localisation on Defects4J; by the
    authors' account it does not beat a fixed cutoff.

### F. Scalable inference

10, 5 and 7 above: Quickscore, candidate truncation in Barinel, loopy belief propagation in
SmartFL. Bounded-cardinality enumeration, used here, is the oldest of these ideas (diagnoses of
small cardinality first) and is not a contribution.

### G. Benchmarks

25. **Lin et al., QuixBugs, 2017** (full).
26. **Muennighoff et al., OctoPack, ICLR 2024** (abstract; the data set itself was inspected).
    HumanEvalFix: one hand-inserted bug in each of the 164 HumanEval solutions; bug types in the
    data: value misuse 44, missing logic 33, excess logic 31, operator misuse 25, variable misuse
    23, function misuse 8.
27. Defects4J multi-fault and BugsInPy (items 3, 4, 20): the realistic benchmarks. Not run here.

### H. Repair

28. **Liu et al., ICST 2019** (abstract). Fault-localisation configuration biases the comparison
    of repair tools; better localisation lets the same repair tool fix more bugs.

### I. Leakage and evaluation practice

1, 3 and 16 above on artificial versus real faults. For LLM-based localisers, several papers warn
that Defects4J and BugsInPy are probably in training data (search summaries only). This project's
protocol answers the non-LLM version of the problem: the program is the statistical unit, all
parameters come from other programs, and test programs that share a name with a training program
are excluded.

### J. Language models

23 above; AgentFL, FlexFL, LLMAO (search summaries only). Not evaluated here: no API access on this
machine, and HumanEval is a likely part of every model's training data.

### The base paper

29. **Mündler et al., PLDI 2025** (full). Type-constrained decoding; between 18 and 70 percent of
    type-correct programs still fail their tests. HumanEval is one of its two benchmarks, which is
    why HumanEvalFix was chosen as the second human-bug benchmark here.

## 3. What the literature says about the direction chosen

* **Solved:** multi-fault localisation from coverage (Barinel, FLITSR); Bayesian derivation of
  single-fault spectrum and mutation scores (Kang et al.); semantic probabilistic localisers at
  project scale (SmartFL, Prosecutor); patch execution as localisation evidence (ProFL).
* **Stated as open by the authors (A):** multiple faults in the Bayesian debugging framework (6);
  validity of the mutant-repairs-fault intuition on real faults (16).
* **Not found (C):** a probabilistic model in which the effect of a mutant or patch on a test
  depends on the other faults the test executes; calibration of fault probabilities when the number
  of faults is unknown.
* **Counter-evidence to keep in mind:** 16 says the evidence this model relies on is weak for real
  faults; 19 shows a simple coverage-only method is strong on multi-fault data; 7 and 8 are much
  richer models evaluated on real projects.

## 4. Search record

Searches of this round (web search, 2026-10-13), by topic: multi-fault mutation-based localisation;
Bayesian mutation evidence with multiple faults; noisy-OR and interventions in software diagnosis;
"partial fix" probabilistic models; calibration, conformal prediction and abstention in fault
localisation; SmartFL; UniVal; FLITSR; multi-fault data sets; BugsInPy studies; unified debugging;
LLM localisers and contamination; repair and localisation accuracy; HumanEvalFix. About twenty
queries. A negative result of such a search is weak evidence; a specialist reviewer may know work
that it missed, as happened with item 6 in version 3.
