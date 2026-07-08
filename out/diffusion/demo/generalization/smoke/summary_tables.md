# Generalization study: summary tables

All references are HMC with instanton Q-hop updates (unbiased topology). z columns are z-scores against exact character-expansion values; `min KS p` is the smallest two-sample KS p-value across all measured Wilson loop sizes.

## Part A: matched-pair beta scan (L=16 -> L=32)

| run | base (L, beta) | target beta | matched beta | beta ratio | plaq z | W(2x2) z | W(4x4) z | W(8x8) z | Q z | Q^2 z | chi_top z | P(Q) chi2 p | min KS p |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_bc1 | (16, 1) | 3.10399 | 3.104 | 1.00 | -0.75 | -0.88 | -1.35 | +0.62 | +1.51 | -0.66 | -1.23 | - | 0.058 |
| A_bc4 | (16, 4) | 14.1464 | 14.15 | 1.00 | -0.45 | -0.59 | +0.18 | +2.73 | -0.23 | -1.03 | -0.90 | - | 0.000 |

## Part D: upper-coupling matched pairs (L=16 -> L=32)

| run | base (L, beta) | target beta | matched beta | beta ratio | plaq z | W(2x2) z | W(4x4) z | W(8x8) z | Q z | Q^2 z | chi_top z | P(Q) chi2 p | min KS p |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D_bc55.0237 | (16, 55.0237) | 218.58 | 218.6 | 1.00 | +0.61 | +0.84 | +0.14 | -1.25 | +0.00 | +inf | +inf | - | 0.000 |

## Part B: target-coupling mismatch (base L=16)

| run | base (L, beta) | target beta | matched beta | beta ratio | plaq z | W(2x2) z | W(4x4) z | W(8x8) z | Q z | Q^2 z | chi_top z | P(Q) chi2 p | min KS p |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B_bc2_bt8 | (16, 2) | 8 | 6.105 | 1.31 | -0.23 | -0.16 | +0.24 | +0.22 | -0.88 | -1.92 | -2.83 | - | 0.000 |
| B_bt6 | (16, 4) | 6 | 14.15 | 0.42 | +0.78 | +0.35 | -0.82 | -0.73 | -1.73 | -1.84 | -1.93 | - | 0.000 |

## Part C: lattice-size scan (pair 4 -> 14.1464)

| run | base (L, beta) | target beta | matched beta | beta ratio | plaq z | W(2x2) z | W(4x4) z | W(8x8) z | Q z | Q^2 z | chi_top z | P(Q) chi2 p | min KS p |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C_L64 | (32, 4) | 14.1464 | 14.15 | 1.00 | +0.07 | +1.66 | +1.94 | +0.75 | -0.52 | -1.27 | -1.63 | - | 0.000 |
