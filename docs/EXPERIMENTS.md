# Experiments

This document has two parts.

* **Part A** (sections 1 to 6): the experiments of version 2.0.0, unchanged. Command:
  `python -m pcg benchmark`; results in `results/benchmark`.
* **Part B** (sections 7 to 15): the research experiments of version 3.0.0. Command:
  `python -m pcg research`; results in `results/research`. Their protocol was fixed beforehand in
  `research/v3/RESEARCH_PROPOSAL.md`.

# Part A: version 2.0.0

Everything in this part was produced by one command, `python -m pcg benchmark`. The tables are
copied from the generated file `results/benchmark/SUMMARY.md`; the test
`test_published_summary_matches_the_result_files` checks that that file agrees with the raw data.
Square brackets are 95% bootstrap intervals that resample whole programs.

Sections 1 to 4 describe the method. Section 5 gives observations. Section 6 separates what was
observed from what is only a hypothesis.

## 1. Benchmark

### Programs

34 small Python functions (`pcg/benchmark_programs.py`): 4 to 16 statements (mean 7.1), each with 7
to 16 hand-written test inputs (mean 10.1). Examples: `binary_search`, `gcd`, `is_prime`,
`merge_sorted`, `classify_triangle`, `median`. `has_close_elements` is problem 0 of HumanEval and
was the original project's only example.

### Oracle

The expected outcome of a test is whatever the reference implementation returns or raises for that
input. The reference implementations are themselves pinned by hand-written literal expectations in
`tests/test_benchmark_mutation.py`. A test's observable behaviour is `return:<repr of value>` or
`raise:<exception type>`; a test passes when the behaviour equals the oracle's.

### Fault injection

Each mutant changes exactly one AST node of the reference program (`pcg/mutation.py`).

| Operator | Category | Transformation |
|---|---|---|
| ROR-flip | comparison | `<` to `>`, `<=` to `>=`, `>` to `<`, `>=` to `<=`, `==` and `!=` swapped |
| ROR-bound | boundary | `<` and `<=` swapped, `>` and `>=` swapped |
| CRP | off_by_one | integer constant `c` to `c + 1` and to `c - 1` |
| LCR | boolean | `and` and `or` swapped |
| NEG | boolean | condition of `if` or `while` negated |
| MEM | boolean | `in` and `not in` swapped |
| AOR | arithmetic | `+` and `-` swapped; `*` to `+`; `/`, `//`, `%` to `*` |
| BCR | return_value | `True` and `False` swapped |
| SDL | omission | an assignment or expression statement replaced by `pass` |
| JMP | control_flow | `break` and `continue` swapped |

JMP produced no mutants: no benchmark program contains `break` or `continue`.

### Ground truth

The fault location of a mutant is the single line on which its text differs from the reference. It
is derived by comparing the two texts, stored in a separate `GroundTruth` object, and read only by
the parameter estimation for *other* programs and by the metric code.

### Mutant classification

| Quantity | Count |
|---|---|
| Mutants generated (distinct texts) | 625 |
| Excluded: no result within the wall-clock limit (`gcd:3:AOR:0`) | 1 |
| Valid | 624 |
| Detected by at least one test, used for localisation | 594 |
| Not detected (equivalent or missed), never counted as localised | 30 |

| Category | Valid | Detected |
|---|---|---|
| arithmetic | 65 | 64 |
| boolean | 80 | 79 |
| boundary | 50 | 35 |
| comparison | 73 | 73 |
| omission | 84 | 83 |
| off_by_one | 256 | 244 |
| return_value | 16 | 16 |

For every mutant, `results/benchmark/cases.jsonl` records the mutated source, the transformation,
the changed line, the tests, the oracle outcomes, the observed outcomes, per-test coverage and the
classification.

## 2. Methods compared

All methods receive the same execution evidence: the coverage matrix and the pass/fail vector. None
receives ground truth. `ef` and `ep` are the numbers of failing and passing tests that executed a
statement; `F` and `P` are the totals.

| Method | Score | Can use | Cannot use |
|---|---|---|---|
| Chance | all statements tied | nothing | everything |
| Execution only | `ef` | failing runs | passing runs |
| Simple heuristic | `ef - ep` | coverage and outcomes | anything probabilistic; labelled a heuristic |
| Tarantula | `(ef/F) / (ef/F + ep/P)` | coverage and outcomes | training data |
| Ochiai | `ef / sqrt(F (ef + ep))` | coverage and outcomes | training data |
| PCG, fixed theta | posterior, one fixed exposure rate | coverage, outcomes, parameters from other programs | static flags |
| **PCG** | posterior, exposure rate summed out | same | static flags |
| PCG + slicing | PCG with scopes cut to dependence slices | additionally the dependence graph | static flags |
| PCG + static | PCG with pylint flags as evidence | additionally pylint | |
| LLM only (simulated study only) | 1 minus confidence | the simulated signal | execution |

PCG uses labelled mutants of other programs to estimate five numbers and a ten-point prior. The
spectrum baselines need no training. This is a real difference in what the methods require, not an
unfair advantage in evidence about the evaluated program.

