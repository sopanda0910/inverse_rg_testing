# 2D U(2): design, derivations, and what has been measured

Opened 2026-08-19, successor to the closed 2D U(1) study. This is the U(2)
analogue of `docs/u1_2d/NARRATIVE.md`: the mathematics the code rests on, derived
rather than asserted, with every claim tagged by how it was checked.

Code: `u2_2d/`. Outputs: `out/u2_2d/`. One-page orientation: `u2_2d/README.md`.

---

## 1. Why U(2), and the shape of the plan

2D U(1) is finished. The two candidate successors were 2D SU(2) (attempted, set
aside — the single-plaquette curl basis is incomplete there) and 2D U(2). U(2)
wins on three counts:

1. **It is exactly solvable.** 2D lattice gauge theory is solvable for any compact
   group, and for U(2) the character sum is tractable in closed form. There is an
   exact answer to compare against for the plaquette, every Wilson loop, the
   string tension, the free energy, and the whole topological charge
   distribution.
2. **Its topology is U(1) topology.** `pi_1(U(2)) = Z`, detected by the
   determinant, and `pi_1(SU(2)) = 0`. So the hard part of the U(1) study — the
   part about transporting topological sectors across an RG step — carries over
   literally rather than by analogy.
3. **It is genuinely non-abelian.** Unlike U(1), the group does not commute, so
   the machinery has to survive contact with a real gauge group.

The plan under test: write each link as `U = e^{i phi} q` with `q in SU(2)`,
generate the U(1)-like part with the existing diffusion model, and handle the
SU(2) part cheaply. Section 4 shows what needed sharpening in that plan and why
the sharpened version costs nothing.

---

## 2. Representation and conventions

Links are stored exactly as in the sibling NTHMC `src/nthmc/u2` code, so
configurations are interchangeable between the two projects:

```
U = e^{i phi} q,   q = q0 I + i sum_a q_a sigma_a,   |q| = 1
links[..., 5] = (phi, q0, q1, q2, q3)
U = e^{i phi} [[q0 + i q3,  q2 + i q1],
               [-q2 + i q1, q0 - i q3]]
```

Because `U(2) = (U(1) x SU(2)) / Z_2`, the pairs `(phi, q)` and `(phi + pi, -q)`
are the same group element. Everything below is invariant under that flip.

Index convention mirrors `u1_2d.lgt.lattice` with one extra trailing axis:
`links[batch, mu, x, y, :]`, dim `-3` is x, dim `-2` is y. Plaquette
`P = U_0(x) U_1(x + 0) U_0(x + 1)^dag U_1(x)^dag`, the same orientation as U(1).

Action, in the `u1_2d` sign convention (NTHMC carries an extra additive `beta V`,
irrelevant to dynamics but not to free energies):

```
S(U) = -beta sum_p (1/2) ReTr P_p = -beta sum_p q0_p cos(phi_p)
```

Topological charge from the determinant phase, rounded (NTHMC uses a
`floor(0.1 + .)` offset; same quantity):

```
Q = sum_p wrap(arg det P_p) / 2 pi
```

---

## 3. The determinant sector is a compact U(1) gauge field

`det : U(2) -> U(1)` is a group homomorphism and `det U = e^{2 i phi}`. Define

```
psi_{x,mu} = wrap(2 phi_{x,mu}).
```

Four consequences, each checked to machine precision by
`u2_2d/scripts/09_verify_identities.py`:

* **`psi` is a U(1) gauge field.** Under `U -> G_x U G_{x+mu}^dag` with
  `G = e^{i gamma} g`, the determinant transforms as
  `psi -> psi + gamma_x - gamma_{x+mu}`, so SU(2)-valued gauge transformations
  leave `psi` untouched and U(2) ones act on it as U(1) gauge transformations.
* **The plaquette determinant phase is the plain SUM of link phases**, because
  `det` is multiplicative — no ordering, no conjugation. So
  `arg det P_p` equals `u1_2d`'s plaquette angle computed on `psi`, and every
  `u1_2d.lgt` routine applies to `psi` unchanged.
* **`Q` is a functional of `psi` alone.** The SU(2) sector cannot change the
  topological charge. This is the fact the whole design is organized around.
