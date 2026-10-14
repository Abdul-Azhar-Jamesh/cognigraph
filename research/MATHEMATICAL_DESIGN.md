# Mathematical design: interventional multi-fault diagnosis (version 4)

Written before any code of the new model existed. The version 3 design is kept unchanged in
[v3/MATHEMATICAL_DESIGN.md](v3/MATHEMATICAL_DESIGN.md). Amendments made after implementation are
appended in section 12 and never edited into the text above them.

## 1. Why the version 3 model fails with two faults

Version 3 summarises the mutation analysis of statement `i` by one level `M_i` and multiplies the
prior odds of `F_i` by a ratio learned from single-fault programs. In single-fault data, "a variant
makes some but not all failing tests pass" is 20 times more frequent for fault-free statements
(learned ratio 0.048) and "no variant makes a failing test pass" 40 times more (ratio 0.023).

With two faults `i` and `g`, the exact repair of `i` leaves every test that `g` breaks failing. So
the correct statement shows precisely the pattern that the single-fault table reads as innocence.
The table is not wrong; it answers a question about a different population. A table cannot fix
this, because what a variant of `i` does depends on **which other statements are faulty**. That
dependence has to be in the model.

## 2. Variables and notation

| Symbol | Meaning | Status |
|---|---|---|
| `n`, `m` | statements, tests | given |
| `C[j,i]` | test `j` executes statement `i` in the analysed program | observed |
| `y_j` | test `j` fails on the analysed program | observed |
| `F_i` | statement `i` is faulty | latent |
| `Theta` | exposure rate, on a grid with weights `w` | latent |
| `k_j(F)` | `sum_i C[j,i] F_i`, faulty statements test `j` executes | derived |
| `v`, `s(v)` | a variant (single edit) and the statement it edits | given |
| `z[v,j]` | for a failing test `j` that executes `s(v)`: the variant makes it pass | observed |
| `b[v,j]` | for a passing test `j` that executes `s(v)`: the variant makes it fail | observed |
| `A_i` | some variant of `i` is a repair of the fault at `i` | latent |
| `R_v` | type of variant `v`: repair, masker or inert | latent |

A test that does not execute `s(v)` cannot be changed by `v`: the programs are deterministic and the
edit is never reached. Those pairs carry no information and are not modelled.

## 3. Generative model

**Faults.** `F_i ~ Bernoulli(pi_n)` independently, `pi_n = min(mu / n, 0.5)`.

**Mechanism of a test.** For every test `j` and every faulty statement `i` it executes there is a
latent exposure `X[j,i] ~ Bernoulli(Theta)`, and a leak `L_j ~ Bernoulli(lambda)`:

```
y_j = L_j  OR  OR_i X[j,i]            so   P(y_j = 1 | F, Theta) = 1 - (1 - lambda)(1 - Theta)^k_j
```

This is exactly the version 2 model; nothing changes when no variants are observed.

**A variant is an intervention.** Variant `v` replaces statement `s = s(v)` by other code.

* *Repair* (possible only if `F_s = 1`). The fault at `s` is removed, so the exposures `X[j,s]`
  disappear. A failing test `j` becomes passing exactly when nothing else made it fail:

  ```
  P(z[v,j] = 1 | y_j = 1, F, Theta, repair)
      = gamma * P(L_j = 0, X[j,i] = 0 for all faulty i != s | y_j = 1)
      = gamma * (1 - lambda) * Theta * (1 - Theta)^(k_j - 1) / (1 - (1 - lambda)(1 - Theta)^k_j)
      =: gamma * q(k_j, Theta)
  ```

  `gamma <= 1` allows a repair that is only partial. A passing test stays passing except with
  probability `beta`.
* *Masker*: a change that makes tests pass or fail for reasons unrelated to repair (for example an
  early return). Flips each failing test it reaches with probability `psi`, breaks each passing
  test with probability `eta_m`.
* *Inert*: flips with probability `epsilon`, breaks with probability `eta_0`.

Type probabilities: a variant of a fault-free statement, or of a faulty statement that has no
repair among its variants (`A_s = 0`), is a masker with probability `kappa`, else inert. If
`F_s = 1` and `A_s = 1` (probability `alpha`), each variant is a repair with probability `rho`, and
otherwise a masker or inert as above.