## 3. Protocol

* **Leave-one-program-out.** To analyse a mutant of program `X`, parameters are estimated from the
  valid mutants (detected and undetected) of the other 33 programs.
* **Seed.** `20261013` for every random step. Inference and tie handling use no randomness.
* **Step limit.** A test is stopped and counted as failed after 20,000 executed lines.

## 4. Metrics

**Ranking** (detected mutants; one known faulty line each):

| Metric | Definition |
|---|---|
| Top-1, Top-3 | probability that the faulty line is among the first 1 or 3 statements |
| MRR | mean of 1 / rank |
| EXAM | fraction of statements inspected before reaching the fault (lower is better) |

Ties are scored by expectation under a random tie-break: a fault tied with two other statements
for first place scores Top-1 = 1/3.

**Probabilistic quality** (all statements of all valid mutants, out-of-fold):

| Metric | Definition |
|---|---|
| Brier score | mean of (probability - outcome)^2 |
| Log loss | mean negative log-likelihood |
| ECE | weighted mean gap between predicted and observed frequency, 10 equal-width bins |

Ochiai and the other baselines produce scores, not probabilities, so these metrics are not defined
for them.

**Uncertainty and tests.** The program is the sampling unit. Intervals: percentile bootstrap, 5,000
resamples of programs. Paired comparison: per-mutant differences, summarised per program, tested
with a two-sided sign-flip permutation test (20,000 resamples). No correction for multiple
comparisons is applied.

## 5. Results

### 5.1 Single-fault localisation (594 detected mutants)

| Method | Top-1 | Top-3 | MRR | EXAM |
|---|---|---|---|---|
| Chance | 0.136 [0.122, 0.153] | 0.409 [0.367, 0.458] | 0.354 [0.329, 0.382] | 0.568 [0.561, 0.576] |
| Execution only | 0.307 [0.270, 0.346] | 0.739 [0.678, 0.800] | 0.547 [0.510, 0.585] | 0.345 [0.317, 0.378] |
| Simple heuristic | 0.469 [0.426, 0.516] | 0.757 [0.699, 0.820] | 0.639 [0.603, 0.679] | 0.342 [0.304, 0.383] |
| Tarantula | 0.338 [0.286, 0.390] | 0.815 [0.770, 0.860] | 0.589 [0.555, 0.623] | 0.310 [0.294, 0.329] |
| Ochiai | 0.538 [0.486, 0.592] | 0.912 [0.877, 0.947] | 0.726 [0.690, 0.761] | 0.236 [0.219, 0.256] |
| PCG, fixed theta | 0.540 [0.487, 0.594] | 0.845 [0.796, 0.897] | 0.704 [0.667, 0.743] | 0.277 [0.253, 0.304] |
| **PCG** | 0.547 [0.494, 0.600] | 0.900 [0.861, 0.937] | 0.726 [0.688, 0.764] | 0.243 [0.225, 0.263] |
| PCG + slicing | 0.406 [0.364, 0.448] | 0.717 [0.661, 0.777] | 0.593 [0.557, 0.629] | 0.367 [0.339, 0.399] |
| PCG + static | 0.555 [0.502, 0.609] | 0.902 [0.864, 0.938] | 0.732 [0.694, 0.770] | 0.240 [0.222, 0.260] |

Paired comparisons (difference = first minus second):

| Comparison | Metric | Mean difference [95% CI] | Programs better / worse / equal | p |
|---|---|---|---|---|
| PCG - Ochiai | Top-1 | +0.0089 [-0.0002, +0.0192] | 7 / 2 / 25 | 0.0640 |
| PCG - Ochiai | MRR | +0.0004 [-0.0065, +0.0068] | 8 / 10 / 16 | 0.9609 |
| PCG - Ochiai | EXAM | +0.0066 [+0.0003, +0.0132] | 11 / 7 / 16 (lower is better: PCG slightly worse) | 0.0356 |
| PCG - Tarantula | Top-1 | +0.2092 [+0.1653, +0.2550] | 34 / 0 / 0 | < 0.0001 |
| PCG - PCG fixed theta | MRR | +0.0218 [+0.0080, +0.0371] | 15 / 6 / 13 | 0.0080 |
| PCG + slicing - PCG | Top-1 | -0.1408 [-0.1772, -0.1041] | 1 / 32 / 1 | < 0.0001 |
| PCG + static - PCG | Top-1 | +0.0081 [+0.0036, +0.0134] | 10 / 0 / 24 | 0.0019 |

MRR by fault category:

| Category | n | Ochiai | PCG | PCG fixed theta | PCG + slicing | PCG + static |
|---|---|---|---|---|---|---|
| arithmetic | 64 | 0.758 | 0.751 | 0.747 | 0.731 | 0.751 |
| boolean | 79 | 0.862 | 0.856 | 0.847 | 0.797 | 0.856 |
| boundary | 35 | 0.437 | 0.459 | 0.363 | 0.260 | 0.459 |
| comparison | 73 | 0.828 | 0.850 | 0.834 | 0.660 | 0.850 |
| omission | 83 | 0.710 | 0.698 | 0.705 | 0.383 | 0.739 |
| off_by_one | 244 | 0.671 | 0.670 | 0.638 | 0.564 | 0.670 |
| return_value | 16 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

