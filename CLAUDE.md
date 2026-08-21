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
  (i) the exact-sector crutch exists because 2D U(2) is solvable, and closes in
  4D SU(3) where there is no closed-form P(Q) to seed from -- a real limit on
  transferring the method, and it belongs in the discussion; (ii) local
  equilibration at high beta is not free either (cold starts fail to thermalize
  LOCALLY within 200 trajectories from beta_f = 537 up), so a rung at model
  beta 200 is expensive even with sectors installed. The natural escape is to
  bootstrap -- train rung n+1 on rung n's lifted output instead of on HMC -- which
  the pipeline does not do (the net trains once on fixed HMC rungs) and which
  risks compounding error up the ladder. Settle the capacity experiment first;
  bootstrapping onto a capacity-limited net compounds the wrong thing.

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

  **ONE ACTIONABLE DEFECT falls out, and it is not cosmetic.** Rethermalization
  is a low-pass repair: ten sweeps take W(1x1) from 62 -> 1.3 ppm and W(2x2) from
  67 -> 1.9, leave W(4x4) unmoved at 69, and make W(8x8) FOUR TIMES WORSE,
  378 -> 1581. So POST-retherm N* at W(8x8) is **137 while the delivered L = 64
  ensemble carries 256 configurations** — it is already past the point where its
  own W(8x8) systematic exceeds its statistical error. `n_retherm` is 10 and was
  never tuned against this; this is the quantity that should set it. It is also
  the mechanism behind u1's Fig. 38 (`54_seed_accuracy_figures.py`): that
  figure's residual is infrared-dominated because rethermalization PUT it there.
  u1 is not wrong — it measures post-retherm output and attributes the residual
  correctly — but it never measured the PRE-retherm lift separately, so the
  causal half of its story is asserted rather than shown.

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
  Diagnosis: at `hidden: 64, depth: 4` the net is CAPACITY-LIMITED, and 113 rungs
  share what 12 rungs used to own. Corroborating: `val_total` was still at its
  best at epoch 118 of 120 (no early stop) with the GPU at 30% — input-bound at
  `batch_size: 32`, i.e. it ran out of budget, not out of signal.
  **So do not widen coverage again without raising capacity and epochs first.**
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
  27 appendix figures match their canonical sources. Run before submitting.

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
