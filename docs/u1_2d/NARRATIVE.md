# The InverseRG Project: Complete Narrative, Mathematics, and Reasoning

*A ground-up explanation of everything this project does and why — written to be
readable without prior lattice field theory background, but without sacrificing
rigor. Equations are written in LaTeX (rendered by GitHub, VS Code preview, and
most markdown viewers); every symbol is defined before use.*

Last updated: 2026-08-02 (through the exactness program and its terminating
experiments).

---

## Part I — The physics problem

### 1. What we are trying to compute

Quantum field theory predictions are averages. Imagine the theory as an
enormous lottery over field configurations: each possible configuration $U$ of
the field is assigned a real number $S(U)$, called the **action**, which
measures how much that configuration "costs." Cheap configurations are likely;
expensive ones are exponentially suppressed. Every measurable quantity $O$ is
then an expectation value over this lottery:

$$
\langle O \rangle \;=\; \frac{1}{Z} \int \mathcal{D}U \; O(U)\, e^{-S(U)},
\qquad
Z \;=\; \int \mathcal{D}U \; e^{-S(U)},
$$

where $Z$ (the **partition function**) is just the normalization constant that
makes the probabilities sum to one, and $\int \mathcal{D}U$ denotes
integration over *all possible field configurations*.

The difficulty is dimensionality. A field assigns values to every point of
spacetime, so "all configurations" is an astronomically high-dimensional
space — far beyond anything a grid-based numerical integrator could touch. The
only general-purpose tool that survives in high dimensions is **Monte Carlo**:
instead of integrating over everything, draw random configurations
$U_1, \dots, U_n$ with probability proportional to $e^{-S(U)}$ (the
**Boltzmann distribution**), and average the observable over the draws:

$$
\langle O \rangle \;\approx\; \frac{1}{n} \sum_{i=1}^{n} O(U_i).
$$

The magic of Monte Carlo is that the error shrinks like $1/\sqrt{n}$
*regardless of dimension* — provided you can actually produce the samples. That
proviso is the entire story. Everything in this project is about *how to draw
those samples efficiently*, especially in regimes where the standard methods
grind to a halt.

### 2. The lattice and the U(1) gauge theory testbed

To make the integral finite, spacetime is replaced by a periodic square grid
(a **lattice**) of size $L \times L$ — periodic meaning the grid wraps around
like the surface of a torus, so there are no boundaries to worry about.

In a *gauge theory*, the degrees of freedom do not live on the grid points
themselves but on the **links** between neighboring points. This is not an
arbitrary choice: gauge fields physically describe how a particle's internal
phase changes as it moves from one point to another, and "how things change
along a path" naturally attaches to the edges of the grid, not its vertices.

Our testbed is two-dimensional compact U(1): each link carries a single angle

$$
\theta_\mu(x, y) \in (-\pi, \pi],
$$

where $\mu \in \{0, 1\}$ says whether the link points in the $x$- or
$y$-direction. A configuration is therefore an array `theta[2, L, L]` —
$2L^2$ angles in total. "Compact" refers to the fact that the variable is an
angle on a circle rather than an unbounded real number; this compactness is
what makes topology possible (Section 4).

The fundamental gauge-invariant building block is the **plaquette**: walk
around one elementary square of the grid, adding the link angles with signs
determined by the direction of travel (forward links add, backward links
subtract):

$$
\theta_p(x, y) \;=\; \theta_x(x, y) + \theta_y(x{+}1, y) - \theta_x(x, y{+}1) - \theta_y(x, y),
$$

wrapped back into $(-\pi, \pi]$. Physically, $\theta_p$ is the "magnetic
flux" threading that little square: it measures the net twist a charged
particle's phase would pick up if it traveled around the square. The **Wilson
action** rewards small flux:

$$
S(\theta) \;=\; -\beta \sum_{p} \cos \theta_p .
$$

Each plaquette contributes $-\beta \cos\theta_p$, which is minimized at
$\theta_p = 0$ — so the action is lowest when all fluxes vanish. The parameter
$\beta$ plays the role of inverse coupling strength (equivalently, inverse
temperature):

- **Large $\beta$**: the cosine penalty is steep, the field is stiff and
  ordered, all plaquette angles cluster near $0$. This is the approach to the
  **continuum limit**, where lattice artifacts vanish and the theory looks
  like smooth continuum physics — and precisely the regime we ultimately care
  about.
- **Small $\beta$**: the penalty is weak, the angles fluctuate wildly, the
  field is disordered — and, crucially, *easy to sample*.

The distribution we must sample from is

$$
p(\theta) \;=\; \frac{1}{Z} \exp\!\Big( \beta \sum_p \cos \theta_p \Big).
$$

### 3. Gauge invariance — the symmetry that shapes everything

A **gauge transformation** picks an arbitrary angle $\alpha(x, y)$ at every
*site* of the lattice and shifts every link by the difference of the $\alpha$
values at its two endpoints:

$$
\theta_\mu(x) \;\longrightarrow\; \theta_\mu(x) + \alpha(x + \hat\mu) - \alpha(x),
$$

where $\hat\mu$ is the unit step in direction $\mu$. The intuition: each site
gets to privately redefine its "zero of phase," and links — which measure
phase *differences* between sites — shift accordingly.

Now walk around any closed loop and add up these shifts. Every intermediate
site's $\alpha$ appears once with a plus sign (entering) and once with a minus
sign (leaving), so the shifts cancel *exactly*. Therefore every plaquette
angle — and hence the action and every physical observable — is completely
unchanged by gauge transformations.

This has a profound structural consequence. Configuration space contains
enormous flat directions (**gauge orbits**): with $L^2$ sites, there are
$L^2$ independent $\alpha$'s worth of transformations, so roughly half of the
$2L^2$ link variables carry *no physical information whatsoever*. The physical
content of a configuration lives entirely in the plaquettes. Any model that
treats raw link values as meaningful is spending capacity learning pure
noise — coordinates that the theory itself says are meaningless. This single
observation drives the entire network architecture in Part III: the network
never sees, and never needs to see, anything but gauge-invariant quantities.

### 4. Topology — the quantized winding number

Sum all *wrapped* plaquette angles over the periodic lattice and divide by
$2\pi$:

$$
Q \;=\; \frac{1}{2\pi} \sum_{p} \theta_p ,
\qquad \text{each } \theta_p \text{ wrapped to } (-\pi, \pi].
$$

Here is the subtle and beautiful point. If the plaquette angles were *not*
wrapped — if we used the raw sums of link angles — the total would telescope
to exactly zero, because every link appears in exactly two plaquettes with
opposite signs. The wrapping operation is what breaks the telescope: whenever
a raw plaquette angle crosses $\pm\pi$, wrapping silently adds or subtracts a
multiple of $2\pi$. The total is therefore always an exact **integer**
multiple of $2\pi$, and $Q$ counts how many times the U(1) phase winds around
the torus as a whole. It cannot change smoothly — a configuration is in
winding sector $Q = 0$, or $Q = 1$, or $Q = -3$, never in between.

**Derivation (why $Q$ is exactly an integer).** Write the wrap explicitly:
for each plaquette, $\mathrm{wrap}(\theta_p^{\mathrm{raw}}) =
\theta_p^{\mathrm{raw}} + 2\pi n_p$ for a unique integer $n_p$ (the winding
count that brings the raw sum into $(-\pi, \pi]$). Summing over all
plaquettes,

$$
\sum_p \mathrm{wrap}(\theta_p^{\mathrm{raw}})
\;=\; \underbrace{\sum_p \theta_p^{\mathrm{raw}}}_{=\,0 \text{ (telescopes)}}
\;+\; 2\pi \sum_p n_p
\;=\; 2\pi \sum_p n_p ,
$$

so $Q = \sum_p n_p \in \mathbb{Z}$ identically — not approximately, not
statistically, but as an algebraic identity on every configuration. The
telescoping step is the same bookkeeping as gauge invariance: on the periodic
lattice every link appears in exactly two plaquettes with opposite
orientation. This also makes precise *when* $Q$ changes: only when some
$\theta_p^{\mathrm{raw}}$ crosses $\pm\pi$ so that its $n_p$ jumps — the
"barrier crossing" of the freezing argument below.

$Q$ is the lattice version of **topological charge**, the two-dimensional
analogue of QCD's instanton number. The key statistical target built from it
is the **topological susceptibility**

$$
\chi_t \;=\; \frac{\langle Q^2 \rangle}{V}, \qquad V = L^2,
$$

which measures how vigorously the theory fluctuates between winding sectors.
A correct sampler must reproduce not just the typical size of $Q$ but the
whole distribution $P(Q)$ over sectors.

**Why topology is the villain of this story.** To change $Q$, some plaquette
angle must physically swing across $\pm\pi$. At the top of that swing the
plaquette contributes $-\beta\cos(\pm\pi) = +\beta$ instead of $\approx -\beta$
— an action barrier of order $\beta$. The probability of such a fluctuation
falls off *exponentially* in $\beta$. So any sampler that makes **local**
moves — which is almost every sampler ever used — gets **frozen** in a single
$Q$ sector as $\beta$ grows. The insidious part: the frozen chain produces
configurations that look perfectly thermalized by every local measure
(plaquette averages, short-distance correlations all correct) while the
topological statistics are silently, badly wrong. You get precise answers to
the wrong question. This is one of the most serious practical obstacles in
real lattice QCD as simulations push toward the continuum, and it is the
specific disease this project is designed to cure.

### 5. Why 2D U(1) is the right mock: exact solvability

In two dimensions this theory is **exactly solvable**, and this is the entire
justification for choosing it as the development testbed. After a change of
variables, the plaquette angles decouple: each plaquette independently follows
the single-angle density

$$
f(\theta_p) \;\propto\; e^{\beta \cos \theta_p},
$$

up to one single global constraint that ties them together — precisely the
topological constraint from Section 4. Because everything factorizes, all
observables have closed forms in terms of the Fourier ("character")
coefficients of $f$, which are ratios of modified Bessel functions:

$$
r_q(\beta) \;=\; \frac{I_q(\beta)}{I_0(\beta)}.
$$

Concretely:

- the mean plaquette is $\langle \cos\theta_p \rangle = r_1(\beta)$;
- a Wilson loop enclosing area $A$ has expectation $r_1(\beta)^A$
  (the "area law" — each enclosed plaquette contributes one independent
  factor);
- the finite-volume sector distribution $P(Q)$ follows from a
  characteristic-function inversion over the $r_q$;
- $\chi_t$ follows directly from $P(Q)$.

**Derivation (why the plaquettes decouple, and the exact formulas).** On the
$L \times L$ torus one can change variables from the $2L^2$ link angles to:
the $L^2$ plaquette angles, the two holonomy phases (products of links
winding around each direction of the torus — the "Polyakov loops"), and pure
gauge directions. The Jacobian of this change of variables is constant, the
Wilson action depends only on the plaquettes, and the plaquette angles are
independent except for the single constraint that their (unwrapped) sum is
fixed by the winding structure. Enforcing the constraint with a Fourier
representation of the periodic delta function gives the exact partition
function of the sector decomposition,

$$
Z \;\propto\; \sum_{q \in \mathbb{Z}} \big[\, b_q(\beta) \,\big]^{V},
\qquad
b_q(\beta) \;=\; \frac{1}{2\pi}\int_{-\pi}^{\pi} d\theta\; e^{\beta\cos\theta}\, e^{i q \theta}
\;=\; I_q(\beta),
$$

with $I_q$ the modified Bessel functions — each sector contributes the $V$-th
power of one character coefficient. Because the $q \neq 0$ coefficients are
exponentially suppressed relative to $q = 0$ at fixed $\beta/V$, local
observables reduce to single-plaquette integrals in practice:

$$
\langle \cos\theta_p \rangle
\;=\; \frac{\int d\theta\, \cos\theta\; e^{\beta\cos\theta}}{\int d\theta\; e^{\beta\cos\theta}}
\;=\; \frac{I_1(\beta)}{I_0(\beta)} \;=\; r_1(\beta),
$$

(differentiate the integral representation
$I_q(\beta) = \frac{1}{\pi}\int_0^\pi e^{\beta\cos\theta}\cos(q\theta)\,d\theta$
with respect to $\beta$), and a Wilson loop of area $A$ factorizes into the
product of the $A$ enclosed plaquette expectations, $r_1^A$ — the exact area
law. The finite-volume sector distribution follows from the same
decomposition: $P(Q) \propto [\,\tilde b(Q)\,]$ obtained by the
characteristic-function inversion implemented in `lgt/exact.py`
(`topological_charge_distribution`), and
$\chi_t = \sum_Q Q^2 P(Q) / V$. Every "exact" number in this document is one
of these expressions evaluated numerically to machine precision.

**We can grade every sampler against exact answers.** Every claim in this
project — every z-score, every validation table — is a comparison against
closed-form truth, not against another (possibly also-wrong) simulation. In
the eventual target theory, 4D SU(3), no such exact references exist and
validation itself becomes a hard problem; developing the method where the
answer key exists is what makes the negative results in Part IV *trustworthy
negatives* rather than ambiguities.

### 6. HMC — the workhorse, and how it fails

**Hybrid Monte Carlo (HMC)**, the standard sampler of lattice field theory,
is built on a physical analogy: treat $S(\theta)$ as a potential energy
landscape. Pair each angle with a fictitious momentum drawn fresh from a
Gaussian, then let the system coast under Hamilton's equations for a while
(numerically, with a leapfrog or Omelyan integrator), and finally
accept or reject the endpoint with a Metropolis test based on the energy
change. The Metropolis step is what makes HMC *exact*: integrator errors are
corrected by occasional rejections, and the chain provably converges to
$p(\theta)$.

**Precise statement of exactness.** With momenta $\pi \sim \mathcal{N}(0, I)$
refreshed each trajectory, the joint target is
$\propto e^{-H(\theta,\pi)}$ with $H = \tfrac{1}{2}|\pi|^2 + S(\theta)$. The
leapfrog/Omelyan map $\Phi$ is (i) *volume-preserving* (it is a composition
of shears, each updating one of $(\theta, \pi)$ using only the other) and
(ii) *reversible* ($\Phi^{-1} = F \Phi F$ with the momentum flip
$F: \pi \mapsto -\pi$). For any map with these two properties, accepting the
proposal with probability $\min(1, e^{-\Delta H})$ satisfies detailed balance
with respect to $e^{-H}$; marginalizing the Gaussian momenta leaves exactly
$p(\theta)$. No property of the integrator's *accuracy* is used — accuracy
only sets the acceptance rate, never the stationary distribution. This is
the gold standard of "exact" that Part IV's certificate program tries (and
fails) to match for the generative sampler, and the reason the final
architecture wraps Markov-chain steps around the generative proposal rather
than the other way around.

Autocorrelation is quantified by the **integrated autocorrelation time** of
an observable $O$,

$$
\tau_{\mathrm{int}}(O) \;=\; \tfrac{1}{2} + \sum_{t=1}^{\infty} \rho_O(t),
\qquad
\rho_O(t) = \mathrm{corr}\big(O_i, O_{i+t}\big),
$$

which enters the error of a length-$n$ chain average as
$\mathrm{Var}(\bar O) = (2\tau_{\mathrm{int}}/n)\,\mathrm{Var}(O)$ — the
origin of the $n_{\mathrm{eff}} = n / 2\tau_{\mathrm{int}}$ rule below. Its
costs come in three layers:

- **Thermalization (burn-in).** Starting from an arbitrary configuration, the
  chain needs many trajectories before its samples actually represent $p$.
  Think of it as the time for the system to forget its artificial starting
  point. This grows at large $\beta$, where the landscape is stiff.
- **Autocorrelation.** Successive samples are highly similar — each trajectory
  only moves the configuration a little. If $\tau_{\mathrm{int}}$ is the
  integrated autocorrelation time, the effective number of independent samples
  in a chain of length $n$ is

$$
n_{\mathrm{eff}} \;=\; \frac{n}{2\,\tau_{\mathrm{int}}}.
$$

  Near a continuum limit $\tau_{\mathrm{int}}$ explodes — the phenomenon
  called **critical slowing down**: the physics develops long-range
  correlations, but the sampler still takes short-range steps.
- **Topological freezing.** The extreme case of the above:
  $\tau_{\mathrm{int}}$ for $Q$ grows *exponentially* in $\beta$ (Section 4).
  Our measured example: at $L=32,\ \beta=55$, HMC needed roughly 8000 burn-in
  trajectories (about 28 minutes) before passing quality gates; at
  $\beta = 218$ it failed them at every burn-in length we tried.

The project's baseline is deliberately strong. We augment HMC with an
**instanton hop**: a global Metropolis proposal that adds a smooth
uniform-flux configuration carrying winding $\Delta Q = \pm 1$ — every
plaquette shifted by the same amount $\pm 2\pi / V$. Its action cost is

$$
\Delta S \;\approx\; \frac{2\pi^2 \beta}{V},
$$

which is *volume-independent in the combination that matters* and stays small
at practical volumes, so the proposal is accepted often and un-freezes
topology essentially for free.

**Derivation of the hop cost.** The instanton field shifts every plaquette
angle by the same amount $\delta = 2\pi/V$ (so the total winding changes by
exactly $2\pi$, i.e. $\Delta Q = 1$). Expanding the action change per
plaquette to second order and summing,

$$
\Delta S \;=\; \beta \sum_p \big[ \cos\theta_p - \cos(\theta_p + \delta) \big]
\;\approx\; \beta\, \delta \sum_p \sin\theta_p
\;+\; \frac{\beta\, \delta^2}{2} \sum_p \cos\theta_p .
$$

The first term averages to zero in equilibrium ($\langle\sin\theta_p\rangle =
0$ by the $\theta \to -\theta$ symmetry) and only contributes fluctuation;
the second gives $\tfrac{\beta}{2} \cdot \tfrac{4\pi^2}{V^2} \cdot V
\langle\cos\theta_p\rangle \approx 2\pi^2\beta/V$ for
$\langle\cos\theta_p\rangle \approx 1$ at large $\beta$. The same estimate
sets the *residual strain* left behind by the deterministic charge transport
in Section 13 — the quantity rethermalization is asked to relax. Beating naive HMC would be a strawman; every
head-to-head comparison in this project is against instanton-augmented HMC.

---

## Part II — The inverse renormalization group idea

### 7. Blocking: coarse-graining a configuration

The renormalization group (RG) is the physics of "zooming out": systematically
averaging over fine-grained detail to obtain an effective description at
longer distances. Our concrete blocking map takes an $L \times L$
configuration to an $L/2 \times L/2$ one: each coarse link is the wrapped sum
of the two fine links lying along its path. The essential geometric fact,
which everything downstream leans on, is:

> **A coarse plaquette angle equals the wrapped sum of the four fine
> plaquette angles inside its $2\times 2$ cell.**

(The interior fine links cancel in pairs, exactly as in the gauge-invariance
telescope; only the fluxes survive.) Two consequences:

- **Coupling flow.** The coarse plaquette aggregates four independent fine
  fluctuations, so it fluctuates more — the blocked ensemble looks like the
  same theory at a *weaker* coupling. At tree level (small fluctuations,
  variances add):

$$
\beta_{\mathrm{coarse}} \;=\; \frac{\beta_{\mathrm{fine}}}{4}.
$$

  *Derivation.* At large $\beta$ the single-plaquette density
  $\propto e^{\beta\cos\theta_p}$ is approximately Gaussian with variance
  $\mathrm{Var}(\theta_p) \approx 1/\beta$. The coarse plaquette is the sum
  of four (weakly correlated) fine plaquette angles, so
  $\mathrm{Var}(\Theta_P) \approx 4/\beta_f$; demanding this equal
  $1/\beta_c$ gives $\beta_c = \beta_f/4$. Beyond tree level the Gaussian
  approximation fails, and we instead define the matched coupling as the
  maximizer of the exact single-angle log-likelihood of the *observed*
  blocked plaquette angles: the blocked angle is a wrapped sum of four
  i.i.d. plaquette angles, whose exact density is the character convolution