### 5.2 Probabilistic quality

| Model | Statements | Faulty | Brier | Log loss | ECE |
|---|---|---|---|---|---|
| Base rate (prior for every statement) | 5056 | 624 | 0.1084 | 0.3746 | 0.0015 |
| PCG, fixed theta | 5056 | 624 | 0.0912 | 0.4056 | 0.0821 |
| **PCG** | 5056 | 624 | 0.0760 | 0.2712 | 0.0454 |
| PCG + slicing | 5056 | 624 | 0.0902 | 0.3202 | 0.0303 |
| PCG + static | 5056 | 624 | 0.0749 | 0.2680 | 0.0449 |

Reliability of PCG:

| Predicted range | Statements | Mean predicted | Observed faulty |
|---|---|---|---|
| 0.0-0.1 | 2511 | 0.027 | 0.025 |
| 0.1-0.2 | 1142 | 0.142 | 0.049 |
| 0.2-0.3 | 482 | 0.243 | 0.141 |
| 0.3-0.4 | 376 | 0.360 | 0.295 |
| 0.4-0.5 | 129 | 0.450 | 0.442 |
| 0.5-0.6 | 139 | 0.535 | 0.489 |
| 0.6-0.7 | 38 | 0.648 | 0.368 |
| 0.7-0.8 | 47 | 0.762 | 0.574 |
| 0.8-0.9 | 66 | 0.838 | 0.727 |
| 0.9-1.0 | 126 | 0.970 | 0.889 |

Figure: `results/benchmark/fig_reliability.png`.

Fault-free programs: for the 34 reference programs (all tests pass), the mean `P(no fault)` rises
from 0.406 a priori to 0.894 a posteriori; the lowest posterior is 0.773.

### 5.3 Slicing ablation

In the full benchmark the faulty line lies outside the slice scope of at least one failing test for
71 of the 83 detected omission mutants, and for 0 of the 511 other mutants. With omission mutants
removed from training and evaluation:

| Method (511 mutants) | Top-1 | Top-3 | MRR |
|---|---|---|---|
| Ochiai | 0.546 [0.492, 0.602] | 0.904 [0.861, 0.942] | 0.728 [0.690, 0.765] |
| PCG | 0.557 [0.503, 0.611] | 0.897 [0.852, 0.936] | 0.731 [0.691, 0.770] |
| PCG + slicing | 0.566 [0.515, 0.620] | 0.901 [0.857, 0.940] | 0.737 [0.699, 0.775] |

PCG + slicing minus PCG, Top-1: +0.0098 [+0.0000, +0.0288], better in 2 programs, equal in 32,
p = 0.4991.

### 5.4 Sensitivity to hand-set parameters

The fixed-theta model was re-run with parameters typed in by hand: 25 combinations of
`theta` in {0.3, 0.5, 0.7, 0.9, 0.99} and `pi` in {0.02, 0.05, 0.1, 0.2, 0.3}, plus four leak values.
Over the 29 combinations Top-1 ranges from 0.483 to 0.557 and the Brier score from 0.0747 to 0.1528.
Full grid: `sensitivity.csv`; figure: `fig_sensitivity.png`.

### 5.5 Two-fault programs

415 two-fault programs sampled; 1 excluded, 4 not detected, 410 evaluated. Parameters are those of
the single-fault folds. Ties use mid-ranks, so the all-tied chance baseline scores 0 on Top-1 by
construction.

| Method | First fault Top-1 | First fault Top-3 | First fault MRR | Both in top 3 | Both in top 5 | Mean rank |
|---|---|---|---|---|---|---|
| Tarantula | 0.156 [0.109, 0.211] | 0.829 [0.748, 0.902] | 0.521 [0.480, 0.563] | 0.402 [0.328, 0.480] | 0.756 [0.683, 0.830] | 3.30 [2.99, 3.69] |
| Ochiai | 0.366 [0.280, 0.454] | 0.946 [0.905, 0.979] | 0.686 [0.636, 0.733] | 0.334 [0.269, 0.397] | 0.693 [0.604, 0.782] | 3.12 [2.85, 3.48] |
| PCG | 0.378 [0.300, 0.458] | 0.954 [0.919, 0.981] | 0.693 [0.647, 0.738] | 0.346 [0.284, 0.410] | 0.732 [0.654, 0.811] | 3.03 [2.77, 3.35] |

PCG minus Ochiai: first-fault Top-1 +0.0122 [-0.0218, +0.0463], p = 0.4922; mean rank -0.0970
[-0.2263, +0.0479], p = 0.1882. The remaining baselines are in `SUMMARY.md`.

### 5.6 Simulated LLM-confidence signal

**The confidence values in this experiment are synthetic.** Each statement receives a "confidence
that this line is correct" drawn from a Beta distribution: Beta(8, 2) for fault-free statements and
the distribution in the table for faulty ones. The model then learns the signal's likelihood on the
other programs and fuses it. This measures what a signal of a given quality would contribute. It is
not a measurement of any language model.

