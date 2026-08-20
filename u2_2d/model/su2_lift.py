"""The SU(2) half of the factorized inverse-RG lift -- the half that needs no model.

The design splits one U(2) inverse-RG step into

    p(psi, q) = p(psi) p(q | psi),

with psi = wrap(2 phi) the determinant field. Everything hard lives in p(psi):
it carries all the topology, it is where critical slowing down and topological
freezing happen, and it is what the diffusion model is trained on
(`u2_2d.model.det_lift`). The conditional p(q | psi) needs no model at all, for
two reasons that are both exact:

* 2D SU(2) has trivial pi_1, so the conditional has no sector structure to
  transport and no freezing to defeat; it is a short-correlation-length local
  theory that a checkerboard heatbath equilibrates in a few sweeps.
* at frozen phi the U(2) local weight is exactly exp(beta k . q), the standard
  SU(2) heatbath conditional, so `lgt.local_updates.conditional_su2_sweeps` is an
  EXACT sampler for p(q | psi) -- it never touches psi, so the determinant sector,
  and with it Q, survives bit-for-bit.

Fixing phi = psi / 2 and letting q range over SU(2) covers the fiber over a given
determinant exactly once (U = e^{i psi/2} q for q in SU(2) is a bijection onto
{U : det U = e^{i psi}}), so the conditional sampler is neither over- nor
under-counting the Z_2 of U(2) = (U(1) x SU(2)) / Z_2.

This module supplies only the SEED for that sampler: a naive inverse blocking of
the coarse SU(2) sector. Since the conditional heatbath is exact, the seed cannot
bias the result -- it only decides how many sweeps are needed -- which is exactly
why "naively inverse block SU(2)" is the right amount of intelligence to spend
here.
"""

import torch

from ..lgt.lattice import su2_exp, su2_log


def half_quaternion(q: torch.Tensor) -> torch.Tensor:
    """Geodesic square root: H with H H = q, on the principal branch."""
    return su2_exp(0.5 * su2_log(q))


def naive_su2_inverse_block(coarse_su2: torch.Tensor) -> torch.Tensor:
    """[B, 2, Lc, Lc, 4] coarse SU(2) links -> [B, 2, 2Lc, 2Lc, 4] fine seed.

    Each coarse link is split into two identical geodesic halves, which reproduces
    the blocking constraint exactly along the blocked paths (H H = Q), and the
    fine links that blocking never constrained -- x-links on odd y, y-links on odd
    x -- get the same halves, the smoothest filling available without a model.
    """
    half = half_quaternion(coarse_su2)
    return half.repeat_interleave(2, dim=-3).repeat_interleave(2, dim=-2)


def assemble_links(psi_fine: torch.Tensor, su2_fine: torch.Tensor) -> torch.Tensor:
    """(determinant field, SU(2) seed) -> U(2) links [B, 2, L, L, 5].

    phi = psi / 2 picks the branch; the other branch is q -> -q, which the
    conditional SU(2) sampler explores anyway.
    """
    return torch.cat([0.5 * psi_fine.unsqueeze(-1), su2_fine], dim=-1)
