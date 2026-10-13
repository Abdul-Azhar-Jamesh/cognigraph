# Mathematical design of the extension (version 3)

Written before implementation. Section 2 examines the existing model; sections 3 to 7 specify the
changes; section 8 lists the properties that must be tested; section 9 gives a worked example whose
numbers the tests must reproduce.

Notation: `n` statements, `m` tests, `F_i` in {0,1} the fault indicator of statement `i`,
`T_j` the outcome of test `j`, `S_j` the set of statements test `j` executed, `Theta` the exposure
rate, `lambda` the leak.

## 1. Two different questions

1. **Is the inference correct for the specified model?** Yes, to numerical precision: exact
   enumeration agrees with naive brute force, with closed forms, with pgmpy, and with an independent
   recomputation from raw records ([BASELINE.md](BASELINE.md), section 3).
2. **Is the specified model a good description of faults?** Only partly. Section 2 lists where it
   is known to be wrong. Agreement with brute force says nothing about this question; it is
   answered empirically by calibration on data the parameters did not see.

## 2. Examination of the existing model (version 2.0.0)

| Aspect | Definition | Assessment |
|---|---|---|
| `F_i` | 1 if the text of statement `i` differs from the reference program | Operational. A statement that should exist but does not (omission) has no variable |
| `T_j` | fail if the observable behaviour (return value or exception type) differs from the oracle | Sound for deterministic code |
| `S_j` | statements executed by test `j` in the faulty program | Treated as fixed although a fault can change it |
| Prior | `F_i` independent Bernoulli(`pi`), one `pi` for all programs | **Mis-specified**, see 2.1 |
| Likelihood | `P(T_j = pass | F, Theta) = (1 - lambda)(1 - Theta)^{k_j}`, `k_j` = number of faulty statements in `S_j` | Noisy-OR. Cannot express masking or faults that need each other |
| `lambda` | `P(fail)` when no modelled fault was executed | Covers flaky tests and unmodelled faults. Estimated as 0.0006 because the benchmark is deterministic; on other code it would be larger |
| `Theta` | probability that an executed fault breaks a test; latent, shared by all faults of a program version | Fault-specific in reality. Exact for one fault; an approximation for several |
| Test independence | Outcomes independent given `F` and `Theta` | Violated by near-duplicate tests; a known source of over-confidence |
| Per-statement evidence | `A_i` depends on `F_i` only | **Questionable** for evidence derived from the same executions, see section 4 |
| Passing tests | Lower the fault probability of what they execute by `(1 - Theta)` each | Correct in direction; too strong if tests are dependent |
| Unexecuted statements | Posterior = prior | Honest; means incomplete coverage caps what can be concluded |
| Normalisation, stability | Log-space enumeration with log-sum-exp; impossible evidence raises an error | Verified |
| Complexity | `O(G 2^a (a + m))` | Exponential; adequate up to 22 executed statements |

### 2.1 The constant prior is wrong for the task

The model is applied to programs that are known to be faulty. In the benchmark each analysed
program has exactly one faulty statement, placed in a program of `n` statements. The marginal
probability that a given statement is the faulty one is then `1/n`, not a constant.
Version 2.0.0 pools: `pi = (number of faults + 1) / (number of statements + 2) = 0.1236`. For a
program with 4 statements the true rate is 0.25; for one with 16 it is 0.0625. Consequences:

* statements whose posterior stays near the prior (unexecuted ones, and weakly implicated ones) are
  miscalibrated in a way that depends on program size;
* probabilities are not comparable across programs of different sizes;
* the prior probability of "no fault", `(1 - pi)^n`, shrinks with program size for no reason.

### 2.2 Identifiability

* With labelled single-fault data, `lambda` and `q = 1 - (1 - lambda)(1 - theta)` are binomial
  proportions and are identified; so is `theta`.
* The mixing weights of `Theta` are identified only up to the information in the per-fault counts:
  a mixture of binomials with `n_f` trials determines at most the first `n_f` moments of the mixing
  distribution. With 7 to 16 tests per program the fit is coarse; the EM solution concentrates on
  three or four grid points, which is typical of such estimators and should not be over-read.
* Without labels, the parameters cannot be estimated from the spectrum of one program. They must be
  transferred from other programs, which is why behaviour under distribution shift is a central
  question of this proposal.

### 2.3 Duplication between evidence sources

* An `undefined-variable` warning and a `NameError` in a test are two observations of one defect.
  The static factor and the test factors both count it. The flag is rare (1.2% of fault-free
  statements) so the effect is small; it is left as documented in LIMITATIONS.
* Mutation evidence is derived from the *same test executions* as the coverage evidence. This
  dependence is strong and is treated explicitly in section 4.

## 3. Size-aware prior

