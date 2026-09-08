# Pre-registered analysis: does wider training coverage produce better seeds?

Written **2026-09-08 08:55**, while the widened-grid scan is still running and
before any of its eight new couplings have been scored. The seven original
couplings have been seen; the eight new ones have not. This file fixes the
analysis so the confirmatory test cannot be chosen after the fact.

## The defect this replaces

The endpoint used until now was binary: *does the diffusion seed resolve a
finite relaxation time?* It is inverted for good seeds, and the inversion is
mechanical, not statistical.

`fit_relaxation_time` fits `mean(t) ≈ target + A·exp(-t/tau)`. A seed that is
**far** from the target relaxes visibly, so the fit succeeds and returns a
finite `tau` — scored as a **success**. A seed that is **already at the
target** has no decay to resolve, so the fit returns `inf` (or is rejected by
the goodness-of-fit veto) — scored as a **failure**.

Measured on the seven original couplings, raw seed `max|z|` at record 0
(before any trajectory) against the finite-`tau` indicator:

| checkpoint | raw seed max\|z\| | binary "resolves" |
|---|---|---|
| `deployed` (β_max=60) | **65–78** at every coupling | 6/7 (pre-veto) |
| `wide2000` | **1.2–10.3** | 2/7 |
| `wide2000_dense` | **1.1–11.4** | 3/7 |

`deployed`'s seeds are 65–78σ from exact and score as successes; the wide
checkpoints' seeds are near exact and score as failures. The binary endpoint
was ranking checkpoints by *how much room their seeds left to relax*, which is
the opposite of seed quality. The goodness-of-fit veto fixed part of this
(`deployed` 6/7 → 2/7) but the metric remains wrong in principle: it cannot
distinguish `tau=0` (already correct, the best case) from `tau=483` (correct
only after 483 records, a bad case), scoring both as "resolved".

## Primary endpoint (pre-registered)

**`Z = max|z|` of the raw diffusion seed at record 0**, over
`{plaquette, W(2×2), W(4×4)}`, against the exact closed-form value, with `z`
the across-chain SEM at 64 chains.

Chosen because it is (i) the quantity the claim is about — how far the
delivered seed is from the truth; (ii) fit-free, so it inherits none of the
relaxation estimator's failure modes (local minima, the χ²/dof veto, the
chain-order dependence fixed on 2026-09-08); (iii) continuous, so a paired
rank test uses the magnitudes rather than 15 bits; (iv) already recorded — it
needs no new compute, only the saved series.

## Test (pre-registered)

- **Design**: paired over all 15 couplings (fine β 250–2600); the pairing is
  exact, since every checkpoint is evaluated on identical cases.
- **Primary test**: Wilcoxon signed-rank on `log Z`, `deployed` vs
  `wide2000` and `deployed` vs `wide2000_dense`, two-sided, α = 0.05.
- **Effect size**: median ratio `Z_deployed / Z_wide` with a bootstrap CI.
- **Secondary, reported but not decisive**: the binary indicator, so the
  change of endpoint is visible rather than silent.
- **Pre-specified subgroup**: the 8 off-rung couplings alone (they sit in the
  gaps between `wide2000`'s trained rungs, so they are the honest test of
  coverage rather than of hitting a rung).

## What would falsify the coverage claim

`wide2000` failing to beat `deployed` on `Z`, or beating it only on the 7
on-rung couplings and not on the 8 off-rung ones — the latter would say the
wide checkpoints only work where they were trained, which is a much weaker
claim than "wider coverage helps".

## Known limitation, stated in advance

On the seven already-seen couplings the primary endpoint gives `wide2000`
better at 7/7 (median 10.7×, p = 0.0156) and `wide2000_dense` better at 7/7
(median 13.1×, p = 0.0156). Those seven are **not** independent confirmation
of a rule chosen partly by looking at them. The eight new couplings are the
confirmatory sample, and the paper should report the 15-coupling result with
this history stated.
