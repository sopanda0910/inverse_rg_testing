# CLAUDE.md

Project conventions for AI coding agents (Claude, Codex, etc.) working on InverseRG.

## Project Overview

Diffusion-based inverse renormalization group for lattice field theories.
A score-based diffusion model lifts coarse configurations to fine
configurations so that gauge-invariant observable distributions match direct
HMC; iterating up a matched beta ladder reaches lattice sizes/couplings where
direct HMC suffers from critical slowing down and topological freezing.

Three sibling packages, one per theory. `u2_2d/` is the ACTIVE one; `u1_2d/` is
closed and `su2_2d/` is set aside.

- `u1_2d/` — 2D compact U(1). **REOPENED 2026-08-20** (it was closed/frozen from
  2026-08-02, and much of what follows was written under that assumption). It is
  the paper being written first, with `u2_2d` as its extension, and the claim
  the paper makes is that **a diffusion-model configuration is a better HMC
  starting seed**. New U(1) work is in scope again — `scripts/58_seed_sampler_grid.py`
  is the 2x3 seed/sampler grid added under the reopening. The body of the study —
  campaign, ESS/exactness program, matching-residual decomposition,
  AIS transport, L=64 head-to-head — is finished and documented. Results in
  `out/u1_2d/paper_appendix/appendix.md`, full story in `docs/u1_2d/NARRATIVE.md`,
  audit in `docs/u1_2d/V2_AUDIT.md`. Treat settled results as settled; bug-parity
  fixes only. **Post-closure corrections (2026-08-14/15) are in
  `docs/u1_2d/NARRATIVE.md` §25.5** — read it before quoting Tables S1, S3, S4, S6b
  or S7b, all of which carried numbers from superseded runs, and before
  quoting the exact-P(Q) crutch (§21.6, `PHYSICS_WALKTHROUGH.md` F1).
  **The two owed referee experiments were run 2026-08-15 and are in §25.6**
  (Tables S8–S10): the classical-remedy benchmark, the Zhu et al. head-to-head,
  and the MALA-exactness test. **§25.7 closes the `U1_2D_REVIEW.md` backlog**
  (M3, M4, `norm_type`, validation σ-bias, the citation audit in §26.1, and the
  `topo_weight` follow-up). Two consequences to know before quoting anything:
  Table S3 is regenerated on τ_int-aware records with a denominator of **38,
  not 35** — the three deep-frozen cases were never untestable, the χ² gate was
  silently dropping them — and the `TODO.md` §2 recommendation to adopt
  `topo_weight = 0.3` is **withdrawn**, since it does not move the raw sector
  match rate it would have to act through.
