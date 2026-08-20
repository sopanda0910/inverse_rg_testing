# 2D U(2) Inverse RG: Narrative, Mathematics, and Measurements

*The complete story of the 2D U(2) study — what it is, why it is built the way it
is, every derivation that carries weight, and every number that has been measured.
Written to be read without prior lattice background but without softening the
mathematics. Companion to `DESIGN.md` (derivations in condensed form) and to
`docs/u1_2d/NARRATIVE.md` (the closed U(1) predecessor).*

Last updated: 2026-08-20.

---

## Part 0 — The one-paragraph version

2D U(2) lattice gauge theory is exactly solvable, non-abelian, and carries its
topology entirely in the determinant of the link variable. Writing each link as
$U = e^{i\phi} q$ with $q \in SU(2)$, the field $\psi = \arg\det U = 2\phi$ is an
honest compact U(1) gauge field, and the topological charge is a functional of
$\psi$ alone. So a diffusion model trained on the determinant sector — reusing the
U(1) machinery unchanged — generates the topology, while the SU(2) sector needs no
model at all: at frozen $\phi$ the local weight is exactly $e^{\beta\,k\cdot q}$,
which a heat bath samples exactly. The inverse-RG ladder then transports
topological charge as an *identity*, climbing to couplings where local algorithms
cannot change sector at all. What is new relative to U(1) is a $\mathbb{Z}_2$
obstruction: $U(2) = (U(1)\times SU(2))/\mathbb{Z}_2$ makes even charge changes free
and forces odd ones across a monodromy, which splits the classical freezing problem
into two mechanisms with different controlling parameters — the even channel is a
ladder invariant and never closes, the odd one closes at $\beta \approx 15$–$20$
and stays closed. The measured advantage is **reachability, not speed**: for local
observables the ladder is $3.7\times$ more expensive than HMC with a winding update
at the accuracy-of-record setting, of which a tunable factor of three is
recoverable, while for topology the classical arm covers only half the exact
$P(Q)$, reaches *no* odd sector at all, and cannot improve on that at any cost.

---

## Part I — Why U(2), and what carries over

### 1. The problem being solved

Lattice gauge theory computes expectation values
$$\langle \mathcal{O}\rangle = \frac{1}{Z}\int \mathcal{D}U \; \mathcal{O}(U)\, e^{-S(U)},
\qquad Z = \int \mathcal{D}U\, e^{-S(U)},$$
by Monte Carlo. The standard tool, hybrid Monte Carlo (HMC), evolves the field
through a fictitious Hamiltonian dynamics and accepts with a Metropolis test. It
works well until the continuum limit, where two things go wrong at once:

* **critical slowing down** — autocorrelation times grow as a power of the
  correlation length, so independent configurations get expensive;
* **topological freezing** — the configuration space splits into sectors labelled
  by an integer $Q$, the action barrier between them grows with $\beta$, and the
  chain stops changing sector *entirely*. Not slowly: never.

Freezing is the harder failure because it is not a slow mode, it is a
disconnected one. A frozen chain reports small error bars on a wrong answer,
because it never samples the sectors it is missing.

**Inverse RG** attacks this by sampling where it is easy and lifting to where it
is hard. Coarse-grain by a factor of two and the theory becomes cheaper in every
respect; the inverse map — coarse configuration to fine configuration — is what a
diffusion model learns. Iterating the lift climbs a matched ladder of $(L, \beta)$
rungs toward the continuum, and if the lift carries topology correctly then the
frozen sectors arrive for free.

### 2. Why U(2) is the right successor to U(1)

The U(1) study (closed 2026-08-02) established the machinery and its limits. U(2)
was chosen for three reasons, and each turned out to hold:

1. **It is exactly solvable.** In two dimensions the plaquettes are independent
   after gauge fixing, so the partition function on a $V$-site torus is a sum over
   irreducible representations,
   $$Z = \sum_{(j,k)} \left(\frac{c_{j,k}}{d_j}\right)^{V},$$
   and every observable of interest has a closed form. Validation compares against
   the truth, not against another simulation.
2. **It is genuinely non-abelian.** $SU(2) \subset U(2)$ is the smallest
   non-abelian compact group, so the plaquette is a matrix product that does not
   commute, and the naive abelian shortcuts must be re-derived rather than assumed.
3. **Its topology is abelian.** $\pi_1(U(2)) = \mathbb{Z}$ is detected entirely by
   the determinant, and $\pi_1(SU(2)) = 0$. So the hard part — topology — reduces
   to the problem already solved, while the group is new.

That third point is what makes the project tractable, and it is worth being
precise about, because it is the load-bearing structural claim.

### 3. Representation and conventions

A U(2) matrix factorizes as a phase times a special-unitary matrix,
$$U = e^{i\phi}\, q, \qquad q = q_0 \mathbb{1} + i q_a \sigma_a, \qquad
\sum_{\mu=0}^{3} q_\mu^2 = 1,$$
with $\sigma_a$ the Pauli matrices. The code stores links as `[..., 5]` arrays
$(\phi, q_0, q_1, q_2, q_3)$, matching the sibling NTHMC repository so
configurations are interchangeable.

The factorization is **two-to-one**: $(\phi, q)$ and $(\phi + \pi, -q)$ give the
same $U$. That redundancy is exactly the $\mathbb{Z}_2$ that later obstructs
odd-charge winding, so it is not a bookkeeping nuisance — it is the physics.

Plaquette, action, and charge:
$$P_{x} = U_0(x)\, U_1(x+\hat 0)\, U_0(x+\hat 1)^\dagger\, U_1(x)^\dagger,
\qquad S = -\beta \sum_x \tfrac{1}{2}\mathrm{Re}\,\mathrm{Tr}\, P_x,$$
$$Q = \frac{1}{2\pi}\sum_x \mathrm{wrap}\big(\arg\det P_x\big) \in \mathbb{Z}.$$

Writing $P = e^{i\phi_P} q_P$ gives $\tfrac{1}{2}\mathrm{Re}\mathrm{Tr}\,P =
q_{P,0}\cos\phi_P$, a fact used repeatedly below.

### 4. The determinant sector is a compact U(1) gauge field

Define
$$\psi_\mu(x) = \mathrm{wrap}\big(2\phi_\mu(x)\big) = \arg\det U_\mu(x).$$

Because $\det$ is a group homomorphism, $\det(AB) = \det A \det B$, the determinant
of the plaquette is the product of the link determinants — so the *phase* of the
plaquette determinant is the plain **sum** of link phases:
$$\arg\det P_x = \psi_0(x) + \psi_1(x+\hat 0) - \psi_0(x+\hat 1) - \psi_1(x).$$

That is precisely the 2D compact-U(1) plaquette angle. No approximation, no
large-$\beta$ limit: the matrices do not commute, but their determinants do, and
the topological charge only ever sees determinants. Concretely:

> **$Q$ is a functional of $\psi$ alone.** The SU(2) content of the configuration
> is invisible to the topological charge.

`lgt.lattice.det_links` returns $\psi$ in the exact `[B, 2, L, L]` layout that
every `u1_2d.lgt` routine consumes, so the entire U(1) topology stack — charge,
instanton fields, blocking telescope, charge projection — is reused verbatim.

### 5. The blocking telescope survives, exactly

An inverse-RG step must know how a coarse plaquette relates to the four fine
plaquettes it contains. For U(1) this is a telescoping sum: interior links cancel
in pairs and the coarse plaquette angle is the wrapped sum of the four fine ones.
For a general non-abelian group it fails, because the four fine plaquettes are
matrices in different gauge frames and only their *ordered* product telescopes.

But the determinant is a homomorphism, so
$$\arg\det P^{\rm coarse} = \mathrm{wrap}\Big(\sum_{i=1}^{4} \arg\det P^{\rm fine}_i\Big)$$
holds identically. The abelian telescope survives verbatim in a non-abelian
theory, and therefore

> **Sector transport across an inverse-RG step is an identity, not an
> approximation.** Setting $\psi$ sets $Q$.

This is verified numerically in `scripts/09_verify_identities.py`.

### 6. The joint does not factorize — and the fix is free

It is tempting to write $p(\psi, q) = p(\psi)\,p(q)$ and generate the sectors
independently. That is **wrong**, and the reason is one line: the action couples
them multiplicatively,
$$\tfrac{1}{2}\mathrm{Re}\mathrm{Tr}\,P = \cos(\omega_P)\cos(\phi_P),$$
a product, not a sum. Independent generation is wrong at $O(\phi^2\omega^2)$.

The correct decomposition is conditional,
$$p(\psi, q) = p(\psi)\; p(q \mid \psi),$$
and the second factor costs nothing, because at frozen $\phi$ the U(2) local
weight for one SU(2) link is exactly
$$w(q) \propto \exp\big(\beta\, k\cdot q\big),$$
the standard SU(2) heat-bath form with a staple-dependent $k$. So
`lgt.local_updates.conditional_su2_sweeps` is an **exact sampler** for
$p(q\mid\psi)$, and — critically — it leaves $\psi$, and hence $Q$, bit-for-bit
unchanged.

Consequences worth stating plainly:

* The model generates $\psi$ only. The SU(2) sector has **zero learned
  parameters**.
* Naive inverse blocking of the coarse SU(2) part is only a *seed*; because what
  follows is an exact sampler, that seed cannot bias anything.
