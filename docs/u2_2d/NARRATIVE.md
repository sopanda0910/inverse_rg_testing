# 2D U(2) Inverse RG: Narrative, Mathematics, and Measurements

*The complete story of the 2D U(2) study — what it is, why it is built the way it
is, every derivation that carries weight, and every number that has been measured.
Written to be read without prior lattice background but without softening the
mathematics. Companion to `DESIGN.md` (derivations in condensed form) and to
`docs/u1_2d/NARRATIVE.md` (the closed U(1) predecessor).*

Last updated: 2026-08-19.

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
and odd ones cost $O(\beta L)$, which splits the classical freezing problem into
two mechanisms with different scaling — and only one of them is protected by the
ladder. The measured advantage is **reachability, not speed**: for local
observables the ladder is currently several times more expensive than HMC with a
winding update, while for topology the classical arm covers only half the exact
$P(Q)$ and cannot improve on that at any cost.

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
| odd $\Delta Q$ (crosses $\mathbb{Z}_2$) | $O(\beta L)$ | $\beta L$ | grows as $L^3$ |

Along a matched ladder $\beta_f = 4\beta_c$, $L_f = 2L_c$, so $\beta/V$ is
constant — the even-charge move never gets harder — while $\beta L$ grows by $8$
per rung. Measured on this ladder:

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
1.15) and one a *deficit* (0.78). The $O(\beta L)$ barrier blocks the
odd$\leftrightarrow$even channel in **both** directions, so the parity balance
simply keeps whatever the initial condition gave it: these runs start hot, which
strands excess odd weight, while a *cold* start reaches **no odd sectors at all**
(measured — see the seed benchmark, arm D). "Depletion" is the special case, not
the rule; the test is on $|z_{\rm odd}|$, and the verdict is named
PARITY-**STUCK** rather than PARITY-FROZEN for exactly that reason.

Two boundaries are visible and they are different:

* **Parity boundary at $\beta L \approx 450$–$830$**, bracketed by $16/28$ (clean)
  and $16/51.75$ (stuck). Sharp, and invisible to the usual diagnostic: every stuck
  case still shows 13000–22000 sector changes and *zero* frozen chains.
* **Thermalization boundary at $\beta/V \approx 0.25$.** The $L = 8$, $\beta = 20$
  case sits at $\beta L = 160$, far *below* the parity boundary, and is stuck
  anyway — it fails on the other axis. A hot start there cannot relax *down* (17%
  of chains stranded, $\langle Q^2\rangle$ 63% high); a cold start cannot climb up.

These are genuinely two axes, which is why the regime figure is drawn in the
$(\beta L,\ \beta/V)$ plane rather than against $\beta$. **Any statement of the
form "frozen at $\beta = X$" is incomplete in U(2)** — it needs both.

The practical upshot: **the ladder base can be placed where $P(Q)$ is genuinely
sampled**, and transport then carries an honestly-sampled distribution into the
parity-stuck regime where no local algorithm could produce it. That converts the
study's weakest claim ("$P(Q)$ is exact by construction, so it is not evidence")
into its strongest.

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
form beyond the one already verified. At $L = 64$ the generated ensemble departs
from 1 monotonically, reaching $1.00545$ at $A = 144$, with $z$ against the exact
result rising smoothly from $-2.13$ at $A = 1$ to $+1.70$ at $A = 144$
(correlation between $\log A$ and $z$: $+0.972$).

It is tempting to call that model error. **It is not established, and the control
says so.** At $L = 32$, where an HMC reference exists, the *reference* departs
from 1 by more than the generated ensemble does — $0.9785$ against $0.9998$ at
$A = 120$ — because a $12\times12$ loop covers 14% of a $32^2$ torus while the
exact form used here is the infinite-volume one, and because large loops carry
the largest variance. At $L = 64$ the geometry is much safer ($A/V = 0.035$) but
there is no same-size reference, and the largest-loop deviation is about
$2\sigma$.

So the honest statement is: *the generated ensemble shows a smooth, monotonic
area-law excess at $L = 64$ of order half a percent at the largest loop, which is
consistent with weak positive plaquette correlation the target theory does not
have, and which is currently uncontrolled.* Settling it needs an HMC reference at
$L = 64$, $\beta = 416.524$ — expensive, but the only thing that converts this
from a suggestive trend into a measurement.

## Part IV — Measurements

<!-- BEGIN GENERATED RESULTS -->

*Generated by `scripts/12_results_section.py` from the JSON each stage wrote; do not edit by hand.*

### Ladder: observables against the closed form

| $L$ | $\beta$ | $\langle P\rangle$ | exact | rel. err | pre-retherm | $\langle Q^2\rangle$ | exact |
|---|---|---|---|---|---|---|---|
| 32 | 105.651 | 0.981029 | 0.981023 | $+5.72e-06$ | 0.981123 | 1.0273 | 1.0012 |
| 64 | 416.524 | 0.995191 | 0.995195 | $-4.97e-06$ | 0.995263 | 1.0273 | 1.0012 |

The pre-rethermalization column is the one that separates model quality from local-update repair: where it already matches, the diffusion lift earned the agreement unaided.

### Validation against HMC and the closed form

| $L$ | $\beta$ | plaquette $z$ vs exact | max Wilson $z$ vs ref | mean | reference |
|---|---|---|---|---|---|
| 32 | 105.651 | $+0.31$ | 1.46 | 0.94 | stage-01 ensemble |
| 64 | 416.524 | $-2.13$ | - | - | exact only (no HMC reference) |

