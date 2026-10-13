# Research results (generated file, do not edit)

Produced by `python -m pcg research`. Every number is read from the data files in this directory. Intervals are 95% bootstrap intervals over programs. No multiple-comparison correction is applied.

## 1. Datasets

| Dataset | Content | Cases evaluated |
|---|---|---|
| D1 | project benchmark, single-fault mutants, leave-one-program-out | 594 |
| D2 | QuixBugs, one human-written bug per program | 31 of 31 |
| D3 | QuixBugs correct programs, sampled mutants | 382 detected of 402 valid |

QuixBugs: 31 programs have JSON tests, 31 are used. 231 of 242 tests are kept; dropped: {'duplicate_input': 0, 'reference_disagrees_with_expected_output': 2, 'reference_exceeded_step_limit': 9, 'reference_raised': 0}. Runs without a result: 1. Fault kinds in D2: ['missing line', 'modified line'].

## 2. Learned mutation-evidence tables (pooled over D1)

Estimated among statements that every failing test executed (context "all").

| Level | 0 no variant | 1 no effect | 2 partial | 3 fixes failing, breaks passing | 4 all tests pass |
|---|---|---|---|---|---|
| P(level \| faulty) | 0.1402 | 0.0134 | 0.0083 | 0.0150 | 0.8230 |
| P(level \| fault-free) | 0.1794 | 0.5874 | 0.1728 | 0.0552 | 0.0051 |
| likelihood ratio | 0.782 | 0.023 | 0.048 | 0.272 | 162.385 |
| ratio without context (ablation) | 0.640 | 0.022 | 0.059 | 0.580 | 346.581 |

Expected faults per analysed program, mu = 1.000.

## 3. D1: ranking

| Method | Top-1 | Top-3 | MRR |
|---|---|---|---|
| Ochiai | 0.538 [0.486, 0.592] | 0.912 [0.877, 0.947] | 0.726 [0.690, 0.761] |
| Tarantula | 0.338 [0.286, 0.390] | 0.815 [0.770, 0.860] | 0.589 [0.555, 0.623] |
| Barinel | 0.538 [0.488, 0.591] | 0.910 [0.879, 0.942] | 0.724 [0.691, 0.759] |
| Metallaxis | 0.748 [0.679, 0.815] | 0.877 [0.836, 0.916] | 0.827 [0.775, 0.875] |
| MUSE | 0.746 [0.684, 0.805] | 0.854 [0.813, 0.894] | 0.816 [0.775, 0.859] |
| Hybrid average | 0.780 [0.717, 0.840] | 0.913 [0.874, 0.947] | 0.856 [0.811, 0.898] |
| Logistic, spectrum | 0.550 [0.500, 0.599] | 0.921 [0.889, 0.953] | 0.735 [0.701, 0.769] |
| Logistic fusion | 0.959 [0.940, 0.976] | 0.999 [0.998, 1.000] | 0.978 [0.968, 0.987] |
| PCG v2 | 0.547 [0.494, 0.600] | 0.900 [0.861, 0.937] | 0.726 [0.688, 0.764] |
| PCG, size-aware prior | 0.548 [0.496, 0.600] | 0.901 [0.863, 0.937] | 0.727 [0.690, 0.764] |
| PCG fused (proposed) | 0.957 [0.934, 0.975] | 0.990 [0.983, 0.996] | 0.974 [0.961, 0.985] |
| PCG fused, no context | 0.958 [0.937, 0.976] | 1.000 [1.000, 1.000] | 0.977 [0.966, 0.987] |
| PCG fused, constant prior | 0.957 [0.934, 0.975] | 0.990 [0.983, 0.996] | 0.974 [0.961, 0.985] |

