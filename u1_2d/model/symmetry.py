"""Exact lattice symmetries of the Wilson/Villain actions for link fields.

The score network is exactly gauge-invariant and translation-equivariant, but a
plain CNN is NOT equivariant under 90-degree rotations, reflections, or charge
conjugation (theta -> -theta), all of which are exact symmetries of the action.
These transforms let training symmetrize over them by augmentation.

Conventions (see lgt.lattice): field[..., mu, x, y] with mu=0 the x-link from
(x, y) to (x+1, y) and mu=1 the y-link from (x, y) to (x, y+1); dim -2 is x,
dim -1 is y.

Under the rotation R: (x, y) -> (-y, x) (orientation-preserving, Q -> Q):
    ty'[X, Y] = tx[Y, (-X) mod L]        (x-links become y-links)
    tx'[X, Y] = -ty[Y, (-X-1) mod L]     (y-links become reversed x-links)
Under the reflection M: (x, y) -> (-x, y) (orientation-reversing, Q -> -Q):
    tx'[X, Y] = -tx[(-X-1) mod L, Y]
    ty'[X, Y] = ty[(-X) mod L, Y]
Charge conjugation C: theta -> -theta (Q -> -Q).

None of these commute with the even-anchored 2x2 blocking (cells map to shifted
cells), so augmentation must recompute the coarse partner by re-blocking the
transformed fine field rather than transforming the stored coarse field.
"""

import torch


def charge_conjugate(field: torch.Tensor) -> torch.Tensor:
    return -field


def rotate90(field: torch.Tensor) -> torch.Tensor:
    """Rotate the link field by 90 degrees about the origin (Q preserved)."""
    tx = field[..., 0, :, :]
    ty = field[..., 1, :, :]
    new_ty = torch.roll(torch.flip(tx.transpose(-2, -1), dims=[-2]), shifts=1, dims=-2)
    new_tx = -torch.flip(ty.transpose(-2, -1), dims=[-2])
    return torch.stack([new_tx, new_ty], dim=-3)


def reflect_x(field: torch.Tensor) -> torch.Tensor:
    """Reflect x -> -x (Q flips sign)."""
    tx = field[..., 0, :, :]
    ty = field[..., 1, :, :]
    new_tx = -torch.flip(tx, dims=[-2])
    new_ty = torch.roll(torch.flip(ty, dims=[-2]), shifts=1, dims=-2)
    return torch.stack([new_tx, new_ty], dim=-3)


def random_symmetry(field: torch.Tensor, generator: torch.Generator | None = None) -> torch.Tensor:
    """Apply a uniformly random element of the D4 x C symmetry group (16 elements)."""
    draws = torch.randint(0, 4, (3,), generator=generator)
    for _ in range(int(draws[0])):
        field = rotate90(field)
    if int(draws[1]) % 2:
        field = reflect_x(field)
    if int(draws[2]) % 2:
        field = charge_conjugate(field)
    return field
