# The Physics, Walked Through

*A step-by-step defense of the 2D U(1) result: what the physics says, which
parts are exact, which parts are learned, which parts are measured, and exactly
where each claim stops being true.*

Written 2026-08-03, after the U(1) study closed.

---

## How to read this, and how it differs from the other documents

Three documents cover this study, and they answer different questions:

| Document | Question it answers |
|---|---|
| `docs/NARRATIVE.md` | *How does this work?* — the full derivation chain, ground up, readable without lattice background. |
| `out/u1_2d/paper_appendix/appendix.md` | *What did we measure?* — the results of record: 27 figures, 7 tables, the reporting protocol. |
| **this file** | *Why should anyone believe it?* — every claim traced to its warrant, with the failure mode of each. |

The organizing idea here is a **status tag** on every statement. This project's
central hazard is that the exact parts and the learned parts sit adjacent to
each other and read alike in prose. Sorting them is most of the defense:

| Tag | Meaning | If challenged |
|---|---|---|
| **[ALGEBRA]** | True by identity on *every* configuration, to floating point. | Run the check. It either holds or the code is broken. |
| **[SOLVABLE]** | True because 2D U(1) has closed-form answers. | Holds here; **does not transfer** to the target theory. |
| **[LEARNED]** | Produced by the trained network. | Can be wrong; quantified below. |
| **[IMPOSED]** | Supplied by structural machinery, not by the model. | Correct by construction; needs an ingredient. |
| **[MEASURED]** | An empirical number with an error bar. | Cite the number and the provenance. |