| Signal | Faulty lines drawn from | PCG Top-1 | Signal alone Top-1 | PCG + signal Top-1 | PCG + signal MRR | PCG + signal Brier |
|---|---|---|---|---|---|---|
| uninformative | Beta(8, 2) | 0.547 | 0.130 ± 0.011 | 0.548 ± 0.009 | 0.727 ± 0.005 | 0.0760 |
| weak | Beta(6, 4) | 0.547 | 0.554 ± 0.018 | 0.757 ± 0.009 | 0.855 ± 0.006 | 0.0512 |
| strong | Beta(3, 7) | 0.547 | 0.958 ± 0.010 | 0.975 ± 0.004 | 0.986 ± 0.002 | 0.0110 |

Mean ± standard deviation over 10 seeded replicates. PCG alone: MRR 0.726, Brier 0.0760.

### 5.7 Targeted repair

For each detected mutant every single-edit candidate patch was compiled and run against the full
test suite. A strategy walks the candidates of its allowed statements in rank order and stops at
the first that passes all tests.

| Strategy | Plausible repair rate | Exact repair rate | Candidates validated | Fault line in region |
|---|---|---|---|---|
| PCG, top-3 statements | 0.749 [0.676, 0.815] | 0.609 [0.539, 0.678] | 4.75 [4.27, 5.21] | 0.909 [0.859, 0.953] |
| Ochiai, top-3 statements | 0.753 [0.682, 0.817] | 0.613 [0.545, 0.680] | 4.86 [4.37, 5.32] | 0.923 [0.880, 0.960] |
| Unguided, all statements | 0.828 [0.787, 0.868] | 0.658 [0.611, 0.704] | 13.38 [11.14, 15.55] | 1.000 |

"Plausible" means the patch passes every test; "exact" means its text equals the reference.
The 102 mutants that even the unguided search cannot repair are the 83 omission mutants and 19
arithmetic mutants whose inverse edit is not among the operators.

## 6. Observations and what they do not establish

**Observed on this benchmark**

1. PCG and Ochiai are statistically indistinguishable in ranking. The interval for the Top-1
   difference includes zero; MRR is identical to three decimals; EXAM is marginally worse for PCG.
2. Both are far ahead of Tarantula, the simple heuristic and execution-only counting.
3. Summing out the exposure rate matters: with a single fixed `theta`, Top-3 drops from 0.900 to
   0.845 and the log loss (0.406) is worse than predicting the base rate (0.375).
4. PCG's probabilities are informative (Brier 0.076 against 0.108) but over-confident between 0.1
   and 0.3 and above 0.6.
5. Static analysis: pylint attached a behavioural finding to no faulty line and to 52 fault-free
   lines. The small gain of PCG + static comes from lowering those 52 lines. All 52 are in omission mutants, where pylint flags the
   line that *uses* a variable whose assignment was deleted.
6. Dependence slicing hurts overall because it cannot see omission faults. Without them it changes
   two programs, slightly for the better, and the difference is not significant.
7. With two faults PCG is nominally ahead of Ochiai on every metric, with every interval
   including zero.
8. Restricting repair to the three most suspicious statements cuts the number of patches that must
   be validated from 13.4 to 4.8 and costs about 8 points of repair rate. PCG and Ochiai guidance
   are equivalent.

**Hypotheses, not shown**

* That the parity with Ochiai is a property of single-fault spectra in general. The literature
  supports this for single faults (Xie et al., 2013), but this project did not test it beyond its
  own benchmark.
* That a real LLM's confidence would behave like the "weak" or "strong" simulated signal. Published
  work finds code models poorly calibrated out of the box (Spiess et al., 2025).
* That any of these numbers carry over to real faults or larger programs.

**Experiments not run**

* LLM code generation, real LLM confidence, LLM-proposed patches (no API credentials).
* Real-fault benchmarks.
* Gibbs sampling at scale (no benchmark program needs it).

# Part B: research experiments (version 3.0.0)

Tables are copied from the generated file `results/research/SUMMARY.md`. Intervals are 95%
bootstrap intervals over programs. No multiple-comparison correction is applied. The question,
hypotheses and comparisons were written down before the code existed
(`research/v3/RESEARCH_PROPOSAL.md`, section 5); section 15 says which hypotheses held.

## 7. Datasets

| ID | Content | Cases evaluated | Parameters come from |
|---|---|---|---|
| D1 | The project's benchmark: single-fault mutants of 34 programs | 594 detected | the other 33 programs |
| D2 | QuixBugs: one human-written, single-line bug per program | 31 of 31 detected | D1 only ("transfer"), or mutants of the other QuixBugs programs ("in-suite") |
| D3 | Mutants of the 31 correct QuixBugs programs, 15 sampled per program | 382 detected of 402 valid | D1 only |

