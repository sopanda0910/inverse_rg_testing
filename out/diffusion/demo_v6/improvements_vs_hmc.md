# Inverse-RG diffusion vs standard HMC: results and improvements

**Baselines, stated precisely.** "HMC" in every comparison below means **plain
HMC — no instanton (Q-hop) updates** — because that is standard practice; the
global instanton move is this project's own ergodicity fix and would not be
available to a conventional simulation. Q-hop HMC appears in only one role:
manufacturing unbiased *reference ensembles* for distribution-shape (KS) tests.
It is never the baseline being beaten. All expectation values are judged against
the **exact character expansion** of 2D compact U(1) (closed-form Wilson loops,
P(Q), chi_top at finite volume) — never against HMC.

Model: the single v6 checkpoint (continuous-beta training on beta in [1, 60],
L = 8/16/32). Pipeline: conditional diffusion + deterministic charge projection
+ 16 rethermalization sweeps. Data: `generalization/verdict.md` (38 cases, two
seeds on the A/D/E/F tracks) and `generalization/thermalization/` (29-case
benchmark, plain-HMC hot/cold baselines, 640 trajectories each).

---

## 1. Topological charge: the physics plain HMC cannot reach

At beta >~ 10, plain HMC cannot change Q: **zero tunnelings in 321 x 32
trajectories at every coupling from 14.15 to 872.8** (tau_int(Q) = infinity).
Its two standard initializations then fail in the two possible ways: cold
starts sit in Q = 0 forever (<Q^2> = 0, infinitely far from exact in units of
its own error), and hot starts freeze into a random wrong sector whose bias
never decays. The pipeline inherits its sector from the coarse level, where
topology is cheap:

| beta_f (L=32) | exact <Q^2> | pipeline <Q^2> (z) | P(Q) chi^2 p | plain HMC cold | plain HMC hot |
|---|---|---|---|---|---|
| 6.11 | 4.686 | 4.195 (-0.90) | 0.21 | ok (still tunnels, tau_Q ~ 35) | ok (\|z\| ~ 2) |
| 14.15 | 1.904 | 1.695 (-0.72) | 0.69 | **Q^2 = 0 forever** | frozen, \|z\| = 3.4, 0 tunnelings |
| 55.02 | 0.474 | 0.430 (-0.49) | 0.28 | **Q^2 = 0 forever** | frozen, \|z\| = 6.4, 0 tunnelings |
| 218.6 | 0.0290 | 0.0234 (-0.34) | (Q hist. sparse) | **Q^2 = 0 forever** | frozen, \|z\| = 3.8, 0 tunnelings |
| 872.8 | 1.0e-7 | 0 (consistent) | - | Q = 0 (right by luck: exact ~ 0) | frozen, \|z\| = 5.7 |
| 218.6 at **L=64** | 0.474 | 0.656 (+1.3 / +0.8 both seeds) | 0.13 | **Q^2 = 0 forever** | frozen, \|z\| = 4.2 |

Read the middle rows: across 14.15 -> 218.6 the pipeline tracks the exact
topological susceptibility within \|z\| < 1 and passes the exact-P(Q) chi^2
test, in a regime where plain HMC's Q distribution is simply wrong — not noisy,
wrong, with no amount of running able to fix it (tunneling is suppressed like
exp(-2 beta)).

## 2. Generalization: one model, any coupling, multiple volumes

- **Full track**: 26 matched-pair cases from beta_f = 1.49 to 872.8 pass all
  Wilson-observable tests vs exact (\|z\| <= ~2 with two-seed error bars);
  P(Q) chi^2 passes everywhere it is statistically testable.
- **Extrapolation**: training stopped at beta = 60. At **beta_f = 398.5 and
  872.8** (7x and 15x beyond), plaquette / W(2x2) / W(4x4) match exact within
  \|z\| <= 1.6 at both seeds. At **L = 64** (never trained; trained fine
  lattices end at L = 32) all means pass including <Q^2>. The long-standing
  "small-loop KS shape failure at L >= 64" turned out to be mostly the
  *references'* fault, not the model's — resolved in section 5.
- **Out-of-sample = in-sample now**: on ten mid-gap couplings chosen to be
  maximally far from every training beta, raw spurious-charge excess is 2.56 —
  *identical* to the trained-adjacent value. In v5 (grid training) these were
  4.57 vs 3.26. Continuous-beta training removed the distinction.

## 3. Cost vs plain HMC: thermalization

Yardsticks per case: 2 tau_int = trajectories plain HMC pays *per independent
configuration, forever*; burn-in = its one-time entry cost. t_therm = HMC
trajectories a raw diffusion seed needs to pass \|z\| <= 2 on the slowest
Wilson observable (chain-count matched).