| Comparison | Metric | Mean difference [95% CI] | Sign-flip p |
|---|---|---|---|
| pcg_fused - pcg_size | top1 | +0.4088 [+0.3580, +0.4589] | < 0.0001 |
| pcg_fused - pcg_size | reciprocal_rank | +0.2471 [+0.2122, +0.2822] | < 0.0001 |
| pcg_fused - lr_fusion | top1 | -0.0028 [-0.0183, +0.0116] | 0.6580 |
| pcg_fused - lr_fusion | reciprocal_rank | -0.0042 [-0.0132, +0.0039] | 0.3486 |
| pcg_fused - hybrid_avg | top1 | +0.1770 [+0.1154, +0.2413] | < 0.0001 |
| pcg_fused - hybrid_avg | reciprocal_rank | +0.1185 [+0.0756, +0.1644] | < 0.0001 |
| pcg_fused - metallaxis | top1 | +0.2085 [+0.1403, +0.2790] | < 0.0001 |
| pcg_fused - metallaxis | reciprocal_rank | +0.1475 [+0.0991, +0.1998] | < 0.0001 |
| pcg_fused - ochiai | top1 | +0.4186 [+0.3659, +0.4696] | < 0.0001 |
| pcg_fused - ochiai | reciprocal_rank | +0.2484 [+0.2131, +0.2837] | < 0.0001 |
| pcg_fused - pcg_fused_nocontext | top1 | -0.0017 [-0.0043, +0.0000] | 0.4971 |
| pcg_fused - pcg_fused_nocontext | reciprocal_rank | -0.0032 [-0.0058, -0.0012] | 0.0078 |
| pcg_size - pcg | top1 | +0.0009 [+0.0000, +0.0027] | 1.0000 |
| pcg_size - pcg | reciprocal_rank | +0.0009 [+0.0000, +0.0025] | 0.4976 |

MRR by fault category:

| Category | n | Ochiai | Metallaxis | Hybrid average | Logistic fusion | PCG size-aware | PCG fused |
|---|---|---|---|---|---|---|---|
| arithmetic | 64 | 0.758 | 0.834 | 0.867 | 0.881 | 0.751 | 0.878 |
| boolean | 79 | 0.862 | 0.936 | 0.955 | 1.000 | 0.858 | 1.000 |
| boundary | 35 | 0.437 | 0.942 | 0.971 | 1.000 | 0.459 | 1.000 |
| comparison | 73 | 0.828 | 0.963 | 0.963 | 1.000 | 0.850 | 1.000 |
| off_by_one | 244 | 0.671 | 0.932 | 0.947 | 0.998 | 0.672 | 0.993 |
| omission | 83 | 0.710 | 0.208 | 0.312 | 0.943 | 0.698 | 0.930 |
| return_value | 16 | 1.000 | 0.984 | 1.000 | 1.000 | 1.000 | 1.000 |

Level of the faulty statement in D1: level 0: 83, level 1: 7, level 2: 4, level 3: 8, level 4: 492. Level 4 means a variant restores all tests, which on injected faults is usually the exact inverse of the injection.

## 4. D1 stress test: the reference-restoring variant removed

The variant whose text equals the reference program is removed from every mutation analysis, in training and in evaluation. This uses ground truth to remove information and is a stress test, not a result.

| Method | Top-1 | Top-3 | MRR |
|---|---|---|---|
| Ochiai | 0.538 [0.486, 0.592] | 0.912 [0.877, 0.947] | 0.726 [0.690, 0.761] |
| Metallaxis | 0.549 [0.475, 0.627] | 0.788 [0.727, 0.848] | 0.692 [0.633, 0.752] |
| MUSE | 0.482 [0.398, 0.571] | 0.706 [0.637, 0.774] | 0.628 [0.562, 0.697] |
| Hybrid average | 0.602 [0.533, 0.674] | 0.861 [0.803, 0.915] | 0.744 [0.691, 0.796] |
| Logistic fusion | 0.771 [0.717, 0.823] | 0.947 [0.918, 0.973] | 0.860 [0.825, 0.893] |
| PCG, size-aware prior | 0.548 [0.496, 0.600] | 0.901 [0.863, 0.937] | 0.727 [0.690, 0.764] |
| PCG fused (proposed) | 0.729 [0.678, 0.783] | 0.920 [0.888, 0.950] | 0.832 [0.798, 0.868] |

| Comparison | Metric | Mean difference [95% CI] | Sign-flip p |
|---|---|---|---|
| pcg_fused - pcg_size | top1 | +0.1815 [+0.1381, +0.2243] | < 0.0001 |
| pcg_fused - pcg_size | reciprocal_rank | +0.1053 [+0.0752, +0.1334] | < 0.0001 |
| pcg_fused - lr_fusion | top1 | -0.0417 [-0.0741, -0.0105] | 0.0147 |
| pcg_fused - lr_fusion | reciprocal_rank | -0.0273 [-0.0473, -0.0085] | 0.0046 |
| pcg_fused - hybrid_avg | top1 | +0.1269 [+0.0799, +0.1734] | < 0.0001 |
| pcg_fused - hybrid_avg | reciprocal_rank | +0.0886 [+0.0548, +0.1218] | < 0.0001 |
| pcg_fused - metallaxis | top1 | +0.1798 [+0.1285, +0.2304] | < 0.0001 |
| pcg_fused - metallaxis | reciprocal_rank | +0.1403 [+0.1014, +0.1792] | < 0.0001 |

## 5. D1: quality of probabilities (detected cases, out-of-fold)

