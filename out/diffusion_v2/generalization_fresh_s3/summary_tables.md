# Generalization study: summary tables

All references are HMC with instanton Q-hop updates (unbiased topology). z columns are z-scores against exact character-expansion values; `min KS p` is the smallest two-sample KS p-value across all measured Wilson loop sizes.

## Part A: matched-pair beta scan (L=16 -> L=32)

| run | base (L, beta) | target beta | matched beta | beta ratio | plaq z | W(2x2) z | W(4x4) z | W(8x8) z | Q z | Q^2 z | chi_top z | P(Q) chi2 p | min KS p | raw Q match | raw Q^2 (base) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_bc8 | (16, 8) | 30.3772 | 30.38 | 1.00 | -1.33 | -0.34 | -0.11 | +0.12 | +4.18 | +0.62 | -0.20 | 0.003 | 0.009 | 0.29 | 3.49 (0.94) |

## Part D: upper-coupling matched pairs (L=16 -> L=32)

| run | base (L, beta) | target beta | matched beta | beta ratio | plaq z | W(2x2) z | W(4x4) z | W(8x8) z | Q z | Q^2 z | chi_top z | P(Q) chi2 p | min KS p | raw Q match | raw Q^2 (base) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D_bc14.1464 | (16, 14.1464) | 55.0237 | 55.02 | 1.00 | +2.24 | +2.97 | +1.45 | +0.28 | -1.77 | -0.21 | -0.35 | 0.308 | 0.078 | 0.26 | 3.20 (0.46) |

## Part F: extrapolation demo (targets far beyond the training range, incl. large volume)

| run | base (L, beta) | target beta | matched beta | beta ratio | plaq z | W(2x2) z | W(4x4) z | W(8x8) z | Q z | Q^2 z | chi_top z | P(Q) chi2 p | min KS p | raw Q match | raw Q^2 (base) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F_L64_bc55.0237 | (32, 55.0237) | 218.58 | 218.6 | 1.00 | -0.49 | -0.86 | -0.76 | -0.30 | +1.05 | -0.28 | -0.34 | 0.817 | 0.000 | 0.19 | 13.34 (0.45) |

## Part B: target-coupling mismatch (base L=16)

| run | base (L, beta) | target beta | matched beta | beta ratio | plaq z | W(2x2) z | W(4x4) z | W(8x8) z | Q z | Q^2 z | chi_top z | P(Q) chi2 p | min KS p | raw Q match | raw Q^2 (base) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B_bt20 | (16, 4) | 20 | 14.15 | 1.41 | -1.49 | -2.56 | -2.32 | -1.55 | +0.94 | +2.80 | +2.89 | 0.299 | 0.037 | 0.23 | 3.92 (2.05) |