| regime | raw-seed t_therm | plain-HMC interval | plain-HMC burn-in (hot/cold) |
|---|---|---|---|
| beta_f <= 10 | 2-21 | 2.7-15 | 7-200 / 9-108 | 
| **beta_f 10-70** | **0-24 (seeds win 10/13)** | 9-35 | never / 140-600 |
| beta_f >= 78 | never (raw); pipeline fine | 16-82 | never / 200-never |
| L=64, L=128 at beta 14.15 (v3 ckpt) | 1 / 1 | 37 / 61 | never / ~300-470 |

- In the ladder's working zone (beta_f ~ 10-70) a raw seed is worth its cost
  before HMC has produced *one* independent configuration — and unlike any
  fresh HMC chain it starts in the correct topological sector (hot starts
  never recover; cold starts never leave Q = 0).
- The volume trend is the strongest cost result: at L = 128 one independent
  plain-HMC configuration costs ~60x more than thermalizing a seed.
- Honesty rows: at beta_f <= 10 plain HMC is simply good — nothing to win; and
  at the time of the main campaign, raw seeds above beta_f ~ 78 needed the
  pipeline's retherm sweeps. SUPERSEDED by section 6: with the exact-score
  blend the never-zone is gone — raw seeds thermalize in 0-12 trajectories at
  every coupling to 872.8.

## 4. Improvement ledger (v2 baseline -> v6)

| metric | v2 (2026-07-08) | v6 (2026-07-19) |
|---|---|---|
| validated coupling reach (vs exact) | beta_f = 218.6 | **beta_f = 872.8** |
| training->deployment extrapolation | 4x | **15x** |
| raw spurious Q^2 excess (model-level) | 4.67 | **2.56 (-45%)** |
| out-of-sample penalty (raw topology) | untested | **zero** (2.56 = 2.56; v5 measured the gap: 4.57 vs 3.26) |
| crossover <Q^2> (2 -> 6.105) | swung -4.2..+3.4 sigma across retrains | -0.9 / -0.06 +- 0.36 with seed error bars (swings shown to be seed noise) |
| raw-seed never-zone | beta_f ~ 16-30 (and above) | none below beta_f ~ 78 |
| seeds beat HMC interval | 2 couplings | 10 of 13 in beta_f 10-70, in/out-of-sample alike |
| checkpoint comparability of the study | none (RNG-coupled, Q pinned) | per-case seeds + raw metrics + OOS/extrapolation tracks |
| training coupling coverage | 6-point grid | continuous log-uniform [1, 60] + sector-augmented anchors |

## 5. Post-campaign diagnostics (2026-07-19, log: `diag_run.log`)

**(a) The large-volume KS caveat traced to the references, not the model.**
The L >= 64 Q-hop reference ensembles were regenerated cold with burn-in 5000
(campaign references used far less), scored against exact, and the cached
generated ensembles re-KS'd against the new references:

| case | old ref z vs exact | burn-5000 ref z | generated KS vs new ref |
|---|---|---|---|
| L=64, beta=14.15 | -1.20 | -0.36 | **every Wilson loop passes**; only Q / chi_top fail |
| L=128, beta=14.15 | +2.94 | -3.05 | marginal only: plaq p=0.022, W(8x8) p=0.012 |
| L=64, beta=218.6 | +12.11 | +4.30 (still biased) | unreliable in both directions |

- At beta = 14.15, L = 64 the "per-mil small-loop shape failure seen at every
  L >= 64 test since v2" **disappears entirely** once the reference is
  properly thermalized. The surviving Q / chi_top KS failures are by
  construction, not defects: the pipeline's per-config sector sequence is
  inherited from the coarse level and charge-enforced rather than Q-hop
  sampled, while the Q *moments* themselves pass vs exact.
- At L = 128 the residual failures sit at p ~ 0.01-0.02 — the same order as
  the references' own scatter: the old and new reference straddle the exact
  plaquette at roughly +3 / -3 sigma. KS at this resolution tests the
  reference as much as the model.
- At beta = 218.6, L = 64 no affordable HMC reference is exact-quality: after
  5000 burn-in trajectories the reference is still +4.3 sigma off the exact
  plaquette (was +12.1) and its slowest large-loop modes remain under-relaxed,
  so KS flips failures between loop sizes depending on burn-in.

Consequence adopted for validation policy: **at L >= 64 and/or beta >~ 200,
exact character-expansion tests are the standard; KS-vs-HMC is reported but
bounded by reference quality.** The regime where the reference sampler itself
cannot reach exactness at any affordable budget is precisely the regime this
ladder exists for — there the generated ensembles (which pass every exact-mean
test) are arguably *better* than anything available to compare them against.