4800 statements, 594 faulty. Skill is 1 - Brier / Brier(base rate 1/n); positive means better than the base rate.

| Method | Brier [95% CI] | Skill | Log loss | ECE |
|---|---|---|---|---|
| Base rate 1/n | 0.1069 [0.0939, 0.1212] | +0.000 | 0.3672 | 0.0000 |
| Base rate pooled (in-sample) | 0.1084 [0.0959, 0.1228] | -0.015 | 0.3743 | 0.0000 |
| Logistic, spectrum | 0.0837 [0.0750, 0.0947] | +0.217 | 0.2582 | 0.0144 |
| Logistic fusion | 0.0141 [0.0103, 0.0192] | +0.868 | 0.0547 | 0.0092 |
| PCG v2 | 0.0739 [0.0658, 0.0839] | +0.309 | 0.2557 | 0.0530 |
| PCG, size-aware prior | 0.0742 [0.0647, 0.0858] | +0.306 | 0.2550 | 0.0517 |
| PCG fused (proposed) | 0.0145 [0.0101, 0.0202] | +0.864 | 0.0744 | 0.0450 |
| PCG fused, no context | 0.0090 [0.0055, 0.0136] | +0.916 | 0.0401 | 0.0161 |
| PCG fused, constant prior | 0.0143 [0.0108, 0.0189] | +0.866 | 0.0752 | 0.0455 |
| PCG fused, recalibrated | 0.0095 [0.0058, 0.0146] | +0.911 | 0.0399 | 0.0054 |

| Comparison | Metric | Mean difference [95% CI] | Sign-flip p |
|---|---|---|---|
| pcg_fused - lr_fusion | brier (lower is better) | +0.0004 [-0.0025, +0.0036] | 0.7098 |
| pcg_fused - pcg_size | brier (lower is better) | -0.0597 [-0.0672, -0.0539] | < 0.0001 |
| pcg_fused - pcg_fused_nocontext | brier (lower is better) | +0.0055 [+0.0041, +0.0073] | < 0.0001 |
| pcg_fused_recal - pcg_fused | brier (lower is better) | -0.0050 [-0.0066, -0.0037] | < 0.0001 |
| pcg_size - pcg | brier (lower is better) | +0.0003 [-0.0014, +0.0024] | 0.0005 |

Recalibration maps (nested): slope a between 1.359 and 1.491; map fitted on all out-of-fold D1 posteriors for transfer: a = 1.391, b = -1.601.

## 6. D1: selective localisation

Error rate = 1 - Top-1 of the method whose answers are scored. AURC = mean error when the most confident cases are answered first (lower is better). Normalised gain: 1 = oracle confidence, 0 = confidence carries no information.

| Confidence | Answers scored | Error rate | AURC | Normalised gain | Risk at 50% coverage |
|---|---|---|---|---|---|
| PCG v2 | PCG v2 | 0.453 | 0.250 | +0.665 | 0.288 |
| PCG, size-aware prior | PCG, size-aware prior | 0.452 | 0.251 | +0.662 | 0.288 |
| PCG fused (proposed) | PCG fused (proposed) | 0.043 | 0.003 | +0.955 | 0.000 |
| Logistic, spectrum | Logistic, spectrum | 0.450 | 0.479 | -0.097 | 0.380 |
| Logistic fusion | Logistic fusion | 0.041 | 0.008 | +0.811 | 0.003 |
| Ochiai | Ochiai | 0.462 | 0.362 | +0.324 | 0.341 |
| Ochiai gap | Ochiai | 0.462 | 0.312 | +0.487 | 0.320 |
| Metallaxis | Metallaxis | 0.252 | 0.196 | +0.262 | 0.194 |
| Hybrid average | Hybrid average | 0.220 | 0.220 | +0.001 | 0.223 |

| Comparison (first minus second) | AURC difference [95% CI] | Normalised-gain difference [95% CI] |
|---|---|---|
| pcg_size - ochiai_gap | -0.061 [-0.106, -0.030] | +0.174 [+0.082, +0.308] |
| pcg_size - ochiai | -0.112 [-0.163, -0.050] | +0.338 [+0.138, +0.524] |
| pcg_fused - lr_fusion | -0.005 [-0.016, +0.002] | +0.144 [-0.025, +0.375] |

## 7. D1: constant versus size-aware prior (all valid mutants, spectrum evidence only)