$$
f_4(\Theta) \;=\; \frac{1}{2\pi}\Big( 1 + 2\sum_{q \ge 1} r_q(\beta_f)^4 \cos(q\Theta) \Big)
$$

  (wrapped convolution multiplies Fourier coefficients), and
  $\beta_c := \arg\max_{\beta} \sum_i \log f_{\beta}(\Theta_i)$ — the
  minimum-KL projection of the blocked ensemble onto the single-coupling
  family, implemented in `lgt/blocking.py`. In 2D U(1) there is no phase transition; the RG flow runs
  monotonically toward strong coupling ($\beta \to 0$).

- **Topology is (almost) preserved.** $Q$ on the coarse lattice is the sum of
  wrapped cell-sums; it can differ from the fine $Q$ only if some cell's
  four-plaquette sum crosses $\pm\pi$ during wrapping. At the couplings where
  topology matters (large $\beta$, tiny plaquette angles) that probability is
  exponentially small. Blocking transports the winding number down to the
  coarse level essentially intact.

### 8. The ladder: sample where it's easy, lift to where it's hard

Put the two facts together. RG flows *toward* strong coupling, and strong
coupling (small $\beta$) is exactly where sampling is easy — no stiffness, no
freezing, tunneling between sectors happens constantly. The **inverse-RG
ladder** runs the flow backwards:

1. **Base.** Sample a small, weakly-coupled ensemble with HMC (e.g. $L=8$,
   $\beta \approx 1.35$) — seconds of work, no freezing anywhere.
2. **Learn the lift.** Learn the conditional distribution
   $p(\text{fine} \mid \text{coarse})$ of fine configurations given their
   blocked partner, at matched couplings. Training data is cheap: generate
   fine ensembles by HMC at moderate couplings, block them, and you have
   perfectly matched (fine, coarse) pairs.
3. **Climb.** Apply the learned model to the base ensemble to generate $L=16$
   configurations at $\beta = 4$; treat those as the new coarse ensemble;
   lift again to $L=32$ at $\beta \approx 14.1$; again to $L=64$ at
   $\beta \approx 55$; and so on.

Each rung doubles $L$ and (approximately) quadruples $\beta$, so a handful of
rungs reaches exactly the frozen regime that defeats direct simulation — yet
**no step of the ladder ever required sampling a frozen theory directly**.
Every HMC run in the entire pipeline happens at couplings where HMC is fast
and correct.

The topological payoff is the core design insight of the whole project.
Because blocking preserves $Q$, the coarse ensemble's sector statistics —
obtained cheaply at small $\beta$ where tunneling is frequent — are
*transported* up the ladder rather than re-sampled at the fine level. The
model never needs to tunnel between sectors at large $\beta$; it inherits the
correct sector from its conditioner. Topology rides the ladder for free.

**Why that is an identity, not a hope.** "Blocking preserves $Q$" is a
statement about the *map*; what the argument actually needs is a statement
about the *measure* — that the coarse ensemble's $P(Q)$ equals the fine
theory's. It does, exactly, and for a reason worth stating. The
finite-volume topological charge satisfies $\langle Q^2\rangle \approx
\chi_t V$ with $\chi_t \approx 1/(4\pi^2\beta)$, so

$$
\langle Q^2 \rangle \;\approx\; \frac{V}{4\pi^2 \beta}
\qquad\text{is invariant under}\qquad
(V,\beta) \to (4V,\, 4\beta),
$$

which is precisely one ladder step ($L \to 2L$, $\beta \to 4\beta$).
$\langle Q^2\rangle$ is a **fixed point of the ladder**. Evaluating the exact
finite-volume $P(Q)$ (Villain, where $\beta_c = \beta_f/4$ is exact) at four
successive rungs starting from $L=8,\ \beta=1.3472$ gives

$$
1.20271 \;\to\; 1.20334 \;\to\; 1.20334 \;\to\; 1.20334,
$$

invariant to five decimals. The campaign's measured-matching Wilson ladder
inherits it to 4% ($1.986 \to 1.934 \to 1.904 \to 1.903$), the drift sitting
in the first, strongest-coupling step where the tree-level relation is worst.

Two consequences. First, sector transport is *exact at the level of the
target*: the coarse base's sector distribution is the correct sector
distribution for the fine theory, not an approximation that happens to be
close. Second — the physical reading of the whole construction — since
$\langle Q^2\rangle$ (and hence the physical volume in units of the
topological correlation length) is held fixed while $L$ doubles and $a$
shrinks, **the ladder is a continuum-limit trajectory at fixed physical
volume**, not a thermodynamic-limit one. The endpoint ($L=64$,
$\beta\approx55$) should be read as *the same physical system, resolved eight
times more finely than the base* — which is exactly the limit in which
topological freezing is the obstruction, and exactly why this is the right
testbed.

**What this does and does not license.** The identity is a statement about
*distributions*, and it is worth being precise about the gap between that and
what the model does, because the two are easy to conflate and the project's
own measurements keep them apart:

- The identity says: the coarse ensemble's $P(Q)$ **is** the right target for
  the fine theory. That part is exact and needs no learning.
- The measurements say: the model does **not** faithfully carry an individual
  configuration's charge across the step. The raw charge-match rate is 0.21,
  the transport-mode worst $|z(\langle Q^2\rangle)|$ is 11.8, and the raw
  $Q^2$ excess *grows with volume* (1.7–2.7 at $L\le32$ to 7.1–28.2 at
  $L=64/128$).

So "topology rides the ladder for free" is true of the *target* and false of
the *transport*. The resolution is the one the pipeline actually implements
and should be stated as the design, not as a patch: because the correct
sector distribution is known exactly (by this identity, or directly from the
character expansion), the sector is **imposed structurally** — C-antithetic
symmetrization plus resampling from the exact finite-volume $P(Q)$ at the
target coupling — rather than trusted to the network. The learned model is
asked to supply the expensive part, a thermalized UV at the target coupling;
it is not asked to be a topological transport operator, and the measurements
say it would fail if it were.

That is a coherent division of labour, and it is honest about which half is
exact. The cost is a real limitation to carry forward: the structural route
needs the exact $P(Q)$, which this solvable theory supplies and a
non-abelian target in 4D will not. In 2D SU(2) the point is moot ($\pi_1$ is
trivial, no sectors); in 4D it is *the* open problem this line inherits.

The learned lift is a **conditional generative model**: given a coarse
configuration, produce a fine one distributed according to the physics. We
chose score-based diffusion for it, for reasons the next part makes concrete.

---

## Part III — Diffusion on a torus of angles

### 9. The forward process: exact heat kernel on the circle

A diffusion model works by destroying data with gradually increasing noise,
then learning to reverse the destruction. To generate, you start from pure
noise and run the learned reversal. For our data — angles — the "noise" must
respect periodicity: adding Gaussian noise to an angle and then forgetting
the wrap would treat $-\pi$ and $\pi$ as distant points when they are the
same point. Our forward process is

$$
\theta_t \;=\; \mathrm{wrap}\big(\theta_0 + \sigma(t)\, z\big),
\qquad z \sim \mathcal{N}(0, 1) \text{ independently per link},
$$

with $\mathrm{wrap}(x) = \mathrm{atan2}(\sin x, \cos x)$ mapping back to
$(-\pi, \pi]$. The transition density of this process is the **wrapped
normal** — a Gaussian summed over all the ways the noise could have wound
around the circle:

$$
K_\sigma(d) \;=\; \sum_{k=-\infty}^{\infty} \mathcal{N}\big(d + 2\pi k;\; 0,\; \sigma^2\big).
$$

This is precisely the **heat kernel on the circle**: the exact probability law
of Brownian motion on U(1).

**Derivation (wrapped normal = heat kernel).** Brownian motion on the circle
with variance function $\sigma^2(t)$ obeys the heat equation
$\partial_t p = \tfrac{1}{2}\tfrac{d\sigma^2}{dt}\, \partial_\theta^2 p$ with
periodic boundary conditions. Expanding in Fourier modes
$e^{iq\theta}$, each mode decays independently:
$\hat p(q, t) = \hat p(q, 0)\, e^{-q^2 \sigma^2(t)/2}$ — this is the
character-space form. Resumming with the Poisson summation formula converts
the mode sum into the winding sum, which is exactly $K_\sigma$ above: the two
expressions

$$
K_\sigma(d) \;=\; \sum_{k \in \mathbb{Z}} \mathcal{N}(d + 2\pi k; 0, \sigma^2)
\;=\; \frac{1}{2\pi}\Big( 1 + 2\sum_{q \ge 1} e^{-q^2\sigma^2/2}\cos(q d) \Big)
$$

are the same function, one converging fast at small $\sigma$ (few windings
matter), the other at large $\sigma$ (few modes survive). Equivalently, as an
SDE: the forward process is $d\theta = g(t)\, dW$ with
$g^2(t) = \tfrac{d}{dt}\sigma^2(t)$ (the "variance-exploding" convention —
no drift, noise only), and the wrapped normal is its exact transition
density. That exactness is a luxury of an *abelian* group:
angles add, so noise accumulates linearly, and the distribution after any
finite time is known in closed form. (Contrast SU(3), the eventual target:
matrix multiplications do not commute, the finite-time law of Brownian motion
on the group is not Gaussian in any coordinate system, and published
approaches approximate it. That approximation is the single biggest new
difficulty waiting beyond this mock — remember this when we reach Section 20.)

How noisy is fully noisy? The Fourier coefficients of $K_\sigma$ decay as

$$
\hat K_\sigma(q) \;=\; e^{-q^2 \sigma^2 / 2},
$$

so as $\sigma$ grows the kernel flattens double-exponentially fast toward the
uniform distribution on the circle; at $\sigma = 6$ it is uniform to about
$10^{-8}$. Uniform-on-every-link is the Haar measure of
$\mathrm{U}(1)^{2L^2}$ — the maximally ignorant distribution on configuration
space, containing zero information about the physics. So the forward process
interpolates cleanly from "physics" ($\sigma = 0$) to "pure noise"
($\sigma = \sigma_{\max} = 6$), and generation runs the movie backward,
starting from uniform random angles.

### 10. The score function and why it is all you need

Let $p_t$ denote the distribution of noised data at noise level $\sigma(t)$.
Its **score** is the gradient of its log-density:

$$
s(\theta, t) \;=\; \nabla_\theta \log p_t(\theta).
$$

Intuitively, the score is a vector field of arrows: at every point of
configuration space it points in the direction where probability increases
fastest — "toward the data," with magnitude telling you how urgently. Note
what it does *not* require: the normalization $Z$. Since
$\log p = \log(\text{unnormalized}) - \log Z$ and $Z$ is a constant, the
gradient kills it. This is why score-based methods are natural for physics,
where unnormalized densities are easy and $Z$ is hopeless.

A classical result (Anderson, 1982) says the forward noising SDE has an exact
reverse-time SDE whose drift involves *only the score*. For our
variance-exploding process:

$$
d\theta \;=\; -\,\dot\sigma\,\sigma\; s(\theta, t)\, dt \;+\; \text{(noise term)} ,
\qquad \text{(time running backwards)} .
$$

**Precise statement (Anderson 1982).** If the forward process is
$dx = f(x,t)\,dt + g(t)\,dW$ with marginals $p_t$, then the time-reversed
process

$$
dx \;=\; \big[ f(x,t) - g^2(t)\, \nabla_x \log p_t(x) \big]\, d\bar t
\;+\; g(t)\, d\bar W
$$

(run with time decreasing, $\bar W$ an independent Wiener process) has the
*same* marginals $p_t$. For our variance-exploding process $f = 0$ and
$g^2 = \frac{d\sigma^2}{dt}$, which gives the drift quoted above. So a single
learned object — a network approximating $s$ — suffices to integrate noise
back into physics.

