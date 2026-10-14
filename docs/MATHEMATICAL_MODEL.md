# Mathematical model

This document defines the model exactly as it is implemented. Each section names the code that
implements it. A complete numerical example is worked by hand in section 8 and is checked by the
test `tests/test_docs_example.py`.

## 1. What is being estimated

For one Python function that has been run against a test suite, we want, for every statement
`i`, the probability that the statement is faulty given everything observed:

```
P(F_i = 1 | test outcomes, static-analysis flags)
```

Five things are easy to confuse and are kept apart throughout:

| Notion | Meaning here | Is it observed? |
|---|---|---|
| Syntactically valid | The program compiles | Yes (compiler) |
| Flagged | A static analyser attached a behavioural warning to the statement | Yes (pylint) |
| Implicated | The statement was executed by a failing test | Yes (coverage) |
| Faulty (ground truth) | The statement's text differs from the reference program | Only in the benchmark, and only by the evaluation code |
| Probability of being faulty | The model's posterior belief `P(F_i = 1 | evidence)` | Computed |

"Faulty" has an operational definition: in the benchmark a statement is faulty if and only if a
mutation operator changed it. The model never sees this label for the program it analyses.

## 2. Random variables

| Symbol | Values | Role | Meaning |
|---|---|---|---|
| `F_i` | 0, 1 | latent | statement `i` is faulty (`i = 1..n`) |
| `T_j` | pass, fail | observed | outcome of test `j` (`j = 1..m`) |
| `A_i` | 0, 1 | observed, optional | pylint attached a behavioural finding to statement `i` |
| `C_i` | bin `1..B` | observed, optional | binned confidence signal for statement `i` (LLM channel) |
| `Theta` | grid `theta_1..theta_G` | latent | exposure rate: probability that an executed faulty statement makes a test fail |

Given structure (not random in the model):

* `S_j`, the **scope** of test `j`: the set of statements that can influence its outcome. By default
  `S_j` is the set of statements the test executed (its coverage). In the slicing variant it is the
  executed statements in the backward dependence slice of the statement that ended the test.

Conditioning on coverage is a simplification: in reality a fault can change which statements run.
This is standard in spectrum-based fault localisation and is listed in LIMITATIONS.md.

## 3. The graph

Code: `pcg/graph.py`, `pcg/dependence.py`.

| Node | Identifier | Carries |
|---|---|---|
| Statement | `s:<line>` | the latent variable `F_line` |
| Variable | `v:<name>` | a program variable |
| Test | `t:<index>` | the observed outcome `T_index`; a test is an input/output constraint |
| Diagnostic | `d:<line>:<symbol>` | one behavioural pylint finding |

| Edge | From, to | Meaning | Used by inference? |
|---|---|---|---|
| `in_scope` | statement, test | the statement is a parent of the test outcome in the Bayesian network | Yes: defines the noisy-OR factors |
| `flags` | diagnostic, statement | sets `A_i = 1` | Yes, when static evidence is enabled |
| `data` | statement, statement | the target may read a value the source wrote | Yes, in the slicing variant (they decide `in_scope`) |
| `control` | header, statement | the header decides whether the target runs | Yes, in the slicing variant |
| `def`, `use` | statement, variable / variable, statement | variable definitions and uses | Indirectly: data edges are derived from them |
| `executed` | statement, test | executed but sliced out of the scope | No (kept for display) |

The Bayesian network is read off this graph by `fault_model_from_graph`: there is one node `F_i`
per statement node, one node `T_j` per test node, and an arrow `F_i -> T_j` for every `in_scope`
edge. The test `test_removing_one_graph_edge_changes_the_posterior` deletes a single edge and
shows that the posterior changes.

## 4. Joint distribution

Code: `pcg/model.py`.

```
P(F, Theta, T, A) = P(Theta) * prod_i [ P(F_i) * P(A_i | F_i) ] * prod_j P(T_j | F_{S_j}, Theta)
```

**Prior.** `P(F_i = 1) = pi`, the same for every statement, and the `F_i` are independent a priori.
`P(Theta = theta_g) = w_g`.

**Test factor (noisy-OR).** Let `k_j(F) = sum over i in S_j of F_i` be the number of faulty
statements in the scope of test `j`. Then

```
P(T_j = pass | F, Theta) = (1 - lambda) * (1 - Theta)^{k_j(F)}
P(T_j = fail | F, Theta) = 1 - (1 - lambda) * (1 - Theta)^{k_j(F)}
```

Reading: every faulty statement in scope independently gets a chance `Theta` to break the test;
`lambda` (the leak) is the chance that the test fails for a reason the model has no variable for.
With no faulty statement in scope the test fails with probability `lambda`; with one, with
probability `1 - (1 - lambda)(1 - Theta)`.

