"""Exact heat kernel on SU(2) — the non-abelian counterpart of the wrapped
Gaussian that made U(1) DSM exact.

With half-angle theta (U = exp(i theta n.sigma), theta in [0, pi]) and the
Laplace-Beltrami operator built from T_a = sigma_a/2 (Casimir j(j+1)), the
kernel at diffusion time s = sigma^2, as a density w.r.t. normalized Haar
measure, is the character sum

    K_s(theta) = sum_j (2j+1) chi_j(theta) exp(-s j (j+1) / 2),
    chi_j(theta) = sin((2j+1) theta) / sin(theta),   j = 0, 1/2, 1, ...

Small s needs many terms: cutoff 2j_max ~ 14 / sqrt(s). The exact conditional
score of U_t = U_0 exp(i (omega.sigma)/2), in the right-tangent coordinates
used everywhere in this package, is

    score_a = (1/2) (d/dtheta log K_s)(theta) n_hat_a,

because the derivative of the class angle along T_a is D_a theta = n_hat_a/2.
"""

import math

import torch

from . import group


def _j2_max(s: float) -> int:
    return max(6, int(math.ceil(14.0 / math.sqrt(max(s, 1e-8)))))


def kernel_value(theta: torch.Tensor, s: float) -> torch.Tensor:
    """K_s(theta), stable at theta -> 0 and pi (series limit of chi_j)."""
    theta = theta.clamp(1e-6, math.pi - 1e-6)
    out = torch.zeros_like(theta)
    for j2 in range(0, _j2_max(s) + 1):
        n = j2 + 1
        casimir = 0.25 * j2 * (j2 + 2)
        out = out + n * torch.sin(n * theta) / torch.sin(theta) * math.exp(-0.5 * s * casimir)
    return out


def log_kernel(theta: torch.Tensor, s: float) -> torch.Tensor:
    return torch.log(kernel_value(theta, s).clamp_min(1e-300))


def sample_angle(s: float, shape, generator: torch.Generator | None = None) -> torch.Tensor:
    """Sample the class angle from the density prop to K_s(theta) sin^2(theta)
    on [0, pi] by dense inverse-CDF."""
    grid = torch.linspace(1e-5, math.pi - 1e-5, 4096, dtype=torch.float64)
    dens = kernel_value(grid, s).clamp_min(0.0) * torch.sin(grid) ** 2
    cdf = torch.cumsum(dens, dim=0)
    cdf = cdf / cdf[-1]
    u = torch.rand(shape, generator=generator, dtype=torch.float64)
    idx = torch.searchsorted(cdf, u.reshape(-1)).clamp(1, len(grid) - 1)
    c0, c1 = cdf[idx - 1], cdf[idx]
    frac = ((u.reshape(-1) - c0) / (c1 - c0).clamp_min(1e-30)).clamp(0.0, 1.0)
    theta = grid[idx - 1] + frac * (grid[idx] - grid[idx - 1])
    return theta.reshape(shape).float()


def exact_conditional_score(u_t: torch.Tensor, u_0: torch.Tensor, sigma: float) -> torch.Tensor:
    """Score of the heat-kernel conditional at u_t given u_0, in the
    left-multiplication tangent coordinates (curves e^{i t sigma_a/2} U) used
    by the HMC and the score head: [..., 3].

    The relative element must be the LEFT one, X = u_t u_0^-1 (the class angle
    is the same either way, but the axis differs by Ad(u_t)): along
    e^{i t sigma_a/2} u_t the displacement of X is d theta = n_hat_a(X)/2.
    """
    s = sigma * sigma
    x = group.mul(u_t, group.inverse(u_0))
    omega = group.logmap(x)
    theta = (omega.norm(dim=-1, keepdim=True) / 2.0).clamp(1e-5, math.pi - 1e-5)
    n_hat = omega / omega.norm(dim=-1, keepdim=True).clamp_min(1e-12)
    # enable_grad: this internal derivative must work even when the caller
    # evaluates targets under torch.no_grad() (e.g. EMA validation)
    with torch.enable_grad():
        t = theta.detach().reshape(-1).requires_grad_(True)
        (dlogk,) = torch.autograd.grad(log_kernel(t, s).sum(), t)
    dlogk = dlogk.reshape(theta.shape)
    return 0.5 * dlogk * n_hat
