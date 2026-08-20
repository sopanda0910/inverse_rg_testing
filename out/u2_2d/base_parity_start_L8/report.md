# Parity mobility at L = 8

Hot start, no burn-in, unseeded. The decisive column is PARITY FLIPS:
where it is zero the odd fraction is a fixed label, the independent
draws are the chains, and only more chains improve it.

| beta | start | beta L | Q changes | parity flips | chains flipped | odd frac | exact | binomial z | tau_int(Q^2) |
|---|---|---|---|---|---|---|---|---|---|
| 10 | hot | 80 | 7102 | 3530 | 128/128 | 0.4860 | 0.4854 | -0.38 | 0.57 |
| 10 | cold | 80 | 7095 | 3560 | 128/128 | 0.4802 | 0.4854 | -0.73 | 0.57 |
| 20 | hot | 160 | 3456 | 0 | 0/128 | 0.5156 | 0.3335 | +4.37 | 0.50 |
| 20 | cold | 160 | 204 | 1 | 1/128 | 0.0003 | 0.3335 | -8.00 | 0.55 |