* **The abelian telescope survives blocking.** With the blocking rule
  `V_0(X,Y) = U_0(2X,2Y) U_0(2X+1,2Y)` (and likewise in y), the coarse plaquette
  determinant is the product of the four fine plaquette determinants, so the
  coarse determinant plaquette angle is the wrapped sum of the four fine ones —
  **exactly**, non-abelian group notwithstanding. Hence `Q_coarse = Q_fine` up to
  wrap events, and sector transport across an inverse-RG step is an identity, as
  it was in U(1).

---

## 4. The joint distribution does not factorize — and the fix is free

The tempting reading of the split representation is that U(2) is "a U(1) field
times an SU(2) field", so one could generate the two independently and multiply.
That is wrong. Expand the action density:

```
(1/2) ReTr P = cos(omega_p) cos(phi_p)
             = 1 - phi_p^2/2 - omega_p^2/2 + phi_p^2 omega_p^2/4 + ...
```

where `q0_p = cos omega_p`. It is a **product** of the two sectors, not a sum.
They decouple at Gaussian order and couple at quartic order; nothing about the
coordinates makes them independent.

The repair is to factorize **conditionally** rather than independently:

```
p(psi, q) = p(psi) . p(q | psi)
```

and this costs nothing, because the conditional is exactly sampleable. Writing
`Sigma` for the staple sum of a link and `n = q Sigma`:

```
(1/2) ReTr(U Sigma) = Re(e^{i phi} n_0) = |n_0| cos(phi + arg n_0)
```

so the central phase is von Mises; and at fixed `phi`, with `s = e^{i phi} Sigma`,

```
(1/2) ReTr(U Sigma) = k . q,   k = (Re s_0, -Re s_1, -Re s_2, -Re s_3)
```

so the SU(2) part is the standard heatbath conditional `p(q) ~ exp(beta k . q)`.
Alternating the two is a Gibbs sampler on U(2) — the U(2) reading of
Cabibbo-Marinari, exact because `U(1) x SU(2)` covers the group. Freezing `phi`
and iterating only the second gives an **exact sampler for `p(q | psi)`** that
leaves `psi`, and therefore `Q`, bit-for-bit unchanged
(`lgt.local_updates.conditional_su2_sweeps`).

Fixing `phi = psi / 2` and letting `q` range over SU(2) covers the fiber
`{U : det U = e^{i psi}}` exactly once, so this neither over- nor under-counts the
`Z_2`.

**Measured (`test_su2_sector_is_reconstructible_from_the_determinant_sector`,
beta = 8, L = 6, 2624 configurations).** Take an equilibrated ensemble, throw the
SU(2) sector away completely — replace it with Haar noise, which drops
`<(1/2)ReTr P>` from 0.7337 to 0.0019 — keep only `psi`, and run the conditional
sampler:

| conditional sweeps | `<(1/2)ReTr P>` | `W(2x2)` |
|---|---|---|
| 0 (Haar noise) | 0.00191 | 0.00056 |
| 2 | 0.73180 | 0.28722 |
| 5 | 0.73352 | 0.29202 |
| 10 | 0.73336 | 0.28886 |
| 25 | 0.73339 | 0.29065 |
| original ensemble | 0.73368 | 0.29104 |
| exact (infinite volume) | 0.73298 | 0.28865 |

`Q` is identical to the original at every row. **Two sweeps recover the joint.**
The SU(2) sector needs no model — the original plan's instinct was right, and the
conditional formulation is what makes it exact.

---

## 5. The determinant sector is not U(1) Wilson at beta/4

The second consequence of non-factorization. Integrate the SU(2) part out of one
plaquette against normalized Haar measure:

```
int dq exp(beta q0 cos phi_p) = 2 I_1(z) / z,   z = beta cos phi_p
```

In 2D the plaquettes are independent up to one global constraint, so the marginal
of `psi` is a compact U(1) lattice gauge theory with single-plaquette weight

```
w_det(alpha) = 2 I_1(z) / z,   z = beta cos(alpha / 2),   alpha in (-pi, pi]
```

(`lgt.actions.DetSectorAction`; `z >= 0` throughout because `alpha/2` lies in
`(-pi/2, pi/2]`). At large beta, using `I_1(z) ~ e^z / sqrt(2 pi z)`,