* Measured: discard the SU(2) sector entirely (replace with Haar noise, whose
  $\langle\frac12\mathrm{ReTr}P\rangle = 0.0019$) and two conditional sweeps
  recover $0.7318$ against an original $0.7337$; five sweeps give $0.7335$. $Q$ is
  identical throughout.

### 7. The determinant marginal is not Wilson at $\beta/4$

If the model generates $\psi$, what distribution should it target? Integrating
SU(2) out of a single plaquette gives the exact marginal weight
$$w_{\rm det}(\alpha) = \frac{2 I_1(z)}{z}, \qquad z = \beta\cos(\alpha/2),$$
where $\alpha$ is the determinant plaquette angle and $I_\nu$ is a modified Bessel
function (`lgt.actions.DetSectorAction`). Expanding, this is Wilson at $\beta/4$
**plus** a $\tfrac{3}{2}\log\cos(\alpha/2)$ measure term from the three SU(2)
directions.

So anything needing an analytic U(1) coupling must call
`lgt.exact.matched_u1_beta` — the minimum-KL projection of $w_{\rm det}$ onto the
Wilson family — never the tree-level $\beta/4$. They differ by **23% at
$\beta = 4$** and **0.003% at $\beta = 220$**: the naive value is badly wrong
exactly where the ladder starts.

The exact score used in the small-$\sigma$ physics blend follows from
differentiating $\log w_{\rm det}$:
$$\frac{d}{d\alpha}\log w_{\rm det}(\alpha)
= -\frac{\beta}{2}\sin(\alpha/2)\,\frac{I_2(z)}{I_1(z)},$$
which tends to the Wilson form only as the Bessel ratio $\to 1$ at large coupling.

### 8. Exact solution on the torus

Irreducible representations of U(2) are labelled $(j, k)$ with $j$ the SU(2) spin,
$k$ the U(1) charge, subject to the consistency condition $k \equiv 2j \pmod 2$ —
this is the same $\mathbb{Z}_2$ again, now as a selection rule. With dimension
$d_j = 2j+1$, the heat-kernel coefficients are
$$c_{j,k} = d_j \cdot \frac{2 I_{2j+1}(\beta)}{\beta} \quad\text{(fundamental
normalization)},$$
and the partition function on $V$ plaquettes is $Z = \sum_{j,k}(c_{j,k}/d_j)^V$.
Verified against direct Weyl integration to $10^{-10}$.

Two closed forms used constantly:
* **Area law**, exact in 2D because plaquettes are independent:
  $\langle \tfrac12\mathrm{ReTr}\,W(A)\rangle = r_{\rm fund}^{A}$, depending only
  on the enclosed area $A$, not the loop shape.
* **Determinant-sector $P(Q)$**, matching heat bath to 1–2% in every sector at
  $\beta = 2, 5, 8$.

---

## Part II — Topology in U(2): the $\mathbb{Z}_2$ obstruction

### 9. The statement

$U(2) = (U(1) \times SU(2))/\mathbb{Z}_2$, where the quotient identifies
$(\phi, q) \sim (\phi + \pi, -q)$. Tracking that identification around the torus
gives a parity selection rule:

> $Q$ **even** $\iff$ the ordered product of SU(2) plaquettes is $+1$;
> $Q$ **odd** $\iff$ it is $-1$.

So a change of topological charge by an **even** amount can be done in the U(1)
factor alone — it is central, it commutes with everything, and the SU(2) sector
never notices. A change by an **odd** amount cannot: it must drag SU(2) across a
$-1$ monodromy.

### 10. What that costs, measured

The even-charge move is the U(1) instanton unchanged. Its action cost is the
familiar
$$\Delta S = \frac{2\pi^2 \beta}{V},$$
and this is `central_winding_field`; `winding_update` defaults to
`charge_step = 2` for exactly this reason. Measured against the prediction:

| $L$ | $\beta$ | forced $\Delta S$, $\Delta Q = 2$ | predicted $2\pi^2\beta/V$ | acceptance |
|---|---|---|---|---|
| 8 | 8 | 5.9 | 2.5 | 0.406 |
| 8 | 20 | 5.5 | 6.2 | 0.000 |
| 16 | 20 | 1.4 | 1.5 | 0.281 |

The odd-charge move has no cheap implementation, and two constructions were tried
and measured:

* halving the U(1) instanton leaves one plaquette carrying a spurious $-1$, at
  cost $2\beta$ ($\Delta S = 37$ at $\beta = 20$, $L = 8$);
* the $U(1)_T$ subgroup construction costs $O(\beta L)$ instead ($\Delta S = 110$).

Gauge fixing does not help. Measured forced costs and acceptances:

| $L$ | $\beta$ | forced $\Delta S$, $\Delta Q = 1$ | acceptance | after exact SU(2) sweeps |
|---|---|---|---|---|
| 8 | 8 | 40.0 | 0.000 | $-0.9$ |
| 8 | 20 | 112.5 | 0.000 | $-1.6$ |
| 16 | 20 | 191.0 | 0.000 | $+1.6$ |

The last column is the point of the whole design: **the generative route does not
pay this cost.** Setting $\psi$ sets $Q$ — including odd $Q$ — and the exact
conditional SU(2) sampler then relaxes the monodromy for free. The classical move
is rejected with probability 1; the ladder simply arrives.

### 11. Two freezing mechanisms, with different scaling

This is the sharpest new result of the study, and it explains an apparent paradox:
U(2) HMC at $\beta \approx 200$ is *not* frozen, even though at $\beta = 20$ on a
smaller lattice it is.

The two moves have different controlling parameters:

| move | cost | controlling parameter | behaviour along the ladder |
|---|---|---|---|
| even $\Delta Q$ (central instanton) | $2\pi^2\beta/V$ | $\beta/V$ | **invariant** |
| odd $\Delta Q$ (crosses $\mathbb{Z}_2$), as a *global* shift | $O(\beta L)$ | $\beta L$ | grows as $L^3$ |
| odd $\Delta Q$, as HMC actually does it (*local nucleation*) | $O(\beta)$ per site | $\beta$ | grows as $\beta$ |

**The last two rows are not in conflict, and separating them fixes an error this
document carried.** $O(\beta L)$ is the cost of the explicit global constructions
in §10 — halving the central instanton, or the $U(1)_T$ subgroup shift — and it is
why no *fixed shift field* gives a cheap odd-charge move. But HMC does not use a
fixed shift field. It nucleates the $\mathbb{Z}_2$ crossing locally, so the
measured rate is a per-site rate times the volume, controlled by $\beta$ alone:
at $\beta = 14$ the flip rate per chain-trajectory is $2.7\times10^{-3}$ at
$L = 8$ and $9.6\times10^{-3}$ at $L = 16$, a ratio of $3.5$ against a volume
ratio of $4$. Quoting the global cost as the controlling parameter for the
*dynamics* — which earlier drafts did — predicts that a larger $L$ at fixed
$\beta$ freezes, and the opposite is measured. §12.1 has the flip counts.

Along a matched ladder $\beta_f = 4\beta_c$, $L_f = 2L_c$, so $\beta/V$ is
constant — the even-charge move never gets harder — while $\beta$ itself grows by
$4$ per rung, which is what shuts the odd channel. Measured on this ladder:

| $L$ | $\beta$ | $\beta/V$ | $\beta L$ |
|---|---|---|---|
| 8 | 14 | 0.219 | 112 |
| 16 | 51.75 | 0.202 | 828 |
| 32 | 203.15 | 0.198 | 6501 |
| 64 | 808.84 | 0.197 | 51766 |

The consequence is that a plain freezing diagnostic — "does the chain change
sector?" — reports **healthy** in a regime where $P(Q)$ is badly wrong, because
even-charge moves keep firing while the odd/even balance is stuck. The measurement
that exposes it is the total odd-sector weight, and it needs a *coherent* test:
each odd sector is individually within $1\sigma$, and jointly they are not.

### 12. Where $P(Q)$ can be sampled rather than seeded

`scripts/07_pq_sampling.py` runs unseeded HMC-plus-winding and compares the
resulting sector histogram to the closed form, with errors bootstrapped over
**chains** (a frozen chain contributes one independent charge however long it
runs). The verdict combines two independent failure modes: the chains must
actually tunnel, *and* the histogram must agree.

| $L$ | $\beta$ | $\beta/V$ | $\beta L$ | $\langle Q^2\rangle$ | exact | $z$ | $\chi^2$/dof | odd ratio | $z_{\rm odd}$ | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| 8 | 6 | 0.094 | 48 | $1.8799 \pm 0.018$ | 1.8674 | $+0.70$ | 1.03 | 0.994 | $-0.67$ | SAMPLED |
| 8 | 8 | 0.125 | 64 | $1.1973 \pm 0.012$ | 1.2007 | $-0.28$ | 0.89 | 0.994 | $-0.71$ | SAMPLED |
| 8 | 10 | 0.156 | 80 | $0.8533 \pm 0.009$ | 0.8603 | $-0.80$ | 0.49 | 0.989 | $-0.98$ | SAMPLED |
| 8 | 12 | 0.188 | 96 | $0.6655 \pm 0.011$ | 0.6707 | $-0.50$ | 0.88 | 0.999 | $-0.05$ | SAMPLED |
| **8** | **14** | **0.219** | **112** | $0.5547 \pm 0.021$ | 0.5514 | $+0.16$ | 1.29 | 0.978 | $-0.51$ | **SAMPLED** |
| 8 | 20 | 0.313 | 160 | $0.5775 \pm 0.043$ | 0.3551 | $+5.22$ | 22.45 | 1.694 | $+7.40$ | PARITY-STUCK |
| **16** | **28** | **0.109** | **448** | $1.0088 \pm 0.011$ | 1.0012 | $+0.69$ | 0.27 | 1.030 | $+0.69$ | **SAMPLED** |
| 16 | 51.75 | 0.202 | 828 | $0.5746 \pm 0.027$ | 0.5211 | $+2.02$ | 2.89 | 1.152 | $+2.89$ | PARITY-STUCK |
| 16 | 56 | 0.219 | 896 | $0.5331 \pm 0.027$ | 0.4793 | $+1.96$ | 2.72 | 1.152 | $+2.82$ | PARITY-STUCK |
| 32 | 203.15 | 0.198 | 6501 | $0.4323 \pm 0.051$ | 0.5150 | $-1.64$ | 1.79 | 0.778 | $-2.22$ | PARITY-STUCK |