**The key quantity.** `q(k, Theta)` is the probability that a failing test fails *only* because of
the statement under repair:

| | `q(1, Theta)` | `q(2, Theta)` | `q(3, Theta)` |
|---|---|---|---|
| `lambda -> 0` | 1 | `(1 - Theta) / (2 - Theta)` | `(1 - Theta)^2 / (3 - 3 Theta + Theta^2)` |
| `Theta = 0.5` | 1 | 0.333 | 0.143 |
| `Theta = 0.9` | 1 | 0.091 | 0.009 |

With one fault a repair flips every failing test (up to `gamma`). With a second fault in the same
test it usually does not. The version 3 table had no way to express this.

## 4. Likelihood of the variant evidence

Write `N_v` for the likelihood of the observations of `v` when `v` is not a repair:

```
N_v = kappa * prod_j psi^z (1-psi)^(1-z) * prod_j eta_m^b (1-eta_m)^(1-b)
    + (1-kappa) * prod_j epsilon^z (1-epsilon)^(1-z) * prod_j eta_0^b (1-eta_0)^(1-b)
```

and `Rep_v(F, Theta)` when it is:

```
Rep_v = prod_{j failing, C[j,s]=1} (gamma q(k_j,Theta))^z (1 - gamma q(k_j,Theta))^(1-z)
      * prod_{j passing, C[j,s]=1} beta^b (1-beta)^(1-b)
```

`N_v` does not depend on `F`. For the variants `V_s` of one statement:

```
P(obs of V_s | F_s = 0)         = prod_v N_v
P(obs of V_s | F_s = 1, F, Th.) = (1-alpha) prod_v N_v + alpha prod_v [rho Rep_v + (1-rho) N_v]
```

Dividing by `prod_v N_v`, the whole variant evidence enters the posterior as one factor per
*faulty* statement:

```
Lambda_s(F, Theta) = (1 - alpha) + alpha * prod_{v in V_s} [ 1 + rho (Rep_v(F,Theta) / N_v - 1) ]
```

and `Lambda_s = 1` for statements without variants. `Lambda_s >= 1 - alpha` always: failing to find
a repair can lower the odds of a statement by at most the factor `1 - alpha`, however many variants
were tried.

**Posterior.**

```
P(F | data) ∝ sum_Theta w(Theta) * prod_i pi_n^F_i (1-pi_n)^(1-F_i)
              * prod_j P(y_j | k_j(F), Theta)
              * prod_{s: F_s = 1} Lambda_s(F, Theta)^tau
```

`tau` in (0, 1] is a temperature for the variant layer (section 7). `tau = 1` is the model as
written.

## 5. Relation to existing methods

| Method | Recovered as |
|---|---|
| PCG version 2 | no variants: all `Lambda_s = 1` |
| PCG version 3 fusion | restrict to `|F| = 1`: then `k_j = 1`, `q = q(1,Theta)`, and `Lambda_s` is a number per statement, a likelihood ratio like the version 3 table but computed from the variant outcomes instead of five levels |
| Barinel | no variants, per-candidate health instead of a shared `Theta`, candidates from minimal hitting sets |
| Kang, Choi and Yoo (2023), appendix | single fault, `lambda = 0`: a MUSE-like score from the Bayesian formula. Their stated limitation, the single-fault assumption, is what `q(k, Theta)` removes |
| MUSE | counts failing-to-passing and passing-to-failing changes per variant; the same observations, as a score |
| QMR-DT / Quickscore (Heckerman 1989) | the same bipartite noisy-OR structure for diseases and findings; here extended by interventions on the causes |

What is new relative to these is the intervention layer with a flip probability that depends on the
other faults in the test's scope. I found no earlier model with this property (search record in
RELATED_WORK_AND_NOVELTY.md). That is a search-limited statement.

## 6. Inference

**Bounded cardinality.** Enumerate every `F` with `|F| <= c` (default `c = 3`), compute the
unnormalised log posterior for every grid value of `Theta`, normalise over the enumerated set.
Number of configurations `sum_{r<=c} C(n, r)`: 1,351 for `n = 20`, 20,876 for `n = 50`, 166,751 for
`n = 100`. Cost `O(N_c * G * (m + c * Vbar * m_f))` with `G` grid points, `Vbar` variants per
statement, `m_f` failing tests.