| Program size | Statements | Observed fault rate | Mean predicted, constant | Mean predicted, size-aware | Brier constant | Brier size-aware | ECE constant | ECE size-aware |
|---|---|---|---|---|---|---|---|---|
| all | 5056 | 0.1234 | 0.1688 | 0.1675 | 0.0760 | 0.0762 | 0.0454 | 0.0441 |
| 4 to 5 statements | 537 | 0.2067 | 0.2478 | 0.2799 | 0.0828 | 0.0930 | 0.0604 | 0.0770 |
| 6 to 8 statements | 2028 | 0.1371 | 0.1820 | 0.1877 | 0.0843 | 0.0857 | 0.0449 | 0.0506 |
| 9 to 16 statements | 2491 | 0.0943 | 0.1410 | 0.1268 | 0.0677 | 0.0649 | 0.0467 | 0.0332 |

Paired Brier difference, size-aware minus constant: +0.00027 [-0.00135, +0.00229], p = 0.0005.

## 8. D2: human-written bugs, parameters transferred from D1

| Method | Top-1 | Top-3 | MRR |
|---|---|---|---|
| Ochiai | 0.376 [0.260, 0.509] | 0.666 [0.554, 0.777] | 0.565 [0.474, 0.665] |
| Tarantula | 0.315 [0.217, 0.430] | 0.635 [0.514, 0.752] | 0.526 [0.442, 0.616] |
| Barinel | 0.381 [0.266, 0.512] | 0.671 [0.559, 0.782] | 0.570 [0.479, 0.669] |
| Metallaxis | 0.305 [0.182, 0.441] | 0.611 [0.468, 0.753] | 0.501 [0.399, 0.609] |
| MUSE | 0.395 [0.248, 0.549] | 0.556 [0.404, 0.702] | 0.542 [0.424, 0.665] |
| Hybrid average | 0.309 [0.185, 0.444] | 0.626 [0.478, 0.769] | 0.513 [0.414, 0.620] |
| Logistic, spectrum | 0.381 [0.266, 0.512] | 0.671 [0.559, 0.782] | 0.570 [0.479, 0.669] |
| Logistic fusion | 0.575 [0.403, 0.742] | 0.742 [0.602, 0.876] | 0.699 [0.572, 0.819] |
| PCG v2 | 0.381 [0.266, 0.512] | 0.660 [0.540, 0.777] | 0.562 [0.465, 0.663] |
| PCG, size-aware prior | 0.381 [0.266, 0.512] | 0.660 [0.540, 0.777] | 0.562 [0.465, 0.663] |
| PCG fused (proposed) | 0.511 [0.339, 0.672] | 0.742 [0.591, 0.876] | 0.666 [0.543, 0.782] |
| PCG fused, no context | 0.575 [0.414, 0.737] | 0.785 [0.651, 0.903] | 0.706 [0.584, 0.822] |
| PCG fused, constant prior | 0.511 [0.339, 0.672] | 0.742 [0.591, 0.876] | 0.662 [0.537, 0.779] |

| Comparison | Metric | Mean difference [95% CI] | Sign-flip p |
|---|---|---|---|
| pcg_fused - pcg_size | top1 | +0.1297 [-0.0501, +0.3006] | 0.1601 |
| pcg_fused - pcg_size | reciprocal_rank | +0.1041 [-0.0130, +0.2196] | 0.0926 |
| pcg_fused - lr_fusion | top1 | -0.0645 [-0.1774, +0.0161] | 0.3793 |
| pcg_fused - lr_fusion | reciprocal_rank | -0.0331 [-0.1125, +0.0315] | 0.4136 |
| pcg_fused - hybrid_avg | top1 | +0.2016 [-0.0188, +0.4033] | 0.0777 |
| pcg_fused - hybrid_avg | reciprocal_rank | +0.1523 [+0.0041, +0.2963] | 0.0574 |
| pcg_fused - metallaxis | top1 | +0.2059 [-0.0145, +0.4081] | 0.0705 |
| pcg_fused - metallaxis | reciprocal_rank | +0.1647 [+0.0128, +0.3123] | 0.0450 |
| pcg_fused - ochiai | top1 | +0.1350 [-0.0475, +0.3097] | 0.1511 |
| pcg_fused - ochiai | reciprocal_rank | +0.1008 [-0.0187, +0.2195] | 0.1102 |
| pcg_fused - pcg_fused_nocontext | top1 | -0.0645 [-0.1613, +0.0000] | 0.4962 |
| pcg_fused - pcg_fused_nocontext | reciprocal_rank | -0.0404 [-0.0906, -0.0037] | 0.0629 |
| pcg_size - pcg | top1 | +0.0000 [+0.0000, +0.0000] | 1.0000 |
| pcg_size - pcg | reciprocal_rank | +0.0000 [+0.0000, +0.0000] | 1.0000 |