```
-log w_det = const + beta [1 - cos(alpha/2)] + (3/2) log cos(alpha/2) + ...
           = const + (beta/8) alpha^2 + O(alpha^4) + measure term
```

Matching the quadratic coefficient to U(1) Wilson `(beta_1 / 2) theta^2` gives
`beta_1 = beta / 4`, recovering the tree-level normalization guide of
`docs/Field_transform.html`. The `(3/2) log cos(alpha/2)` term — the measure factor
from the three integrated-out SU(2) directions — is what keeps the determinant
sector from being Wilson at *any* coupling.

`lgt.exact.matched_u1_beta` is the minimum-KL projection onto the U(1) family
(match `r_1`; the Wilson weight is a one-parameter exponential family whose
sufficient statistic is `sum_p cos alpha_p`, so `r_1`-matching is the maximum
likelihood fit). Measured residuals:

| `beta_U(2)` | `beta_1` | `beta_1 / (beta/4)` | `chi_t` residual | `r_2` residual | KS distance |
|---|---|---|---|---|---|
| 4 | 0.772 | 0.772 | +7.8e-3 | +3.27e-1 | 3.1e-3 |
| 14 | 3.560 | 1.017 | +1.82e-2 | +2.62e-2 | 6.7e-3 |
| 40 | 10.012 | 1.001 | +8.5e-4 | +5.23e-4 | 1.9e-3 |
| 220 | 55.002 | 1.00003 | +2.2e-5 | +2.4e-6 | 3.2e-4 |

So `beta/4` is a large-beta limit, not an identity: it is 23% wrong at
`beta = 4`. Anything quoting an analytic U(1) coupling — in particular the
coupling the score network is conditioned on and the analytic force hint inside
its head — must use `matched_u1_beta`. The training target itself is unaffected,
because training data are real U(2) determinant fields.

---

## 6. Exact solution on the torus

In axial gauge the plaquettes are independent up to one global constraint, and
for genus `g = 1`

```
Z = sum_r (c_r / d_r)^V,    c_r = int dU chi_r(U)^* e^{beta (1/2) ReTr U},  V = L^2
```

