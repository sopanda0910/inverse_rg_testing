# Generalization study: summary tables

All references are HMC with instanton Q-hop updates (unbiased topology). z columns are z-scores against exact character-expansion values; `min KS p` is the smallest two-sample KS p-value across all measured Wilson loop sizes.

## Part A: matched-pair beta scan (L=16 -> L=32)

| run | base (L, beta) | target beta | matched beta | beta ratio | plaq z | W(2x2) z | W(4x4) z | W(8x8) z | Q z | Q^2 z | chi_top z | P(Q) chi2 p | min KS p | raw Q match | raw Q^2 (base) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_bc8 | (16, 8) | 30.3772 | 30.38 | 1.00 | +0.84 | +1.25 | +0.28 | -1.45 | +1.32 | +0.60 | +0.78 | 0.537 | 0.078 | 0.28 | 3.53 (1.00) |

## Part D: upper-coupling matched pairs (L=16 -> L=32)

| run | base (L, beta) | target beta | matched beta | beta ratio | plaq z | W(2x2) z | W(4x4) z | W(8x8) z | Q z | Q^2 z | chi_top z | P(Q) chi2 p | min KS p | raw Q match | raw Q^2 (base) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D_bc14.1464 | (16, 14.1464) | 55.0237 | 55.02 | 1.00 | +0.83 | -0.50 | -0.59 | +0.05 | +1.63 | +0.67 | +0.87 | 0.516 | 0.001 | 0.27 | 3.10 (0.55) |

## Part F: extrapolation demo (targets far beyond the training range, incl. large volume)

| run | base (L, beta) | target beta | matched beta | beta ratio | plaq z | W(2x2) z | W(4x4) z | W(8x8) z | Q z | Q^2 z | chi_top z | P(Q) chi2 p | min KS p | raw Q match | raw Q^2 (base) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F_L64_bc55.0237 | (32, 55.0237) | 218.58 | 218.6 | 1.00 | +0.59 | +0.47 | +0.40 | -0.02 | +0.20 | -2.03 | -1.88 | 0.685 | 0.001 | 0.14 | 12.77 (0.36) |

## Part B: target-coupling mismatch (base L=16)

| run | base (L, beta) | target beta | matched beta | beta ratio | plaq z | W(2x2) z | W(4x4) z | W(8x8) z | Q z | Q^2 z | chi_top z | P(Q) chi2 p | min KS p | raw Q match | raw Q^2 (base) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B_bt20 | (16, 4) | 20 | 14.15 | 1.41 | +0.99 | +0.53 | -0.25 | -0.46 | -0.16 | +3.10 | +2.97 | 0.093 | 0.152 | 0.32 | 3.17 (2.05) |
