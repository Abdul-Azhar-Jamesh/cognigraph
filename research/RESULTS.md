# Results, version 4

Every number below was checked against the saved files named in the headings (independent recomputation
from `per_case.csv` and `probabilities.jsonl`: 0 mismatches in 77 spot checks, see
[FINAL_RESEARCH_AUDIT.md](FINAL_RESEARCH_AUDIT.md)). Protocol: [RESEARCH_PROTOCOL.md](RESEARCH_PROTOCOL.md).
Model: [MATHEMATICAL_DESIGN.md](MATHEMATICAL_DESIGN.md). Threats: [THREATS_TO_VALIDITY.md](THREATS_TO_VALIDITY.md).
All parameters of the proposed model (IV) come from the project's own single-fault programs (D1); no held-out
label was used. MAP = mean average precision, programs are the statistical unit, intervals are 95% cluster
bootstrap.

## 1. What was run

| Run | Content | Artifacts |
|---|---|---|
| `python -m pcg v4` (112 min) | 10 held-out sets: QuixBugs 31 programs (1, 2, 3 injected faults, human bugs QH, human + 1 injected QHM); HumanEvalFix 147 usable programs (E1, E2, E3, EH = 146 human bugs, EHM); development set D1 | `results/v4/` (raw: `per_case.csv`, `probabilities.jsonl`; derived: `summary.json`, `SUMMARY.md`, `tables/*.csv`, `figures/fig1-8.{png,pdf}`) |
| `python -m pcg v4-synthetic` (about 28 min) | simulated programs, 7 scenarios | `results/v4_synthetic/` (`SUMMARY.md`, `figures/fig_synthetic.{png,pdf}`) |
| tie-corrected sensitivity (post hoc) | expected average precision under random tie-breaking | `results/v4_sensitivity/` |
| `python -m pcg demo-v4` | three rule-selected cases | `results/demo_v4/` |

## 2. Hypotheses, as pre-registered (`results/v4/SUMMARY.md` section 16)

| | Outcome | Evidence |
|---|---|---|
| **H1** two faults, MAP, Holm over 10 comparisons | **Partly supported.** Supported against PCG v3 fused (Q2 +0.083 [+0.054, +0.111]; E2 +0.085 [+0.066, +0.104]) and, on E2 only, logistic fusion (+0.036 [+0.017, +0.055], Holm p 0.006). **Not supported** against PCG spectrum-only (+0.053, +0.025), MUSE (+0.031 [-0.018, +0.078]; +0.028 [-0.004, +0.058]) and FLITSR\* (+0.058, +0.029) | decision rule 2 of the protocol applies: the model repairs the project's own multi-fault failure but is not shown better than MUSE or FLITSR\* |
| **H2** single-fault cost at most 0.02 Top-1 | Supported on held-out Q1 (+0.003 [-0.010, +0.016]) and E1 (0.000 [-0.011, +0.011]). Not supported on the development set D1 (-0.017 [-0.033, +0.000]) | |
| **H3** human bugs, MRR above spectrum-only | Supported: EH +0.171 [+0.120, +0.223]; QH +0.145 [+0.029, +0.264] (31 bugs). Against PCG v3 fused: EH +0.042 [+0.013, +0.071], QH -0.014 [-0.069, +0.041]. Against logistic fusion: EH +0.037 [+0.015, +0.062], QH -0.054 [-0.155, +0.032] | |
| **H4** unknown number of faults | Supported with small margins over logistic fusion: Q-mix +0.014 [+0.001, +0.029], E-mix +0.010 [+0.002, +0.019] | |
| **H5** probabilities | **Not supported.** IV has a lower Brier score than PCG v3 fused and logistic fusion on D1-2, Q2, E2, Q3 and E3 (paired differences negative, intervals excluding 0), but its Brier skill against the base rate is negative on Q3 (-0.125), E3 (-0.167) and EHM (-0.036); positive on Q2 (+0.043), E2 (+0.027), EH (+0.158), QH (+0.086), QHM (+0.056). It is slightly worse than v3 fused on single-fault Q1 (+0.004), E1 (+0.004) and QH (+0.015) | |
| **H6** three against four allowed faults | Supported: marginals differ by less than 0.05 in 100 of 100 cases (maximum 0.041); same top statement in 92% | |
| **H7** inferred number of faults | Supported: AUC 0.854 [0.818, 0.889] (Q-mix), 0.844 [0.823, 0.866] (E-mix). Mean expected faults for 1, 2, 3 true faults: 1.24, 1.73, 1.78 (Q); 1.20, 1.67, 1.73 (E): it separates one from several faults, not two from three | |

