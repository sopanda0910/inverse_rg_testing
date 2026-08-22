# Sampling P(Q): L = 8

Unseeded HMC + winding update. Errors bootstrap over CHAINS, so a
frozen chain counts as one independent charge however long it ran.
P(odd) is bootstrapped DIRECTLY from the parity indicator rather
than summed in quadrature over sectors, which would understate it.
Winding move: charge_step 2, interval 1.

Parity mobility is a FLIP COUNT, not a hypothesis test, and
agreement is a bootstrap-calibrated p-value; see `verdict`.

| beta | beta/V | <Q^2> | exact | z | changes | parity flips | frozen | gof p | odd/exact | z_odd | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3 | 0.0469 | 3.6931 +- 0.1751 | 3.8539 | -0.92 | 591 | 351 | 0% | 0.955 | 1.0194 | +0.54 | SAMPLED |

Coldest coupling with honestly sampled topology: **beta = 3** at L = 8.
