# `out/u2_2d/data_random` — u2 `random_rungs` coverage data

Generated 2026-09-03/04 on a 2018 Mac Mini (Intel i5-8500B, 6 cores, 8 GB,
CPU-only) per `docs/MAC_MINI_TASKS.md` task 1. 102 ensembles, 128 configs each,
`[N, 2, L, L, 5]` CPU tensors: 60 x L16 + 36 x L32 + 6 x L8, beta 4.05 to 407.3.

Config: `u2_2d/configs/random_rungs_gen.yaml`. Its `random_rungs` block is
byte-identical to `default.yaml`'s, and its `data:` block now matches
`default.yaml`'s in every key.

## One deviation from the task doc, and it was required

The doc's sketch of the config listed four `data:` keys; `default.yaml`'s block
has SEVEN. Omitting the other three does not inherit them from `default.yaml`,
it falls back to the SCRIPT defaults, and `winding_interval` defaults to **1**,
not 5 — so the marginal odd winding move (25 conditional SU(2) sweeps) fires on
every trajectory instead of every fifth. `default.yaml`'s own comment already
measured that as 7.6x more expensive for no benefit. Confirmed here: the one
rung generated before the omission was caught (L16, beta 7.5726) took 980 s;
regenerated at interval 5 it took 138 s, a 7.1x ratio. That rung was DELETED and
regenerated so all 102 share one recipe.

`seed_exact_sectors` and `thermalize_sweeps` were also added but are inert for
random rungs — `utils.expand_rungs` writes both into every random rung itself
(False and 60) and the per-rung value wins in stage 01.

## Verification: `63_widening_test_data_check.py --data-dir out/u2_2d/data_random`

All 102 rungs, chain-resampling bootstrap, against the closed forms in
`u2_2d.lgt.exact`. Full output: `artifacts/data_random_check.txt`.

    plaquette z : mean -0.06  sd 0.88  max |z| 2.62   |z|>2: 5 (chance 4.6)   |z|>3: 0
    <Q^2>     z : |z|>2: 6 (chance 4.6)   |z|>3: 1

The plaquette column is a clean null at every coupling. ONE rung is flagged.

### The flagged rung: L=8, beta=13.0449, <Q^2> z = -4.27 — DIAGNOSED BENIGN

Measured <Q^2> 0.4531 +- 0.0350 against exact 0.6024. The flag is an
UNDERESTIMATED ERROR BAR, not a bad ensemble:

* Its error bar is 0.0350 while its neighbour at beta=12.5129 — essentially the
  same coupling, exact <Q^2> 0.6353 vs 0.6024 — reports 0.1147, 3.3x larger. A
  collapsed chain-to-chain spread shrinks the bootstrap error and inflates z.
* Two INDEPENDENT high-statistics runs at the same coupling (128 chains x 2048
  configs, burn_in 1200, same marginal move) bracket the closed form:
  hot start 0.5566 +- 0.0242 (z = -1.89), cold start 0.5898 +- 0.0295
  (z = -0.43). The coupling samples correctly and the closed form is right.
* Scaling those errors back to this rung's 16x-smaller statistics gives a true
  SEM near 0.10 — matching the neighbour — at which the deviation is z ~ -1.5.

The other five L=8 rungs are clean (z = -0.34, +1.71, +1.52, +0.14, -0.02).
Shipping as-is; recorded here rather than silently passed.

## Environment note (does not travel with the data)

PyTorch's last x86-64 macOS wheel is 2.2.2, built against the NumPy 1.x C API,
so NumPy is pinned to 1.26.4 on that machine and a venv-local `sitecustomize.py`
aliases `np.trapezoid` (NumPy 2 spelling, used in 21 places here) to `np.trapz`.
Repo code was not modified. Irrelevant on the Windows machine.
