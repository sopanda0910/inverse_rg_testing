# Sampling P(Q): L = 8

Unseeded HMC + winding update. Errors bootstrap over CHAINS, so a
frozen chain counts as one independent charge however long it ran.
P(odd) is bootstrapped DIRECTLY from the parity indicator rather
than summed in quadrature over sectors, which would understate it.
Winding move: charge_step 1, interval 5.

Parity mobility is a FLIP COUNT, not a hypothesis test, and
agreement is a bootstrap-calibrated p-value; see `verdict`.

| beta | beta/V | <Q^2> | exact | z | changes | parity flips | frozen | gof p | C-asym z | odd/exact | z_odd | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 6 | 0.0938 | 1.8576 +- 0.0144 | 1.8674 | -0.68 | 30368 | 19330 | 0% | 0.500 | -1.91 | 1.0056 | +1.20 | SAMPLED |
| 10 | 0.1562 | 0.8519 +- 0.0085 | 0.8603 | -0.99 | 22853 | 20333 | 0% | 0.665 | -0.07 | 0.9919 | -1.57 | SAMPLED |
| 14 | 0.2188 | 0.5559 +- 0.0071 | 0.5514 | +0.63 | 17924 | 17839 | 0% | 0.345 | +0.89 | 0.9978 | -0.35 | SAMPLED |
| 20 | 0.3125 | 0.3559 +- 0.0039 | 0.3551 | +0.20 | 12851 | 12851 | 0% | 0.864 | -0.39 | 1.0042 | +0.50 | SAMPLED |

Coldest coupling with honestly sampled topology: **beta = 20** at L = 8.