**The sign of the parity imbalance is not fixed, and that is the clue to the
mechanism.** Two of the three stuck cases show an *excess* of odd weight (1.69,
1.15) and one a *deficit* (0.78). The barrier blocks the odd$\leftrightarrow$even
channel in **both** directions, so the parity balance simply keeps whatever the
initial condition gave it: these runs start hot, which strands excess odd weight,
while a *cold* start reaches **no odd sectors at all**. "Depletion" is the special
case, not the rule; the test is on $|z_{\rm odd}|$, and the verdict is named
PARITY-**STUCK** rather than PARITY-FROZEN for exactly that reason.

#### 12.1 Correction: the controlling parameter is $\beta$, not $\beta L$ — and the verdict is the wrong instrument

An earlier version of this section read a **parity boundary at
$\beta L \approx 450$–$830$** off the table above, bracketed by $16/28$ (clean)
and $16/51.75$ (stuck), and then needed a *second* axis — a thermalization
boundary at $\beta/V \approx 0.25$ — to explain why $L = 8$, $\beta = 20$ is stuck
at $\beta L = 160$, far below that boundary. Two axes, one of them fitted to three
points. **Both conclusions were artifacts of using the verdict as the
measurement**, and replacing it with a direct count of parity flips
(`scripts/15_base_parity.py`) removes the second axis entirely.

| $L$ | $\beta$ | $\beta L$ | $Q$ changes | **parity flips** |
|---|---|---|---|---|
| 8 | 6 | 48 | 20304 | 12810 |
| 8 | 10 | 80 | 14296 | 7100 |
| 8 | 14 | 112 | 6864 | 347 |
| 8 | 20 | 160 | 5862 | **4** |
| 16 | 14 | 224 | 32169 | 2453 |
| 16 | 21 | 336 | 26110 | **2** |
| 16 | 28 | 448 | 22283 | **0** |

Against $\beta L$ this does not collapse: $L = 16$ at $\beta L = 224$ flips 2453
times while $L = 8$ at $\beta L = 160$ flips four — a *larger* $\beta L$ with three
orders of magnitude more mobility. Against $\beta$ it collapses cleanly at both
volumes: **odd mobility dies between $\beta = 14$ and $\beta \approx 20$**, with
the per-site rate falling about a hundredfold across that interval. One axis, not
two, and the $L = 8$, $\beta = 20$ case needs no special pleading — it is simply
past the edge, like everything else past $\beta \approx 20$.

**Why the verdict misled.** The PARITY-STUCK test is a hypothesis test on the odd
weight computed from a *single* binomial draw over chains. It can pass with zero
mobility, and at the one coupling that matters most it does: **$L = 16$,
$\beta = 28$ — the ladder base — has zero parity flips and is called SAMPLED.** A
verdict answers "is this distribution right?", which is a fine question and not the
same question as "does the algorithm move?". Establish mobility by counting flips;
use the verdict to test the resulting distribution. The two conflicting
measurements this study carried at the base — $z_{\rm odd} = +2.42$ from the stored
ensemble against $+0.69$ from a scan at the identical coupling — were never a
contradiction and never a bias: they are two draws of a 256-chain binomial that
landed two sigma apart.

#### 12.2 What the base actually samples, and the bound that makes it safe

The claim about the base has to be stated in two halves, because the two halves
have different status.

**Sampled: the sector shape within a parity class.** 106823 $Q$ changes per 1024
chains per 1200 trajectories, $\tau_{\rm int}(Q^2) = 0.55$ draws, and a sector
histogram matching the closed form at $\chi^2/{\rm dof} = 1.53$. This is genuine
equilibrium sampling of everything except one bit.

**Not sampled: that one bit.** The odd/even weight is frozen in during the
hot-start ordering and never revisited — one independent draw per chain, forever.
The proof is a cold start, which under an equilibrating algorithm could not matter:

| $L$ | $\beta$ | exact odd | hot start | cold start |
|---|---|---|---|---|
| 8 | 10 (mobile) | 0.4854 | 0.4860 | 0.4802 |
| 8 | 20 (frozen) | 0.3335 | 0.5156 | 0.0003 |
| 16 | 28 (frozen, **the base**) | 0.4928 | 0.4727 | 0.0000 |

Where parity moves, the initial condition is irrelevant and both starts land on the
exact value. Where it does not, the two starts differ by everything available. The
$L = 8$, $\beta = 20$ row is the important one: the exact odd weight there is
$0.3335$, well away from $1/2$, and the hot quench returns $0.5156$ — wrong by
$+55\%$. **The quench does not sample parity. It lands near $1/2$.**

So why is the base defensible? Because of a bound that can be quoted rather than
assumed. Exact $P({\rm odd})$ approaches $1/2$ from below as $P(Q)$ broadens, and
at $L = 16$ it runs $0.5000$ at $\beta = 14$, $0.4989$ at $21$, $0.4928$ at $28$,
$0.4861$ at $32$, $0.4239$ at $51.75$. The base sits at $\beta = 28$ with
$\langle Q^2\rangle = 1.0012$, so freezing in $1/2$ costs $+0.0072$ absolute —
$1.5\%$ relative, and $0.45\sigma$ against the binomial error of 1024 chains. It is
below the resolution the ensemble can offer.

**That is a real constraint on where a base may be placed, and it should be stated
as a design rule rather than discovered again:** the base needs
$\langle Q^2\rangle \gtrsim 1$, which is exactly the regime where $P({\rm odd})$ is
within a percent of $1/2$. A colder, narrower base fails badly — at $L = 8$,
$\beta = 20$, $\langle Q^2\rangle = 0.355$, the same procedure is off by $55\%$.
The topology-matched ladder targets $\langle Q^2\rangle \approx 1$ anyway, so the
requirement costs nothing here; it is a coincidence of design that should not be
relied on silently.

If a base with *fully mobile* parity is ever wanted, $L = 16$ at $\beta = 14$ has
2453 flips and $z_{\rm odd} = +0.50$. The cost is a top rung near $\beta = 224$
rather than $416.5$, which is why it has not been adopted: the present base buys a
colder headline coupling in exchange for a quantified $0.45\sigma$ systematic on
one bit.

The practical upshot survives, in a narrower form than before: **the ladder base
can be placed where the sector distribution is genuinely sampled and the parity
weight is provably right to better than the statistical resolution**, and transport
then carries that distribution into the deeply frozen regime where no local
algorithm could produce it.

---

## Part III — The pipeline

### 13. One inverse-RG step, in order

Given a coarse ensemble at $(L_c, \beta_c)$, one step produces $(2L_c, \beta_f)$:

1. **Lift the determinant field.** Conditional diffusion generates $\psi_{\rm fine}$
   from $\psi_{\rm coarse}$, with reconstruction guidance and in-trajectory charge
   projection. This is the only learned component.
2. **Seed the SU(2) sector** by naive inverse blocking of the coarse SU(2) part.
3. **Equilibrate SU(2) at frozen $\psi$** with the exact conditional heat bath.
   Cannot disturb $\psi$ or $Q$.
4. **Short joint rethermalization** at the target coupling, which repairs residual
   determinant-sector model error locally.

Step 3 is the load-bearing simplification and it is exact, so *all* modelling
error in the step lives in step 1.

### 14. The score network and its conditioning

Training is denoising score matching on the wrapped-Gaussian heat kernel of the
determinant field, reusing `u1_2d.model` unchanged. The network is fully
convolutional and conditioned on the coupling, **not** on the lattice size — which
is why coverage in $\beta$ matters and coverage in $L$ does not.

Conditioning channels (`coarse_conditioning_channels`, `cond_channels = 5`):
$\cos$ and $\sin$ of the coarse plaquette angle, $\cos$ and $\sin$ of the coarse
$2\times2$ loop angle, and — the fifth channel — the **raw wrapped plaquette
angle**. The fifth exists because $\cos/\sin$ discard the winding count: the raw
angle is the local winding density and sums to $2\pi Q_{\rm coarse}$, giving a
locally-receptive network direct access to where the coarse configuration carries
its charge.

With `cond_film = true` the *spatial mean* of the conditioning channels is
additionally projected into the FiLM embedding, so the global scalar
$Q_{\rm coarse}/V$ reaches every residual block. The projection is
zero-initialized, so it begins as a no-op and must earn its contribution.

