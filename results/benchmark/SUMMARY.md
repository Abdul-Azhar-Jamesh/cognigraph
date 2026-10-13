# Benchmark results (generated file, do not edit)

Produced by `python -m pcg benchmark`. Every number below is read from the data files in this directory. Intervals are 95% percentile bootstrap intervals that resample whole programs.

## 1. Benchmark

| Quantity | Value |
|---|---|
| Reference programs | 34 |
| Statements per program (min / mean / max) | 4 / 7.1 / 16 |
| Tests per program (min / mean / max) | 7 / 10.1 / 16 |
| Single-fault mutants generated | 625 |
| Excluded (runner exceeded the wall-clock limit) | 1 |
| Valid mutants | 624 |
| Detected by the tests (used for localisation) | 594 |
| Not detected (equivalent or missed; never counted as localised) | 30 |

| Fault category | Valid mutants | Detected |
|---|---|---|
| arithmetic | 65 | 64 |
| boolean | 80 | 79 |
| boundary | 50 | 35 |
| comparison | 73 | 73 |
| off_by_one | 256 | 244 |
| omission | 84 | 83 |
| return_value | 16 | 16 |

## 2. Estimated parameters (pooled over all mutants, for reference)

Each evaluated program uses its own leave-one-program-out estimate (`params_lopo.json`); the pooled values below show the typical magnitudes.

| Parameter | Meaning | Estimate |
|---|---|---|
| pi | P(statement faulty) | 0.1236 |
| lambda | P(test fails with no fault in scope) | 0.000608 |
| theta (pooled) | P(executed fault makes the test fail) | 0.6350 |
| P(A=1 \| F=1) | pylint flags a faulty statement | 0.0016 |
| P(A=1 \| F=0) | pylint flags a fault-free statement | 0.0120 |

Exposure-rate prior fitted by EM (mixture of binomials):

| theta | 0.05 | 0.15 | 0.25 | 0.35 | 0.45 | 0.55 | 0.65 | 0.75 | 0.85 | 0.95 |
|---|---|---|---|---|---|---|---|---|---|---|
| weight | 0.037 | 0.160 | 0.002 | 0.002 | 0.029 | 0.251 | 0.002 | 0.002 | 0.002 | 0.515 |

## 3. Single-fault localisation (leave-one-program-out)

594 detected mutants. Ties are scored by their expected value under a random tie-break.

| Method | Top-1 | Top-3 | MRR | EXAM (lower is better) |
|---|---|---|---|---|
| Chance | 0.136 [0.122, 0.153] | 0.409 [0.367, 0.458] | 0.354 [0.329, 0.382] | 0.568 [0.561, 0.576] |
| Execution only (ef) | 0.307 [0.270, 0.346] | 0.739 [0.678, 0.800] | 0.547 [0.510, 0.585] | 0.345 [0.317, 0.378] |
| Heuristic (ef - ep) | 0.469 [0.426, 0.516] | 0.757 [0.699, 0.820] | 0.639 [0.603, 0.679] | 0.342 [0.304, 0.383] |
| Tarantula | 0.338 [0.286, 0.390] | 0.815 [0.770, 0.860] | 0.589 [0.555, 0.623] | 0.310 [0.294, 0.329] |
| Ochiai | 0.538 [0.486, 0.592] | 0.912 [0.877, 0.947] | 0.726 [0.690, 0.761] | 0.236 [0.219, 0.256] |
| PCG, fixed theta | 0.540 [0.487, 0.594] | 0.845 [0.796, 0.897] | 0.704 [0.667, 0.743] | 0.277 [0.253, 0.304] |
| PCG | 0.547 [0.494, 0.600] | 0.900 [0.861, 0.937] | 0.726 [0.688, 0.764] | 0.243 [0.225, 0.263] |
| PCG + slicing | 0.406 [0.364, 0.448] | 0.717 [0.661, 0.777] | 0.593 [0.557, 0.629] | 0.367 [0.339, 0.399] |
| PCG + static | 0.555 [0.502, 0.609] | 0.902 [0.864, 0.938] | 0.732 [0.694, 0.770] | 0.240 [0.222, 0.260] |

### Paired comparisons

Differences are per mutant; the test is a sign-flip permutation test on per-program mean differences.

