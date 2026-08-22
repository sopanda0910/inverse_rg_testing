# Sampling P(Q): L = 16

Unseeded HMC + winding update. Errors bootstrap over CHAINS, so a
frozen chain counts as one independent charge however long it ran.
P(odd) is bootstrapped DIRECTLY from the parity indicator rather
than summed in quadrature over sectors, which would understate it.
Winding move: charge_step 1, interval 5.

Parity mobility is a FLIP COUNT, not a hypothesis test, and
agreement is a bootstrap-calibrated p-value; see `verdict`.

| beta | beta/V | <Q^2> | exact | z | changes | parity flips | frozen | gof p | C-asym z | odd/exact | z_odd | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 28 | 0.1094 | 1.0060 +- 0.0105 | 1.0012 | +0.45 | 45909 | 45909 | 0% | 0.287 | -0.48 | 1.0078 | +2.61 | SAMPLED |
| 51.75 | 0.2021 | 0.5225 +- 0.0046 | 0.5211 | +0.29 | 34152 | 34152 | 0% | 0.612 | -0.61 | 0.9948 | -1.11 | SAMPLED |
| 56 | 0.2188 | 0.4815 +- 0.0040 | 0.4793 | +0.55 | 32556 | 32556 | 0% | 0.493 | +1.66 | 1.0020 | +0.40 | SAMPLED |

Coldest coupling with honestly sampled topology: **beta = 56** at L = 16.