QuixBugs details: 40 programs exist; 31 have JSON test cases and all 31 are used; the other 9 need
object graphs as input. 231 of the 242 tests are kept: 9 are dropped because the benchmark's own
correct program exceeds the step limit of 100,000 lines, 2 because its output differs from the
expected output in the benchmark. One sampled mutant produced no result within the time limit.
Fault lines were obtained by comparing the buggy and the correct version; 29 bugs are a modified
line and 2 are a missing line (blamed on the statement after the gap).

## 8. Methods

| Name | Kind | Uses |
|---|---|---|
| Ochiai, Tarantula | spectrum formulas | coverage and outcomes |
| Barinel | Bayesian, candidate-based (Abreu et al., 2009) | coverage and outcomes |
| Metallaxis, MUSE | mutation-based formulas | outcomes of single-edit variants |
| Hybrid average | mean of Ochiai and Metallaxis | both |
| Logistic, spectrum | logistic regression | spectrum features; trained on other programs |
| Logistic fusion | logistic regression | spectrum, mutation and static features; trained on other programs |
| PCG v2 | the version-2 model | coverage and outcomes; parameters from other programs |
| PCG, size-aware prior | PCG v2 with prior `mu / n` | same |
| **PCG fused** (proposed) | size-aware prior plus mutation evidence conditioned on coverage context | coverage, outcomes, variants |
| PCG fused, no context | ablation: mutation evidence without the conditioning | same |
| PCG fused, constant prior | ablation: constant prior | same |
| PCG fused, recalibrated | Platt scaling of the fused posterior; ranking unchanged | same, plus a map fitted on other programs |

Mutation analysis: every single-edit variant of the program under analysis is run on all tests
(13,430 variants for D1; 6,969 distinct programs executed).

## 9. Ranking

### 9.1 D1: injected faults in the project's programs

| Method | Top-1 | Top-3 | MRR |
|---|---|---|---|
| Ochiai | 0.538 [0.486, 0.592] | 0.912 [0.877, 0.947] | 0.726 [0.690, 0.761] |
| Barinel | 0.538 [0.488, 0.591] | 0.910 [0.879, 0.942] | 0.724 [0.691, 0.759] |
| Metallaxis | 0.748 [0.679, 0.815] | 0.877 [0.836, 0.916] | 0.827 [0.775, 0.875] |
| MUSE | 0.746 [0.684, 0.805] | 0.854 [0.813, 0.894] | 0.816 [0.775, 0.859] |
| Hybrid average | 0.780 [0.717, 0.840] | 0.913 [0.874, 0.947] | 0.856 [0.811, 0.898] |
| Logistic, spectrum | 0.550 [0.500, 0.599] | 0.921 [0.889, 0.953] | 0.735 [0.701, 0.769] |
| Logistic fusion | 0.959 [0.940, 0.976] | 0.999 [0.998, 1.000] | 0.978 [0.968, 0.987] |
| PCG v2 | 0.547 [0.494, 0.600] | 0.900 [0.861, 0.937] | 0.726 [0.688, 0.764] |
| PCG, size-aware prior | 0.548 [0.496, 0.600] | 0.901 [0.863, 0.937] | 0.727 [0.690, 0.764] |
| **PCG fused** | 0.957 [0.934, 0.975] | 0.990 [0.983, 0.996] | 0.974 [0.961, 0.985] |
| PCG fused, no context | 0.958 [0.937, 0.976] | 1.000 [1.000, 1.000] | 0.977 [0.966, 0.987] |

**These numbers are inflated for every method that uses mutation evidence.** The analysis variants
are produced by the same operators that injected the fault, so for 492 of the 594 faults one
variant is the exact repair. Section 9.2 removes it.

### 9.2 D1 stress test: the exact-repair variant removed

The variant whose text equals the reference program is removed from the analysis, in training and
in evaluation. This uses ground truth to remove information; it is a stress test, not a result.

| Method | Top-1 | Top-3 | MRR |
|---|---|---|---|
| Ochiai | 0.538 [0.486, 0.592] | 0.912 [0.877, 0.947] | 0.726 [0.690, 0.761] |
| Metallaxis | 0.549 [0.475, 0.627] | 0.788 [0.727, 0.848] | 0.692 [0.633, 0.752] |
| MUSE | 0.482 [0.398, 0.571] | 0.706 [0.637, 0.774] | 0.628 [0.562, 0.697] |
| Hybrid average | 0.602 [0.533, 0.674] | 0.861 [0.803, 0.915] | 0.744 [0.691, 0.796] |
| Logistic fusion | 0.771 [0.717, 0.823] | 0.947 [0.918, 0.973] | 0.860 [0.825, 0.893] |
| PCG, size-aware prior | 0.548 [0.496, 0.600] | 0.901 [0.863, 0.937] | 0.727 [0.690, 0.764] |
| **PCG fused** | 0.729 [0.678, 0.783] | 0.920 [0.888, 0.950] | 0.832 [0.798, 0.868] |

PCG fused minus PCG size-aware: Top-1 +0.182 [+0.138, +0.224]. PCG fused minus logistic fusion:
Top-1 -0.042 [-0.074, -0.011], MRR -0.027 [-0.047, -0.009]: here logistic fusion is better.

