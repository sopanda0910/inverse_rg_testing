# Global topological moves in 2D U(1) and 2D U(2)

One document for both theories: how the instanton update is built, why the U(1)
construction is optimal, why halving it for U(2) fails, and the fix that makes
odd-charge moves cheap. Every number here is measured, and the script that
produced it is named.

**Read this before quoting any claim about topological freezing or
reachability.** The measurements in §5 retire a claim that appears throughout the
U(2) write-up.

---

## 1. What the move has to do

A topological sector is a property of the whole configuration, so no local update
can change it: `Q` is an integer functional, and a continuous local deformation
cannot move an integer. As $\beta$ grows the action barrier between sectors grows
with it, and an ordinary HMC chain stops changing `Q` entirely — *topological
freezing*. Since $\langle Q^2 \rangle$ and every quantity depending on the sector
distribution then come out wrong, a correct sampler needs a **global** move that
jumps between sectors in one step and is accepted often enough to matter.

The move must be:

* **exact** — a Metropolis proposal with a valid acceptance, not a heuristic;
* **symmetric and involutive**, so acceptance is $\min(1, e^{-\Delta S})$ with no
  Jacobian to track;
* **cheap**, meaning $\Delta S = O(1)$ at the couplings of interest, not
  $O(\beta)$.

---

## 2. U(1): the construction, and why it is optimal

### 2.1 The field

`u1_2d.lgt.local_updates.instanton_field` builds a smooth $Q = +1$ configuration:

$$\theta_y(x, y) = \frac{2\pi x}{L^2}, \qquad
  \theta_x(L-1, y) = -\frac{2\pi y}{L}$$

Every plaquette angle equals $2\pi / L^2$. `topological_update` adds $\pm$ this
field to a configuration and applies a Metropolis test.

### 2.2 Why the second line is not cosmetic

The raw alternating sum of plaquette angles telescopes to **zero identically** —
each link enters two plaquettes with opposite sign. A configuration whose
*wrapped* plaquettes sum to $2\pi$ must therefore have at least one plaquette
whose raw angle differs from its wrapped one. In this construction exactly one
does: the corner, at $2\pi/L^2 - 2\pi$.

**That corner is invisible to the action.** The U(1) action depends on the
plaquette only through $\cos\theta_p$, which is $2\pi$-periodic, so
$\cos(2\pi/L^2 - 2\pi) = \cos(2\pi/L^2)$. Measured directly — `plaquette_angles`
wraps internally, so every plaquette reads exactly $2\pi/L^2$:

| $L$ | $Q$ | plaquettes off-uniform | $\max\lvert\cos\theta_p - \cos(2\pi/V)\rvert$ |
|---|---|---|---|
| 8 | +1.0 | 0 | $5.96\times10^{-8}$ |
| 16 | +1.0 | 0 | 0 |
| 32 | +1.0 | 0 | 0 |

### 2.3 Cost, and optimality

With every plaquette carrying the same flux,

$$\Delta S \;=\; \tfrac12 \beta \sum_p \left(\frac{2\pi}{V}\right)^{2}
           \;=\; \frac{2\pi^{2}\beta}{V}.$$

Uniform flux is the **minimum-action** winding-1 configuration for the Wilson
action, by convexity of $-\cos$ on $(-\pi, \pi]$ subject to a fixed total flux. So
$2\pi^2\beta/V$ is a floor: no fixed shift field with $\Delta Q = 1$ can cost
less. The controlling parameter is $\beta / V$, which a matched RG ladder holds
nearly constant — which is why the move keeps working at every rung.

**The U(1) instanton needs no repair.** It is not merely adequate; it is optimal.

---

## 3. U(2): why the same field only gives $\Delta Q = 2$

### 3.1 The factor of two

In the NTHMC-compatible split representation $U = e^{i\phi} q$ with $q \in SU(2)$,

