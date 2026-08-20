"""Forward 2x2 blocking of 2D U(2) and nonperturbative coarse-coupling matching.

Blocking rule (fixed, gauge covariant): a coarse link is the ORDERED product of
the two straight fine links along the coarse path,

    V_0(X, Y) = U_0(2X, 2Y) U_0(2X+1, 2Y)
    V_1(X, Y) = U_1(2X, 2Y) U_1(2X, 2Y+1),

which is the U(2) reading of the `u1_2d.lgt.blocking` rule (there the product is
a sum of angles because the group commutes).

TWO THINGS SURVIVE THE MOVE TO A NON-ABELIAN GROUP, AND THEY ARE WHY THIS PROJECT
IS SHAPED THE WAY IT IS.

1. The determinant telescope is EXACT. det is a homomorphism, so
   det(coarse plaquette) = product of the four fine plaquette determinants
   regardless of ordering or conjugation. The coarse determinant plaquette angle
   is therefore the wrapped sum of the four fine ones, exactly as in U(1), and
   Q_coarse = Q_fine up to wrap events. Topological charge transport across an
   inverse-RG step is an identity here, not an approximation.
   (The SU(2) part of the coarse plaquette is a product of conjugated fine SU(2)
   plaquettes -- no such statement, and none is needed.)

2. Tree-level, beta_c = beta_f / 4, in every one of the four u(2) directions. The
   coarse plaquette is a product of four fine ones, so at weak coupling the
   algebra elements add and the variance quadruples. That is the same relation
   the determinant sector obeys exactly and the same one U(1) obeys, so a single
   ladder schedule serves the whole theory.

Nonperturbatively the blocked theory is not Wilson U(2), but -- as in U(1) -- it
is exactly known: distinct coarse plaquettes are built from disjoint sets of
i.i.d. fine plaquettes, so every character ratio maps as r_R -> r_R(beta_f)^4
(`blocked_character_exact`). One Wilson coupling reproduces one of them.
Matching r_fund (equivalently the mean plaquette) is the maximum-likelihood fit,
because the Wilson weight exp(beta sum_p (1/2)ReTr P) is a one-parameter
exponential family whose sufficient statistic is sum_p (1/2)ReTr P; so it is also
the minimum-KL projection onto the Wilson family, and it is what fixes the
fundamental Wilson loops and the string tension. `matching_residuals` prices what
it cannot fix.
"""

import numpy as np
import torch
from scipy.optimize import brentq

from .exact import (
    character_coefficients,
    det_character_exact,
    det_topological_susceptibility,
    plaquette_exact,
    wilson_loop_exact,
)
from .lattice import (
    det_phase,
    half_retr,
    plaquette,
    su2_exp,
    su2_log,
    u2_mul,
    wrap,
)


def block_links(links: torch.Tensor) -> torch.Tensor:
    """[B, 2, L, L, 5] -> [B, 2, L/2, L/2, 5] (also accepts unbatched [2, L, L, 5])."""
    squeeze = links.dim() == 4
    if squeeze:
        links = links.unsqueeze(0)
    u0, u1 = links[:, 0], links[:, 1]
    coarse_x = u2_mul(u0[:, 0::2, 0::2], u0[:, 1::2, 0::2])
    coarse_y = u2_mul(u1[:, 0::2, 0::2], u1[:, 0::2, 1::2])
    out = torch.stack([coarse_x, coarse_y], dim=1)
    return out.squeeze(0) if squeeze else out


def blocked_det_plaquette_from_fine(links: torch.Tensor) -> torch.Tensor:
    """Coarse determinant plaquette angles as wrapped sums of the four fine ones.

    Equal to `det_phase(plaquette(block_links(links)))` identically -- that
    equality is the exact telescope, and `scripts/09_verify_identities.py` checks
    it numerically because it is the load-bearing fact of the whole design.
    """
    alpha = det_phase(plaquette(links))
    if alpha.dim() == 2:
        alpha = alpha.unsqueeze(0)
    cell = (alpha[:, 0::2, 0::2] + alpha[:, 1::2, 0::2]
            + alpha[:, 0::2, 1::2] + alpha[:, 1::2, 1::2])
    return wrap(cell)