**Assumption.** A program submitted for localisation contains on average `mu` faulty statements,
and a priori every statement is equally likely to be one of them.

**Prior.** `pi_n = min(mu / n, 1/2)`.

**Estimation.** `mu_hat` = mean number of faulty statements per training case. For single-fault
training data `mu_hat = 1`. The cap at 1/2 only matters for `n < 2 mu`.

**Justification.** Under the assumption, `E[sum_i F_i] = n * pi_n = mu` for every program size, and
the marginal fault rate of a statement in a program of size `n` is exactly `mu / n`. The constant
prior of version 2.0.0 is the special case in which all programs have the same size.

**What it does not fix.** `mu = 1` is a property of benchmarks with one fault per program. It is
appropriate for "the tests fail, find the fault" and is not a claim about fault density in software.
The prior of "no fault" becomes `(1 - mu/n)^n`, about `e^{-mu} = 0.37` for all sizes, which is
arbitrary for programs whose tests all pass; the fault-free experiment reports its effect.

## 4. Mutation-analysis evidence

### 4.1 Observation

Let `P` be the program under analysis, with failing tests `T_F` (non-empty) and passing tests
`T_P`. For statement `i`, let `Mut(i)` be its single-edit variants (the operators of
`pcg/mutation.py`). Each variant `u` is run on all tests. Define

```
f2p(u) = number of tests in T_F that pass under u
p2f(u) = number of tests in T_P that fail under u
```

The evidence variable `M_i` takes one of five levels:

| Level | Meaning |
|---|---|
| 0 | `Mut(i)` is empty: no operator applies to the statement |
| 1 | no variant makes any failing test pass |
| 2 | some variant makes some, but not all, failing tests pass |
| 3 | some variant makes all failing tests pass, and every such variant breaks a passing test |
| 4 | some variant makes all tests pass |

Variants that do not compile or produce no result within the limits are ignored.

### 4.2 Why a naive factor would double count

**Fact.** If no failing test executes statement `i`, then no variant of `i` changes the outcome of
any failing test. (The variant differs from `P` only in statement `i`; a run that never reaches `i`
is identical in both.) Hence `M_i` is at most 1, whatever `F_i` is.

So for such statements `M_i` carries **no information about `F_i` beyond what coverage already
gave**. A single table `P(M_i | F_i)` estimated over all statements would nevertheless assign them
a likelihood ratio below 1, because "level 1" is more common among fault-free statements overall.
The same coverage fact would be counted twice: once by the noisy-OR factors and once by the
mutation factor.

The same argument applies in a weaker form to statements executed by only some failing tests: they
cannot reach levels 3 or 4.

### 4.3 Coverage-conditioned likelihood

Define the coverage context of a statement, a deterministic function of the observed spectrum:

```
K_i = all   if every failing test executed statement i
K_i = part  if some but not all failing tests executed it
K_i = none  if no failing test executed it
```

The factor is `P(M_i | F_i, K_i)`:

| Context | Likelihood ratio used | Reason |
|---|---|---|
| `none` | exactly 1 | Section 4.2: the evidence is determined by coverage |
| `part` | exactly 1 | In single-fault training data a faulty statement always has context `all`, so `P(M | F=1, part)` cannot be estimated. Using 1 means "no evidence", which is safe |
| `all` | `P(M_i = v | F_i = 1, all) / P(M_i = v | F_i = 0, all)` from learned tables | Both tables are estimated only among statements that all failing tests executed, so the comparison is between like and like |

**Estimation.** For level `v` and `f` in {0, 1}:

```
P(M = v | F = f, all) = (count of training statements with context all, fault state f, level v  + 1)
                        / (count of training statements with context all and fault state f  + 5)
```

Training statements come from detected mutants of other programs only.

**Joint distribution of version 3.**

```
P(F, Theta, T, A, M | K) = P(Theta) · Π_i [ P(F_i) P(A_i | F_i) P(M_i | F_i, K_i) ] · Π_j P(T_j | F_{S_j}, Theta)
```

with `P(F_i = 1) = pi_n`. As before, the per-statement factors fold into an effective prior by Bayes'
rule in odds form, and the test factors are handled by exact enumeration. Complexity is unchanged.

**Remaining assumption, stated plainly.** Given `F_i` and the context, `M_i` is treated as
independent of the test outcomes and of the other `M_k`. This is not exactly true: for instance two
statements can both admit a variant that makes all tests pass. The discriminative baseline makes no
such assumption, so comparing the two (P2) measures what the assumption costs.

**Graph.** Each statement with a non-trivial factor gets an evidence node `m:<line>` carrying the
level and the context, with an edge to its statement. `fault_model_from_graph` reads the level and
context from that node; removing the node removes the factor.

## 5. Recalibration

For a posterior `p` define `z = log(p / (1 - p))` and

```
p' = sigmoid(a z + b)
```

