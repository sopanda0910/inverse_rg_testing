# Sampling P(Q): L = 8

Unseeded HMC + winding update. Errors bootstrap over CHAINS, so a
frozen chain counts as one independent charge however long it ran.

| beta | beta/V | <Q^2> | exact | z | changes | frozen | chi2/dof | odd/exact | z_odd | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| 6 | 0.0938 | 1.8672 +- 0.0177 | 1.8674 | -0.01 | 15050 | 0% | 0.55 | 0.991 | -0.96 | SAMPLED |
| 10 | 0.1562 | 0.8448 +- 0.0124 | 0.8603 | -1.25 | 11401 | 0% | 2.81 | 0.990 | -0.88 | DISAGREES |
| 14 | 0.2188 | 0.5445 +- 0.0089 | 0.5514 | -0.77 | 8975 | 0% | 1.31 | 0.987 | -0.99 | SAMPLED |
| 20 | 0.3125 | 0.3536 +- 0.0060 | 0.3551 | -0.24 | 6313 | 0% | 0.13 | 0.992 | -0.43 | SAMPLED |

Coldest coupling with honestly sampled topology: **beta = 20** at L = 8.
