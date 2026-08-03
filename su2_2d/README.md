# su2_2d — 2D SU(2) inverse-RG diffusion (active line)

First non-abelian step of the InverseRG program, inheriting the load-bearing
structure of the closed U(1) study (`u1_2d/`, `docs/NARRATIVE.md`): matched
2x2 blocking ladder, denoising score matching on the exact group heat kernel,
gauge-covariant curl-head score, HMC-wrapped correctness.

**Status: scripted, not yet run.** Unit tests pass; the heavy pipeline stages
(01 data, 02 train, 03 lift) have not been executed.

## Conventions

- Links are unit quaternions `[..., 2, L, L, 4]` = (w, v); `U = w + i v.sigma`,
  so the product carries a minus cross term and `tr U = 2w` (`lgt/group.py`).
- Algebra coordinates `omega` with `U = exp(i (omega.sigma)/2)`; half-angle
  `theta = |omega|/2 in [0, pi]`.
- Plaquette word `P(x,y) = Ux(x,y) Uy(x+1,y) Ux(x,y+1)^-1 Uy(x,y)^-1`; Wilson
  action `S = -(beta/2) sum tr P`.
- Exact references by plaquette decoupling: `<(1/2) tr P> = I_2(beta)/I_1(beta)`,
  exact area law for Wilson loops (`lgt/exact.py`).
- Heat kernel `K_s(theta) = sum_j (2j+1) chi_j(theta) e^{-s j(j+1)/2}` with
  cutoff `2j_max ~ 14/sqrt(s)`; exact conditional score
  `(1/2) (dlog K/dtheta) n_hat` (`lgt/heat_kernel.py`). DSM stays exact.
- 2D SU(2) has trivial pi_1: no topological sectors. That is deliberate — it
  isolates the non-abelian score/geometry problems from the topology problems
  U(1) already solved (instanton transport) before 4D brings both at once.

## Layout

```
lgt/     group algebra, lattice words, blocking, HMC, exact refs, heat kernel
model/   heat-kernel noising + DSM targets, curl-head score net, schedule,
         trainer (EMA-validated), ancestral group sampler (conditional lift)
scripts/ 00 smoke, 01 generate data, 02 train, 03 sample + validate
configs/ su2.yaml (rungs, training, first lift 8:4 -> 16:16)
tests/   sign-convention and exactness tests (matrix cross-checks, autograd)
```

## Roadmap

1. ~~Group/lattice/HMC/exact core~~ (done, tested)
2. ~~Heat-kernel targets + curl head + trainer + sampler~~ (scripted)
3. Run 00 smoke, then 01-03: first conditional lift 8:4 -> 16:16
4. Matched-coupling refinement (character matching, not just beta/4)
5. Ladder iteration + validation suite (port u1_2d/validate structure)
6. AIS bridge for exactness (construction transfers: differentiable invariant
   features + HMC kernel both exist here; no exact-P(Q) crutch available —
   and none needed, pi_1 trivial)
```
