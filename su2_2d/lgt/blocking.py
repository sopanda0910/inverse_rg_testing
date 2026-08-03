"""2x2 blocking for SU(2) links: the coarse link is the path-ordered product
of the two fine links it spans (non-abelian counterpart of the U(1) angle
sum), evaluated on even anchor sites."""

import torch

from . import group
from .lattice import X_DIM, Y_DIM


def block_links(field: torch.Tensor) -> torch.Tensor:
    """[..., 2, L, L, 4] -> [..., 2, L/2, L/2, 4]."""
    squeeze = field.dim() == 4
    if squeeze:
        field = field.unsqueeze(0)
    ux, uy = field[..., 0, :, :, :], field[..., 1, :, :, :]
    cx = group.mul(ux, torch.roll(ux, -1, X_DIM))[..., 0::2, 0::2, :]
    cy = group.mul(uy, torch.roll(uy, -1, Y_DIM))[..., 0::2, 0::2, :]
    out = torch.stack([cx, cy], dim=-4)
    return out.squeeze(0) if squeeze else out