Read the *exact* column. A $z$ against the HMC reference carries that reference's own uncorrelated-sample assumption, which is not true of a Markov chain; this study measured a spurious $-3.26\sigma$ that way while the generated ensemble was in fact closer to exact than the reference was.

### Seed quality and topological reach

$L = 64$, $\beta = 416.524$, 64 chains, 300 trajectories per arm.

| arm | $|\Delta P/P|$ at $t=0$ | at $t=T$ | $\langle Q^2\rangle$ | sectors | $P(Q)$ covered | odd sectors |
|---|---|---|---|---|---|---|
| **A** diffusion seed | $7.81e-07$ | $1.85e-06$ | 0.922 | 5 | 0.991 | 2 |
| B cold start | $4.83e-03$ | $4.30e-05$ | 0.000 | 1 | 0.399 | 0 |
| C hot start | $1.00e+00$ | $6.24e-02$ | 109.370 | 51 | 1.000 | 25 |
| D cold + winding | $4.83e-03$ | $5.18e-05$ | 0.856 | 3 | 0.507 | 0 |

Exact $\langle Q^2\rangle = 1.0012$. The independent-configuration interval for a plain chain is $2\tau_{\rm int} = 1.6$ trajectories.

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
| W 1x1 | 4.130e-04 | 4.219e-04 | 0.979 |
| W 2x2 | 2.432e-03 | 2.455e-03 | 0.991 |
| W 4x4 | 1.341e-02 | 1.415e-02 | 0.947 |
| W 8x8 | 4.881e-02 | 5.002e-02 | 0.976 |

### Cost per independent configuration

$L = 64$, $\beta = 416.524$, 64 chains. For a Markov chain the cost is $2\tau_{\rm int}\,t_{\rm traj}/n_{\rm chains}$, with $\tau_{\rm int}$ measured on the equilibrated tail only.

| arm | $\tau_{\rm int}(P)$ | s / trajectory | **s / independent config** |
|---|---|---|---|
| A diffusion seed | 3.6 | 0.852 | **0.0955** |
| B cold start | 16.9 | 0.895 | **0.4724** |
| C hot start | nan | 0.929 | - |
| D cold plus winding | 8.0 | 0.851 | **0.2122** |

Ladder: **0.8203 s** per configuration including base generation, **0.4805 s** for the top rung alone.

**For local observables the ladder is 3.87x SLOWER than HMC + winding.** That is the honest headline and it should not be buried: this method is not a speed-up for the plaquette or small Wilson loops, and the cost is dominated by the 200-step diffusion sampler, which is tunable but has not been tuned.

**The topological claim is reachability, not speed.** The classical arm covers 0.507 of the exact $P(Q)$ with zero odd sectors and cannot improve on that at any cost, because odd charge has probability *zero* in its stationary distribution rather than merely long autocorrelation. A ratio of seconds against an arm that never arrives is meaningless, so the two claims must be stated separately.

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

### 18. Statistical methods

**Chain bootstrap.** Above the freezing threshold the number of independent
topological charges is the number of *chains*, not configurations. Quoting a naive
standard error over configurations understates the uncertainty by
$\sqrt{n_{\rm draws}}$ and manufactures fake discrepancies. Every topological error
bar here resamples whole chains with replacement, which degrades gracefully to
exactly that limit.

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
   claim is "no burn-in to pay", not "cheaper".
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
| sampling regimes | verdicts in the $(\beta L, \beta/V)$ plane | this is the only figure that makes the *two* freezing mechanisms visible at once; a single-axis $\beta$ plot cannot |
| winding economics | forced $\Delta S$ for even vs odd, and after SU(2) sweeps | the three-bar grouping is the argument: free, blocked, recovered |
| Wilson spread | per-configuration histograms with $\sigma$ in the legend | means agree to $10^{-6}$; only the width is informative |
| ladder accuracy | pre- and post-rethermalization side by side | keeps "what the model earned" separable from "what the sweeps repaired" |
| area-law ratio | $W(A)/W(1)^A$ for generated **and** reference | the reference curve is not decoration — without it a reader concludes model error from what is finite volume; at $L=32$ the reference is the worse of the two |

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

* **Report both freezing parameters.** Any statement of the form "frozen at
  $\beta = X$" is incomplete in U(2); it needs $\beta/V$ *and* $\beta L$.
* **Show the pre-rethermalization observable.** It is the only thing separating a
  good model from a good local-update repair, and it costs one extra column.

### 23. What a referee will attack first

* *"Your $P(Q)$ agreement is circular."* — Answer: at the base it is sampled, not
  seeded, with the scan in §12 as evidence, and the seeded rungs are training data
  and references that topology never flows through.
* *"You only reach sectors because you put them there."* — Answer: correct, and
  that is the mechanism. The claim is that the base is a coupling where sampling
  works and the top is one where it provably does not, with $\beta L$ separating
  them by a factor of 100.
* *"Observable agreement does not mean the density is right."* — Correct, and
  conceded in the U(1) study. Hence the spread comparison, and hence the honest
  framing of claim 3 as the weakest.
* *"What does it cost?"* — **Measured, and the answer is unflattering: for local
  observables the ladder is 3.87x SLOWER than HMC + winding** (0.820 s versus
  0.212 s per independent configuration at $L = 64$). Do not lead with speed. The
  cost is dominated by the 200-step diffusion sampler, a tunable that has not been
  tuned, so the number can move — but as it stands the method earns its place on
  *reachability*, not throughput, and the write-up must say so in those words.
  Quoting a speed-up against an arm that never reaches the odd sectors would be
  comparing against a chain that samples the wrong distribution.