### 9.3 D2: human-written bugs (QuixBugs), parameters from D1 only

| Method | Top-1 | Top-3 | MRR |
|---|---|---|---|
| Ochiai | 0.376 [0.260, 0.509] | 0.666 [0.554, 0.777] | 0.565 [0.474, 0.665] |
| Barinel | 0.381 [0.266, 0.512] | 0.671 [0.559, 0.782] | 0.570 [0.479, 0.669] |
| Metallaxis | 0.305 [0.182, 0.441] | 0.611 [0.468, 0.753] | 0.501 [0.399, 0.609] |
| MUSE | 0.395 [0.248, 0.549] | 0.556 [0.404, 0.702] | 0.542 [0.424, 0.665] |
| Hybrid average | 0.309 [0.185, 0.444] | 0.626 [0.478, 0.769] | 0.513 [0.414, 0.620] |
| Logistic, spectrum | 0.381 [0.266, 0.512] | 0.671 [0.559, 0.782] | 0.570 [0.479, 0.669] |
| Logistic fusion | 0.575 [0.403, 0.742] | 0.742 [0.602, 0.876] | 0.699 [0.572, 0.819] |
| PCG v2 | 0.381 [0.266, 0.512] | 0.660 [0.540, 0.777] | 0.562 [0.465, 0.663] |
| **PCG fused** | 0.511 [0.339, 0.672] | 0.742 [0.591, 0.876] | 0.666 [0.543, 0.782] |
| PCG fused, no context | 0.575 [0.414, 0.737] | 0.785 [0.651, 0.903] | 0.706 [0.584, 0.822] |

| Comparison | Metric | Mean difference [95% CI] | p |
|---|---|---|---|
| PCG fused - PCG size-aware | Top-1 | +0.130 [-0.050, +0.301] | 0.160 |
| PCG fused - PCG size-aware | MRR | +0.104 [-0.013, +0.220] | 0.093 |
| PCG fused - logistic fusion | Top-1 | -0.065 [-0.177, +0.016] | 0.379 |
| PCG fused - logistic fusion | MRR | -0.033 [-0.113, +0.032] | 0.414 |
| PCG fused - hybrid average | MRR | +0.152 [+0.004, +0.296] | 0.057 |
| PCG fused - Metallaxis | MRR | +0.165 [+0.013, +0.312] | 0.045 |
| PCG fused - PCG fused, no context | MRR | -0.040 [-0.091, -0.004] | 0.063 |

Mutation evidence level of the faulty statement in D2: no variant applies for 7 bugs; no variant
makes a failing test pass for 12; a variant fixes some failing tests for 5; all failing tests but
breaks a passing one for 2; all tests for 5. So for only 5 of 31 human-written bugs is a single
edit a plausible repair, against 492 of 594 injected faults.

With parameters estimated on mutants of the other QuixBugs programs instead ("in-suite"): PCG fused
Top-1 0.551, MRR 0.685; logistic fusion 0.478 and 0.629; PCG fused minus PCG size-aware MRR +0.123
[+0.014, +0.232], p = 0.038; PCG fused minus logistic fusion MRR +0.056 [-0.005, +0.126].

### 9.4 D3: injected faults in QuixBugs programs, parameters from D1 only

| Method | Top-1 | Top-3 | MRR |
|---|---|---|---|
| Ochiai | 0.344 [0.291, 0.400] | 0.705 [0.641, 0.766] | 0.558 [0.513, 0.605] |
| Metallaxis | 0.506 [0.439, 0.572] | 0.757 [0.695, 0.818] | 0.659 [0.605, 0.713] |
| Hybrid average | 0.534 [0.465, 0.604] | 0.809 [0.744, 0.873] | 0.690 [0.634, 0.745] |
| Logistic fusion | 0.917 [0.878, 0.950] | 0.991 [0.976, 1.000] | 0.953 [0.929, 0.973] |
| PCG v2 | 0.346 [0.291, 0.406] | 0.700 [0.636, 0.763] | 0.558 [0.512, 0.606] |
| **PCG fused** | 0.911 [0.873, 0.942] | 0.983 [0.968, 0.995] | 0.947 [0.921, 0.966] |

The same inflation as in 9.1 applies.

## 10. Quality of the probabilities

Skill = 1 - Brier / Brier(base rate `1/n`). Detected cases only, since mutation evidence is defined
only when a test fails.

