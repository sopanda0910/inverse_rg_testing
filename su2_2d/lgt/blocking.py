"""2x2 blocking for SU(2) links: the coarse link is the path-ordered product
of the two fine links it spans (non-abelian counterpart of the U(1) angle
sum), evaluated on even anchor sites."""

import torch
from scipy.optimize import brentq

from . import group
from .exact import plaquette_exact
from .lattice import X_DIM, Y_DIM


def matched_coarse_beta(fine_beta: float, n_block: int = 2) -> float:
    """Coarse coupling whose plaquette equals the blocked fine plaquette.

    In 2D the blocked plaquette IS the fine n_block x n_block Wilson loop, and
    plaquettes decouple, so the matching condition is exact and closed-form:

        p(beta_c) = p(beta_f) ** (n_block ** 2),    p(b) = I_2(b) / I_1(b).

    No MLE/character fitting is needed (the U(1) package had to fit, having no
    such identity). Tree level (beta_f / n_block^2) is a poor substitute and
    gets worse toward weak coupling: at beta_f = 16 it gives 4.000 vs the
    exact 4.305, and at beta_f = 2 it gives 0.500 vs 0.141. Conditioning a
    lift on a tree-level coarse ensemble is a train/test mismatch -- the model
    is trained on blocked fine configs, which follow the matched coupling.
    """
    target = plaquette_exact(fine_beta) ** (n_block**2)
    return float(brentq(lambda b: plaquette_exact(b) - target, 1e-4, fine_beta))


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
