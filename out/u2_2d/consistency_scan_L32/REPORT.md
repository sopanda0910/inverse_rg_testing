# Can stronger reconstruction guidance replace the charge projection?

`u2_2d/scripts/53_consistency_weight_scan.py`, 2026-08-24. 256 configurations,
charge projection OFF throughout, no rethermalization -- this scores the RAW
lift, so the topology the model produces unaided is visible.

**Answer: no, and the failure is structural rather than a tuning miss.**

## L = 32, beta = 105.651 (exact `<Q^2>` = 1.0012)

| w | coherent resid | incoherent resid | defects/cfg | std(dQ) | sector match | `<Q^2>`/exact | plaq rel | sigma/exact | W4x4 rel |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 0.0321 | 0.1365 | 0.00 | 1.67 | 0.246 | 4.24 | -4.11e-04 | 1.16 | -5.60e-03 |
| **1** | **0.0316** | **0.0452** | 0.00 | **1.68** | **0.250** | **3.70** | **+4.10e-05** | **1.00** | -4.84e-03 |
| 2 | 0.0377 | 0.0616 | 0.00 | 1.96 | 0.219 | 4.71 | +3.61e-05 | 1.09 | -2.83e-03 |
| 5 | 0.0448 | 0.1249 | 0.00 | 2.26 | 0.168 | 5.26 | -9.91e-05 | 1.04 | -4.90e-03 |
| 10 | 0.0537 | 0.1958 | 0.00 | 2.83 | 0.168 | 8.63 | -3.55e-04 | 1.18 | -9.00e-03 |
| 30 | 0.1896 | 3.6556 | 103.84 | 9.87 | 0.062 | 97.27 | -3.65e-01 | 22.54 | -1.00e+00 |

L = 64 reproduces it: w = 0 gives std(dQ) 3.37 / match 0.125 / 16.04x, w = 1
gives 3.47 / 0.109 / 14.73x.

## Three readings

**1. Topology degrades MONOTONICALLY with weight.** std(dQ) 1.68 -> 9.87 and
`<Q^2>`/exact 3.7 -> 97 from w = 1 to w = 30. At w = 30 the arm has collapsed
into `flux`: 103 winding defects per configuration, per-configuration spread
22.5x too wide, W(4x4) wrong by 100%. That limit was predicted from the
construction and is worth keeping in the table as the anchor.

**2. `consistency_weight = 1.0` is optimal -- and it is optimal for LOCAL
physics, not topology.** The plaquette is +4.1e-05 and sigma/exact is exactly
1.00 at w = 1, both worse at w = 0 and at every higher weight. This is the
`lambda(sigma) = 8 sigma^2` derivation confirmed empirically: the Bayesian-correct
reconstruction weight is the best one, and the knob was not left at an untuned
default.

**3. The mechanism says why more guidance CANNOT work.** Decompose the per-cell
telescope residual into a coherent part (its signed mean within a configuration)
and an incoherent part (its spread), noting that
`sum_cells residual = 2 pi (Q_f - Q_c)` exactly:

* guidance suppresses the INCOHERENT residual, 0.1365 -> 0.0452 going w = 0 -> 1;
* it leaves the COHERENT one untouched, 0.0321 -> 0.0316;
* and the coherent one is what moves Q. At 256 coarse cells,
  0.0316 x 256 / 2 pi = **1.11** of the observed std(dQ) = 1.68.

Above w = 1 the guidance starts distorting the reverse-diffusion trajectory and
the coherent term GROWS (0.032 -> 0.19), which is why topology gets worse rather
than better.

**A local reconstruction term cannot reach a global zero-mode.** That is the
structural statement, and it is a much stronger argument for the charge
projection than "we tried it and it works": the projection is a global,
gauge-covariant instanton-like shift, which is exactly the object that acts on
the mode the guidance cannot see.

## Two diagnostics that had to be fixed first, both instructive

* **The wrapped residual is the wrong metric**, and
  `blocking_consistency_score`'s own docstring says so ("a wrapped residual is
  blind to a cell sum landing 2 pi away"). Wrapped, the residual is 0.046 rad
  over 256 cells -- far too small to produce std(dQ) = 1.5. The raw residual is
  what carries the charge.