- `u2_2d/` — 2D U(2). **ACTIVE (opened 2026-08-19).** The successor study, and
  the reason it was chosen: 2D U(2) is exactly solvable, and its topology is
  carried entirely by the determinant, which is an honest compact U(1) field —
  so the closed U(1) machinery is reused rather than rewritten, while the group
  is genuinely non-abelian. Links are stored in the NTHMC-compatible split
  representation `U = e^{i phi} q` as `[..., 5]` = `(phi, q0, q1, q2, q3)`.
  Read `u2_2d/README.md` first, then `docs/u2_2d/DESIGN.md` for the
  derivations and the measured results. The design, and the three facts that
  carry it:

  * `psi = wrap(2 phi) = arg det U` is a compact U(1) gauge field, and
    `lgt.lattice.det_links` hands it back in exactly the `[B, 2, L, L]` layout
    every `u1_2d.lgt` routine consumes. **Q is a functional of psi alone.**
    Because det is a homomorphism, the plaquette determinant phase is the plain
    SUM of link phases, so the abelian telescope of `u1_2d` survives verbatim:
    the coarse determinant plaquette is the wrapped sum of the four fine ones,
    exactly, non-abelian group notwithstanding. Sector transport across an
    inverse-RG step is therefore an identity, as in U(1).
  * One inverse-RG step factorizes as `p(psi, q) = p(psi) p(q | psi)`. The model
    generates `psi` only. The SU(2) sector needs no model: at frozen `phi` the
    U(2) local weight is exactly `exp(beta k . q)`, so
    `lgt.local_updates.conditional_su2_sweeps` is an EXACT sampler for
    `p(q | psi)` and leaves `psi` and `Q` bit-for-bit unchanged. Naive inverse
    blocking of the coarse SU(2) part is only the seed; it cannot bias anything.
  * **The joint does NOT factorize** — `(1/2)ReTr P = cos(omega_p) cos(phi_p)` is
    a product, not a sum. Generating the two sectors independently and combining
    them is wrong at O(phi^2 omega^2). Two consequences, both already handled:
    the SU(2) sector must be generated CONDITIONALLY (it is), and `psi`'s own
    marginal is NOT U(1) Wilson at `beta/4`. Integrating SU(2) out of a plaquette
    gives the exact marginal weight `w_det(alpha) = 2 I_1(z)/z`,
    `z = beta cos(alpha/2)` (`lgt.actions.DetSectorAction`), which is Wilson at
    `beta/4` plus a `(3/2) log cos(alpha/2)` measure term. Anything that needs an
    analytic U(1) coupling must call `lgt.exact.matched_u1_beta` (the minimum-KL
    projection), NOT `beta/4`: they differ by 23% at beta = 4 and 0.003% at
    beta = 220.

  **The U(2)-specific result, measured — do not re-derive it.** `U(2) =
  (U(1) x SU(2)) / Z_2`, so `Q` even <=> the ordered product of SU(2) plaquettes
  is +1 and `Q` odd <=> it is -1. An EVEN change of Q is free (the U(1) instanton
  added to `phi`, purely central, `dS = O(beta/V)` — that is
  `central_winding_field`, and `winding_update` defaults to `charge_step=2`). An
  ODD change cannot leave SU(2) alone and no fixed shift field does it cheaply:
  halving the U(1) instanton leaves one plaquette with a spurious -1 at cost
  `2 beta` (dS = 37 at beta = 20, L = 8), and the `U(1)_T` subgroup construction
  costs O(beta L) instead (dS = 110); gauge fixing does not help. The GENERATIVE
  route is unaffected and this is the point: setting `psi` sets `Q`, and the exact
  conditional SU(2) sampler relaxes the monodromy for free (dS = 26-149 after
  `set_topological_charge`, back to ~5 after 25 conditional sweeps). The
  diffusion ladder reaches odd sectors where the classical global move cannot.

  Exactly solvable, and implemented: `lgt.exact` has the U(2) character expansion
  on the torus, `Z = sum_{j,k} (c_{j,k}/d_j)^V` over irreps `(j, k)` with
  `k = 2j (mod 2)` — verified against Weyl integration to 1e-10 — the exact area
  law `<(1/2)ReTr W(A)> = r_fund^A`, and the determinant-sector `P(Q)`, which
  matches heatbath to 1-2% in every sector at beta = 2, 5, 8. Tree-level ladder
  relation `beta_c = beta_f / 4` in all four u(2) directions.

  **TWO FREEZING MECHANISMS, NOT ONE — measured 2026-08-19, and the single most
  useful U(2) fact.** The two winding moves have different controlling parameters
  and only one is protected by the ladder:
  * EVEN dQ (central instanton) costs `2 pi^2 beta / V`, so it is governed by
    `beta / V` — which the matched ladder holds nearly CONSTANT (0.219 -> 0.202 ->
    0.198 -> 0.197 across L = 8..64). Even-charge mobility is a ladder invariant
    and never degrades.
  * ODD dQ must cross the Z_2 monodromy. **Its controlling parameter is `beta`,
    NOT `beta L` — corrected 2026-08-20, and the earlier `beta L` claim here was
    wrong.** `scripts/15_base_parity.py` counts PARITY FLIPS directly instead of
    inferring mobility from a verdict, and they collapse on `beta` at both volumes:
    L=8 gives 12810 / 7100 / 347 / 4 flips at beta = 6 / 10 / 14 / 20, and L=16
    gives 2453 / 2 / 0 at beta = 14 / 21 / 28. Under `beta L` that does not
    collapse at all — L=16 at `beta L` = 224 flips 2453 times while L=8 at
    `beta L` = 160 flips four. Odd mobility dies between **beta = 14 and beta = 20
    at every volume tested**, with the per-site rate falling ~100x across it.
    **All of those flip counts are for the JOINT proposal and are SUPERSEDED as a
    statement about the theory (2026-08-20).** They measure how badly that
    proposal was priced, not where odd charge becomes unreachable. Under the
    marginal move there is no death at all in the range tested: acceptance is
    0.339 at L=8/beta=20, 0.602 at L=16/beta=28 and 0.599 at L=64/beta=416.5,
    with correct P(odd) from a COLD start in every case. Quote these numbers only
    to explain why the old proposal failed.
    **The head-to-head at MATCHED protocol was run 2026-08-21 and settles it.**
    L = 16, hot start, 256 chains, 2000 trajectories, the same script and seed,
    only `--charge-step` differing (`out/u2_2d/base_parity_v2{,_marginal}/`):

    | beta | joint flips | MARGINAL flips | joint tau(Q^2) | marginal tau(Q^2) |
    |---|---|---|---|---|
    | 14 | 4919 | 72522 | 0.55 | 2.73 |
    | 21 | 13 | 67298 | 0.53 | 2.37 |
    | 28 | 0 | 61403 | 0.55 | 1.98 |

    The marginal rate is FLAT across the whole range the joint proposal dies in
    — it falls 15% while the joint falls to zero — and odd fraction is correct at
    every point (z = -0.50 / +0.41 / -1.65 against exact 0.5000 / 0.4989 /
    0.4928). There is no odd-charge mobility edge at L = 16 below beta = 28.
    **And note which way tau_int(Q^2) points: the BROKEN sampler looks 4x
    better.** The joint move shuffles Q by +-2 quickly inside one parity class,
    so Q^2 decorrelates in 0.55 draws while the chain never crosses the
    monodromy at all; the marginal move's 1.98-2.73 is the honest cost of
    sampling the parity degree of freedom too. So tau_int(Q^2) joins
    sector-change counts on the list of diagnostics that report HEALTHY on a
    parity-frozen chain — do not use it as an ergodicity test either.
  Consequence: the ordinary freezing diagnostic ("does the chain change sector?")
  reports HEALTHY in a regime where P(Q) is 20% wrong, because even moves keep
  firing while the odd/even balance is stuck. Do NOT conclude a coupling is ergodic
  from sector-change counts. But do NOT use `07_pq_sampling.py`'s `PARITY-STUCK`
  verdict as the mobility test either: it is a hypothesis test on ONE binomial draw
  of the odd weight and it passes on luck. It calls L=16, beta=28 SAMPLED, and that
  coupling has **zero** parity flips in 256 chains over 2000 trajectories. Count
  flips (stage 15) to establish mobility; use stage 07 to test the resulting
  distribution. The superseded boundary quoted here — `beta L ~ 450 SAMPLED, ~830
  PARITY-STUCK` — was fitted to the L=16 verdicts alone and the L=8 points
  contradict it.
  Separately, a thermalization boundary at `beta / V ~ 0.25`: at beta = 20, L = 8 a
  hot start cannot relax DOWN (17% of chains stranded, <Q^2> 63% high) and a cold
  start cannot climb UP. beta = 14 at L = 8 is inside the window in both directions.

  **THE MARGINAL ODD MOVE IS CORRECT AT ITS DEPLOYED SETTING -- verified
  2026-08-21, `scripts/34_marginal_move_bias.py`.** A first pass had it ~1% LOW
  in the odd weight at all four L=8 couplings (odd/exact 0.9909 / 0.9897 / 0.9870
  / 0.9923), which looked like a systematic. It was not; it was 128 chains x 150
  draws of noise. At 128 x 1280:

  | beta | SU(2) sweeps after an accepted move | odd/exact | z |
  |---|---|---|---|
  | 10 | 5 | 0.99386 | -2.40 |
  | 10 | **25 (deployed)** | 1.00065 | **+0.26** |
  | 10 | 100 | 0.99756 | -1.07 |
  | 14 | 5 | 1.00251 | +0.96 |
  | 14 | **25 (deployed)** | 1.00411 | **+1.46** |
  | 14 | 100 | 0.99994 | -0.02 |

  **Read the whole table, not the beta=10 column.** An intermediate write-up here
  claimed the 5-sweep row demonstrated the mechanism -- `n_su2_sweeps` is the
  move's ONE approximation (see the `marginal_winding_update` docstring), the
  resample runs only on ACCEPTED configurations, so at finite sweeps it should
  penalise exactly the moves that flip parity. The completed scan does NOT
  support that: beta=14 at 5 sweeps is +0.96, not negative, so ONE cell of six
  sits at -2.4 sigma and the rest are within 1.5, which is unremarkable across
  six cells. The defensible conclusion is the narrow one -- **no detectable bias
  at the deployed setting, and none at 100 sweeps either** -- not a demonstrated
  sweep-count effect. `BatchedHMCU2` now exposes `winding_su2_sweeps` so the
  question is scannable rather than hardcoded if it is ever reopened.

  **The closed form is not the suspect for any P(Q) disagreement -- it is
  numerically converged.** `det_topological_charge_distribution` does a trapezoid
  k-integral against `cos(2 pi k q)` on ~600 points, about 20 per oscillation at
  the largest sector, which is where a sub-percent parity-structured error would
  live. Recomputed with a 16x finer k grid, 4x wider k cut, 4x finer alpha grid
  and 4x more sectors, <Q^2> and P(odd) move by less than 1e-6 relative at every
  coupling from L=8 beta=6 to L=16 beta=56. Do not re-audit it.

  **`07_pq_sampling.py`'s STATISTICS WERE REBUILT ON 2026-08-22 AND ITS VERDICT
  WAS NOT CALIBRATED BEFORE THAT. Every verdict in this file predating that date
  is unreliable in BOTH directions.** Three defects, found in sequence:

  * `odd_z` summed per-sector bootstrap errors in QUADRATURE. Those cells are
    multinomial and hence negatively correlated, so the sum overstates the error
    and shrank every |odd_z|. Now bootstrapped directly from the parity
    indicator over CHAINS, as `34_marginal_move_bias.py` does.
  * The agreement test, `chi2 = sum_q z_q^2` against `2 * n_sectors`, was never
    a chi-squared of anything: correlated cells, the wrong per-cell variance
    (`sqrt(p(1-p)/n)` where Pearson wants `sqrt(p/n)`, inflating each term by
    `1/(1-p)`), `n_sectors` instead of `k-1`, and tail bins with expected counts
    of a few. Replaced by `sector_goodness_of_fit`: a Mahalanobis statistic on
    the per-CHAIN sector-frequency vectors -- chains are independent replicas, so
    the multinomial correlation, the autocorrelation and the freezing all live
    inside a chain and the covariance is estimated from the chains themselves --
    with a BOOTSTRAPPED p-value and per-chain bin pooling (`p * n_draws >= 1`).
  * `PARITY-STUCK` was declared from `|odd_z| > 2`, a pure significance gate.

  **THE CALIBRATION IS THE RESULT, and it is worse than "miscalibrated"
  (`48_verdict_calibration.py`, which feeds the script synthetic histories drawn
  from the closed form so the null is true by construction; 300 replicas per
  cell at the real 256 x 300 shape).** On EXACT data the old verdict misfired
  13% of the time (DISAGREES 8%, PARITY-STUCK 5%). And on the `parity_frozen`
  arm -- every chain pinned to one parity forever, the exact pathology the
  verdict exists for -- `|odd_z| > 2` fired at **5%, its null rate**, because
  each chain's parity was drawn from the CORRECT weight so the pooled odd
  fraction came out right. The old rule had essentially NO POWER on the thing it
  was built to detect while firing on 13% of good data. After the rebuild:

  | arm | what it is | old | fixed |
  |---|---|---|---|
  | iid | true null | 87% SAMPLED | **99%** |
  | sticky | true null, autocorrelated | -- | 95-100% |
  | parity_frozen | the real pathology | ~5% caught | **100% caught** |

  **FINAL CALIBRATION, all 12 cells, 300 replicas each**
  (`out/u2_2d/verdict_calibration_v3/`), rejection at alpha = 0.01 and median
  goodness-of-fit p, against a target of 1% and 0.5:

  | beta | iid | sticky | parity_frozen caught | odd_bias power |
  |---|---|---|---|---|
  | 28 | 2% (p 0.527) | 1% (p 0.499) | **100%** | 22% |
  | 51.75 | 1% (p 0.493) | 1% (p 0.463) | **100%** | 19% |
  | 56 | 1% (p 0.507) | 0% (p 0.525) | **100%** | 15% |

  So the test is calibrated on true nulls at BOTH couplings and under
  autocorrelation, and has full power on the pathology. Note the last column
  before quoting any `odd_z`: at the 0.8% deviation actually observed the test
  fires only 15-22% of the time, so the +2.61 at beta = 28 is **neither
  dismissible nor established** -- it is a weak hint of a small real bias in the
  marginal move, and settling it needs ~5-10x the statistics at that one
  coupling. Recorded as open, not resolved.

  **THE RE-MEASURED VERDICTS: EVERY COUPLING TESTED SAMPLES TOPOLOGY HONESTLY,
  AT BOTH VOLUMES (2026-08-22, `pq_sampling_marginal_L{8,16}_v3/`).** Marginal
  move, `--charge-step 1 --winding-interval 5`, 256 x 300 draws at L = 16 and
  128 x 300 at L = 8:

  | L | beta | <Q^2> z | changes | parity flips | gof p | C-asym z | odd/exact | verdict |
  |---|---|---|---|---|---|---|---|---|
  | 16 | 28 | +0.45 | 45909 | 45909 | 0.353 | -0.48 | 1.0078 | SAMPLED |
  | 16 | 51.75 | +0.29 | 34152 | 34152 | 0.732 | -0.61 | 0.9948 | SAMPLED |
  | 16 | 56 | +0.55 | 32556 | 32556 | 0.022 | +1.66 | 1.0020 | SAMPLED |
  | 8 | 6 | -0.68 | 30368 | 19330 | 0.479 | -1.91 | 1.0056 | SAMPLED |
  | 8 | 10 | -0.99 | 22853 | 20333 | 0.661 | -0.07 | 0.9919 | SAMPLED |
  | 8 | 14 | +0.63 | 17924 | 17839 | 0.469 | +0.89 | 0.9978 | SAMPLED |
  | 8 | 20 | +0.20 | 12851 | 12851 | 0.866 | -0.39 | 1.0042 | SAMPLED |

  **So `beta = 51.75` and `56` at L = 16 are NOT PARITY-STUCK and the standing
  caveat against raising the ladder base is LIFTED** -- those couplings sample
  topology rather than having it installed, which is the stronger claim. Every
  sector change at L = 16 IS a parity flip, as it must be for a dQ = +-1 move.
  beta = 56 is confirmed at two independent seeds (p = 0.493 and 0.743).

  **A THIRD STATISTICS BUG WAS FOUND BY THAT CONFIRMATION SEED, and the lesson
  is the one worth carrying.** beta = 56 first returned gof p = 0.022 -- above
  the gate but lowest in the set. The independent seed returned **p = 0.0002,
  X^2 = 51.6**, with `<Q^2>` z = -0.09, odd/exact z = -0.21, and NO individual
  sector past 1.2 sigma. A DISAGREES with no disagreement in it. Cause: sector
  frequencies are multinomial and sum to a constant, so the all-ones direction
  carries essentially zero variance, and `pinv(rcond = 1e-10)` inverted it,
  dividing a tiny mean offset by a tinier variance. `sector_goodness_of_fit` now
  DROPS ONE BIN, which removes the redundancy exactly and has no tuning
  parameter (raising `rcond` to 1e-4 is equivalent but arbitrary). Same two
  datasets: X^2 = 3.46 and 1.97.
  Note what did NOT find it -- the pooled-tail rule was the obvious suspect and
  made no difference at all (< 0.01 in X^2). **An independent seed found it. A
  low-but-passing p-value is worth a second seed, not a footnote.**

  **A CHARGE-CONJUGATION TEST WAS ADDED AND IS THE SHARPEST ONE HERE.** The
  action is invariant under U -> U*, which sends Q -> -Q, so P(Q) is exactly even
  and `mean(sign Q)` must vanish -- a test needing NO closed form, so it cannot
  be blamed on the reference and it ports to any theory with a topological
  charge. All seven couplings scatter within +-2 with mixed signs, so there is no
  systematic C violation; it is what turned the beta = 56 goodness-of-fit flag
  into a specific, checkable statement.

  **AND THE CHARGE HISTORIES ARE NOW SAVED.** The statistics here changed twice
  in one day and each change cost hours of HMC to regenerate verdicts, because
  only summaries were ever written. `07` now writes the `[n_draws, n_chains]`
  arrays and takes `--reanalyse`, which recomputes every verdict from them with
  no HMC at all (verified to reproduce a live run exactly). A further change to
  these statistics costs seconds. `chain_bootstrap` also grew an EXACT fast path
  for the mean (resampling chain means is an algebraic identity at equal chain
  length) -- bit-identical, 96x faster, and what makes calibrating this
  affordable. Both are covered by `u2_2d/tests/test_pq_statistics.py`.

  **The ladder base is UNSEEDED, and the claim has to be stated in two halves
  (revised 2026-08-20).** `seed_exact_sectors` is off at L = 8 and at the L = 16
  base; the colder rungs stay seeded, which is safe because they are training data
  and validation references and topology is TRANSPORTED, not learned
  (`apply_coarse_charge` imposes Q). What the base genuinely samples is the sector
  shape WITHIN a parity class — 106823 Q changes per 1024 chains per 1200
  trajectories, tau_int(Q^2) = 0.55 draws, chi2/dof 1.53. What it does NOT sample is
  the parity weight itself: zero flips, ever. That weight is frozen in during the
  hot-start ordering, one independent draw per chain, and the proof is that the
  identical procedure from a COLD start gives odd fraction 0.0000 against a hot
  start's 0.4727 at the same coupling (exact 0.4928). At L = 8, beta = 20 — where
  the exact odd weight is 0.3335 rather than ~1/2 — the hot quench returns 0.5156,
  wrong by +55%, so the quench does not sample parity, it lands near 1/2.
  **The base is safe for a reason that must be quoted, not assumed:** exact P(odd)
  is within 1% of 1/2 whenever <Q^2> >~ 1, and the base has <Q^2> = 1.0012, so the
  frozen-in weight is right to ~0.007 absolute — 0.45 sigma at 1024 chains. A base
  with narrow P(Q) would fail this badly. If a fully mobile base is ever needed,
  L = 16 under the MARGINAL move is mobile at every coupling tested — 72522 flips
  at beta = 14, 61403 at beta = 28, odd z within 1.7 sigma throughout — so the
  base no longer has to rely on the frozen-in argument above if the move is
  switched. (`--charge-step 1 --winding-interval 5`.)
  beta = 51.75 and 56 at L = 16 were called NOT usable as a base — both
  PARITY-STUCK. **Treat that verdict as UNTESTED rather than as a fact
  (2026-08-21):** it was measured under the retired joint proposal, which is now
  known to score zero flips at couplings where the marginal move scores 61403,
  and `07_pq_sampling.py` has not been re-run under the marginal move.
  Do not raise the base coupling on the strength of the old verdict OR in defiance
  of it — re-run stage 07 with `--charge-step 1` first. Same for every other
  `PARITY-STUCK` label in this file.

  **The ladder schedule is TOPOLOGY-matched, not plaquette-matched.** Because
  transport is an identity, the base's P(Q) is what every rung inherits, and under
  plaquette matching the exact <Q^2> still drifts -6.9% from L=8 to L=64 — a
  systematic the ladder structurally cannot correct.
  `lgt.blocking.topology_matched_fine_beta` picks beta_f preserving exact <Q^2>
  instead. Note the trap: better statistics make that drift MORE visible, not less
  (moving the base to L=16/beta=28 tightens the error 3.7x and cuts the drift only
  2.5x, so the z-score gets worse). Removing the bias is the only fix that survives.

  **COST, measured 2026-08-19 — the ladder is NOT a speed-up.** At L = 64,
  beta = 416.524: HMC + winding delivers an independent configuration (for LOCAL
  observables) in 0.212 s, the ladder in 0.820 s including base generation, 0.481 s
  for the top rung alone — so the ladder is **3.87x SLOWER**. Do not lead with
  speed; the cost is dominated by the 200-step diffusion sampler, which is tunable
  and untuned. **The REACHABILITY claim that used to sit here is RETIRED
  (2026-08-20).** It read: the classical arm covers 0.507 of exact P(Q) with zero
  odd sectors "and cannot improve at any cost, because odd charge has probability
  zero in its stationary distribution". That was false — it was a property of the
  *joint* winding proposal, not of the theory. With the marginal odd move
  (`docs/INSTANTON.md`) a cold classical chain at the top rung reaches P(Q)
  coverage **1.000** with 4 odd sectors and <Q^2> = 0.973 against exact 1.001
  (stage 08 arm G, 2587 parity flips). Do not claim the classical arm cannot reach
  odd charge.
  What survives, and is the better claim because it is a cost statement rather
  than an impossibility one: arm G needs the EXPENSIVE odd move and 1100 s to get
  there, while the diffusion seed plus the CHEAP even move (arm E) is already at
  coverage 1.000 in 379 s with **zero parity flips** — every odd sector it
  occupies was inherited from the seed, not manufactured. Same endpoint, 2.9x less
  cost, and arm A shows the seed starts there with no winding moves at all.
  `scripts/13_cost_comparison.py`. **The "the sampler is untuned" hedge was tested
  (2026-08-20, `scripts/14_sampler_steps.py`) and it is REAL, worth about 3x:** at 25
  steps instead of 200 the top rung goes from 2.22x slower to 1.38x FASTER than
  hmc+winding, at ~2.7x the extended-loop error and no measurable change in local
  observables after retherm. Below 18 steps the lift collapses. The ladder of record
  stays at 200 because it is the accuracy measurement; a production run should use
  25. What does not move is the ~90 s fixed overhead per ladder pass (30 SU(2) +
  10 retherm sweeps) — that is the next knob, not the sampler.

  **The seed benchmark (`scripts/08_hmc_seed_benchmark.py`) is the headline.** At
  L = 64, beta = 416.524, 300 trajectories, four arms: the diffusion seed starts at
  relative plaquette error 8.2e-06 against a cold start's 4.8e-03, and does not
  move; the cold arms plateau at ~4e-05 after 300 trajectories, still 5x further
  from exact than the seed was at t = 0; a hot start never thermalizes at all (flat
  at 6e-02). **Do NOT quote the seed's t=0 error as a ratio.** With 64
  configurations the sampling floor on that number is ~7e-06, so 8.2e-06 IS the
  floor; an earlier run measured 7.8e-07 and a "6200x better" ratio was quoted off
  it, which was measuring noise. The defensible statement: the seed is at
  equilibrium to within the resolution the ensemble can offer, while a cold start
  is three orders of magnitude away. Sector coverage: seed 0.995 of exact P(Q) with
  3 odd sectors, cold 0.399 with 0, cold+winding 0.507 with 0. Read coverage WITH
  <Q^2> — the hot arm "covers" 1.000 while carrying <Q^2> = 109 against exact
  1.001.

  **Training needs COUPLING coverage, not lattice-size coverage.** The score net is
  fully convolutional and conditioned on `det_lift.model_beta` (the minimum-KL U(1)
  projection), not on L. A ladder rung needing model beta 104 against a training
  maximum of 50.8 produced a coherent negative bias in ALL ~24 observables at that
  rung (plaquette z = -1.86) while the interpolated rung was clean. Supply the
  coupling at a SMALLER L — the map is local, so it teaches the same thing for a
  quarter of the cost.
  **The beta scan (2026-08-21) turns that into a quantitative rule.**
  `scripts/28_crossover_scan.py` measures seed t_therm at 14 couplings, and it
  tracks DISTANCE TO THE NEAREST TRAINING RUNG in model beta, not beta itself.
  The deployed `det_score_net.pt` has rungs at model beta 0.6, 1.7, 3.6, 7.0,
  12.9, 14.0, 26.4, 50.8, 104.1. Against those: <= 4% from a rung gives seed
  t_therm 3-10 (beta_f = 414.9 sits 0% from the 104.1 rung and is the BEST point
  in the scan, t_therm 3); 16-21% away gives 51-59 (beta_f = 88.8 is model beta
  22.2, in the middle of the 14.0 -> 26.4 gap, and is the worst interpolated
  point); past the top rung the seed does not thermalize on ANY local observable
  (beta_f = 537 is model beta 134, +29%, t_therm inf). So a bad point in that
  scan is a COVERAGE hole, not a beta effect — check the gap before concluding
  anything about the method. NOTE the ceiling: no available checkpoint
  (incumbent, `_cov`, or v2) exceeds model beta 104.1, so beta_f >~ 460 at
  L = 32 is extrapolation for all of them, and `30_seed_quality_figure.py`
  hatches that region for exactly that reason.

  **THE BETA SCAN IS DONE (2026-08-21) AND SEED QUALITY TRACKS TRAINING
  COVERAGE, NOT BETA.** `scripts/28_crossover_scan.py` + `30_seed_quality_figure.py`
  (fig21): 14 couplings, beta_f = 10.9 to 1623, L_f = 32 lifted from L_c = 16,
  run TWICE over the same couplings with the same seed -- once with plain HMC in
  every arm and once with the marginal odd winding move in every arm, so cold and
  hot starts are PAIRED and the only difference is the move. Six arms total; the
  diffusion seed is never given a sampler the classical arms are denied.
  Spearman(gap to nearest training rung, seed t_therm) = **+0.62** over the ten
  in-coverage couplings, and the split is the result:

  | gap to nearest rung (model beta) | seed t_therm | median |
  |---|---|---|
  | <= 10% | 10, 4, 6, 3 | 5 |
  | >= 16% | 10, 51, 50 | 50 |
  | past the top rung (104.1) | inf, inf, inf, inf | never |

  The three couplings where the seed beats the decorrelation interval --
  beta_f = 44.0 (t_therm 0), 58.0 (4), 414.9 (3) -- are all within 15% of a rung,
  and 414.9 is 0.4% from one. The three worst (88.8, 127.6, 264.2) sit 16 / 21 /
  30% into gaps. **Do not report a bad point in that scan as a beta effect.**

  **BUT THE gap ~ 0 END OF THAT CORRELATION IS IN-SAMPLE, and the Spearman is
  anchored by it (found 2026-08-21, `scripts/36_transport_check.py` session).**
  `default.yaml` trains on TWELVE FIXED RUNGS and the top three are
  `L=32 beta=105.651`, `L=32 beta=416.524` and **`L=64 beta=416.524`**. The
  scan's best point, `32->64 at beta_f = 415.61`, lifts an L=32 coarse ensemble
  at beta = 105.423 to L=64 at beta = 415.61 -- so BOTH the coarse input and the
  fine target are training rungs, at the SAME volumes, 0.2% off in beta. It is
  the trained lift, not a 0.2% extrapolation of it. The L=32 analogue
  (beta_f = 414.90) is fine-side in-sample the same way. Of 15 couplings across
  both scans exactly ONE is fully in-sample and one more is fine-side; they must
  be MARKED and excluded from the correlation, not quoted as the headline.
  **The claim does not need them.** The seed thermalizes while BOTH classical
  arms are `inf` at beta_f = 58.03, 87.04, 127.55, 183.59 and 264.24 -- all
  out-of-sample, gaps +3.6% to +30% -- plus beta_f = 44.0 at t_therm 0 against a
  cold start's 90. Six out-of-sample wins carry the result; lead with those.

  **THE VOLUME SCAN IS DONE (2026-08-21) AND THERE IS A REAL VOLUME EFFECT AT
  FIXED COVERAGE.** `--fine-size 64` from L_c = 32, four couplings, both rounds
  (`out/u2_2d/crossover_L64/`). The coverage ORDERING transfers exactly -- best
  point stays best, past-the-top-rung stays dead -- but everything degrades:

  | model beta | gap | L=32 seed | L=64 seed |
  |---|---|---|---|
  | ~103.9 | -0.2% (IN-SAMPLE) | 3 | 6 |
  | ~45 | -9.6% / -11.6% | **6** | **inf** |
  | ~22 | -16% / -17.6% | 59 | 79 |
  | ~200 | past top rung | inf | inf |

  The model beta ~45 row is the one that matters: essentially the same coupling
  and the same coverage gap, one volume apart, t_therm 6 -> never. Coverage is
  NOT the only variable. Cold and hot are `inf` at all four L=64 couplings in
  BOTH rounds despite 810-4152 parity flips from the fully ergodic dQ=1 move --
  topological ergodicity does not buy local thermalization, now measured at two
  volumes.

  **TOPOLOGY TRANSPORT IS EXACT, MEASURED CONFIGURATION BY CONFIGURATION
  (2026-08-21, `scripts/36_transport_check.py`).** 100% of fine charges equal
  their coarse charge at coarse beta 23.62 and 105.244 -- not <Q^2> agreeing on
  average, every single configuration. This was asserted throughout and checked
  only on the BLOCKING map (`09_verify_identities.py`), never on the GENERATIVE
  path. It is the identity the whole framing rests on, so it now has a test.

  **THE BEST STATEMENT OF WHAT THE MODEL DOES, and it is not the t_therm one.**
  The deployed ladder base is at beta = 3.5, L = 8 (model beta 0.62), where HMC
  is fully ergodic in topology, and it is UNSEEDED. The ladder invariant makes
  exact <Q^2> ~ V/(4 pi^2 beta) a FIXED POINT of beta_f = 4 beta_c, L_f = 2 L_c,
  so the coarse P(Q) IS the fine theory's P(Q). Transport is exact. Therefore the
  pipeline delivers configurations at beta = 416 carrying a topological charge
  drawn from a distribution SAMPLED AT A COUPLING WHERE SAMPLING WORKS. HMC at
  beta = 416 cannot do that at any cost -- it is frozen, so it keeps whatever Q
  it started with. Lead with this; it is cleaner than any t_therm ratio and it
  does not depend on the contaminated point above.

  **`physics_blend_coef` IS A DEAD END -- do not reach for it again**
  (`scripts/35_physics_blend_probe.py`, 2026-08-21). It looked like the free fix
  for the coverage ceiling, since `det_sector_exact_score` is exact at ANY beta
  and has no training range. Measured on the raw lift at L = 32: at the on-rung
  control (beta_f = 414.9) the plaquette relative deviation goes +8.3e-05 at
  blend 0 to -9.9e-02 at blend 0.5, and at blend 1.0 it CORRUPTS TOPOLOGY
  outright, <Q^2> 0.219 -> 9.0 against an exact ~0.25. Every coupling degrades
  monotonically in the blend. The analytic score is the psi MARGINAL; the lift
  needs the CONDITIONAL p(psi_f | psi_c), and mixing the two does not survive.
  DENSITY and WIDTH fail differently and need different fixes: a density gap
  degrades the seed but leaves it finite and still far better than a cold start,
  and it is a CAPACITY problem (both coverage retrains regressed precision at
  fixed capacity, see below) rather than a data problem; past the top rung the
  failure is total, and no checkpoint we have exceeds model beta 104.1.

  Two limits the scan establishes for the paper:
  * The classical arms confirm the target regime. In the PLAIN round cold start
    is `inf` from beta_f = 58 upward and hot start from 44. In the WINDING round,
    with the fully ergodic dQ=1 move, cold and hot are STILL `inf` everywhere
    above beta_f = 127 -- topological ergodicity does not buy local
    thermalization, and they are separate failures.
  * The marginal winding move itself decays at the very top: parity flips fall
    5712 -> 3301 -> 515 -> 2 across beta_f = 10.9 -> 1623. The classical baseline
    does eventually die, just far later than the joint proposal did.

  **THE TRAINING DATA HAS A BOOTSTRAP CEILING, and it is the sharper limit.**
  Every training rung from model beta 12.9 upward carries `seed_exact_sectors:
  true` and `sector_augment: 0.5`; only the low rungs (<= 7.0) are honestly
  sampled. So the high-beta training data does not sample its own topology, it
  INSTALLS it from the exactly-known P(Q). This is sound HERE for a reason that
  must be quoted rather than assumed: the score net models `psi` only and Q is
  TRANSPORTED by `enforce_coarse_charge`, so what the data must be right about is
  the conditional local structure at fixed sector, which heatbath/overrelaxation
  equilibrates whether or not the chain can tunnel. Freezing is a global
  pathology; the learned object is local. Two things this does NOT rescue:
  (i) the exact-sector crutch exists because 2D U(2) is solvable -- but see the
  correction immediately below, which is much less pessimistic than the version
  of this sentence that stood until 2026-08-21; (ii) local
  equilibration at high beta is not free either (cold starts fail to thermalize
  LOCALLY within 200 trajectories from beta_f = 537 up), so a rung at model
  beta 200 is expensive even with sectors installed. The natural escape is to
  bootstrap -- train rung n+1 on rung n's lifted output instead of on HMC -- which
  the pipeline does not do (the net trains once on fixed HMC rungs) and which
  risks compounding error up the ladder. Settle the capacity experiment first;
  bootstrapping onto a capacity-limited net compounds the wrong thing.

  **THE EXACT-P(Q) DEPENDENCY IS WEAKER THAN THIS FILE CLAIMED (2026-08-21).**
  Read `lgt/sector_seed.py`: the closed form enters at exactly ONE point, the
  first of three steps --

      Q ~ P(Q) exact  ->  set_topological_charge (deterministic)
                      ->  conditional_su2_sweeps (exact sampler for p(q | psi))

  -- and all it does there is choose the sector FREQUENCIES of the TRAINING data.
  At deployment those frequencies are overridden: Q is imposed by
  `enforce_coarse_charge` from the coarse ensemble, so what the net needs from
  its training data is sector COVERAGE (has it seen configurations at Q != 0),
  not correct sector weights. Coverage needs no closed form -- charges can be
  imposed by any means. So the honest statement is that the exact P(Q) is a
  CONVENIENCE for building training data and a REQUIREMENT for validation, not a
  requirement of the method, and the "closes in 4D SU(3)" claim was too strong.
  **This is testable and not yet tested:** retrain with a deliberately WRONG
  sector distribution (uniform over the same range instead of exact P(Q)) and see
  whether lift quality moves. If it does not, the exactly-solvable dependency is
  gone from the method and survives only in the scoring. Queue it behind the
  capacity experiment.

  **THE DIVISION OF LABOUR IS A REQUIREMENT, NOT AN OBSERVATION — measured in
  BOTH studies, 2026-08-21.** `u1_2d/scripts/59_pre_post_retherm.py` scores the
  lift at every scale BEFORE and AFTER the rethermalization tail, cumulatively on
  the same configurations. The repair factor (|relative deviation raw| / |after
  10 sweeps|) at u1 beta_f = 55.02, L = 32 is MONOTONE in loop size:

  | Q | W(1x1) | W(2x2) | W(4x4) | W(6x6) | W(8x8) |
  |---|---|---|---|---|---|
  | 0 (cannot move it) | 64x | 14x | 3.9x | 1.6x | **0.99x** |

  Local rethermalization is a LOW-PASS repair and it reaches exactly 1.0 at
  W(8x8) — ten sweeps do nothing at all for the largest loop — while Q is at
  zero by construction, since retherm runs `topological_updates=False`. So the
  accuracy demanded of the model is SCALE-DEPENDENT and strictest where nothing
  downstream can help: it may be wrong in the ultraviolet (repaired 64x), must be
  accurate in the infrared (repaired 1.0x), and must be EXACT in topology — which
  is why Q is TRANSPORTED rather than generated, a requirement rather than a
  convenience. The model meets the obligation: after ten sweeps W(8x8) sits at
  +1.54 sigma (beta_f = 55) and +0.14 sigma (beta_f = 218).
  The residual REVERSES across the tail — z falls with loop area before it
  (+34.61 -> +1.42) and grows with loop area after it (+0.53 -> +1.54) — which is
  the measured cause of u1's Fig. 38, previously asserted.
  Do NOT state this as "rethermalization damages the infrared": that happens only
  at the much stiffer u2 coupling (beta = 416.5, W(8x8) 4x worse). In u1 the
  factor merely reaches 1.

  **THE SAME SEM AUDIT APPLIED TO u1 (2026-08-21) -- u1 SURVIVES BETTER, BUT
  NOT ENTIRELY.** `59_pre_post_retherm.py` already records `z`, `relative_sem`,
  `relative_sigma_1config` and `n_star`, so unlike u2's `31` it can be checked
  without re-running. At beta_f = 55.02, L = 32, 256 configurations the raw z is
  29.33 / 8.07 / 3.64 / 2.04 / **1.17** at W(1x1) / W(2x2) / W(4x4) / W(6x6) /
  W(8x8). So the monotone low-pass trend (repair factors 64x / 14x / 3.9x / 1.6x)
  IS on resolved numbers -- **the u1 mechanism claim stands where the u2 one was
  retracted** -- but the HEADLINE ENDPOINT does not: "ten sweeps do nothing at
  all for the largest loop", factor 0.99x, rests on a raw z of 1.17, which is
  not resolved at 256 configurations. Quote the trend, mark the W(8x8) entry as
  unresolved, and do not use it as the punchline.
  At beta_f = 218.58 every RAW value is resolved (z = -256 to -34) but every
  POST-retherm z is <= 0.41, so those repair factors (up to 256094x) are LOWER
  BOUNDS, not measurements -- the denominator is consistent with zero.
  Test parity between the two studies is tracked in `docs/PARITY_U1_U2.md`,
  which also lists the audit obligations that now apply to both.

  **AND A CAVEAT ON u1'S GENERALIZATION CLAIM, found the same way.** At
  beta_f = 218.58, one of u1's own "validated far outside the training range"
  cases, the RAW lift is 257 sigma off on the plaquette and 8.7% off at W(8x8);
  ten sweeps bring it to 0.17 sigma, repair factors 1e3-1e5. Outside the training
  range the validation is largely validating the HMC TAIL, not the model. u1's
  claim is about the delivered pipeline and stays true as stated, but "the model
  generalizes far outside its training range" and "the pipeline's output agrees
  far outside its training range" are different sentences and only the second is
  measured. Consistent with the u2 beta scan, where the raw lift also collapses
  past the top training rung.
  Caveat on the numbers themselves: those z use a NAIVE across-configuration SEM
  while u1's convention is tau_int-aware error bars (NARRATIVE 25.7 / M4), so with
  256 configurations from 16 chains they are inflated and must be recomputed
  before they go in a figure. `N*` is unaffected — it uses the single-configuration
  sigma.

  **THE SCALE DECOMPOSITION — a DISCUSSION point for the paper, and it changes
  no number of record.** `scripts/31_division_of_labour.py` (fig22), at L = 64,
  beta = 416.524, 256 configurations, cold-start UNSEEDED classical arms.
  **z stays the presentation of record everywhere** (fig18, fig20, the
  validation tables): large Wilson loops genuinely fluctuate more per
  configuration, so the same absolute error legitimately shows as less
  significant on them, and z is the statistic that says so. Panel (a) is z,
  unchanged. What follows is reported alongside it, not instead of it.

  |z| by scale — W(1x1) / W(2x2) / W(4x4) / W(8x8) / <Q^2>:
  seed PRE-retherm 17.54 / 3.14 / 0.46 / 0.32 / 0.52; seed POST 10 retherm
  sweeps 0.40 / 0.10 / 0.49 / 1.37 / 0.52; plain HMC after 400 trajectories
  13.53 / 9.36 / 6.45 / 4.74 / inf. No classical arm reaches |z| <= 2 at ANY
  scale, including the fully ergodic dQ=1 one.

  Three things the z table alone does not show. **Do not build a mechanism on
  the z shape without checking the numerator — that error was made here once.**
  * The fall with loop size is NOT special to the seed. `z = sqrt(N) bias/sigma`
    and sqrt(N) is common to every observable, so the z SHAPE is the shape of the
    N-independent ratio bias/sigma — the shape is real. But the frozen classical
    chain, with no model in it at all, falls 2.9x across the same axis; the seed
    falls 55x. **The EXCESS over the classical baseline is the signal, not the
    fall itself.**
  * The model does NOT get better in the infrared. Its relative bias is FLAT in
    scale — 62 / 67 / 69 ppm at W(1x1) / W(2x2) / W(4x4) — while the theory's own
    per-configuration sigma grows 374x. The bar rises and the model's error does
    not. At the plaquette the seed is actually WORSE than a cold start (62 vs
    42 ppm). So the correct claim is "the model's systematic is scale-independent
    while a classical chain's grows", NOT "the model supplies the infrared".
    Topology is the one place the strong claim holds unconditionally, because Q
    is TRANSPORTED rather than modelled.
  * `N* = (sigma/bias)^2`, configurations usable before the model's systematic
    exceeds the user's own statistical error, is the N-independent practitioner's
    form. Seed PRE: 1 / 26 / 1221 / 2501. Frozen classical: 1 / 3 / 6 / 11. That
    ~200x is a statement about the method, not about the ensemble size.
    **CAVEAT, 2026-08-21: only the first two entries of each row are resolved.**
    N* SQUARES the bias, so where the bias is consistent with zero the N* is
    unbounded and means nothing -- at 256 configurations that is W(4x4) and
    everything larger (raw z = 0.6 / -0.3 / -0.8). Quote the W(1x1) and W(2x2)
    ratio, which is real; treat 1221 and 2501 as lower bounds at best. This is
    the same error that produced the retracted "actionable defect" below.

  **THE L=16 beta=28 <Q^2> DISCREPANCY DOES NOT REPRODUCE ON THE DEPLOYED
  ARTIFACTS (2026-08-22).** The standing open item was `<Q^2> = 0.9485 +- 0.0164`
  against exact 1.0012 (z = -3.22) from `07_pq_sampling.py`. Measured directly on
  the ensembles the pipeline actually uses, with binned errors:

  | artifact | n | <Q^2> | exact | z |
  |---|---|---|---|---|
  | base `data/u2_L16_beta28` | 4096 | 0.9668 +- 0.0253 | 1.0012 | **-1.36** |
  | `ladder_L32_beta105.651` | 1024 | 1.0156 +- 0.0448 | 1.0012 | **+0.32** |
  | `ladder_L64_beta416.524` | 1024 | 1.0156 +- 0.0448 | 1.0012 | **+0.32** |

  So the deployed base is 1.4 sigma low and the rungs are half a sigma high --
  nothing to explain. The stage-07 number came from a DIFFERENT, freshly
  generated ensemble and carried a quadrature-summed bootstrap error, which
  `34_marginal_move_bias.py` already established understates (multinomial cells
  are negatively correlated). **Re-run stage 07 with a direct bootstrap before
  treating this as open again**; do not quote z = -3.22.

  **AND THE LADDER'S SUBSAMPLE IS OPTIMAL, not degraded.** `03_run_ladder` takes
  the LAST 1024 of the base's 4096 -- verified by matching charges configuration
  by configuration. With 1024 chains and chain-major ordering that is draw 3 of
  4: every chain represented exactly once, and the most-thermalized draw. The
  subsample guard being inactive (no `n_chains` in the old metadata) therefore
  cost nothing here. Per-draw `<Q^2>` runs 0.891 (draw 0) to 1.016 (draw 3),
  which is ordinary sampling at SEM 0.045 and not a thermalization trend.

  **THE `mean |z|` ALARM WAS LARGELY AN ARTEFACT -- OBSERVABLES ARE NOT
  INDEPENDENT, N_eff = 3.77 NOT 41 (2026-08-22,
  `u2_2d.validate.stats.effective_observable_count`).** The correlation matrix
  of the 41 scored observables at L = 32 has top eigenvalue **18.6** (one mode
  carries 45% of the variance) and mean within-family |correlation| **0.62** --
  2D Wilson loops of different sizes are near-deterministic functions of one
  another. Participation ratio: **3.77 at L = 32, 3.25 at L = 64**. So
  `SE(mean |z|) = sqrt(1 - 2/pi)/sqrt(N_eff)` is **0.31**, not 0.09, and three
  claims made here were overstated by 3.3x:

  | claim | as quoted (N = 41) | at N_eff | verdict |
  |---|---|---|---|
  | validation L=32 mean\|z\| 0.484 | 3.3 sigma below null | **1.0** | unremarkable |
  | capacity ext loops 0.187 | 6.5 sigma | **2.0** | suggestive only |
  | sector ablation, 0.096 apart | excludes > 0.27 | **excludes only > 0.88** | weak bound |

  **So the earlier note here that a 0.187 scorecard "indicates overestimated
  error bars -- not a good model" was too strong.** It is 2 sigma. Never quote a
  `mean |z|` without `N_eff` beside it; `mean_abs_z_sigma(value, n_eff)` does it.

  **AND ON THE EXTENDED-LOOP SUBSET IT IS WORSE THAN THAT: N_eff = 1.45 AT
  L = 32, 1.27 AT L = 64** (measured 2026-08-22, `47_effective_observables.py`;
  `validate.report.compare` now records `n_effective` and
  `n_effective_extended` on every summary it writes, so this never has to be
  recomputed by hand again). The thirteen area >= 16 Wilson loops that criterion
  (c) of `25_challenger_report.py` averages are worth about ONE AND A HALF
  independent observables, so `SE(mean |z|)` on that column is **~0.50**, and the
  whole guard barely discriminates:

  | comparison | move | in SE | verdict |
  |---|---|---|---|
  | v2, L=32 | 0.168 -> 0.292 | **0.2** | unresolved |
  | v2, L=64 | 1.061 -> 1.225 | **0.3** | unresolved |
  | capacity, L=32 | 0.168 -> 0.666 | **1.0** | unresolved |
  | capacity, L=64 | 1.061 -> 0.319 | 1.4 | marginal |

  The declared 5% gate is LEFT AS IT WAS -- moving a criterion once the numbers
  are known is the failure that script exists to prevent -- but every row now
  prints its resolution, so a "FAIL" worth a fifth of a sigma cannot be quoted as
  a regression. **The capacity verdict is unaffected**: it never rested on this
  column, it rests on the tuned sweep count (5 -> 15/35) and the density gap.

  **tau_int-AWARE ERRORS ARE NOW IN u2, ARE THE VALIDATION OF RECORD, AND ARE
  *NOT* THE EXPLANATION.** `u2_2d/validate/stats.py` ports u1's estimator;
  `04_validate.py` takes `--generated-n-chains` and `03_run_ladder.py` now
  records `n_chains` in ladder metadata. Measured on the ladder of record:
  `mean |z|` 0.522 -> 0.484 (L = 32) and 0.789 -> 0.728 (L = 64) -- a 7-8%
  correction, real and worth keeping, but an order of magnitude too small to
  explain the sub-null scores.
  **PROMOTED 2026-08-22:** `out/u2_2d/validation/` now HOLDS the tau_int-aware
  numbers and the naive-SEM run is kept verbatim at
  `out/u2_2d/validation_naive_superseded/`. Both directories carry a README
  saying which is which; do not quote the superseded one. With `N_eff` applied
  the promoted scorecard sits essentially ON the half-normal null -- `mean |z|`
  vs reference 0.762 at L = 32 (+0.12 sigma) and 0.528 at L = 64 (+0.80 sigma) --
  so the "sub-null" alarm is closed at both volumes. Two traps
  found while wiring it: the estimator needs chain-major ordering
  (`index = draw*n_chains + chain`, which u2's `sample` satisfies) and silently
  returns a plausible ~0.5 otherwise; and **the deployed ensembles predate the
  `n_chains` metadata field, so `03_run_ladder`'s subsample guard has been
  inactive without saying so** -- it now warns instead.
  NOTE `04_validate.py --config` defaults to **smoke.yaml**, not default.yaml.
  Forgetting it silently validates the L = 16 smoke rung and reports it as if it
  were the ladder of record.

  **THE POST-RETHERM CREEP IN THE MULTI-LIFT RESULT WAS NOISE (2026-08-22).**
  At 4x the statistics it went the diagnostic way: u2 in-coverage post |z| went
  0.63 / 0.83 / **1.86** at n = 64 to 0.08 / 0.71 / **0.82** at n = 256, and u1
  ceiling 0.19 / 0.01 / **2.69** at n = 128 to 0.15 / 0.32 / **0.63** at n = 256.
  Since `z ~ sqrt(N)`, a real bias would have DOUBLED; it fell by half. So "no
  compounding" now holds for the DELIVERED product, not only the raw lift.
  Charge preservation reproduces at the higher statistics (u2 98.4 -> 97.7%,
  u1 81.2 -> 82.0%), so that effect is real.

  **u1's SAMPLER STEP COUNT IS *NOT* TOO HIGH -- 200 IS JUSTIFIED, AND THE
  EARLIER "10-20x TOO HIGH" NOTE HERE IS WITHDRAWN (corrected 2026-08-22 the
  same day it was written).** The first scan called
  `generate_fine_from_coarse` with the FUNCTION DEFAULTS, and those are not the
  deployed sampler: `v3_scale.yaml` runs `physics_blend_coef: 1.0`,
  `physics_blend_beta_min: 5.0`, and `03_run_ladder.py` rebuilds the noise
  schedule with `sigma_min_beta_coef: 0.1` before sampling, while the function
  default blends OFF. The blend and the step count interact, so an unblended
  scan cannot see the cost. `63_sampler_steps.py` now takes `--config` and
  reads every knob from it. **General lesson: a measurement of a tunable is
  only about the deployed system if it reads the deployed configuration.**

  Re-measured with the deployed knobs (`out/u1_2d/sampler_steps_deployed/`),
  worst-loop |z| against the closed form at beta_f = 55.02 / 218.58:

  | steps | raw | post | cost |
  |---|---|---|---|
  | 12 | 32.9 / 36.9 | 0.50 / 0.58 | 17x cheaper |
  | 18 | 16.0 / 19.7 | 0.44 / 0.52 | 11x cheaper |
  | 100 | 3.4 / 17.4 | 0.44 / 0.50 | 3x cheaper |
  | **200** | **1.0 / 4.3** | 0.43 / 0.50 | deployed |

  **THE TWO PRODUCTS WANT DIFFERENT SETTINGS AND THAT IS THE RESULT.** The post
  column is flat from 12 steps up, so the DELIVERED ensemble needs 18; the raw
  column is still falling at 100, so the SEED needs 200 -- and every
  seed-quality claim (t_therm, N*, the prolongator ablation) is measured on the
  raw lift. The script now prints both knees and calls neither "the" knee.
  Also note the raw column is now MONOTONE in step count, so the old claim that
  it was unusable because the bias changes sign was itself an artefact of the
  unblended sampler; at beta_f = 218.58 it still plateaus around 15-29 before
  dropping to 4.3 at 200, which is the coverage limit (3.6x past beta_max = 60)
  rather than a sampler effect.

  Verified end to end rather than argued: `u1_2d/configs/v3_scale_s18.yaml` runs
  the whole deployed ladder at 18 steps into `out/u1_2d/validation_s18/`. The
  delivered ensemble is indistinguishable from the record (max |z| 2.07 -> 1.42,
  1.74 -> 2.18, 1.28 -> 1.64 across the three rungs) while the raw lift degrades
  3-4x at every rung (12.3 -> 53.1 at the top). Sixteen retherm sweeps hide in
  the ensemble what the seed pays. That config is KEPT as the record of the
  negative result; `v3_scale.yaml` stays at 200.
  **u2's own 25-step finding was AUDITED for the same defect and is clean.**
  `14_sampler_steps.py` calls the real `generate_ladder` and reads every knob
  from `ladder_cfg` (including `physics_blend_coef`, which u2 deploys at 0.0
  anyway), and its schedule comes from the checkpoint via `load_det_model`. It
  also scales `charge_projection_interval` with the step count, which the u1
  script does not need. Its guidance -- read the RUNG 0 PRE-retherm column, not
  the top rung's plaquette -- is the same "score the raw product" rule this
  correction arrives at from the other direction.

  **SWEEPS BEAT TRAJECTORIES AS THE REPAIR MOVE, IN BOTH STUDIES (2026-08-22,
  u2 `44_sweeps_vs_trajectories.py`, u1 `61_sweeps_vs_trajectories.py`).** One
  lift, cloned, the same budget spent two ways, costs matched in LINK TOUCHES
  (retherm sweep = 3, trajectory = `n_steps`). u1: 6 / 12 / 24 touches to
  |z| <= 2 at beta_f = 55.02 / 98.47 / 218.58 against 380 / never-in-1500 /
  never-in-2220 for trajectories. u2: 6 touches at every coupling including
  +214% past the training ceiling, against never in 2560-4600. Cold-start
  trajectories never converge in any cell of either study. **This is a METHOD
  statement, not a u2 quirk** -- the repair for a raw lift is cheap exact local
  sweeps, and any t_therm quoted in trajectories understates the seed by two
  orders of magnitude as a practical cost.

  **u1'S OBSERVABLE SCAN (fig 46, `62_observable_scan.py`, 2026-08-22) IS THE
  CLEANEST COVERAGE FIGURE IN EITHER STUDY.** 14 couplings, beta 6 to 518,
  L = 32 from L = 16, relative deviation AND z. u1's training coverage is DENSE
  to beta = 60 (4 fixed rungs + 102 random, all beta_max 60) rather than isolated
  rungs, so the ceiling is a step and the bias SIGN flips across it: raw z at
  W(1x1) is -0.6 / +6.1 / +9.0 / +8.9 / +8.7 / +21.7 inside coverage and -63 /
  -138 / -150 / -162 / -179 / -198 / -205 outside. Ten sweeps return nearly every
  coupling to |z| < 2, far past the ceiling included.
  **NOTE THE CONTRAST WITH u2, it is informative:** in u2's scan the ppm and z
  columns point OPPOSITE ways (Spearman -0.82 against +0.80); in u1's they agree.
  The reversal is a property of the RANGE -- u2 spans model beta 2.8 to 327,
  across which the theory's own spread moves by orders of magnitude -- not of
  either code. That is the argument for treating "report z, not just a ratio" as
  a standing rule.

  **MULTIPLE LIFTS: THE RUNG COUNT IS FREE, THE FINAL RUNG SETS THE ACCURACY,
  AND ONLY THE TAIL MOVES TOPOLOGY (2026-08-22, `45_multi_lift_compounding.py`
  + u1's `60_`, fig30, report in
  `out/u2_2d/multi_lift_incov/MULTI_LIFT_REPORT.md`).** Eight cells: two
  theories x two endpoints (in coverage / past the ceiling) x intermediate
  retherm on/off, each reaching ONE fixed endpoint by 1, 2 and 3 lifts.
  * **No compounding.** 3 lifts sits at 0.94-1.02x the 1-lift error with the
    ladder's retherm, 0.84-1.00x without. A ladder can be as long as the base
    coupling requires.
  * **The error is injected by the LAST lift.** u2's 3-lift trace is z = +15.80
    (L=16, model beta 4.4), +0.91 (L=32, 15.8), -157.44 (L=64, 61.7). So
    accuracy is set by the FINAL rung's distance from training coverage, not by
    the rung count. **Laddering therefore does NOT extend the coupling reach** --
    every lift multiplies beta by ~4, so the last lift lands at the same model
    beta whatever path reached it. The ladder buys VOLUME, not coupling.
  * **The lift is exactly charge-preserving under COMPOSITION** -- 100% of
    configurations keep their starting charge at 1, 2 and 3 lifts in all four
    chains when nothing rethermalizes between rungs. This extends
    `36_transport_check.py` from one lift to three.
  * **The ladder's own retherm sweeps re-sample Q**, and the loss tracks how
    weak the intermediate rung is: u1 keeps 33.6% (L=16 retherm at beta 3.87)
    and 81.2% (beta 5.24); u2, whose intermediates are stiffer, keeps 98.4% and
    100%. NOT corruption -- `<Q^2>` moves TOWARD exact (u1: 1.633 -> 1.539
    against exact 1.386), because a rung weak enough for local moves to change Q
    is one where they sample it correctly.
    **So state the framing precisely: as deployed, the ladder RE-SAMPLES
    topology at every rung where that is still valid and transports it unchanged
    once the coupling is stiff enough that it is not.** "Drawn at the base and
    carried unchanged to the top" is exact only with intermediate retherm off.
  * Caveat: post-retherm endpoint |z| creeps with lift count (u2 in-coverage
    0.63/0.83/1.86; u1 ceiling 0.19/0.01/2.69). All below 2, so unresolved at
    64-128 configurations, but monotone in three of four chains.

  **THE OBSERVABLE SCAN (fig29, `scripts/43_observable_scan.py`, 2026-08-21)
  MEASURES THE COVERAGE STORY DIRECTLY, and it needed z to say anything.** 12
  couplings, L = 32 lifted from L = 16, 64 configurations, raw lift and after 10
  rethermalization sweeps, against the closed form. Read in RELATIVE DEVIATION
  alone the figure says "agreement improves with beta" -- Spearman(model beta,
  post-tail relative deviation) = -0.82, p = 0.001. That is the theory getting
  quieter, not the model getting better. In z the sign REVERSES:
  Spearman(model beta, |z| of the raw lift) = **+0.80, p = 0.002**, and the raw
  |z| at W(1x1) climbs 3.8 -> 123 across the range.
  * **The raw lift's error is resolved at 12/12 couplings** (W1x1), 10/12 at
    W(2x2), 8/12 at W(4x4). This is a real, large, measurable systematic.
  * **The two IN-SAMPLE couplings are the only points that break the trend**, by
    4x in median |z| (10.9 against 48.1), and are the ONLY two with POSITIVE
    bias -- off-rung the model is coherently negative, matching the note above
    about a negative bias in all ~24 observables at an out-of-coverage rung.
    They are marked IN-SAMPLE in the figure and must not be quoted as evidence
    of generalization.
  * **After 10 retherm sweeps, 34 of 36 (loop, coupling) cells are UNRESOLVED**,
    median |z| 0.50, including at model beta 327 -- 214% past the top training
    rung. Cheap EXACT local sweeps repair local observables at every coupling
    tested.
  Note the apparent tension with "past the top rung the seed does not thermalize
  on ANY local observable" (the crossover scan). It is probably not a
  contradiction: that statement is about HMC TRAJECTORIES under a strict
  5-consecutive-record t_therm criterion, while this is 10 heatbath +
  overrelaxation sweeps, which are a far stronger LOCAL move. If so the useful
  form is: out of coverage, the fix for local observables is cheap local sweeps
  rather than more HMC -- and it does not touch topology, which retherm leaves
  invariant by construction and which the model supplies exactly by transport.
  **TESTED 2026-08-21, `scripts/44_sweeps_vs_trajectories.py` -- one lift, one
  set of configurations, cloned, the budget spent two ways, matched in LINK
  TOUCHES (a retherm sweep is 3, an HMC trajectory is `n_steps` = 23-64).** The
  sweep half is clean and is the result: **two sweeps, six link-touches, reach
  |z| <= 2 at all three couplings** -- in coverage, +29% past the top rung, and
  +214% past it -- while the trajectory arm spends 920-2560 link-touches without
  getting there. Local exact sweeps repair the raw lift at any coupling tested,
  cheaply, and they cannot touch topology (`topological_updates=False`), which is
  transported.
  **DO NOT yet quote the sweeps-vs-trajectories RATIO.** The trajectory arm fails
  at the IN-COVERAGE coupling too (|z| 7.66 after 40 trajectories), where
  `28_crossover_scan.py` reports a FINITE t_therm at a comparable coupling using
  the identical criterion (same z, same five consecutive records; its `t_therm`
  is in RECORDS, so 6 means 12 trajectories) on the same kind of raw-lift input
  -- verified by reading its source, it does not retherm before the HMC arm
  either. So the trajectory arm is UNVALIDATED: either 40 trajectories is simply
  too short, or it differs from that scan in a way not yet identified. The 200-unit rerun at the
  in-coverage coupling is DONE (`out/u2_2d/sweeps_vs_trajectories_long/`) and
  says the arm is not broken, just slow: the seed's slowest |z| falls
  monotonically 76.9 -> 11.2 -> 7.3 -> 6.5 -> 4.8 -> 3.9 -> 3.1 over 200
  trajectories and then PLATEAUS at 3-4.5, dipping to 2.50 at unit 156 but never
  holding <= 2. The cold arm tracks it (min 3.42) so both HMC arms behave the
  same way. So the comparison at this coupling is **6 link-touches (2 sweeps,
  |z| 1.1, stable) against 4600 (200 trajectories, |z| ~4, plateaued)** -- the
  ratio is real and now measured, not a budget artefact.
  **THE APPARENT DISAGREEMENT WITH `28_crossover_scan.py` IS RESOLVED and there
  is no bug: t_therm IS GENUINELY RUGGED IN COUPLING, reproducibly.** The scan's
  own seed t_therm reads 59 / 51 / **6** / 50 at model beta 22.2 / 31.9 / 45.9 /
  66.1, and the fast point REPLICATES across its two independent rounds
  (plaquette/W2x2/W4x4 = 6/3/0 in the plain round, 5/2/0 in the topological one),
  as do its slow neighbours. An independent implementation
  (`44_sweeps_vs_trajectories.py`) reproduces the same landscape: at beta_f =
  183.59 (model beta 45.9) the seed reaches |z| <= 2 in **22 trajectories**,
  while 4.5% away at beta_f = 175.66 (model beta 43.9) it never gets there in
  200. So a single t_therm is a property of its coupling and NOT interpolatable
  to a neighbour; the earlier note here that the two scripts disagreed was
  comparing two different couplings.
  **The consequence for fig21 and for the Spearman of +0.62 is real**: individual
  t_therm points carry ~10x scatter between adjacent couplings, so no single
  point should be quoted as evidence, and the correlation must be presented as a
  trend across the whole scan rather than through named examples.

  **THE "ACTIONABLE DEFECT" THAT USED TO SIT HERE IS RETRACTED (2026-08-21,
  `scripts/42_retherm_reconcile.py`, write-up in
  `out/u2_2d/retherm_reconcile/RECONCILIATION.md`).** It read: ten sweeps make
  W(8x8) FOUR TIMES WORSE (378 -> 1581 ppm), so post-retherm `N*` at W(8x8) is
  137 while the delivered L = 64 ensemble carries 256 configurations, and
  `n_retherm` should be tuned against that. **Neither number was ever resolved.**
  sigma at W(8x8) is 19500 ppm, so 256 configurations give a standard error of
  1219 ppm and the two disputed values are z = 0.31 and z = 1.30. The competing
  measurement (`33_retherm_scan.py`, "2.3x BETTER") is the same quantity
  fluctuating the other way; measured on the SAME configurations in one pass the
  sign flips with sweep count (-949, -2498, +424, +1.6, +723, -1614 ppm at
  0/2/5/10/20/40 sweeps). `N* = (sigma/bias)^2` on a bias consistent with zero is
  unbounded -- 1.4e8 at 10 sweeps here -- so the finding was a squared noise
  fluctuation. There is no basis for retuning `n_retherm` and no evidence that
  rethermalization damages the infrared in u2. The metric-artefact hypothesis is
  refuted too: sigma moves only x0.93 across the tail, far too little to carry a
  4x disagreement, so the disagreement was in the numerator.
  **The claim about u1's Fig. 38 goes with it** -- "the residual is
  infrared-dominated because rethermalization PUT it there" was resting on this
  number and is now unsupported at the u2 coupling. u1's own measurement
  (`59_pre_post_retherm.py`) is separate and unaffected; there the repair factor
  merely reaches 1.0 at W(8x8), it does not go below it.

  **WHAT THE SCALE DECOMPOSITION ACTUALLY ESTABLISHES, in z against a naive SEM
  at 256 configurations.** Raw lift: W(1x1) 61.8 ppm / SEM 3.3 = **z 18.6**;
  W(2x2) 64.9 / 20.1 = **z 3.2**; W(4x4) 87.6 / 143.9 = z 0.6; W(6x6) z -0.3;
  W(8x8) z -0.8. So the model's residual is RESOLVABLE ONLY AT W(1x1) AND
  W(2x2), and ten sweeps remove it at both (z -> -0.16 and 0.67). At W(4x4) and
  larger the RAW lift is already statistically indistinguishable from exact, so
  nothing can be said about what the tail does there without a much larger
  ensemble. The flatness claim -- 62 / 67 / 69 ppm while the theory's own sigma
  grows 374x -- stands on two resolved points plus a consistent 2-sigma bound of
  ~290 ppm at the third; state it that way, not as three measurements.
  `<Q^2>` is 0.8281 at every sweep count to all printed digits: retherm runs
  `topological_updates=False`, so transport survives the tail exactly.
  **The general lesson, which is the one worth carrying: an N* or a ratio built
  from a large-loop bias needs its SEM checked first. Large loops have enormous
  per-configuration spread and 256 configurations do not resolve them.**

  **BUT COVERAGE IS BOUGHT, NOT FREE — measured twice, 2026-08-20 and 2026-08-21,
  and this is the more useful half of the lesson.** Two independent attempts to
  widen coupling coverage BOTH regressed lift precision, with the SAME signature:
  the tuned-sweep count the diffusion lift needs to hit the exact plaquette went
  **5 -> 30** in each. The first was the `_cov` retrain (12 fixed rungs, wider
  beta); the second was the full u1-style port (114 rungs, 3 volumes, random beta,
  sector augmentation, `configs/v2.yaml`, `det_score_net_v2.pt`). Different rung
  sets, different data, different seeds, same number.
  The v2 challenger's full scorecard against `25_challenger_report.py`: <Q^2> at
  the ladder base IMPROVED (z -0.78 -> -0.43, but that is a stage-01 data gain,
  not a model gain — topology is transported, so training cannot touch it);
  extended-loop mean |z| regressed at BOTH volumes (L=32 0.187 -> 0.292,
  L=64 1.134 -> 1.225); density gap regressed in 3 of 4 cases, improving ONLY at
  the top-rung case (+0.019 / +0.014 / +0.003 / -0.006 as beta rises — a
  monotone trade, which is what capacity dilution looks like).
  **CAVEAT ON EVERY `mean |z|` COMPARISON IN THIS FILE (2026-08-21).** A model
  that is EXACTLY right, scored with CORRECT error bars, gives
  `mean |z| = sqrt(2/pi) = 0.798`, because |z| is then half-normal. So an
  extended-loop `mean |z|` of **0.187 is four times better than perfect** and is
  not a good score -- it is evidence that those error bars are overestimated, or
  that the observables entering the mean are strongly correlated so the z's are
  not independent draws. Read the v2 move 0.187 -> 0.292 and the capacity move
  0.187 -> 0.666 with that in mind: both go TOWARD 0.798, not away from it, and
  calling them "regressions" assumes the 0.187 baseline was meaningful. The
  L = 64 pair (1.134 -> 1.225, and capacity's 1.134 -> 0.319) brackets 0.798 from
  the other side and is the more interpretable of the two volumes.
  This does NOT overturn the capacity verdict -- that rests mainly on the tuned
  sweep count and the density gap, neither of which is a z -- but the
  extended-loop column should not be quoted as evidence on its own until the
  error bars in `25_challenger_report.py` are checked against
  `tau_int`-aware ones (u1 NARRATIVE 25.7 / M4 made exactly this correction).
  Same class of error as the retracted W(8x8) finding above: a statistic quoted
  without asking what value it would take if nothing were wrong.

  Diagnosis: at `hidden: 64, depth: 4` the net is CAPACITY-LIMITED, and 113 rungs
  share what 12 rungs used to own. Corroborating: `val_total` was still at its
  best at epoch 118 of 120 (no early stop) with the GPU at 30% — input-bound at
  `batch_size: 32`, i.e. it ran out of budget, not out of signal.
  **So do not widen coverage again without raising capacity and epochs first.**

  **AND THE u1 COMPARISON SHOWS WHY -- u2 RAN u1'S DATA RECIPE UNDER-PROVISIONED
  (2026-08-21).** u1 DOES train on randomly sampled beta; that was one of the
  keys to its generalization, and any claim here that random-beta coverage is
  itself harmful is wrong. Side by side:

  | config | fixed rungs | random | beta max | hidden | depth | batch | epochs |
  |---|---|---|---|---|---|---|---|
  | u1 v3_scale | 4 | 102 | 60 | 80 | 5 | **16** | 80 |
  | u1 v2 | 4 | 78 | 60 | 56 | 4 | 16 | 100 |
  | u2 default (DEPLOYED) | 12 | -- | 430 | 64 | 4 | 32 | 120 |
  | u2 v2 (regressed) | 12 | 102 | 430 | 64 | 4 | 32 | 120 |
  | u2 capacity (running) | 12 | 102 | 430 | 96 | 5 | 64 | 260 |

  u2's v2 copied u1's data strategy onto a SMALLER net (64/4 against u1's 80/5)
  over a WIDER beta range (model beta to 104 against u1's 60). The right lesson
  is not "random beta dilutes capacity" but "u2 under-provisioned relative to
  u1's own recipe". Note also `batch_size`: u1 uses **16**, the capacity config
  uses 64, which at a fixed epoch budget is 4x fewer gradient steps. **If the
  capacity retrain disappoints, change the batch size before the width.**
  NOTE the deployed `det_score_net.pt` has NO random rungs -- its history carries
  10 val keys and the 9 unique model betas of the 12 fixed rungs. `default.yaml`
  has since GROWN a `random_rungs` block, so the file no longer describes the
  deployed checkpoint; do not read training coverage off it.
  `det_score_net.pt` stays deployed; `out/u2_2d/data_v2/` is KEPT because its
  improvement is in the data and is independent of the net, and is the right
  starting point for the capacity experiment.

- `su2_2d/` — 2D SU(2). **SET ASIDE (2026-08-03) and NOT in the working tree.**
  It was removed from tracking in `f7bca3b` while the focus moved to
  documenting and publishing U(1). Recover it with
  `git checkout 87fd6fa -- su2_2d` (27 files: quaternion link variables, exact
  group heat-kernel targets, group-manifold HMC, non-abelian curl-head score).
  Its heavy stages were run far enough to localize the first failure — the
  single-plaquette curl basis is incomplete for SU(2) — and no further.
  Do not reference `su2_2d/` paths in commands until it is restored.

The final U(1) checkpoints are `out/u1_2d/checkpoints/score_net.pt` (pipeline)
and `score_net_rkl2.pt` (likelihood/ESS work only). Everything else in
`out/u1_2d/` is reports/figures/summaries — regenerable `.pt` ensembles were
pruned 2026-08-02 (recoverable from git history if ever needed).

**Second prune, 2026-08-18 (1104 MB → 111 MB).** Two classes went:
(i) superseded or zero-reference run directories — `ptbc_benchmark/` (untuned),
`sector_mode_table/` (superseded by `_tau_aware`), `ais_transport_preFoldFix/`,
`ais_transport_rich/`, `generalization_exact_sectors_{b,seed2}/`,
`generalization_fresh_s4/`, `pq_hmc_tail_adaptive/`,
`ode_reweighting_{easy,probes8}/`, `tiling_smoke/`, the seven stray `*.log`, and
the `campaign_state/` + `*/state/` sentinels; (ii) regenerable `.pt` ensembles
inside directories that *are* of record (`generalization*`, `thermalization`,
`validation`, `data`, plus `.png`/`.npz`/`.log` under `gpu_verification/` and
`proj_sigma_ab/`, both of which are process-verification runs whose results live
in their `.json`/`.md`). Every `report.md`, appendix figure, and summary `.json`
survives; all 169 tests, `29_verify_identities.py`, and
`30_assemble_appendix_figures.py --check` pass after the prune.
**The narrative record of all of it stays in `docs/u1_2d/NARRATIVE.md`** — that is the
point of the prune, so a dead `out/` path quoted there is expected, not a bug.
Everything is recoverable from git history (all of `out/` was tracked).
Three directories were *spared* despite looking prunable, because they are live
figure inputs: `ode_reweighting_sweep/` and `model_ess_noguide/` (figures 19,
24, 26) and `thermalization/*_series.npz` (figures 12, 16, via scripts 08/11).

## Key Conventions

### Physics (U(1), and carried to SU(2) where stated)

- Link angles `theta[mu, x, y]` on periodic 2D square lattice, shape `[2, L, L]` or `[B, 2, L, L]`
- `field[:, 0]` = x-links (mu=0), `field[:, 1]` = y-links (mu=1)
- Index convention: `field[batch, mu, x, y]`; dim -2 is x, dim -1 is y
- Wilson action: `S = -beta * sum cos(plaquette_angles)`
- Angles always regularized to `(-pi, pi]` via `atan2(sin, cos)` (`u1_2d.lgt.lattice.wrap`)
- Plaquette: `p(x, y) = ux(x,y) + uy(x+1,y) - ux(x,y+1) - uy(x,y)`, wrapped
- Tree-level coupling relation across one 2x2 blocking step: `beta_c = beta_f / 4`
- 2D U(1) has no phase transition; RG flows go toward strong coupling (beta -> 0)
- U(2) links are `[..., 5]` = `(phi, q0, q1, q2, q3)` with
  `U = e^{i phi} (q0 I + i q_a sigma_a)`; index convention `links[batch, mu, x, y, :]`,
  so dim -3 is x and dim -2 is y (the `u1_2d` convention shifted by the group axis).
  Plaquette `P = U_0(x) U_1(x+0) U_0(x+1)^dag U_1(x)^dag`, same orientation as U(1).
  Action `S = -beta sum_p (1/2) ReTr P = -beta sum_p q0_p cos(phi_p)`.
  Topological charge `Q = sum_p wrap(arg det P) / 2 pi`, rounded.
  Tree-level ladder relation `beta_c = beta_f / 4`, same as U(1).
  `U(2) ~ 4 x U(1)` in the determinant sector — but only asymptotically; use
  `u2_2d.lgt.exact.matched_u1_beta`, never `beta/4`, whenever a number matters.
- SU(2) links are unit quaternions `[..., 4]` (w, v); plaquette word
  `P = U_x(x,y) U_y(x+1,y) U_x(x,y+1)^-1 U_y(x,y)^-1`; action
  `S = -(beta/2) * sum tr P`; 2D SU(2) has trivial pi_1 — no topological
  sectors (that is the point of doing it before 4D).

### Diffusion / Ladder

- Fine ensembles generated by batched HMC (Omelyan for U(1), expmap leapfrog for SU(2))
- Score network trained by denoising score matching on the group heat kernel
  (wrapped Gaussian on U(1); character-expansion kernel on SU(2))
- Beta ladder: matched sequence of (L, beta) rungs; each inverse step doubles L
- Validation compares gauge-invariant observables (plaquette, rectangles,
  Wilson loops, and for U(1) topological charge/susceptibility) between
  generated and reference ensembles; U(1) also has exact character-expansion
  references (`u1_2d.lgt.exact`), SU(2) has `su2_2d.lgt.exact`
- Exactness lesson from U(1) (measured, do not re-litigate): the model's
  density gap is fine-side model error (~1 nat/site mean, 0.02–0.07 std).
  The matching-residual explanation is eliminated by the **within-arm R²_c
  decomposition** (≤6% of fiber log-weight variance is coarse-explainable,
  and a matching residual is a c-only function so it can land nowhere else)
  — *not* by the Villain arm, which corroborates but is confounded. Do not
  retrain a Villain-specific checkpoint to "fix" that arm: the effect is a
  few percent of variance while same-architecture checkpoint variants move
  spreads 2–6× (Table S5), so any cross-model comparison is an order of
  magnitude noisier than its own signal. Closed; see `docs/u1_2d/NARRATIVE.md`
  §18.5 for the full write-up and the general lesson (prefer within-model
  decompositions to cross-arm subtractions for small effects).
  Exactness **must** come from Markov-chain machinery wrapped around the
  proposal — not from the proposal's own likelihood. This is a *design
  directive* for SU(2), not a property the U(1) pipeline delivered: the
  deployed ladder applies **no accept/reject to the proposal** (the only MH
  is inside local retherm sweeps and the instanton hop), so as shipped it is
  a **validated heuristic**, asymptotically exact only in the retherm → ∞
  limit that costs what direct simulation costs. The conceptually clean
  claim is the *seeded* mode: exact HMC from a diffusion seed is
  asymptotically exact within its sector, with the sector supplied by
  transport. AIS bridging reaches its derived floor in 8 of 10 seeds
  (1.97–2.71× spread reduction at the extrapolation case) but did **not**
  lift ESS — it is a validated *mechanism*, not a delivered exactness route.
  The other 2 of 10 diverge by 10²–10³. The cause is the **surrogate's
  regularization**, established by intervention (Table S7c): holding inputs
  byte-identical and varying only a floor on the ridge grid moves held-out σ
  2132 → 43.1 at the extrapolation case, spanning both modes on its own. Both
  divergent seeds had selected the grid's smallest ridge and no converged seed
  did (p = 0.022), with coefficient norms 231/247 vs 40–105.
  Guard on the **surrogate coefficient norm**, not `hmc_acceptance_min` —
  acceptance is downstream and misses cases (at 32:218.6 σ blows up 18× with
  acceptance flat at 0.958). Do not reach for basis width, and do not trust
  `fit_surrogate_cv` to pick the ridge: its held-out folds sit on the fit
  manifold, while the coefficients only explode off it, so CV is blind to this
  failure by construction. More ridge is not monotonically better — 16:55.02
  reverses — so there is no floor to hard-code.
  (Table S7b/S7c, `parse_ais_seed_rate.py`, `40_fold_noise_audit.py`,
  `41_ridge_scan_report.py`.)
- The classical baseline of record is **HMC + winding update**, not PTBC and not
  plain HMC. Measured 2026-08-15 at L = 32 (Table S8): plain periodic HMC is
  fully frozen (0 sector changes in 3000 trajectories at β = 14.15/55.02/218.58),
  the winding update reproduces exact ⟨Q²⟩ to 2% with τ_int(Q²) ≈ 1.2–2.9 for a
  1–18% overhead, and a **properly tuned** PTBC ladder (swap acceptance
  0.68–0.98, τ_int ≈ 3) still costs 25–121× more. PTBC exists to manufacture a
  global topological move for theories that lack one; this theory has an exact
  one, so importing that comparison measures nothing. Do not re-open the PTBC
  arm — `u1_2d/lgt/ptbc.py` and its 20 tests are kept as the record that it was
  checked, and `out/u1_2d/ptbc_benchmark_tuned/` is the data of record (the
  untuned `ptbc_benchmark/` was superseded — its numbers are 45–51× pessimistic
  and its swap-acceptance column is halved by a since-fixed bug — and was
  deleted in the 2026-08-18 prune). Cost claims
  go against `hmc+inst` (0.198 s per independent configuration at β = 218.58).
  If the PTBC arm is ever re-run: it is latency-bound, so use the stacked
  action (`StackedDefectWilsonAction`) on GPU — replicas are then nearly free —
  and time the single-replica arms on CPU, which is faster for them.
- Ladder invariant (use it, it is the design's justification): with
  β_f = 4β_c and L_f = 2L_c, the exact finite-volume ⟨Q²⟩ ≈ V/(4π²β) is a
  **fixed point** of the ladder (Villain: 1.20271 → 1.20334 → 1.20334 →
  1.20334 over four rungs). So the coarse ensemble's P(Q) *is* the fine
  theory's P(Q) — sector transport is an identity, not an approximation —
  and climbing the ladder is a continuum-limit trajectory at fixed physical
  volume.
- Validation caveat carried to SU(2): observable-level agreement is sharp
  (plaquette to ~2 parts in 10⁴) but does not constrain the density (KL is
  ~450–2100 nats/config). Residual model error concentrates in *extended*
  observables — std(z) grows 1.09 → 1.44 from W(4×4) to W(12×12). Report
  large-loop dispersion, not just plaquette/W(2×2)/W(4×4).

### Code Style

- No comments that merely narrate what code does
- All tensor operations handle both single and batched inputs
- Use `torch.no_grad()` for measurement computations when not inside training
- Preserve backward compatibility when adding new methods

### Testing

- `pytest u1_2d/tests -q` (169 tests) and `pytest u2_2d/tests -q` (84 tests);
  `su2_2d/tests` only exists once su2_2d is restored from git — see above
- `python u2_2d/scripts/07_pq_sampling.py` — where P(Q) can be SAMPLED rather than
  seeded; the `PARITY-STUCK` verdict is the U(2)-specific one. Minutes.
- `python u2_2d/scripts/08_hmc_seed_benchmark.py` — the headline claim: a generated
  configuration as an HMC starting point, against cold, hot, and winding baselines.
- `python u2_2d/scripts/15_base_parity.py` — counts PARITY FLIPS. The correct test
  for odd-charge mobility, and it supersedes reading it off 07's verdict. `--cold`
  adds the cold-start arm, which is what proves the split is inherited rather than
  sampled where the flip count is zero.
- `python u2_2d/scripts/14_sampler_steps.py` — the reverse-diffusion step count as a
  cost/accuracy dial. Read the RUNG 0 pre-retherm column (its input is the fixed HMC
  base) and the top rung's extended loops; the top rung's plaquette compounds two
  lifts and crosses zero near 18 steps, so tuning on it picks a bad setting.
- `python u2_2d/scripts/09_verify_identities.py` — the exact U(2) identities
  (group representation, gauge invariance, the determinant telescope, analytic
  force vs autograd, microcanonical overrelaxation, winding parity, the character
  expansion vs Weyl integration). Seconds; must pass.
- `python u1_2d/scripts/29_verify_identities.py` — the exact physics identities
  (Q integrality, gauge invariance, blocking telescope, curl-head completeness,
  <Q^2> ladder fixed point, area law, instanton cost). Seconds; must pass.
- `python u1_2d/scripts/30_assemble_appendix_figures.py --check` — verifies the
  **46** (not 27) u1 appendix figures match their canonical sources. Run before
  submitting.
- `python u2_2d/scripts/49_assemble_appendix_figures.py --check` — the u2
  equivalent, added 2026-08-22, and its **staleness test is different by
  necessity**. u1's appendix figures are COPIES, so staleness is a hash mismatch
  against the source. Every u2 figure is written in place by its own script, so
  there is no second copy to compare — what can be compared is TIME, and a
  figure is stale when it is older than the newest input it was drawn from.
  Weaker than a hash (blind to a source edited without touching mtime, fires on
  a harmless re-save) but it catches the failure this project actually has: an
  upstream run regenerated while the figure below it was not. On its first run
  it caught three — `fig08`, `fig12`, `fig23` were drawn from the naive-SEM
  validation before `out/u2_2d/validation/` was promoted to the tau_int-aware
  numbers. 36 figures tracked; the three L16/beta56 smoke-config variants of
  fig1-3 are listed as deliberately EXCLUDED so "untracked" means "unexamined".
  `--write-appendix` regenerates `out/u2_2d/paper_appendix/appendix.md` from
  the captions in the script, so a caption cannot say one thing in the manifest
  and another in the appendix.
- `python u1_2d/scripts/64_export_paper_bundle.py` — assembles
  `paper/main.tex` + `paper/figures/{u1_2d,u2_2d}/` for Overleaf (gitignored;
  regenerable). It is a section-by-section OUTLINE with real figures, captions
  and cross-references and no prose. Three things it does that a manual copy
  gets wrong: rewrites dots out of filenames (`beta105.651` defeats graphicx
  extension detection); checks every tracked figure is placed EXACTLY once
  across the plan, so a figure in no section is an error rather than a silent
  omission; and converts u2's plain-markdown captions to LaTeX (they contain
  `<Q^2>`, `w_det(alpha)`, `Z_2` — a blanket escape is unreadable and no escape
  is a hard error). There is no TeX toolchain in this environment, so it lints
  for unescaped specials rather than compiling; build once in Overleaf before
  trusting it.
  **TWO-COLUMN (`\documentclass[twocolumn,10pt]{article}`), and the span of each
  figure is MEASURED, not guessed.** A single column here is ~3.2 in, and these
  are mostly multi-panel plots — median aspect 1.89 — so 72 of the 82 get
  `figure*` and span both columns. The rule is `aspect >= 1.5` OR
  `native width >= 2000 px`, and the second clause exists because aspect alone
  got it wrong: `46_observable_scan.png` is a four-panel figure 2459 px wide at
  aspect 1.48, just under the threshold, and would have been squeezed to 1.6 in
  per panel. Editorial exceptions live in `FORCE_SPAN` (currently u1's lead
  figure) rather than being smuggled in by tuning the threshold. Figures past
  `aspect 6` get a `% WARNING` comment — `16_autocorrelation_modes.png` is
  16588x1326 and is a 0.5 in strip even at full text width; it needs splitting
  or rotating. `\linewidth` is used for every width so one spec serves both
  environments. Title and abstract span via the standard
  `\twocolumn[\begin{@twocolumnfalse}...]` idiom. Switching to APS styling is
  one line (`revtex4-2`), noted in the file's own header.
  **THE OVERLEAF COMPILE TIMEOUT WAS AN RGBA PROBLEM, NOT A FIGURE-COUNT ONE
  (2026-08-22).** Matplotlib writes colour type 6 (RGBA), and all 82 figures
  were. pdfTeX copies a PNG's compressed stream straight into the PDF ONLY for
  colour types 0/2/3 at 8 or 16 bits, non-interlaced, with no transparency;
  RGBA misses that path, so it decodes with libpng, splits the alpha into a
  separate SOFT-MASK image and re-encodes both -- over 145 megapixels here.
  That is what exhausts a free-plan budget, and dropping figures would not have
  fixed it. The exporter now flattens onto white, which is **exactly lossless
  in this bundle** (every alpha channel measured fully opaque, extrema
  (255,255); output verified pixel-identical, worst difference 0 across all 82)
  and yields RGB 8-bit non-interlaced -- the pass-through case.
  **Do NOT "fix" this by downsampling:** resampling anti-aliased line art
  creates more distinct colours than the crisp original, so a 300 dpi cap
  measured **112%** of the original bytes -- it costs quality and saves
  nothing -- and pixel count stops mattering once decoding is skipped.
  Escalation if it is still too heavy: `--palette` (256 colours, 14.0 -> 5.6 MB,
  still pass-through, but LOSSY: worst case measured 0.33% of pixels off by more
  than 8/255, all on anti-aliased edges), and `--draft`, which emits
  `\includegraphics[draft]` so no image file is read at all -- the way to
  iterate on structure and float placement.
  **The main-text pipeline schematic is u2's `fig28_pipeline`, not
  u1's `44_pipeline`** — `41_pipeline_schematic.py` draws one schematic for both
  studies — and `fig30_multi_lift` sits in the METHOD section, not section 8.

## File Layout

```
u2_2d/            -- ACTIVE 2D U(2) study (configs, lgt, model, pipeline, scripts, tests, validate)
u1_2d/            -- CLOSED 2D U(1) study (configs, lgt, model, pipeline, scripts, tests, validate)
su2_2d/           -- SET ASIDE, not in the tree (git checkout 87fd6fa -- su2_2d)
docs/u1_2d/       -- NARRATIVE.md (full mathematical story), V2_AUDIT.md (final U(1) audit),
                     PHYSICS_WALKTHROUGH.md, U1_2D_REVIEW.md, PAPER_OUTLINE.md, READING_GUIDE.md
docs/u2_2d/       -- DESIGN.md (U(2) derivations and measured results)
docs/             -- Field_transform.html (NTHMC note on the U(1) vs U(2) field transformation)
out/u2_2d/        -- U(2) outputs: data, checkpoints, ladder, validation
out/u1_2d/        -- U(1) results of record: reports, figures, summaries, final checkpoints
out/su2_2d/       -- SU(2) outputs (untracked; only if su2_2d is restored)
artifacts/        -- gitignored scratch (safe to delete)
```

The sibling `NTHMC` repository (outside this tree, at `../NTHMC`) holds the
JAX-based 2D U(1) and 2D U(2) HMC and neural field-transformation code. `u2_2d`
deliberately matches its split representation, plaquette orientation and
determinant-phase topological charge, so configurations are interchangeable. Two
deliberate differences: `u2_2d` drops NTHMC's additive `beta V` constant from the
action to match the `u1_2d` sign convention, and rounds the topological charge
rather than using NTHMC's `floor(0.1 + .)` offset.

## Virtual Environment

A project-local virtualenv is at `.venv/` (gitignored).

**Always use the venv Python** — never the system Python:

```bash
# Windows
.venv/Scripts/python.exe -m pytest u1_2d/tests -q
```

Torch must come from the CUDA 12.8 index — the RTX 5060 is Blackwell (sm_120)
and pre-cu128 wheels report `cuda.is_available() == True`, then die at the first
kernel launch. `utils.configure_device` checks for this and refuses to start.

```bash
.venv/Scripts/pip install --index-url https://download.pytorch.org/whl/cu128 torch
.venv/Scripts/pip install -e ".[dev]"
```

## Compute (this machine)

**Current: RTX 5060 Laptop (8 GiB, sm_120) + Ryzen 7 260 (8c/16t), CUDA 12.8.**
`device: auto` resolves to `cuda`; override with `--device` or `U1_2D_DEVICE`.
8 GiB is ample — the whole v3_scale training set on-device is well under 1 GiB.

**Pick the device per stage from measurement, not intuition.** Batched HMC is
kernel-launch-bound at this project's volumes and is often *faster on CPU*
(sweeps/s, GPU÷CPU): 16 chains — L=16 0.43×, L=32 0.50×, L=64 1.36×; 64 chains —
L=16 0.79×, L=32 1.13×, L=64 3.08×. So the crossover is ~L=64 at 16 chains and
~L=32 at 64 chains. Model sampling and training always want the GPU.

| stage | device | why |
|---|---|---|
| 01 data | **cpu**, 8 shards | pure HMC at L≤32 |
| 02 train | cuda | score net |
| 03 ladder | cuda | sampler-dominated |
| 04 validate | **cpu** | reference HMC at L=16/32 |
| 05 therm | cuda | 64-chain baselines at L≥32 |
| 06 study | cuda | ladder sampling dominates |

**U(2) HAS A DIFFERENT DEVICE RULE FROM U(1) -- measured 2026-08-19, do not
carry the U(1) table over.** GPU/CPU trajectory rate for `u2_2d` batched HMC
(Ryzen 7 260 at one torch thread vs RTX 5060):

| L | chains | cpu traj/s | gpu traj/s | gpu/cpu |
|---|---|---|---|---|
| 8 | 32 | 10.05 | 5.18 | 0.52 |
| 16 | 32 | 3.93 | 5.26 | 1.34 |
| 16 | 64 | 2.13 | 5.30 | 2.48 |
| 32 | 32 | 1.15 | 5.36 | 4.67 |
| 32 | 64 | 0.58 | 4.81 | 8.30 |
| 64 | 64 | 0.12 | 4.88 | 39.96 |

The crossover is **L = 16**, not L = 64 as it is for U(1), because a quaternion
link carries ~6x the arithmetic of an angle so each launch pays for itself two
factors of two earlier. GPU throughput is FLAT at ~5 traj/s from L = 16 to
L = 64 -- purely launch-bound -- so on the GPU the large lattices are nearly
free, and the right move is to run the L = 8 rungs on CPU and everything else on
GPU *concurrently*. `u2_2d/scripts/run_stage01.ps1` does exactly that (3 CPU
shards + 4 GPU shards). Heatbath crosses over at the same point (L=32/64ch:
1.73 cpu vs 10.83 gpu sweeps/s).

Two other measured U(2) speedups, already applied: `lattice.staples(links, mu=)`
computes one link direction instead of both (the checkerboard sweeps update one
at a time, so computing both wasted exactly half of every heatbath and
overrelaxation sweep); and stage 01 thermalizes with heatbath + overrelaxation
before HMC (`thermalize_sweeps`), which replaced 2000 burn-in trajectories with
60 sweeps + 300 trajectories at L = 32, ~7x cheaper. Both are exact updates of
the same action, and the plaquette-vs-closed-form check is printed every run.

**THIS 8 GiB CARD HOLDS THREE CUDA CONTEXTS OF THIS WORKLOAD, NOT FOUR --
measured the hard way, 2026-08-21.** Running the capacity retrain (hidden 96,
depth 5, batch 64) alongside two L=64 crossover scans and an L=16 P(Q) run killed
the retrain with `CUDA error: out of memory` at epoch 36, and killed the P(Q) run
the same way an hour later. Three contexts sit at ~4.2 GiB and are stable.
`PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`, the usual remedy for
fragmentation-driven OOM, **is not supported on Windows** -- it warns and does
nothing. So the only levers are context count and restartability:
* Cap concurrent CUDA stages at three.
* Make long trainings restartable. `configs/*.yaml` now accept `resume: true` and
  `snapshot_every` (plumbed through `02_train.py`; the trainer default is 10).
  With `snapshot_every: 2` an OOM costs two epochs, and `run_queue_resume.ps1`
  wraps training in a retry loop that resumes automatically -- it fired
  unattended on 2026-08-21 and recovered without intervention.
* **Gate dependent stages on the trainer having EXITED 0.** The original parallel
  queue did not, and would have built the ladder, validation, seed benchmark and
  both prolongators on a quarter-trained checkpoint that happened to be on disk,
  producing a capacity A/B with nothing in the output saying so.

**PROCESSES LAUNCHED FROM THE EDITOR-ATTACHED SHELL DIE WITH THE SESSION.**
Measured: that shell's job object reports `LimitFlags=0x3C00`, i.e.
`KILL_ON_JOB_CLOSE=YES`, and every child inherits it -- closing VS Code or ending
the agent session kills every run. A process launched through Task Scheduler gets
`LimitFlags=0x0` and survives. `Register-ScheduledTask` works without elevation;
use `-ExecutionTimeLimit ([TimeSpan]::Zero)` or the task is killed at 72 hours.
Two tasks are registered and idle for this purpose: `u2_capacity_queue` and
`u2_gpu_tail`. This is why the note below prescribes scheduled tasks.

**Long runs: hold the machine awake with
`powershell -ExecutionPolicy Bypass -File u2_2d/scripts/keep_awake.ps1`.** It
calls SetThreadExecutionState(ES_CONTINUOUS), needs no administrator rights, and
releases automatically when the process exits -- there is no global setting left
behind to undo. Do not use a key-pressing loop.

**Parallelism: fan out over units, not threads.** Both heavy stages are
latency-bound — 01 holds one core, 06 holds the GPU at ~32% — and the batch
sizes are fixed by the physics, so the only lever is running units
concurrently. Threads inside one unit make it *worse*: 01 measures 154
sweeps/s on 1 torch thread, 142 on 8, 91 on 12.

```bash
# 01: N = physical cores, one thread each. 21.7 min -> 3.2 min.
for i in 0..7: 01_generate_data.py --shard $i/8 &   # U1_2D_TORCH_THREADS=1
01_generate_data.py --merge-shards

# 06: N = 3-4 on 8 GiB (each shard carries its own CUDA context + model)
for i in 0..3: 06_generalization_study.py --shard $i/4 --out-dir DIR &
06_generalization_study.py --merge-shards --out-dir DIR
```

`u1_2d/scripts/shard_runner.py` holds the helper and the full contract a
shardable stage must honor (own per-shard result file, aggregates deferred to
the merge, round-robin so expensive families spread evenly). Read it before
adding `--shard` to another stage.

**Device convention — the bug class CPU-only machines cannot show you.**
Ensembles are CPU-resident (`load_ensemble` pins `map_location`, `save_ensemble`
calls `.cpu()`, `generate_fine_from_coarse` returns CPU chunks); only the model
forward and the HMC integrator run on `device`. `run_hmc_ensemble` is the **one**
function that returns tensors on its `device`, so normalize its output before it
meets anything else. Three real bugs came from violating this (06, 27, 28, plus
`model/ais.py` `g_of` converting dtype but not device). Guard:
`python u1_2d/scripts/32_gpu_smoke.py` runs every compute-bearing script once on
the GPU and flags `DEVICE-BUG` separately from ordinary failures.

Historical (Snapdragon X Elite, CPU-only) — still the recipe if a run moves back
to that laptop: EcoQoS as-is, **no priority games**, `U1_2D_TORCH_THREADS=8` as
the single-process ceiling, **never parallel worker processes** — priority
elevation + parallelism hard-crashed that machine twice on 2026-07-24. Launch
detached long runs via Windows scheduled tasks (`schtasks /Run /TN <name>`), not
from an editor-attached shell; drivers are sentinel-resumable.
