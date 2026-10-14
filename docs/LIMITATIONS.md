# Limitations and threats to validity

What the project does not show, where its models are known to be wrong, and which choices could
bias the results. Numbers come from `results/benchmark/SUMMARY.md` (version 2 experiments) and
`results/research/SUMMARY.md` (research experiments). D1 is the project's own benchmark of injected
faults, D2 the 31 human-written bugs of QuixBugs, D3 injected faults in QuixBugs programs.

## 1. What the results do and do not support

| Statement | Supported? |
|---|---|
| With spectrum evidence alone, the model ranks about as well as Ochiai and Barinel | Yes, on D1, D2 and D3 |
| With spectrum evidence alone, the model ranks better than Ochiai | **No** |
| Adding mutation evidence improves ranking on injected single faults | Yes, strongly, but the size of the gain is inflated (section 3.1); +0.18 Top-1 remains in the stress test |
| Adding mutation evidence improves ranking on human-written bugs | **Direction only.** Top-1 0.38 to 0.51, interval [-0.05, +0.30] with 31 bugs; significant only with in-suite parameters |
| The model-based fusion ranks better than a learned (logistic) fusion | **No.** Parity on D1 and D3, worse in the stress test, undecided on D2 |
| The model-based fusion gives probabilities that hold up better on unseen programs than the logistic fusion's | Yes on D3 (Brier difference -0.009, interval excludes 0); direction only on D2 |
| The probabilities are calibrated in distribution | Partly: ECE 0.045 for the fused model; logistic fusion is better (0.009) |
| The probabilities are usable on human-written bugs | Better than the base rate (skill +0.22), with ECE 0.06; 31 bugs |
| Recalibration fixes miscalibration | In distribution yes; **on human-written bugs no** (log loss gets worse) |
| Conditioning mutation evidence on coverage context helps | **No. Refuted** on every dataset |
| The size-aware prior helps | **No** overall; it helps large programs and hurts small ones |
| The posterior tells when the top-ranked statement can be trusted | Yes on D1, better than Ochiai-based confidence; direction only on D2 |
| The fused model works with several faults | **No. It is worse than the spectrum-only model on two-fault programs** |
| Static analysis or type checking helps localise these faults | **No.** pylint flagged no faulty line in the 594 + 31 detected faulty programs |
| LLM confidence helps | **Not tested with real data** |
| Any of this holds for real projects | **No evidence** |

## 2. Model assumptions that are known to be violated

**Coverage is treated as fixed.** A fault can change which statements run; an omitted statement has
no variable at all.

**Faults are independent a priori.** Real faults cluster.

**Tests are conditionally independent given the faults and the exposure rate.** Near-duplicate
tests are counted as separate evidence; this is the main source of over-confidence in the
spectrum-only model.

**One exposure rate per program version.** Exact for one fault, an approximation for several.

**Noisy-OR cannot express masking** or faults that only show in combination.

**The mutation-evidence tables assume a single fault.** They are estimated on single-fault
programs, where "no variant of this statement makes a failing test pass" is strong evidence that
the statement is innocent (likelihood ratio 0.023). When a second fault keeps the tests failing,
that inference is wrong, and the model then *lowers* the probability of truly faulty statements.
Measured consequence: on 410 two-fault programs, both faults are in the top three for 19.8% with the
fused model against 35.9% without mutation evidence. **The fused model should not be used when
several faults are likely.**

**Mutation evidence is treated as independent of test outcomes given the fault state and the
coverage context.** It is computed from the same executions. The conditioning that was designed to
remove the most obvious part of this dependence made results worse (hypothesis H3), so the
dependence structure is not understood well enough; see `research/v3/RESEARCH_PROPOSAL.md`, section 7.

**Static flags are assumed independent of test outcomes.** A warning and a crash can describe the
same defect.

**Statement granularity.** Statements that always execute together cannot be separated by coverage.

**Unexecuted statements keep the prior.**

## 3. Benchmark limitations

### 3.1 Circularity of mutation evidence on injected faults

On D1 and D3 the variants used for analysis are produced by the same operators that injected the
fault. For 492 of the 594 faults in D1 one variant is the exact repair, and the fault is then found
almost by construction. Every method that uses mutation evidence benefits (Metallaxis, MUSE, the
hybrid, logistic fusion, the fused model). Three things limit the damage: the stress test that
removes the exact-repair variant, the comparison among methods that all share the advantage, and
D2, where the bugs were written by people (only 5 of 31 have a single-edit plausible repair).
The headline numbers of D1 and D3 for these methods must not be quoted without this caveat.