(the general formula carries `d_r^{2-2g}`, which is 1 on the torus — this is why
it reduces to `u1_2d`'s `sum_q c_q^V` when all `d_r = 1`).

**Irreps in the split coordinates.** Since `U(2) = (U(1) x SU(2)) / Z_2`, an irrep
is a pair `(j, k)` — SU(2) spin `j`, central U(1) charge `k` — subject to
`k = 2j (mod 2)`, with character `chi_{(j,k)}(e^{i phi} q) = e^{i k phi} chi_j(q)`
and dimension `d = 2j + 1`.

**The SU(2) one-link integral.** With `chi_j(q) = sin((2j+1) w) / sin w` and Haar
measure `(2/pi) sin^2 w dw`, using
`sin w sin(n w) = [cos((n-1)w) - cos((n+1)w)] / 2` and
`I_{n-1}(a) - I_{n+1}(a) = (2n/a) I_n(a)`:

```
int dq chi_j(q) e^{a q0} = (2j + 1) . 2 I_{2j+1}(a) / a = d_j g_j(a)
```

(the dimension factor is easy to drop and was, once — it cancels from `c_r / d_r`
so the partition sum is unaffected, but Wilson loops need it restored).

**Character coefficients collapse to one quadrature:**

```
c_{j,k}(beta) = d_j int_0^{2pi} (d phi / 2 pi) e^{-i k phi} g_j(beta cos phi)
```

Continuing `g_j` to negative argument picks up two signs — `I_nu(-x) = (-1)^nu I_nu(x)`
and the explicit `1/z` — giving `(-1)^(nu+1)`, i.e. `g_j` is even for integer `j`
and odd for half-integer `j`. So the integral vanishes unless `k = 2j (mod 2)`:
**the `Z_2` constraint falls out of the arithmetic rather than being imposed.**

**Checks (all in `09_verify_identities.py` and the test suite):**

* Infinite volume, from Weyl integration over U(2) with `x = beta/2`:
  `Z_1 = I_0(x)^2 - I_1(x)^2` and
  `<(1/2)ReTr P> = I_1(x)(I_0(x) - I_2(x)) / (2 Z_1)`. The character expansion
  reproduces this to 1e-10 at `beta = 0.5 ... 120`.
* `r_fund = c_fund / (2 c_0)` equals `<(1/2)ReTr P>` exactly, and the 2D area law
  `<(1/2)ReTr W(A)> = r_fund^A` holds to 1e-9.
* Finite volume `(1/V) d log Z / d beta` converges to the infinite-volume value:
  at `beta = 10`, L = 4 gives 0.79305, L = 8 gives 0.7907535, L = 16 gives
  0.7907534, against 0.7907534.

**Determinant-sector `P(Q)`.** Because `det` is a homomorphism, the determinant of
the global constraint is exactly the U(1) constraint `sum_p alpha_p = 0 mod 2 pi`,
so `u1_2d`'s constrained-sum representation applies verbatim with
`plaquette_weight` replaced by `w_det`:

```
P(Q) ~ int dk e^{-2 pi i k Q} psi(k)^V,   psi(k) = <cos(k alpha)>_{w_det}
```

**Measured against heatbath, L = 6, 38400 configurations per coupling:**

| beta | `<Q^2>` measured / exact | worst sector ratio |
|---|---|---|
| 2 | 2.6128 / 2.5849 | 1.02 (Q = ±2) |
| 5 | 1.3539 / 1.3499 | 1.06 (Q = ±3) |
| 8 | 0.6854 / 0.6753 | 1.08 (Q = ±3) |

Every sector, odd and even, to 1–2%. This validates both the exact formula and
the charge definition.

---

## 7. The U(2)-specific result: odd topological sectors

Multiply the ordered product of all plaquettes on the torus. It equals the
identity, and separating the central phase gives
`e^{i sum_p phi_p} (ordered prod q_p) = 1`, with the left factor in
`SU(2) ∩ U(1).I = {±1}`. Hence

```
Q even  <=>  ordered product of SU(2) plaquettes = +1
Q odd   <=>  ordered product of SU(2) plaquettes = -1
```

**Even charge changes are free.** Adding the U(1) instanton to `phi` shifts every
plaquette phase by `2 pi / V`, is purely central so it commutes with everything,
and costs `dS ~ 2 pi^2 beta / V`. This is `central_winding_field`, and it is the
U(1) move verbatim, giving `delta Q = ±2`.

**Odd charge changes cannot leave the SU(2) sector alone.** Choosing the branch of
`phi = psi/2` link by link is a `Z_2` gauge field; flipping one link flips two
plaquettes, so the *parity* of the number of plaquettes carrying a spurious `-1`
is branch independent — and it is odd. (Sum the raw plaquette phase over the
lattice: it is `pi + pi sum_p m_p` and must vanish, so `sum_p m_p` is odd.)
Halving the U(1) instanton therefore leaves exactly one plaquette with an extra
factor `-1`, at cost `2 beta`. Spreading the required monodromy smoothly through
the `U(1)_T` subgroup `exp(i lam T)`, `T = (I + n.sigma)/2` — i.e.
`diag(e^{i lam}, 1)` in the `n` colour frame — is topologically correct, but its
transition column does not commute with the SU(2) background and costs
`O(beta L)`. Axial gauge fixing and randomizing the colour axis do not help.

**Measured (`u2_2d/scripts/05_topology_study.py`):**

| beta | L | `dQ=2` accept | `dQ=2` forced cost / predicted | `dQ=1` accept | `dQ=1` forced cost | after conditional SU(2) |
|---|---|---|---|---|---|---|
| 8 | 8 | 0.500 | 3.4 / 2.5 | 0.000 | 38.4 | **4.7** |
| 20 | 8 | 0.031 | 5.5 / 6.2 | 0.000 | 114.2 | **1.3** |
| 20 | 16 | 0.344 | 1.4 / 1.5 | 0.000 | 190.8 | **3.4** |

The last column is the point. `set_topological_charge` reaches any sector
deterministically, and `conditional_su2_sweeps` — exact for `p(q | psi)`, and
unable to move `Q` — removes essentially all of the odd-charge defect, leaving
only the physical free-energy cost of the sector. **The classical global move
pays 38–191; the generative route pays 1–5.**

HMC freezing, same script, L = 8, 400 trajectories x 16 chains:

| beta | plain HMC sector changes | + winding (even only) | `<Q^2>` plain / winding / exact |
|---|---|---|---|
| 8 | 545 | 895 | 1.158 / 1.274 / 1.201 |
| 20 | 0 | 6 | 0.000 / 0.018 / 0.355 |
| 56 | 0 | 0 | 0.000 / 0.000 / 0.030 |

So 2D U(2) freezes *harder* than 2D U(1): above the threshold the only cheap
global move is even-charge, and odd sectors are unreachable. This is the gap the
inverse-RG ladder is aimed at, and it is a sharper gap than the U(1) study had.

**Consequence for reference ensembles.** Above the threshold no local dynamics
equilibrates `P(Q)`, so stage-01 ensembles are not references — at the ladder base
they came out with `<Q^2> = 0.083` against an exact 0.504. `lgt/sector_seed.py`
seeds chains from the exact `P(Q)` and then re-equilibrates the SU(2) sector
exactly; that moved L = 16, beta = 56 from `<Q^2> = 0.125` to 0.542 against an
exact 0.479. Such ensembles have exact sector weights **by construction** and must
never also be cited as evidence that `P(Q)` is reproduced. Note also that above
the threshold the number of *independent* charges in an ensemble equals the number
of chains, not the number of configurations.

---

## 8. The ladder

One inverse-RG step, `lgt`-level facts assembled:

1. lift `psi` with the conditional diffusion model (the `u1_2d` score net,
   conditioned on `matched_u1_beta`), with structural charge transport;
2. seed the SU(2) sector by naive inverse blocking of the coarse SU(2) part
   (`model/su2_lift.py`: geodesic halves, which reproduce the blocking constraint
   exactly);
3. equilibrate the SU(2) sector at frozen `psi` — exact, and cannot move `Q`;
4. short joint rethermalization, which is where determinant-sector model error is
   locally repaired.

Coupling schedule: tree level is `beta_c = beta_f / 4` in all four `u(2)`
directions (the coarse plaquette is a product of four fine ones, so at weak
coupling the algebra elements add and the variance quadruples). Nonperturbatively
`r_R -> r_R(beta_f)^4` for every irrep, and the `r_fund`-matched coupling is the
minimum-KL projection: `beta_f = 56` matches to `beta_c = 15.05`, not 14.00. The
configs use the matched values.

The determinant-sector `<Q^2>` is close to a fixed point of the ladder
(`beta_f = 4 beta_c`, `L_f = 2 L_c`): starting from `beta = 56.6, L = 8` it runs
0.02893 → 0.02577 → 0.02505 → 0.02488, converging to ~0.5% per rung. Less exact
than the U(1) Villain case, which was a fixed point to five digits, because the
determinant sector is not Villain — measured, not assumed.

**Smoke-run status (15 training epochs, deliberately undertrained).** Lifting
L = 8, `beta` = 15.05 to L = 16, `beta` = 56:

* plaquette 0.964187 against exact 0.964114, `z = +0.68`;
* largest Wilson loop `z = 1.50` against the HMC reference;
* `<Q^2>` pre-rethermalization equals the coarse base's exactly — **charge
  transport is exact** — and drifts up during rethermalization because the
  undertrained model leaves the configuration far from equilibrium (plaquette
  0.78 before, 0.964 after). That drift is the diagnostic for model convergence,
  which is why both values are recorded at every rung.
* The determinant-sector Wilson loops carry `z` up to 7 while the full-U(2) ones
  sit near 2. That split is exactly the diagnostic the two observable families
  were built for: the error is in `p(psi)`, which is the model, not in
  `p(q | psi)`, which is exact.

---

## 9. Open items

* Train to convergence and rerun the ladder; the smoke model is 15 epochs.
* Extend the ladder past one rung (`configs/default.yaml` goes to L = 64).
* The odd-charge global move is open as a *classical* algorithms question. An
  exact Metropolis version needs the marginal `p(psi)`, which is known
  analytically only up to the single global constraint; AIS or thermodynamic
  integration over the SU(2) sector would close it. Not needed by the ladder.
* Wilson loops at finite volume are currently compared against the infinite-volume
  area law; the finite-volume non-abelian formula is not implemented.
