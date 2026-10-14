# Research gap matrix, version 4

Paper numbers refer to [LITERATURE_REVIEW.md](LITERATURE_REVIEW.md). The version 3 matrix is in
[v3/RESEARCH_GAP_MATRIX.md](v3/RESEARCH_GAP_MATRIX.md). "Kind": A stated by the authors, B inferred,
C not found (search-limited).

| Gap | Kind | What existing work already solves | What remains | Why it matters | Feasible here? | How a reviewer could attack the novelty | Evidence that would show a real difference | Experiment |
|---|---|---|---|---|---|---|---|---|
| **N1** Bayesian use of mutant or patch outcomes when there may be several faults | A (paper 6, section 7) + C | Single-fault Bayesian derivations of spectrum and mutation scores (6); multi-fault Bayesian diagnosis from coverage only (5); patch outcomes as ranking evidence (15) | A model in which the effect of a variant on a test depends on the other faults that test executes | Version 3's own fusion collapses with two faults (both in top 3: 0.198 against 0.359 without fusion). Real programs do contain several faults (20) | Yes: the variant outcomes already exist; inference over at most three faults is polynomial | "This is Barinel plus MUSE"; "Prosecutor already does counterfactual Bayesian localisation"; "higher-order mutants already handle multiple faults" | Parameters learned on single faults only must transfer to multi-fault programs, and beat version 3, Barinel, FLITSR\* and MUSE there | H1, H4 |
| **N2** Cost of allowing several faults when there is only one | B | Nothing found that quantifies it for a probabilistic localiser | The size of the single-fault penalty of a multi-fault model, and where it comes from | A multi-fault model is only useful if the penalty is small, because most analysed programs may have one fault | Yes | "Obvious trade-off" | A measured interval, and an explanation of the cases lost | H2, ablation with at most 1 and 2 faults |
| **N3** Calibration of fault probabilities when the number of faults is unknown | C | Calibration for single faults (version 3); inspection cutoffs (24) | Whether posteriors remain usable as probabilities with 2 or 3 faults and under shift to human-written bugs | Probabilities are the stated advantage of a Bayesian localiser over a score | Yes | "Small programs, injected faults" | Brier skill above the base rate on every held-out set; comparison with the learned model | H5 |
| **N4** Inferring how many faults there are | C | Nothing found | Whether the posterior number of faults carries information | Tells a developer or repair tool whether one fix can be enough | Yes, free by-product | "Trivially follows from the number of failing tests" | AUC of the posterior expected count for separating multi-fault from single-fault programs | H7 |
| **N5** Mutation evidence on human-written bugs | A (16) | The intuition fails on real faults (16); 5 of 31 QuixBugs bugs have a restoring variant (version 3) | Whether a model that bounds the penalty for "no repair found" degrades more gracefully than a learned table | Decides whether any of this is useful outside injected faults | Partly: 31 + about 147 small human-written bugs | "Not real project bugs" | MRR against the spectrum-only model and against version 3 on HumanEvalFix | H3, human-fitted condition |
| **N6** Larger human-written benchmark | not a research gap | | Version 3 had 31 bugs | Statistical power | Yes: HumanEvalFix | | | all E sets |
| **N7** Strong multi-fault baseline | not a research gap | FLITSR (19) | It was not among version 3's baselines | Fairness | Yes: re-implemented | "Re-implementation may differ from the tool" | Tests of the properties the paper states | all |
| **N8** Composite-likelihood over-confidence in evidence fusion | B | General statistics (23) | Whether treating variants as independent harms calibration, and whether an exact treatment of "one repair per statement, one sole cause per test" fixes it | Explains a failure seen on development data | Yes | "Engineering detail" | Composite against exclusive layer, same data | ablation |
| G4 (v3) shift from injected to human-written | C | First measurement in version 3 | Larger sample | | Yes | | | E sets, QH |
| Scalability to project code | A (5, 6) | SmartFL, Prosecutor | Everything | The main limit on practical usefulness | **No** with this tool chain | | | not addressed |
| Naturally co-occurring faults | A (20) | Multi-fault Defects4J and BugsInPy exist | Evaluating there | Injected pairs may not behave like real co-occurring faults | **No**: Java, or per-project environments | | | not addressed; hybrids of a human bug and an injected fault are the nearest substitute |

## Reading the matrix

* N1 is the gap the work is built on. It has an author-stated part (the single-fault limitation of
  the Bayesian debugging framework) and a search-limited part (no interventional multi-fault model
  found).
* N2 to N5 are questions the same experiment answers; none of them is claimed as an algorithmic
  contribution.
* The last two rows are the reasons the result, whatever it is, will not be a claim about software
  projects.