| Comparison | Metric | Mean difference [95% CI] | Programs better / worse / equal | Sign-flip p |
|---|---|---|---|---|
| pcg - ochiai | top1 | +0.0089 [-0.0002, +0.0192] | 7 / 2 / 25 | 0.0640 |
| pcg - ochiai | reciprocal_rank | +0.0004 [-0.0065, +0.0068] | 8 / 10 / 16 | 0.9609 |
| pcg - ochiai | exam | +0.0066 [+0.0003, +0.0132] | 11 / 7 / 16 | 0.0356 |
| pcg - tarantula | top1 | +0.2092 [+0.1653, +0.2550] | 34 / 0 / 0 | < 0.0001 |
| pcg - tarantula | reciprocal_rank | +0.1371 [+0.1163, +0.1582] | 33 / 1 / 0 | < 0.0001 |
| pcg - tarantula | exam | -0.0667 [-0.0760, -0.0570] | 1 / 30 / 3 | < 0.0001 |
| pcg - pcg_fixed_theta | top1 | +0.0067 [+0.0008, +0.0147] | 4 / 0 / 30 | 0.1248 |
| pcg - pcg_fixed_theta | reciprocal_rank | +0.0218 [+0.0080, +0.0371] | 15 / 6 / 13 | 0.0080 |
| pcg - pcg_fixed_theta | exam | -0.0341 [-0.0605, -0.0107] | 6 / 14 / 14 | 0.0143 |
| pcg_slice - pcg | top1 | -0.1408 [-0.1772, -0.1041] | 1 / 32 / 1 | < 0.0001 |
| pcg_slice - pcg | reciprocal_rank | -0.1331 [-0.1638, -0.1036] | 1 / 33 / 0 | < 0.0001 |
| pcg_slice - pcg | exam | +0.1238 [+0.0917, +0.1608] | 33 / 1 / 0 | < 0.0001 |
| pcg_static - pcg | top1 | +0.0081 [+0.0036, +0.0134] | 10 / 0 / 24 | 0.0019 |
| pcg_static - pcg | reciprocal_rank | +0.0057 [+0.0028, +0.0092] | 11 / 0 / 23 | 0.0014 |
| pcg_static - pcg | exam | -0.0026 [-0.0043, -0.0012] | 0 / 11 / 23 | 0.0014 |

### By fault category (MRR)

| Category | n | Ochiai | PCG | PCG fixed theta | PCG + slicing | PCG + static |
|---|---|---|---|---|---|---|
| arithmetic | 64 | 0.758 | 0.751 | 0.747 | 0.731 | 0.751 |
| boolean | 79 | 0.862 | 0.856 | 0.847 | 0.797 | 0.856 |
| boundary | 35 | 0.437 | 0.459 | 0.363 | 0.260 | 0.459 |
| comparison | 73 | 0.828 | 0.850 | 0.834 | 0.660 | 0.850 |
| off_by_one | 244 | 0.671 | 0.670 | 0.638 | 0.564 | 0.670 |
| omission | 83 | 0.710 | 0.698 | 0.705 | 0.383 | 0.739 |
| return_value | 16 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 4. Probabilistic quality of the posteriors

All statements of all valid mutants, out-of-fold. The base-rate reference predicts the prior for every statement.

| Model | Statements | Faulty | Brier | Log loss | ECE (10 bins) |
|---|---|---|---|---|---|
| Base rate (prior only) | 5056 | 624 | 0.1084 | 0.3746 | 0.0015 |
| PCG, fixed theta | 5056 | 624 | 0.0912 | 0.4056 | 0.0821 |
| PCG | 5056 | 624 | 0.0760 | 0.2712 | 0.0454 |
| PCG + slicing | 5056 | 624 | 0.0902 | 0.3202 | 0.0303 |
| PCG + static | 5056 | 624 | 0.0749 | 0.2680 | 0.0449 |

Reliability table for PCG (predicted vs observed):

| Bin | Statements | Mean predicted | Observed frequency |
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

Fault-free reference programs (all tests pass): mean P(no fault) rises from 0.406 (prior) to 0.894 (posterior); minimum posterior 0.773.

## 5. Ablation: dependence slicing

Slicing shrinks each test's scope to its backward dependence slice. A deleted statement (SDL mutant) has no dependences, so slicing cannot see it. The table repeats the comparison with SDL mutants removed from both training and evaluation.

| Method (511 detected non-SDL mutants) | Top-1 | Top-3 | MRR |
|---|---|---|---|
| Ochiai | 0.546 [0.492, 0.602] | 0.904 [0.861, 0.942] | 0.728 [0.690, 0.765] |
| PCG | 0.557 [0.503, 0.611] | 0.897 [0.852, 0.936] | 0.731 [0.691, 0.770] |
| PCG + slicing | 0.566 [0.515, 0.620] | 0.901 [0.857, 0.940] | 0.737 [0.699, 0.775] |

In the full benchmark, the faulty line lies outside the slice scope of at least one failing test for 71 of 83 detected SDL mutants and for 0 of 511 other mutants.

| Comparison | Metric | Mean difference [95% CI] | Programs better / worse / equal | Sign-flip p |
|---|---|---|---|---|
| pcg_slice - pcg | top1 | +0.0098 [+0.0000, +0.0288] | 2 / 0 / 32 | 0.4991 |
| pcg_slice - pcg | reciprocal_rank | +0.0062 [+0.0000, +0.0171] | 2 / 0 / 32 | 0.4991 |
| pcg_slice - pcg | exam | -0.0036 [-0.0093, +0.0000] | 0 / 2 / 32 | 0.4991 |

## 6. Sensitivity to hand-set parameters (fixed-theta model)

Over 29 hand-set (theta, lambda, pi) combinations: Top-1 ranges from 0.483 to 0.557; Brier score from 0.0747 to 0.1528. Full grid: `sensitivity.csv`.

## 7. Two-fault programs

