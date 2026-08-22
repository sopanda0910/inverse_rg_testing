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
| 56 | 0.2188 | 0.4790 +- 0.0038 | 0.4793 | -0.09 | 32406 | 32406 | 0% | 0.743 | -0.84 | 0.9990 | -0.21 | SAMPLED |

Coldest coupling with honestly sampled topology: **beta = 56** at L = 16.