Every **[ALGEBRA]** claim below is verified by
[29_verify_identities.py](../u1_2d/scripts/29_verify_identities.py), which runs
in seconds and prints pass/fail per identity. Its output as of this writing is
reproduced in the [appendix](#appendix--the-exact-identities-verified). Run it
before defending any of this out loud.

> **A repo fix made while writing this.** The editable install in `.venv` still
> mapped the pre-restructure package names (`diffusion`, `diffusion_v2`), so
> **every** script in `u1_2d/scripts/` raised `ModuleNotFoundError` when run
> directly — including the ones that regenerate the appendix. Fixed by
> reinstalling (`pip install -e . --no-deps --no-build-isolation`). Worth
> knowing before anyone tries to reproduce a table.

---

## 0. The claim, in one paragraph

At large $\beta$ (near the continuum limit) the standard sampler for this
theory freezes: local Monte Carlo cannot change the topological sector, and
the resulting ensembles are *silently* wrong — every short-distance observable
looks perfect while the topology is stuck. This project samples cheaply at
**small** $\beta$ on a **small** lattice, where nothing freezes, and then runs
the renormalization group *backwards* with a learned conditional diffusion
model, doubling the lattice and quadrupling the coupling at each rung. The
generated ensembles reproduce exact analytic results across 38 cases spanning
$\beta = 1.49$ to $872.8$ and $L$ up to $128$, at a cost per configuration that
is **flat in $\beta$**, against a classical baseline whose entry cost diverges
and then stops reaching correctness at all. The generated distribution is
*not* the Boltzmann distribution — the gap is measured at $\approx 1$ nat per
site — so correctness is supplied by exact Markov-chain machinery wrapped
around the model, not by the model itself.

Everything below is the defense of that paragraph, sentence by sentence.

---

## Part A — The target: what we are sampling, and why it is hard

### A1. The problem is sampling, not integration

Every prediction is an expectation over field configurations weighted by
$e^{-S(U)}$. The configuration space has $2L^2$ dimensions ($8192$ at $L=64$),
so quadrature is out and Monte Carlo is the only survivor — its $1/\sqrt{n}$
error is dimension-independent, *provided you can draw the samples*. That
proviso is the whole subject. Nothing in this project improves an estimator;
everything improves a sampler.

### A2. Degrees of freedom live on links; physics lives in plaquettes

A configuration is `theta[2, L, L]`: one angle per link, $\mu = 0$ for
$x$-links and $\mu = 1$ for $y$-links. The elementary gauge-invariant object
is the **plaquette** — the total phase picked up going around one unit square:

$$
\theta_p(x, y) = \theta_x(x, y) + \theta_y(x{+}1, y) - \theta_x(x, y{+}1) - \theta_y(x, y),
$$

wrapped into $(-\pi, \pi]$. The Wilson action rewards small flux,
$S = -\beta \sum_p \cos\theta_p$, so large $\beta$ means a stiff, ordered field
(the continuum limit, and the regime we want) and small $\beta$ means a
disordered field (easy to sample). Implementation:
[lattice.py:29](../u1_2d/lgt/lattice.py#L29).

### A3. Gauge invariance: half the coordinates are fictitious — **[ALGEBRA]**

A gauge transformation shifts every link by the difference of a free angle at
its endpoints, $\theta_\mu(x) \to \theta_\mu(x) + \alpha(x) - \alpha(x + \hat\mu)$.
Around any closed loop those shifts telescope to zero, so every plaquette — and
therefore the action and every observable — is untouched.

**Why this is architectural and not decorative.** With $L^2$ free $\alpha$'s
against $2L^2$ link variables, roughly *half* of every configuration is
physically meaningless. A model treating raw links as data spends half its
capacity memorizing a coordinate choice. This single fact dictates the network
design in C4.

*Verified:* under a random gauge transformation at every site, $\max|\Delta\cos\theta_p| = 7.8\times10^{-16}$
and $\max|\Delta Q| = 1.3\times10^{-15}$.

### A4. Topological charge is an exact integer — **[ALGEBRA]**

$$
Q = \frac{1}{2\pi}\sum_p \theta_p, \qquad \text{each } \theta_p \text{ wrapped}.
$$

The subtlety that makes this work: *unwrapped*, the sum telescopes to exactly
zero, because each link appears in two plaquettes with opposite sign. Wrapping
breaks the telescope — each plaquette silently contributes $2\pi n_p$ — so
$Q = \sum_p n_p$ is an **integer identically**, on every configuration, not
approximately and not statistically.

*Verified:* on random configurations, $Q \in \{-3, +5, +3, -5\}$ with
$\max|Q - \mathrm{round}(Q)| = 0$ exactly.

**Why this is the villain.** Changing $Q$ requires some plaquette angle to swing
across $\pm\pi$, where it contributes $+\beta$ instead of $\approx -\beta$. The
barrier is $O(\beta)$, so the tunneling rate falls *exponentially* in $\beta$
and any local sampler freezes into one sector. The insidious part — and the
reason this needs saying to a referee before anything else — is that a frozen
chain looks *perfectly healthy*: plaquettes, short correlators, all correct,
while $P(Q)$ is silently wrong. This is not a hypothetical; it is the published
result of Schaefer–Sommer–Virotta (NPB 845, 93), that Wilson loops decouple
from the slow topological modes.

### A5. 2D U(1) is exactly solvable — **[SOLVABLE]**

This is the entire reason for the choice of testbed. The plaquette angles
decouple, so everything reduces to Fourier coefficients of the single-plaquette
weight — ratios of modified Bessel functions $r_q(\beta) = I_q(\beta)/I_0(\beta)$:

- mean plaquette $\langle\cos\theta_p\rangle = r_1(\beta)$;
- Wilson loop of area $A$: $\langle W(A)\rangle = r_1^A$ — the exact area law;
- $P(Q)$ from a characteristic-function inversion;
- $\chi_t = \langle Q^2\rangle / V$.

*Verified:* $\langle W(A)\rangle / r_1^A - 1 = 0$ to machine zero at
$\beta = 4$ and $55.02$, for $A = 4$ and $16$. Implementation:
[exact.py](../u1_2d/lgt/exact.py).

**What this buys, and what it costs.** Every z-score in this study is against
*closed-form truth*, not against another simulation that might share the same
bug. That is what makes the negative results in Part D trustworthy negatives
rather than ambiguities. The cost is that four separate ingredients —
exact observables, exact $P(Q)$, exact $\Delta F$, exact blocked characters —
are **crutches that do not exist in 4D SU(3)**. Track them; they are itemized
in F1.

---

## Part B — The mechanism: why running the RG backwards is legitimate

### B1. The blocking telescope — **[ALGEBRA]**

A coarse link is the wrapped sum of the two fine links along its path. The
geometric fact everything downstream rests on:

> **A coarse plaquette angle equals the wrapped sum of the four fine plaquette
> angles in its $2\times2$ cell.**

Interior fine links cancel in pairs — the same telescope as gauge invariance.

*Verified:* $\max|\theta_P^{\text{coarse}} - \mathrm{wrap}(\sum_{\text{cell}}\theta_p)| = 1.3\times10^{-15}$.
Implementation: [blocking.py:55](../u1_2d/lgt/blocking.py#L55).

Two consequences follow immediately: the coarse plaquette aggregates four fine
fluctuations so it fluctuates *more* (the coarse theory is more strongly
coupled — B2), and $Q$ passes down to the coarse lattice essentially intact
(B3).

### B2. Coupling matching: tree level is not good enough — **[SOLVABLE]**

The textbook relation is $\beta_c = \beta_f / 4$: variances add, four
plaquettes, $\mathrm{Var}(\theta_p) \approx 1/\beta$. **This is wrong at the
couplings the ladder actually uses**, and getting it right matters.

Because blocked plaquettes are wrapped sums of i.i.d. fine plaquettes and
wrapped convolution multiplies Fourier coefficients, the blocked theory's
characters are known exactly: $r_q^{\text{blocked}} = r_q(\beta_f)^4$. The
matched coupling is then fixed by $r_1(\beta_c) = r_1(\beta_f)^4$ — which is
simultaneously the maximum-likelihood fit and the minimum-KL projection of the
blocked theory onto the one-parameter Wilson family (the Wilson weight is an
exponential family with sufficient statistic $\sum_p\cos\theta_p$, so matching
the mean plaquette *is* the MLE).

*Verified, and the size of the error:*

| $\beta_f$ | tree level $\beta_f/4$ | exact matched $\beta_c$ | tree-level error |
|---|---|---|---|
| 14.1464 | 3.5366 | **3.999989** | 13.1% |
| 55.0237 | 13.7559 | **14.146405** | 2.8% |

Two things to notice. First, a 13% coupling error at the bottom rung is not a
rounding detail — it is the difference between conditioning the model on the
right theory and the wrong one. Second, **the matched values reproduce the
ladder schedule exactly**: $55.0237 \to 14.1464 \to 4.0$. The ladder is a
self-consistent chain under exact matching, not a hand-tuned sequence.

For the **Villain** action the relation $\beta_c = \beta_f/4$ *is* exact
(wrapped Gaussians, variances add with no truncation) — verified to
$10^{-15}$. That is what makes Villain usable as a control arm (D4).

### B3. The ladder, and why sector transport is an identity — **[SOLVABLE]**

The RG flows *toward* strong coupling, and strong coupling is where sampling is
easy. So run it backwards: HMC a small weakly-coupled base ($L=8$,
$\beta\approx1.35$ — seconds, no freezing anywhere), then lift
$L\to2L$, $\beta\to\approx4\beta$ repeatedly. **No step of the ladder ever
samples a frozen theory directly.**

The topological payoff is the design's actual justification, and it is worth
stating precisely because it is stronger than it first appears. "Blocking
preserves $Q$" is a statement about the *map*. What the argument needs is a
statement about the *measure*. It holds, for a clean reason:

$$
\langle Q^2\rangle \approx \frac{V}{4\pi^2\beta}
\qquad\text{is invariant under}\qquad
(V, \beta) \to (4V, 4\beta),
$$

which is exactly one ladder step. $\langle Q^2\rangle$ is a **fixed point of the
ladder**.

*Verified* on the exact finite-volume $P(Q)$ (Villain, where matching is exact),
four rungs from $L=8, \beta=1.3472$:

$$
1.20271 \;\to\; 1.20334 \;\to\; 1.20334 \;\to\; 1.20334
$$

— a relative drift of $5.2\times10^{-4}$ across the whole ladder.

Two readings, both load-bearing:

1. **Sector transport is exact at the level of the target.** The coarse
   ensemble's $P(Q)$ *is* the fine theory's $P(Q)$ — not an approximation that
   happens to be close.
2. **The ladder is a continuum-limit trajectory at fixed physical volume.**
   $\langle Q^2\rangle$ is held fixed while $L$ doubles and the lattice spacing
   shrinks. The endpoint ($L=64$, $\beta\approx55$) is *the same physical
   system, resolved 8× more finely* — which is precisely the limit where
   freezing is the obstruction. This is why the testbed is the right one.

### B4. What that identity does **not** license — **[MEASURED]**

This is the single most important scoping statement in the project, and the
place a referee will push hardest. The identity is about *distributions*. The
model's per-configuration behavior is a different question, and the
measurements separate them sharply:

| | status | value |
|---|---|---|
| Coarse $P(Q)$ is the right target | **[ALGEBRA/SOLVABLE]** | exact, drift $5\times10^{-4}$ |
| Model carries an individual config's charge | **[LEARNED]** | raw charge-match rate **0.21** |
| Transport-mode worst $|z(\langle Q^2\rangle)|$ | **[MEASURED]** | **11.8** |
| Raw $Q^2$ excess, $L \le 32$ → $L = 64/128$ | **[MEASURED]** | 1.7–2.7 → **7.1–28.2** |

So *"topology rides the ladder for free"* is **true of the target and false of
the transport**, and the excess **grows with volume**. The resolution is the
pipeline's actual design, and it should be presented as a design rather than a
patch: because the correct sector distribution is known exactly, the sector is
**[IMPOSED]** structurally — charge-conjugation-antithetic symmetrization plus
resampling from the exact finite-volume $P(Q)$ at the target coupling — rather
than trusted to the network. The model is asked for the expensive part (a
thermalized UV at the target coupling); it is *not* asked to be a topological
transport operator, and the measurements say it would fail if it were.

That is a coherent division of labour and only one half of it is exact. **The
cost is real and must be stated**: the structural route consumes the exact
$P(Q)$ that this solvable theory supplies and a 4D non-abelian target will not.
In 2D SU(2) the point is moot ($\pi_1$ trivial, no sectors); in 4D it is *the*
open problem this line inherits.

---

## Part C — The learned part

### C1. The forward process is the exact heat kernel on the circle — **[ALGEBRA]**

Noise must respect periodicity, or $-\pi$ and $\pi$ get treated as distant when
they are the same point. The forward process is
$\theta_t = \mathrm{wrap}(\theta_0 + \sigma z)$, whose transition density is the
**wrapped normal** — equivalently the heat kernel on U(1), with two equivalent
forms:

$$
K_\sigma(d) = \sum_{k\in\mathbb{Z}} \mathcal{N}(d + 2\pi k;\, 0, \sigma^2)
= \frac{1}{2\pi}\Big(1 + 2\sum_{q\ge1} e^{-q^2\sigma^2/2}\cos(qd)\Big),
$$

the first converging fast at small $\sigma$, the second at large $\sigma$.
Mode coefficients decay as $e^{-q^2\sigma^2/2}$, so at $\sigma_{\max} = 6$ the
kernel is uniform to $\sim10^{-8}$ — and uniform-per-link is the Haar measure,
containing zero physics. The process interpolates cleanly from physics to
noise. Implementation: [wrapped.py](../u1_2d/model/wrapped.py).

**Flag this as an abelian luxury.** Angles commute, so noise accumulates
linearly and the finite-time law is closed-form. For SU(3) it is not, and every
published approach approximates it. That approximation is the largest new
difficulty waiting past this testbed — and it is *why* the exactness route of
Part D is unavailable there in principle, not merely in practice.

### C2. The score is all you need — **[ALGEBRA]**

Anderson's theorem: the forward SDE's time reversal has a drift involving only
$s = \nabla\log p_t$. Since $\log p = \log(\text{unnormalized}) - \log Z$ and
the gradient kills the constant, **the intractable partition function never
appears**. That is why score methods are natural for physics.

### C3. Denoising score matching — **[ALGEBRA]**

The chicken-and-egg — we need $\nabla\log p_t$ but $p_t$ is the unknown — is
resolved by Vincent's identity: regressing on the *conditional* score
(closed-form, known) differs from regressing on the *marginal* score (unknown)
only by a constant. The mechanism worth holding onto: each training pair gives
a *noisy* arrow pointing back at its own $\theta_0$; the network, forced to
give one answer per noisy input, learns the *average* arrow — which is the true
score.

Three refinements that are physics, not hyperparameters:

- **Scaled score.** The net predicts $\sigma\cdot s$, which is $O(1)$ at every
  noise level; the raw score blows up like $1/\sigma$.
- **$\beta$-aware noise floor**, $\sigma_{\min}(\beta) = \min(\sigma_{\min}, c/\sqrt\beta)$.
  Physical link fluctuations shrink like $1/\sqrt\beta$; a *fixed* floor would
  at some $\beta$ become larger than the physics itself, and the model would
  stop resolving the target entirely.
- **Small-$\sigma$ oversampling at high $\beta$**, for the same reason.

### C4. The curl head: exactly the right function class — **[ALGEBRA]**

The network never sees raw links. Inputs are $\cos/\sin$ of plaquette and
rectangle angles, so *every internal activation is exactly gauge-invariant for
any weights*. The output is one scalar $h_p$ per plaquette, assembled as a
lattice curl:

$$
s_x(x,y) = h(x,y) - h(x,y{-}1), \qquad s_y(x,y) = h(x{-}1,y) - h(x,y).
$$

**Why exactly this.** By the chain rule, the gradient of *any* function of
plaquette angles is $s_\mu(x) = \sum_p (\partial F/\partial\theta_p)(\partial\theta_p/\partial\theta_\mu(x))$,
and $\partial\theta_p/\partial\theta_\mu(x)$ is $\pm1$ for the two plaquettes
containing that link — which is the stencil above with $h_p = \partial F/\partial\theta_p$.
The head does not *approximate* the right function class; it **parameterizes it
exactly and nothing else**.

*Verified:* setting $h_p = -\beta\sin\theta_p$ reproduces the exact Wilson score
$-\partial S/\partial\theta$ to $1.8\times10^{-15}$.

**The completeness argument, with its one honest caveat.** A gauge-invariant
function on a *periodic* lattice depends on plaquettes **and** on the two
holonomies (Polyakov loops) — plaquettes alone do not coordinatize the
gauge-invariant content of a torus. The saving facts: the Wilson density is
*uniform* in the holonomies (the action has only plaquettes), and the noising
kernel is a per-link translation-invariant convolution, which preserves both
gauge invariance and holonomy uniformity. So $p_t$ is a function of plaquettes
alone times a uniform holonomy factor at every noise level, its score has
exactly the curl form with zero holonomy component, and the curl head produces
zero there too. **The parameterization is complete, not merely contained.**

> **This is the property that failed first in SU(2)**, and the reason 2D SU(2)
> was chosen as the next step. There the noising couples neighboring plaquettes
> and their gradients lie *outside* the single-plaquette span: per-configuration
> least squares reaches only ~18% of the DSM target variance (~50% with
> rectangles). Completeness here is a genuinely abelian gift. See F4.

### C5. Topology transport machinery — **[IMPOSED]**

The learned score is local (finite receptive field); $Q$ is global. No amount
of training makes a local function reliably control a global integer. Three
structural mechanisms carry the sector instead:

- **Coarse-charge enforcement.** Add the smooth instanton field carrying
  $\Delta Q = Q_{\text{coarse}} - Q_{\text{fine}}$. Timing is deliberate: applied
  during *late* sampling — after the sector has effectively frozen, but while
  enough noise remains to relax the uniform strain of $2\pi\Delta Q/V$ per
  plaquette. *Verified:* the instanton field carries $Q = 1$ to $10^{-7}$ at
  cost $\Delta S = 1.06$ ($L{=}32$) and $0.25$ ($L{=}64$) at $\beta = 55$,
  against the predicted $2\pi^2\beta/V = 1.06$ and $0.27$ — small and shrinking
  with volume, which is why the hop stays cheap.
- **Blocking-consistency guidance**, with width $\lambda(\sigma) = 8\sigma^2$ —
  *derived, not tuned*: the blocked plaquette's boundary is eight fine links each
  carrying variance $\sigma^2$, so that is exactly how much the constraint should
  slack. One subtlety with teeth: the residual is deliberately **not wrapped**,
  because a wrapped residual is blind to a cell landing $2\pi$ away — precisely
  the failure mode that spawns spurious winding defects.
- **Rethermalization.** A few local heatbath/overrelaxation sweeps fix UV
  roughness. Under the project's honesty convention retherm performs **no**
  topological moves, so measured topology reflects what the model plus transport
  actually delivered — never what retherm manufactured
  ([local_updates.py:140](../u1_2d/lgt/local_updates.py#L140)).

**How much of the topology is the model's? None, and it gets worse with
volume** (measured 2026-08-14). "Imposed" is not a hedge here; it is the whole
of it. With enforcement disabled, the raw model lands in its coarse partner's
sector 4.7–29% of the time, and that *falls* with volume — 11.5% at $L = 64$,
6.2% at $L = 128$. Distributionally it is worse than that ratio suggests:
raw $\langle Q^2\rangle$ / exact is $\approx 1$ where the theory has plenty of
topology and then runs away exactly where it matters —

| case | $L$ | raw $\langle Q^2\rangle$ | after transport | exact |
|---|---|---|---|---|
| A_bc1 | 32 | 9.77 | 10.76 | 10.81 |
| A_bc4 | 32 | 4.70 | 1.63 | 1.90 |
| A_bc8 | 32 | 3.99 | 0.88 | 0.87 |
| E_bc11.8 | 32 | 3.12 | 0.57 | 0.57 |
| C_L64 | 64 | 19.01 | 6.22 | 7.62 |
| C_L128 | 128 | 80.64 | 27.56 | 30.46 |

— a $2.5$–$5.4\times$ excess at strong coupling and $2.65\times$ at $L = 128$.
The model *manufactures* topological charge precisely in the frozen regime the
method exists to reach, which is the direct empirical statement of the
locality argument opening this section. The diffusion model supplies
short-distance fluctuations; the sector is supplied by the B3 identity, and it
is correct because the ladder preserves $P(Q)$, not because anything learned it.

---

## Part D — Grading: the two claims, kept apart

The single most important structural fact about this study is that
**observable agreement and distributional correctness are different claims**,
and only the first is established. Conflating them is the easiest way for an
honest study to overclaim.

### D1. Graded on observables — **[MEASURED]**, and this claim stands

38 cases, $\beta_f$ from 1.49 to 872.8 (15× the training maximum of 60), $L$ to
128 (16× the largest training area), one checkpoint, no per-case tuning.

> **Check before quoting.** The appendix also describes $L = 128$ as "64× the
> smallest" training area. With training at $L = 8, 16, 32$ the smallest area is
> 64 and $128^2/64 = 256$, not 64 — the figure appears to assume $L = 16$ as the
> smallest. The "16× the largest" form is arithmetically clean ($16384/1024$)
> and is the one used here.

**"Matches exact" is an upper bound on bias, and the bound is tight.** With
$n = 64$–128 configs the median relative SEM on $\langle\cos\theta_p\rangle$ is
0.0087%, so passing $|z| \le 2$ means *"no bias above ~2 parts in $10^4$
detected"* — not "agreement". Three residuals are visible at that precision and
are reported rather than left implicit:

- **A coherent negative offset.** All 20 Wilson-type observables have mean
  $z < 0$ (plaquette $-0.423 \pm 0.204$). The ensembles are systematically very
  slightly *less ordered* than exact. Real systematic, not scatter.
- **Over-dispersion.** $\mathrm{std}(z)$ should be 1; measured 1.255 (plaquette)
  to 2.785 ($Q^2$).
- **The bias concentrates in extended observables.** $\mathrm{std}(z)$ grows
  monotonically with loop area, $1.093$ ($4{\times}4$) → $1.438$
  ($12{\times}12$), with $\max|z|$ rising $3.12 \to 5.91$.

That last item is the observable-side *shadow* of the density gap below — the
error lives in long-wavelength modes, exactly the modes local rethermalization
relaxes slowest. It is a **measured** bridge between D1 and D2, not a
conjectured one. And it is not an error-bar artifact: the coarse base has
$\tau_{\text{int}} = 0.50$–$0.62$, bounding inherited-correlation inflation at
$\le 1.12\times$, and $z_{\text{exact}}$ never involves a reference chain's errors.

**The cost claim, stated honestly.** The flat $\sim2.4$ s/config is a *marginal*
cost. The campaign that produced the checkpoint cost **8820 s once**, which
exceeds *every* instanton-HMC burn-in that converges; for a single ensemble at a
single coupling below $\beta\approx55$ the classical baseline is cheaper
outright, and the appendix says so. The defensible claim is about **scaling**:
generative cost is a fixed charge plus a $\beta$-independent marginal cost,
against a baseline whose entry cost diverges (8 s → 16 s → 1677 s → never) and
then stops reaching correctness.

### D2. Graded as a measure — **[MEASURED]**, and this claim fails

Flow-based samplers claim *provable unbiasedness* via importance weights. Can
this pipeline? Answering required building the machinery, and the answer is a
quantified no.

**The right weight.** For a conditional model, the naive joint weight carries
the coarse configuration's own probability mass ($O(e^V)$), so even a *perfect*
model would score $\mathrm{ESS} = 1/N$ — broken by construction. The correct
choice divides the coarse density out, which is legitimate because HMC samples
it *exactly*:

$$
\log w = -S_{\text{fine}}(x) + S_{\text{matched}}(c) - \log q(x \mid c).
$$

**Getting $q$.** Diffusion models don't hand you a density, but the
probability-flow ODE shares the same marginals while being deterministic, and a
deterministic flow has a computable density via the instantaneous
change-of-variables formula. The correction that made the weights *valid*
rather than merely suggestive: **sample the ODE itself**, accumulating the
divergence along the way, so each configuration emerges paired with the exact
density of the process that produced it. Evaluating a separately-drawn ensemble
would not be valid — the evaluation map is not the inverse of the sampling map
at finite step count.

**The instrument was validated before being pointed at the model**: on an
exactly solvable wrapped-Gaussian target it returns $\mathrm{ESS}/N > 0.5$, and
the free-energy certificate closes to $<0.02$ nats on synthetic exact weights.
Therefore any spread observed on the real model is *the model's density error*
— not estimator noise, not a bug. This calibration is what licenses every
negative below.

**The measurement.** Log-weight standard deviations of **18 / 42 / 84 / 164**
on the four standard cases, against a usability bar of $O(1\text{–}3)$.

**ESS stops reporting, so we replaced it.** Self-normalized ESS/N is bounded
below by $1/N$, and every case sits exactly there ($0.016 = 1/64$). That is not
a small ESS; it is an *unresolved* one — two proposals differing by an order of
magnitude in spread report the identical number. The fix is an identity: for
valid weights,

$$
\mathbb{E}_q[\log w] - \Delta F_{\text{exact}} = -\,\mathrm{KL}(q\|p),
$$

and $\Delta F$ is computable here from the character expansion **[SOLVABLE]**.
The *mean* log-weight is well-behaved precisely where the mean of $w$ is not, so
this turns a broken certificate into a direct measurement:
**$\approx 0.88$ nats/site at $16{:}55$ and $1.02$ at $32{:}218.6$** — i.e. 448
and 2098 nats per configuration.

This is, in my view, the most transferable methodological contribution in the
study, and it is worth leading with: *how to measure distributional correctness
after ESS has saturated.*

### D3. Why the dissociation had to happen

D1 and D2 look contradictory — plaquettes to $10^{-4}$, density off by 2098
nats — and reconciling them is the first thing anyone will ask.

They are consistent because low-order gauge-invariant observables are a
**very low-dimensional projection** of a $2L^2$-dimensional measure. A handful
of numbers cannot constrain a density. And the residual *is* detectable once
you look at extended observables (D1, third bullet), which is exactly where the
appendix says to look.

The physics literature has an independent statement of the same hazard —
Schaefer–Sommer–Virotta: Wilson loops decouple from the slow modes. So this
dissociation is not a quirk of this checkpoint; it is what one should *expect*
from a model trained on a local objective and graded on a few low-dimensional
projections. That published result should be cited exactly here.

### D4. The falsification chain, and the control that closes it

Six interventions, each converged with an identified mechanism:

| Intervention | Result | Mechanism |
|---|---|---|
| Sampling-time knobs | one win: $42 \to 24$ | endgame offset at $\sigma_{\min}$ |
| ML fine-tuning (197k params) | **worse everywhere** | forward/reverse-KL asymmetry |
| Single-case reverse-KL | destroys extrapolation (2202) | selection noise + overfit |
| Multi-case reverse-KL (guarded) | **halves spread everywhere** | kept; the one real win |
| Capacity/data scale-up (3.7×) | better in-range, worse out | small net *was* the regularizer |
| Per-level SMC | no gain | no weight diversity to harvest |
| Surrogate-bridge AIS | reaches its floor 8 seeds in 10, ESS flat | sector component won't regress; the 2 failures are integrator collapse, not fit |

The recurring mechanism is worth stating once, because it explains three
separate failures: **maximum likelihood optimizes the wrong direction of KL.**
The ML objective is an expectation *under the data* — it penalizes $q$ being
small where data lives, and is indifferent to where $q$ puts the rest of its
mass. Weight variance is governed by fluctuations *under the model*. The two
share a global minimum but away from it their gradients are not even positively
correlated. A finite-capacity model can sharpen onto the data manifold while
carving density away from the regions its own sampler visits — which is exactly
what was measured, at 197k parameters and again at **354**. So the asymmetry is
*intrinsic to the objective, not a capacity effect*. Project rule:
**validation likelihood is the wrong selection metric for ESS.**

**The control that converts exhaustion into closure.** One competing explanation
survives all six: the coarse conditioner is a *single-coupling* Wilson ensemble,
but the true blocked measure carries induced multi-coupling structure. That
mismatch would show up in the weights *without being the model's fault*.

Here the story has a wrinkle worth telling honestly, because it is a good
methodological lesson. The intended control was a Villain arm (exact blocking,
therefore no matching residual), read as the subtraction Wilson − Villain. It
**cannot** be read that way: correcting a bug in the arm made the Villain
spreads *larger* (+4%, +99%, +51%), because the corrected arm conditions the
Wilson-trained model at couplings it never saw. The arm measures model error
*plus* an out-of-distribution penalty.

The conclusion survives on **stronger, Villain-independent grounds**. A matching
residual is by construction a function of the coarse configuration *alone*.
Therefore it can contribute **only** to the coarse-explainable share of the
fiber log-weight variance, $R^2_c$ — and $R^2_c$ is measured directly *within a
single arm*, no cross-model comparison: **0.062, 0.005, 0.023** (and 0.003–0.064
in deployment settings). At most ~6% of the variance is coarse-explainable at
all, and even that is an upper bound because $c$-dependent *model* error lands
in the same regression. **The matching floor is negligible; the gap is fine-side
model error, in full.**

> **The transferable lesson.** When the effect of interest is small compared to
> model-to-model variation, prefer a **within-model decomposition** to a
> **cross-arm subtraction**. Table S5 shows same-architecture checkpoint
> variants moving spreads by 2–6×; an effect bounded at a few percent cannot be
> resolved by a comparison whose confounds are an order of magnitude larger.
> The $R^2_c$ regression costs one linear fit on data already in hand, has no
> confound, and gave the tighter answer.

---

## Part E — The defense: objections, answers, and residual risk

Ordered by how hard they bite. The third column is what I would *concede*.

| # | Objection | Answer | Residual risk |
|---|---|---|---|
| 1 | *Topology transport is the weak point and degrades with volume.* | Correct, and stated: raw match rate 0.21, $Q^2$ excess 1.7–2.7 → 7.1–28.2. It is rescued by exact-sector mode. | **Real.** The rescue consumes the exact $P(Q)$, unavailable where you'd need the method. This is the sharpest live criticism. |
| 2 | *The baseline already solves the advertised problem.* | Instanton-HMC $\langle Q^2\rangle$ is correct in *every* row of Table S1 — the failures are **UV thermalization**, not topology. | The headline regime is thermalization-limited. The incumbent remedy (Endres et al. multiscale thermalization) is uncited and uncompared. **Owed.** |
| 3 | *ESS is reported at its floor.* | Acknowledged and replaced by the KL readout (D2). | $N = 64$ should be re-run at $N \gg 64$ so the number is resolved rather than saturated. **Owed.** |
| 4 | *You claim exactness you don't have.* | The deployed pipeline applies **no accept/reject to the proposal**. It is a validated *heuristic*. The asymptotically exact mode is **seeding**. | None, if stated. This distinction must survive editing into any paper. |
| 5 | *The gap is understated in prose.* | Spreads are 15–164 nats against an $O(1\text{–}3)$ bar — a shortfall of $e^{100}$, not "an order of magnitude". | Prose must match Table S5. |
| 6 | *Mean $\|z\|$ = 1.77 vs reference implies mis-stated errors.* | Against *exact* values it is 1.06; the 1.77 is vs the HMC reference and includes its noise. | Report the exact-referenced number and say which is which. |
| 7 | *Priority: this has been done.* | Zhu et al. (JHEP 03 2026 111) do diffusion for 2D U(1) with $\beta$-extrapolation, size transfer, **and** MALA-based exactness. | **Serious.** All four advertised advantages are theirs. Frame on the *falsification program*, not the sampler. |

**The framing consequence of #7 is the most important editorial decision in the
project.** A paper framed *"we built a diffusion-based inverse-RG sampler"* is
exposed on priority. A paper framed *"inverse-RG generative samplers have never
been tested for distributional correctness; here is what happens when you do,
and here is the mechanism"* is novel, useful, and squarely what was established.
The strongest contribution here is a **negative result** — and it should be led
with, not buried.

---

## Part F — Where the physics stops transferring

### F1. The crutch ledger

Four **[SOLVABLE]** ingredients are load-bearing and none survive the trip to
4D SU(3):

| Crutch | Used for | Replacement in 4D |
|---|---|---|
| Exact observables ($r_q$, area law) | every z-score | none — validation itself becomes research |
| Exact finite-volume $P(Q)$ | *mostly a diagnostic, not a rescue* — see below | a short instanton-HMC tail; measured cost ≤ 150 traj |
| Exact $\Delta F$ | the KL measurement of D2 | none — only the spread remains measurable |
| Exact blocked characters | coupling matching (B2) | numerical matching, with its own error |

**The $P(Q)$ row was rewritten on 2026-08-14, and the demotion is the single
biggest change to this ledger.** It previously read "exact-sector mode, the
topology rescue / **none. This is the open problem.**" Three measurements
moved it:

*Transport already passes.* Regenerated from the current ensembles of record,
transport-mode $\chi^2$ against exact $P(Q)$ fails 3 of 35 cases against
exact-sector mode's 2 of 35 — both at the multiple-testing false-positive rate.
All three transport failures are the deliberately-mismatched track-B controls;
none is a volume case. At $L = 128$ transport gives $p = 0.87$ (the published
claim that it gives $0.005$ and passes *only* under exact-sector mode was
transcribed from a superseded run). What exact-sector mode still buys is a
tighter $\langle Q^2\rangle$ — worst $|z|$ $10.9 \to 2.8$ — and clearing the
track-B controls.

*The theory-agnostic replacement is cheap and does not scale.* Fixing $P(Q)$
with a short instanton-HMC tail needs, at fixed $\beta$ over a $16\times$
volume range, **100, 0, 0** trajectories at $V = 2048, 8192, 32768$ — while the
$\chi^2$ test's power *rises* (7, 11, 15 populated bins), so the falling cost
is not a resolution artifact. Across the $L = 32$ $\beta$-ladder the tail never
exceeds **150** trajectories. There is no scaling exponent to quote.

*Why this is structural rather than lucky.* It is the B3 identity doing the
work. Charge projection hands the fine configuration its coarse partner's $Q$,
and along the ladder $\langle Q^2\rangle \approx V/4\pi^2\beta$ is invariant, so
the coarse $P(Q)$ *is* the fine theory's. Sector correctness is inherited from
HMC at the coarse coupling, where HMC still mixes. Nothing in that argument
needs $P(Q)$ in closed form — only a computable topological charge, which 4D
SU(3) has.

**What has not moved.** At $\beta \gtrsim 55$ the $\chi^2$ has $\le 3$
populated bins, and at $\beta = 218.6$, $L = 32$ exactly one. In the
deep-frozen regime these tests have almost no power, and a "pass" there is
close to vacuous. That is a limit on the *test*, and it is now the honest
residual — not a dependency on the crutch.

### F2. What actually transfers

The load-bearing *structure*, all of which is theory-independent: the matched
ladder; the equivariant curl-form score; DSM on the group heat kernel; retherm-
based exactness; the guarded-checkpoint discipline; the AIS bridge (needs only
differentiable invariant features and an HMC kernel); and the honesty protocol
that converted every negative into a mechanism.

### F3. The design directive, read literally

> **Exactness must come from Markov-chain machinery wrapped around the
> generative proposal — Metropolis tails, seeded chains — not from the
> proposal's own likelihood.**

**Must**, not *does*. This describes what the successor has to be built around;
it is **not** a property the U(1) pipeline delivered. As deployed, the ladder
applies no accept/reject to the proposal — the only Metropolis moves are inside
local retherm sweeps and the instanton hop. Sixteen local sweeps reduce the
bias without removing it, and they are slowest precisely on the long-wavelength
modes where the residual sits. The exactness knob and the speedup knob are the
same knob. What *is* asymptotically exact is the **seeded** mode: exact HMC from
a diffusion configuration, correct within its sector, with the sector supplied
by the transport identity of B3.

### F4. The first thing SU(2) broke

Worth knowing, because it is the cleanest evidence that this testbed was chosen
correctly. The **curl-head completeness argument of C4 is abelian**. In SU(2)
the single-plaquette basis reaches only ~18% of the DSM target variance
(rectangles: ~50%; $2\times2$ adds nothing). Everything else — sampler,
coupling matching, continuous-$\beta$ training — was verified correct by
elimination. 2D SU(2) was picked to expose exactly this class of gap before 4D,
and it did so immediately.

---

## Appendix — the exact identities, verified

Output of `.venv/Scripts/python.exe u1_2d/scripts/29_verify_identities.py`,
2026-08-03. None of these involve the trained model; they either hold to
floating point or the argument above has a hole.

```
1. Q is an exact integer on every configuration (sec A4)
   Q = ['-3.000000000000', '+5.000000000000', '+3.000000000000', '-5.000000000000']
   [ok] max |Q - round(Q)|: 0.000e+00  (tol 1e-12)

2. Gauge invariance of the plaquette and of Q (sec A3)
   [ok] max |cos p(gauged) - cos p|: 7.772e-16  (tol 1e-12)
   [ok] max |Q(gauged) - Q|: 1.332e-15  (tol 1e-12)

3. Coarse plaquette = wrapped sum of its four fine plaquettes (sec B1)
   [ok] max |P_coarse - wrap(sum of 4 fine)|: 1.332e-15  (tol 1e-12)

4. Curl head spans exactly the Wilson score, h_p = -beta sin(theta_p) (sec C4)
   [ok] max |curl(h) + dS/dtheta|: 1.776e-15  (tol 1e-12)

5. <Q^2> is a fixed point of the ladder, (V, beta) -> (4V, 4beta) (sec B3)
   <Q^2>: 1.20271 -> 1.20334 -> 1.20334 -> 1.20334
   [ok] relative drift rung 1 -> rung 4: 5.195e-04  (tol 1e-03)

6. Villain blocking is exactly beta_f/4; Wilson is not (sec B2)
   beta_f =  14.1464   Wilson-matched beta_c =  3.999989   (tree level 3.5366, off by 13.1%)
   [ok] Villain match == beta_f/4 at beta_f=14.1464: 7.518e-11  (tol 1e-09)
   beta_f =  55.0237   Wilson-matched beta_c = 14.146405   (tree level 13.7559, off by 2.8%)
   [ok] Villain match == beta_f/4 at beta_f=55.0237: 1.110e-15  (tol 1e-09)

7. Exact area law <W(A)> = r_1^A in infinite volume (sec A5)
   [ok] beta=4.0000 A= 4: |W/r_1^A - 1|: 0.000e+00  (tol 1e-09)
   [ok] beta=4.0000 A=16: |W/r_1^A - 1|: 0.000e+00  (tol 1e-09)
   [ok] beta=55.0237 A= 4: |W/r_1^A - 1|: 0.000e+00  (tol 1e-09)
   [ok] beta=55.0237 A=16: |W/r_1^A - 1|: 0.000e+00  (tol 1e-09)

8. Instanton hop carries Q = 1 at cost dS ~ 2 pi^2 beta / V (sec C5)
   L= 32 beta=55.0237: dS =  1.0625   2 pi^2 beta/V =  1.0607
   [ok] L=32: |Q(instanton) - 1|: 5.960e-08  (tol 1e-06)
   L= 64 beta=55.0237: dS =  0.2500   2 pi^2 beta/V =  0.2652
   [ok] L=64: |Q(instanton) - 1|: 1.192e-07  (tol 1e-06)

All exact identities hold.
```

---

## One-page summary

**The physics.** 2D compact U(1): angles on links, action rewarding small
plaquette flux, an exactly-integer topological charge that local samplers
cannot change at large $\beta$. Exactly solvable, so there is an answer key.

**The idea.** RG flows toward strong coupling, which is where sampling is easy.
Run it backwards with a learned conditional diffusion model. $\langle Q^2\rangle$
is a *fixed point* of the ladder step, so the cheap coarse ensemble's sector
distribution **is** the expensive fine theory's — and climbing the ladder is a
continuum-limit trajectory at fixed physical volume.

**What is exact.** $Q\in\mathbb{Z}$; gauge invariance; the blocking telescope;
the curl head spanning precisely the gauge-invariant gradient class; HMC
detailed balance; AIS unbiasedness; the fiber-weight identity. All verified to
floating point.

**What is learned.** One thing only: the score. Everything else is algebra or
structure.

**What is measured.** Observables to 2 parts in $10^4$ across 38 cases to 15×
the training coupling — *and* a density gap of $\approx1$ nat/site that six
interventions failed to close, with a mechanism for each.

**What to claim.** That the sampler is flat-cost and correct-on-observables
where the classical baseline's entry cost diverges; that its correctness comes
from Markov-chain machinery wrapped around it; and — the strongest and most
defensible contribution — that inverse-RG generative samplers had never been
tested for distributional correctness, here is the measurement, and here is why
it fails.

**What not to claim.** That the generated ensemble is the Boltzmann
distribution. It demonstrably is not, and the study's own instrument is what
proves it.