with `a > 0` and `b` chosen to minimise the log loss on statements of other programs (Platt scaling
on the log-odds; with `b = 0` this is temperature scaling with temperature `1/a`).

**Leakage control.** When program `X` is evaluated, `(a, b)` are fitted on posteriors of programs
`Y != X` that were themselves computed with parameters from programs other than `X` and `Y` (nested
leave-one-program-out). For the external benchmark, `(a, b)` are fitted on the out-of-fold
posteriors of the project's benchmark only.

**Property.** For `a > 0` the map is strictly increasing, so it cannot change the order of
statements. Recalibration can improve probabilities and cannot improve or harm any ranking metric.

## 6. Selective localisation

Confidence of a localisation result: `c = max_i p_i`, the largest posterior. Decision rule: answer
with the top-ranked statement if `c >= tau`, otherwise abstain.

For a set of cases sorted by decreasing confidence, at coverage `k/N` (the `k` most confident
cases are answered):

```
selective accuracy(k) = mean Top-1 of the k most confident cases
risk(k)               = 1 - selective accuracy(k)
AURC                  = mean over k = 1..N of risk(k)
```

Top-1 is the tie-aware expected value used throughout. Lower AURC is better. Two reference values
are reported with it: the AURC of a confidence that carries no information (equal to the overall
error rate in expectation) and of an oracle confidence that answers the correct cases first.

Confidences compared: largest posterior (`pcg`, `pcg_size`, `pcg_fused`), largest predicted
probability (`lr_spectrum`, `lr_fusion`), the largest Ochiai score, and the gap between the largest
and second-largest Ochiai score.

## 7. Baselines, specified

**Barinel.** Candidates `d`: all minimal hitting sets of the failing tests' coverage with at most 3
statements. `Pr(d) = p^{|d|} (1 - p)^{n - |d|}` with `p` the same prior the PCG model uses.
`Pr(e | d) = max over h in [0,1]^{|d|} of Π_pass Π_{j in d, executed} h_j · Π_fail (1 - Π_{j in d, executed} h_j)`.
For `|d| = 1` the maximiser is `h = n_pass / (n_pass + n_fail)` over the tests executing the
statement. For larger `d` the maximum is found numerically. A statement's score is the largest
posterior of a candidate that contains it, which reproduces the order in which statements appear in
Barinel's ranked diagnosis; statements in no candidate score 0. Check: the paper's example
(`Pr(e | {1,2}) = 0.185`, `Pr(e | {1,3}) = 0.036`, posteriors 0.839 and 0.161).

**Metallaxis.** A variant `u` *kills* a test if the test's behaviour signature under `u` differs
from its signature under `P`. With `kf(u)`, `kp(u)` the numbers of failing and passing tests
killed: `score(u) = kf(u) / sqrt(|T_F| (kf(u) + kp(u)))`, 0 if undefined; statement score = maximum
over its variants; 0 for a statement without variants.

**MUSE.** `score(u) = f2p(u) - alpha * p2f(u)` with `alpha = (sum_u f2p(u)) / (sum_u p2f(u))` over
all variants of the program (`alpha = 0` if the denominator is 0); statement score = mean over its
variants; a statement without variants is ranked below all others.

**Hybrid average.** Mean of the Ochiai score and the Metallaxis score, both in [0, 1].

**Logistic regression.** `P(F_i = 1 | x_i) = sigmoid(w · x_i + w_0)`, fitted on the statements of
the detected training mutants by Newton's method with an L2 penalty of 1.0 on the weights of
standardised features. Spectrum features: `ef/F`, `ep/P`, Ochiai, Tarantula, indicator of context
`all`. Fusion adds: Metallaxis, MUSE, five indicators for the level `M_i`, the static flag.
Because it minimises log loss, it is calibrated on its training distribution by construction, which
makes it the right competitor for the probabilistic metrics.

## 8. Properties that the tests must establish

| # | Property | How it is checked |
|---|---|---|
| T1 | With all likelihood ratios equal to 1 the fused model equals the spectrum-only model | Direct comparison |
| T2 | For contexts `none` and `part` the factor is exactly 1 whatever the level | Unit test |
| T3 | A statement that no failing test executes has level at most 1 | Checked on every benchmark case |
| T4 | Raising a statement's likelihood ratio raises its posterior | Monotonicity test |
| T5 | Learned tables are probability distributions and recover the generating tables on simulated data | Simulation |
| T6 | Size-aware prior: expected number of faults equals `mu` for every `n >= 2 mu` | Arithmetic test |
| T7 | Recalibration with `a > 0` leaves every ranking metric unchanged | Before/after comparison |
| T8 | Barinel reproduces the worked example of its paper | Numerical test |
| T9 | Metallaxis and MUSE reproduce hand-computed values on a small example | Numerical test |
| T10 | Logistic regression recovers known coefficients on simulated data and its gradient is zero at the solution | Numerical test |
| T11 | AURC equals the hand-computed value on a small example; an oracle confidence gives the minimum | Numerical test |
| T12 | The worked example of section 9 | Numerical test |
| T13 | No inference function receives ground truth; training folds exclude the evaluated program for every learned quantity (model parameters, mutation tables, regression weights, recalibration map) | Signature and fold tests |
| T14 | All result files of version 2.0.0 are reproduced bit for bit after the extension | Hash comparison with the stored manifest |