The discrete scheme we use (SMLD "ancestral" sampling) steps down a ladder of
noise levels $\sigma_{\max} = 6 = \sigma_1 > \sigma_2 > \dots > \sigma_n =
\sigma_{\min}$, and its update rule is not an ad-hoc discretization but an
exact conditional-Gaussian identity. *Derivation:* if $x_i = x_0 +
\sigma_i z$ ignoring wrapping (locally valid), then conditionally on $x_i$,
the less-noisy $x_{i+1} = x_0 + \sigma_{i+1} z'$ is Gaussian with mean and
variance obtained by standard Gaussian conditioning; replacing the
unknown $x_0$-dependence using the score identity
$\mathbb{E}[x_0 \mid x_i] = x_i + \sigma_i^2 s(x_i)$ (Tweedie's formula)
yields

$$
x_{i+1} \;=\; x_i \;+\; \big(\sigma_i^2 - \sigma_{i+1}^2\big)\, s(x_i)
\;+\; \sqrt{ \frac{\sigma_{i+1}^2 \big(\sigma_i^2 - \sigma_{i+1}^2\big)}{\sigma_i^2} }\; z,
\qquad z \sim \mathcal{N}(0, I),
$$

which is exactly the predictor step implemented in `model/sampler.py` — the
"precisely-right amount of fresh noise" is the conditional variance of this
identity, and every state is re-wrapped after each update (legitimate because
both the kernels and the score are periodic, so wrapping commutes with the
dynamics). Optionally, **Langevin corrector** steps are
interleaved: small stochastic gradient-ascent moves on $\log p_t$ that
re-equilibrate the ensemble at each noise level, correcting drift the
predictor steps accumulate.

### 11. Denoising score matching — the training objective, with proof sketch

There is an apparent chicken-and-egg problem: to train the network we need
target values of $s = \nabla \log p_t$, but $p_t$ — the noised *marginal* of
our unknown data distribution — is exactly what we don't have. What we *do*
have, exactly, is the conditional law of the noising process itself:
$p_t(\theta_t \mid \theta_0) = K_\sigma(\theta_t - \theta_0)$.

**Denoising score matching** (Vincent, 2011) resolves this with an identity:
regressing onto the *conditional* score is equivalent to regressing onto the
true *marginal* score:

$$
\mathbb{E}_{\theta_0, \theta_t}
\Big\| s_{\mathrm{net}}(\theta_t) - \nabla_{\theta_t} \log K_\sigma(\theta_t - \theta_0) \Big\|^2
\;=\;
\mathbb{E}_{\theta_t}
\Big\| s_{\mathrm{net}}(\theta_t) - \nabla_{\theta_t} \log p_t(\theta_t) \Big\|^2
\;+\; \text{const}.
$$

*Proof sketch.* Expand both sides; the squared-network terms coincide, so
only the cross terms need to match. Write the marginal as the mixture
$p_t(\theta_t) = \int K_\sigma(\theta_t - \theta_0)\, p_0(\theta_0)\, d\theta_0$
and differentiate under the integral: this shows $\nabla \log p_t(\theta_t)$
is precisely the *posterior average* of the conditional score,

$$
\nabla \log p_t(\theta_t)
\;=\;
\mathbb{E}\big[\, \nabla \log K_\sigma(\theta_t - \theta_0) \;\big|\; \theta_t \,\big],
$$

averaged over which clean configuration $\theta_0$ the noisy one came from.
And a mean-squared error is always minimized by the conditional mean. So the
network that minimizes the left-hand side (cheap, computable) is exactly the
true marginal score — the thing we actually need. $\square$

The intuition is worth holding onto: each training pair gives a *noisy* arrow
(pointing back toward its particular $\theta_0$), and the network, forced to
give one answer per noisy input, learns the *average* arrow — which is the
true score.

For the wrapped normal, the conditional score has closed form — a
winding-weighted average over the candidate unwrapped displacements:

$$
\nabla \log K_\sigma(d) \;=\; -\frac{1}{\sigma^2} \sum_k w_k \,(d + 2\pi k),
\qquad
w_k \;=\; \mathrm{softmax}_k\!\left( -\frac{(d + 2\pi k)^2}{2\sigma^2} \right),
$$

implemented in `model/wrapped.py`. Each term asks "what if the noise wound
around $k$ times?" and weights the answers by their Gaussian likelihoods. At
small $\sigma$ only $k=0$ matters; at large $\sigma$ the windings blend and
the score correctly flattens toward zero (uniform distribution — no
direction is preferred).

Training is then a simple loop: draw a data pair (fine configuration plus its
blocked coarse partner), draw a noise level, noise the fine configuration,
and regress the network's output onto this exact closed-form target. Three
practical refinements matter:

- **Scaled score.** The network predicts $\sigma \cdot s$ rather than $s$.
  The raw score blows up like $1/\sigma$ at small noise; the scaled version is
  $O(1)$ at every level, which keeps the regression well-conditioned across
  the whole schedule.
- **Beta-aware noise floor.** The smallest noise level is

$$
\sigma_{\min}(\beta) \;=\; \min\!\left( \sigma_{\min},\; \frac{c}{\sqrt{\beta}} \right),
$$

  because the physical link fluctuations themselves shrink like
  $1/\sqrt{\beta}$ (stiffer action, smaller wiggles). A fixed floor would at
  some $\beta$ become *larger than the physics* — the model would stop
  resolving the target distribution entirely.
- **Small-$\sigma$ oversampling at high beta.** The noise-level sampling
  distribution is tilted toward small $\sigma$ when $\beta$ is large, for the
  same reason: the model must be most accurate precisely where the target
  distribution is narrowest and the endgame of sampling is decided.

### 12. Building the symmetry in: the gauge-covariant score network

Instead of hoping a generic CNN discovers gauge symmetry from data — it
would waste capacity and never get it *exactly* right — the architecture
makes the symmetry structural:

- **Inputs are invariants.** The network never sees raw link angles. Its
  inputs are $\cos$ and $\sin$ of the plaquette angles and of $1\times 2$ /
  $2\times 1$ rectangle angles of the noisy configuration. Since these are
  gauge-invariant, *every internal activation of the network is exactly
  gauge-invariant*, by construction, for any weights.

- **Output through the curl head.** The network emits one scalar $h_p$ per
  plaquette, and the score components are assembled as the lattice "curl" of
  this scalar field:

$$
s_x(x, y) \;=\; h(x, y) - h(x, y{-}1),
\qquad
s_y(x, y) \;=\; h(x{-}1, y) - h(x, y).
$$

  Why this specific form? By the chain rule, the gradient of *any* function
  $F$ that depends on the configuration only through plaquette angles is

$$
s_\mu(x) \;=\; \frac{\partial F}{\partial \theta_\mu(x)}
\;=\; \sum_p \frac{\partial F}{\partial \theta_p} \cdot
\frac{\partial \theta_p}{\partial \theta_\mu(x)},
$$

  and $\partial \theta_p / \partial \theta_\mu(x)$ is $\pm 1$ for the (at
  most two) plaquettes containing that link — which is exactly the curl
  stencil above with $h_p = \partial F / \partial \theta_p$. The head doesn't
  approximate the right function class — it *parameterizes precisely* the
  right function class and nothing more. Sanity anchor: setting
  $h_p = -\beta \sin\theta_p$ reproduces the exact Wilson action score
  identically.

  *Why the true score is in this class (with the one honest caveat).* A
  smooth gauge-invariant function on the torus of link angles depends on the
  plaquette angles **and** on the two holonomies (the phases of the Polyakov
  loops winding around each direction of the torus) — the plaquettes alone do
  not coordinatize the gauge-invariant content of a periodic lattice. The
  Wilson density is *uniform* in the holonomies (the action contains only
  plaquettes), and the forward noising kernel is a per-link translation-
  invariant convolution, which preserves both gauge invariance and holonomy
  uniformity. Hence $p_t$ is, at every noise level, a function of plaquette
  angles alone times a uniform holonomy factor, and its score — the gradient
  of $\log p_t$ — has exactly the curl form, with zero component along the
  holonomy directions. The curl head automatically produces zero along those
  directions too (a constant shift of all links in one row changes no
  plaquette), so the parameterization is complete, not merely contained.

- **Conditioning.** The coarse configuration enters only through *its*
  invariants (coarse plaquettes and loops), upsampled to the fine grid and
  concatenated at the input. One global channel deserves special mention: a
  FiLM channel carries the spatial mean of the raw coarse plaquette angle,
  which by Section 4 equals

$$
\overline{\theta_p^{\,\mathrm{coarse}}} \;=\; \frac{2\pi\, Q_{\mathrm{coarse}}}{V},
$$

  — a direct, global topology signal. This matters because $Q$ is a *global*
  quantity that no finite local receptive field could ever compute; the
  architecture hands it to every layer for free.

- **Coupling and noise conditioning.** $\beta$ and $\sigma$ enter through
  sinusoidal embeddings that modulate every block (FiLM: per-channel scale
  and shift). This is what lets **one network serve a continuum of
  couplings** — training draws $\beta$ log-uniformly from $[1, 60]$ rather
  than from a fixed list, and the same weights are queried at any $\beta$ at
  sampling time.

- **Other exactness aids.** Symmetry augmentation during training
  ($90^\circ$ rotations, reflections, and charge conjugation
  $\theta \to -\theta$ — all exact symmetries of the Wilson action), and
  per-site channel normalization (no statistics that depend on lattice size,
  so the fully-convolutional network runs unchanged at any $L$).

### 13. Topology transport machinery — the part local learning cannot do

The learned score is local — a finite receptive field — while $Q$ is global.
No amount of training can make a local function reliably control a global
integer. Three structural mechanisms carry the sector instead:

- **Coarse-charge enforcement.** Blocking preserves $Q$ (Section 7), so a
  correctly-lifted fine sample's sector *should* equal its coarse
  conditioner's. We enforce this: compute
  $\Delta Q = Q_{\mathrm{coarse}} - Q_{\mathrm{fine}}$ and add the smooth
  instanton field carrying exactly that winding (a deterministic,
  gauge-covariant map that uses only the conditioning input). The timing is
  deliberate: enforcement is applied periodically during *late* sampling —
  after the sector has effectively frozen, below which the model will no
  longer spontaneously tunnel, but while enough noise remains for the sampler
  to relax the small uniform strain the shift introduces
  ($2\pi \Delta Q / V$ per plaquette).

  **Where the freezing $\sigma$ actually is (measured 2026-08-14).** This
  text previously asserted $\sigma \sim O(1)$ without measuring it.
  `scripts/33_charge_freezing_sigma.py` runs the sampler with enforcement off
  and records the fraction of configurations changing sector at each $\sigma$
  step: tunnelling stops at $\sigma_{\text{freeze}} = 0.304$ (16:14.1) and
  $0.312$ (32:55.0), roughly $3\times$ below the assertion and below the
  deployed threshold `charge_projection_sigma = 0.5`. The threshold is
  therefore mis-set *against its own stated criterion* — the first two or so
  of the ~11 projections fire while the model can still undo them.

  It makes no measurable difference. A 3 × 3 A/B (thresholds 0.20 / 0.31 /
  0.50 × seeds 11 / 12 / 13, full ladder + validation each) gives mean
  $|z_{\text{exact}}|$ of 0.812 / 0.814 / 0.768, with between-arm spread
  (0.026) *smaller* than between-seed spread (0.030): $F(2,6) = 2.30$ against
  $F_{\text{crit}} = 5.14$. The count of $|z| > 3$ observables is identical
  across all three arms at every seed (0 / 1 / 0 of 86). Changing the
  threshold by $2.5\times$ moves nothing across the outlier line, because the
  projections that fire *after* freezing plus the final post-sampling
  projection already determine the sector. Recorded as a measured null, not
  an assumed one; the correction belongs in this paragraph rather than in the
  config. Provenance: `out/u1_2d/proj_sigma_ab/seed_sweep_summary.json`,
  `scripts/parse_proj_seed_sweep.py`.

  The same measurement gives the sector-transport machinery's value directly.
  With projection disabled, the fraction of samples landing in the coarse
  configuration's sector on their own is:

  | $L$ | $\beta_f$ | $V = 2L^2$ | $\sigma_{\text{freeze}}$ | Q match rate, no projection |
  |---|---|---|---|---|
  | 16 | 14.15 | 512 | 0.304 | 0.484 |
  | 32 | 55.02 | 2048 | 0.312 | 0.234 |
  | 64 | 218.58 | 8192 | 0.307 | 0.094 |

  Two things to read off this. The match rate roughly **halves for every
  $4\times$ in volume** (ratios 2.07 and 2.49), so at $L=128$ it would be a
  few percent: a local score with a finite receptive field cannot control a
  global integer, and the degradation is quantitative, not incidental. This
  is the sharpest available statement of the objection in §25.1, and it is
  the reason the transport machinery is structural rather than a convenience.

  Second, $\sigma_{\text{freeze}}$ is **flat in volume** (0.304, 0.312,
  0.307 across a $16\times$ range in $V$). So the freezing scale is a
  property of the noise schedule, not of the lattice, and the threshold
  conclusion above transfers across volumes rather than needing a per-$L$
  sweep. Provenance: `out/u1_2d/charge_freezing_L64/charge_freezing.json`.

- **Blocking-consistency guidance.** During sampling, an extra score term
  pulls each $2\times2$ cell's fine-plaquette sum toward its coarse
  plaquette angle — the gradient of a soft constraint

$$
-\,\frac{\big( \textstyle\sum_{\text{cell}} \theta_p^{\,\mathrm{fine}} - \theta_p^{\,\mathrm{coarse}} \big)^2}{2\,\lambda(\sigma)},
\qquad
\lambda(\sigma) = 8\sigma^2,
$$

  where the width $8\sigma^2$ is not a tuning knob but a derived quantity:
  the blocked plaquette's boundary consists of eight fine links, each
  carrying noise of variance $\sigma^2$ at level $\sigma$, so that is
  exactly how much the constraint *should* be allowed to slack. The gradient
  is assembled through the same curl head, so guidance stays exactly
  gauge-covariant. One subtlety with teeth: the residual is deliberately
  **not wrapped**. A wrapped residual would be blind to a cell landing
  $2\pi$ away from its target — which is precisely the failure mode that
  spawns spurious winding defects. The unwrapped residual sees, and
  corrects, the $2\pi$ slip.

- **Rethermalization.** After sampling, a few sweeps of local heatbath and
  overrelaxation updates at the target coupling cheaply fix UV
  (short-distance) imperfections — the kind of small local roughness a
  generative model leaves behind. Under the project's **honesty convention**,
  retherm performs *no* topological moves: measured topology therefore
  reflects what the model plus structural transport actually delivered,
  never what retherm manufactured after the fact. A separate production mode
  ("exact-sector") exists for when the goal is generating usable ensembles
  rather than grading the model: it draws each configuration's sector from
  the exact finite-volume $P(Q)$ at the target coupling and imposes it with
  the instanton shift — correct sector statistics by construction.

### 14. What the validated pipeline achieves (the v2 campaign, pre-this-week)

Under strict conventions — two independent seeds per case, per-chain error
bars, z-scores against the exact references of Section 5, and raw
*pre-enforcement* topology metrics whenever the model itself is being graded
— the validated results are:

- **Observable agreement across 38 cases** spanning $\beta = 1.49$ to
  $\beta = 872.8$ — the latter **15× beyond the training maximum** of
  $\beta = 60$ — and volumes up to $L = 128$ (64× the training area).
- **Head-to-head against instanton-HMC at $L = 32$:** the diffusion pipeline
  costs a flat $\sim 2.4$ s/configuration at *every* coupling, while HMC's
  entry cost explodes with $\beta$: it passes quality gates only after
  $\sim 28$ minutes of burn-in at $\beta = 55$, and fails them at every
  burn-in length tested at $\beta = 218$. The crossover is exactly the
  regime the ladder was designed for.
- **The seeding result** — arguably the most practically important: use a
  diffusion batch as HMC's *starting point*, then run a seconds-long
  instanton-HMC tail. The tail re-equilibrates even deliberately mismatched
  topology (a $P(Q)$ chi-squared p-value of $0.0005$ recovering to $0.43$
  in 6 seconds of MCMC). Diffusion supplies the expensive thermalized start;
  a provably-exact Markov chain supplies correctness. Keep this division of
  labor in mind — Part IV will elevate it from a convenience to a design
  principle.

---

## Part IV — The exactness program (this week)

Everything above validates *observables*: the generated ensembles agree with
exact answers on every quantity we measure. Competing flow-based samplers
(normalizing-flow papers in lattice field theory) make a *stronger* claim:
**provably unbiased estimators** via importance weights, with the effective
sample size (ESS) as the headline metric. Their models expose a tractable
density $q(x)$, so every expectation can be exactly reweighted to the target.
This week asked: can this pipeline make that claim too? Answering required
building new machinery (the ODE likelihood), and produced one modest
positive, several rigorous negatives, and — most valuably — a quantified
verdict on *why* and *by how much* the claim is out of reach.

### 15. Importance sampling in one page

Suppose samples come from the wrong distribution $q$, but for any
configuration we can compute both $q(x)$ and the unnormalized target
$e^{-S(x)}$. Then weighted averages repair the bias exactly:

$$
\langle O \rangle_p \;=\; \frac{\mathbb{E}_q[\, w(x)\, O(x) \,]}{\mathbb{E}_q[\, w(x) \,]},
\qquad
w(x) \;=\; \frac{e^{-S(x)}}{q(x)}.
$$

This is **self-normalized importance sampling (SNIS)** — the ratio form makes
all unknown normalization constants cancel. Each sample is re-weighted by how
much the target likes it relative to how often the proposal produces it.

The catch is *variance*. If $\log w$ fluctuates substantially across samples,
the exponential turns modest log-fluctuations into enormous weight ratios,
and a handful of samples dominate the averages — the estimator is unbiased
but useless. The standard diagnostic is

$$
\frac{\mathrm{ESS}}{N} \;=\; \frac{\big(\sum_i w_i\big)^2}{N \sum_i w_i^2},
$$

the fraction of samples that are "effectively" contributing. For roughly
lognormal weights there is a devastating rule of thumb:

$$
\frac{\mathrm{ESS}}{N} \;\approx\; e^{-\mathrm{Var}[\log w]}.
$$

*Derivation.* In the large-$N$ limit
$\mathrm{ESS}/N \to (\mathbb{E}[w])^2 / \mathbb{E}[w^2]$. If
$\log w \sim \mathcal{N}(\mu, s^2)$, the lognormal moment formula
$\mathbb{E}[w^k] = e^{k\mu + k^2 s^2/2}$ gives
$(\mathbb{E} w)^2/\mathbb{E}[w^2] = e^{2\mu + s^2} / e^{2\mu + 2s^2} =
e^{-s^2}$. The lognormal assumption is not decorative here: our $\log w$ is a
sum of $\sim 2L^2$ weakly-dependent per-site contributions (Section 18's
frontier scan verifies the $\sqrt{V}$ scaling), so the central limit theorem
makes it accurate precisely in the regime that matters.

**ESS decays exponentially in the log-weight variance.** This one formula
explains most of what follows. If the standard deviation of $\log w$ is 3,
you keep roughly $e^{-9} \approx 10^{-4}$ of your samples. If it is 20 — a
number that will appear below — reweighting is not merely inefficient but
cosmically hopeless: no achievable $N$ compensates. Weights are useful only
when the *total* spread of $\log w$ across the whole configuration is
$O(1)$, no matter how many samples you draw.

An equivalent route to exactness with the same requirement: **independence
Metropolis** — treat the model's draws as proposals in a Markov chain,
accepting proposed draw $j$ over current state $i$ with probability
$\min(1, w_j / w_i)$. Asymptotically exact, and its acceptance rate degrades
with weight spread in exactly the same way ESS does. There is no clever
estimator that evades the variance; the density itself must be good.

### 16. Getting $q$: the probability-flow ODE and its likelihood

Diffusion models, unlike normalizing flows, do not hand you $q(x)$ — the
stochastic sampler's density is an intractable marginal over noise paths. But
every diffusion process has a deterministic twin, the **probability-flow
ODE**, which shares the *exact same marginal distributions* at every noise
level while being fully deterministic. For our variance-exploding process it
reads

$$
\frac{dx}{d\sigma} \;=\; -\,\sigma\, s(x, \sigma).
$$

*Derivation (why the marginals match).* The forward SDE's marginals obey the
Fokker–Planck equation, which for a pure-diffusion process can be rewritten
as a continuity equation:

$$
\partial_t p_t \;=\; \tfrac{1}{2} g^2 \nabla^2 p_t
\;=\; -\nabla \cdot \Big( p_t \cdot \underbrace{\big[ -\tfrac{1}{2} g^2 \nabla \log p_t \big]}_{v(x,t)} \Big),
$$

using $\nabla p_t = p_t \nabla \log p_t$. A continuity equation says exactly
that the density is transported by the deterministic velocity field $v$ — so
the ODE $\dot x = v(x, t)$ reproduces every marginal $p_t$ without any noise.
Substituting $g^2\,dt = d\sigma^2 = 2\sigma\,d\sigma$ gives the
$dx/d\sigma = -\sigma s$ form above. (The stochastic reverse SDE and this ODE
are two members of a whole family sharing marginals; the ODE is the
zero-noise member, and the only one whose *path-wise* density is tractable.)

A deterministic, invertible flow has a computable density, via the
*instantaneous change of variables* formula:

$$
\frac{d}{dt} \log p\big(x(t)\big) \;=\; -\,\nabla \cdot f\big(x(t)\big),
$$

where $f$ is the ODE's velocity field.

*Derivation.* Along a trajectory, the total derivative is
$\frac{d}{dt}\log p_t(x(t)) = \partial_t \log p_t + \dot x \cdot \nabla \log
p_t$. The continuity equation $\partial_t p_t = -\nabla\cdot(p_t f)$ expands
to $\partial_t \log p_t = -\nabla \cdot f - f \cdot \nabla \log p_t$;
substituting, the two $f \cdot \nabla \log p_t$ terms cancel and only
$-\nabla \cdot f$ survives. $\square$ This is the continuous-time limit of
the familiar "log-density change = log |Jacobian determinant|" of a discrete
invertible map: instead of one big determinant, you accumulate the trace of
the Jacobian (the divergence) continuously along the trajectory. Integrating
from the uniform prior at $\sigma_{\max}$ down to $\sigma_{\min}$:

$$
\log q(x_0) \;=\; \log(\text{uniform}) \;+\; \int \sigma \, (\nabla \cdot s)\; d\sigma
\quad \text{along the trajectory}.
$$

The divergence of a $2L^2$-dimensional vector field is the expensive part —
naively it costs one backpropagation per coordinate. We estimate it with
**Hutchinson probes**: for random vectors $v$ with
$\mathbb{E}[v v^\top] = I$ (we use Rademacher $\pm 1$ signs),

$$
\nabla \cdot s \;=\; \mathbb{E}_v\big[\, v^\top \tfrac{\partial (s \cdot v)}{\partial x} \,\big],
$$

each probe costing a single backpropagation. (*Why it is unbiased:* for any
matrix $A$, $\mathbb{E}[v^\top A v] = \sum_{ij} A_{ij}\mathbb{E}[v_i v_j] =
\mathrm{tr}\,A$ whenever $\mathbb{E}[v v^\top] = I$; here $A$ is the Jacobian
$\partial s/\partial x$, and $v^\top A v$ is computed without ever forming
$A$ — the vector-Jacobian product is one reverse-mode pass.) Numerical integration is Heun's
method (second order) on the log-spaced sigma grid. An exact mode (one
backprop per coordinate, no probe noise) exists for calibration at small $L$.

**The one-pass insight** — the correction that made the weights *valid*
rather than merely suggestive: our first implementation generated samples
with the *stochastic* sampler and evaluated $\log q$ with the *ODE*. Those
two processes share marginals only when the score is perfect; with a learned,
imperfect score they are genuinely different distributions, so the computed
density was not the density of the sampler that produced the samples — the
"weights" were a diagnostic, not a certificate. The fix is conceptually
simple: **sample the ODE itself**, accumulating the divergence along the way,
so that every configuration emerges paired with the exact log-density of the
very process that generated it. Residual caveats, both verified small: Heun
discretization error, and Hutchinson noise — which is unbiased in $\log q$
but (by Jensen's inequality) biases $e^{-\log q}$, and hence the weights,
upward. Both shrink with more steps/probes, not with more samples, so they
are controlled independently of ensemble size.

**Validation of the machinery itself**, before pointing it at the real model:
on an exactly solvable target (independent wrapped Gaussians, where the true
noised score is known in closed form), the sampled density round-trips
against an independent evaluator within 1 log-unit, and achieves
$\mathrm{ESS}/N > 0.5$. The pipeline is correct. Therefore any weight spread
observed on the real model is *the model's density error* — not estimator
noise, not a bug — full stop. This calibration is what licenses every
negative conclusion below.

### 17. Which weights: the fiber correction

For a conditional model there is a choice of what to reweight. The naive
"joint" weight compares the joint proposal (coarse from HMC, fine from the
model) to the fine target — but this makes the weight carry the full
fluctuation of the coarse configuration's own probability mass, a quantity of
order $e^V$, so even a *perfect* conditional model would score
$\mathrm{ESS} = 1/N$. The estimator would be broken by construction, telling
us nothing about the model.

The right choice exploits what we know exactly. The coarse HMC ensemble
samples the matched Wilson action $\pi_c \propto e^{-S_{\mathrm{matched}}}$
*exactly* (HMC is exact). Conditioning on the coarse configuration, the
correct and fully-known SNIS weight for the fine level is

$$
\log w \;=\; -\,S_{\mathrm{fine}}(x) \;+\; S_{\mathrm{matched}}(c) \;-\; \log q(x \mid c),
$$

the **fiber-corrected** weight: the coarse density divides out, and what
remains compares the model's conditional density against the target's
conditional density on each fiber. This per-level quantity is exactly what
multilevel flow papers report, and it is the weight used throughout
everything below.

*Derivation (consistency of the fiber weight).* The actual sampling process
draws pairs $(c, x)$ from the joint proposal
$q_{\mathrm{joint}}(c, x) = \pi_c(c)\, q(x \mid c)$, with
$\pi_c = e^{-S_{\mathrm{matched}}}/Z_c$ known up to its constant. With
$w = e^{-S_{\mathrm{fine}}(x) + S_{\mathrm{matched}}(c)} / q(x \mid c)$,

$$
\mathbb{E}_{q_{\mathrm{joint}}}\big[ w\, O(x) \big]
= \int dc\, dx\; \pi_c(c)\, q(x|c)\;
\frac{e^{-S_f(x)}\, e^{+S_m(c)}}{q(x|c)}\; O(x)
= \frac{1}{Z_c} \int dc \int dx\; e^{-S_f(x)}\, O(x),
$$

and the (divergent-looking but harmless) coarse volume factor
$\int dc\,1$ together with $1/Z_c$ cancels identically in the SNIS ratio
$\mathbb{E}[wO]/\mathbb{E}[w]$, leaving exactly
$\int e^{-S_f} O / \int e^{-S_f} = \langle O \rangle_{p_{\mathrm{fine}}}$.
Consistency requires only that both proposal factors be *known* — which they
are: $\pi_c$ because HMC is exact, and $q(x|c)$ because of the one-pass ODE
construction. This is the sense in which the certificate program's weights
were valid with no approximation beyond discretization and probe noise.

### 18. The iterations, in order, with what each taught

**Baseline measurement.** Valid fiber weights on the standard four cases —
$(L{:}\beta)$ = $16{:}14.1$, $16{:}55$, $32{:}55$, $32{:}218.6$ — gave
log-weight standard deviations of **18 / 42 / 84 / 164** respectively.
Recall the bar: usable reweighting needs $O(1{-}3)$. ESS was pinned at its
floor of $1/N$ everywhere. Two structural facts were extracted. First, the
spread scales like $\beta V$ — pointing to a small *coherent* per-plaquette
error, not isolated blunders. (For calibration: topology-sector action
differences are only $2\pi^2\beta/V \approx 4$ log-units — far too small to
explain spreads of 40–160, so this is not a topology problem.) Second,
stability controls (8 Hutchinson probes; 240 integration steps) left the
numbers unchanged — the spread is model density error, not estimator noise.

**Tier 0 — proposal-knob sweep (free, no retraining).** The sampling-time
knobs — terminal noise floor, exact-score blend strength, guidance weight —
parameterize a *family* of proposal distributions, each of which gets its own
valid density from the one-pass machinery. So ESS can be tuned over this
family for free. Result: lowering the terminal floor coefficient from 0.1 to
0.03 genuinely helped (std $42 \to 24$ at $16{:}55$). The mechanism is an
"endgame offset": the ODE stops integrating at $\sigma_{\min}$ — its samples
follow the *slightly noised* target — while the weights compare against the
$\sigma = 0$ target; integrating closer to zero shrinks that mismatch. Sharp
negative from the same sweep: *strengthening* the analytic score blend
monotonically **hurt** (std up to 128 at blend strength 4). The blend's
harmonic approximation,

$$
\beta_{\mathrm{eff}} \;=\; \frac{\beta}{1 + 4\beta\sigma^2},
$$

is derived for the $\sigma \to 0$ endgame; at mid-sigma it is a *worse*
density model than the learned score, and leaning on it there poisons the
transport. Tools earn their keep only in the regime they were derived for.

**Tier 2 — maximum-likelihood fine-tuning (negative, with a mechanism).** We
built a fully differentiable version of the ODE likelihood — gradients flow
through the entire trajectory *and* through the divergence estimate, a
second-order construction — and used it to maximize
$\mathbb{E}_{\mathrm{data}}[\log q(\text{fine} \mid \text{coarse})]$ starting
from the warm checkpoint. Validation likelihood improved dramatically
($+0.37$ nats per degree of freedom, roughly 190 log-units per
configuration). Deployed weight spread got **worse at every coupling**. The
mechanism is the **forward/reverse KL asymmetry**, which is worth stating
precisely because it recurred three times (here, and in the correction head
at two very different capacities). The ML objective is, up to a
model-independent entropy constant,

$$
\mathbb{E}_{\pi_c}\, \mathbb{E}_{p(x|c)}\big[ -\log q(x|c) \big]
\;=\; \mathbb{E}_{\pi_c}\big[ \mathrm{KL}\big( p(\cdot|c) \,\|\, q(\cdot|c) \big) \big] + \mathrm{const},
$$

an expectation **under the target** $p$: it penalizes $q$ being small where
*data* lives, and is utterly indifferent to where $q$ puts the rest of its
mass. The weight variance that controls ESS is instead governed by
fluctuations of $\log(p/q)$ **under the model** $q$ — the
$\mathrm{KL}(q \| p)$ / $\chi^2(p \| q)$ direction: it penalizes $q$ putting
mass where the target is small, i.e. exactly the regions the sampler visits
but the data never does. The two divergences share a unique global minimum
(the perfect model) but away from it their gradients are not even positively
correlated: a finite-capacity model improving one can *systematically* worsen
the other, which is precisely what the measurements show. A model can sharpen
onto the data manifold while simultaneously carving density away from the
regions its own sampler actually visits.
Lesson, now a project rule: **validation likelihood is the wrong selection
metric for ESS.**

**Tier 3, first attempt — single-case reverse KL (negative, caught by
design).** Minimize the reverse direction directly:

$$
\mathbb{E}_q\big[\, S(x) + \log q(x) \,\big] \;=\; \mathrm{KL}(q \,\|\, p) + \text{const},
$$

with the gradient taken by backpropagating through the deterministic ODE
trajectory (the reparameterization trick — possible only *because* the
sampler is an ODE), trained at the single case $16{:}55$. Its own evaluation
ESS doubled. Fresh-seed verification then showed the gain was **selection
noise on a fixed evaluation set** — and worse, the never-trained
extrapolation coupling had been destroyed (std 555 at $32{:}218.6$, against
161 for the untouched baseline). Both
failure modes were promptly engineered away:

**Tier 3, second attempt — rkl2 (the one genuine model improvement).**
Round-robin reverse-KL training over three cases spanning the coupling range;
evaluation on rotating *disjoint* coarse subsets with rotating seeds (nothing
fixed to overfit by selection); and checkpoint saves gated on two conditions
simultaneously — mean ESS improvement *and* a never-trained extrapolation
monitor staying below $1.5\times$ its initial spread. The guard did real
work: it blocked 4 of 6 save opportunities, including the
highest-training-ESS state. Result under fresh-seed verification: **spread
reduced by $1.33\times$ on the geometric mean over the four standard cases**
— 19.2 / 18.3 / 53.9 / 127.8 against a baseline of 17.5 / 42.0 / 63.2 /
161.1 — including on cases never trained on, later extended to five
never-trained points from $\beta = 2$ to $218$. The gain is **not uniform**,
and the original claim that it halved the spread at *every* coupling does not
survive regeneration: it is $2.3\times$ at $16{:}55$, where the spread was
largest, $1.2$–$1.3\times$ at the two $L=32$ cases, and $1.09\times$
*negative* at the mildest case $16{:}14.1$. It remains the unique optimum on
the guard protocol's aggregate criterion, so it is kept and is the default
checkpoint — but the honest frame tightens rather than loosens: ESS stayed at
$1/N$, and $42 \to 18$ at one case out of four is a modest step measured
against a bar of $O(1{-}3)$ — the first step on a logarithmic journey, not
the last.

**Capacity/data scale-up (negative — the "just scale it" falsification).**
Hypothesis: the density gap is a capacity/coverage problem, so a bigger
network with more data closes it. Test: $3.7\times$ parameters, 24 additional
$L=32$ training ensembles, fresh training ($59$ min on the RTX 5060, against
$\sim 4.7$ h for the same config on the Snapdragon CPU). Result:
better than the baseline at every monitor but worse than rkl2 on the
aggregate (geometric mean 45.5 against rkl2's 39.4), and — a detail the
frozen campaign's numbers hid — it is actually the *best* variant at the
mildest monitor ($15.0$ at $16{:}14.1$, beating both baseline and rkl2). The
verdict "discarded" therefore rests on the aggregate criterion, not on a
clean sweep; under subsequent reverse-KL pressure
its extrapolation collapsed immediately (every save guard-blocked).
Interpretation, two-fold: DSM's pointwise regression objective simply does
not target the *integrated transport error* that determines $\log q$ — being
slightly wrong everywhere along the trajectory in a correlated way is
invisible to the pointwise loss but fatal to the likelihood. And the small
network's restrictive function class was itself the *regularizer* that made
extrapolation work; extra capacity spent that inheritance on in-distribution
fit. You get what you train for.

**The frontier scan (the decisive measurement).** To decide whether any
avenue could close the gap, we measured the per-site decomposition
$\mathrm{std}(\log w) / (2L^2)$ — density error per link — across a grid
$L \in \{8, 16\}$, $\beta \in [2, 55]$:

- **Volume behavior is benign.** At fixed $\beta$, total spread grows like
  $\sqrt{V}$ — the signature of *independent per-site errors* — with the
  per-site error actually dropping slightly with $L$. Volume is not the
  enemy; there is no coherent $\propto V$ catastrophe.
- **Coupling behavior holds the surprise.** Per-site error is 0.02–0.04 nats
  around the trained region, and — contrary to my prior prediction —
  **2–3× worse at low beta** (0.05–0.07 nats at $L=8$, $\beta \le 14$).
  Wide, entropy-rich distributions are harder to transport accurately than
  narrow, stiff ones: at high $\beta$ the target is almost a Gaussian spike
  the model can nail, while at low $\beta$ the model must move probability
  mass across a genuinely broad, multimodal landscape and every misplaced
  sliver costs log-density. My earlier prediction that small volumes would
  already be in usable-ESS territory was wrong for exactly this reason.
- **The bar, quantified.** Usable ESS needs total spread $O(1{-}3)$, which
  at these volumes means **per-site error below $\sim 0.005$ nats**. The
  current best is 3.7–12.5× away from that bar, *everywhere* in the scanned
  region — there is no corner of parameter space where the certificate
  almost works.

**SMC ladder (estimator-side attempt, quantified negative).** Could smarter
estimator structure substitute for density quality? Sequential Monte Carlo
over the production ladder: per-level fiber weights plus systematic
resampling at each rung — the textbook-correct SMC structure, cross-checked
against the frontier numbers. The result is arithmetic, not subtle: at
per-level $\mathrm{ESS} = 1/N$, resampling collapses each generation to
$\sim 2$ unique ancestors (unique fraction 0.01). The machinery is right but
has no weight diversity to work with; it would become valuable only *after*
the per-level spread is fixed. Estimator restructuring cannot substitute for
model density quality — it can only harvest quality that already exists.

**The correction head (the terminating experiment).** One cheap hypothesis
remained. The baseline scaling ($\mathrm{std} \propto \beta V$) suggests a
small *coherent, physics-shaped* score offset — and a uniform per-plaquette
drift error points exactly along one distinguished direction in function
space: the Wilson-action curl. Test: a $\sim 350$-parameter head,

$$
s_{\mathrm{eff}} \;=\; \big(1 + a(\sigma, \beta)\big)\, s_{\mathrm{model}}
\;+\; b(\sigma, \beta)\, \mathrm{curl}_{\mathrm{Wilson}}(\theta, \beta_{\mathrm{eff}}),
$$

with $a, b$ two smooth scalar functions of $(\sigma, \beta)$ from a
zero-initialized MLP, the base network frozen, trained by the differentiable
ODE likelihood over all 106 continuous-beta rungs, judged on disjoint
fresh-seed cases. The tiny capacity is matched to the hypothesis *on
purpose*: two smooth scalars of $(\sigma, \beta)$ cannot memorize
configurations or couplings, so if this helps, it generalizes by
construction — and if it fails, the conclusion is equally sharp: the residual
density error is genuinely high-dimensional, not a physics-shaped offset, and
the entire fine-tuning avenue is closed.

**Verdict (2026-08-02): decisively negative — and mechanistically the most
instructive failure of the program.** Training reproduced the Tier-2 pattern
in miniature: the data-side validation likelihood improved substantially
($-1.044 \to -0.607$ per degree of freedom by step 50, the best-validation
save), after which the coefficients diverged (the large-$\sigma$ Wilson-drift
coefficient $b$ ran away to $\sim 13$ by step 200 while validation collapsed
— the optimizer had found a direction that inflates data-side integrated
likelihood by distorting the large-$\sigma$ flow). But the damning result is
the *best-validation* checkpoint, evaluated on disjoint fresh-seed cases: the
deployed log-weight spread grew $2$–$6\times$ at **every** case relative to
the uncorrected model (e.g. $16{:}25$: $18 \to 106$; $32{:}14.1$: $42 \to
156$), and the corrected sampler's raw observables acquired enormous biases
(plaquette $z$-scores of $-26$ to $-66$). The forward/reverse-KL asymmetry is
therefore **not a capacity phenomenon**: even 354 physics-shaped parameters,
selected at their data-likelihood optimum, move density *toward* the data
manifold and *away* from the model's own sampling trajectories. Two
conclusions follow. First, the residual density error is not a coherent
$(\sigma, \beta)$-smooth offset — the hypothesis is falsified in its
strongest form. Second, data-side maximum likelihood is structurally the
wrong objective for improving a sampler's own density, at any capacity; only
sampling-side (reverse-KL) training ever helped here, and it plateaued at the
$2\times$ delivered by rkl2. With that, the fine-tuning avenue is closed:
`score_net_rkl2.pt` stands as the final density checkpoint of the U(1)
program, the per-site gap stands at $0.02$–$0.07$ nats against the
$\sim 0.005$ bar, and further progress on the exactness certificate is a
from-scratch likelihood-native training project — deliberately not
undertaken, for the strategic reasons recorded in Section 20.

### 18.5 The Villain control: how it works, what it gave, and whether it was worth it

Sections 15--18 established that the model's density sits about a nat per site
away from the target, and that six interventions failed to close it. One
competing explanation survived all of them, and it is not a model defect at
all.

**The question the control answers.** The pipeline conditions each generation
on a coarse configuration drawn from a *single-coupling* Wilson ensemble. But
the true blocked measure of a Wilson theory is not a single-coupling Wilson
theory: blocking induces rectangle terms, higher characters, and an infinite
tail of further couplings. Projecting all of that onto one $\beta_c$ is an
approximation, and whatever it discards shows up in the importance weights
*without being the score model's fault*. If that projection error were the
dominant term, the entire fine-tuning program would have been chasing
something no amount of fine-side training could fix. So: is the measured gap
model error, or matching error?

**How the control works.** For the Villain action the blocking relation is
exact. The Villain plaquette weight is a wrapped Gaussian of variance
$1/\beta$; the coarse plaquette is the wrapped sum of four of them; wrapped
convolution adds variances, giving $4/\beta_f$; demanding that equal
$1/\beta_c$ gives

$$
\beta_c \;=\; \beta_f/4 \qquad \text{exactly, with no truncation.}
$$

There is no induced-coupling tail to discard, so a Villain arm has *no*
matching residual by construction and its fiber spread is model error alone.
Run both arms at matched cases and the difference isolates the matching floor.
That is the design.

**What it gave.** The arms were run at three cases. The Villain arm was rerun
on 2026-08-03 after a bug fix: `approx_matched_coarse_beta` had been called
without its `action_type` argument, whose default is `"wilson"`, so the arm
had been running at $\beta_c = 4.0$ and $14.1464$ instead of the exact
$14.1464/4 = 3.5366$ and $55.0237/4 = 13.7559$. Both runs are internally
valid --- the base HMC, $S_{\rm matched}$ and $\Delta F$ all used the same
$\beta_c$ --- but only the corrected one has the exact-matching property the
control depends on.

| arm | 16:14.1 std/site ($R^2_c$) | 16:55.0 | 32:55.0 |
|---|---|---|---|
| Wilson (matching residual + model error) | 0.0238 (0.045) | 0.0364 (0.105) | 0.0173 (0.085) |
| Villain, $\beta_c = \beta_f/4$ (corrected) | 0.0257 (0.023) | 0.0366 (0.016) | 0.0187 (0.106) |
| Villain, Wilson-matched $\beta_c$ (superseded) | 0.0287 (0.174) | 0.0459 (0.031) | 0.0268 (0.048) |

The first two rows are the current measurement. The third is retained from the
original campaign and was **not** re-measured — only the corrected variant is
worth spending compute on — so it is a historical row, and the
corrected-vs-superseded comparison below is likewise an observation about that
campaign rather than a re-verified result.

**The correction made the control's arm worse, not better.** Fixing the
matching *raised* the Villain spreads by $+4\%$, $+99\%$ and $+51\%$. That is
the opposite of the expected direction and it deserves an explanation rather
than a footnote. (Read against the corrected row as it now stands, the
apparent size of this effect is smaller still; the sign, which is what the
argument turns on, is what the original run established.)

The most likely cause is conditioning-distribution shift. The checkpoint was
trained on **Wilson** data, and $4.0$ and $14.1464$ are not arbitrary numbers:
they are literally the ladder's own coarse couplings (`ladder.beta_schedule =
[4.0, 14.1464, 55.0237]`, with $14.1464$ also a training rung at $L = 16$).
The buggy run therefore happened to present the model with coarse ensembles
close to those it was built around, while the corrected run presents Villain
ensembles at couplings that appear nowhere in training. The corrected arm thus
measures model error *plus* an out-of-distribution conditioning penalty.

That story should not be oversold: the effect is **not monotone** in the
$\beta_c$ error. The $13\%$ mismatch at $\beta_f = 14.1$ moved the spread by
$+4\%$, while the $2.8\%$ mismatch at $\beta_f = 55.0$ moved it by $+99\%$. A
single-parameter "sensitivity to $\beta_c$" account does not fit. Something
discrete --- seen-versus-unseen conditioning --- fits better, but separating
the two would take a dedicated experiment, and none was run.

**Was the control useful? Partly, and not in the way intended.**

*As a subtraction, no.* Wilson $-$ Villain was supposed to be the matching
floor. It cannot be read that way, because the two arms differ by more than
the presence of a matching residual: they differ in the action generating the
conditioner and in how far that conditioner sits from anything the model was
trained on. And the effect being resolved is small --- bounded below at a few
percent of the variance --- while the study's own Table S5 shows *checkpoint
variants of the same architecture moving spreads by factors of 2--6*. An
effect cannot be resolved by a comparison whose confounds are an order of
magnitude larger than the signal. This is also why retraining a
Villain-specific checkpoint would not rescue the design: it would replace an
out-of-distribution confound with a model-identity confound of comparable or
greater size.

*As a consistency check, yes --- but a thin one.* Wilson $\le$ Villain at
every case, so the ordering the matching-floor hypothesis would have had to
violate is intact: had Wilson come out *above* Villain, the excess would have
been a candidate matching floor and the whole closure would have been in
doubt. It did not. The margin, however, is slim --- Villain exceeds Wilson by
$8\%$, $0.5\%$ and $8\%$ of the Wilson spread, and the middle case is a tie
within any reasonable error. An earlier draft of this section reported the
margin as *wide* ($43$–$132\%$); that reading came from a single campaign and
did not survive re-measurement. The check should therefore be read as "the
ordering is not violated", which is all the argument needs, and not as
"Villain is substantially worse", which the data no longer supports.

*And the question it was built for is answered anyway, by a cleaner argument
that needs no second arm.* The matching residual is, by construction, a
function of the coarse configuration alone --- it is the discrepancy between
$S_{\rm matched}(c)$ and the true blocked action evaluated on the same $c$.
Any such term can therefore contribute **only** to the coarse-explainable
share of the fiber log-weight variance, $R^2_c$. And $R^2_c$ is measured
directly, within a single arm, with no cross-model comparison: for Wilson it
is $0.045$, $0.105$, $0.085$. At most about **ten percent** of the variance is
coarse-explainable *at all*, and even that is an upper bound, because
$c$-dependent **model** error lands in the same regression. The matching floor
is therefore negligible against a gap of $\approx 1$ nat/site, and the
measured density gap is fine-side model error. The Villain arm corroborates
this. It never had to carry it.

Two honest notes on this number. It is roughly **twice** the bound the
original campaign reported ($0.062$, $0.005$, $0.023$, quoted then as "about
six percent"), so the ceiling on any matching-residual contribution is looser
than previously claimed --- the conclusion is unchanged, the margin is not.
And $R^2_c$ is the *least* stable quantity in this section: across the two
campaigns individual cases moved by more than a factor of twenty (Wilson
$16{:}55$ went $0.005 \to 0.105$), which is unsurprising for a regression
$R^2$ estimated from $96$ configurations against a handful of coarse
observables. The argument is robust because it needs only "$R^2_c$ is small",
a statement that survives at either value; any future use of these numbers
should carry that caveat rather than treating a specific $R^2_c$ as measured
to better than a factor of a few. The rise itself is corroborated, though: the
coarse regressions computed independently from the AIS baseline samples give
$R^2_c = 0.006$–$0.100$, with $0.100$ at $16{:}55$ against the
matching-residual arm's $0.105$ on a separately drawn ensemble.

**The transferable lesson.** When the quantity of interest is small compared
with model-to-model variation, prefer a *within-model decomposition* to a
*cross-arm subtraction*. The decomposition here --- regress the log-weights on
coarse-only observables and read off the explainable share --- costs one
linear fit on data already in hand, has no confound, and gave a tighter answer
than the second campaign it was meant to be checked against. The same
reasoning applies directly to the non-abelian successor, where exact
companion actions are scarcer and cross-arm controls correspondingly more
expensive and more confounded.

### 19. The generalization discipline (what keeps all of this honest)

Overfitting was not a hypothetical risk here — it actually happened twice
(single-case RKL; big-net RKL) and was *caught* twice. The protocol that did
the catching, now standard for every experiment in this project:

1. **Fresh-seed verification only.** Judgments are made exclusively on
   verification runs with new seeds, never on training-time evaluations —
   and every evaluation regenerates its ensembles from scratch, so
   configuration-level overfitting is structurally impossible, not merely
   discouraged.
2. **Disjoint case splits.** Improvements are judged on $(L, \beta)$
   combinations never used in either training or checkpoint selection.
3. **Rotating evaluation subsets** during training — no fixed eval set means
   no way to overfit by repeatedly selecting against it.
4. **Never-trained monitor cases** with veto power over checkpoint saves
   (the guard that blocked 4 of 6 saves in rkl2, including the
   most-tempting one).
5. **Capacity matched to hypothesis** wherever possible — the correction
   head is the extreme case: an experiment *designed* so that success would
   generalize by construction and failure would be conclusive.
6. **Degenerate-weight guards in reporting.** When the effective sample
   count is $\sim 1$, the SNIS error estimate is itself invalid (it is
   computed from the same collapsed weights), so z-scores are suppressed
   rather than printed with absurd false precision.

### 20. Where this leaves the physics claims

Two claims, cleanly separated — the separation itself being one of the
week's products:

- **As a sampler graded on observables** (the paper's actual claim):
  validated far outside the training range, with flat *marginal* generation
  cost in exactly the regime where exact-by-construction HMC becomes
  unusable — plus the seeding mode, where diffusion supplies the expensive
  thermalized starting ensemble and a seconds-long exact MCMC tail supplies
  correctness. This claim stands, was never in question this week, and is
  the transferable architecture.

  Three scoping qualifications, added by the 2026-08-03 audit, so that
  "validated" is not read as more than it is. (i) *It is an upper bound on
  bias, and a tight one*: the median relative SEM on the plaquette is
  0.0087%, so passing $|z|\le 2$ means "no bias above ~2 parts in $10^4$
  detected", not "agreement". (ii) *There is a small coherent residual*: all
  20 Wilson-type observables carry a negative mean $z$ (plaquette
  $-0.423\pm0.204$) — the generated ensembles are systematically very
  slightly less ordered than exact. (iii) *The residual concentrates in
  extended observables*: $\mathrm{std}(z)$ grows monotonically with loop
  area, $1.09$ at $W(4\times4)$ to $1.44$ at $W(12\times12)$, with
  $\max|z|$ rising $3.1 \to 5.9$. That last item is the observable-side
  shadow of the density gap below — the error lives in the long-wavelength
  modes that local rethermalization relaxes slowest — and it is a *measured*
  bridge between the two bullets rather than a conjectured one. It is not an
  error-bar artifact: the coarse base at thin=5 has $\tau_{\rm int} =
  0.50$–$0.62$, bounding inherited-correlation inflation at $\le 1.12\times$,
  and $z_{\rm exact}$ never involves the reference chain's errors.

  Cost honesty, same audit: the flat cost above is a *marginal* cost. The
  campaign that produced the checkpoint cost 8820 s once (21.7 min data +
  125.3 min training), which exceeds every instanton-HMC burn-in that
  converges; for a single ensemble at a single coupling below $\beta\approx55$
  the classical baseline is cheaper outright. The defensible claim is that
  the generative cost is a fixed charge plus a $\beta$-independent marginal
  cost, against a baseline whose entry cost diverges and then stops reaching
  correctness at all.

- **As an exact sampler certified by importance weights** (the flow papers'
  claim): now *quantified* as out of reach — per-site density error of
  0.018–0.062 nats against a bar of $\sim 0.005$ — with a documented
  falsification chain showing that sampler knobs, both directions of
  KL fine-tuning, capacity/data scaling, and estimator restructuring do not
  close the gap. And in the non-abelian target theory this route is
  unavailable *in principle* (the forward heat kernel, and hence the score
  target, is itself approximate — Section 9), which converts this week's
  negative into a design directive:

> **Exactness must come from Markov-chain machinery wrapped around the
> generative proposal — Metropolis tails, seeded chains — not from the
> proposal's own likelihood.**

Read the emphasis literally: **must**, not *does*. The directive describes
what the successor has to be built around, not a property this pipeline
already delivers. As deployed, the U(1) ladder applies no accept/reject to
the generated proposal — the only Metropolis moves live inside the local
rethermalization sweeps and the instanton hop. Sixteen local sweeps reduce
the proposal's bias without removing it, and they are slowest precisely on
the long-wavelength modes where the residual sits (§20, item iii). So the
generation pipeline is an *observable-validated heuristic*, asymptotically
exact only in the retherm $\to\infty$ limit, which costs what direct
simulation costs: the exactness knob and the speedup knob are the same knob.
What is genuinely asymptotically exact is the **seeded** mode — exact HMC
started from a diffusion configuration, correct within its sector, with the
sector supplied by the transport identity of §8. That is the mode the
head-to-head, seeding and three-way results validate, and the one to carry
forward.

That directive — together with the ladder, the equivariance strategy, the
topology transport machinery, and the honesty protocol — is the inheritance
the next model (non-abelian) starts from.

### 21. Annealed importance sampling: the mathematical completion of the transport

Everything in sections 15–18 measured the gap between the diffusion model's
density $q$ and the target $p$ and tried to *shrink* it by changing $q$. The
program's five converged negatives said: within this model class and
objective, $q$ is as close to $p$ as it will get. Annealed importance
sampling (AIS; Neal 2001) is the one mechanism that attacks the gap without
touching $q$ at all — and it composes with the diffusion machinery so cleanly
that it is best understood as the *continuation* of the probability-flow
transport by other means.

**The structural fit.** The probability-flow ODE (section 16) is a
deterministic transport: it carries a wrapped-Gaussian reference at
$\sigma_{\max}$ down to the model distribution at $\sigma_{\min}$, and the
instantaneous change-of-variables formula hands us, for each sample $x_0$,
the exact value $\log q(x_0 \mid c)$. That pair — a sample *with its own
density* — is precisely the input AIS needs and precisely what ordinary MCMC
initialization throws away. Rethermalization (the pipeline's Markov-chain
wrapper) destroys density tracking: after a few HMC sweeps we no longer know
the density of what we have, which is why retherm gives correctness without
importance weights. AIS threads the needle: it interleaves the *same kind* of
exact MCMC updates with weight increments arranged so that density tracking
is never needed beyond the starting point.

**The construction.** We cannot evaluate $q$ at new points (one ODE solve
gives the density only of its own endpoint), so the bridge does not
interpolate $q \to p$ directly. Instead, fit a tractable *surrogate* for the
log-density mismatch: with differentiable gauge-invariant observables
$O_k(x)$ (plaquette characters, rectangles, the matched coarse action of the
blocked field, a smooth $Q^2$),

$$
\log \tilde q(x) \;=\; -S_f(x) + G(x), \qquad
G(x) \;=\; \textstyle\sum_k g_k\, O_k(x) + \text{const},
$$

with $g$ fit by ridge-regularized least squares of $\log q + S_f$ on the
features at the initial samples — an $L^2(q)$ projection of the log-density
error onto the feature span. Then define the bridge family

$$
\pi_t(x) \;\propto\; \exp\!\bigl(-S_f(x) + (1-t)\,G(x)\bigr),
\qquad t: 0 \to 1,
$$

so $\pi_0 = \tilde q$ (the surrogate approximation of the model) and
$\pi_1 = p$ (the exact target). Every $\pi_t$ is known in closed form up to
normalization and is autograd-differentiable — so the *same* HMC and
instanton-hop kernels that give the pipeline its exactness apply to every
bridge distribution unchanged.

**The weight identity and why it is unbiased.** Run $K$ bridge steps
$t_0 = 0 < t_1 < \dots < t_K = 1$. After accumulating increment $k$, move
the sample by any kernel $T_k$ that leaves $\pi_{t_k}$ invariant. The AIS
weight telescopes:

$$
\log w \;=\; \underbrace{\bigl[\log \tilde q(x_0) - \log q(x_0 \mid
c_0)\bigr]}_{\text{surrogate fit residual}} \;+\;
\underbrace{\sum_{k=1}^{K} (t_{k-1} - t_k)\, G(x_{k-1})}_{\text{AIS
increments}} .
$$

Unbiasedness is three lines of the extended-state-space argument: the joint
forward density of the trajectory $(x_0, \dots, x_K)$ is
$q(x_0)\prod_k T_k(x_{k-1} \to x_k)$; multiply and divide by the reverse
trajectory density built from the reversals $\tilde T_k$ (detailed balance
w.r.t. $\pi_{t_k}$ gives $\pi_{t_k}(x_{k-1}) T_k(x_{k-1} \to x_k) =
\pi_{t_k}(x_k) \tilde T_k(x_k \to x_{k-1})$); every transition-kernel factor
cancels against its reversal, and what survives is exactly the ratio of
consecutive bridge densities — the increments above. Hence
$\mathbb{E}[w\, h(x_K)] = Z_{\text{ratio}}\, \mathbb{E}_{p}[h]$ for any $h$:
valid importance weights with **no density tracking through the MCMC**. This
is the precise sense in which AIS reconciles the two exactness routes the
program had kept separate — the weighted route (needs density, no MCMC) and
the retherm route (MCMC, no density).

**The variance budget, and the floor theorem we then measured.** The two
terms of $\log w$ are independent levers:

$$
\operatorname{Var}[\log w] \;=\;
\operatorname{Var}\bigl[\underbrace{\log \tilde q - \log q}_{\text{fit
residual}}\bigr] \;+\; \textstyle\sum_k \operatorname{Var}[\text{increment}_k].
$$

The increments shrink as the schedule refines — they can be paid down with
compute. The fit residual **cannot**: it is fixed the moment the basis is
chosen, and equals $(1 - R^2)\cdot\operatorname{Var}[\text{target}]$ from
the regression. So AIS comes with a sharp falsifiable prediction: as $K$
grows, the delivered log-weight std must converge to
$\sqrt{1 - R^2}\,\cdot\,\text{std}_{\text{before}}$ and no further. The
measurement (Table S7 of the appendix): at the extrapolation case
$32{:}218.6$, predicted floor $47.1$, measured $44.7$ — the bridge saturates
its floor. What remains is a *basis-representation* question, not a bridging
question.

**How often that happens (measured 2026-08-14).** The paragraph above rests
on one seed, which is not enough to say "the mechanism works as derived."
Repeating the extrapolation case across all ten runs on record at the shipped
protocol gives a strictly bimodal outcome: **eight reduce the spread by
1.97–2.71× (mean 2.42×), two diverge by $10^2$–$10^3$.** A 20% failure rate
(95% CI 6–51%, binomial score interval) belongs in the claim: the floor is
reachable and is
reached about four times in five. Table S7b of the appendix carries the
per-seed table.

**The failure is the surrogate's regularization** (corrected 2026-08-14; this
paragraph previously concluded "the failure is in the bridge, not the basis").
Held-out $R^2$ genuinely does not separate the two modes — the diverged seeds
sit at $0.869$ and $0.940$, at or *above* every healthy seed ($0.756$–$0.909$)
— and minimum bridge-HMC acceptance genuinely does ($0.052$ and $0.370$ against
$0.865$–$0.974$), with the worse of the two also collapsing its step size
$13\times$. Both observations survive. The inference drawn from them did not.

Three quantities move together here — ridge, coefficient norm, and acceptance
— and reading a cause off their correlation was the mistake. Both divergent
seeds had also selected the *smallest ridge on the grid*, $0.001$, and no
converged seed had ($p = 0.022$ under independence), with standardized
coefficient norms of $231$ and $247$ against $40$–$105$ for the eight
successes. Intervening settles it: holding the ODE samples, baseline and seed
byte-identical and varying only a lower bound on the ridge grid moves held-out
$\sigma$ from $2132$ to $43.1$ at this case. Regularization alone spans both
modes, so the chain is *under-regularized surrogate $\to$ steep bridge $\to$
integrator failure*, one mechanism rather than two independent ones.

That also demotes the guard. Acceptance is downstream, and it misses cases: in
the same scan, $32{:}218.6$ blows up to $18\times$ its baseline while minimum
acceptance sits unchanged at $0.958$. An acceptance floor would not have fired.
The quantity to assert on is the surrogate coefficient norm. And the selection
rule itself is unsound for this problem — `fit_surrogate_cv` scores ridges by
out-of-fold residual, but its held-out folds come from the same ODE samples as
the fit folds and therefore lie *on* the fit manifold, precisely where the
pathological coefficients are well behaved. Cross-validation cannot see this
failure by construction. Table S7c carries the scan.

An unrelated check on the headline survives all of this: over the eight healthy
seeds the free-energy certificate returns $1.01$–$1.68$ nats/site (mean
$1.16$) at this case, an estimator sharing no machinery with the fiber-weight
route and landing on the same $\sim 1$ nat/site bulk offset — the headline
density gap is not an artifact of one estimator.

**Why widening the basis is not the answer either.** The obvious next move —
add features until $R^2 \to 1$ — was tried (11 features) and produced the
program's sixth converged negative: in-sample $R^2$ rose, and the held-out
weights exploded by two to three orders of magnitude at two of four cases.
The story was that a wide, *weakly-regularized* basis extrapolates wildly once
the bridge dynamics move samples off the fit manifold — the
deployment-vs-data-side asymmetry of section 18 in another costume. The
10-seed repeat shows the *narrow* basis fails at a comparable rate with no
loss of held-out $R^2$, so width is not the lever it was taken to be. But the
ridge intervention above vindicates the other half of that story: it is
exactly regularization, and exactly off-manifold extrapolation, and it fires
at any basis width. Width was the wrong noun in a sentence that was otherwise
right — which is why widening did not help and narrowing does not protect.

Two lessons generalize past this project. A mechanism validated on a single
seed at a single case measures the mechanism *and* the draw, and here the draw
was carrying 20% of the claim. And when several quantities move together, the
one that separates your outcomes most cleanly is not thereby the cause — the
acceptance rate separated the modes perfectly and was still the symptom. Only
the intervention, holding everything else byte-identical, settled it.

**The sector decomposition of the remaining gap.** The weights after AIS
still degenerate — but now we can say precisely on what. Write the model's
error as (bulk smooth offset) + (topological-sector frequency mismatch). The
bulk part regresses onto smooth observables and anneals through the bridge;
the sector part is a *single number per sector* (how much probability the
model puts in sector $Q$ versus the target's exactly-known $P(Q)$) and is
invisible to any smooth feature. Conditioning fixes it in principle: for any
observable $h$,

$$
\mathbb{E}_p[h] \;=\; \sum_Q P_{\text{exact}}(Q)\;
\mathbb{E}_p[h \mid Q],
$$

and within-sector self-normalized weights validly estimate each
$\mathbb{E}_p[h \mid Q]$ (conditioning on a weight-measurable event preserves
the importance identity), while the exactly solvable theory supplies
$P_{\text{exact}}(Q)$ — the abelian crutch. Measured: the sector masses are
indeed removed, but the *within-sector* spread is the same bulk
$0.02$–$0.07$ nats/site as everywhere else, so per-sector estimates remain
single-sample-dominated at $n \approx 100$. The two components of the gap are
now separately quantified, and each crutch (bridge for the bulk, sectors for
the topology) demonstrably removes its own component — they simply cannot,
at this model quality, jointly reach usable ESS.

**The KL identity — the certificate that became a measurement.** For any
valid weights, Jensen's inequality has an exact companion:

$$
\mathbb{E}_q[\log w] \;=\; \Delta F_{\text{exact}} \;-\;
\mathrm{KL}(q \,\|\, p),
$$

and in this theory $\Delta F_{\text{exact}}$ is computable from the character
expansion. The free-energy certificate was built to *verify* the weight chain
(log-mean-exp must equal $\Delta F$); at the model's actual ESS the
log-mean-exp cannot converge — but the *mean* log-weight turns the same
identity into an unbiased, error-barred **measurement of
$\mathrm{KL}(q\|p)$**: about $0.9$–$1.0$ nats per site. That single number is
the program's cleanest statement of where the generative model ends: the
per-site density offset that five fine-tunes, a capacity scale-up, a
physics-form correction, and an annealed bridge each confronted, quantified —
and left standing.

### 21.5 The open problem: topology without an exact $P(Q)$

**Status change, 2026-08-14.** This section was written as an unrun open
problem. Routes 1 and 2 below have since been measured, and the dependency is
substantially smaller than the section claimed — the load-bearing number it
rested on (C_L128 transport χ² p = 0.005) was stale, and the current ensembles
of record give **0.8663**. The original framing is kept below with corrections
marked, because the reasoning about *why* the dependency would matter is still
the right reasoning; it is the premise that failed. The measurements are in
§21.6.

**The dependency.** Sector statistics in this study are made correct by one of
two mechanisms, and only one of them exists outside a solvable theory:

- *Transport mode* — the model's own sector, carried up from the coarse
  configuration by the instanton projection of §13. Available anywhere.
- *Exact-sector mode* — configurations are resampled so the sector histogram
  matches the analytically known finite-volume $P(Q)$. Available only where
  $P(Q)$ is known in closed form, i.e. essentially only here.

~~Exact-sector mode is what rescues the topology results: $\chi^2$ failures
fall $5/35 \to 1/35$ and worst $|z(\langle Q^2\rangle)|$ falls $11.8 \to 2.8$
(Table S3). At $L = 128$ the Wilson observables pass in either mode, but the
topology passes **only** in exact-sector mode ($p:\ 0.005 \to 0.39$). So the
headline large-volume result rests on a crutch that 4D SU(3) does not
provide.~~

**Corrected (2026-08-14).** Regenerated from the current ensembles of record
(Table S3, `42_sector_mode_table.py`), $\chi^2$ failures are $3/35$ transport
against $2/35$ exact-sector — both at the multiple-testing false-positive rate,
so the two modes are not distinguishable on that metric. All three transport
failures are track-B cases whose base coupling is *deliberately* mismatched;
none is a volume case. At $L = 128$ transport gives $p = 0.8663$ and
exact-sector $0.3875$, so topology passes **in both**, and the crutch does not
rescue it. What exact-sector mode still does is tighten
$\langle Q^2\rangle$ (worst $|z|$: $10.9 \to 2.8$) and clear the track-B
failures. That is a real but much narrower benefit than "the large-volume
result rests on it".

**Why it gets worse with volume, measured.** With the projection disabled the
model lands in its conditioner's sector at a rate that falls roughly by half
per $4\times$ in volume — 0.484, 0.234, 0.094 at $L = 16, 32, 64$ (§13). The
raw spurious $\langle Q^2\rangle$ excess moves the same way, from 1.7–2.7 at
$L \le 32$ to 7.14–28.15 at $L = 64/128$. This is a deficiency that grows in
precisely the direction the method exists to scale in, which is what makes it
the central open problem rather than a caveat.

**What would settle it** (not run):

1. *Transport-only at $L = 64$ and $L = 128$, reported without any
   exact-$P(Q)$ resampling.* The numbers above say what to expect — failure —
   so the deliverable is the honest failure curve of $\chi^2$ and
   $z(\langle Q^2\rangle)$ against volume, not a pass.
2. *An instanton-HMC tail as the sector fixer instead of $P(Q)$.* Table S4
   already shows a 200-trajectory tail repairing $P(Q)$; the open question is
   the tail length needed as a function of $V$, and whether it grows fast
   enough to eat the flat-cost advantage. This is the practical route and it
   is theory-agnostic.
3. *A sector-aware training term.* Today's hyperparameter sweep found
   `topo_weight` to be the one knob that cleared its noise floor, which points
   here; whether that survives replication is being measured separately.

~~**The honest position.** Route 2 is the one that transfers, and its cost is
unmeasured. Until it is, the correct statement is that this pipeline
demonstrates *observable-level* scaling to $L = 128$ and *sector-level*
correctness only where $P(Q)$ is known analytically.~~ The 2D SU(2) successor
does not test this — $\pi_1(SU(2))$ is trivial, so there are no sectors to
get wrong — and that should be said explicitly rather than allowed to read as
a passed test.

### 21.6 Topology without an exact $P(Q)$: measured

Routes 1 and 2 of §21.5 were run on 2026-08-14
(`38_sector_tail_scaling.py`, `42_sector_mode_table.py`).

**Route 1 — transport-only, reported without exact-$P(Q)$ resampling.** The
expected deliverable was "the honest failure curve." There is no failure
curve. Transport-mode $\chi^2$ against exact $P(Q)$ passes at every volume
tested: $p = 0.87$ at $L = 128$, $0.24$ at $L = 64$, and across the whole
$L = 32$ $\beta$-ladder. The only transport failures anywhere are the
deliberately-mismatched track-B cases.

**Route 2 — instanton-HMC tail as the sector fixer.** The open question was
how tail length scales with $V$. Measured at fixed $\beta = 14.1464$ over a
$16\times$ volume range, and across $\beta = 4.4$–$218.6$ at $L = 32$:

| | $V = 2048$ | $8192$ | $32768$ |
|---|---|---|---|
| tail needed (traj) | 100 | 0 | 0 |
| $\chi^2$ testable bins | 7 | 11 | 15 |

No growth — the cost *falls* to zero while the test's power *rises*, so this is
not a resolution artifact. Over the $\beta$ sweep at $L = 32$ the tail never
exceeds **150 trajectories** and is usually zero. There is no scaling exponent
to quote because there is nothing scaling.

**Why transport works, structurally.** This is the ladder fixed point doing the
work, not the model. Charge projection assigns the fine configuration its
coarse partner's $Q$, and with $\beta_f = 4\beta_c$, $L_f = 2L_c$ the exact
$\langle Q^2\rangle \approx V/4\pi^2\beta$ is invariant, so the coarse $P(Q)$
*is* the fine theory's $P(Q)$. Sector correctness is inherited from HMC at the
coarse coupling, where HMC still mixes. Nothing about it needs $P(Q)$ in closed
form, so it transfers to any theory with a computable topological charge.

**What the model itself contributes: nothing, and it degrades with volume.**
Raw (pre-projection) output lands in the coarse partner's sector 4.7–29% of
the time, falling to 11.5% at $L = 64$ and 6.2% at $L = 128$. Raw
$\langle Q^2\rangle / \text{exact}$ is $\approx 1$ at weak coupling and runs to
$2.5\times$ (A_bc4), $4.6\times$ (A_bc8), $5.4\times$ (E_bc11.8) and
$2.65\times$ ($L = 128$) — the model manufactures topological charge precisely
where the theory has least. The diffusion model supplies fine-scale
fluctuations; the topology is supplied by transport.

**The honest position, revised.** The exact-$P(Q)$ dependence is not the
study's largest unresolved liability. It is used as a *diagnostic* (the χ²
against exact $P(Q)$) far more than as a *crutch*, and where it is used as a
crutch its measured benefit is tightening $\langle Q^2\rangle$ and clearing
deliberately-mismatched controls — not making large volumes pass. The residual
caveat that does survive: at $\beta \gtrsim 55$ the χ² has $\le 3$ populated
bins and at $\beta = 218.6$, $L = 32$ only one, so in the deep-frozen regime
these tests have little power and "passes" there means little. That is a
limit on the *test*, not a dependency on the crutch.

### 22. Closure: what "finished" means, and what transfers

The 2D U(1) study is finished in the strong sense: every avenue is either
adopted, or closed by a converged measurement with an understood mechanism.

* **Adopted:** the v2 campaign pipeline (retherm + instanton tails +
  exact-sector mode) for physics claims; $\sigma_{\min}$-coef $0.03$ and the
  guarded rkl2 checkpoint for likelihood work; AIS as the validated
  exactness mechanism (floor-saturating, positive spread reduction).
* **Closed with mechanism:** matching residual (negligible — established by
  the *within-arm* $R^2_c$ decomposition, since a matching residual is a
  $c$-only function and so can contribute only to the coarse-explainable
  share of the fiber log-weight variance, which is $\le 6\%$; the Villain
  arm corroborates but is confounded by a train/test mismatch and must not
  be read as a subtraction — §18.5); data-side fine-tuning in all forms (forward/reverse-KL
  asymmetry); capacity scaling (extrapolation cost); SMC (no weight
  diversity); wide surrogate bases (off-manifold extrapolation);
  sector-crutch-alone and bridge-alone exactness (each removes only its own
  component of a now fully decomposed gap).
* **Measured and named as residual:** the $\approx 1$ nat/site mean density
  offset; the $0.018$–$0.062$ nats/site spread; the volume-growing raw $Q^2$
  excess (rescued only by the abelian $P(Q)$ crutch); the repeatable
  Wilson-loop distribution-shape (KS) mismatch at the farthest extrapolation
  point, whose means nonetheless pass.
* **The claim that survived everything:** at large $\beta$, plain HMC is
  topologically frozen; instanton-HMC pays an entry cost that at $L = 64$
  leaves it $\sim\!6\sigma$ biased on Wilson observables even after
  $16\times$ the standard burn-in; the diffusion pipeline is flat-cost,
  passes all observables, and its correctness is carried by exact
  Markov-chain machinery wrapped around a proposal whose density error is
  now measured, decomposed, and understood.

What transfers to the non-abelian successor is exactly the load-bearing
structure: the ladder, the equivariant curl-form score, DSM on the group
heat kernel, retherm-based exactness, the guarded-checkpoint discipline, the
AIS bridge (whose construction needs only differentiable invariant features
and an HMC kernel — both already built for SU(2)), and the honesty protocol
that turned every negative into a mechanism. What does *not* transfer is the
exact character-expansion referee — $P(Q)$, $\Delta F$, exact observables —
which is why it was worth extracting every certificate this solvable theory
could give before leaving it.

---

## Part V — The literature this work sits in

> **Provenance and status of this Part (added 2026-08-03).** Sections 23–26
> were compiled by a systematic literature search performed *after* the U(1)
> study closed. Until that search, this document contained **two citations in
> total** (Anderson 1982 in §10, Neal 2001 in §21) and no related-work
> section. Items marked **[V]** were verified by fetching arXiv abstract pages
> or full text, in several cases with verbatim quotation; items marked **[I]**
> are inference, chiefly from exhaustive *negative* search (having looked and
> not found). **Every citation here must be checked against the actual paper
> before it appears in a submission** — this Part is a research map, not a
> verified bibliography. The conclusions in §24 are consequential enough that
> the checking is worth doing carefully.

### 23. Background: what was already known

**23.1 Inverse RG on configurations is a 2002 idea, not a 2026 one.**
Reversing a blocking transformation to *generate* fine configurations from
coarse ones originates with Ron, Swendsen and Brandt, PRL **89**, 275701
(2002) **[V]**, entirely pre-ML. The machine-learning revival is Efthymiou,
Beach and Melko, PRB **99**, 075113 (2019) **[V]** ("super-resolving the
Ising model" with CNNs), and then the reference point for field theory:
Bachtis, Aarts, Di Renzo and Lucini, **PRL 128, 081603 (2022)** **[V]**, which
inverse-transforms 2D phi^4 configurations from V = 8^2 up to V' = 512^2 and
claims to *"evade the critical slowing down effect."* Their map is a stack of
transposed convolutions — a *deterministic supervised upsampler*, not a
conditional generative model — the coupling flow is handled by histogram
reweighting rather than an analytic matching, and validation is on critical
exponents only, with no distributional check. Follow-ups: Bachtis, PRB
**110**, L140202 (2024) (spin glasses, 8^3 -> 128^3); Bachtis,
arXiv:2405.16288 (review). Rançon, Ivek and Balog, PRE **113**, 055302 (2026)
**[V]** state the framing this project also arrived at — configuration-level
inversion is *"formally impossible... can be approached probabilistically"* —
and report the sobering result that **three-parameter networks suffice** for
2D Ising inverse RG, extra capacity giving no benefit.

**23.2 The classical ancestor of this entire architecture.**
Endres, Brower, Detmold, Orginos and Pochinsky, **PRD 92, 114516 (2015)**
**[V]**, describe *"a multiscale thermalization algorithm for lattice gauge
theory... combining standard Monte Carlo with ideas drawn from real space
renormalization group and multigrid methods,"* which *"ameliorates the problem
of topological freezing."* Their procedure is: RG-matched coarse action →
equilibrate coarse cheaply → **prolongate to fine** → **rethermalize in
parallel**. Crucially their prolongator **preserves topological charge per
configuration** (fine↔prolongated Q correlation > 0.8), and rethermalization
takes ~50–100 trajectories against 1000+ from a cold or hot start. Detmold and
Endres, PRD **97**, 074507 (2018), conjecture the rethermalization cost
*vanishes* toward the continuum.

This is, structurally, the pipeline in this document with a *learned*
prolongator in place of their classical one: the matched-beta ladder ↔ their
r_0 matching; §8's retherm ↔ their step 4; §13's topology transport ↔ their
Q-preserving prolongation. It is the single most important omitted citation,
and the comparison it demands — *does a learned prolongator beat a classical
smearing-based one?* — has never been run here.

**23.3 Diffusion models for lattice field theory.**
Wang, Aarts and Zhou, JHEP **05** (2024) 060 **[V]**, established diffusion
models as stochastic quantization for LFT. Cotler and Rezchikov,
arXiv:2308.12355 **[V]**, *"explain how to use diffusion models to learn
inverse renormalization group flows of statistical and quantum field
theories"* — and already propose bridge/parallel-tempering samplers,
pre-empting the AIS framing of §21. Masuki and Ashida, arXiv:2501.09064
**[V]**, share the title concept for ML benchmarks rather than LFT.

**23.4 Normalizing flows, and what is actually known about their scaling.**
The canonical gauge-theory flow papers are Albergo, Kanwar and Shanahan, PRD
**100**, 034515 (2019), and Kanwar, Albergo, Boyda, Cranmer, Hackett,
Racanière, Rezende and Shanahan, **PRL 125, 121601 (2020)** **[V]**. Two facts
matter for how this project has been describing them.

First, the 2D U(1) flow result is at a **fixed L = 16, beta = 1–7**, and
reports **integrated autocorrelation times, not ESS**: tau_int(Q) ≈ 10 for the
flow against ≈ 4000 (heat bath) and ≈ 15000 (HMC). The "ESS/N ≈ 0.5–0.7"
figure quoted in the Fig. 19 caption of the appendix is *not* from this paper
and should not be attributed to it — its actual source is the Singha et al.
Lattice 2026 Q-shift result of §23.7, where it is additionally reported as
*flat in volume*.

Second, and more important, **flow ESS collapses with volume**. Del Debbio,
Marsh Rossney and Wilson, PRD **104**, 094507 (2021) **[V]**, work only at
6^2–20^2 and warn that *"as we move towards the continuum limit the training
costs scale extremely quickly."* Abbott et al., arXiv:2211.07541 **[V]**,
state plainly that flow demonstrations *"have been at the scale of toy models,
and it remains to be determined whether they can be applied to
state-of-the-art lattice QCD."* Nicoli et al., PRD **108** (2023) **[V]**,
document mode collapse as the failure mode. Singha et al., arXiv:2604.10209
**[V]**, measure a super-resolving-NF comparator falling to **~0.01% ESS at
L = 256**.

The correct summary is therefore *not* the flat "flows have exactness, we have
reach." For *general-purpose* flows the honest statement is that *both*
families degrade with volume — they retain asymptotic exactness via
reweighting/MH at toy volumes and lose efficiency beyond them, while this
pipeline gave up the reweighting route entirely. But that qualification does
**not** rescue the comparison, because the sharpest competitor (§23.7) reports
ESS/N 0.5–0.7 *flat in volume* by restricting the flow to a single sector and
recovering topology with an exact bijection. Against that specific design this
project is behind on exactness and not obviously ahead on anything except
beta-reach and the gauge-field setting. The uncomfortable reading — and the
correct one — is that this pipeline's O(100)-nat weight spread is not a
generic feature of the problem that everyone shares.

**23.5 Topological freezing and its established remedies.** The freezing
phenomenon: Del Debbio, Manca and Vicari, PLB **594**, 315 (2004). The result
that most directly threatens this project's validation strategy is Schaefer,
Sommer and Virotta, **NPB 845, 93 (2011)** **[V]**, which demonstrates that
**Wilson loops decouple from the slow topological modes** — i.e. a sampler can
reproduce Wilson-loop observables essentially perfectly while Q is badly
wrong. That is the published, physics-level statement of the dissociation this
project measured independently in §20 (sharp observables, ~1 nat/site density
error) and it should be cited exactly there.

Remedies with published numbers that any speed claim must be measured
against: open boundary conditions, Lüscher and Schaefer, JHEP **07** (2011)
036 **[V]**; metadynamics, Laio, Martinelli and Sanfilippo, JHEP **07** (2016)
089 **[V]**; parallel tempering in boundary conditions, Hasenbusch, PRD **96**,
054504 (2017) and Bonanno, Bonati and D'Elia, JHEP **03** (2021) 111 **[V]**
(*two orders of magnitude* in tau(Q^2)); out-of-equilibrium / stochastic
normalizing flows, Bonanno, Nada and Vadacchino, JHEP **04** (2024) 126 **[V]**.

**23.6 The "strongest classical baseline we could construct" is published.**
The instanton/winding-update HMC used as the head-to-head competitor is
Albandea, Hernández, Ramos and Romero-López, **EPJC 81, 873 (2021)** **[V]** —
winding HMC for **2D U(1)**, *"reversible jumps between topological sectors —
winding steps — combined with standard HMC steps,"* validated against the same
exact finite-beta analytics used here. It must be cited as prior art rather
than presented as constructed in-house. Their companion work notes the
difficulty of extending winding moves to 4D SU(2), which is directly useful
for the `su2_2d` line.

**23.7 The nearest competitor is a conference talk, not an arXiv paper.**
An automated arXiv sweep will *not* find it, and initially reported the
project's own note on it as a misattribution — wrongly. The work is Singha,
Kauffmann, Jansen, Finkenrath, Arora and Nakajima, "Generative sampling across
topological sectors in 2D U(1) lattice gauge theory," **Lattice 2026**
(U. Maryland), building on RiGCS (arXiv:2503.08918, Ising, ICLR) and
arXiv:2604.10209 (continuous phi^4). Two methods, both normalizing flows in
plaquette space with exact likelihood:

1. **Q-shift.** The flow is deliberately mode-collapsed to Q = 0 (reverse-KL
   plus a soft-Q^2 penalty), and an exact unit-Jacobian bijection
   T_q: phi_p -> phi_p - 2*pi*q/V shifts the charge by q, with mixture
   importance sampling over sectors. Unbiased by construction:
   chi_top within ±0.5% of exact through L = 32 (LCP beta/L^2 = 0.094,
   beta = 6–96), **ESS/N 0.5–0.7 flat in volume**, tau_int(Q^2) ≈ 1.
2. **Multilevel** (preliminary, L ≤ 16): a learned conditional 2x2 -> LxL
   doubling on the line of constant physics — *the same tree-level
   beta_c = beta_f/4 relation as this project's ladder* — in which doubling
   **exactly preserves plaquette flux** (three fine plaquettes generated, the
   fourth solved, Bianchi automatic), so topology is fixed at the cheap coarse
   level. tau_int(Q^2) = 1.36 at L = 16 against 3.63 for a multiscale flow.

Two consequences. First, this — not Kanwar et al. — is the actual source of
the "ESS/N ≈ 0.5–0.7" figure quoted in the Fig. 19 caption, and there it is
correctly sourced and *flat in volume*, which makes it a stronger comparator
than §23.4's volume-collapsing flow results suggest. Second, their backup
material gives the uniform Q-shift as an HMC topology move with
volume-independent dS ~ 2*pi^2*beta/V, which is **mathematically the same move**
as this project's smooth-instanton Metropolis hop
(`lgt/local_updates.py::instanton_field`, every plaquette = 2*pi/L^2).
Their multilevel result also means plain "RG-inspired hierarchical doubling"
is no longer a distinguishing frame. The published uniform-winding prior art
remains Albandea et al. (§23.6), whose boundary-window winding kick they report
freezing at large beta/L^2 where the uniform shift does not.

*Method note:* this entry is the clearest evidence that §23's arXiv-based
sweep has a systematic blind spot for conference proceedings, and that its
negative results ("nobody has done X") are weaker than its positive ones.
Treat §24.2's novelty claims accordingly.

### 24. Honest positioning: what is novel here and what is not

**24.1 The headline concept is substantially published.** The most direct
overlap is Zhu, Aarts, Wang, Zhou and Wang, arXiv:2502.05504, **JHEP 03 (2026)
111** **[V, abstract quoted verbatim]**: a diffusion model for **2D U(1) gauge
theory**, trained at small beta and *"extrapolated to larger inverse coupling
regions without encountering the topological freezing problem"*, where *"the
trained model can be employed to sample configurations on different lattice
sizes without requiring further training"*, and whose *"exactness... is ensured
by incorporating Metropolis-adjusted Langevin dynamics into the generation
process."* (Earlier workshop version: arXiv:2410.19602, NeurIPS 2024 ML4PS.)

Set against this document's four claimed advantages — extrapolation reach,
one-checkpoint generality, freezing avoidance, and MCMC-wrapped exactness —
all four are theirs, and they *achieved* the exactness §20 measured as out of
reach. The §20 design directive ("exactness must come from Markov-chain
machinery wrapped around the generative proposal") is, in substance, their
published method. Any submission must engage this paper directly.

**24.1a Measured against their own case (2026-08-15).** The workshop version
(arXiv:2410.19602) was read in full. Three things change the picture above, and
the third is the substantive one.

*What their method actually is.* Not inverse RG. A U-Net score model at **fixed
L = 16**, trained at β = 1 on 30,720 HMC configurations (×5 by gauge
augmentation), extrapolated in coupling by rescaling the learned score,
s → (β/β₀)s, which they call physics conditioning. No coarse conditioning, no
ladder, no scale doubling. The overlap with this project is the *goal*, not the
mechanism — so "the ladder, in flow form" applies to Bauer et al., not to them.

*The MALA claim is not in that version.* The workshop paper contains no
accept/reject step and makes no exactness claim; its stated contribution is
that freezing is "alleviated". The MALA sentence quoted above is from the JHEP
version only. The assertion that they "achieved the exactness §20 measured as
out of reach" is therefore unverified against anything read here, and should
not be repeated until the JHEP text is checked.

*Their headline result does not survive the comparison they flagged as
pending.* Their §3.2 says: "We are currently comparing the numerically computed
distribution with the analytical prediction, which is possible in this simple
theory." This project has that prediction. Their figures are vector graphics,
so the histogram counts are recoverable exactly — every recovered bar is an
integer count out of their stated 1,024, to within 0.001 of a configuration
(`47_zhu_figure_extract.py`). At L = 16, β = 7:

| Q | −4 | −3 | −2 | −1 | 0 | +1 | +2 | +3 | +4 |
|---|---|---|---|---|---|---|---|---|---|
| exact | 0.1 | 4.7 | 55.8 | 247.8 | **407.3** | 247.8 | 55.8 | 4.7 | 0.1 |
| their DM | 13 | 29 | 113 | 218 | **247** | 231 | 118 | 40 | 14 |
| their HMC | — | — | — | 23 | **965** | 35 | — | — | — |

| arm | ⟨Q²⟩ | ratio to exact (1.0064) | χ² p |
|---|---|---|---|
| their HMC | 0.0567 | 0.06× | 1×10⁻²⁷¹ |
| their diffusion model | 2.3715 | **2.36×** | 9×10⁻¹²⁸ |
| this project's pipeline | 1.0859 | **1.08×** | **0.41** |

Their reading of the HMC arm is right — it is frozen. But the diffusion arm
**overshoots**: 39% too few configurations at Q = 0, ≈2× too many at |Q| = 2,
≈7× at |Q| = 3, and ≈100× at |Q| = 4 (13 and 14 configurations where the theory
predicts 0.1). "Explores a wider range of topological sectors, yielding a
larger topological susceptibility" is literally true and is the wrong amount of
wider; the true χ_Q lies between their two curves and neither reaches it.

Three caveats, all load-bearing. This is the **workshop** version and they
flagged the comparison as in progress, so the JHEP version may have closed it —
this is not a claim about their current work. Our arm runs our checkpoint one
rung *below* its trained range (8 → 16, against 16 → 32 in training). And these
are digitized figure counts, not released data.

*Why this matters beyond their paper.* It is the same failure mode as our own
**raw** model output: over-production of topological charge at large β — 2.5×
at A_bc4, 4.6× at A_bc8, 5.4× at E_bc11.8 (§21.6), and 2.36× here. A
β-extrapolated diffusion sampler appears to manufacture topology in the frozen
regime, the effect is invisible without an exact reference, and in this project
it is removed not by the network but by the transport identity of §8. That is a
sharper and more defensible framing of the contribution than any of the four
advantages listed above: the field's diffusion samplers are being validated on
observables and Q-histogram *width*, and width is not correctness.

Provenance: `u1_2d/scripts/47_zhu_figure_extract.py`,
`46_zhu_comparison.py`, `out/u1_2d/zhu_comparison/`.

Similarly, the coarse→fine learned stochastic map is Bauer, Kapust, Pawlowski
and Temmen, arXiv:2412.12842 **[V]**: *"a renormalisation group inspired
normalising flow... we use samples from a coarse lattice field theory and learn
a stochastic map to the targeted fine theory... efficient sampling on lattices
as large as 128x128... when only having sampling access on a 4x4 lattice."*
That is the ladder, in flow form.

**24.2 What appears to remain novel**, in decreasing confidence:

1. **Inverse-RG scale doubling applied to *gauge* fields.** Every inverse-RG
   and super-resolution paper found is scalar or spin (phi^4, Ising, Potts,
   Edwards–Anderson); every gauge diffusion paper found is fixed-volume or
   same-volume transfer. Nobody appears to join the two. **[I, from exhaustive
   negative search]**
2. **An explicit matched-beta ladder with a derived coupling relation** —
   beta_c = beta_f/4 at tree level, refined by the exact character-convolution
   MLE of §7 — together with the ⟨Q²⟩ ladder-invariance identity of §8, which
   turns sector transport from a plausible heuristic into an exact statement.
3. **The falsification program itself.** Measuring the density gap (~1
   nat/site) and closing off six remedies with converged negatives. Every
   inverse-RG paper above validates on critical exponents or observables and
   never asks whether the generated ensemble *is* the Boltzmann distribution.
   Bachtis, arXiv:2310.12631 **[V]**, explicitly lists *"how to incorporate
   numerical exactness within inverse renormalization group methods"* as open
   future work. **This is the strongest and most defensible contribution in
   the project — and it is a negative result.**
4. Structural coarse-charge transport as an explicit gauge-covariant instanton
   shift with the derived guidance width lambda(sigma) = 8 sigma^2.

**24.3 The implication for how to write this up.** A paper framed as *"we built
a diffusion-based inverse-RG sampler"* is exposed on priority to Zhu et al. and
Bachtis et al. A paper framed as *"inverse-RG generative samplers have never
been tested for distributional correctness; here is what happens when you do,
and here is the mechanism"* is novel, useful, and squarely within what this
project actually established. §24.1a strengthens this considerably: the
published diffusion result for this exact theory reports a *wider* Q
distribution as the success criterion, and against the exact P(Q) that width
is a 2.36× overshoot. The framing "width is not correctness, and here is the
reference that decides it" is now supported by an independent paper's own
numbers, not only by our internal negatives. The falsification chain, the guarded-checkpoint
protocol, the Villain control, and the observable-vs-density dissociation of
§20 are the assets — and §23.5 supplies the published physics result that
explains *why* that dissociation had to happen.

### 25. Objections a referee will raise, and the experiments they imply

1. **Topology transport is the weak point, and it degrades with volume.** The
   raw charge-match rate is 0.21 — the model's fine sector matches its coarse
   conditioner about a fifth of the time — transport-mode worst |z(⟨Q²⟩)| is
   10.9, and the raw Q² excess grows from 1.7–2.7 at L ≤ 32 to 7.1–28.2 at
   L = 64/128. It is rescued by exact-sector mode, which draws Q from the
   **exact analytic P(Q)** — unavailable in any theory where one would actually
   need this method. §8's "topology rides the ladder for free" is in tension
   with Table S3, and §23.5 explains how Wilson observables can look excellent
   while this is true.

   **Answered, 2026-08-14 (§21.6).** The premise is half right and the
   conclusion is wrong. Right: the *model's own* topology is bad and degrades
   with volume — raw sector match falls to 6.2% at L = 128 and raw ⟨Q²⟩ runs
   2.5–5.4× above exact at strong coupling. Wrong: that this is rescued by the
   analytic P(Q). Regenerated on the current ensembles, transport fails χ² in
   3 of 35 cases against exact-sector's 2 of 35 — both at the false-positive
   rate — and all three transport failures are the deliberately-mismatched
   track-B controls. At L = 128 transport gives p = 0.87, not the 0.005 this
   objection was built on. The correctness comes from the ladder identity
   (coarse P(Q) *is* fine P(Q)), which needs no closed-form P(Q), and where a
   fix *is* needed a ≤ 150-trajectory instanton tail supplies it with no growth
   in volume. The surviving caveat is that at β ≳ 55 the χ² has ≤ 3 populated
   bins, so those passes are weak evidence.
2. **The baseline already solves the advertised problem.** Table S1 records
   that instanton-HMC ⟨Q²⟩ is correct in *every* row and that the failures are
   UV thermalization. So the headline regime is thermalization-limited, not
   topology-limited — and the incumbent remedy for that is Endres et al.
   multiscale thermalization (§23.2), uncited and uncompared.
3. **Cost accounting.** Now partly addressed (Fig. 18 charges the 8820 s
   campaign entry cost), but a break-even configuration count against each
   classical remedy is still owed.
4. **ESS reported at its floor.** ESS/N = 0.016 in every row of Table S2 is
   exactly 1/64 at N = 64: an *unresolved* estimate, not a measurement. Re-run
   with N >> 64 so the number is resolved.
5. **The size of the gap is understated in prose.** Table S5 spreads are
   15–164 nats and Fig. 23 states growth ∝ beta*V; against the O(1–3)
   usability bar the shortfall at L = 32, beta = 218.6 is ~100 nats, i.e.
   e^100 — not "roughly an order of magnitude."
6. **Mean |z| and multiplicity.** For a correct sampler with correct errors
   mean |z| should be ≈ 0.8; the vs-reference value is 1.77 (vs-exact 1.06).
   Combined with the loop-size dispersion growth documented in §20, "matches
   exact results" needs the scoping it now carries.
   *(Updated 2026-08-14: on the GPU-regenerated pipeline validation this is
   now mean |z_exact| = 0.588 over 84 observables with 0 past |z| = 3 —
   slightly BELOW the ideal 0.798, i.e. the error bars are mildly
   conservative rather than too tight. The vs-exact half of this objection is
   answered; the dispersion-growth half stands. Figure 28 plots it.)*

**Status of these objections as of 2026-08-14.** Three have moved:

- *1 (topology degrades with volume)* is now **measured, and worse than the
  prose suggested**: the no-projection match rate is 0.484 / 0.234 / 0.094 at
  L = 16 / 32 / 64, halving per 4× volume (§13). The objection stands and is
  now quantitative. The exact-P(Q) dependence it points at remains the single
  largest obstacle to transferring this method to a theory where P(Q) is not
  known in closed form, and nothing here addresses that.
- *4 (ESS at its floor)* is **answered, and the answer is worse than the
  objection assumed.** Every quoted ESS/N was exactly 1/64. Re-running at
  n = 512 gives exactly 1/512 — so the effective sample size is **one
  configuration, independent of N**. The estimator was not merely unresolved,
  it was optimistic: ESS/N tracking 1/N is complete weight degeneracy, and no
  achievable N rescues raw transport as an importance sampler. The honest
  phrasing is "one effective configuration however many you draw", not
  "ESS/N = 0.016". See the appendix Table S2 note.
- *6* is half-answered, as above.

- *the tiling/replication warm-start baseline* (implied experiment 3) is
  **done, and it comes out in the pipeline's favour** — see Table S6b. Three
  non-learned prolongators, including the exact inverse of the blocking rule
  and a flux-spreading variant that equalizes all four fine plaquettes per
  cell, need 67–502 trajectories where the seed needs 0–8, and every one of
  them is *worse than a fresh cold start*. Prolonging a coarse configuration
  by any obvious deterministic rule produces a state that satisfies the
  coarse constraint while being wrong at short distances, which the chain
  must then undo. The speedup is specific to the learned map, not to having
  been handed the coarse configuration.

- *the Endres-style prolongator comparison* (implied experiment 2) is **done**
  and is in the same table. APE smearing applied to the flux prolongator, with
  the smearing count tuned per β to match the exact plaquette rather than
  fixed, is the only non-learned arm that beats a fresh cold start, and it
  thermalizes at β_f = 218.58 (164 trajectories) where both fresh starts and
  every geometric prolongator fail inside the budget. It is a real method and
  the naive prolongators are a strawman for it. The learned seed still wins
  by 4.5× at β_f = 4.44, 40× at 6.11 and 27× at 218.58 — a large, consistent
  margin over a working competitor, not a walkover. The claim that the
  diffusion seed is the *only* usable start in the frozen regime is false and
  should not be made.

The Zhu et al. comparison and the tau_int-aware classical-remedy benchmark were
both run on 2026-08-15 and are in **§25.6**. Transport-only topology at
L = 64/128 without the analytic P(Q) crutch was run on 2026-08-14 and is
answered under objection 1 above and in §21.6.

**Experiments implied — status.** The direct Zhu et al. comparison is **done**
(§25.6b: their diffusion arm sits at 2.36x the exact ⟨Q²⟩, their HMC arm at
0.06x, ours at 1.08x with chi² p = 0.41). The tau_int-aware benchmark against
PTBC and open boundaries is **done and retired by measurement** (§25.6a): a
properly tuned PTBC ladder mixes well (swap acceptance 0.68–0.98, tau_int ≈ 3)
and is still 25–121x more expensive than the exact winding update, which this
theory already possesses and which is the global move PTBC exists to
manufacture — so PTBC is the wrong baseline here. The comparison that replaces it is against `hmc+inst`, now
measured at 0.198 s per independent configuration at beta = 218.58, and a
break-even configuration count against *that* is the one cost item still owed.
(The prolongator comparison against Endres-style APE smearing and the naive
tiling warm-start baseline are done — Table S6b; transport-only topology is
done — §21.6; the MALA-exactness claim is tested in §25.6c.)

### 25.5 Post-closure corrections (2026-08-14/15)

Work after the 2026-08-02 closure corrected five published items. None required
retraining and the deployed checkpoints are untouched; the corrections are
recorded here because several change what the study may claim.

**Corrected claims.** (i) The AIS divergence cause was misattributed to the
bridge integrator; it is the surrogate's regularization, established by
intervention — §21 above. (ii) The exact-P(Q) dependence was overstated —
§21.5/§21.6 and `PHYSICS_WALKTHROUGH.md` F1. (iii) Four appendix tables carried
numbers from superseded runs.

**Stale tables, found by a full appendix audit and corrected against source:**

| table | what was stale |
|---|---|
| S1 | four deep-burn-in rows from an older scan; β = 218.58 at 8000 traj is max \|z\| **3.2, not 7.2** — near the pass threshold, not hopeless |
| S3 | whole transport/exact-sector comparison; now regenerated by script |
| S4 | disagreed with its source in nearly every cell; quoted β_f = 43.6 for a case at 45.62; mixed two runs in one row |
| S6b | the 640-trajectory budget reported three convergent cases as "never" |
| Fig. 20 caption | listed five transport χ² failures; three remain |

Verified correct and unchanged: Table S2 (all four n = 512 rows match
`model_ess_n512/` exactly), S5, S6, S7, the S7b table body, and all 28 figures
(`30_assemble_appendix_figures.py --check`: 0 stale, 0 missing, 0 untracked).

**New measurements not covered above.** Hyperparameters: five of six knobs sit
inside the baseline seed-noise floor (43.8–59.1); `topo_weight` clears it and
replicates — all five raised-weight seeds below all three baseline seeds, exact
one-sided rank test p = 0.018, dose-response saturating (0.1 → 0.3 buys 1.27×,
0.3 → 0.5 a further 1.07×). Not adopted here, since a 1.27× gain in a quantity
still 14–39× from usable does not justify invalidating every recorded number;
recorded as the successor's starting point (`TODO.md` §2). Prolongator baseline
re-run at 2000 trajectories (Table S6b). Independence-Metropolis on this
proposal is not viable — acceptance ≤ 0.00195, but that is exactly 1/n, the
estimator's floor, so it is an upper bound and not a measurement.

**Five methodological lessons, all earned the hard way here:**

1. *Compute the resolution floor before reading the number.* ESS/N, MH
   acceptance and the sector-tail length all return 1/n, 1/n and
   `min_traj + check_every` when the underlying quantity is degenerate or zero.
   Three measurements in one session first read as findings and were floors.
2. *Perfect separation is not causation.* Minimum HMC acceptance separated the
   AIS modes with no overlap and was still the symptom. Only an intervention
   holding everything else byte-identical settled it.
3. *Cross-validation only sees the manifold it was given.* If the failure lives
   off the training manifold, out-of-fold scoring cannot detect it at any
   number of folds.
4. *Regenerating ensembles silently invalidates transcribed tables.* Five
   appendix items drifted this way. Tables should be emitted by a script
   reading the data of record — as S3 and S4 now are.
5. *Budget conventions become claims.* "never" in Table S6b meant "not within
   640 trajectories" and was read as failure. Put the budget in the cell.

New scripts: `38_sector_tail_scaling.py`, `39_mh_acceptance.py`,
`40_fold_noise_audit.py`, `41_ridge_scan_report.py`, `42_sector_mode_table.py`.
New outputs: `out/u1_2d/ridge_scan/`, `sector_mode_table/`,
`tiling_baseline_2000/`, `ais_transport_foldfixed/`, `mh_acceptance.json`.

### 25.6 The three owed experiments, measured (2026-08-15)

The two experiments §25 listed as still owed — a direct Zhu et al. comparison,
and tau_int-aware benchmarking against PTBC and open boundary conditions — were
run, together with a third that tests the competing "MALA makes it exact" claim
on its own terms. All three are negative or reframing results, and one of them
says the benchmark itself was aimed at the wrong target.

#### (a) PTBC is the wrong classical baseline for 2D U(1)

Four arms at L = 32, 3000 trajectories, scored on the cost of one *independent*
configuration, `2 * tau_int(Q^2) * (s/traj) * replicas_charged` — PTBC pays for
every replica and measures only the c = 1 one, so it is charged for all 12.

| beta | arm | tau_int(Q²) | ⟨Q²⟩ | exact ⟨Q²⟩ | s / independent cfg |
|---|---|---|---|---|---|
| 14.1464 | hmc | frozen (0 changes) | 0.0000 | 1.9040 | ∞ |
| 14.1464 | hmc+inst | 2.85(44) | 1.8705 | 1.9040 | **0.124** |
| 14.1464 | ptbc (tuned, 13 rep) | 2.30 | 1.8742 | 1.9040 | 3.14 |
| 14.1464 | open | 1.04(10) | 4.4183 | — | 0.040 |
| 55.0237 | hmc | frozen | 0.0000 | 0.4743 | ∞ |
| 55.0237 | hmc+inst | 1.20(13) | 0.4791 | 0.4743 | **0.090** |
| 55.0237 | ptbc (tuned, 18 rep) | 2.99 | 0.5247 | 0.4743 | 10.87 |
| 55.0237 | open | 0.55(4) | 3.0497 | — | 0.038 |
| 218.58 | hmc | frozen | 0.0000 | 0.0290 | ∞ |
| 218.58 | hmc+inst | 1.39(15) | 0.0296 | 0.0290 | **0.198** |
| 218.58 | ptbc (tuned, 20 rep) | 3.13 | 0.0375 | 0.0290 | 21.34 |
| 218.58 | open | 0.52(4) | 2.7701 | — | 0.076 |

Three things follow, and the first is the one that matters.

**The winding update is exact and nearly free here.** It reproduces the analytic
⟨Q²⟩ to −1.8% / +1.0% / +2.0%, holds tau_int near 1 at every coupling including
the deeply frozen one, and costs 1–18% over plain HMC — which is itself
completely frozen, 0 sector changes in 3000 trajectories at all three couplings.
This is the baseline the pipeline has to beat, and it is a hard one.

**Tuned PTBC works, and is still 25–121x more expensive.** The tuned ladder is
a genuinely functional sampler: swap acceptance 0.68–0.98 on every pair,
tau_int(Q²) of 2.3–3.1, and ⟨Q²⟩ consistent with the exact value to about 2
sigma at all three couplings. It is not a strawman. It is simply redundant —
PTBC exists because in 4D SU(3) there is no global topological move with usable
acceptance, so it manufactures one out of a replica ladder, and 2D U(1) already
*has* that move exactly (Albandea et al.). Buying a substitute for something you
already own costs 1.5–2 orders of magnitude here. The literature's "two orders
of magnitude" for PTBC is measured against a frozen chain, not against a
winding update.

**Open boundaries are cheap but change the observable.** They give the shortest
tau_int in the table, but Q stops being an integer and ⟨Q²⟩ = 2.77–4.42 against
a periodic exact value of 0.029–1.904. Fast, and measuring a different quantity.
That is the Lüscher–Schaefer trade stated plainly, not a defect of the method.

**What the tuning was worth, and a correction to an earlier claim in this
section.** The first run used a full-line defect (l_d = L), which PRD 96 054504
§IV C names explicitly as the worst choice, with a ladder calibrated only in c.
Fixing both — l_d = 2, and the ladder bottom stepped in beta*c rather than c,
since the defect only switches off once beta*c drops below O(1) — together with
folding the replica index into the HMC batch dimension and moving the arm to
the GPU, improved the PTBC cost by **45–51x**:

| beta | as first run | tuned + batched | tau_int | swap acceptance |
|---|---|---|---|---|
| 14.1464 | 159.2 | 3.14 | 22.8 → 2.30 | 0.25–0.61 → 0.71–0.94 |
| 55.0237 | 484.1 | 10.87 | 44.0 → 2.99 | 0.00–0.69 → 0.70–0.98 |
| 218.58 | 773.6 | 21.34 | 39.4 → 3.13 | 0.00–0.81 → 0.68–0.95 |

This section previously argued the tuned run *need not be performed* because
arithmetic bounded it near 135 s at beta = 218.58. That bound was wrong by a
factor of 6 — the true figure is 21.34 s — because it priced the extra replicas
as a linear cost increase when the arm is latency-bound, so on GPU the ladder
went from 12 to 20 replicas at **no** per-trajectory cost (0.177 → 0.170 s).
The sign of the conclusion survived; the magnitude did not, and the magnitude
was quoted. The numbers above are measured, not bounded.

**One caveat still understates PTBC:** Hasenbusch's hierarchical local-update
scheme (sub-rectangle sweeps between swaps) is not implemented, so this remains
unoptimized PTBC.

**A reporting bug found while tuning.** Swap acceptance was averaged over all
trajectories including those where a pair was not proposed — pairs alternate
parity, so **every acceptance in the first run was halved**. `swap_replicas`
now returns NaN for unproposed pairs and callers aggregate with a NaN-skipping
mean, so the column is acceptance per *proposal*, which is what Hasenbusch's
>30% criterion refers to. This affected no cost number (tau_int and s/traj come
from the chain itself), only the diagnostic column, but it is why the first run
looked even more broken than it was.

**Device convention.** Each arm is timed on the hardware that suits it, since
handicapping one would corrupt the comparison. The single-replica arms
(`hmc`, `hmc+inst`, `open`) are latency-bound on one small batch and run faster
on CPU; the stacked PTBC ladder saturates the GPU better and is timed there.
This favours PTBC, which is the direction that makes the conclusion robust.

The honest summary is that §25's "benchmark against PTBC and open boundaries"
was the wrong experiment to have asked for. The right one — benchmark against
the exact winding update — was in the same script and takes 20 seconds. It is
now the `hmc+inst` row, and it is the number the pipeline's cost claims should
be compared against.

Code: `u1_2d/lgt/ptbc.py` (+ 20 tests in `u1_2d/tests/test_ptbc.py`),
`u1_2d/scripts/43_ptbc_benchmark.py`; data
`out/u1_2d/ptbc_benchmark/` (first run, untuned) and
`out/u1_2d/ptbc_benchmark_tuned/` (of record).

#### (b) Zhu et al.: the same failure mode, now scored against the exact answer

arXiv:2410.19602 reports its 2D U(1) topology only as histograms, with no table
and no released data, and flags the one comparison that would settle whether
they are right: *"We are currently comparing the numerically computed
distribution with the analytical prediction, which is possible in this simple
theory."* That prediction is `u1_2d.lgt.exact`.

Their numbers are recoverable. The figures are vector graphics — the PDF
contains no image XObjects — so every bar is a path with explicit corner
coordinates. Calibrating against the axis ticks returns heights that are
integer multiples of 1/1024, their stated ensemble size, to within 0.001 of a
configuration, summing to 1023 of 1024. This is digitization of a published
figure, not their data, and is labelled as such wherever it is used.

At their case, L = 16, beta = 7 (exact ⟨Q²⟩ = 1.0064):

| arm | ⟨Q²⟩ | /exact | chi² p | source |
|---|---|---|---|---|
| exact | 1.0064 | 1.00 | — | analytic |
| HMC (Zhu et al.) | 0.0567 | 0.06 | 1.1e−271 | digitized |
| diffusion (Zhu et al.) | 2.3715 | **2.36** | 9.3e−128 | digitized |
| hmc, no topological moves (ours) | 0.6729 | 0.67 | 7.3e−27 | measured |
| inverse-rg, 8→16 (ours) | 1.0859 | 1.08 | **0.41** | measured |

Their paper presents the wider Q distribution as the desirable outcome, against
a frozen HMC arm. Both halves are wrong in the same direction and by different
amounts: their HMC undershoots by 18x and their model overshoots by 2.4x, and
both reject the exact distribution at overwhelming significance. A wider
distribution than a frozen chain is not evidence of correctness when the
correct answer is available and sits between them.

This is the same over-production failure our own raw model shows (§21.6: raw
⟨Q²⟩ runs 2.5–5.4x above exact at strong coupling), which is worth stating
plainly — it is a property of score-based samplers on this theory, not a
mistake specific to their pipeline. The difference is that sector transport
corrects it here and their rescaled-score extrapolation has no analogous step.

**Caveat on our arm:** the checkpoint is trained for 16→32 and used at 8→16,
one rung below its trained range. The architecture is convolutional so it runs,
but that row is an out-of-range use and is labelled so. The comparison that
carries the weight — is a wider Q distribution automatically better? — rests on
the `exact` and digitized rows, which carry no such caveat.

Code: `u1_2d/scripts/46_zhu_comparison.py`, `47_zhu_figure_extract.py`; data
`out/u1_2d/zhu_comparison/`.

#### (c) MALA acceptance is a local diagnostic and does not test exactness

Zhu et al. state that "exactness ... is ensured by incorporating
Metropolis-adjusted Langevin dynamics into the generation process." §20 measured
that route as out of reach and F3 states the deployed ladder applies no
accept/reject to the proposal at all. Those cannot both be right, and the
mechanism is testable without their code: run MALA on the exact Boltzmann target
starting from model output, and compare its acceptance against the same
measurement started from equilibrium HMC configurations at the same coupling.

| beta | eps | acc (model) | acc (equilibrium) | ratio | Δ⟨Q²⟩ |
|---|---|---|---|---|---|
| 14.1464 | 0.003 | 0.9997 | 0.9991 | 1.001 | 0 |
| 14.1464 | 0.01 | 0.9978 | 0.9988 | 0.999 | 0 |
| 14.1464 | 0.03 | 0.9428 | 0.9534 | 0.989 | 0 |
| 14.1464 | 0.1 | 0.0169 | 0.0294 | 0.574 | 0 |
| 55.0237 | 0.003 | 0.9997 | 0.9994 | 1.000 | 0 |
| 55.0237 | 0.01 | 0.9838 | 0.9881 | 0.996 | 0 |
| 55.0237 | 0.03 | 0.6038 | 0.6388 | 0.945 | 0 |
| 55.0237 | 0.1 | 0.000 | 0.000 | n/a | 0 |

The naive reading — ratio ≈ 1, so the model is already at the target and
MALA-wrapped exactness is nearly free — is wrong, and the last column is why.
**⟨Q²⟩ is bit-identical before and after in every one of the eight settings**:
across 50 steps x 64 configurations x 8 settings, MALA changed the topological
sector exactly zero times. It cannot; the required move is not in its proposal
at any step size that accepts.

So high acceptance says each configuration sits in a region of typical action —
a *local* statement — while saying nothing about whether the ensemble is
distributed correctly. This is the same dissociation as D1/D2 and §20: healthy
local diagnostics while the density is 10–100 nats off. The cost of
exactness-by-MALA is its mixing time on exactly the modes it cannot move, which
acceptance does not bound and this script does not measure. **F3 stands**, and
the "exactness is ensured by MALA" claim is unsupported by an acceptance rate
however high.

(The eps → 0 rows are uninformative by construction: a vanishing step accepts
everything for any configuration, right or wrong. The informative entries are
the largest eps, where the arms separate — and even there the separation is 5%.)

Code: `u1_2d/scripts/45_mala_exactness.py`; data
`out/u1_2d/mala_exactness/mala_exactness.json`.

#### What this changes in the objection list

Both experiments §25 listed as owed are now done, and the residual owed item is
different from the one recorded there: a break-even configuration count for the
pipeline against **`hmc+inst`** (0.198 s per independent configuration at
beta = 218.58), which is a far more demanding comparison than PTBC. The
"tau_int-aware benchmarking against PTBC and open boundaries" line should be
read as retired-by-measurement rather than answered in the pipeline's favour.

Two lessons, in the same register as §25.5.

*A classical baseline imported from another theory can be the wrong baseline.*
PTBC's reputation is earned in 4D SU(3), where the alternative is nothing.
Transplanting the comparison without asking what it substitutes for produced a
number whose sign was deducible in advance from the structure of the theory.

*A bound is not a measurement, and must not be quoted as one.* The argument for
skipping the tuned run was sound in structure — the conclusion could not flip —
but it was used to justify a stated magnitude, and that magnitude was wrong by
6x because the bound assumed a linear cost in replicas for a latency-bound
kernel. The measurement then moved the headline margin from "10³–10⁴x" to
"25–121x". When the cost of measuring is 30 minutes, the bound should be used
to decide *priority*, never to fill in the number.

New scripts: `43_ptbc_benchmark.py`, `44_frozen_regime_power.py`,
`45_mala_exactness.py`, `46_zhu_comparison.py`, `47_zhu_figure_extract.py`.
New module: `u1_2d/lgt/ptbc.py`. New outputs: `out/u1_2d/ptbc_benchmark/`,
`mala_exactness/`, `zhu_comparison/`.

### 25.7 Closing the review backlog (2026-08-15)

`docs/U1_2D_REVIEW.md` §Remaining carried four code items, a citation audit, and
one deferred measurement. All are now closed. Two of them changed published
numbers, and one retracts a recommendation, so they are recorded here rather
than only in the review.

**M3 — the χ² gate was hiding the test where it mattered most.** The P(Q)
chi-squared row was emitted only when at least two bins had expected > 2 *and*
observed counts landed in them; otherwise nothing was written, and the table
rendered "-", indistinguishable from "not applicable". `validate/report.py` now
pools low-expectation bins and out-of-support charge into overflow cells and
always emits a verdict (`u1_2d/tests/test_pq_chi2_gate.py` pins it).

The review justified this on `su2_2d` reuse. The real cost was here: the gate
had been silently dropping the sector test at the **three highest couplings in
the 38-case study** — β = 218.58, 398.5, 872.8 — which Table S3 reported as
having "no populated bins to test". They are testable with pooling and all
three pass (transport p = 0.388 / 0.971 / 1.000). That is the extrapolation
regime the whole method exists for, and it had no P(Q) test at all.

A second effect runs the other way and is equally welcome: charge falling
*outside* the tabulated support was being discarded by the histogram rather
than counted against the model. Counting it moves the deliberately-mismatched
track-B controls from marginal to decisive — B_bt55.0237 from p = 4.3×10⁻⁵ to
3.2×10⁻⁵⁴. The controls that are *supposed* to fail now fail unambiguously.

**M4 — the 38-case study was not τ_int-aware.** It called `validate_ensemble`
without `n_chains`/`ref_n_chains`, so every error bar was a fixed 20-bin
estimate rather than the per-chain τ_int estimate the honesty conventions
describe, and the case tables inherited z-scores built on the wrong errors.
Fixed at the call site. Because the study caches its ensembles, re-validation
needed no regeneration at all: `48_revalidate_tau_aware.py` reloads the cached
generated/reference pairs and re-scores them into a parallel directory, leaving
the original record intact for diffing.

| arm | cases | mean \|z_exact\| | \|z\| > 3 flags |
|---|---|---|---|
| transport | 44 | 0.957 → **0.888** | 38 → **33** |
| exact-sector | 38 | 0.847 → **0.778** | 1 → 1 |

For a correct sampler with correct errors the expectation is ≈ 0.798, so both
arms move *toward* it — the old error bars were mildly too tight, and objection
6 of §25 is answered a second way. Table S3 is regenerated on these records
(appendix); its conclusion — transport and exact-sector are indistinguishable,
every transport failure is a deliberate mismatch — is unchanged.

**`norm_type` and the validation σ-bias — two latent traps, no recorded
numbers moved.** `norm_type` defaulted to `"group"`, which normalizes over the
whole spatial extent and so makes the learned map lattice-size dependent; the
project's no-L-dependence claim survived only because every shipped config
overrode it. Default flipped to `"channel"`. Checkpoints record `norm_type` in
`model_kwargs`, so nothing rebuilds. Separately, validation drew t ~ U[0,1]
while training raised t to k(β) under `high_beta_sigma_bias`, so best-epoch
selection was scoring a noise distribution the model was not being trained on —
underweighting exactly the small-σ/high-β regime the bias exists to fix.
`sample_sigma` gained a `t` override so validation reuses the training warp
with its own seeded stream. Affects future training only.

**Citations — checked, and the study was conflating two papers.** §26.1 is the
new bibliography: 14 entries verified against arXiv/INSPIRE/publisher records,
15 listed explicitly as unverified rather than presented as confirmed. The
substantive finding is that "Zhu et al." is **two** papers — arXiv:2502.05504 =
JHEP 03 (2026) 111, the journal paper whose MALA claim §25.6c tests, and
arXiv:2410.19602, a shorter NeurIPS 2024 workshop paper, which is the one whose
figures §25.6b digitizes. Scripts 46/47 named the right one; §26 named only the
other, so the digitization provenance pointed at the wrong document. Also, the
Rançon citation had lost an author (there are two authors named Rançon). One
apparent error is a genuine coincidence: Zhu JHEP 03 (2026) 111 and Bonanno,
Bonati & D'Elia JHEP 03 (2021) 111 really do share an issue and article number
in different years, and neither should be "corrected".

**`topo_weight` — the follow-up measurement, and it is a null that retracts a
recommendation.** `TODO.md` §2 found `topo_weight` the one hyperparameter of
six that separated from seed noise on the deployed fiber log-weight spread
(pooled one-sided rank p = 0.018), and recorded it as the recommended starting
point for a successor. It also named the test that would settle whether the
effect is real: does `topo_weight` raise the **raw sector match rate**, the
mechanism it would have to act through?

Measured (`49_topo_weight_match_rate.py`, 8 already-trained checkpoints, 128
configurations per arm, at L = 32 and β = 14.15 / 55.02). The comparison is
*paired* — one coarse ensemble per case, shared by every arm — because the
coarse HMC draw is a larger variance source than the effect:

| group | arms | mean raw match rate |
|---|---|---|
| baseline seeds | base_s0/s1/s2 | 0.2227 – **0.2539** |
| raised topo_weight | topo03 ×3, topo05 ×2 | 0.2031 – 0.2383 |

**No separation.** All five raised-weight arms sit inside the three-seed
baseline spread, and the best of them (0.2383) is below the best baseline
(0.2539). `topo_weight` does not act through the raw sector match rate. Whatever
produced the log-weight-spread separation in `TODO.md` §2, it is not the
topological mechanism the penalty was designed around, and **the recommendation
to carry `topo_weight = 0.3` forward as a topology setting is withdrawn** on
this evidence. The spread result itself stands as recorded; only its
interpretation was load-bearing, and it does not survive.

This is the §25.5 lesson recurring: a separation that replicates can still be
acting through something other than its stated mechanism, and the cheap test is
to measure the mechanism directly rather than collect more of the same
endpoint.

New scripts: `48_revalidate_tau_aware.py`, `49_topo_weight_match_rate.py`.
New tests: `u1_2d/tests/test_pq_chi2_gate.py`. New outputs:
`out/u1_2d/generalization_tau_aware/`,
`generalization_exact_sectors_tau_aware/`, `sector_mode_table_tau_aware/`,
`topo_weight_match_rate/`.

### 26. Minimum citation set

*Inverse RG / super-resolution* — Ron, Swendsen, Brandt PRL **89**, 275701
(2002); Efthymiou, Beach, Melko PRB **99**, 075113 (2019); Bachtis, Aarts, Di
Renzo, Lucini PRL **128**, 081603 (2022); Bachtis PRB **110**, L140202 (2024);
Bachtis arXiv:2405.16288; Rançon, Rançon, Ivek, Balog PRE **113**, 055302
(2026).

*Diffusion for LFT* — Wang, Aarts, Zhou JHEP **05** (2024) 060 /
arXiv:2309.17082; **Zhu, Aarts, Wang, Zhou, Wang, "Physics-Conditioned
Diffusion Models for Lattice Gauge Theory", JHEP 03 (2026) 111 /
arXiv:2502.05504 (mandatory: direct competitor)**; **Zhu, Aarts, Wang, Zhou,
Wang, "Diffusion models for lattice gauge field simulations", arXiv:2410.19602,
NeurIPS 2024 ML4PS workshop** — a *separate, shorter* paper by the same authors
and the one whose figures §25.6b digitizes; the two must not be conflated;
Cotler, Rezchikov arXiv:2308.12355; Masuki, Ashida arXiv:2501.09064.

*Flows* — Albergo, Kanwar, Shanahan PRD **100**, 034515 (2019); Kanwar et al.
PRL **125**, 121601 (2020); Del Debbio, Marsh Rossney, Wilson PRD **104**,
094507 (2021); Abbott et al. arXiv:2211.07541; Nicoli et al. PRD **108**
(2023); Bauer, Kapust, Pawlowski, Temmen arXiv:2412.12842; Singha,
Chakrabarti, Arora PRD **108**, 074518 (2023); Singha et al. arXiv:2604.10209.

*Topological freezing and remedies* — Del Debbio, Manca, Vicari PLB **594**,
315 (2004); **Schaefer, Sommer, Virotta NPB 845, 93 (2011)**; Lüscher,
Schaefer JHEP **07** (2011) 036; Laio, Martinelli, Sanfilippo JHEP **07**
(2016) 089; Hasenbusch PRD **96**, 054504 (2017); Bonanno, Bonati, D'Elia JHEP
**03** (2021) 111; Bonanno, Nada, Vadacchino JHEP **04** (2024) 126;
**Albandea, Hernández, Ramos, Romero-López EPJC 81, 873 (2021) (mandatory: the
winding-HMC baseline)**.

*Multiscale thermalization / seeding* — **Endres, Brower, Detmold, Orginos,
Pochinsky PRD 92, 114516 (2015) (mandatory)**; Detmold, Endres PRD **97**,
074507 (2018).

*Diffusion ML foundations* (currently absent) — Vincent (2011) for denoising
score matching; Song, Ermon (2019); Ho, Jain, Abbeel (2020); Song et al. ICLR
(2021) for the SDE/probability-flow formulation; Grathwohl et al. (FFJORD) for
the continuous-flow likelihood; Neal (2001) for AIS (already cited in §21).

### 26.1 Bibliography, with verification status (2026-08-15)

Review item 2 of `docs/U1_2D_REVIEW.md` §Remaining asked for every Part V
citation to be checked against the actual paper, and for a bibliography. This
is that check. **Verified** means the title, author list, journal, volume,
article number and year were confirmed against arXiv, INSPIRE, or the
publisher's record on 2026-08-15. Entries marked *unverified* were not checked
and must be before submission — they are listed as such rather than silently
presented as confirmed.

**Verified.**

| citation | identifier |
|---|---|
| Lüscher, Schaefer, "Lattice QCD without topology barriers", JHEP **07** (2011) 036 | arXiv:1105.4749 |
| Schaefer, Sommer, Virotta, "Critical slowing down and error analysis in lattice QCD simulations", Nucl. Phys. B **845**, 93 (2011) | arXiv:1009.5228 |
| Hasenbusch, "Fighting topological freezing in the two-dimensional CP^{N−1} model", PRD **96**, 054504 (2017) | arXiv:1706.04443 |
| Bonanno, Bonati, D'Elia, "Large-N SU(N) Yang–Mills theories with milder topological freezing", JHEP **03** (2021) 111 | 10.1007/JHEP03(2021)111 |
| Bonanno, Nada, Vadacchino, "Mitigating topological freezing using out-of-equilibrium simulations", JHEP **04** (2024) 126 | arXiv:2402.06561 |
| Laio, Martinelli, Sanfilippo, "Metadynamics surfing on topology barriers: the CP^{N−1} case", JHEP **07** (2016) 089 | 10.1007/JHEP07(2016)089 |
| Albandea, Hernández, Ramos, Romero-López, "Topological sampling through windings", EPJC **81**, 873 (2021) | arXiv:2106.14234 |
| Endres, Brower, Detmold, Orginos, Pochinsky, "Multiscale Monte Carlo equilibration: Pure Yang–Mills theory", PRD **92**, 114516 (2015) | arXiv:1510.04675 |
| Bachtis, Aarts, Di Renzo, Lucini, "Inverse Renormalization Group in Quantum Field Theory", PRL **128**, 081603 (2022) | 10.1103/PhysRevLett.128.081603 |
| Rançon, Rançon, Ivek, Balog, "Dreaming up scale invariance via inverse renormalization group", PRE **113**, 055302 (2026) | arXiv:2506.04016 |
| Wang, Aarts, Zhou, "Diffusion models as stochastic quantization in lattice field theory", JHEP **05** (2024) 060 | arXiv:2309.17082 |
| Zhu, Aarts, Wang, Zhou, Wang, "Physics-Conditioned Diffusion Models for Lattice Gauge Theory", JHEP **03** (2026) 111 | arXiv:2502.05504 |
| Zhu, Aarts, Wang, Zhou, Wang, "Diffusion models for lattice gauge field simulations", NeurIPS 2024 ML4PS workshop | arXiv:2410.19602 |
| Singha, Chakrabarti, Arora, "Sampling gauge theory using a retrainable conditional flow-based model", PRD **108**, 074518 (2023) | 10.1103/PhysRevD.108.074518 |

**Three corrections this check produced.**

1. *Zhu et al. is two papers, and the study used both without distinguishing
   them.* arXiv:2502.05504 = JHEP 03 (2026) 111 is the journal paper whose
   MALA-exactness claim §25.6c tests. arXiv:2410.19602 is a separate, shorter
   NeurIPS 2024 workshop paper, and it is the one whose figures §25.6b
   digitizes. Scripts `46`/`47` correctly name 2410.19602; §26 previously named
   only the journal paper, so the digitization provenance pointed at the wrong
   document. Both are now listed.
2. *The Rançon citation dropped an author.* It is Adam Rançon, **Ulysse
   Rançon**, Tomislav Ivek, Ivan Balog — two authors named Rançon, and the
   second was lost.
3. *A coincidence that looks like an error and is not.* Zhu et al. JHEP **03**
   (2026) **111** and Bonanno, Bonati & D'Elia JHEP **03** (2021) **111** share
   an issue and article number in different years. Both were confirmed
   independently against INSPIRE. Do not "fix" either one.

**Unverified — must be checked before submission.** Ron, Swendsen & Brandt PRL
89, 275701 (2002); Efthymiou, Beach & Melko PRB 99, 075113 (2019); Bachtis PRB
110, L140202 (2024); Bachtis arXiv:2405.16288; Cotler & Rezchikov
arXiv:2308.12355; Masuki & Ashida arXiv:2501.09064; Albergo, Kanwar & Shanahan
PRD 100, 034515 (2019); Kanwar et al. PRL 125, 121601 (2020); Del Debbio, Marsh
Rossney & Wilson PRD 104, 094507 (2021); Abbott et al. arXiv:2211.07541; Nicoli
et al. PRD 108 (2023) *(no article number recorded — incomplete as written)*;
Bauer, Kapust, Pawlowski & Temmen arXiv:2412.12842; Singha et al.
arXiv:2604.10209; Del Debbio, Manca & Vicari PLB 594, 315 (2004); Detmold &
Endres PRD 97, 074507 (2018).

Note also that an **erratum** exists for Albandea et al. (EPJC **83**, 508
(2023)) and should be cited alongside the original, since that paper is now the
classical baseline of record for this study (§25.6a, Table S8).