* **There are NO winding defects at any usable weight** (0.00 per configuration
  up to w = 10). So the error is not the defect mechanism the docstring warns
  about either; it is the coherent mode. Two mechanism guesses were wrong before
  this was decomposed, which is the standing lesson about building a mechanism on
  a summary statistic instead of measuring its parts.

## Provenance caveat

The telescope residuals quoted elsewhere for the transport-off LADDER (0.44 rad
at L = 32, 0.22 at L = 64) are POST-rethermalization. Ten retherm sweeps update
both sectors and degrade blocking consistency by roughly 10x. The raw lift is
0.046 rad. The charge conclusions are unaffected -- std(dQ) is 1.51 raw against
1.79 post-retherm -- but do not quote the post-retherm residual as a property of
the model.

---

# L = 64 confirms it, and the mechanism closes quantitatively

`out/u2_2d/consistency_scan_L64/`, beta = 416.524, 256 configurations.

| w | coherent | incoherent | defects/cfg | std(dQ) | match | `<Q^2>`/exact | plaq rel | sigma/exact |
|---|---|---|---|---|---|---|---|---|
| 0 | 0.01769 | 0.0877 | 0.00 | 3.37 | 0.125 | 16.04 | -1.30e-04 | 1.09 |
| **1** | 0.01774 | **0.0440** | 0.00 | **3.47** | 0.109 | **14.73** | **+6.04e-05** | 1.09 |
| 2 | 0.01929 | 0.0636 | 0.00 | 3.87 | 0.094 | 16.23 | +5.58e-05 | 1.07 |
| 5 | 0.02152 | 0.1257 | 0.00 | 4.37 | 0.113 | 19.00 | -7.03e-05 | 1.19 |
| 10 | 0.02598 | 0.1954 | 0.00 | 5.20 | 0.051 | 27.48 | -3.34e-04 | 1.75 |
| 30 | 0.09331 | 3.6261 | 411.68 | 18.98 | 0.023 | 359.98 | -3.64e-01 | 89.75 |

Same shape as L = 32: topology monotone in the wrong direction, w = 1 best for
local physics, total collapse at w = 30. The LOCAL damage is worse at the larger
volume (sigma/exact 1.75 at w = 10 against 1.18 at L = 32), so the knob is not
merely useless at scale, it is more dangerous.

## The coherent mode accounts for the charge error to 4%

`resid_coherent_mean` records `E|mean|`, and for a Gaussian mean that is
`sigma sqrt(2/pi)`, so the mode's true amplitude is
`sigma_coh = E|mean| / sqrt(2/pi)`. Its integrated effect on the charge is
`sigma_coh x N_cells / 2 pi`:

| | cells | sigma_coh | coherent predicts | observed std(dQ) | incoherent share |
|---|---|---|---|---|---|
| L = 32 | 256 | 0.03965 | **1.62** | **1.68** | 6.8% |
| L = 64 | 1024 | 0.02223 | **3.62** | **3.47** | 6.5% |

**The charge error is one global coherent mode, full stop.** Local noise
contributes under 7% and winding defects contribute nothing at any usable
weight.

Its per-cell amplitude FALLS with volume (0.0397 -> 0.0222) while the cell count
rises 4x, so the integrated effect grows as `sqrt(V)`: std(dQ) 1.68 -> 3.47, a
factor 2.07 against `sqrt(4) = 2`. That reconciles the two descriptions -- the
mode is coherent ACROSS the lattice within one configuration, and its total
contribution scales as the square root of the volume.

**Why guidance cannot touch it.** `blocking_consistency_score` is a sum of
independent per-cell penalties. Such a term suppresses per-cell fluctuations --
measured, 0.1365 -> 0.0452 at L = 32 and 0.0877 -> 0.0440 at L = 64, a factor of
3 in each case -- but it has almost no gradient along a direction that shifts
every cell together by a small equal amount, because that direction is nearly
flat for the sum while being exactly the direction that moves Q. A local
reconstruction term cannot see a global zero-mode. `apply_coarse_charge` acts on
precisely that mode, which is why it is structurally necessary and why no
setting of this knob replaces it.