**Why this matters less than it appears to.** Topology in this architecture is
*imposed, not learned*: `apply_coarse_charge` adds the smooth instanton difference
to force $Q$ onto the coarse value, both periodically during sampling (below
$\sigma = 0.5$) and once at the end. Whatever the network does with the topology
channel, the final sector is set by construction. Conditioning can only influence
how *typical* a configuration is within its sector — never which sector it
reaches. This is the structural reason richer global conditioning (attention,
learned $Q$ embeddings) is not where the remaining error lives.

### 15. Matching the ladder: two criteria, and why topology wins

A ladder step needs $\beta_f$ given $\beta_c$. Two criteria are available:

* **Plaquette matching** (`approx_matched_fine_beta`): choose $\beta_f$ so the
  coarse ensemble is distributed as the *blocked* fine ensemble. Right for the
  local action.
* **Topology matching** (`topology_matched_fine_beta`, added in this study): choose
  $\beta_f$ so the exact finite-volume $\langle Q^2\rangle$ is preserved.

They are not the same, and the difference matters *because transport is an
identity*. Under plaquette matching the exact $\langle Q^2\rangle$ still drifts —
$-6.9\%$ from $L=8$, $\beta=14$ to $L=64$, $\beta=808.84$ — and the ladder
structurally cannot correct it: whatever $P(Q)$ the base has is what every rung
inherits. Topology matching removes the drift by construction.

The two criteria nearly agree, and diverge only on small lattices where the
determinant-sector $P(Q)$ is still pre-asymptotic: starting from $L = 8$,
$\beta = 14$ they differ by 5.2%, 1.2%, 0.3% at successive rungs.

A subtlety worth recording: improving the *statistics* of the base makes the drift
**more** visible, not less, because the bias does not average away. Moving the base
from $L=8$/$\beta=14$ to $L=16$/$\beta=28$ tightens the error bar 3.7× and reduces
the drift only 2.5×, so the $z$-score would have got *worse*. Removing the bias is
the only fix that survives better statistics.

---


### 16. Residual model error: where it lives, and how big

Observable *means* agree with the closed form to a few parts in $10^6$, which by
itself says very little — the U(1) study established that agreement to two parts
in $10^4$ on the plaquette coexisted with a density gap of hundreds of nats. Two
sharper probes were run.

**Per-configuration spread.** The width of the distribution, not its centre.
Against an HMC reference at $L = 32$, $\beta = 105.651$:

| loop | generated $\sigma$ | HMC $\sigma$ | ratio |
|---|---|---|---|
| $1\times1$ | $4.130\times10^{-4}$ | $4.219\times10^{-4}$ | 0.979 |
| $2\times2$ | $2.432\times10^{-3}$ | $2.455\times10^{-3}$ | 0.991 |
| $4\times4$ | $1.341\times10^{-2}$ | $1.415\times10^{-2}$ | 0.947 |
| $8\times8$ | $4.881\times10^{-2}$ | $5.002\times10^{-2}$ | 0.976 |

Consistently **2–5% under-dispersed** with no trend in loop size. Mild
mode-seeking, which is the expected failure direction for a diffusion model, and
notably *not* the U(1) failure mode, where the discrepancy grew with loop size
(std$(z)$ $1.09 \to 1.44$ from $W(4\times4)$ to $W(12\times12)$).

**The area-law ratio, and why it must be read against a control.** In infinite
volume the plaquettes inside a 2D Wilson loop are independent, so
$$\langle W(A)\rangle = \langle W(1)\rangle^{A}$$
identically, and the ratio $\langle W(A)\rangle / \langle W(1)\rangle^{A}$ is a
test an ensemble applies to *itself* — no reference, no error model, no closed
form beyond the one already verified. Applied to the exact values at $L = 64$ it
returns $1.00000$ at every area up to $A = 144$, so the identity is clean at this
geometry and any departure is a property of the ensemble.

At $L = 64$ the generated ensemble departs from 1 monotonically as the loop grows.
Earlier drafts of this document called that *suggestive but uncontrolled* and said
settling it required a direct HMC ensemble at $L = 64$, $\beta = 416.524$. That
ensemble now exists, and a second piece of evidence arrived unplanned: the base
was regenerated with more chains for an unrelated reason (§12.2), which re-drew the
whole ladder from a fresh coarse ensemble.

**The trend flipped sign.** At $A = 144$ the generated ensemble moved from
$z = +1.70$ to $z = -2.43$ against the exact value, with the pipeline, the
checkpoint, the coupling and the step count all unchanged — only the base
realization differed. A systematic model bias cannot do that. A correlated
statistical fluctuation is the only thing that can.

The reference, which was not regenerated, is the second control:

| $A$ | generated ratio | HMC reference ratio | exact ratio |
|---|---|---|---|
| 16 | 0.99997 | 1.00017 | 1.00000 |
| 36 | 0.99977 | 1.00032 | 1.00000 |
| 64 | 0.99907 | 1.00035 | 1.00000 |
| 100 | 0.99759 | 0.99923 | 1.00000 |
| 144 | **0.99482** | **0.99623** | 1.00000 |

Applied to the exact values the ratio returns $1.00000$ at every area, so the
identity is clean at this geometry and any departure belongs to the ensemble. Both
ensembles depart; over loops of area $\ge 48$ the mean absolute deviation from
exact is $1.13\times10^{-3}$ for the generated ensemble against
$9.9\times10^{-4}$ for the reference, and at the largest loop the *reference* is
the further of the two. Against the reference directly, the generated ensemble
agrees to $+0.09\sigma$, $+0.05\sigma$ and $-0.21\sigma$ at $A = 144$, $120$ and
$100$.

**So the area-law excess is finite statistics, not model error.** The size is what
it should be: the per-configuration spread of $W(12\times12)$ over this many
configurations gives a standard error near $1.8\times10^{-3}$ relative before any
correction for chain autocorrelation, so both ensembles sit one to one-and-a-half
sigma out.

One number in the same table has to be read with care in the other direction. The
plaquette disagrees with the reference at $z = +3.98$ — but the split is
$+0.80\sigma$ for the generated ensemble against exact and $-4.25\sigma$ for the
*reference* against exact. The reference is the one that is off, because its error
bar is a plain $\sigma/\sqrt{N}$ over a Markov chain with acceptance $0.37$ and is
therefore optimistic. A large $z$ against a reference is a statement about two
error models, not about one ensemble; the exact column is the one to quote.

The one genuinely instructive thing here is *why it looked so convincing*. The
trend is smooth, monotonic in $A$, and correlated with $\log A$ at $+0.972$ —
every visual cue of a systematic. But large Wilson loops within a single ensemble
are strongly correlated with each other, being functionals of the same bulk
field, so eighteen same-signed points are **one** fluctuation drawn eighteen
times, not eighteen independent confirmations. The correlation coefficient
measures the smoothness of the rendering, not the significance of the effect.
This is the same lesson as the $\langle Q^2\rangle$ drift in §13, arriving from
the opposite direction: there, better statistics made a real bias *more* visible;
here, correlated observables made a non-existent one look real. Both are reasons
to insist on a same-size control rather than reasoning from a trend.

The general rule this study now applies: **a monotonic trend across observables
that are functionals of the same field is not evidence of a systematic.** Two
tests distinguish the cases, and neither is the smoothness of the curve — a
same-size control that deviates comparably, and independence under
re-randomization of the inputs. The $\langle Q^2\rangle$ drift survived both and
was real; the area-law excess failed both and was not.

## Part IV — Measurements

<!-- BEGIN GENERATED RESULTS -->

*Generated by `scripts/12_results_section.py` from the JSON each stage wrote; do not edit by hand.*

### Ladder: observables against the closed form

| $L$ | $\beta$ | $\langle P\rangle$ | exact | rel. err | pre-retherm | $\langle Q^2\rangle$ | exact |
|---|---|---|---|---|---|---|---|
| 32 | 105.651 | 0.981029 | 0.981023 | $+6.21e-06$ | 0.981123 | 1.0156 | 1.0012 |
| 64 | 416.524 | 0.995197 | 0.995195 | $+1.32e-06$ | 0.995260 | 1.0156 | 1.0012 |

The pre-rethermalization column is the one that separates model quality from local-update repair: where it already matches, the diffusion lift earned the agreement unaided.

### Validation against HMC and the closed form

| $L$ | $\beta$ | plaquette $z$ vs exact | max Wilson $z$ vs ref | mean | reference |
|---|---|---|---|---|---|
| 32 | 105.651 | $+0.47$ | 1.34 | 0.84 | stage-01 ensemble |
| 64 | 416.524 | $+0.80$ | 3.98 | 0.60 | stage-01 ensemble |

Read the *exact* column. A $z$ against the HMC reference carries that reference's own uncorrelated-sample assumption, which is not true of a Markov chain; this study measured a spurious $-3.26\sigma$ that way while the generated ensemble was in fact closer to exact than the reference was.

### The top rung against a direct HMC reference

$L = 64$, $\beta = 416.524$ -- the extrapolation the ladder exists for, now with a direct HMC ensemble at the same coupling. It is a **control, not a competing sampler**: its topology is seeded from the closed form ($\beta L = 26658$, two orders past the parity boundary), so it says nothing about sectors and everything about local and extended observables.

