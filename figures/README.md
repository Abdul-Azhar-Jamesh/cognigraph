# Figure index

Figures are written by the experiment code into the folder of the run that produced them, next to the manifest that fixes
their checksum. They are therefore **not copied here** (one authoritative copy of each). Version-4 figures exist as PNG
(300 dpi) and PDF, are rebuilt from the raw result files by `python -m pcg v4-report`, and are described in
[../research/RESULTS.md](../research/RESULTS.md).

## Version 4 (`results/v4/figures/`)

| Figure | Shows |
|---|---|
| `results/v4/figures/fig1_two_fault_map.png` (`.pdf`) | mean average precision of all methods on the two-fault sets D1-2, Q2, E2 |
| `results/v4/figures/fig2_single_vs_two_fault.png` (`.pdf`) | each method on one-fault Top-1 against two-fault MAP |
| `results/v4/figures/fig3_map_by_fault_count.png` (`.pdf`) | MAP by number of injected faults (1, 2, 3) |
| `results/v4/figures/fig4_reliability.png` (`.pdf`) | reliability curves with ECE |
| `results/v4/figures/fig5_risk_coverage.png` (`.pdf`) | selective localisation (risk against coverage) |
| `results/v4/figures/fig6_ablations.png` (`.pdf`) | ablations of the interventional model |
| `results/v4/figures/fig7_inferred_fault_count.png` (`.pdf`) | posterior expected number of faults against the true number |
| `results/v4/figures/fig8_human_bugs.png` (`.pdf`) | reciprocal rank on the human-written bugs |
| `results/v4_synthetic/figures/fig_synthetic.png` (`.pdf`) | simulated programs: ranking and calibration when assumptions hold or break |
| `results/demo_v4/two_faults/posteriors.png`, `results/demo_v4/cost_of_generality/posteriors.png`, `results/demo_v4/no_repair/posteriors.png` | the three demonstration cases |

CSV tables of version 4: `results/v4/tables/ranking_all.csv`, `calibration_all.csv`, `paired_comparisons.csv`
(and `results/v4/SUMMARY.md`, `results/v4/summary.json`).

## Versions 2 and 3

| Figure | Shows |
|---|---|
| `results/benchmark/fig_method_comparison.png` | version-2 methods on injected faults |
| `results/benchmark/fig_reliability.png` | version-2 calibration |
| `results/benchmark/fig_sensitivity.png` | version-2 sensitivity of the parameters |
| `results/research/fig_fusion_ranking.png` | version-3 fusion ranking on D1, D2, D3 |
| `results/research/fig_fusion_reliability.png` | version-3 reliability |
| `results/research/fig_risk_coverage.png` | version-3 risk-coverage curves |
| `results/demo/original_example/graph.png`, `results/demo/clear_success/graph.png`, `results/demo/worst_case/graph.png`, `results/demo/human_bug/graph.png` | constraint graphs of the version-3 demonstration cases |

Known cosmetic defect: the legend of `fig3_map_by_fault_count` covers part of the right panel (see
[../research/FINAL_RESEARCH_AUDIT.md](../research/FINAL_RESEARCH_AUDIT.md)).
