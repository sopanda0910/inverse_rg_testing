# Inverse-RG Conditional Diffusion for 2D U(1) Lattice Gauge Theory

A research codebase that trains a **conditional diffusion model to invert one
renormalization-group step** for 2D compact U(1) pure gauge theory: given a
coarse-lattice gauge configuration at lattice spacing `2a`, sample a fine-lattice
configuration at spacing `a`. Iterating the learned step turns a cheap coarse HMC
ensemble into ensembles at very fine spacing, **evading critical slowing down and
topological freezing** of direct fine-lattice HMC.

## Physics setup

- **Theory**: 2D compact U(1) on a periodic `L x L` lattice; link variables are
  angles `theta_mu(x) in (-pi, pi]`, `U_mu(x) = exp(i theta_mu(x))`.
- **Conventions**: fields are
  `theta[mu, x, y]` / `theta[B, mu, x, y]`, `mu = 0` are x-links; the plaquette is
  `theta_p(x,y) = theta_x(x,y) + theta_y(x+1,y) - theta_x(x,y+1) - theta_y(x,y)`,
  always wrapped to `(-pi, pi]` via `atan2(sin, cos)`.
- **Actions**:
  - Wilson: `S = -beta sum_p cos(theta_p)`
  - Villain (heat kernel): per-plaquette weight `sum_n exp(-beta/2 (theta_p + 2 pi n)^2)`.
    Under our 2x2 blocking the Villain theory renormalizes **exactly** within its
    family: `beta -> beta / 4`. This pins down the rung structure and is used as a
    correctness anchor throughout the tests.
- **Topological charge**: `Q = (1/2 pi) sum_p theta_p` with each `theta_p` wrapped:
  an exact integer on every configuration.

### Exact results used for validation (`lgt/exact.py`)

Everything follows from the character expansion (`Z = sum_q c_q^V`, `c_q` the
Fourier coefficients of the single-plaquette weight; `r_q = c_q / c_0`):

| Quantity | Formula |
|---|---|
| Mean plaquette (infinite V) | Wilson: `I_1(beta)/I_0(beta)`; Villain: `exp(-1/(2 beta))` |
| Mean plaquette / Wilson loop, finite V | `<W(A)> = sum_q r_q^{V-A} r_{q+1}^A / sum_q r_q^V` |
| String tension (exact area law) | `sigma = -log r_1`; every Creutz ratio equals `sigma` |
| Topological charge distribution, finite V | `P(Q) ~ int dk e^{-2 pi i k Q} psi(k)^V`, `psi(k) = <cos k theta>_f` (plaquettes i.i.d. subject to the global constraint `sum_p theta_p = 2 pi Q`) |
| Topological susceptibility | infinite V: `<(theta_p / 2 pi)^2>_f`; finite V from `P(Q)` |

## Pipeline

1. **HMC** (`lgt/hmc.py`): batched Omelyan HMC (vectorized over parallel
   chains) produces ensembles at
   cheap rungs. Optional **instanton updates** (global `Q -> Q +- 1` Metropolis
   moves through the smooth torus instanton, `dS = O(beta/V)`) keep reference
   topology ergodic at couplings where plain HMC is frozen.
2. **Forward blocking** (`lgt/blocking.py`): fixed gauge-covariant 2x2 decimation
   (coarse link = product of the two straight fine links). The coarse plaquette
   is exactly the wrapped sum of the four fine plaquettes in the cell. Coarse
   coupling: `beta/4` exactly for Villain; for Wilson, `match_coarse_beta`
   determines it nonperturbatively by matching the blocked mean plaquette to the
   exact finite-volume formula (`approx_matched_*` give the analytic i.i.d.
   estimate `r_1(beta_c) = r_1(beta_f)^4`, used to build ladder schedules).
   Mean-plaquette matching is not an arbitrary single-observable choice: the
   Wilson weight is a one-parameter exponential family with sufficient statistic
   `sum_p cos theta_p`, so it is the maximum-likelihood / minimum-KL projection
   of the exactly known blocked theory (`r_q -> r_q(beta_f)^4`) onto the Wilson
   family, and it preserves every fundamental Wilson loop and the string tension
   (`<W(A)> = r_1^A`). What one coupling cannot also fix (`r_{q>=2}`, `chi_t`,
   distribution shape) is quantified exactly by `matching_residuals` and mapped
   across couplings by `scripts/10_beta_matching_study.py`; the `chi_t` residual
   peaks at ~6% in the crossover `beta_f ~ 5-6.5` and is `<~ 2e-2` at the ladder
   rungs. `match_coarse_beta(..., n_characters=n)` offers a multi-character
   least-squares alternative for diagnostics, deliberately not the default.
