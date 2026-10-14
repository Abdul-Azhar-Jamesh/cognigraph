# Related work and novelty statement, version 4

What exactly is claimed to be new, against which prior work, and how that claim could be wrong.
Sources and how far each was read: [LITERATURE_REVIEW.md](LITERATURE_REVIEW.md).

## 1. Correction of the version 3 statement

Version 3 said that a white-box probabilistic combination of spectrum and mutation evidence "was
not found". Kang, Choi and Yoo (ISSTA 2023) had already put spectrum formulas, a MUSE-like mutation
formula and patch-based updating into one Bayesian framework. Version 3's fusion is an instance of
that idea with learned likelihood tables. Its remaining contributions are the measurements
(calibration, transfer to human-written bugs, comparison with a learned combiner), not the model.

## 2. Comparison table

| Work | Evidence | Several faults | Variants or patches as evidence | Probabilities evaluated | Scale | Python |
|---|---|---|---|---|---|---|
| Ochiai, Tarantula | coverage | no | no | no | any | yes |
| Barinel (2009) | coverage | **yes**, candidate sets | no | no | hundreds of lines | re-implemented here |
| FLITSR (2023) | coverage | **yes**, iterative reduction | no | no (ranking) | projects | re-implemented here |
| Metallaxis, MUSE | variants | no (scores) | **yes** | no | small to medium | yes |
| Higher-order-mutant localisation | variants | heuristically | **yes** | no | small | not checked |
| ProFL, unified debugging (2020) | coverage + patch runs | no | **yes**, ranking rules | no | projects | no |
| Kang, Choi, Yoo (2023) | coverage, patches, values | **no** (stated limitation) | **yes**, Bayesian | no | projects (for patch ranking) | no |
| SmartFL (2022, 2025) | program semantics | not stated in the abstract | no | no | projects | no |
| Prosecutor (2026) | error propagation + predicate flips | not stated in the abstract | counterfactual predicate flips | not stated in the abstract | projects | no |
| CFaults (2024) | program logic | **yes**, MaxSAT | no | not probabilistic | small C programs | no |
| PCG version 3 | coverage + variant summary | no (single-fault tables) | **yes**, learned table | **yes** | at most 22 statements | yes |
| **This work (IV)** | coverage + per-test variant outcomes | **yes**, up to 3, exact | **yes**, as interventions | **yes** | small functions | yes |

Entries marked "not stated in the abstract" are exactly that: I have not read those papers in
full, and they may handle the item.

## 3. The claim

> A noisy-OR diagnosis model in which a program variant is an intervention on one statement, with
> the probability that a repair makes a failing test pass equal to the probability that the
> repaired statement is the test's sole cause of failure, `q(k, theta)`. All parameters are
> estimated from single-fault programs; the behaviour with several faults follows from the model.
> Inference is exact for at most three simultaneous faults under "one repair per statement, one
> sole cause per test".

What is **not** claimed: a new inference algorithm (bounded-cardinality enumeration is old); a new
kind of evidence (the observations are those of MUSE and unified debugging); superiority over
semantic localisers; anything about project-scale code.

## 4. How a sceptical reviewer would attack it, and the honest answer

| Attack | Answer |
|---|---|
| "Barinel with MUSE features." | Barinel's likelihood has no term for variants. The difference is the factor `Lambda_s(F, theta)`, whose value for one statement depends on the other members of `F`. Whether that difference matters is an empirical question: hypothesis H1 tests it against Barinel, FLITSR\* and MUSE |
| "Kang et al. already have a Bayesian model of mutants and patches." | Under a single-fault assumption, which they name as their major limitation. The single-fault restriction of this model (`c = 1`) is close to theirs and is included as an ablation |
| "Prosecutor does counterfactual Bayesian fault localisation at scale." | Yes, with predicate flips on an error-propagation graph, for Java projects. It is a stronger system. This work differs in the kind of intervention and in addressing an unknown number of faults; it cannot be compared head to head here. If Prosecutor already handles multiple faults (its abstract does not say), the remaining difference is small |
| "Higher-order mutants already address multiple faults." | They change which variants are generated. This model changes how first-order variant outcomes are read. The two are compatible; no comparison was run |
| "Injected faults by the same operators as the variants: of course it works." | Correct for the multi-fault mutant sets, and stated. The hybrids of a human-written bug with one injected fault, and the human-written bugs themselves, are the checks; the second is where mutation evidence is known to be weak (paper 16) |
| "Functions of ten statements." | True. The result is about whether the modelling idea is sound, not about usefulness on projects |
| "You only searched the web for twenty queries." | True. Version 3 missed a directly relevant ISSTA paper that way. The claim is search-limited |

## 5. Evidence that would establish a real difference

1. Parameters learned on single faults only; no multi-fault data in training. (By construction.)
2. On held-out two-fault programs, a higher mean average precision than the coverage-only
   multi-fault methods and than the single-fault mutation methods, with intervals. (H1)
3. The effect disappears when the model is restricted to one fault. (Ablation `c = 1`.)
4. The effect is present where the model's key mechanism can act (every fault has a restoring
   variant) and smaller where it cannot. (Breakdown.)
5. Synthetic data from the model: inference is calibrated; under broken assumptions it degrades in
   the predicted direction. (Stage A.)

If 2 fails, there is no contribution of the model. If 2 holds but 3 does not, the gain is not due
to the multi-fault mechanism.

## 6. Position after the experiments

See [RESULTS.md](RESULTS.md) and [FINAL_RESEARCH_AUDIT.md](FINAL_RESEARCH_AUDIT.md); this file is
not rewritten in the light of the results.
