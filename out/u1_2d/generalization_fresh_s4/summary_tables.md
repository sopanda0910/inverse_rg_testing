# Generalization study: summary tables

All references are HMC with instanton Q-hop updates (unbiased topology). z columns are z-scores against exact character-expansion values; `min KS p` is the smallest two-sample KS p-value across all measured Wilson loop sizes.

## Part A: matched-pair beta scan (L=16 -> L=32)

| run | base (L, beta) | target beta | matched beta | beta ratio | plaq z | W(2x2) z | W(4x4) z | W(8x8) z | Q z | Q^2 z | chi_top z | P(Q) chi2 p | min KS p | raw Q match | raw Q^2 (base) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_bc8 | (16, 8) | 30.3772 | 30.38 | 1.00 | +2.31 | +2.07 | +2.11 | +1.50 | +0.78 | -1.74 | -2.29 | 0.345 | 0.012 | 0.28 | 2.43 (0.69) |

## Part D: upper-coupling matched pairs (L=16 -> L=32)

| run | base (L, beta) | target beta | matched beta | beta ratio | plaq z | W(2x2) z | W(4x4) z | W(8x8) z | Q z | Q^2 z | chi_top z | P(Q) chi2 p | min KS p | raw Q match | raw Q^2 (base) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D_bc14.1464 | (16, 14.1464) | 55.0237 | 55.02 | 1.00 | +1.11 | +0.51 | +0.82 | +0.57 | +0.62 | -2.24 | -2.91 | 0.026 | 0.048 | 0.33 | 3.08 (0.33) |

## Part F: extrapolation demo (targets far beyond the training range, incl. large volume)

| run | base (L, beta) | target beta | matched beta | beta ratio | plaq z | W(2x2) z | W(4x4) z | W(8x8) z | Q z | Q^2 z | chi_top z | P(Q) chi2 p | min KS p | raw Q match | raw Q^2 (base) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F_L64_bc55.0237 | (32, 55.0237) | 218.58 | 218.6 | 1.00 | -0.58 | -0.54 | +0.01 | -0.89 | -1.70 | +0.12 | -0.12 | 0.374 | 0.000 | 0.12 | 13.31 (0.48) |

## Part B: target-coupling mismatch (base L=16)

| run | base (L, beta) | target beta | matched beta | beta ratio | plaq z | W(2x2) z | W(4x4) z | W(8x8) z | Q z | Q^2 z | chi_top z | P(Q) chi2 p | min KS p | raw Q match | raw Q^2 (base) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B_bt20 | (16, 4) | 20 | 14.15 | 1.41 | +1.48 | +1.26 | +0.26 | -0.64 | -0.66 | +2.64 | +3.33 | 0.008 | 0.137 | 0.18 | 4.28 (2.11) |
