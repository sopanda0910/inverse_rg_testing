# u2 validation of record

**This directory carries tau_int-AWARE error bars, and it replaced the naive-SEM
version on 2026-08-22.** The superseded run is kept verbatim at
`../validation_naive_superseded/`.

## Why the change

The naive `sigma / sqrt(N)` assumes the configurations are independent draws.
They are not: a ladder ensemble comes from a fixed number of HMC chains and
inherits whatever correlation its coarse input carried. The naive SEM is
therefore too small and every `|z|` built on it is too large. u1 made the same
correction as NARRATIVE 25.7 / M4; `u2_2d/validate/stats.py` is the port.

The correction is real but modest -- `mean |z|` moved 0.522 -> 0.484 at L = 32
and 0.789 -> 0.728 at L = 64 against the closed form, a 7-8% effect. It is not
the explanation for the scorecards sitting below the half-normal null; see
below.

## How to read `mean_wilson_z`

`|z|` is half-normal when the model is exactly right AND the error bars are
correct, so the value to compare against is **`sqrt(2/pi) = 0.798`**, not zero.
A score far below the null is evidence about the error bars or about
correlations between observables, not evidence of a good model.

The resolution of that mean is `sqrt(1 - 2/pi) / sqrt(N_eff)` where `N_eff` is
the participation ratio of the observables' correlation matrix -- recorded in
`summary.json` as `n_effective`, and NOT the row count:

| L | rows | N_eff (all) | N_eff (extended, area >= 16) | mean \|z\| vs reference | sigma from null |
|---|---|---|---|---|---|
| 32 | 41 | 3.73 | **1.45** | 0.762 | +0.12 |
| 64 | 41 | 3.24 | **1.27** | 0.528 | +0.80 |

Both volumes sit essentially ON the null once `N_eff` is used. Note the second
column especially: the thirteen extended Wilson loops are worth **about one and
a half independent observables**, so an extended-loop `mean |z|` has a standard
error near 0.50 and differences of a tenth between checkpoints are noise. That
is the correct reading of the challenger comparisons in
`../challenger_report*.md`.

## Provenance

* `summary.json`, `report_L*.md` -- `04_validate.py --config u2_2d/configs/default.yaml`
  with `--generated-n-chains`, against `out/u2_2d/ladder`.
  NOTE `04_validate.py --config` defaults to **smoke.yaml**; forgetting the flag
  silently validates the L = 16 smoke rung and reports it as the ladder.
* `n_effective`, `n_effective_extended` -- back-filled by
  `47_effective_observables.py`. `validate.report.compare` now records them
  directly, so future runs need no back-fill.
* `wilson_distributions*.json` -- **carried over from the superseded run.** They
  hold raw per-configuration values and the HMC reference from that run; the
  error model does not touch either, but they were not regenerated here.
* `_orphaned/` -- an L = 16 report from a run that used the smoke config; not
  part of the ladder of record.