**(b) The raw-seed wall at beta_f >~ 78 is small-sigma score accuracy, not the
sampling noise floor.** Sampling-time A/B at beta_f = 218.6 and 872.8: lowering
the floor coefficient 0.3 -> 0.1 and adding a second corrector step each cut
raw smallest-loop |z| by 30-50% (e.g. plaquette z -98 -> -68 -> -52 at 218.6),
but nothing collapses to O(1), and the extra corrector step *worsens* the
plaquette at 872.8 (-104 -> -114). The pipeline's 16 rethermalization sweeps
remain the correct mechanism above the wall; the identified training-side
lever for a future run is oversampling small sigma at high beta.

## 6. Exact-score blend: the raw-seed wall is gone (2026-07-19 evening)

Following the section-5 diagnosis (the wall was small-sigma score accuracy), the
sampler now blends the model score into the ANALYTIC score of the noised Wilson
target as sigma -> 0: weight w = 1/(1 + (sigma sqrt(beta))^2), drift =
plaquette curl of -beta_eff sin(theta_p) with beta_eff = beta/(1 + 4 beta
sigma^2) (the exact Gaussian-smeared precision; 4 links of noise per
plaquette). Zero learned parameters, zero data: the small-sigma endgame is
Langevin dynamics under the true action — asymptotically exact MCMC at any
coupling, trained or not. Recipe: `--physics-blend 1.0 --sigma-floor-coef 0.1`
(the deeper sampling floor is only safe *because* the exact score owns that
region; without the blend it amplifies model bias). Full rerun of all study
parts A-F (two seeds on E/F) + the thermalization scan:
`generalization_blend/`.

- **Raw UV bias essentially eliminated.** Raw pre-retherm plaquette lands
  within ~5e-5 of exact where v6 was off by ~5e-3 (e.g. beta_f = 178.5:
  0.99119 -> 0.99714 vs exact 0.99719); at beta 218.6 / 872.8 the raw
  smallest-loop z went from -98 / -131 to O(1).
- **The raw-seed never-zone no longer exists.** t_therm (slowest Wilson
  observable) at beta_f = 78.5 / 118 / 138 / 158 / 178 / 218.6 / 398 / 873:
  v6 = never at every one; blend = 5 / 6 / 0 / 12 / 0 / 0 / 0 / 0. At L = 64,
  beta 218.6: never -> 2. Raw samples at 15x the training coupling now arrive
  effectively thermalized; the retherm stage is a no-op safeguard there.
- **Everything still passes vs exact, including the volume scan.** All 38
  cases pass the pipeline tests (|z| <= ~2, P(Q) chi^2 where testable), now
  including C_L64 (+0.47) and C_L128 (+0.97) at the new checkpoint.
- **Honest trade-off:** the pre-enforcement spurious-Q^2 excess (model-level
  topology transport, no charge enforcement) worsens moderately (e.g. part A
  2.30 -> 7.45, part E 2.56 -> 3.83): the pure action score does not carry the
  learned topo-penalty's suppression of winding defects, and the action is
  locally blind to a formed winding. The pipeline's deterministic charge
  enforcement + in-sampler projection make this irrelevant downstream (all
  post-pipeline Q^2 and P(Q) tests above pass), but raw-metric comparisons
  between checkpoints must use matching blend settings. Low beta (< ~5) also
  gains nothing (the harmonic limit is poor there and plain HMC was already
  winning); a beta-gated blend is the obvious refinement.

## 7. One-paragraph claim (safe to quote)

A single conditional diffusion model, trained once on couplings beta in [1, 60]
and lattices up to L = 32, generates gauge-field ensembles whose Wilson loops
and topological-charge distributions match exact results across beta_f = 1.5 to
872.8 and volumes to L = 64 — means everywhere, and full distribution shapes
at L = 64 once the HMC reference is itself properly thermalized (L = 128
validated at the previous checkpoint) — including regimes where standard HMC's
topology is provably
frozen (zero tunnelings, exp(-2 beta) suppression) and its Q distribution is
unfixably wrong from either standard initialization. With the exact-score blend
(a zero-parameter, physics-derived drift that hands the small-noise endgame to
the analytic Wilson score), raw samples arrive effectively thermalized at every
coupling tested — 0-12 plain-HMC trajectories to pass every Wilson observable
from beta_f = 6 to 872.8, where fresh HMC chains need hundreds of trajectories
or never thermalize at all.

Artifacts: `generalization/verdict.md` (all numbers), `showcase.png` (one-look
figure), `report.md` (v6 campaign detail), predecessor reports under
`out/diffusion/demo/generalization_v{3,4,5}/`.