| loop | area | $z$ generated | $z$ reference | $|{\rm dev}|$ generated | $|{\rm dev}|$ reference |
|---|---|---|---|---|---|
| W 1x1 | 1 | $+0.80$ | $-4.25$ | $1.32e-06$ | $1.06e-05$ |
| W 1x2 | 2 | $+1.39$ | $-1.86$ | $5.54e-06$ | $1.19e-05$ |
| W 2x2 | 4 | $+0.96$ | $-0.31$ | $9.49e-06$ | $4.37e-06$ |
| W 2x3 | 6 | $+0.56$ | $-0.95$ | $9.73e-06$ | $2.32e-05$ |
| W 3x3 | 9 | $+0.40$ | $+0.01$ | $1.22e-05$ | $3.97e-07$ |
| W 3x4 | 12 | $+0.56$ | $-0.26$ | $2.52e-05$ | $1.59e-05$ |
| W 4x4 | 16 | $-0.07$ | $+0.03$ | $4.83e-06$ | $3.17e-06$ |
| W 4x5 | 20 | $-0.36$ | $-0.32$ | $3.32e-05$ | $4.05e-05$ |
| W 5x5 | 25 | $-0.49$ | $-0.51$ | $6.12e-05$ | $9.03e-05$ |
| W 5x6 | 30 | $-0.52$ | $-0.34$ | $8.34e-05$ | $7.70e-05$ |
| W 6x6 | 36 | $-0.76$ | $-0.19$ | $1.54e-04$ | $5.44e-05$ |
| W 6x7 | 42 | $-0.83$ | $-0.35$ | $2.08e-04$ | $1.26e-04$ |
| W 7x7 | 49 | $-1.12$ | $-0.20$ | $3.42e-04$ | $8.72e-05$ |
| W 7x8 | 56 | $-1.11$ | $-0.46$ | $3.98e-04$ | $2.43e-04$ |
| W 8x8 | 64 | $-1.47$ | $-0.39$ | $6.23e-04$ | $2.43e-04$ |
| W 8x10 | 80 | $-1.52$ | $-0.83$ | $8.47e-04$ | $6.75e-04$ |
| W 10x10 | 100 | $-1.96$ | $-1.10$ | $1.41e-03$ | $1.14e-03$ |
| W 10x12 | 120 | $-2.11$ | $-1.51$ | $1.83e-03$ | $1.90e-03$ |
| W 12x12 | 144 | $-2.43$ | $-1.79$ | $2.50e-03$ | $2.65e-03$ |

Over loops of area $\ge 48$ the mean absolute deviation from exact is $1.13e-03$ for the generated ensemble and $9.91e-04$ for the reference -- the same size, and at the largest loop the *reference* is the further of the two. **The large-loop drift is not model error.** It is what an ensemble of this size does at this coupling, and the ladder reproduces it.

Two cautions on reading the $z$ columns. The deviations of large loops *within one ensemble* are strongly correlated -- they are all functionals of the same bulk field -- so nineteen same-signed rows are one fluctuation, not nineteen. And the reference's error bar is a plain $\sigma/\sqrt{N}$ over a Markov chain with acceptance 0.37, so it is optimistic; its plaquette $z$ of $-4.25$ measures that optimism, not a defect in the closed form.

### Seed quality and topological reach

$L = 64$, $\beta = 416.524$, 64 chains, 300 trajectories per arm.

| arm | $|\Delta P/P|$ at $t=0$ | at $t=T$ | $\langle Q^2\rangle$ | sectors | $P(Q)$ covered | odd sectors |
|---|---|---|---|---|---|---|
| **A** diffusion seed | $8.21e-06$ | $4.49e-06$ | 1.141 | 6 | 0.995 | 3 |
| B cold start | $4.83e-03$ | $4.30e-05$ | 0.000 | 1 | 0.399 | 0 |
| C hot start | $1.00e+00$ | $6.24e-02$ | 109.370 | 51 | 1.000 | 25 |
| D cold + winding | $4.83e-03$ | $5.18e-05$ | 0.856 | 3 | 0.507 | 0 |

Exact $\langle Q^2\rangle = 1.0012$. The independent-configuration interval for a plain chain is $2\tau_{\rm int} = 3.2$ trajectories.

**Read coverage together with the second moment, never alone.** The
hot-start arm covers 1.000 of the exact $P(Q)$ by visiting 51 sectors
while carrying a second moment of 109 against an exact 1.001 -- it covers
everything by being everywhere, and is nowhere near equilibrium (its
plaquette is still 6% off after 300 trajectories). Coverage rewards
breadth; only the pair of numbers identifies a correct distribution.

The diffusion arm uses the first 64 configurations of the 512-configuration
ensemble, so its sampling error on the second moment is about 0.09 and it
will not equal the ladder value exactly.

### Per-configuration Wilson spread

At $L = 32$, $\beta = 105.651$. Means agree to $10^{-6}$; the width is the informative quantity.

| loop | generated $\sigma$ | HMC $\sigma$ | ratio |
|---|---|---|---|
| W 1x1 | 4.105e-04 | 4.219e-04 | 0.973 |
| W 2x2 | 2.398e-03 | 2.455e-03 | 0.977 |
| W 4x4 | 1.390e-02 | 1.415e-02 | 0.982 |
| W 8x8 | 4.849e-02 | 5.002e-02 | 0.969 |

### Per-configuration Wilson spread at the top rung

At $L = 64$, $\beta = 416.524$. Means agree to $10^{-6}$; the width is the informative quantity.

| loop | generated $\sigma$ | HMC $\sigma$ | ratio |
|---|---|---|---|
| W 1x1 | 5.311e-05 | 5.659e-05 | 0.939 |
| W 2x2 | 3.147e-04 | 3.208e-04 | 0.981 |
| W 4x4 | 2.164e-03 | 2.105e-03 | 1.028 |
| W 8x8 | 1.357e-02 | 1.397e-02 | 0.972 |

The width tracks the reference to within 3-8% at every loop size and shows **no growth with loop area**. That is the comparison the U(1) study could not pass -- there the dispersion ratio climbed 1.09 to 1.44 from $W(4\times4)$ to $W(12\times12)$, and residual model error was diagnosed by exactly that growth. Here it is flat, at the rung furthest from anything the model was trained on.

### Cost per independent configuration

$L = 64$, $\beta = 416.524$, 64 chains. For a Markov chain the cost is $2\tau_{\rm int}\,t_{\rm traj}/n_{\rm chains}$, with $\tau_{\rm int}$ measured on the equilibrated tail only.

| arm | $\tau_{\rm int}(P)$ | s / trajectory | **s / independent config** |
|---|---|---|---|
| A diffusion seed | 5.9 | 1.568 | **0.2911** |
| B cold start | 16.9 | 0.895 | **0.4724** |
| C hot start | nan | 0.929 | - |
| D cold plus winding | 8.0 | 0.851 | **0.2122** |

Ladder: **0.7803 s** per configuration including base generation, **0.4678 s** for the top rung alone.

**For local observables the ladder is 3.68x SLOWER than HMC + winding.** That is the honest headline and it should not be buried: this method is not a speed-up for the plaquette or small Wilson loops. The cost is dominated by the 200-step diffusion sampler, and the obvious hedge -- that the sampler is tunable and was never tuned -- **is real and worth about a factor of three**, measured in the scan below. At 25 steps the top rung turns from 2.22x slower into 1.38x *faster* than HMC + winding, at roughly 2.7x the extended-loop error and no measurable change in local observables after rethermalization. So the number quoted here is the cost of the ACCURACY-OF-RECORD setting, not a floor. What does not move is the remaining overhead: the exact conditional SU(2) sampler, which no amount of sampler tuning touches.

**The topological claim is reachability, not speed.** The classical arm covers 0.507 of the exact $P(Q)$ with zero odd sectors and cannot improve on that at any cost, because odd charge has probability *zero* in its stationary distribution rather than merely long autocorrelation. A ratio of seconds against an arm that never arrives is meaningless, so the two claims must be stated separately.

### How many reverse-diffusion steps the lift needs

The 200-step sampler was chosen once and never revisited, and stage 13 charged the whole ladder for it. The narrative used to hedge the cost verdict on the grounds that the sampler was *tunable but untuned*, which is not a defensible thing to leave in a paper: either the hedge is real and the cost number is inflated, or it is not and the verdict is final. It is tuned now, and the answer is that the hedge is real and worth about a factor of three -- purchased, not free.

Scan run at 512 configurations per rung, so the comparable quantity across rows is seconds *per configuration*; the ladder of record at 200 steps and 1024 configurations reproduces this table's 200-step row to 0.5%.

**Read rung 0, not the top rung.** Rung 0 lifts the fixed HMC base, byte identical in every run, so its error is one diffusion lift and nothing else. The top rung lifts rung 0's *output*, so its plaquette error is a compound of two lifts that partially cancel -- it runs the wrong way across this scan and means nothing on its own. Extended loops at the top rung are the second honest column, because that is where residual model error concentrates.

