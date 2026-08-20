# u2_2d — diffusion-based inverse RG for 2D U(2)

Successor to the closed `u1_2d` study. 2D U(2) is exactly solvable, its topology
is carried entirely by an honest compact U(1) field, and it is non-abelian — so
it tests whether the U(1) machinery survives contact with a real gauge group
without yet paying the cost of a theory with no exact answers.

## The idea, and the one place it needed sharpening

Write each link in the split representation

    U = e^{i phi} q,    q in SU(2),    stored as (phi, q0, q1, q2, q3)

and split one inverse-RG step as

    p(psi, q) = p(psi) p(q | psi),    psi = wrap(2 phi) = arg det U.

The determinant field `psi` is a genuine compact U(1) lattice gauge field: SU(2)
gauge transformations leave it alone, U(2) ones act on it as U(1) ones, and
`det_links` returns it in exactly the `[B, 2, L, L]` layout every `u1_2d.lgt`
routine already consumes. **All the topology lives there**, and the diffusion
model that lifts it is the U(1) model, reused unchanged.

The SU(2) sector needs no model. At frozen `phi` the U(2) local weight is exactly
`exp(beta k . q)` — the standard SU(2) heatbath conditional — so
`conditional_su2_sweeps` is an *exact* sampler for `p(q | psi)`, and 2D SU(2) has
no topological obstruction to slow it down. Seeding it by naive inverse blocking
of the coarse SU(2) part only decides how many sweeps are needed.

One thing does *not* factorize, and the code is built around it:

**The joint distribution is not a product.** `(1/2)ReTr P = cos(omega_p) cos(phi_p)`
is a product of the two sectors, not a sum, so independently generating a U(1)
part and an SU(2) part and multiplying them is wrong at O(phi^2 omega^2).
Generating `psi` and then `q` *conditioned on it* is right, and costs nothing
extra. The exact consequence is that `psi`'s own marginal is not U(1) Wilson at
`beta/4` either: integrating SU(2) out of a plaquette gives

    w_det(alpha) = 2 I_1(z) / z,    z = beta cos(alpha / 2)

(`lgt.actions.DetSectorAction`), whose large-beta limit is Wilson at `beta/4` plus
a `(3/2) log cos(alpha/2)` measure term. `lgt.exact.matched_u1_beta` is the
minimum-KL projection onto the U(1) family and is what the network is conditioned
on: it differs from `beta/4` by 23% at `beta = 4` and by 0.003% at `beta = 220`.

## What is exact here

| statement | where | status |
|---|---|---|
| `Q` is a functional of `psi` alone | `lgt/lattice.py` | machine precision |
| coarse determinant plaquette = wrapped sum of four fine ones | `lgt/blocking.py` | machine precision, non-abelian group notwithstanding |
| `det(block(U)) = block(det(U))` | `lgt/blocking.py` | machine precision |
| `Q_coarse = Q_fine` | `lgt/blocking.py` | exact up to wrap events |
| character expansion `Z = sum_{j,k} (c_{j,k}/d_j)^V` | `lgt/exact.py` | reproduces Weyl integration to 1e-10 |
| area law `<(1/2)ReTr W(A)> = r_fund^A` | `lgt/exact.py` | exact in 2D |
| determinant-sector `P(Q)` | `lgt/exact.py` | matches heatbath to 1–2% in every sector, `beta = 2, 5, 8` |
| analytic `u(2)` force = autograd | `lgt/hmc.py` | 1e-15 |
| overrelaxation is microcanonical | `lgt/local_updates.py` | 1e-14 |
| `conditional_su2_sweeps` leaves `psi` and `Q` alone | `lgt/local_updates.py` | bit-for-bit |
| Omelyan is second order and reversible | `lgt/hmc.py` | dt^2 scaling, 1e-15 reversibility |

`python u2_2d/scripts/09_verify_identities.py` checks all of them in seconds.

## The U(2)-specific result: odd topological sectors

`U(2) = (U(1) x SU(2)) / Z_2`, and multiplying the ordered product of all
plaquettes gives `e^{i sum_p phi_p} (ordered prod q_p) = 1`. Hence

    Q even  <=>  ordered product of SU(2) plaquettes = +1
    Q odd   <=>  ordered product of SU(2) plaquettes = -1.

So an **even** change of `Q` is free — it is the U(1) instanton added to `phi`,
purely central, `dS = O(beta / V)`. An **odd** change of `Q` cannot leave the
SU(2) sector alone, and no fixed shift field achieves it cheaply: halving the U(1)
instanton leaves one plaquette carrying a spurious `-1` at cost `2 beta`
(measured `dS = 37` at `beta = 20, L = 8`), and spreading the required monodromy
through the `U(1)_T` subgroup costs `O(beta L)` instead (measured 110). Gauge
fixing does not remove it.

The generative route is not affected, and that is the point. Setting `psi` sets
`Q`, and the exact conditional SU(2) sampler then relaxes the monodromy for free:
measured, `set_topological_charge` to an odd sector leaves `dS = 26–149` and
`conditional_su2_sweeps` brings it back to ~5 — the physical free-energy cost of
the sector. **The diffusion ladder reaches odd sectors where the classical global
move cannot.**

## Layout

```
lgt/lattice.py        split representation, group ops, loops, staples, determinant bridge
lgt/actions.py        Wilson U(2); the exact SU(2)-integrated determinant action
lgt/exact.py          U(2) character expansion; determinant-sector P(Q), chi_t, matching
lgt/hmc.py            batched group-manifold HMC, analytic u(2) force
lgt/local_updates.py  U(2) Gibbs heatbath, overrelaxation, winding moves, p(q | psi)
lgt/blocking.py       2x2 blocking, determinant telescope, coarse-coupling matching
model/det_lift.py     adapter onto the u1_2d score net (conditioning coupling included)
model/su2_lift.py     naive SU(2) inverse blocking (the seed, not the sampler)
pipeline/ladder.py    one inverse-RG step, and the ladder
validate/             observables split into full-U(2) and determinant-sector families
```

## Running

```bash
.venv/Scripts/python.exe u2_2d/scripts/09_verify_identities.py           # seconds, must pass
.venv/Scripts/python.exe -m pytest u2_2d/tests -q                        # 84 tests

.venv/Scripts/python.exe u2_2d/scripts/01_generate_data.py --config u2_2d/configs/smoke.yaml --device cpu
.venv/Scripts/python.exe u2_2d/scripts/02_train.py        --config u2_2d/configs/smoke.yaml
.venv/Scripts/python.exe u2_2d/scripts/03_run_ladder.py   --config u2_2d/configs/smoke.yaml
.venv/Scripts/python.exe u2_2d/scripts/04_validate.py     --config u2_2d/configs/smoke.yaml --device cpu
```

Outputs go to `out/u2_2d/`. Device choice follows the U(1) study's measured rule:
CPU for batched HMC at these volumes (stages 01 and 04), GPU for training and
model sampling (stages 02 and 03). `U2_2D_DEVICE` overrides, falling back to
`U1_2D_DEVICE`.

## Relationship to NTHMC

`lgt/lattice.py` uses the same split representation, plaquette orientation and
determinant-phase topological charge as the sibling `NTHMC/src/nthmc/u2` code, so
configurations and conventions are interchangeable. Two deliberate differences:
this action drops NTHMC's additive `beta V` constant to match the `u1_2d` sign
convention, and `topological_charge` rounds rather than using the
`floor(0.1 + .)` offset.