| Method | D1 Brier | D1 log loss | D1 ECE | D2 Brier | D2 skill | D2 log loss | D2 ECE | D3 Brier | D3 log loss | D3 ECE |
|---|---|---|---|---|---|---|---|---|---|---|
| Base rate 1/n | 0.1069 | 0.3672 | 0.0000 | 0.1121 | 0.000 | 0.3798 | 0.0000 | 0.1078 | 0.3688 | 0.0000 |
| Logistic, spectrum | 0.0837 | 0.2582 | 0.0144 | 0.1123 | -0.002 | 0.3550 | 0.0609 | 0.1240 | 0.3744 | 0.0991 |
| Logistic fusion | 0.0141 | 0.0547 | 0.0092 | 0.0918 | +0.181 | 0.4098 | 0.0829 | 0.0288 | 0.1087 | 0.0254 |
| PCG v2 | 0.0739 | 0.2557 | 0.0530 | 0.0973 | +0.132 | 0.3353 | 0.0668 | 0.0933 | 0.3242 | 0.0685 |
| PCG, size-aware prior | 0.0742 | 0.2550 | 0.0517 | 0.0974 | +0.131 | 0.3346 | 0.0585 | 0.0942 | 0.3239 | 0.0689 |
| **PCG fused** | 0.0145 | 0.0744 | 0.0450 | 0.0872 | +0.222 | 0.3161 | 0.0616 | 0.0200 | 0.0884 | 0.0410 |
| PCG fused, no context | 0.0090 | 0.0401 | 0.0161 | 0.0796 | +0.290 | 0.2872 | 0.0572 | 0.0159 | 0.0645 | 0.0197 |
| PCG fused, recalibrated | 0.0095 | 0.0399 | 0.0054 | 0.0878 | +0.217 | 0.4127 | 0.0756 | 0.0169 | 0.0643 | 0.0106 |

Paired Brier differences (negative favours the first):

| Comparison | D1 | D2 | D3 |
|---|---|---|---|
| PCG fused - logistic fusion | +0.0004 [-0.0025, +0.0036] | -0.0046 [-0.0224, +0.0122] | -0.0088 [-0.0135, -0.0048] |
| PCG fused - PCG fused, no context | +0.0055 [+0.0041, +0.0073] | +0.0076 [+0.0042, +0.0118] | +0.0041 [+0.0028, +0.0057] |
| PCG fused recalibrated - PCG fused | -0.0050 [-0.0066, -0.0037] | not computed | not computed |

Figure: `results/research/fig_fusion_reliability.png`.

## 11. Selective localisation

A method answers only its most confident cases. AURC is the mean error over all coverage levels
(lower is better). Normalised gain: 1 means the confidence orders cases as well as an oracle would,
0 means it carries no information.

| Confidence (answers scored) | D1 error rate | D1 AURC | D1 gain | D2 error rate | D2 AURC | D2 gain |
|---|---|---|---|---|---|---|
| Largest posterior (PCG v2) | 0.453 | 0.250 | +0.665 | 0.619 | 0.376 | +0.793 |
| Largest posterior (PCG size-aware) | 0.452 | 0.251 | +0.662 | 0.619 | 0.374 | +0.801 |
| Largest Ochiai score (Ochiai) | 0.462 | 0.362 | +0.324 | 0.624 | 0.574 | +0.162 |
| Ochiai gap, first minus second (Ochiai) | 0.462 | 0.312 | +0.487 | 0.624 | 0.424 | +0.647 |
| Largest probability (logistic, spectrum) | 0.450 | 0.479 | -0.097 | 0.619 | 0.569 | +0.164 |
| Largest posterior (PCG fused) | 0.043 | 0.003 | +0.955 | 0.489 | 0.263 | +0.682 |
| Largest probability (logistic fusion) | 0.041 | 0.008 | +0.811 | 0.425 | 0.213 | +0.681 |

AURC differences with intervals (first minus second; negative favours the first):

| Comparison | D1 | D2 |
|---|---|---|
| PCG size-aware posterior - Ochiai gap | -0.061 [-0.106, -0.030] | -0.050 [-0.161, +0.015] |
| PCG size-aware posterior - largest Ochiai score | -0.112 [-0.163, -0.050] | -0.200 [-0.267, -0.115] |
| PCG fused posterior - logistic fusion probability | -0.005 [-0.016, +0.002] | +0.050 [-0.051, +0.168] |

Figure: `fig_risk_coverage.png`.

## 12. Size-aware prior (all 624 valid mutants, spectrum evidence only)

| Program size | Statements | Observed fault rate | Brier, constant prior | Brier, size-aware | ECE, constant | ECE, size-aware |
|---|---|---|---|---|---|---|
| all | 5056 | 0.1234 | 0.0760 | 0.0762 | 0.0454 | 0.0441 |
| 4 to 5 statements | 537 | 0.2067 | 0.0828 | 0.0930 | 0.0604 | 0.0770 |
| 6 to 8 statements | 2028 | 0.1371 | 0.0843 | 0.0857 | 0.0449 | 0.0506 |
| 9 to 16 statements | 2491 | 0.0943 | 0.0677 | 0.0649 | 0.0467 | 0.0332 |

Paired Brier difference, size-aware minus constant: +0.0003 [-0.0014, +0.0023].

## 13. Post hoc analysis: two faults

Not pre-registered; added after hypothesis H3 was refuted. 410 detected two-fault programs, scored
with models trained on single-fault mutants. Of their 820 faulty statements, 481 were executed by
all failing tests, 274 by some, 65 by none.