415 sampled, 1 excluded (runner limit), 4 not detected, 410 evaluated. Parameters come from the single-fault folds. Ties use mid-ranks here, so a method that ties every statement (chance) scores 0 on Top-1 by construction.

| Method | First fault Top-1 | First fault Top-3 | First fault MRR | Both in top 3 | Both in top 5 | Mean rank |
|---|---|---|---|---|---|---|
| Chance | 0.000 [0.000, 0.000] | 0.246 [0.113, 0.405] | 0.251 [0.231, 0.274] | 0.246 [0.113, 0.405] | 0.893 [0.766, 1.000] | 4.26 [3.86, 4.70] |
| Execution only (ef) | 0.168 [0.103, 0.234] | 0.890 [0.846, 0.933] | 0.540 [0.492, 0.590] | 0.278 [0.213, 0.347] | 0.683 [0.587, 0.779] | 3.46 [3.14, 3.84] |
| Heuristic (ef - ep) | 0.332 [0.252, 0.411] | 0.888 [0.840, 0.932] | 0.653 [0.605, 0.701] | 0.285 [0.226, 0.346] | 0.637 [0.546, 0.734] | 3.36 [3.05, 3.71] |
| Tarantula | 0.156 [0.109, 0.211] | 0.829 [0.748, 0.902] | 0.521 [0.480, 0.563] | 0.402 [0.328, 0.480] | 0.756 [0.683, 0.830] | 3.30 [2.99, 3.69] |
| Ochiai | 0.366 [0.280, 0.454] | 0.946 [0.905, 0.979] | 0.686 [0.636, 0.733] | 0.334 [0.269, 0.397] | 0.693 [0.604, 0.782] | 3.12 [2.85, 3.48] |
| PCG | 0.378 [0.300, 0.458] | 0.954 [0.919, 0.981] | 0.693 [0.647, 0.738] | 0.346 [0.284, 0.410] | 0.732 [0.654, 0.811] | 3.03 [2.77, 3.35] |

| Comparison | Metric | Mean difference [95% CI] | Programs better / worse / equal | Sign-flip p |
|---|---|---|---|---|
| pcg - ochiai | first_top1 | +0.0122 [-0.0218, +0.0463] | 9 / 6 / 19 | 0.4922 |
| pcg - ochiai | first_reciprocal_rank | +0.0077 [-0.0095, +0.0253] | 16 / 7 / 11 | 0.3626 |
| pcg - ochiai | all_top3 | +0.0122 [-0.0374, +0.0605] | 12 / 14 / 8 | 0.5350 |
| pcg - ochiai | mean_rank | -0.0970 [-0.2263, +0.0479] | 13 / 18 / 3 | 0.1882 |

## 8. SIMULATED LLM-confidence signal

**The confidence values in this section are synthetic.** They are drawn from Beta distributions that depend on the ground truth, to measure how the model would use a signal of known quality. They are not outputs of any language model and say nothing about real LLM calibration.

| Signal | Faulty-line distribution | PCG Top-1 | LLM-only Top-1 | PCG + LLM Top-1 | PCG MRR | PCG + LLM MRR | PCG Brier | PCG + LLM Brier |
|---|---|---|---|---|---|---|---|---|
| uninformative | Beta(8, 2) | 0.547 | 0.130 ± 0.011 | 0.548 ± 0.009 | 0.726 | 0.727 ± 0.005 | 0.0760 | 0.0760 |
| weak | Beta(6, 4) | 0.547 | 0.554 ± 0.018 | 0.757 ± 0.009 | 0.726 | 0.855 ± 0.006 | 0.0760 | 0.0512 |
| strong | Beta(3, 7) | 0.547 | 0.958 ± 0.010 | 0.975 ± 0.004 | 0.726 | 0.986 ± 0.002 | 0.0760 | 0.0110 |

Fault-free lines always draw from Beta(8, 2). Mean ± standard deviation over 10 seeded replicates.

## 9. Targeted repair

A patch is *plausible* when it compiles and passes every test; *exact* when its text equals the reference program. Plausible does not mean correct.

| Strategy | Plausible repair rate | Exact repair rate | Candidates validated | Fault line inside region |
|---|---|---|---|---|
| PCG, top-3 statements | 0.749 [0.676, 0.815] | 0.609 [0.539, 0.678] | 4.75 [4.27, 5.21] | 0.909 [0.859, 0.953] |
| Ochiai, top-3 statements | 0.753 [0.682, 0.817] | 0.613 [0.545, 0.680] | 4.86 [4.37, 5.32] | 0.923 [0.880, 0.960] |
| Unguided, all statements | 0.828 [0.787, 0.868] | 0.658 [0.611, 0.704] | 13.38 [11.14, 15.55] | 1.000 [1.000, 1.000] |

| Comparison | Metric | Mean difference [95% CI] | Programs better / worse / equal | Sign-flip p |
|---|---|---|---|---|
| pcg_top3 - ochiai_top3 | repaired | -0.0034 [-0.0145, +0.0084] | 2 / 4 / 28 | 0.7200 |
| pcg_top3 - ochiai_top3 | candidates_tried | -0.1111 [-0.1901, -0.0391] | 7 / 18 / 9 | 0.0102 |