**What the truncation does.** It is exact inference in the model whose prior is conditioned on
`|F| <= c`. It is *not* a bound on the error relative to the unrestricted model: evidence can in
principle demand more than `c` faults. Therefore:

* for programs with at most 16 executed statements the unrestricted posterior (all `2^a`
  configurations) is also computed and the largest difference of any marginal is reported;
* the posterior mass on `|F| = c` is reported as a warning signal (mass at the boundary).

**Checks.** (i) With no variants the result must equal version 2 exact inference restricted to
`|F| <= c`. (ii) Against brute-force enumeration written independently in the tests, with random
variant outcomes. (iii) With `|F| <= 1` and `alpha = 0` the marginals must equal the single-fault
closed form.

## 7. The variant layer is a composite likelihood

The product over variants treats them as independent given `F` and `Theta`. They are not:

1. variants of the same statement see the same exposures `X[j,s]`;
2. for a test with two faults, "repair of `i` flips it" and "repair of `g` flips it" are mutually
   exclusive events (only one fault can be the sole cause), but the product treats them as
   independent;
3. `Theta` is shared by all faults, although faults differ in exposure.

Multiplying dependent terms as if independent gives correct point estimates in many settings but
over-states the amount of evidence (Varin, Reid and Firth 2011). The expected symptom is
over-confident posteriors. Two remedies are specified in advance:

* **Temperature `tau`**, chosen on training programs only by minimising the log loss of the
  marginals (grid 0.25, 0.5, 0.75, 1.0).
* **Reporting calibration** (Brier, log loss, ECE) for `tau = 1` and for the selected `tau`.

## 8. Parameter estimation and identifiability

All parameters are estimated on single-fault programs other than the one analysed.

* `kappa, psi, epsilon, eta_m, eta_0`: two-component mixture fitted by EM on the variants of
  fault-free statements.
* `alpha, rho, gamma, beta`: EM on the variants of the faulty statements, with `N_v` fixed from the
  previous step and `q = q(1, Theta) ≈ 1` (leak is of order 0.001).
* `lambda`, the grid weights `w`, `mu`: as in versions 2 and 3.

Identifiability. `alpha` is the share of faulty statements that have at least one repair-like
variant; `rho` the share of repair-like variants among the variants of such statements; `gamma` the
share of failing tests a repair flips; all three are identified from single-fault data whenever
some statements have several variants and several failing tests. **`q(k, Theta)` for `k >= 2` has
no free parameter**: it is implied by the noisy-OR mechanism. The multi-fault behaviour of the
model is therefore a *prediction* from single-fault data, not something fitted to multi-fault data.
That is what makes the experiment in section 10 a real test.

Known weak point: `alpha` is a property of the fault population. Injected faults are produced by
the same operators as the variants, so `alpha` learned there is high (about 0.83 of faulty
statements have a restoring variant); for human-written bugs it is low (5 of 31 in QuixBugs). The
bound `Lambda_s >= 1 - alpha` limits the damage but does not remove it. Reported both ways:
parameters transferred from injected faults, and parameters estimated on human-written bugs of
other programs.

## 9. Calibration and uncertainty

The marginals `P(F_i = 1 | data)` are evaluated as probabilities exactly as in version 3. Under
multiple faults the base rate changes (two faulty statements among `n`), and the prior still
expects `mu = 1`; a shift in the number of faults is part of what is tested.

## 10. Predicted behaviour in controlled scenarios

These were written down before running anything.

| Scenario | Prediction |
|---|---|
| S1 One fault, a repair variant exists, 4 failing tests | Same ranking as version 3; `Lambda` large for the faulty statement |
| S2 Two faults `i`, `g`; all failing tests execute both; repair variants exist for both | Each repair flips only part of the failing tests. Version 3 reads both as "partial" (ratio 0.048) and demotes them. New model: `{i, g}` explains all flips and non-flips; both marginals high |
| S3 Two faults, repair exists only for `i` | `i` high. `g` identified only as well as coverage allows; the non-flipped tests raise every statement they execute |
| S4 One fault, no repair variant (the human-bug case) | Evidence against the faulty statement bounded by `1 - alpha`; ranking falls back towards the coverage-only model |
| S5 A masker on a fault-free statement flips all failing tests and breaks passing ones | `N_v` explains it (`psi`, `eta_m` high); `Rep_v / N_v` small because repairs rarely break passing tests |
| S6 Data generated from the model itself with coupled exposures | Marginals over-confident at `tau = 1`, better calibrated at `tau < 1` (section 7) |
| S7 Three faults, `c = 3` | Still exact; with four faults and `c = 3` the truncation is wrong by construction and the boundary mass should be large |