Level of the faulty statement in D2: level 0: 7, level 1: 12, level 2: 5, level 3: 2, level 4: 5.

Quality of probabilities:

235 statements, 31 faulty. Skill is 1 - Brier / Brier(base rate 1/n); positive means better than the base rate.

| Method | Brier [95% CI] | Skill | Log loss | ECE |
|---|---|---|---|---|
| Base rate 1/n | 0.1121 [0.0995, 0.1257] | +0.000 | 0.3798 | 0.0000 |
| Base rate pooled (in-sample) | 0.1145 [0.1022, 0.1282] | -0.022 | 0.3900 | 0.0000 |
| Logistic, spectrum | 0.1123 [0.0956, 0.1302] | -0.002 | 0.3550 | 0.0609 |
| Logistic fusion | 0.0918 [0.0707, 0.1149] | +0.181 | 0.4098 | 0.0829 |
| PCG v2 | 0.0973 [0.0780, 0.1173] | +0.132 | 0.3353 | 0.0668 |
| PCG, size-aware prior | 0.0974 [0.0778, 0.1184] | +0.131 | 0.3346 | 0.0585 |
| PCG fused (proposed) | 0.0872 [0.0614, 0.1168] | +0.222 | 0.3161 | 0.0616 |
| PCG fused, no context | 0.0796 [0.0543, 0.1088] | +0.290 | 0.2872 | 0.0572 |
| PCG fused, constant prior | 0.0868 [0.0612, 0.1162] | +0.225 | 0.3167 | 0.0746 |
| PCG fused, recalibrated | 0.0878 [0.0638, 0.1143] | +0.217 | 0.4127 | 0.0756 |

| Comparison | Metric | Mean difference [95% CI] | Sign-flip p |
|---|---|---|---|
| pcg_fused - lr_fusion | brier (lower is better) | -0.0046 [-0.0224, +0.0122] | 0.4488 |
| pcg_fused - pcg_size | brier (lower is better) | -0.0102 [-0.0335, +0.0136] | 0.7057 |
| pcg_fused - pcg_fused_nocontext | brier (lower is better) | +0.0076 [+0.0042, +0.0118] | 0.0001 |

Selective localisation:

| Confidence | Answers scored | Error rate | AURC | Normalised gain | Risk at 50% coverage |
|---|---|---|---|---|---|
| PCG v2 | PCG v2 | 0.619 | 0.376 | +0.793 | 0.458 |
| PCG, size-aware prior | PCG, size-aware prior | 0.619 | 0.374 | +0.801 | 0.437 |
| PCG fused (proposed) | PCG fused (proposed) | 0.489 | 0.263 | +0.682 | 0.281 |
| Logistic, spectrum | Logistic, spectrum | 0.619 | 0.569 | +0.164 | 0.564 |
| Logistic fusion | Logistic fusion | 0.425 | 0.213 | +0.681 | 0.229 |
| Ochiai | Ochiai | 0.624 | 0.574 | +0.162 | 0.564 |
| Ochiai gap | Ochiai | 0.624 | 0.424 | +0.647 | 0.480 |
| Metallaxis | Metallaxis | 0.695 | 0.651 | +0.138 | 0.637 |
| Hybrid average | Hybrid average | 0.691 | 0.688 | +0.009 | 0.691 |

| Comparison (first minus second) | AURC difference [95% CI] | Normalised-gain difference [95% CI] |
|---|---|---|
| pcg_size - ochiai_gap | -0.050 [-0.161, +0.015] | +0.153 [-0.062, +0.557] |
| pcg_size - ochiai | -0.200 [-0.267, -0.115] | +0.639 [+0.407, +0.856] |
| pcg_fused - lr_fusion | +0.050 [-0.051, +0.168] | +0.000 [-0.199, +0.230] |

## 9. D2 with parameters from mutants of the other QuixBugs programs (in-suite)

