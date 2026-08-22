# Sampling P(Q): L = 16

Unseeded HMC + winding update. Errors bootstrap over CHAINS, so a
frozen chain counts as one independent charge however long it ran.

| beta | beta/V | <Q^2> | exact | z | changes | frozen | chi2/dof | odd/exact | z_odd | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| 14 | 0.0547 | 2.2666 +- 0.0640 | 2.2074 | +0.92 | 13865 | 0% | 1.76 | 1.009 | +0.58 | SAMPLED |
| 28 | 0.1094 | 0.9485 +- 0.0164 | 1.0012 | -3.22 | 11462 | 0% | 2.80 | 0.992 | -0.55 | DISAGREES |
| 51.75 | 0.2021 | 0.5319 +- 0.0091 | 0.5211 | +1.19 | 8517 | 0% | 1.17 | 1.012 | +0.69 | SAMPLED |
| 56 | 0.2188 | 0.4754 +- 0.0073 | 0.4793 | -0.54 | 8042 | 0% | 1.39 | 1.013 | +0.88 | SAMPLED |

Coldest coupling with honestly sampled topology: **beta = 56** at L = 16.