## 3. Findings the hypotheses do not capture

* **The gain is mostly in the first fault.** First-fault Top-1 on Q2 / E2: IV 0.450 / 0.499, MUSE 0.426 / 0.470, v3 fused 0.291 / 0.358, Ochiai and FLITSR\* about 0.12 / 0.16. Having *all* faults in the top 3 is not better: Q2 IV 0.262 against MUSE 0.344 and spectrum-only 0.248; E2 IV 0.404 against 0.377 and 0.379; Q3 0.104 against 0.156 (spectrum-only); E3 0.138 against 0.173.
* **With three faults the pre-registered MAP does not favour IV**: Q3 0.703 against spectrum-only 0.733 and Ochiai 0.733; E3 0.689 against 0.736 and 0.734.
* **Ablations** (MAP on Q2 / E2): proposed 0.632 / 0.663; at most 2 faults 0.632 / 0.663 (identical: the third fault is never needed here); at most 1 fault 0.577 / 0.605; composite layer 0.601 / 0.639; no variants 0.578 / 0.638. Variant evidence adds +0.054 / +0.025 MAP; allowing a second fault adds +0.055 / +0.058; the exact (exclusive) layer adds +0.031 / +0.024 over the composite layer.
* **Human bugs**: IV Top-1 on EH 0.630 against v3 fused 0.575 and logistic fusion 0.582; on QH 0.452 against 0.452 and 0.548. Where a restoring variant exists (EH 46 bugs) IV's MRR is 0.989; where none exists (100 bugs) 0.656 against spectrum-only 0.597.
* **Fitting the variant layer on human bugs** (HumanEvalFix, 5 folds) changes IV's MAP on EH from 0.754 to 0.769 ([-0.004, +0.037]): no significant gain. Estimating from HumanEval single-fault mutants instead of D1 changes IV by at most 0.007.
* **Selective localisation** (descriptive, no intervals): AURC of IV is the lowest on Q-mix 0.159 (v3 fused 0.164), E-mix 0.137 (0.152), EH 0.129 (0.152); on QH logistic fusion is best (0.233 against 0.284).
* **Calibration** (reliability curves, `fig4`): ECE of IV 0.032 (Q-mix), 0.048 (E-mix), 0.069 (EH) against 0.080, 0.091, 0.087 for v3 fused and 0.138-0.150 for logistic fusion.

## 4. Tie handling: a flaw in the pre-registered metric and its sensitivity (`results/v4_sensitivity/`)

The pre-registered average precision uses mid-ranks and can exceed 1 when faults tie (1.0-5.1% of cases per method, maximum 1.5); coverage-only methods tie more often (4.5% of cases) than IV (1.4%), so they were favoured. The pre-registered numbers stand in Section 2. **Post hoc**, with the expected average precision under random tie-breaking (300 draws): IV beats PCG v3 fused, spectrum-only, FLITSR\* and logistic fusion on both Q2 and E2 (differences +0.046 to +0.093, Holm p at most 0.022), but not MUSE (Q2 +0.030 [-0.016, +0.075]; E2 +0.025 [-0.003, +0.053]). With three faults the corrected MAP is IV 0.654 / 0.659 against spectrum-only 0.624 / 0.637, MUSE 0.631 / 0.664. This correction favours the proposed method and was made after seeing the results; it is reported as a sensitivity analysis, not as the confirmatory result.

## 5. Simulated programs (`results/v4_synthetic/SUMMARY.md`, `fig_synthetic`)