### 3.2 Deletion faults have no variants

The deletion operator writes `pass`, and no operator applies to `pass`. A deleted statement
therefore has evidence level 0, which is informative on D1 for a reason unrelated to real bugs.

### 3.3 The human-written benchmark is small and special

QuixBugs has 31 usable programs here. Intervals are wide and most comparisons on D2 are not
significant. The bugs are single-line puzzles written for a programming challenge, in classic
algorithms of 3 to 18 statements. They are human-written, not injected by this project, and not
taken from real software projects. Nine programs with object-graph inputs are excluded. Eleven
of 242 tests are dropped (section 7 of EXPERIMENTS).

### 3.4 Self-written benchmark, used during development

All D1 programs except `has_close_elements` were written for this project. Two design decisions of
version 2 (latent exposure rate; excluding the `unnecessary-pass` message) were made after seeing D1
results. The research hypotheses were fixed before the new code existed, but D1 had been seen
before. D2 and D3 were not used for any design decision; the one analysis added after seeing them
(two faults) is labelled post hoc.

### 3.5 Other

Off-by-one mutants are about 40% of D1. Undetected mutants are excluded from localisation. One
mutant in D1 and one in D3 produce no result within the time limit. The `break`/`continue`
operator produces no mutants in D1. Real project benchmarks (BugsInPy, Defects4J) were not used:
they need per-project environments and programs far beyond exact inference.

## 4. Evidence sources

**Compiler diagnostics** are a gate only.

**Static analysis:** pylint only; a hand-written rule decides which messages count as behavioural.
It flagged a line in 30 of 594 faulty programs of D1 and in none of D2, never the faulty line.

**Type checking** was not added as an evidence channel. In D1, 42 of 594 faults make some failing
test raise a type, name or attribute error; in D2 none of 31 does. 438 and 22, respectively, only
return wrong values. Such faults are outside what a type system can constrain, which is consistent
with the base paper's own Table 3.

**Mutation analysis is expensive.** It runs every single-edit variant against all tests: about 23
variant executions per faulty program in D1, and 279 seconds for the 413 QuixBugs cases, against
well under a second for spectrum evidence. For real projects this cost is a known obstacle.

**LLM confidence:** no real LLM output was evaluated; only the simulated study of version 2.
`pcg/llm.py` was never run against the live API.

## 5. Baselines

* **Barinel** is reimplemented with exhaustive candidate enumeration instead of the paper's
  heuristic generator, and with an exact maximum-likelihood step. It is faithful in the model, not
  in the search heuristic.
* **Metallaxis and MUSE** follow the definitions in Pearson et al. (2017), not the original papers,
  which were not read in full. The mutation operators are this project's ten, not those of the
  original tools.
* **Hybrid average** is in the spirit of Pearson et al.'s MCBFL-hybrid-avg; their coverage
  adjustment of mutant scores is not reproduced.
* **Logistic regression** stands in for learning-to-rank combination (CombineFL). It is a pointwise
  linear model; pairwise or listwise rankers were not tried.
* **No state-of-the-art localiser** (for example SmartFL, or an LLM-based one) is compared.

## 6. Dependence analysis, repair, execution isolation

Unchanged from version 2: static slicing is blind to omission faults and made results worse; the
repair search can only produce single edits from the same family as the injected faults, so repair
rates are optimistic, and a patch that passes the tests is plausible, not proven correct; the child
process protects against crashes and endless loops and is not a security sandbox.

## 7. Statistical caveats

* The sampling unit is the program: 34 programs in D1, 31 in D2 and D3.
* Many comparisons are reported and none is corrected for multiplicity. Individual p-values near
  0.05 are not findings. The pre-registered primary comparisons are listed in
  `research/v3/RESEARCH_PROPOSAL.md`, section 5; everything else is exploratory.
* The sign-flip test and the bootstrap interval can disagree when most programs move slightly one
  way and a few move a lot the other way (example: size-aware prior, Brier difference +0.0003,
  interval includes 0, p = 0.0005). Such a difference has no practical relevance.
* ECE depends on the binning; bins with few statements are noisy.
* Probabilistic metrics in the research experiments are computed on detected cases only.
* Ties are scored by expectation; other conventions would change absolute numbers.

## 8. What is not claimed

* No new localisation algorithm. Bayesian spectrum-based localisation is Barinel (2009); richer
  probabilistic localisers exist (SmartFL; probabilistic program dependence graphs).
* No state-of-the-art accuracy.
* No result about real software projects or about language models.