def half_link(links: torch.Tensor) -> torch.Tensor:
    """The geodesic square root of each link: H with H H = U, phase halved.

    Used by the naive SU(2) inverse blocking, where splitting a coarse link into
    two identical halves reproduces the blocked product exactly.
    """
    return torch.cat([0.5 * links[..., :1], su2_exp(0.5 * su2_log(links[..., 1:]))], dim=-1)


def tree_level_coarse_beta(fine_beta: float) -> float:
    return fine_beta / 4.0


def blocked_character_exact(fine_beta: float, two_j: int = 1, charge: int = 1) -> float:
    """Exact character ratio of the blocked theory: r_R -> r_R(beta_f)^4."""
    return wilson_loop_exact(fine_beta, 4, two_j=two_j, charge=charge)


def approx_matched_coarse_beta(fine_beta: float) -> float:
    """Infinite-volume blocked coupling: solve r_fund(beta_c) = r_fund(beta_f)^4."""
    target = plaquette_exact(fine_beta) ** 4
    return float(brentq(lambda b: plaquette_exact(b) - target, 1e-6, 4.0 * fine_beta + 10.0,
                        xtol=1e-9))


def approx_matched_fine_beta(coarse_beta: float) -> float:
    """Inverse of `approx_matched_coarse_beta`, for building ladder schedules."""
    target = plaquette_exact(coarse_beta) ** 0.25
    return float(brentq(lambda b: plaquette_exact(b) - target, coarse_beta,
                        64.0 * (coarse_beta + 1.0), xtol=1e-9))


def topology_matched_fine_beta(coarse_beta: float, coarse_size: int) -> float:
    """Fine coupling that preserves the exact finite-volume <Q^2> across one step.

    The ladder's usual criterion (`approx_matched_fine_beta`) matches the mean
    PLAQUETTE, which is the right thing for the local action but leaves <Q^2>
    drifting: from L = 8, beta = 14 the exact value falls 6.9% by L = 64. That
    drift is a systematic the ladder cannot correct, because an inverse-RG step
    transports topological charge as an IDENTITY -- whatever P(Q) the base has is
    what every rung above it gets. Matching <Q^2> instead makes the transported
    value correct by construction and leaves only the base's statistical error.

    The two criteria nearly agree and diverge only on small lattices, where the
    determinant-sector P(Q) is still outside its asymptotic regime: starting from
    L = 8, beta = 14 they differ by 5.2% at the first step, 1.2% at the second and
    0.3% at the third. Preferring this one costs a slightly different coupling and
    buys an unbiased <Q^2>; which matters depends on whether the study's claim is
    about the action or about topology.
    """
    target = det_topological_susceptibility(coarse_beta, coarse_size) * coarse_size ** 2
    fine_size = 2 * coarse_size

    def gap(beta: float) -> float:
        return det_topological_susceptibility(beta, fine_size) * fine_size ** 2 - target

    return float(brentq(gap, coarse_beta, 64.0 * (coarse_beta + 1.0), xtol=1e-9))


def topology_matched_schedule(base_beta: float, base_size: int, n_rungs: int) -> list[float]:
    """`n_rungs` successive fine couplings, each preserving the exact <Q^2>."""
    schedule, beta, size = [], base_beta, base_size
    for _ in range(n_rungs):
        beta = topology_matched_fine_beta(beta, size)
        size *= 2
        schedule.append(beta)
    return schedule