| Method | Top-1 | Top-3 | MRR |
|---|---|---|---|
| Ochiai | 0.376 [0.260, 0.509] | 0.666 [0.554, 0.777] | 0.565 [0.474, 0.665] |
| Tarantula | 0.315 [0.217, 0.430] | 0.635 [0.514, 0.752] | 0.526 [0.442, 0.616] |
| Barinel | 0.381 [0.266, 0.512] | 0.671 [0.559, 0.782] | 0.570 [0.479, 0.669] |
| Metallaxis | 0.305 [0.182, 0.441] | 0.611 [0.468, 0.753] | 0.501 [0.399, 0.609] |
| MUSE | 0.395 [0.248, 0.549] | 0.556 [0.404, 0.702] | 0.542 [0.424, 0.665] |
| Hybrid average | 0.309 [0.185, 0.444] | 0.626 [0.478, 0.769] | 0.513 [0.414, 0.620] |
| Logistic, spectrum | 0.381 [0.266, 0.512] | 0.671 [0.559, 0.782] | 0.570 [0.479, 0.669] |
| Logistic fusion | 0.478 [0.306, 0.656] | 0.710 [0.559, 0.850] | 0.629 [0.500, 0.754] |
| PCG v2 | 0.381 [0.266, 0.512] | 0.660 [0.540, 0.777] | 0.562 [0.465, 0.663] |
| PCG, size-aware prior | 0.381 [0.266, 0.512] | 0.660 [0.540, 0.777] | 0.562 [0.465, 0.663] |
| PCG fused (proposed) | 0.551 [0.384, 0.710] | 0.750 [0.602, 0.882] | 0.685 [0.558, 0.803] |
| PCG fused, no context | 0.626 [0.473, 0.774] | 0.772 [0.632, 0.898] | 0.730 [0.608, 0.843] |
| PCG fused, constant prior | 0.583 [0.425, 0.737] | 0.750 [0.602, 0.882] | 0.701 [0.575, 0.817] |

| Comparison | Metric | Mean difference [95% CI] | Sign-flip p |
|---|---|---|---|
| pcg_fused - pcg_size | reciprocal_rank | +0.1231 [+0.0142, +0.2321] | 0.0375 |
| pcg_fused - lr_fusion | reciprocal_rank | +0.0561 [-0.0047, +0.1260] | 0.1171 |
| pcg_fused - hybrid_avg | reciprocal_rank | +0.1713 [+0.0293, +0.3121] | 0.0273 |
| pcg_fused - metallaxis | reciprocal_rank | +0.1837 [+0.0372, +0.3284] | 0.0210 |
| pcg_fused - ochiai | reciprocal_rank | +0.1198 [+0.0056, +0.2334] | 0.0495 |
| pcg_fused - pcg_fused_nocontext | reciprocal_rank | -0.0453 [-0.0964, -0.0063] | 0.0337 |
| pcg_size - pcg | reciprocal_rank | +0.0000 [+0.0000, +0.0000] | 1.0000 |

235 statements, 31 faulty. Skill is 1 - Brier / Brier(base rate 1/n); positive means better than the base rate.

| Method | Brier [95% CI] | Skill | Log loss | ECE |
|---|---|---|---|---|
| Base rate 1/n | 0.1121 [0.0995, 0.1257] | +0.000 | 0.3798 | 0.0000 |
| Base rate pooled (in-sample) | 0.1145 [0.1022, 0.1282] | -0.022 | 0.3900 | 0.0000 |
| Logistic, spectrum | 0.1061 [0.0944, 0.1196] | +0.054 | 0.3437 | 0.0309 |
| Logistic fusion | 0.1007 [0.0800, 0.1232] | +0.101 | 0.4742 | 0.0953 |
| PCG v2 | 0.0976 [0.0768, 0.1191] | +0.129 | 0.3391 | 0.0695 |
| PCG, size-aware prior | 0.0972 [0.0761, 0.1198] | +0.133 | 0.3364 | 0.0553 |
| PCG fused (proposed) | 0.0816 [0.0575, 0.1086] | +0.272 | 0.2975 | 0.0581 |
| PCG fused, no context | 0.0776 [0.0536, 0.1046] | +0.307 | 0.2781 | 0.0705 |
| PCG fused, constant prior | 0.0812 [0.0568, 0.1082] | +0.276 | 0.2983 | 0.0653 |

## 10. D3: mutants of QuixBugs programs, parameters transferred from D1

