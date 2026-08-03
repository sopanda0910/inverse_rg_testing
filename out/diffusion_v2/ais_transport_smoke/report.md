# AIS-corrected transport

bridge steps 12, 2 HMC updates/step, Q-hops on, n = 48, split fit (fit even / quote odd)

| L | beta_f | fiber std (before) | ESS/N before | surrogate R^2 | AIS std (held-out) | AIS ESS/N (held-out) | AIS ESS/N (all) | HMC acc | dF gap (sem) |
|---|--------|--------------------|--------------|---------------|--------------------|----------------------|-----------------|---------|--------------|
| 8 | 2 | 7.3 | 0.0211 | 0.076 | 7.14 | 0.042 | 0.021 | 0.89 | -88.45 (0.99) |

## Observables (AIS-weighted vs exact)

| L | beta_f | obs | raw | z_raw | AIS | z_AIS | exact |
|---|--------|-----|-----|-------|-----|-------|-------|
| 8 | 2 | plaquette | 0.74047 (0.0076) | +5.6 | 0.64317 (0.00068) | -- | 0.69777 |
| | | Q^2 | 1.25 (0.2) | +0.1 | 1.0136 (0.019) | -- | 1.2393 |
| | | Q | -0.20833 (0.16) | -1.3 | 1.0037 (0.0058) | -- | 0 |

Weights are valid AIS weights (Neal 2001) from the exact ODE density;
the surrogate fit residual on the held-out half is the irreducible
floor, the bridge increments shrink with more steps. z_AIS suppressed
when effective count < 4. The certificate's exact value here is
2 L^2 log 2pi + log Z_haar(beta_f, L) -- no coarse term (the coarse
level integrates out of the AIS estimator exactly).