def match_coarse_beta(
    blocked_configs: torch.Tensor, beta_bracket: tuple[float, float] = (1e-3, 1024.0)
) -> float:
    """Fit the coarse coupling to a blocked ensemble by matching the mean plaquette
    to its exact finite-volume value (the maximum-likelihood / minimum-KL fit)."""
    coarse_l = blocked_configs.shape[-2]
    target = float(half_retr(plaquette(blocked_configs)).mean())
    lo, hi = beta_bracket
    return float(brentq(lambda b: plaquette_exact(b, coarse_l) - target, lo, hi, xtol=1e-6))


def match_det_coarse_beta(
    blocked_configs: torch.Tensor, beta_bracket: tuple[float, float] = (1e-3, 1024.0)
) -> float:
    """Fit the coarse U(2) coupling from the DETERMINANT sector alone, by matching
    <cos alpha_p>. Useful as a cross-check: if the determinant-sector fit and the
    full-trace fit of `match_coarse_beta` disagree, the blocked ensemble is not
    well described by any single Wilson coupling -- which is exactly the residual
    that `matching_residuals` prices analytically."""
    from u1_2d.lgt.lattice import plaquette_angles

    target = float(torch.cos(plaquette_angles(det_links_of(blocked_configs))).mean())
    lo, hi = beta_bracket
    return float(brentq(lambda b: det_character_exact(b, 1) - target, lo, hi, xtol=1e-6))


def det_links_of(links: torch.Tensor) -> torch.Tensor:
    from .lattice import det_links

    return det_links(links)


def matching_residuals(fine_beta: float, two_j_values: tuple[int, ...] = (0, 2, 3)) -> dict:
    """Simulation-free error budget for describing the blocked theory with one
    Wilson U(2) coupling (infinite volume).

    The r_fund-matched beta' reproduces every fundamental Wilson loop and the
    string tension exactly. Returned are the things one coupling cannot also fix:
    ratios r_R(beta') / r_R(beta_f)^4 for other irreps R, and the same quantity
    for the determinant sector's higher characters.
    """
    matched = approx_matched_coarse_beta(fine_beta)
    js, ks, _ = character_coefficients(fine_beta, two_j_max=4)
    residuals = {}
    for two_j in two_j_values:
        charge = 2 if (two_j % 2 == 0 and two_j == 0) else two_j
        if not ((js == two_j) & (ks == charge)).any():
            continue
        blocked = blocked_character_exact(fine_beta, two_j=two_j, charge=charge)
        if abs(blocked) < 1e-300:
            continue
        residuals[f"2j={two_j},k={charge}"] = (
            wilson_loop_exact(matched, 1, two_j=two_j, charge=charge) / blocked - 1.0
        )
    det_residuals = {
        q: det_character_exact(matched, q) / det_character_exact(fine_beta, q) ** 4 - 1.0
        for q in (2, 3)
    }
    return {
        "matched_beta": matched,
        "tree_level_ratio": matched / tree_level_coarse_beta(fine_beta),
        "character_residuals": residuals,
        "det_character_residuals": det_residuals,
    }


def ladder_charge_fixed_point(coarse_beta: float, coarse_size: int, n_rungs: int = 4) -> list[dict]:
    """<Q^2> along the beta_f = 4 beta_c, L_f = 2 L_c ladder.

    The U(1) study's ladder invariant carries over: the determinant sector's
    exact finite-volume <Q^2> is (nearly) a fixed point of the ladder, so the
    coarse ensemble's P(Q) IS the fine theory's P(Q) and climbing the ladder is a
    continuum-limit trajectory at fixed physical volume. Deviations here are the
    honest U(2) measure of how far the determinant sector is from Villain.
    """
    from .exact import det_topological_susceptibility

    out = []
    beta, size = float(coarse_beta), int(coarse_size)
    for rung in range(n_rungs):
        out.append({
            "rung": rung,
            "beta": beta,
            "lattice_size": size,
            "q_squared": det_topological_susceptibility(beta, size) * size * size,
        })
        beta, size = 4.0 * beta, 2 * size
    return out
