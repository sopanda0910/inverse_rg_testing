# Sampling P(Q): L = 16

Unseeded HMC + winding update. Errors bootstrap over CHAINS, so a
frozen chain counts as one independent charge however long it ran.
P(odd) is bootstrapped DIRECTLY from the parity indicator rather
than summed in quadrature over sectors, which would understate it.
Winding move: charge_step 1, interval 5.

| beta | beta/V | <Q^2> | exact | z | changes | frozen | chi2/dof | odd/exact | z_odd | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| 28 | 0.1094 | 1.0060 +- 0.0105 | 1.0012 | +0.45 | 45909 | 0% | 0.87 | 1.008 | +2.61 | PARITY-STUCK |
| 51.75 | 0.2021 | 0.5225 +- 0.0046 | 0.5211 | +0.29 | 34152 | 0% | 6.90 | 0.995 | -1.11 | DISAGREES |
| 56 | 0.2188 | 0.4815 +- 0.0040 | 0.4793 | +0.55 | 32556 | 0% | 1.09 | 1.002 | +0.40 | SAMPLED |

Coldest coupling with honestly sampled topology: **beta = 56** at L = 16.