| Method | Top-1 | Top-3 | MRR |
|---|---|---|---|
| Ochiai | 0.344 [0.291, 0.400] | 0.705 [0.641, 0.766] | 0.558 [0.513, 0.605] |
| Tarantula | 0.294 [0.249, 0.342] | 0.649 [0.588, 0.710] | 0.515 [0.473, 0.557] |
| Barinel | 0.345 [0.292, 0.401] | 0.699 [0.636, 0.760] | 0.557 [0.512, 0.604] |
| Metallaxis | 0.506 [0.439, 0.572] | 0.757 [0.695, 0.818] | 0.659 [0.605, 0.713] |
| MUSE | 0.695 [0.628, 0.755] | 0.782 [0.728, 0.834] | 0.769 [0.719, 0.817] |
| Hybrid average | 0.534 [0.465, 0.604] | 0.809 [0.744, 0.873] | 0.690 [0.634, 0.745] |
| Logistic, spectrum | 0.351 [0.295, 0.411] | 0.708 [0.644, 0.770] | 0.563 [0.516, 0.612] |
| Logistic fusion | 0.917 [0.878, 0.950] | 0.991 [0.976, 1.000] | 0.953 [0.929, 0.973] |
| PCG v2 | 0.346 [0.291, 0.406] | 0.700 [0.636, 0.763] | 0.558 [0.512, 0.606] |
| PCG, size-aware prior | 0.347 [0.292, 0.406] | 0.701 [0.638, 0.764] | 0.558 [0.512, 0.607] |
| PCG fused (proposed) | 0.911 [0.873, 0.942] | 0.983 [0.968, 0.995] | 0.947 [0.921, 0.966] |
| PCG fused, no context | 0.913 [0.874, 0.945] | 0.983 [0.968, 0.995] | 0.949 [0.923, 0.969] |
| PCG fused, constant prior | 0.911 [0.873, 0.942] | 0.983 [0.968, 0.995] | 0.947 [0.921, 0.966] |

| Comparison | Metric | Mean difference [95% CI] | Sign-flip p |
|---|---|---|---|
| pcg_fused - pcg_size | top1 | +0.5639 [+0.5037, +0.6211] | < 0.0001 |
| pcg_fused - pcg_size | reciprocal_rank | +0.3884 [+0.3405, +0.4347] | < 0.0001 |
| pcg_fused - lr_fusion | top1 | -0.0068 [-0.0193, +0.0051] | 0.3015 |
| pcg_fused - lr_fusion | reciprocal_rank | -0.0066 [-0.0134, +0.0001] | 0.0585 |
| pcg_fused - hybrid_avg | top1 | +0.3762 [+0.3050, +0.4491] | < 0.0001 |
| pcg_fused - hybrid_avg | reciprocal_rank | +0.2570 [+0.2015, +0.3133] | < 0.0001 |
| pcg_fused - metallaxis | top1 | +0.4048 [+0.3345, +0.4756] | < 0.0001 |
| pcg_fused - metallaxis | reciprocal_rank | +0.2878 [+0.2333, +0.3432] | < 0.0001 |
| pcg_fused - ochiai | top1 | +0.5665 [+0.5089, +0.6221] | < 0.0001 |
| pcg_fused - ochiai | reciprocal_rank | +0.3883 [+0.3422, +0.4339] | < 0.0001 |
| pcg_fused - pcg_fused_nocontext | top1 | -0.0026 [-0.0081, +0.0000] | 1.0000 |
| pcg_fused - pcg_fused_nocontext | reciprocal_rank | -0.0020 [-0.0050, -0.0001] | 0.1239 |
| pcg_size - pcg | top1 | +0.0003 [+0.0000, +0.0010] | 1.0000 |
| pcg_size - pcg | reciprocal_rank | +0.0006 [+0.0000, +0.0014] | 0.2472 |

3040 statements, 382 faulty. Skill is 1 - Brier / Brier(base rate 1/n); positive means better than the base rate.

| Method | Brier [95% CI] | Skill | Log loss | ECE |
|---|---|---|---|---|
| Base rate 1/n | 0.1078 [0.0954, 0.1218] | +0.000 | 0.3688 | 0.0000 |
| Base rate pooled (in-sample) | 0.1099 [0.0977, 0.1238] | -0.019 | 0.3780 | 0.0000 |
| Logistic, spectrum | 0.1240 [0.1098, 0.1401] | -0.150 | 0.3744 | 0.0991 |
| Logistic fusion | 0.0288 [0.0217, 0.0373] | +0.733 | 0.1087 | 0.0254 |
| PCG v2 | 0.0933 [0.0827, 0.1055] | +0.134 | 0.3242 | 0.0685 |
| PCG, size-aware prior | 0.0942 [0.0820, 0.1082] | +0.126 | 0.3239 | 0.0689 |
| PCG fused (proposed) | 0.0200 [0.0146, 0.0265] | +0.815 | 0.0884 | 0.0410 |
| PCG fused, no context | 0.0159 [0.0107, 0.0222] | +0.852 | 0.0645 | 0.0197 |
| PCG fused, constant prior | 0.0193 [0.0142, 0.0252] | +0.821 | 0.0882 | 0.0411 |
| PCG fused, recalibrated | 0.0169 [0.0116, 0.0233] | +0.843 | 0.0643 | 0.0106 |

