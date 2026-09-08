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

---

## OUTCOME (added 2026-09-08 11:20, after the eight new couplings were scored)

The analysis above was run as specified. Nothing in the plan was changed after
seeing the data; the one deviation is noted at the end.

### Primary endpoint `Z`, paired over all 15 couplings

| comparison | wins | median ratio (bootstrap CI) | Wilcoxon p |
|---|---|---|---|
| `deployed` vs `wide2000` | **15/15** | 9.4x [6.9, 21.9] | 1e-4 |
| `deployed` vs `wide2000_dense` | **15/15** | 8.7x [7.6, 18.1] | 1e-4 |
| `wide2000` vs `wide2000_dense` | 6/15 | 0.9x [0.8, 1.2] | 0.80 |

### The pre-specified off-rung subgroup (the confirmatory sample)

| comparison | wins | median ratio | Wilcoxon p |
|---|---|---|---|
| `deployed` vs `wide2000` | **8/8** | 8.1x [4.6, 21.9] | 0.0078 |
| `deployed` vs `wide2000_dense` | **8/8** | 8.2x [6.8, 12.7] | 0.0078 |
| `wide2000` vs `wide2000_dense` | 4/8 | 0.9x [0.6, 1.5] | 0.95 |

`p = 0.0078` is the smallest value a two-sided signed-rank test can return at
n = 8 (2/2^8), so the test is SATURATED, not marginal -- it cannot report more
evidence than this at eight pairs.

Relative deviation agrees and is larger throughout (37-45x off-rung), so
nothing turns on the choice of normalisation here.

### Verdict against the pre-registered falsification criteria

Neither fired. The wide checkpoints beat `deployed`, and they beat it on the
off-rung subgroup specifically -- so this is not "wide only works where it was
trained".

**Coverage WIDTH is confirmed. Coverage DENSITY is not resolved in U(1)**
(0.9x, CI straddling 1 on every cut). U(1) supports width only; U(2) resolves
density separately over 44 couplings, and the two studies should be read as
agreeing on width and silent-versus-positive on density.

### The secondary binary endpoint, for the record

`deployed` "resolves" at 8/15 against `wide2000`'s 3/15 -- the checkpoint
whose seeds sit 59-78 sigma from exact scores nearly three times as many
"successes" as the one whose seeds sit at 1-32 sigma. That is the inversion
this pre-registration was written to escape, displayed rather than hidden.

### Deviation from plan

The shared script `84_raw_seed_quality.py` had labelled PPM as primary,
inherited from the U(2) work. This document fixes `Z` as primary, and `Z` is
what is reported as primary above. The script now prints both, always, with
`Z` labelled as the pre-registered primary, so the choice cannot be made
after seeing the numbers. Both point the same way in this test.

### What this changed downstream

Re-scoring both theories on this endpoint changed three claims that had been
resting on the inverted indicator, all now corrected in `paper/current.tex`:

- The **abstract** claimed checkpoints were "indistinguishable at 32x32 and
  separate decisively at 64x64". That pattern is an artifact of the finite-tau
  column. On seed distance the ordering is the same at both volumes and
  separates 4-10x at L=32 already; what actually grows with volume is the
  MAGNITUDE (wide vs default 1.6x at L=32, 3.2x at L=64).
- The **U(2) density paragraph** concluded "density was not the missing
  ingredient". On this endpoint `wide_dense` beats `wide` at 35/44 (2.0x,
  p<1e-4), concentrated entirely inside coverage (27/30) and absent past the
  ceiling (8/14, p=0.36). Range and density act in different places.
- The **coverage-empty-rung mechanism** argued a regression from `wide`
  resolving a finite tau while `wide_dense` did not. The regression is real --
  Z 0.45/0.39 against 6.31/5.96 at that coupling -- so the conclusion stood,
  but the evidence needed replacing.

The sector-augmentation intervention null was also re-scored and HOLDS:
U(2) median ratio 1.0x (p=0.27, n=44), U(1) 0.9x with the marginal signal
pointing away from the intervention (n=7).
