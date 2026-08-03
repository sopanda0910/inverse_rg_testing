"""D4 lattice-symmetry augmentation for SU(2) link fields.

The Wilson action is invariant under the 8 square-lattice symmetries, but a
plain CNN is not (it only has translations, via circular padding). U(1) found
explicit augmentation worth it; the same applies here, and the group elements
themselves are untouched -- only the LINK GEOMETRY is relabelled.

Under a 90-degree rotation, x-links become y-links and one family must be
inverted-and-shifted so that the link still points "out of" its new base site;
under a reflection the same happens within one family. Correctness is not
argued here, it is tested: `tests` assert the plaquette-trace field is
permuted (never changed in value) by every element of the group, which is
exactly the statement that the action is invariant.
"""

import torch

from ..lgt import group
from ..lgt.lattice import X_DIM, Y_DIM


def _reverse_along(links: torch.Tensor, dim: int) -> torch.Tensor:
    """Reflected link family along its own direction.

    With the site reflection sigma(x) = L-1-x, the new link at x runs from
    sigma(x) to sigma(x+1) = L-2-x, so U'(x) = U(L-2-x)^-1. Writing
    v = flip(U) (v[i] = U[L-1-i]) that is inverse(v[i+1]) -- a roll of -1.
    """
    return group.inverse(torch.roll(links.flip(dim), -1, dims=dim))


def transpose_xy(field: torch.Tensor) -> torch.Tensor:
    """Reflection about the diagonal: swap the two axes and the two families."""
    swapped = field.transpose(X_DIM, Y_DIM)
    ux, uy = swapped[..., 0, :, :, :], swapped[..., 1, :, :, :]
    return torch.stack([uy, ux], dim=-4)


def flip_x(field: torch.Tensor) -> torch.Tensor:
    ux, uy = field[..., 0, :, :, :], field[..., 1, :, :, :]
    return torch.stack([_reverse_along(ux, X_DIM), uy.flip(X_DIM)], dim=-4)


def flip_y(field: torch.Tensor) -> torch.Tensor:
    ux, uy = field[..., 0, :, :, :], field[..., 1, :, :, :]
    return torch.stack([ux.flip(Y_DIM), _reverse_along(uy, Y_DIM)], dim=-4)


def d4_element(field: torch.Tensor, k: int) -> torch.Tensor:
    """k in [0, 8): bit 0 = flip x, bit 1 = flip y, bit 2 = transpose."""
    out = field
    if k & 1:
        out = flip_x(out)
    if k & 2:
        out = flip_y(out)
    if k & 4:
        out = transpose_xy(out)
    return out


def random_d4(field: torch.Tensor, generator: torch.Generator | None = None) -> torch.Tensor:
    k = int(torch.randint(0, 8, (1,), generator=generator))
    return d4_element(field, k)