## 9. Worked example

Three statements, three tests, fixed `theta = 0.8`, `lambda = 0.01`.

```
test 1: FAIL  executed {s1, s2}
test 2: pass  executed {s2, s3}
test 3: pass  executed {s3}
```

**Step 1, size-aware prior.** `mu = 1`, `n = 3`, so `pi = 1/3` for every statement. With spectrum
evidence only, exact enumeration gives

```
P(F1) = 0.8327   P(F2) = 0.2378   P(F3) = 0.0196   P(no fault) = 0.0182
```

(With the constant prior 0.1 of the earlier example the values were 0.7668, 0.1693, 0.0044.)

**Step 2, contexts.** The only failing test executed `s1` and `s2`: `K1 = K2 = all`. It did not
execute `s3`: `K3 = none`.

**Step 3, mutation evidence.** Suppose a variant of `s1` makes all tests pass (level 4), no variant
of `s2` makes test 1 pass (level 1), and `s3` has level 1. Take these illustrative tables for
context `all` (they are not estimates):

| Level | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| `P(M | F=1, all)` | 0.05 | 0.15 | 0.05 | 0.15 | 0.60 |
| `P(M | F=0, all)` | 0.10 | 0.60 | 0.10 | 0.10 | 0.10 |

Likelihood ratios: `s1`: 0.60 / 0.10 = 6. `s2`: 0.15 / 0.60 = 0.25. `s3`: 1, because its context
is `none`.

**Step 4, effective priors.** Prior odds are `(1/3)/(2/3) = 0.5`.

```
s1: odds 0.5 * 6    = 3      ->  0.7500
s2: odds 0.5 * 0.25 = 0.125  ->  0.1111
s3: odds 0.5 * 1    = 0.5    ->  0.3333
```

**Step 5, posterior.** Enumeration with these priors and the same test factors:

```
P(F1) = 0.9880   P(F2) = 0.0367   P(F3) = 0.0196   P(no fault) = 0.0039
```

**What the example shows.**

* The mutation evidence moved `s1` from 0.83 to 0.99 and `s2` from 0.24 to 0.04: the two
  statements that coverage could not separate well are now clearly separated.
* `s3` is unchanged at 0.0196: its mutation evidence is ignored because coverage already explains
  it.
* **Without context conditioning** `s3` would also receive the ratio 0.25, its effective prior would
  drop to 0.1111 and its posterior to 0.0050: a fourfold reduction produced by counting the fact
  "no failing test runs `s3`" twice.

**Recalibration example.** With `a = 0.7`, `b = -0.3`: 0.90 becomes 0.7752, 0.50 becomes 0.4256,
0.10 becomes 0.1373. The order is preserved.

## 10. Amendments made during implementation

The text above is unchanged from the version written before implementation. Three things were
learned while implementing it; they are recorded here instead of being edited in.

**A1. The worked example in the Barinel paper is not an exact maximum (affects T8).** For the
candidate `{1, 2}` the paper reports `Pr(e | d) = 0.185` at `h = (0.47, 0.19)`. The likelihood is
`(1 - h1 h2)(1 - h2)(1 - h1) h1`, which decreases in `h2` for every `h1`, so its maximum is on the
boundary: `h2 = 0`, `h1 = 1/2`, value `1/4`. For `{1, 3}` the exact maximum is `1/27 = 0.0370` at
`h = (1/3, 1/2)`, against the reported 0.036. The paper's numbers are what an unconverged gradient
ascent returns. The test therefore checks two things: the likelihood *function* reproduces the
paper's values at the paper's `h`, and the optimiser finds the exact maxima. The ranking of the two
candidates is the same either way; the posteriors are 0.871 and 0.129 instead of 0.839 and 0.161.

**A2. A statement whose only applicable edit was already applied has no variants.** The deletion
operator turns a statement into `pass`, and no operator applies to `pass`. Such a statement gets
level 0 ("no variant"). Level 0 is therefore informative on injected faults for a reason that has
nothing to do with real bugs; see LIMITATIONS.

**A3. Property T3 was confirmed on every case.** In all 594 + 410 + 413 analysed programs, every
statement that no failing test executed had level 0 or 1 (an assertion in `collect_evidence`).
