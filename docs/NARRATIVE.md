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
  delicate and deliberate: enforcement is applied periodically during *late*
  sampling — after the sector has effectively frozen (around
  $\sigma \sim O(1)$, below which the model will no longer spontaneously
  tunnel), but while enough noise remains for the sampler to relax the small
  uniform strain the shift introduces ($2\pi \Delta Q / V$ per plaquette).

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
extrapolation coupling had been destroyed (std 2202 at $32{:}218.6$). Both
failure modes were promptly engineered away:

**Tier 3, second attempt — rkl2 (the one genuine model improvement).**
Round-robin reverse-KL training over three cases spanning the coupling range;
evaluation on rotating *disjoint* coarse subsets with rotating seeds (nothing
fixed to overfit by selection); and checkpoint saves gated on two conditions
simultaneously — mean ESS improvement *and* a never-trained extrapolation
monitor staying below $1.5\times$ its initial spread. The guard did real
work: it blocked 4 of 6 save opportunities, including the
highest-training-ESS state. Result under fresh-seed verification: **spread
roughly halved at every coupling** — 15.1 / 19.7 / 40.8 / 102.6 on the four
standard cases — including on cases never trained on, later extended to five
never-trained points from $\beta = 2$ to $218$. Generalizable, kept, and now
the default checkpoint. But keep the honest frame: ESS stayed at $1/N$.
Halving $42 \to 20$ is real progress measured against a bar of $O(1{-}3)$ —
it is progress on a logarithmic journey of which this is the first step, not
the last.

**Capacity/data scale-up (negative — the "just scale it" falsification).**
Hypothesis: the density gap is a capacity/coverage problem, so a bigger
network with more data closes it. Test: $3.7\times$ parameters, 24 additional
$L=32$ training ensembles, fresh training ($\sim 4.7$ h). Result: better
only exactly where the new data was (in-range $L=32$), *worse* at
extrapolation (211.9 vs 163.7 at $32{:}218.6$), and strictly worse than the
small-net rkl2 checkpoint everywhere; under subsequent reverse-KL pressure
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
  current best is 4–10× away from that bar, *everywhere* in the scanned
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

- **As a sampler graded on observables** (the paper's actual claim): fully
  validated, far outside the training range, with flat generation cost in
  exactly the regime where exact-by-construction HMC becomes unusable — plus
  the seeding mode, where diffusion supplies the expensive thermalized
  starting ensemble and a seconds-long exact MCMC tail supplies
  correctness. This claim stands, was never in question this week, and is
  the transferable architecture.

- **As an exact sampler certified by importance weights** (the flow papers'
  claim): now *quantified* as out of reach — per-site density error of
  0.02–0.07 nats against a bar of $\sim 0.005$ — with a documented
  falsification chain showing that sampler knobs, both directions of
  KL fine-tuning, capacity/data scaling, and estimator restructuring do not
  close the gap. And in the non-abelian target theory this route is
  unavailable *in principle* (the forward heat kernel, and hence the score
  target, is itself approximate — Section 9), which converts this week's
  negative into a design directive:

> **Exactness must come from Markov-chain machinery wrapped around the
> generative proposal — Metropolis tails, seeded chains — not from the
> proposal's own likelihood.**

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
its floor exactly. The mechanism works as derived; what remains is a
*basis-representation* question, not a bridging question.

**Why the basis cannot simply be widened.** The obvious next move — add
features until $R^2 \to 1$ — was tried (11 features) and produced the
program's sixth converged negative: in-sample $R^2$ rose, and the held-out
weights exploded by two to three orders of magnitude at two of four cases.
The mechanism deserves stating because it recurs throughout this project:
the fit is performed on samples from $q$, but the bridge dynamics *move* the
samples toward $p$, evaluating $G$ off the fit manifold, where a wide,
weakly-regularized basis extrapolates wildly. It is the
deployment-vs-data-side asymmetry of section 18 in yet another costume:
an in-sample objective improvement bought a deployed-distribution failure,
now for the surrogate rather than the score.

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

### 22. Closure: what "finished" means, and what transfers

The 2D U(1) study is finished in the strong sense: every avenue is either
adopted, or closed by a converged measurement with an understood mechanism.

* **Adopted:** the v2 campaign pipeline (retherm + instanton tails +
  exact-sector mode) for physics claims; $\sigma_{\min}$-coef $0.03$ and the
  guarded rkl2 checkpoint for likelihood work; AIS as the validated
  exactness mechanism (floor-saturating, positive spread reduction).
* **Closed with mechanism:** matching residual (negligible — Villain
  control); data-side fine-tuning in all forms (forward/reverse-KL
  asymmetry); capacity scaling (extrapolation cost); SMC (no weight
  diversity); wide surrogate bases (off-manifold extrapolation);
  sector-crutch-alone and bridge-alone exactness (each removes only its own
  component of a now fully decomposed gap).
* **Measured and named as residual:** the $\approx 1$ nat/site mean density
  offset; the $0.02$–$0.07$ nats/site spread; the volume-growing raw $Q^2$
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
