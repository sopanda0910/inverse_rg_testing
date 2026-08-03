# Generalization study: summary tables

All references are HMC with instanton Q-hop updates (unbiased topology). z columns are z-scores against exact character-expansion values; `min KS p` is the smallest two-sample KS p-value across all measured Wilson loop sizes.

## Part A: matched-pair beta scan (L=16 -> L=32)

| run | base (L, beta) | target beta | matched beta | beta ratio | plaq z | W(2x2) z | W(4x4) z | W(8x8) z | Q z | Q^2 z | chi_top z | P(Q) chi2 p | min KS p | raw Q match | raw Q^2 (base) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_bc8 | (16, 8) | 30.3772 | 30.38 | 1.00 | -0.02 | +0.56 | +1.42 | +0.44 | +2.37 | -0.86 | -1.23 | 0.159 | 0.003 | 0.24 | 2.89 (0.79) |

## Part D: upper-coupling matched pairs (L=16 -> L=32)

| run | base (L, beta) | target beta | matched beta | beta ratio | plaq z | W(2x2) z | W(4x4) z | W(8x8) z | Q z | Q^2 z | chi_top z | P(Q) chi2 p | min KS p | raw Q match | raw Q^2 (base) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D_bc14.1464 | (16, 14.1464) | 55.0237 | 55.02 | 1.00 | +0.45 | +0.57 | +0.40 | +1.28 | +1.05 | +0.70 | +0.85 | 0.424 | 0.005 | 0.21 | 3.35 (0.54) |

## Part F: extrapolation demo (targets far beyond the training range, incl. large volume)

| run | base (L, beta) | target beta | matched beta | beta ratio | plaq z | W(2x2) z | W(4x4) z | W(8x8) z | Q z | Q^2 z | chi_top z | P(Q) chi2 p | min KS p | raw Q match | raw Q^2 (base) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F_L64_bc55.0237 | (32, 55.0237) | 218.58 | 218.6 | 1.00 | -0.76 | -1.28 | -0.19 | +0.34 | +1.25 | -0.32 | -0.43 | 0.495 | 0.000 | 0.14 | 9.52 (0.45) |

## Part B: target-coupling mismatch (base L=16)

| run | base (L, beta) | target beta | matched beta | beta ratio | plaq z | W(2x2) z | W(4x4) z | W(8x8) z | Q z | Q^2 z | chi_top z | P(Q) chi2 p | min KS p | raw Q match | raw Q^2 (base) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B_bt20 | (16, 4) | 20 | 14.15 | 1.41 | -0.04 | +0.13 | +0.18 | +0.05 | +1.93 | +2.59 | +1.99 | 0.237 | 0.152 | 0.27 | 4.43 (1.89) |
