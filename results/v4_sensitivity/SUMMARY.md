# Tie-corrected sensitivity of the average-precision results (generated)

Expected average precision under random tie-breaking (300 draws per case, seeded).

| Set | Method | MAP (mid-rank, as pre-registered) | MAP (expected) | Cases with AP above 1 |
|---|---|---|---|---|
| Q2 | iv | 0.632 | 0.631 | 2.8% |
| Q2 | pcg_fused | 0.549 | 0.541 | 3.5% |
| Q2 | pcg_size | 0.578 | 0.566 | 3.2% |
| Q2 | lr_fusion | 0.592 | 0.585 | 2.5% |
| Q2 | muse | 0.601 | 0.601 | 0.0% |
| Q2 | flitsr_star | 0.574 | 0.560 | 3.2% |
| Q2 | ochiai | 0.575 | 0.562 | 3.2% |
| E2 | iv | 0.662 | 0.659 | 1.5% |
| E2 | pcg_fused | 0.577 | 0.565 | 2.2% |
| E2 | pcg_size | 0.638 | 0.597 | 7.2% |
| E2 | lr_fusion | 0.626 | 0.617 | 1.7% |
| E2 | muse | 0.635 | 0.633 | 1.5% |
| E2 | flitsr_star | 0.633 | 0.592 | 7.2% |
| E2 | ochiai | 0.633 | 0.592 | 7.2% |
| Q3 | iv | 0.702 | 0.654 | 8.1% |
| Q3 | pcg_fused | 0.654 | 0.593 | 7.5% |
| Q3 | pcg_size | 0.733 | 0.624 | 16.2% |
| Q3 | lr_fusion | 0.663 | 0.628 | 6.9% |
| Q3 | muse | 0.710 | 0.631 | 8.1% |
| Q3 | flitsr_star | 0.729 | 0.622 | 15.6% |
| Q3 | ochiai | 0.733 | 0.625 | 16.2% |
| E3 | iv | 0.689 | 0.659 | 5.3% |
| E3 | pcg_fused | 0.638 | 0.592 | 5.3% |
| E3 | pcg_size | 0.736 | 0.637 | 14.4% |
| E3 | lr_fusion | 0.657 | 0.630 | 5.6% |
| E3 | muse | 0.718 | 0.664 | 10.6% |
| E3 | flitsr_star | 0.732 | 0.634 | 14.4% |
| E3 | ochiai | 0.734 | 0.633 | 14.6% |
| QHM | iv | 0.624 | 0.628 | 0.0% |
| QHM | pcg_fused | 0.593 | 0.587 | 1.1% |
| QHM | pcg_size | 0.607 | 0.578 | 4.6% |
| QHM | lr_fusion | 0.591 | 0.597 | 0.6% |
| QHM | muse | 0.566 | 0.568 | 1.7% |
| QHM | flitsr_star | 0.589 | 0.560 | 4.6% |
| QHM | ochiai | 0.592 | 0.561 | 4.6% |
| EHM | iv | 0.640 | 0.630 | 3.0% |
| EHM | pcg_fused | 0.571 | 0.554 | 4.2% |
| EHM | pcg_size | 0.634 | 0.588 | 7.7% |
| EHM | lr_fusion | 0.571 | 0.565 | 1.7% |
| EHM | muse | 0.647 | 0.630 | 3.2% |
| EHM | flitsr_star | 0.624 | 0.581 | 7.2% |
| EHM | ochiai | 0.626 | 0.579 | 7.7% |

H1 recomputed with the expected average precision:

| Set | Comparison | Difference [95% CI] | Holm p | Supported |
|---|---|---|---|---|
| Q2 | iv - pcg_fused | +0.091 [+0.061, +0.120] | 0.0005 | yes |
| Q2 | iv - pcg_size | +0.065 [+0.035, +0.095] | 0.0062 | yes |
| Q2 | iv - muse | +0.030 [-0.016, +0.075] | 0.3041 | no |
| Q2 | iv - flitsr_star | +0.072 [+0.041, +0.102] | 0.0047 | yes |
| Q2 | iv - lr_fusion | +0.046 [+0.018, +0.078] | 0.0214 | yes |
| E2 | iv - pcg_fused | +0.093 [+0.074, +0.112] | 0.0005 | yes |
| E2 | iv - pcg_size | +0.062 [+0.041, +0.082] | 0.0005 | yes |
| E2 | iv - muse | +0.025 [-0.003, +0.053] | 0.2008 | no |
| E2 | iv - flitsr_star | +0.067 [+0.047, +0.087] | 0.0005 | yes |
| E2 | iv - lr_fusion | +0.041 [+0.023, +0.059] | 0.0005 | yes |