## 11. Counterexamples and edge cases

* **Fault interaction.** If fault `g` is only reachable because of fault `i` (or masks it), the
  independent exposures are wrong. Repairing `i` may then flip tests "belonging" to `g`. The model
  will read this as strong evidence for `i` alone and miss `g`.
* **Coverage changes under a variant.** `k_j` is computed from the coverage of the analysed
  program. A repair can change which statements a test executes.
* **Omission faults.** A deleted statement has no variants and no coverage of its own.
* **No failing test executes `s`.** Then no `z` exists for its variants; only breaks of passing
  tests are observed, and `Rep_v / N_v` is close to 1.
* **Equivalent variants** behave as inert and are harmless.
* **All tests fail.** `q` is still defined; passing-test evidence is absent.

## 12. Amendments after implementation

The text above is the design as written before coding. These changes were made on development data
(D1) before the protocol was frozen and before any held-out data were used.

**A1. More than two kinds of non-repair variant.** The design had two kinds, masker and inert. On
D1 the two components were absorbed by differences in how often variants *break passing tests*
(94% against 21%), not by flipping. The mixture now has `K` kinds, each with a flip rate `psi_c`
and a break rate `eta_c`: `N_v = sum_c kappa_c * Bin(flips; psi_c) * Bin(breaks; eta_c)`. `K = 5` by
BIC on D1 (58,683; 54,258; 53,522; 53,131; 53,068; 53,051 for `K` = 2 to 7; smallest `K` within 100
of the minimum).

**A2. The exclusive layer replaces the composite layer as the model of record.** Section 7 listed,
before any data, the approximation that two repairs of different statements could both be credited
with fixing the same test. On D1 this is what happened: single-fault log loss 0.143 against 0.074
for version 3, and an inferred number of faults near 2 for single-fault programs. The replacement
is exact under two restrictions:

* at most one variant of a faulty statement is its repair (choice `a_s`: "none" with probability
  `1 - alpha`, or one of its `V_s` variants with probability `alpha / V_s` each);
* every failing test has at most one sole cause.

For a configuration `F` and choices `a`:

```
P(flips on test j | F, a, theta) =
      sum_{c in F, C[j,c]=1}  q(k_j, theta) * g_c * prod_{s != c} h_s
    + (1 - k_j q(k_j, theta)) * prod_s h_s

g_c = gamma^z (1-gamma)^(1-z)   if statement c has a chosen repair with flip z on test j, else 1
h_s = delta^z (1-delta)^(1-z)   likewise for the other statements with a chosen repair
```

and the variant factor of `F` is the sum over all choices `a` of
`prod_s P(a_s) * [beta-term / N_v of the chosen variant] * prod_j P(flips on test j | F, a, theta)`.
The events "c is the sole cause" are disjoint, which is why their probabilities add and why
`k q(k, theta) <= 1`. Cost: `prod_s (V_s + 1)` choices per configuration, at most three statements.

Consequence for section 4: the bound becomes `factor >= 1 - alpha` for the weight of a
configuration (not for the posterior odds of a marginal, which also depend on the other
configurations). The composite layer is kept as an ablation.

**A3. `delta` is not a free parameter.** The probability that a repair makes a test pass although
its statement is not the sole cause is set to the smallest flip rate among the non-repair kinds: in
that situation the repair acts like an inert change.

**A4. `tau = 1`.** With the exclusive layer the calibration problem that motivated the temperature
disappeared on D1; `tau = 0.5` gave no consistent gain. The temperature stays in the code and is
fixed at 1.

**A5. One kind of repair.** A second kind (partial repair) lowered BIC but changed no development
metric by more than 0.005; one kind is used.

**A6. Section 6, check (i) was restated.** The unrestricted posterior is computed for the model
without variants (where it must equal version 2 exact inference; tested) but not for the exclusive
layer, whose cost grows with the product of the numbers of variants of all faulty statements.
Truncation is instead checked by allowing a fourth fault (hypothesis H6).