$$\det U = e^{2i\phi} \quad\Longrightarrow\quad \psi \;\equiv\; \arg\det U \;=\; \mathrm{wrap}(2\phi),$$

and `Q` is the winding of $\psi$. A purely **central** shift
$\phi \to \phi + \lambda$ therefore moves $\psi$ by $2\lambda$ and `Q` by **two**.

That is `central_winding_field`. It commutes with everything, costs
$2\pi^2\beta_{\rm det}/V$ exactly as in U(1), and is the default
(`winding_update(charge_step=2)`). Even-charge mobility is a ladder invariant and
never degrades.

### 3.2 Halving, and the plaquette that flips sign

For $\Delta Q = 1$ the shift must be $\lambda/2$. Every plaquette then picks up
$\pi/V$, which is harmless — except the corner, which goes to

$$\phi_p = \frac{\pi}{V} - \pi \quad\Longrightarrow\quad \cos\phi_p \approx -1 .$$

The U(2) plaquette is $\tfrac12\mathrm{ReTr}\,P = q^0_p \cos\phi_p$, so that single
plaquette flips sign and the joint action pays $\approx 2\beta$ **on one
plaquette**.

**This is the whole difficulty, and it is exactly the $\mathbb{Z}_2$ of
$U(2) = (U(1)\times SU(2))/\mathbb{Z}_2$.** U(1) survives its corner because
$\cos$ is $2\pi$-periodic; U(2) does not, because its action sees
$\cos(\psi_p/2)$ and a $2\pi$ shift in $\psi$ is a $\pi$ shift in $\phi$, which
flips the sign rather than restoring it.

The obvious repair — flip $q^0_p$ at the same corner so the two sign flips cancel
— is blocked: $\mathbb{Z}_2$ curvature always has an **even** number of $-1$
plaquettes, so no single plaquette can be flipped alone.

### 3.3 The two published constructions are the same construction

`winding_field(charge=1)` uses the $U(1)_T$ subgroup element $\exp(i\lambda T)$
with $T = (I + n\cdot\sigma)/2$. Written out,

$$\exp(i\lambda T) = e^{i\lambda/2}\exp\!\left(i\tfrac{\lambda}{2} n\cdot\sigma\right)
  = \mathrm{diag}\!\left(e^{i\lambda},\, 1\right),$$

which is precisely *"half-instanton on $\phi$ **and** the matching half-instanton
on SU(2) about a fixed axis"*. The SU(2) half carries $\cos(\lambda_p/2)$,
negative at the same corner where $\cos\phi_p$ is — so **on a cold background the
two $-1$s cancel plaquette by plaquette and the move is free.**
`23_odd_instanton.py` builds both forms independently and they return
byte-identical joint costs, confirming the identity.

What ruins it is the thermalized background: a **fixed** colour axis $n$ does not
commute with the local SU(2) field, so a cancellation that is exact on an ordered
configuration is destroyed on a real one. That, not topology, is the origin of the
measured $O(\beta L)$.

### 3.4 Measured joint cost

`u2_2d/scripts/23_odd_instanton.py`, 32 configurations per case:

| construction | $\lvert\Delta Q\rvert$ | $\Delta S$ joint, $L{=}8,\beta{=}14$ | $L{=}16,\beta{=}28$ |
|---|---|---|---|
| `central_2` (even, reference) | 2.000 | 3.50 | 2.08 |
| `half_central` | 1.000 | 24.01 | 52.61 |
| `u1_t` | 1.000 | 77.79 | 278.08 |
| `spread_twist` | 1.000 | 77.79 | 278.08 |

All three odd constructions achieve $\lvert\Delta Q\rvert = 1$ **exactly**. All
three are unaffordable as joint proposals.

---

## 3.5 What was already available, and what was actually missing

The first question a reader should ask is: if setting $\psi$'s winding already
moves `Q` by one, why is any of this needed? Measured, on a real $L=16$,
$\beta=28$ ensemble:

| check | result |
|---|---|
| `Q(links) == Q(psi)` | **True** |
| `apply_coarse_charge(+1)` then reassemble: $\Delta Q$ | **exactly $+1$, every config** |
| parity actually flipped | **True, every config** |

So odd transport was trivially available all along, and the diffusion lift has
always used it. **Moving `Q` was never the difficulty.** The three constructions
in §3.4 all achieve $\lvert\Delta Q\rvert = 1$ exactly; what they cannot do is
get *accepted*.

The distinction is between two different operations that both "change the
sector":

| | the lift (`lift_determinant`) | the chain move (`winding_update`) |
|---|---|---|
| what it does | **constructs** links from a given $\psi$ | **modifies** an existing thermalized configuration |
| SU(2) sector | built fresh, then equilibrated at frozen $\psi$ | already exists and must be preserved |
| acceptance | none — this is generation, not sampling | Metropolis, must satisfy detailed balance |
| odd-charge cost | free | $2\beta$ on the corner plaquette |

The lift pays nothing because it has no pre-existing SU(2) sector to contradict;
it builds one to match whatever $\psi$ it is handed. A chain move has one, and
the corner plaquette that flips sign is precisely what that sector cannot
accommodate. In a real chain the deployed odd move records **acceptance 0.000 and
zero parity flips** (§5) despite proposing a correct $\Delta Q = \pm 1$ every
step.

**So the missing piece was never a topological move — it was a valid acceptance
criterion.** Both ingredients already existed in the codebase ($\psi$-level charge
setting, and an exact conditional SU(2) sampler); `set_topological_charge`
combines them but is not an MCMC move, so the code could *construct* odd sectors
and could not *sample* them. What §4 adds is the accept/reject that joins them:
use the exact $\psi$-marginal, so the cost borne by an SU(2) sector that is about
to be discarded never enters the acceptance.

---

## 4. The fix: propose in the marginal, resample the conditional

### 4.1 Why there is a marginal to propose in

In two dimensions the SU(2) sector integrates out **exactly, plaquette by
plaquette**, giving the closed-form $\psi$-marginal
$w_{\rm det}(\alpha) = 2 I_1(z)/z$ with $z = \beta\cos(\alpha/2)$
(`u2_2d.lgt.actions.DetSectorAction`). This is a genuine 2D solvability
statement, not a general algorithm — see §6.

### 4.2 The move

1. **Propose** $\psi' = \psi \pm \lambda$ with $\lambda$ the winding-1 U(1)
   instanton. On links this is a pure phase multiply $U \to e^{\pm i\lambda/2} U$:
   $\phi$ shifts by $\pm\lambda/2$, so $\psi = 2\phi$ shifts by $\pm\lambda$ and
   $\Delta Q = \pm 1$ exactly. Symmetric and involutive.