3. **Conditional diffusion** (`model/`): `p_theta(fine | coarse invariants, beta)`
   — the core deliverable (details below).
4. **Ladder deployment** (`pipeline/ladder.py`): HMC at the coarsest rung ->
   conditional generation up one rung -> **mandatory short rethermalization**
   (heatbath / Metropolis + overrelaxation sweeps at the target beta; UV modes
   only, so a few sweeps suffice) -> repeat. Observables are logged per rung so
   bias drift is visible.
5. **Validation** (`validate/`): every generated rung vs exact formulas and vs
   held-out direct-HMC ensembles: plaquette + angle histograms, Wilson loops /
   string tension / Creutz ratios, `P(Q)` and `chi_top`, plaquette two-point
   correlators, jackknife/binning errors, `tau_int` (Madras-Sokal), KS and
   chi-square tests, z-scores in a markdown summary table plus plots.

## Diffusion model design

**Compact variables.** Diffusion runs on the torus, never on raw angles in R:
the forward kernel is the **wrapped Gaussian** `theta_t = wrap(theta_0 + sigma(t) z)`
with a geometric (variance-exploding) `sigma(t)`; at `sigma_max = 6` the state is
uniform on the circle to ~1e-8. Training is denoising score matching with the
exact wrapped-normal score (winding-weighted; `model/wrapped.py`), and sampling
is ancestral SMLD with optional Langevin correctors, wrapping after every step
(`model/sampler.py`). The machinery is verified standalone on the single-plaquette
distribution (`scripts/00_toy_wrapped_diffusion.py`).

**Exact gauge covariance by construction** (`model/score_net.py`):

- The network consumes only **gauge-invariant channels** of the noisy fine links
  (cos/sin of plaquettes and 1x2 / 2x1 rectangles) — never raw angles.
- The output is one scalar per plaquette, mapped to links by the lattice curl
  `s_mu(x) = sum_p h_p d theta_p / d theta_mu(x)`. This makes the score **exactly
  gauge-invariant and exactly orthogonal to gauge orbits**. It is also the correct
  function class: the target conditional density is a function of fine plaquette
  angles only, and the wrapped heat kernel preserves that property at every noise
  level. (`h_p = -beta sin theta_p` reproduces the exact Wilson force — covered by
  a unit test, and exploited as a gated analytic term in the head so the
  small-sigma score is nearly exact from the start of training.)
- **Conditioning**: the coarse lattice enters only through gauge-invariant
  features (cos/sin of coarse plaquettes and coarse 2x2 loops) upsampled onto the
  fine grid (each coarse site covers its 2x2 fine cell — the coarse plaquette sits
  exactly on the four fine plaquettes it constrains), concatenated at the input.
  `log beta` and `log sigma` enter through sinusoidal embeddings driving FiLM
  modulation in every residual block. No gauge relation is imposed *between* the
  lattices (independent gauge groups).
- Fully convolutional with circular padding: translation equivariant, runs on any
  `L`; a single model serves all rungs.

**How topology survives the ladder**: with straight-path blocking the coarse
plaquette equals the wrapped sum of its four fine plaquettes, so `Q` is (up to
exp-small wrapping events) inherited from the coarse configuration. Two
mechanisms enforce this in generation:

1. *Blocking-consistency guidance* (`pipeline/ladder.py`): a reconstruction-
   guidance score pulling each 2x2 cell's fine-plaquette sum toward its coarse
   plaquette angle, with noise-matched strength `lambda(sigma) ~ 8 sigma^2`,
   assembled through the same gauge-covariant curl head as the model score.