**Static-evidence factor.** `P(A_i = 1 | F_i = 1) = alpha_1` and `P(A_i = 1 | F_i = 0) = alpha_0`.

**Confidence-signal factor (optional).** `P(C_i = b | F_i = f) = beta_{f,b}`, a table over `B` bins.
The raw confidence is never used as a probability; only its learned distribution among faulty and
fault-free statements is used.

### Per-statement evidence folds into the prior

Because `A_i` and `C_i` each depend on `F_i` only, Bayes' rule in odds form gives an *effective
prior* for each statement (code: `apply_likelihood_ratio`):

```
odds(F_i | A_i, C_i) = pi / (1 - pi) * P(A_i | F_i=1) / P(A_i | F_i=0) * P(C_i | F_i=1) / P(C_i | F_i=0)
```

The test factors then act on these effective priors. This is exact, not an approximation.

### Independence assumptions, stated plainly

1. Faults are independent a priori. Real faults cluster; this is a simplification.
2. Given `F` and `Theta`, test outcomes are independent of each other. Tests that exercise the same
   path are in fact correlated beyond what `F` explains; summing out a shared `Theta` captures part
   of that correlation, not all of it.
3. Given `F_i`, the static flag `A_i` is independent of the test outcomes. This can fail: an
   `undefined-variable` warning and a `NameError` in a test are two views of one defect, so using
   both counts some evidence twice. In the benchmark the flag is rare (about 1% of statements),
   which limits the effect; see LIMITATIONS.md.
4. Within one program version, all faults share one `Theta`. For a single fault this is no
   restriction. For several faults it is an approximation.

## 5. Parameter estimation

Code: `pcg/estimation.py`. Training data are single-fault mutants of programs **other than** the
one being analysed. All proportions use add-one (Beta(1, 1)) smoothing: `(successes + 1) / (trials + 2)`.

| Parameter | Estimator |
|---|---|
| `pi` | (number of faulty statements + 1) / (number of statements + 2), over all training mutants |
| `lambda` | (failing (mutant, test) pairs with the fault outside the scope + 1) / (such pairs + 2) |
| pooled `theta` | `q` = smoothed failing fraction of pairs with the fault inside the scope; `theta = 1 - (1 - q) / (1 - lambda)` |
| `alpha_1`, `alpha_0` | smoothed fraction of faulty / fault-free statements that are flagged |
| `beta_{f,b}` | (count in bin `b` + 1) / (count + B), separately for faulty and fault-free statements |

The step from `q` to `theta` is needed because, under the model, a test that executes the one
faulty statement fails with probability `q = 1 - (1 - lambda)(1 - theta)`, not `theta`.

### The exposure-rate prior, fitted by EM

Faults differ in how often they break a covering test, so `Theta` is not fixed. Its prior weights
`w_g` on the grid `theta_g = (g - 0.5) / G`, `G = 10`, are fitted to the training faults. Fault `f`
was executed by `n_f` tests of which `x_f` failed; under the model

```
x_f | Theta = theta_g  ~  Binomial(n_f, q_g),     q_g = 1 - (1 - lambda)(1 - theta_g)
```

so the `x_f` follow a mixture of binomials with unknown weights `w`. Expectation-maximisation:

```
E-step:  r_{f,g} = w_g * q_g^{x_f} (1 - q_g)^{n_f - x_f} / sum_h w_h * q_h^{x_f} (1 - q_h)^{n_f - x_f}
M-step:  w_g = (1 / N) * sum_f r_{f,g}
```

The log-likelihood is concave in `w`, so EM started from uniform weights climbs to the maximum.
Afterwards one pseudo-observation per grid point is mixed in, `w_g <- (N * w_g + 1) / (N + G)`, so
no weight is exactly zero. Tests: `test_em_recovers_a_two_component_exposure_mixture`,
`test_estimator_recovers_parameters_of_data_sampled_from_the_model`.

The estimated values of the current run are listed in `results/benchmark/SUMMARY.md`, section 2,
and per held-out program in `results/benchmark/params_lopo.json`.

## 6. Inference

Code: `pcg/model.py::exact_posterior`.

The wanted quantity is

```
P(F_i = 1 | T, A) = sum over (F, g) with F_i = 1 of P(F, theta_g, T, A)  /  sum over all (F, g) of P(F, theta_g, T, A)
```

**Why the posterior does not factorise.** A failing test says "at least one of my parents is
probably faulty". Learning that one parent is faulty makes the others less suspect (explaining
away). The `F_i` are therefore dependent a posteriori and cannot be scored one line at a time.

**Exact enumeration.** Statements that are in no scope are independent of all tests; their
posterior equals their effective prior. For the remaining `a` "active" statements the algorithm
sums all `2^a` fault configurations for each of the `G` grid points, in log space:

```
log w(F, g) = log w_g + sum_i [F_i log p_i + (1 - F_i) log(1 - p_i)] + sum_j log P(t_j | F, theta_g)
```