2. **Accept** with $\min\!\left(1, e^{-[S_{\rm det}(\psi') - S_{\rm det}(\psi)]}\right)$,
   using the **marginal** action and ignoring $q$ entirely.
3. **Resample** $q \sim p(q \mid \psi')$ with `conditional_su2_sweeps`, which is
   exact at frozen $\psi$ and cannot change `Q`.

The $2\beta$ never enters the acceptance, because it is charged to an SU(2)
configuration that is about to be discarded.

### 4.3 Validity, and the one approximation

Step 2 is a collapsed Metropolis step whose acceptance depends on $\psi$ alone, so
the $\psi$-marginal evolves under a kernel with $\pi(\psi)$ stationary. Step 3
restores the conditional. The composite is stationary for $\pi(\psi, q)$
**provided step 3 resamples to equilibrium**; at finite sweep count it is
approximate, controlled by the sweep parameter. 2D SU(2) at frozen $\psi$ has no
topological obstruction and mixes fast, so the effect is expected to be small —
but that is an expectation, and the $\chi^2$ convergence check in §5 is what tests
it.

### 4.4 The odd move is *cheaper* than the even one

Marginal costs, same script:

| | $\beta_{\rm det}$ | even $\Delta S$ | odd $\Delta S$ | ratio |
|---|---|---|---|---|
| $L=8$, $\beta=14$ | 3.560 | 3.393 | **0.787** | 4.3 |
| $L=16$, $\beta=28$ | 7.020 | 2.062 | **0.532** | 3.9 |

The factor of four is not luck: the odd move adds half the flux of the even move
and the action is quadratic in it, so
$\Delta S_{\rm odd} = \Delta S_{\rm even}/4$.

---

## 5. Does it make the classical arm ergodic? Yes.

`u2_2d/scripts/24_marginal_winding.py`, **cold start**, $L=8$, $\beta=20$, where
the exact odd weight is $0.3335$ — deliberately not $\tfrac12$, so an arm cannot
land on it by symmetry:

| move | parity flips | acceptance | $P(\mathrm{odd})$ | $z$ | $\chi^2/\mathrm{dof}$ |
|---|---|---|---|---|---|
| `step2` (deployed) | 0 | 0.006 | 0.0000 | $-17.90$ | 161.29 |
| `step1` (deployed odd) | 0 | 0.000 | 0.0000 | $-17.90$ | 162.31 |
| **`marginal`** | **440** | **0.344** | **0.3297** | $\mathbf{-0.21}$ | **0.03** |

*(32 chains x 40 trajectories — a smoke run. The record numbers are below.)*

### 5.1 The record runs

Full statistics, cold start throughout. $L=64$, $\beta=416.524$ is the ladder's
top rung, i.e. the hardest coupling in the study:

| $L$ | $\beta$ | move | flips | acceptance | $P(\mathrm{odd})$ | exact | $z$ | $\chi^2/\mathrm{dof}$ |
|---|---|---|---|---|---|---|---|---|
| 8  | 20      | `marginal` | — | 0.339 | 0.3298 | 0.3335 | $-1.25$ | 2.35 |
| 16 | 28      | `marginal` | — | 0.602 | 0.4938 | 0.4928 | $+0.29$ | 2.05 |
| 64 | 416.524 | `step2`    | **0** | 0.220 | 0.0000 | 0.4929 | $-78.86$ | 1039.36 |
| 64 | 416.524 | **`marginal`** | **7661** | **0.599** | **0.4939** | 0.4929 | $\mathbf{+0.17}$ | **3.12** |

The $L=8$, $\beta=20$ row is the one that cannot be explained by symmetry: the
exact odd weight there is $0.3335$, not $\tfrac12$, and the move finds it.

### 5.2 In a real benchmark, not a dedicated test

`08_hmc_seed_benchmark.py` at $L=64$, $\beta=416.524$, 400 trajectories, 64
chains. Arms D and G differ **only** in the acceptance rule of the winding move:

| arm | plaquette | $\langle Q^2\rangle$ | $Q$ changes | parity flips | $P(Q)$ covered | odd sectors |
|---|---|---|---|---|---|---|
| D cold + even winding | 0.995247 | 1.125 | 1334 | **0** | 0.507 | 0 |
| G cold + **odd** winding | 0.995250 | 0.973 | 3557 | **2587** | **1.000** | 4 |
| E diffusion + even winding | 0.995186 | 0.989 | 2256 | **0** | **1.000** | 4 |
| A diffusion seed, no winding | 0.995200 | 1.141 | 0 | **0** | 0.995 | 3 |

exact $\langle Q^2\rangle = 1.0012$.

Two things to read off this table, in order of importance:

1. **D $\to$ G retires the reachability claim.** Same start, same everything, and
   parity flips go $0 \to 2587$ purely from changing how the move is priced.
2. **E is the interesting row.** It reaches coverage $1.000$ with **zero** parity
   flips — the even move cannot change parity, so every odd sector it occupies
   came from the seed. G manufactures the same coverage in 1100 s; E inherits it
   in 379 s. The cost of the marginal move is real (each accepted move triggers
   25 conditional SU(2) sweeps, $\approx 7.6\times$ a plain trajectory), which is
   exactly why inheriting the sectors instead of manufacturing them is worth
   something.

### 5.3 Cost control

Measured 2026-08-20: the marginal move costs 1609 ms/trajectory against the
central move's 211 ms, and the number is **flat in $L$** (1609 at $L=16$, 1610 at
$L=32$) — it is entirely the 25 SU(2) sweeps, which are launch-bound. It does not
need to fire every trajectory: composing MCMC kernels on a fixed scan preserves
the target at any interval, so `winding_interval` trades attempts for wall-clock
without touching the stationary distribution. At interval 5, $L=16$, $\beta=28$,
300 trajectories from cold: 152 s (vs 483 s) and 34.6 accepted flips per chain,
against interval 10's 108 s and 18.0. Stage 01 uses interval 5.

Note that $\langle Q^2\rangle$ measured on the final snapshot fluctuates at the
$\pm 2\sigma$ level across intervals (1.516 vs 0.922 on 64 chains) and **must not
be used to select the interval** — the interval provably cannot bias it, only the
mixing rate, so the flip count is the statistic that discriminates.

---

## 6. What this retires, and what survives

### Retired

> *"The classical arm covers 0.507 of the exact $P(Q)$ with zero odd sectors and
> cannot improve at any cost, because odd charge has probability zero in its
> stationary distribution rather than merely long autocorrelation."*

**This must be withdrawn.** Odd charge does not have probability zero in the
stationary distribution of a correctly-built classical chain; it had probability
zero in the stationary distribution of *the move that was implemented*. The
$\beta$-controlled odd-mobility boundary measured in `15_base_parity.py` is a
property of `winding_update` as deployed, not of 2D U(2).

### Survives

* **Everything about the even move.** $\Delta Q = 2$ at $2\pi^2\beta/V$, a ladder
  invariant, unchanged.
* **The U(1) instanton**, which was never in question and is optimal.
* **The diffusion lift's handling of odd charge.** `lift_determinant` sets the
  sector with `apply_coarse_charge` on $\psi$ — a plain U(1) field — so odd
  transport was always correct and costs nothing. **No generated ensemble needs
  regenerating on account of this.**
* **The 2D caveat.** `DetSectorAction` exists because SU(2) integrates out exactly
  per plaquette in two dimensions. There is no such marginal in 4D or with
  fermions, so the reachability argument may survive in the narrower form: *no
  local algorithm reaches these sectors, and the move that does is built from an
  exact marginal that only two dimensions provides.*

### Now open

* The base ensembles were generated with `topological_updates=True` at
  `charge_step=2`, so they can never flip parity — the odd weight is frozen in at
  the hot quench. With a working odd move the base could **sample** parity
  instead of inheriting it, and since transport carries the base's $P(Q)$ to every
  rung, that is the one case where regenerating the ladder buys something real.
* Cost comparisons against "HMC + winding" were made against a non-ergodic
  baseline and need re-running against this one.

---

## 7. Where the code is

| what | where |
|---|---|
| U(1) instanton field, Metropolis move | `u1_2d/lgt/local_updates.py` — `instanton_field`, `topological_update` |
| U(2) even (central) move | `u2_2d/lgt/local_updates.py` — `central_winding_field`, `winding_update` |
| U(2) odd shift fields, $U(1)_T$ | `u2_2d/lgt/local_updates.py` — `winding_field` |
| exact $\psi$-marginal | `u2_2d/lgt/actions.py` — `DetSectorAction` |
| exact conditional SU(2) sampler | `u2_2d/lgt/local_updates.py` — `conditional_su2_sweeps` |
| candidate comparison | `u2_2d/scripts/23_odd_instanton.py` |
| ergodicity test | `u2_2d/scripts/24_marginal_winding.py` |
| narrative version | `docs/u2_2d/NARRATIVE.md` §11.5 |