2. *Structural sector enforcement*: guidance alone provably cannot repair a
   wrong topological sector — the total wrapped plaquette sum is invariant under
   link deformations until a plaquette crosses +-pi (an exact zero mode of any
   curl-type force), and a wrong global `Q` unit smears into a smooth instanton
   costing only `O(beta/V)` action, far below what a learned score can resolve.
   So after sampling, `Q_fine` is set to `Q_coarse` by adding the smooth-
   instanton difference — a deterministic, gauge-covariant map that uses only
   the conditioning input (exact when plaquettes are concentrated, beta >~ 4).

The base rung is simulated where topology is cheap to decorrelate (with
instanton Metropolis updates), and the ladder transports the correct `P(Q)` to
fine rungs where direct HMC is frozen — rethermalization is deliberately run
*without* topological updates so this test stays honest: retherm cannot create
or destroy charge at large beta, it only fixes UV modes within the sector.

## Layout

```
diffusion/
  lgt/            lattice ops, Wilson/Villain actions, batched HMC, heatbath /
                  overrelaxation / instanton updates, blocking + beta matching,
                  exact analytic formulas
  model/          wrapped-Gaussian kernel + score, noise schedule, gauge-covariant
                  score network, DSM training loop (EMA, cosine LR), SMLD sampler
  pipeline/       generate_ladder: iterated generation + rethermalization
  validate/       observables, statistics, report generation
  scripts/        00 toy check, 01 data, 02 train, 03 ladder, 04 validate
  configs/        default.yaml (full), demo.yaml (~1-2 h CPU), smoke.yaml (minutes)
  tests/          pytest suite
```

## Running

From the repository root (venv already set up; on Windows use
`.venv/Scripts/python.exe`, on Unix `.venv/bin/python`):

```bash
python diffusion/scripts/00_toy_wrapped_diffusion.py          # machinery check
python diffusion/scripts/01_generate_data.py --config diffusion/configs/demo.yaml
python diffusion/scripts/02_train.py         --config diffusion/configs/demo.yaml
python diffusion/scripts/03_run_ladder.py    --config diffusion/configs/demo.yaml
python diffusion/scripts/04_validate.py      --config diffusion/configs/demo.yaml

pytest diffusion/tests -q                                     # unit tests
```

Outputs land under `artifacts/diffusion/<run>/`: ensembles (`.pt` with metadata:
beta, L, action, provenance), checkpoints, `validation/report.md`, and one figure
per rung (plaquette-angle histogram, `P(Q)` vs exact, Wilson-loop area law,
plaquette correlator) plus the ladder drift plot and `freezing.json`.

Everything is seeded and configured through YAML; ensembles/checkpoints are
cached on disk, so scripts can be re-run incrementally. CUDA is used when
available (`device: auto`); all tensor code is batched.

## Validation criteria

- Per-rung table: each observable's mean +- error, exact value, z-score vs exact,
  reference-HMC value, z-score vs reference, KS p-value (two-sample) and
  chi-square p for the `Q` histogram. |z| <~ 2-3 and non-tiny p-values pass.
- Ladder drift plot: plaquette z-scores should stay O(1) across rungs (retherm at
  every rung prevents compounding).
- **Headline test**: at the top rung (large beta, e.g. L=32, Wilson beta ~ 14),
  `04_validate.py` measures `tau_int(Q)` of a direct HMC chain — reported as
  frozen when the chain never tunnels — and compares the direct (frozen, wrong)
  `Q` histogram against the ladder ensemble and the exact finite-volume `P(Q)`.
  Success = the ladder reproduces `P(Q)` where HMC cannot.

## Notes / conventions chosen

- Blocked-vs-direct coarse matching for Wilson uses the mean plaquette; the
  blocked theory is not exactly Wilson-form, so small residual differences in
  higher loops are expected and absorbed by rethermalization.
- Reference ensembles for validation are generated *without* instanton updates
  (honest "what plain HMC gives you" baseline); training-data ensembles use them
  so that the model learns the correct topological statistics.
- `tau_int` uses the Madras-Sokal windowing (`c = 6`); errors on means use
  binning (20 bins) or jackknife.
- Wilson loops are measured for all `R x T` in the config list on every
  configuration via wrapped path sums (`lgt/lattice.py` conventions).