where `p_i` is the effective prior. It returns the marginals, `P(no fault | evidence)`, the
evidence `P(T)`, and the posterior over `Theta`.

| Property | Value |
|---|---|
| Exact or approximate | Exact (up to floating-point rounding) |
| Time | `O(G * 2^a * (a + m))` |
| Limit | `a <= 22` (about 4 million configurations); the benchmark maximum is 16 |
| Numerical stability | Sums in log space with the log-sum-exp trick; no probability is ever divided by a tiny number |
| Impossible evidence | If every configuration has probability zero (for example a failing test with an empty scope and `lambda = 0`), `ImpossibleEvidenceError` is raised. With `lambda > 0`, which the estimator guarantees, every outcome has positive probability |

**Validation.** `tests/test_model.py` compares the implementation with (1) a naive brute-force
enumeration on 80 random models, (2) two closed-form results, (3) the Bayesian-network library
pgmpy (variable elimination), to within `1e-9` or better.

**Gibbs sampling (fallback for `a > 22`).** `gibbs_posterior` resamples each `F_i` from
`P(F_i | F_{-i}, Theta, T)` and then `Theta` from `P(Theta | F, T)`, runs four chains, and reports
the Gelman-Rubin statistic. It is approximate; its error falls as `1 / sqrt(samples)`; and it can
mix slowly because the noisy-OR posterior has several modes when `lambda` is small. It is validated
against exact inference on a small model. It is not used in any reported experiment.

## 7. From posterior to decisions

* **Ranking.** Statements are sorted by `P(F_i = 1 | evidence)`.
* **Is there a fault at all?** `P(no fault | evidence)` is reported. Passing tests raise it but never
  to 1: tests cannot prove correctness.
* **Compiler evidence** is not probabilistic. If the program does not compile, it is certainly
  faulty; the parser's reported position is shown as a hint and no posterior is computed.
* **Unexecuted statements** keep their prior. The model has learned nothing about them, and says so.

## 8. Complete worked example

Three statements, three tests, one fixed exposure rate (a one-point grid) so that everything can be
done by hand.

```
pi = 0.1    theta = 0.8    lambda = 0.01

test 1: FAIL   scope {s1, s2}
test 2: pass   scope {s2, s3}
test 3: pass   scope {s3}
```

Per-test factor values: with `k` faulty statements in scope a test passes with probability
`0.99 * 0.2^k`, i.e. 0.99, 0.198, 0.0396 for `k` = 0, 1, 2, and fails with 0.01, 0.802, 0.9604.

| F1 F2 F3 | Prior | P(test 1 fails) | P(test 2 passes) | P(test 3 passes) | Likelihood | Prior x likelihood | Posterior |
|---|---|---|---|---|---|---|---|
| 0 0 0 | 0.729 | 0.0100 | 0.9900 | 0.9900 | 0.009801 | 0.0071449 | 0.0834 |
| 0 0 1 | 0.081 | 0.0100 | 0.1980 | 0.1980 | 0.000392 | 0.0000318 | 0.0004 |
| 0 1 0 | 0.081 | 0.8020 | 0.1980 | 0.9900 | 0.157208 | 0.0127339 | 0.1487 |
| 0 1 1 | 0.009 | 0.8020 | 0.0396 | 0.1980 | 0.006288 | 0.0000566 | 0.0007 |
| 1 0 0 | 0.081 | 0.8020 | 0.9900 | 0.9900 | 0.786040 | 0.0636693 | 0.7436 |
| 1 0 1 | 0.009 | 0.8020 | 0.1980 | 0.1980 | 0.031442 | 0.0002830 | 0.0033 |
| 1 1 0 | 0.009 | 0.9604 | 0.1980 | 0.9900 | 0.188258 | 0.0016943 | 0.0198 |
| 1 1 1 | 0.001 | 0.9604 | 0.0396 | 0.1980 | 0.007530 | 0.0000075 | 0.0001 |

Sum of the "prior x likelihood" column: `P(T) = 0.0856212`. Dividing each row by it gives the
posterior column. Marginals are sums of posterior rows:

```
P(F1 = 1 | T) = 0.7436 + 0.0033 + 0.0198 + 0.0001 = 0.7668
P(F2 = 1 | T) = 0.1487 + 0.0007 + 0.0198 + 0.0001 = 0.1693
P(F3 = 1 | T) = 0.0004 + 0.0007 + 0.0033 + 0.0001 = 0.0044   (summing the unrounded values)
P(no fault | T) = 0.0834
```

What the example shows:

* `s1` and `s2` are both in the failing test, yet `s1` is 4.5 times as suspect: `s2` also ran in a
  passing test, which counts against it by a factor `1 - theta = 0.2`.
