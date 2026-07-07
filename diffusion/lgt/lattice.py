"""Lattice utilities for 2D compact U(1).

Conventions (identical to the parent `inverserg` package):
    theta[mu, x, y] or theta[B, mu, x, y]; mu=0 are x-links, mu=1 are y-links.
    dims -2 is x, dims -1 is y.
    plaquette(x, y) = ux(x,y) + uy(x+1,y) - ux(x,y+1) - uy(x,y), wrapped to (-pi, pi].
"""

import math

import torch

from inverserg.lattice import (
    plaquette_angles,
    rectangle_x_angles,
    rectangle_y_angles,
    wilson_loop_angles,
    mean_plaquette,
    regularize,
)

TWO_PI = 2.0 * math.pi


def wrap(theta: torch.Tensor) -> torch.Tensor:
    """Map angles to (-pi, pi]."""
    return regularize(theta)


def _as_batched(field: torch.Tensor) -> tuple[torch.Tensor, bool]:
    if field.dim() == 3:
        return field.unsqueeze(0), True
    if field.dim() != 4:
        raise ValueError(f"Expected [2, L, L] or [B, 2, L, L], got {tuple(field.shape)}")
    return field, False


def topological_charge_float(field: torch.Tensor) -> torch.Tensor:
    """Sum of wrapped plaquette angles / 2*pi (should be an integer up to fp error)."""
    return plaquette_angles(field).sum(dim=(-2, -1)) / TWO_PI


def topological_charge(field: torch.Tensor) -> torch.Tensor:
    return torch.round(topological_charge_float(field))


def gauge_transform(field: torch.Tensor, alpha: torch.Tensor) -> torch.Tensor:
    """theta_mu(x) -> theta_mu(x) + alpha(x) - alpha(x + mu_hat).

    alpha has shape [L, L] or [B, L, L].
    """
    field, squeezed = _as_batched(field)
    if alpha.dim() == 2:
        alpha = alpha.unsqueeze(0)
    ux = field[:, 0] + alpha - torch.roll(alpha, shifts=-1, dims=-2)
    uy = field[:, 1] + alpha - torch.roll(alpha, shifts=-1, dims=-1)
    out = wrap(torch.stack([ux, uy], dim=1))
    return out.squeeze(0) if squeezed else out


def random_gauge_transform(field: torch.Tensor, generator: torch.Generator | None = None) -> torch.Tensor:
    field_b, squeezed = _as_batched(field)
    batch, _, lattice, _ = field_b.shape
    alpha = (
        torch.rand((batch, lattice, lattice), device=field.device, generator=generator) * TWO_PI
        - math.pi
    )
    out = gauge_transform(field_b, alpha)
    return out.squeeze(0) if squeezed else out


def polyakov_loop_angles(field: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Wrapped winding-loop angles: x-direction loops (per y) and y-direction loops (per x)."""
    field, squeezed = _as_batched(field)
    loop_x = wrap(field[:, 0].sum(dim=-2))
    loop_y = wrap(field[:, 1].sum(dim=-1))
    if squeezed:
        return loop_x.squeeze(0), loop_y.squeeze(0)
    return loop_x, loop_y


def plaquette_correlator(field: torch.Tensor, max_distance: int) -> torch.Tensor:
    """Connected two-point correlator of cos(plaquette) at separations 1..max_distance
    along the x axis, averaged over sites (and batch if present). Returns [max_distance]."""
    plaq = torch.cos(plaquette_angles(field))
    if plaq.dim() == 2:
        plaq = plaq.unsqueeze(0)
    mean = plaq.mean()
    centered = plaq - mean
    corr = []
    for distance in range(1, max_distance + 1):
        shifted = torch.roll(centered, shifts=-distance, dims=-2)
        corr.append((centered * shifted).mean())
    return torch.stack(corr)