| Method | First fault Top-1 | First fault MRR | Both in top 3 | Mean rank |
|---|---|---|---|---|
| Ochiai | 0.366 [0.280, 0.454] | 0.686 [0.636, 0.733] | 0.334 [0.269, 0.397] | 3.12 |
| Hybrid average | 0.588 [0.496, 0.677] | 0.776 [0.720, 0.827] | 0.388 [0.304, 0.475] | 3.01 |
| Logistic fusion | 0.505 [0.411, 0.594] | 0.723 [0.669, 0.774] | 0.302 [0.229, 0.378] | 3.17 |
| PCG, size-aware prior | 0.390 [0.308, 0.474] | 0.700 [0.653, 0.744] | 0.359 [0.299, 0.421] | 2.99 |
| **PCG fused** | 0.351 [0.277, 0.422] | 0.607 [0.559, 0.653] | 0.198 [0.142, 0.257] | 3.63 |
| PCG fused, no context | 0.449 [0.364, 0.528] | 0.700 [0.648, 0.749] | 0.302 [0.227, 0.380] | 3.18 |

PCG fused minus PCG size-aware: both faults in top 3: -0.161 [-0.212, -0.114]; mean rank +0.64
[+0.44, +0.81]. **With two faults the fused model is worse than the model without mutation
evidence.**

## 14. Symptoms visible to a compiler, type checker or analyser

| Symptom | D1, 594 injected faults | D2, 31 human-written bugs |
|---|---|---|
| Program does not compile | 0 | 0 |
| Some failing test raises a type, name or attribute error | 42 | 0 |
| Some failing test raises another exception | 68 | 7 |
| Some failing test does not terminate | 47 | 3 |
| Failing tests only return wrong values | 438 | 22 |
| pylint reports a behavioural finding on some line | 30 | 0 |
| pylint reports one on the faulty line | 0 | 0 |

## 15. What the pre-registered hypotheses came to

| ID | Hypothesis | Outcome |
|---|---|---|
| H1 | The fused model ranks better than the spectrum-only model | **Supported on injected faults** (D1 Top-1 +0.409; stress test +0.182; D3 +0.564, all intervals far from zero). **Direction only on human-written bugs**: D2 Top-1 +0.130 [-0.050, +0.301], MRR +0.104 [-0.013, +0.220]; with in-suite parameters MRR +0.123 [+0.014, +0.232] |
| H2 | The fused model is not worse than logistic fusion by more than 0.02 MRR | **Holds on D1 and D3** (-0.004, -0.007). **Fails in the stress test** (-0.027). **Undecided on D2** (-0.033 [-0.113, +0.032]; +0.056 with in-suite parameters) |
| H3 | Conditioning mutation evidence on the coverage context lowers the log loss | **Refuted** on D1, D2 and D3: the unconditioned ablation has the better Brier score and log loss everywhere, and the better ranking on D2 |
| H4 | The size-aware prior lowers Brier score and ECE | **Refuted for Brier** (+0.0003, no difference); ECE 0.0454 to 0.0441. It helps large programs and hurts small ones |
| H5 | Posterior confidence gives a smaller AURC than Ochiai-based confidence | **Supported on D1** (-0.061 [-0.106, -0.030] against the Ochiai gap). **Direction only on D2** (-0.050 [-0.161, +0.015] against the gap; -0.200 [-0.267, -0.115] against the largest score) |
| H6 | Brier skill on human-written bugs stays above zero with parameters from injected faults | **Supported**: +0.132 (PCG v2), +0.222 (PCG fused); 31 bugs, wide intervals |

### Observations that were not hypothesised

1. **Mutation-only methods do worse than spectrum methods on human-written bugs** (Metallaxis Top-1
   0.305 against Ochiai 0.376), the reverse of the result on injected faults. This repeats the
   finding of Pearson et al. (2017) on a different benchmark.
2. **Probabilities of the model-based fusion transfer better than those of logistic fusion.** In
   distribution (D1) logistic fusion is better calibrated (ECE 0.009 against 0.045, log loss 0.055
   against 0.074). On other programs (D3) the fused model has the lower Brier score (-0.0088
   [-0.0135, -0.0048]). On human-written bugs logistic fusion's log loss (0.410) is worse than the
   base rate's (0.380) while the fused model's (0.316) is better; the Brier difference there is not
   significant.
3. **Recalibration does not transfer to human-written bugs.** In distribution it removes most of the
   miscalibration (ECE 0.045 to 0.005, Brier 0.0145 to 0.0095). On D2 the same kind of map makes the
   log loss worse (0.316 to 0.413) and leaves the Brier score unchanged. On D3 it helps. This
   mirrors what Spiess et al. (2025) report for code language models.
4. **With two faults, mutation evidence trained on single faults does harm** (section 13). "No
   variant makes a failing test pass" is strong evidence of innocence when there is one fault and is
   simply false when a second fault keeps the tests failing.
5. **The explanation first proposed for H3 was also wrong.** Conditioning on the coverage context
   was expected to pay off with two faults. It does not: the unconditioned ablation is better there
   too.
6. **Barinel and Ochiai are indistinguishable** on every dataset, as Barinel's single-fault theorem
   predicts.

### Not run

Real LLM evidence; BugsInPy and Defects4J; the nine QuixBugs programs with graph inputs.