* `s3` ran only in passing tests, so its probability fell from the prior 0.1 to 0.0044.
* 8% of the probability stays on "no fault at all, the failure was a leak". The model does not
  claim certainty.
* A per-line formula could not produce these numbers: `P(F2 | T)` depends on `s1` being available
  as a competing explanation.

**Adding static evidence.** Suppose pylint flags `s2` and the estimated likelihoods are
`alpha_1 = 0.2`, `alpha_0 = 0.05`. The likelihood ratio is 4, so the effective prior of `s2`
becomes `0.1 * 4 / (0.1 * 4 + 0.9) = 0.3077`, and the enumeration is repeated with that prior.

**Adding an uncertain exposure rate.** With the two-point prior `P(Theta = 0.2) = P(Theta = 0.8) = 0.5`
the same evidence gives `P(F1) = 0.6734`, `P(F2) = 0.2456`, `P(F3) = 0.0249` and
`P(Theta = 0.8 | T) = 0.6695`. The model is less sure which statement is to blame because the
passing tests are weaker evidence when the fault might rarely show itself.

## 9. Relation to known methods

The model is a member of a known family and no novelty is claimed for it.

* Noisy-OR Bayesian networks for diagnosis go back to Pearl (1988).
* Bayesian fault localisation from program spectra with an intermittent-failure parameter is the
  idea of Barinel (Abreu, Zoeteweij and van Gemund, 2009). Differences: this implementation
  computes exact statement marginals by full enumeration instead of ranking a heuristically
  generated list of diagnosis candidates; it sums the failure parameter out under a learned prior
  instead of maximising it per candidate; and it adds learned unary evidence factors.
* Ochiai and Tarantula (the baselines) are similarity coefficients on the same spectra and do not
  produce probabilities.

Full references are in REPORT.md.

## 10. Version 3 extension

Sections 1 to 9 describe the model of version 2, which is unchanged and is called `pcg` in the
research experiments. Version 3 adds two per-statement components. Their derivation, the
examination of the version-2 assumptions and a second worked example are in
[../research/v3/MATHEMATICAL_DESIGN.md](../research/v3/MATHEMATICAL_DESIGN.md). Code: `pcg/fusion.py`,
`pcg/mbfl.py`.

**Size-aware prior.** `P(F_i = 1) = min(mu / n, 1/2)`, where `n` is the number of statements and
`mu` the expected number of faulty statements in a program under analysis, estimated from the
training programs (`mu = 1` for single-fault data).

**Mutation-evidence factor.** Every single-edit variant of each statement is run on all tests.
The evidence variable `M_i` has five levels:

| Level | Meaning |
|---|---|
| 0 | no operator applies to the statement |
| 1 | no variant makes a failing test pass |
| 2 | some variant makes some, not all, failing tests pass |
| 3 | some variant makes all failing tests pass and breaks a passing one |
| 4 | some variant makes all tests pass |

and a coverage context `K_i`: executed by all, some or none of the failing tests. The factor is

```
P(M_i = v | F_i, K_i = all)   learned table
likelihood ratio = 1          for K_i = some or none
```

because a variant of a statement that a failing test does not execute cannot change that test.

**Joint distribution.**

```
P(F, Theta, T, A, M | K) = P(Theta) · Π_i [ P(F_i) P(A_i | F_i) P(M_i | F_i, K_i) ] · Π_j P(T_j | F_{S_j}, Theta)
```

The new factor depends on `F_i` only, so it folds into the effective prior exactly as the static
factor does (section 4), and inference is unchanged.

**Estimated table** (pooled over the project's benchmark; each evaluated program uses a table that
excludes its own mutants):

| Level | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| `P(M | F = 1, all)` | 0.1402 | 0.0134 | 0.0083 | 0.0150 | 0.8230 |
| `P(M | F = 0, all)` | 0.1794 | 0.5874 | 0.1728 | 0.0552 | 0.0051 |
| likelihood ratio | 0.78 | 0.023 | 0.048 | 0.27 | 162 |

Two warnings about these numbers. The ratio 162 for level 4 is so large because on injected faults
the exact repair is usually among the variants. And the ratio 0.023 for level 1 is valid only when
there is a single fault; with two faults it misleads (LIMITATIONS, section 2).

**What the experiments say about these components** (EXPERIMENTS, section 15): the mutation factor
improves ranking; the conditioning on `K_i` did *not* help, the unconditioned table gave better
probabilities on every dataset; the size-aware prior made no overall difference.

**Recalibration.** `p' = sigmoid(a · logit(p) + b)` with `a > 0`, fitted on other programs. It is
monotone, so it cannot change a ranking. Fitted slope on the benchmark: `a` between 1.36 and 1.49.

**Selective localisation.** Answer with the top-ranked statement only if the largest posterior
exceeds a threshold. Quality is measured by the area under the risk-coverage curve.
