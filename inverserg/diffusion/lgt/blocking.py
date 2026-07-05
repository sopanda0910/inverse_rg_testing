"""Forward 2x2 blocking and nonperturbative coarse-coupling matching.

Blocking rule (fixed, gauge covariant): a coarse link is the product of the two
straight fine links along the coarse path,
    Theta_x(X, Y) = wrap(theta_x(2X, 2Y) + theta_x(2X+1, 2Y))
    Theta_y(X, Y) = wrap(theta_y(2X, 2Y) + theta_y(2X, 2Y+1)).

With this rule the coarse plaquette angle equals the wrapped sum of the four fine
plaquette angles in the 2x2 cell (telescoping), so for the Villain action the
blocked theory is exactly Villain with beta' = beta / 4: Villain plaquettes are
i.i.d. wrapped Gaussians of variance 1/beta, and the sum of four has variance 4/beta.

For the Wilson action the blocked theory is not exactly Wilson; `match_coarse_beta`
determines beta' nonperturbatively by matching the blocked ensemble's mean plaquette
to the exact finite-volume Wilson-action plaquette on the coarse lattice.
"""

import torch
from scipy.optimize import brentq

from .lattice import wrap, plaquette_angles
from .exact import plaquette_exact


def block_links(field: torch.Tensor) -> torch.Tensor:
    """[B, 2, L, L] -> [B, 2, L/2, L/2] (also accepts unbatched [2, L, L])."""
    squeeze = field.dim() == 3
    if squeeze:
        field = field.unsqueeze(0)
    ux, uy = field[:, 0], field[:, 1]
    coarse_x = ux[:, 0::2, 0::2] + ux[:, 1::2, 0::2]
    coarse_y = uy[:, 0::2, 0::2] + uy[:, 0::2, 1::2]
    out = wrap(torch.stack([coarse_x, coarse_y], dim=1))
    return out.squeeze(0) if squeeze else out


def blocked_plaquette_from_fine(field: torch.Tensor) -> torch.Tensor:
    """Coarse plaquette angles computed directly as wrapped sums of fine plaquettes."""
    plaq = plaquette_angles(field)
    if plaq.dim() == 2:
        plaq = plaq.unsqueeze(0)
    cell_sum = (
        plaq[:, 0::2, 0::2] + plaq[:, 1::2, 0::2] + plaq[:, 0::2, 1::2] + plaq[:, 1::2, 1::2]
    )
    return wrap(cell_sum)


def villain_blocked_beta(beta: float) -> float:
    return beta / 4.0


def approx_matched_coarse_beta(fine_beta: float, action_type: str = "wilson") -> float:
    """Analytic estimate of the blocked coupling: plaquettes are i.i.d., so the
    blocked plaquette expectation is r_1(beta_f)^4; solve r_1(beta_c) = r_1(beta_f)^4.
    Exact for Villain (gives beta_f / 4); very accurate for Wilson."""
    target = plaquette_exact(fine_beta, action_type) ** 4

    def gap(beta: float) -> float:
        return plaquette_exact(beta, action_type) - target

    return float(brentq(gap, 1e-6, 4.0 * fine_beta, xtol=1e-8))


def approx_matched_fine_beta(coarse_beta: float, action_type: str = "wilson") -> float:
    """Inverse of approx_matched_coarse_beta: the fine coupling whose blocked theory
    lands on coarse_beta. Used to build consistent ladder beta schedules."""
    target = plaquette_exact(coarse_beta, action_type) ** 0.25

    def gap(beta: float) -> float:
        return plaquette_exact(beta, action_type) - target

    return float(brentq(gap, coarse_beta, 64.0 * (coarse_beta + 1.0), xtol=1e-8))


def match_coarse_beta(
    blocked_configs: torch.Tensor,
    action_type: str = "wilson",
    beta_bracket: tuple[float, float] = (1e-3, 256.0),
) -> float:
    """Find beta' such that a direct simulation on the coarse lattice reproduces the
    blocked ensemble's mean plaquette (matching against the exact finite-volume value)."""
    coarse_l = blocked_configs.shape[-1]
    target = float(torch.cos(plaquette_angles(blocked_configs)).mean())

    def gap(beta: float) -> float:
        return plaquette_exact(beta, action_type, coarse_l) - target

    lo, hi = beta_bracket
    return float(brentq(gap, lo, hi, xtol=1e-6))
