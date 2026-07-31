"""Forward 2x2 blocking and nonperturbative coarse-coupling matching.

Blocking rule (fixed, gauge covariant): a coarse link is the product of the two
straight fine links along the coarse path,
    Theta_x(X, Y) = wrap(theta_x(2X, 2Y) + theta_x(2X+1, 2Y))
    Theta_y(X, Y) = wrap(theta_y(2X, 2Y) + theta_y(2X, 2Y+1)).

With this rule the coarse plaquette angle equals the wrapped sum of the four fine
plaquette angles in the 2x2 cell (telescoping), so for the Villain action the
blocked theory is exactly Villain with beta' = beta / 4: Villain plaquettes are
i.i.d. wrapped Gaussians of variance 1/beta, and the sum of four has variance 4/beta.

For the Wilson action the blocked theory is not exactly Wilson, but it is exactly
known: distinct coarse plaquettes sum disjoint sets of i.i.d. fine plaquettes, so
the blocked theory is again a single-plaquette theory whose character ratios are
    r_q(blocked) = r_q(beta_f)^4   for every charge q      (`blocked_character_exact`).
A single Wilson coupling beta' can reproduce only a one-parameter slice of this.

Why matching the MEAN PLAQUETTE (and nothing else) is the right one-parameter choice:
the Wilson weight exp(beta cos theta_p) is a one-parameter exponential family whose
sufficient statistic is sum_p cos theta_p, so the beta' that matches <cos theta_p>
is exactly the maximum-likelihood fit of a Wilson model to the blocked ensemble,
i.e. the minimum-KL (information) projection of the true blocked theory onto the
Wilson family. Matching any other observable instead (r_2, chi_t, distribution
shape, ...) yields a Wilson theory strictly farther from the blocked theory in KL,
and it sacrifices r_1 -- which controls every fundamental Wilson loop
(<W(A)> = r_1^A), all Creutz ratios, and the string tension sigma = -log r_1.

What mean-plaquette matching CANNOT fix is the Wilson family itself: residuals in
r_{q>=2}, in the topological susceptibility, and in the plaquette-angle
distribution shape are irreducible within one coupling. `matching_residuals`
quantifies them exactly (no simulation); `scripts/10_beta_matching_study.py`
maps them across the project's coupling range. They fall rapidly with beta_f
(chi_t residual ~5e-2 at beta_f = 4, ~1.6e-2 at 14.15, ~5e-4 at 55) and peak in
the crossover region beta_f ~ 5-6.5.
"""

import math

import numpy as np
import torch
from scipy.optimize import brentq, minimize_scalar

from .lattice import wrap, plaquette_angles
from .exact import (
    TWO_PI,
    blocked_plaquette_angle_density,
    plaquette_angle_density,
    plaquette_character_exact,
    plaquette_exact,
    topological_susceptibility_exact,
)


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


def blocked_character_exact(fine_beta: float, q: int, action_type: str = "wilson") -> float:
    """Exact character ratio of the blocked theory: wrapped convolution of four
    i.i.d. plaquettes multiplies character coefficients, so r_q -> r_q(beta_f)^4."""
    return plaquette_character_exact(fine_beta, q, action_type) ** 4


def approx_matched_coarse_beta(fine_beta: float, action_type: str = "wilson") -> float:
    """Analytic estimate of the blocked coupling: plaquettes are i.i.d., so the
    blocked plaquette expectation is r_1(beta_f)^4; solve r_1(beta_c) = r_1(beta_f)^4.

    Exact for Villain (gives beta_f / 4). For Wilson this is the infinite-volume
    maximum-likelihood / minimum-KL projection onto the Wilson family (see module
    docstring); the irreducible family error is reported by `matching_residuals`.
    """
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
    n_characters: int = 1,
) -> float:
    """Fit the coarse coupling beta' to a blocked ensemble.

    Default (n_characters=1): match the ensemble mean plaquette to the exact
    finite-volume value. This is the maximum-likelihood fit of the Wilson model
    to the blocked configurations (exponential family, sufficient statistic
    sum_p cos theta_p), hence also the minimum-KL projection -- see module
    docstring for why no other single observable should replace it.

    n_characters > 1: least-squares over the first n plaquette characters
    <cos(q Theta_P)>, q = 1..n, against their exact finite-volume values. This
    trades fundamental-Wilson-loop accuracy for distribution-shape accuracy;
    `matching_residuals` gives the exact size of that tradeoff. Provided as a
    diagnostic alternative, not as the pipeline default.
    """
    coarse_l = blocked_configs.shape[-1]
    angles = plaquette_angles(blocked_configs)
    lo, hi = beta_bracket
    if n_characters <= 1:
        target = float(torch.cos(angles).mean())

        def gap(beta: float) -> float:
            return plaquette_exact(beta, action_type, coarse_l) - target

        return float(brentq(gap, lo, hi, xtol=1e-6))

    qs = range(1, n_characters + 1)
    targets = np.array([float(torch.cos(q * angles).mean()) for q in qs])

    def char_sse(beta: float) -> float:
        preds = np.array(
            [plaquette_character_exact(beta, q, action_type, coarse_l) for q in qs]
        )
        return float(((preds - targets) ** 2).sum())

    result = minimize_scalar(char_sse, bounds=(lo, hi), method="bounded", options={"xatol": 1e-8})
    return float(result.x)


def matching_residuals(
    fine_beta: float, action_type: str = "wilson", n_characters: int = 3
) -> dict:
    """Simulation-free error budget of describing the blocked theory by a single
    matched Wilson-type coupling (infinite volume).

    The r_1-matched beta' reproduces r_1 -- hence every fundamental Wilson loop,
    all Creutz ratios, and the string tension -- exactly. Returned are the
    quantities one coupling cannot also fix:
        matched_beta          r_1-matched coarse coupling
        character_residuals   {q: r_q(beta') / r_q(beta_f)^4 - 1} for q = 2..n
        chi_t_residual        chi_t(beta') / chi_t(blocked) - 1
        ks_distance           sup-norm CDF distance between the Wilson(beta') and
                              exact blocked plaquette-angle densities

    For the Villain action the family is closed under blocking and every residual
    vanishes (up to quadrature error).
    """
    target = plaquette_exact(fine_beta, action_type) ** 4
    matched = float(
        brentq(
            lambda b: plaquette_exact(b, action_type) - target,
            1e-8,
            max(4.0 * fine_beta, 1.0),
            xtol=1e-10,
        )
    )
    character_residuals = {
        q: plaquette_character_exact(matched, q, action_type)
        / blocked_character_exact(fine_beta, q, action_type)
        - 1.0
        for q in range(2, n_characters + 1)
    }
    grid = np.linspace(-math.pi, math.pi, 8001)
    f_blocked = blocked_plaquette_angle_density(grid, fine_beta, action_type)
    f_matched = plaquette_angle_density(grid, matched, action_type)
    step = grid[1] - grid[0]
    cdf_blocked = np.cumsum(f_blocked) * step
    cdf_matched = np.cumsum(f_matched) * step
    ks = float(np.abs(cdf_blocked / cdf_blocked[-1] - cdf_matched / cdf_matched[-1]).max())
    chi_blocked = float(
        np.trapezoid((grid / TWO_PI) ** 2 * f_blocked, grid) / np.trapezoid(f_blocked, grid)
    )
    chi_matched = topological_susceptibility_exact(matched, action_type)
    return {
        "matched_beta": matched,
        "character_residuals": character_residuals,
        "chi_t_residual": chi_matched / chi_blocked - 1.0,
        "ks_distance": ks,
    }