| steps | total s | top-rung s/config | vs hmc+winding | **rung 0 pre** | rung 0 post | top $W(4\times4)$ | top $W(8\times8)$ |
|---|---|---|---|---|---|---|---|
| 8 | 54 | 0.0833 | **2.55x faster** | **$-1.23e-02$** | $+4.31e-05$ | $-1.20e-03$ | $-1.49e-02$ |
| 12 | 56 | 0.0900 | **2.36x faster** | **$-2.21e-03$** | $-2.92e-07$ | $-5.30e-04$ | $-7.37e-03$ |
| 18 | 64 | 0.1032 | **2.06x faster** | **$+1.52e-04$** | $+1.28e-05$ | $-1.86e-04$ | $-3.45e-03$ |
| 25 | 118 | 0.1535 | **1.38x faster** | **$+3.21e-04$** | $-1.75e-06$ | $-5.33e-05$ | $-1.14e-03$ |
| 50 | 145 | 0.1670 | **1.27x faster** | **$+2.34e-04$** | $+6.76e-06$ | $-2.07e-04$ | $-2.37e-03$ |
| 100 | 183 | 0.2681 | 1.26x slower | **$+1.61e-04$** | $-2.66e-05$ | $-1.13e-04$ | $-1.88e-03$ |
| 200 | 301 | 0.4703 | 2.22x slower | **$+1.01e-04$** | $+5.72e-06$ | $-2.49e-05$ | $-4.24e-04$ |
| 400 | 547 | 0.8768 | 4.13x slower | **$+1.03e-04$** | $-2.25e-05$ | $+2.21e-05$ | $-1.56e-04$ |

**Tune on $W(8\times8)$, not on the plaquette -- the plaquette has an accidental zero.** Rung 0's plaquette error changes SIGN between 12 and 18 steps, so at 18 steps it reads $+1.5\times10^{-4}$, as good as 100 steps and better than 25, while $W(8\times8)$ at the top rung is eight times worse there than at 200. A quantity passing through zero is a terrible selector, and picking the step count off the plaquette alone would have chosen a setting that is quietly bad at every extended observable. The extended loops are monotone and unambiguous: $W(8\times8)$ improves $1.5\times10^{-2} \to 3.4\times10^{-3} \to 1.1\times10^{-3} \to 4.2\times10^{-4} \to 1.6\times10^{-4}$ at 8, 18, 25, 200, 400 steps.

**So accuracy does not saturate at 200, and the hedge partly survives -- but it is a dial, not a free lunch.** Below 18 steps the lift collapses (rung 0 off by $-1.2\times10^{-2}$ at 8 steps, and the rethermalization sweeps still return $+4.3\times10^{-5}$, hiding all of it). Above that the whole range is usable and the trade is explicit: dropping 200 to 25 makes the top rung **1.38x faster** than HMC + winding instead of 2.22x slower -- a factor of three in cost -- for about 2.7x the extended-loop error and no measurable change in local observables after rethermalization ($-1.8\times10^{-6}$ at 25 steps against $+5.7\times10^{-6}$ at 200). Going the other way, 400 steps buys a further 2.7x on extended loops for 1.8x the cost.

**The ladder of record stays at 200 steps**, because its job is to be the accuracy measurement rather than the cheapest configuration source, and because 25 steps would put the study's extended-observable claims where its own $L = 64$ reference sits rather than comfortably inside it. A production run that wants configurations should use 25.