250 simulated programs per cell, parameters of the generating process fitted on D1; IV's own parameters re-estimated from 400 simulated single-fault programs (they match the generating parameters' results to within 0.005 MAP).

* Model correct: MAP with two faults IV 0.937, MUSE 0.671, spectrum-only 0.630, v3 fused 0.610; with three faults 0.825 against 0.625 (MUSE). Brier skill +0.798 / +0.382.
* Correlated tests, coupled faults, per-fault exposure, many maskers, half the variants: IV stays at 0.73-0.95 and first among all methods.
* Few repairs (only 20% of faulty statements have a repair among their variants, the human-bug situation): IV falls to 0.638 (two faults) and 0.606 (three), level with spectrum-only (0.608, 0.601); Brier skill -0.067 at three faults. Four faults with at most three allowed: 0.755 against MUSE 0.665, skill +0.010, 2.45 faults inferred.
* Calibration worsens with the number of faults even when the model is correct (ECE 0.011, 0.009, 0.065 for 1, 2, 3 faults).
* These worlds are generated by the model's own mechanism, so high scores are expected; the gap to the real data (MAP 0.63-0.66) is the measure of how far real faults are from the model, mainly through how rarely a restoring variant exists.

## 6. Demonstration (`results/demo_v4/DEMO_V4.md`)

Three cases selected by fixed rules. Two faults: IV puts the faults at ranks 3 and 1 (AP 0.833) against 3 and 6 (spectrum-only) and 7.5 and 2 (v3 fused). One fault: IV assigns 0.94 to two faults and ranks the single fault 6th (AP 0.167); v3 fused ranks it 1st: the cost of generality. No variant fixes a failing test: IV finds one fault with 0.98, no better than v3 fused.

## 7. Cost

D1 variants 64 s + 45 s, QuixBugs 494 s, HumanEvalFix 452 s; scoring grows with the product of the numbers of variants of the faulty statements: mean 1.2 s per case, one 28-statement case with 48 variants took 85 s, and the slowest 5% of cases took 98% of the time. Exact inference is limited to functions of about 30 statements.

## 8. Provisional paper material (marked provisional: the evidence is modest)

**Title.** *Interventional Bayesian Fault Localisation When the Number of Faults Is Unknown: A Pre-registered Study on Small Python Programs*

**Abstract (provisional).** Bayesian fault localisers that use mutation or patch outcomes assume a single fault. We model every program variant as an intervention in a noisy-OR diagnosis network, so that a repair fixes a failing test only if its statement is the sole cause of the failure, and infer up to three faults exactly. All parameters are estimated from single-fault programs. On 3,622 held-out programs from QuixBugs and HumanEvalFix, the model removes the collapse of an earlier single-fault fusion with two faults (+0.08 MAP) and has better probabilities than that fusion and than logistic regression on two- and three-fault sets, with first-fault accuracy comparable to MUSE, but is not significantly better than MUSE, and it does not find every fault more often than coverage-only methods. Its probabilities lose to the base rate with three faults. On 146 hand-inserted bugs it improves the reciprocal rank over the single-fault fusion by 0.04.

**Contributions (as supported).** (1) A model in which the effect of a variant depends on the other faults in a test's scope, with exact bounded-cardinality inference and a stated closed form; (2) a pre-registered evaluation with two benchmarks, strong baselines and negative results; (3) a tie-handling flaw in a commonly used multi-fault metric, quantified.

**Resume line.** Built and pre-registered a probabilistic multi-fault localiser (noisy-OR with interventional mutation evidence, exact inference, 221 tests); evaluated on 3,600+ held-out Python programs against Ochiai, Barinel, MUSE, FLITSR and learned fusion; reported both the +0.08 gain over the previous model and the cases where it fails.

**Venue assessment.** No venue-specific claim was verified. The work is a small empirical modelling study on single functions: suitable for a student research track or a workshop. For a research conference it would need real project bugs (multi-fault Defects4J / BugsInPy versions exist), a comparison with SmartFL or Prosecutor, and a model that does not lose to coverage-only methods at three faults.