| Comparison | Metric | Mean difference [95% CI] | Sign-flip p |
|---|---|---|---|
| pcg_fused - lr_fusion | brier (lower is better) | -0.0088 [-0.0135, -0.0048] | < 0.0001 |
| pcg_fused - pcg_size | brier (lower is better) | -0.0742 [-0.0863, -0.0635] | < 0.0001 |
| pcg_fused - pcg_fused_nocontext | brier (lower is better) | +0.0041 [+0.0028, +0.0057] | < 0.0001 |

## 11. Post hoc: two-fault programs

Added after the context hypothesis (P5) was refuted on single faults. Not pre-registered.

410 detected two-fault programs; coverage context of their faulty statements: {'all': 481, 'none': 65, 'part': 274}.

| Method | First fault Top-1 | First fault MRR | Both in top 3 | Both in top 5 | Mean rank |
|---|---|---|---|---|---|
| Ochiai | 0.366 [0.280, 0.454] | 0.686 [0.636, 0.733] | 0.334 [0.269, 0.397] | 0.693 [0.604, 0.782] | 3.12 [2.85, 3.48] |
| Metallaxis | 0.524 [0.442, 0.602] | 0.725 [0.667, 0.777] | 0.332 [0.252, 0.413] | 0.722 [0.625, 0.819] | 3.22 [2.85, 3.65] |
| Hybrid average | 0.588 [0.496, 0.677] | 0.776 [0.720, 0.827] | 0.388 [0.304, 0.475] | 0.710 [0.624, 0.797] | 3.01 [2.70, 3.39] |
| Logistic fusion | 0.505 [0.411, 0.594] | 0.723 [0.669, 0.774] | 0.302 [0.229, 0.378] | 0.732 [0.640, 0.820] | 3.17 [2.93, 3.44] |
| PCG, size-aware prior | 0.390 [0.308, 0.474] | 0.700 [0.653, 0.744] | 0.359 [0.299, 0.421] | 0.739 [0.660, 0.818] | 2.99 [2.75, 3.31] |
| PCG fused (proposed) | 0.351 [0.277, 0.422] | 0.607 [0.559, 0.653] | 0.198 [0.142, 0.257] | 0.688 [0.595, 0.782] | 3.63 [3.38, 3.88] |
| PCG fused, no context | 0.449 [0.364, 0.528] | 0.700 [0.648, 0.749] | 0.302 [0.227, 0.380] | 0.734 [0.651, 0.817] | 3.18 [2.93, 3.46] |

| Comparison | Metric | Mean difference [95% CI] | Sign-flip p |
|---|---|---|---|
| pcg_fused - pcg_fused_nocontext | first_top1 | -0.0976 [-0.1429, -0.0519] | 0.0001 |
| pcg_fused - pcg_fused_nocontext | all_top3 | -0.1049 [-0.1596, -0.0518] | 0.0004 |
| pcg_fused - pcg_fused_nocontext | mean_rank | +0.4524 [+0.2802, +0.6228] | < 0.0001 |
| pcg_fused - lr_fusion | first_top1 | -0.1537 [-0.2335, -0.0775] | < 0.0001 |
| pcg_fused - lr_fusion | all_top3 | -0.1049 [-0.1788, -0.0322] | 0.0072 |
| pcg_fused - lr_fusion | mean_rank | +0.4622 [+0.2531, +0.6761] | < 0.0001 |
| pcg_fused - pcg_size | first_top1 | -0.0390 [-0.1596, +0.0805] | 0.2420 |
| pcg_fused - pcg_size | all_top3 | -0.1610 [-0.2120, -0.1137] | < 0.0001 |
| pcg_fused - pcg_size | mean_rank | +0.6384 [+0.4442, +0.8097] | < 0.0001 |

## 12. Which faults show a symptom that a compiler, type checker or analyser could see?

| Symptom | D1 (injected) | D2 (human-written) |
|---|---|---|
| Detected faults | 594 | 31 |
| Do not compile | 0 | 0 |
| Some failing test raises a type, name or attribute error | 42 | 0 |
| Some failing test raises another exception | 68 | 7 |
| Some failing test does not terminate | 47 | 3 |
| Only wrong return values | 438 | 22 |
| pylint flags some line (behavioural finding) | 30 | 0 |
| pylint flags the faulty line | 0 | 0 |

## 13. Cost of the mutation analysis

| Dataset | Cases | Variants generated | Distinct variant programs executed | Seconds |
|---|---|---|---|---|
| D1 | 594 | 13430 | 6969 | 44 |
| D1_two_fault | 410 | 8111 | 7559 | 17 |
| external | 413 | 8621 | 6065 | 269 |

Seconds are wall-clock on the machine of the run and are the only non-deterministic numbers in this file.