**Per-configuration Wilson spread is flat across the whole scan** ($\sigma[W(2\times2)] = 2.9$-$3.2\times10^{-4}$ against the reference's $3.2\times10^{-4}$), so a coarse sampler biases the mean without narrowing the distribution. Cheap configurations do not come out over-smoothed, which is the failure mode one would expect and it does not happen.

$\langle Q^2\rangle$ is deliberately absent from this table. It is flat by construction -- `apply_coarse_charge` imposes the coarse charge on the final sample -- so topology is transported correctly at any step count, and printing it invites reading a tautology as a result.

**Cost is not linear in the step count.** The two cheapest points fit about 1.05 s per step on a fixed overhead near 90 s: the exact conditional SU(2) sampler (30 sweeps) and the rethermalization (10 sweeps), which no amount of sampler tuning touches. At 200 steps that overhead is 30% of the run, at 25 steps it is three quarters. Anyone moving down the dial hits it quickly, so `n_su2_sweeps` is the next knob to measure, not this one.

### Parity mobility: the odd fraction is a label, not an observable

Hot start, **no burn-in**, unseeded, so a slow relaxation and a frozen label are distinguishable -- they prescribe opposite fixes. The decisive column is **parity flips**.

| $L$ | $\beta$ | start | $\beta L$ | $Q$ changes | **parity flips** | chains flipped | odd frac | exact | binomial $z$ | $\tau_{\rm int}(Q^2)$ |
|---|---|---|---|---|---|---|---|---|---|---|
| 8 | 6 | hot | 48 | 20304 | **12810** | 128/128 | 0.4983 | 0.4999 | $-1.77$ | 0.53 |
| 8 | 10 | cold | 80 | 7095 | **3560** | 128/128 | 0.4802 | 0.4854 | $-0.73$ | 0.57 |
| 8 | 10 | hot | 80 | 14296 | **7100** | 128/128 | 0.4895 | 0.4854 | $+0.51$ | 0.56 |
| 8 | 14 | hot | 112 | 6864 | **347** | 117/128 | 0.4041 | 0.4341 | $+0.26$ | 3.63 |
| 8 | 20 | cold | 160 | 204 | **1** | 1/128 | 0.0003 | 0.3335 | $-8.00$ | 0.55 |
| 8 | 20 | hot | 160 | 5862 | **4** | 3/128 | 0.4437 | 0.3335 | $+2.87$ | 1.46 |
| 16 | 14 | hot | 224 | 32169 | **2453** | 256/256 | 0.5006 | 0.5000 | $+0.50$ | 0.54 |
| 16 | 21 | hot | 336 | 26110 | **2** | 2/256 | 0.4842 | 0.4989 | $-0.34$ | 0.55 |
| 16 | 28 | cold | 448 | 9026 | **0** | 0/256 | 0.0000 | 0.4928 | $-15.77$ | 0.56 |
| 16 | 28 | hot | 448 | 22283 | **0** | 0/256 | 0.5195 | 0.4928 | $+0.85$ | 0.53 |

**Where the flip count is zero, the odd fraction is not a relaxing observable at all.** It is a label assigned to each chain once, during the hot-start ordering, and carried unchanged forever. The number of independent parity draws is then exactly $n_{\rm chains}$ however long anything runs; the error model is a binomial over chains; and the only lever that improves it is more chains. Longer burn-in does nothing, and more draws per chain do nothing.

That resolves a contradiction the study had been carrying. The stored base ensemble measured an odd excess of 13% at $z_{\rm odd} = +2.42$, $\chi^2/{\rm dof} = 2.41$ -- the PARITY-STUCK signature -- while a scan at the *identical* coupling measured 1.030 and $+0.69$, a clean SAMPLED verdict. Neither was wrong and neither was a bias: they are two draws of a 256-chain binomial that landed two sigma apart. A verdict computed from one such draw can pass or fail on luck, which is why a flip count is the better instrument.

**And this is the trap the theory sets.** $\tau_{\rm int}(Q^2)$ is around half a draw at every coupling in the table, including the ones where parity has not moved once. $Q^2$ fluctuates on the EVEN channel, which the central instanton keeps wide open at cost $2\pi^2\beta/V$ -- a ladder invariant that never degrades. It is nearly blind to the odd/even channel, which is shut. A fast autocorrelation time on a quantity blind to the frozen mode certifies an equilibrium that does not exist. Autocorrelate $Q \bmod 2$, or better, count flips.

**The controlling parameter is $\beta$, not $\beta L$, and the study had this wrong.** Read the flip column against $\beta L$ and it does not collapse: $L = 16$ at $\beta L = 224$ flips 2453 times while $L = 8$ at $\beta L = 160$ flips four. Read it against $\beta$ and it does: mobility dies between $\beta = 14$ and $\beta \approx 20$ at **both** volumes, with the per-site rate falling roughly a hundredfold across that interval. The earlier $\beta L \approx 450$-$830$ boundary in `CLAUDE.md` came from stage 07's *verdicts* rather than from flip counts, and it was fitted to the $L = 16$ points while the $L = 8$ points ($\beta L = 112$ sampled, $160$ stuck) contradict it outright. A verdict is a hypothesis test on one binomial draw; a flip count is the mechanism itself.

The consequence is uncomfortable and has to be stated: **the ladder base at $L = 16$, $\beta = 28$ is on the frozen side.** Zero flips in 256 chains over 2000 trajectories. Stage 07 calls it SAMPLED because its odd weight agrees with the closed form -- which is true, and is not the same claim.

### What actually sets the split, where parity is frozen

If the odd fraction were being sampled, the initial condition could not matter. Running the identical procedure from a cold start is therefore the direct test, and it is decisive.

| $L$ | $\beta$ | exact odd | hot start | cold start |
|---|---|---|---|---|
| 8 | 10 | 0.4854 | 0.4895 | 0.4802 |
| 8 | 20 | 0.3335 | 0.4437 | 0.0003 |
| 16 | 28 | 0.4928 | 0.5195 | 0.0000 |

### Where $P(Q)$ can be sampled rather than seeded

| $L$ | $\beta$ | $\beta/V$ | $\beta L$ | $\langle Q^2\rangle$ | exact | $z$ | $\chi^2$/dof | odd ratio | $z_{\rm odd}$ | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| 8 | 6 | 0.094 | 48 | $1.8799 \pm 0.0178$ | 1.8674 | $+0.70$ | 1.03 | 0.994 | $-0.67$ | SAMPLED |
| 8 | 8 | 0.125 | 64 | $1.1973 \pm 0.0120$ | 1.2007 | $-0.28$ | 0.89 | 0.994 | $-0.71$ | SAMPLED |
| 8 | 10 | 0.156 | 80 | $0.8533 \pm 0.0087$ | 0.8603 | $-0.80$ | 0.49 | 0.989 | $-0.98$ | SAMPLED |
| 8 | 12 | 0.188 | 96 | $0.6655 \pm 0.0105$ | 0.6707 | $-0.50$ | 0.88 | 0.999 | $-0.05$ | SAMPLED |
| 8 | 14 | 0.219 | 112 | $0.5547 \pm 0.0209$ | 0.5514 | $+0.16$ | 1.29 | 0.978 | $-0.51$ | SAMPLED |
| 8 | 20 | 0.312 | 160 | $0.5775 \pm 0.0426$ | 0.3551 | $+5.22$ | 22.45 | 1.694 | $+7.40$ | PARITY-STUCK |
| 16 | 28 | 0.109 | 448 | $1.0088 \pm 0.0110$ | 1.0012 | $+0.69$ | 0.27 | 1.030 | $+0.69$ | SAMPLED |
| 16 | 51.75 | 0.202 | 828 | $0.5746 \pm 0.0265$ | 0.5211 | $+2.02$ | 2.89 | 1.152 | $+2.89$ | PARITY-STUCK |
| 16 | 56 | 0.219 | 896 | $0.5331 \pm 0.0274$ | 0.4793 | $+1.96$ | 2.72 | 1.152 | $+2.82$ | PARITY-STUCK |
| 32 | 203.15 | 0.198 | 6501 | $0.4323 \pm 0.0505$ | 0.5150 | $-1.64$ | 1.79 | 0.778 | $-2.22$ | PARITY-STUCK |

<!-- END GENERATED RESULTS -->

---

## Part V — Tooling and implementation

### 17. The scripts, and what each is for

| script | purpose |
|---|---|
| `01_generate_data.py` | HMC ensembles per rung; sharded, thermalizes with heat bath + overrelaxation before HMC |
| `02_train.py` | denoising score matching on the determinant sector |
| `03_run_ladder.py` | climbs the ladder; per-rung save and prefix resume |
| `04_validate.py` | observables vs HMC reference and closed form; validates only configured rungs |
| `05_topology_study.py` | winding economics, freezing, sector histograms |
| `06_figures.py` | density, sectors, area law, matching, ladder drift |
| `07_pq_sampling.py` | **where $P(Q)$ can be sampled rather than seeded** |
| `08_hmc_seed_benchmark.py` | **is a generated configuration a good HMC seed?** four arms |
| `09_verify_identities.py` | the exact identities; seconds, must pass |
| `10_paper_figures.py` | the result figures |
| `11_wilson_distributions.py` | per-configuration Wilson spread, generated vs HMC |
| `12_results_section.py` | regenerates Part IV from the JSON each stage wrote |
| `13_cost_comparison.py` | seconds per independent configuration, both arms |
| `14_sampler_steps.py` | the sampler step count as a cost/accuracy dial |
| `15_base_parity.py` | **parity FLIPS** — does the odd/even channel move at all |
| `16_cost_figures.py` | draws 13 and 14: cost beside reachability, and the sampler dial |

### 18. Statistical methods

**Chain bootstrap.** Above the freezing threshold the number of independent
topological charges is the number of *chains*, not configurations. Quoting a naive
standard error over configurations understates the uncertainty by
$\sqrt{n_{\rm draws}}$ and manufactures fake discrepancies. Every topological error
bar here resamples whole chains with replacement, which degrades gracefully to
exactly that limit.

**Count the rare event; do not infer it from a test on the aggregate.** The single
most expensive methodological mistake in this study was using stage 07's
PARITY-STUCK *verdict* as the measure of odd-charge mobility. A verdict is a
hypothesis test on the odd weight computed from one binomial draw over chains, and
it passes whenever that draw lands near the truth — including when the mobility is
exactly zero, which is what happens at the ladder base. It produced a fitted
$\beta L$ boundary that the $L = 8$ data contradicts, and then a second, spurious
$\beta/V$ axis invented to explain the contradiction away. Counting parity *flips*
(§12.1) collapsed both onto a single $\beta$ axis and cost twenty minutes of
compute. When the question is whether a channel is open, count events in that
channel; a summary statistic downstream of it will be dominated by whatever else
is open.

**Autocorrelate the slow mode, not a proxy for it.** $\tau_{\rm int}(Q^2)$ reads
$\approx 0.55$ draws at every coupling measured, *including* those with zero parity
flips, because $Q^2$ lives on the even channel that stays open. A short
autocorrelation time on a quantity blind to the frozen mode is not weak evidence of
equilibrium — it is systematically misleading, and in this theory it points the
wrong way exactly where it matters most.

**A trap worth recording.** An earlier version of the sector test floored the
per-sector error at the binomial value for $n_{\rm chains}$, intending to stop a
frozen ensemble from looking precise. But the bootstrap already handles that, and
in the *tunnelling* regime the floor dominates the real error and inflates every
bar until $\chi^2$ cannot fail — it scored $0.00$ on data carrying a 22% sector
deficit. The bootstrap alone is the correct error model.

**The parity statistic.** A sector-by-sector $\chi^2$ cannot see the $\mathbb{Z}_2$
obstruction, because the signature is a *coherent* deficit spread across every odd
sector — each within $1\sigma$, jointly far outside. The total odd-sector weight,
with errors added in quadrature, is the diagnostic that works.

**Integrated autocorrelation.** Sokal automatic windowing, summing $\rho$ until the
window reaches $c\tau$ with $c = 5$. Chains with zero variance are *dropped* rather
than counted as $\tau = 1$, which would claim independence for exactly the chains
that have none.

### 19. Engineering notes that cost real time to learn

* **Device rule.** U(2)'s GPU/CPU crossover is $L = 16$, not $L = 64$ as in U(1),
  because a quaternion link carries ~6× the arithmetic of an angle. GPU throughput
  is flat at ~5 trajectories/s from $L = 16$ to $L = 64$ — purely launch-bound — so
  large lattices are nearly free on the GPU.
* **`empty_cache()` allocates.** An OOM handler that calls it can re-raise the very
  error it is handling. Cleanup must be best-effort.
* **`AcceleratorError` is not `OutOfMemoryError`.** A raw
  `cudaErrorMemoryAllocation` surfaces as a different class that does not subclass
  the allocator's exception, so catching only the latter silently misses it. The
  driver reports asynchronously, so the frame it lands on is unrelated to the
  allocation that failed; the message is the only reliable discriminator.
* **PowerShell 5.1 destroys tracebacks.** `& python ... *>&1 | Tee-Object` wraps
  every native stderr line in a `NativeCommandError` and discarded the body of a
  real traceback, keeping only the words "Traceback (most recent call last):".
  Redirect stdout and stderr to separate files.
* **Renamed rungs orphan, they do not replace.** Stage 03 writes ensembles by name,
  so changing the $\beta$ schedule leaves the previous schedule's files behind, and
  any glob-based consumer then reports stale results as current.

---

## Part VI — Presentation: what to show, and how

*Requested explicitly. This section is about the write-up, not the physics.*

### 20. The three claims, in the order they should be made

The study supports three claims of decreasing strength, and conflating them is the
main presentational risk.

1. **A generated configuration is an equilibrium HMC starting point.** Strongest,
   cheapest to verify, and the one a practitioner cares about. Show it as a
   relaxation curve against cold/hot controls with the $2\tau_{\rm int}$ yardstick
   marked — the controls are what give the plot dynamic range, so never drop them.
   Note carefully that this is a claim about the *starting point*, not throughput:
   generating that configuration costs more than continuing a chain would, so the
   claim is "no burn-in to pay", not "cheaper". And do **not** quote the seed's
   $t = 0$ error as a ratio against the cold start. With 64 configurations the
   sampling floor on that number is $\sim 7\times10^{-6}$ and the seed sits at
   $8.2\times10^{-6}$, i.e. on the floor; an earlier run happened to measure
   $7.8\times10^{-7}$ and a "6200x better" figure was quoted off it, which was
   measuring noise. The defensible statement is that the seed is at equilibrium to
   within the resolution the ensemble can offer, and the cold start is three orders
   of magnitude away.
2. **The ladder reaches topological sectors no local algorithm can.** This is the
   U(2)-specific contribution. Show it as *sector coverage weighted by exact
   $P(Q)$*, never as a count of sectors visited: a hot start visits many sectors
   and covers little, because it visits the wrong ones.
3. **The generated density is close to the target.** Weakest, and it should be
   stated with the U(1) caveat attached: observable agreement does not constrain
   the density. Report per-configuration *spread*, not just means.

### 21. Figures that earn their place

| figure | shows | why this form |
|---|---|---|
| seed quality | plaquette relative error vs trajectory, 4 arms, log $y$ | a log axis is mandatory — the arms differ by 3 orders of magnitude at $t = 0$, and a linear axis hides the entire result |
| topological reach | sectors occupied and $\langle Q^2\rangle$ vs trajectory | two panels because "how many" and "weighted how much" are different claims |
| parity mobility | parity **flips** per chain-trajectory vs $\beta$, beside $Q$-changes over the same range | the left panel falls five orders of magnitude where the right one falls four*fold* — that side-by-side is the whole two-mechanism story, and it is why a sector-change count cannot serve as an ergodicity test. Replaces an earlier version plotting stage-07 verdicts in the $(\beta L, \beta/V)$ plane, which encoded two mistakes at once |
| winding economics | forced $\Delta S$ for even vs odd, and after SU(2) sweeps | the three-bar grouping is the argument: free, blocked, recovered |
| Wilson spread | per-configuration histograms with $\sigma$ in the legend | means agree to $10^{-6}$; only the width is informative |
| ladder accuracy | pre- and post-rethermalization side by side | keeps "what the model earned" separable from "what the sweeps repaired" |
| area-law ratio | $W(A)/W(1)^A$ for generated **and** reference | the reference curve is not decoration — without it a reader concludes model error from what is finite volume; at $L=32$ the reference is the worse of the two |
| cost and reach | seconds per independent configuration beside the fraction of exact $P(Q)$ covered, same five bars | the two must sit side by side and must never be collapsed into one number. Alone, panel (a) says the ladder loses; alone, panel (b) says it wins. The honest claim is only visible as a pair, and the odd-sector count printed inside each bar is what stops a reader crediting the hot arm's $1.000$ coverage |
| sampler dial | top-rung cost ratio and **pre-rethermalization** error vs reverse-diffusion steps | answers "then tune it" with a measurement rather than a promise: about a factor of three, purchased not free. The post-rethermalization plaquette is drawn dashed and demoted deliberately — it stays flat past the point where the model stopped working, so it is the wrong accuracy axis, and $\langle Q^2\rangle$ is not an accuracy axis at all because `apply_coarse_charge` imposes it |

The first seven are `u2_2d/scripts/10_paper_figures.py` (`fig06`–`fig12`); the
last two are `u2_2d/scripts/16_cost_figures.py` (`fig13_cost.png`,
`fig14_sampler_steps.png`, added 2026-08-20). Before that the cost answer and the
sampler-tuning answer existed only as tables in §23 and Part IV, which is exactly
the presentation failure §22 warns about — the two claims a referee reaches for
first were the two with no figure.

### 22. Specific presentational improvements over the U(1) write-up

The U(1) appendix is thorough but has three habits worth not repeating:

* **Tables of $z$ against a reference whose own error is underestimated.** The U(1)
  reports quote $z$ against an HMC reference with a naive standard error and no
  $\tau_{\rm int}$ correction. In this study that produced a spurious $-3.26\sigma$
  on `det_plaquette` where the generated ensemble was in fact *closer to exact*
  than the reference was. **Lead with $z$ against the closed form**; show $z$ vs
  reference only where no closed form exists, and say the error is uncorrected.
* **Seeded quantities presented alongside sampled ones without a marker.** Every
  table row whose $P(Q)$ was installed rather than measured should say so in the
  row, not in a footnote three sections away. This study had exactly that failure
  mode internally — a $\langle Q^2\rangle$ from a seeded ensemble read as evidence
  of sampling.
* **Aggregate verdicts that hide their denominator.** A $\chi^2$ that cannot fail
  is worse than no test. State the error model next to every aggregate statistic.

Two things this study does that the U(1) one did not, and which should survive
into the paper:

* **Report the mechanism, not a verdict.** "Frozen at $\beta = X$" is incomplete
  in U(2): the even and odd channels close in different places, and the even one
  never closes along a matched ladder at all. Give the parity flip rate and the
  sector-change rate side by side. A single ergodicity verdict — including this
  study's own PARITY-STUCK — hides which channel is open, and can pass with zero
  odd-charge mobility.
* **Show the pre-rethermalization observable.** It is the only thing separating a
  good model from a good local-update repair, and it costs one extra column.

### 23. What a referee will attack first

* ***"There is nothing non-abelian being learned here."*** — **The most important
  editorial decision in the U(2) study, and it has to be met head-on in the
  abstract rather than defended in a late section.** The objection is factually
  correct as stated: the score network sees only $\psi$, an honest compact U(1)
  field, and the SU(2) sector has zero learned parameters (§6). A reader who
  arrives expecting "a diffusion model for a non-abelian gauge theory" will look
  for a learned non-abelian degree of freedom and not find one.

  Do not answer it by pointing at the group. Answer it with the factorization,
  in this order.

  1. **The split is exact, not an approximation.** $p(\psi, q) = p(\psi)\,p(q\mid\psi)$
     is an identity, and at frozen $\phi$ the conditional is the standard SU(2)
     heat-bath form $\exp(\beta k\cdot q)$ — so `conditional_su2_sweeps` samples
     it *exactly*, leaving $\psi$ and $Q$ bit-for-bit unchanged. Nothing is
     approximated away, and the naive-inverse-blocking seed cannot bias anything.
  2. **Therefore learning SU(2) would be strictly wasted capacity.** There is no
     accuracy to be bought: an exact sampler cannot be improved on. A paper that
     learned it anyway would be spending parameters to approximate something it
     already has in closed form, and would have to explain why.
  3. **The non-abelian content is in what the split does NOT remove**, and that
     is where the study's actual contributions live. The joint does not
     factorize as a product of marginals (§6): $\tfrac12\mathrm{ReTr}P =
     \cos\omega_P\cos\phi_P$, so the SU(2) sector must be generated
     *conditionally* and $\psi$'s own marginal is **not** U(1) Wilson at
     $\beta/4$ but $w_{\rm det}(\alpha) = 2I_1(z)/z$ (§7) — a 23% coupling
     difference at $\beta = 4$. And the $\mathbb{Z}_2$ obstruction (Part II) is
     purely non-abelian: $U(2) = (U(1)\times SU(2))/\mathbb{Z}_2$ is what makes
     odd-charge winding cost $O(\beta L)$ while even-charge winding is free, and
     that two-mechanism freezing structure has no U(1) analogue at all.
  4. **The density-gap statement is stronger here than in U(1) *because* of the
     split, and it is worth saying so.** Since the conditional is the same
     distribution on both sides of the KL, it cancels identically:
     $\mathrm{KL}(m(\psi)p(q|\psi)\,\|\,p(\psi)p(q|\psi)) = \mathrm{KL}(m(\psi)\,\|\,p(\psi))$.
     The determinant sector's density gap **is** the whole pipeline's density
     gap, with no inequality and no residual term — a claim `u1_2d` could not
     make about any of its sectors (§16.5, `scripts/18_density_gap.py`).

  What to concede, in one sentence and without hedging: *this construction is
  specific to groups whose topology lives in an abelian factor, and it does not
  by itself tell you how to lift SU(3), where no such split exists.* That is the
  honest scope, and it is the right lead-in to the outlook section. Claiming
  otherwise is the one thing that would make the objection fatal instead of
  answerable.

* *"Your $P(Q)$ agreement is circular."* — Answer, and it has to be given in two
  halves (§12.2). The sector shape *within* a parity class is genuinely sampled at
  the base: 106823 $Q$ changes, $\chi^2/{\rm dof} = 1.53$, nothing seeded. The
  odd/even weight is *not* sampled — it is frozen in at ordering, one draw per
  chain — and it is right to $0.45\sigma$ because $P({\rm odd})$ is within $1.5\%$
  of $1/2$ whenever $\langle Q^2\rangle \gtrsim 1$, which the base satisfies. Say
  that rather than claiming the base samples topology outright; the referee who
  checks will find the zero flip count, and it is better to have got there first.
  The seeded rungs are training data and references that topology never flows
  through.
* *"You only reach sectors because you put them there."* — Answer: correct, and
  that is the mechanism. The claim is that the base is a coupling where the charge
  distribution is available and the top is one where it provably is not:
  $\beta = 28$ against $\beta = 416.5$, with odd-charge mobility dying at
  $\beta \approx 15$–$20$, so the top rung is more than twenty times past the edge.
* *"Observable agreement does not mean the density is right."* — Correct, and
  conceded in the U(1) study. Hence the spread comparison, and hence the honest
  framing of claim 3 as the weakest. The strongest available answer is the $L = 64$
  spread against a direct HMC reference: within $3$–$8\%$ at every loop size, with
  no growth in loop area — which is exactly the test U(1) failed.
* *"Your large-loop deviation looks like model error."* — It was, until it was
  controlled. The same-size HMC reference deviates comparably (mean
  $9.9\times10^{-4}$ against $1.13\times10^{-3}$ over areas $\ge 48$), and
  re-drawing the base **flipped the sign** of the trend from $+1.70\sigma$ to
  $-2.43\sigma$ with everything else held fixed. Smooth and monotonic in $A$ is
  what one fluctuation looks like when the observables are all functionals of the
  same field.
* *"What does it cost?"* — **Measured, and the answer is unflattering: for local
  observables the ladder is 3.68x SLOWER than HMC + winding** (0.780 s versus
  0.212 s per independent configuration at $L = 64$). Do not lead with speed. The
  cost is dominated by the 200-step diffusion sampler, and the natural follow-up,
  *"then tune it"*, was run: it is worth about a factor of three, purchased rather
  than free. At 25 steps the top rung becomes 1.38x *faster* than HMC + winding, at
  $\sim2.7\times$ the extended-loop error and no measurable change in local
  observables after rethermalization; below 18 steps the lift collapses. So quote
  3.68x as the cost of the accuracy-of-record setting and say the dial exists.
  Beyond that the remaining cost is the exact conditional SU(2) sampler, which no
  sampler tuning touches. The method earns its place on *reachability*, not
  throughput, and the write-up must say so in those words: quoting a speed-up
  against an arm that never reaches the odd sectors would be comparing against a
  chain that samples the wrong distribution.
