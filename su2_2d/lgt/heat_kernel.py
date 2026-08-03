"""Exact heat kernel on SU(2) — the non-abelian counterpart of the wrapped
Gaussian that made U(1) DSM exact.

With half-angle theta (U = exp(i theta n.sigma), theta in [0, pi]) and the
Laplace-Beltrami operator built from T_a = sigma_a/2 (Casimir j(j+1)), the
kernel at diffusion time s = sigma^2, as a density w.r.t. normalized Haar
measure, is the character sum

    K_s(theta) = sum_{n>=1} n [sin(n theta) / sin(theta)] exp(-s (n^2 - 1) / 8).

TWO REPRESENTATIONS (the U(1) package's wrapped-normal trick, carried over).
The character sum needs ~14/sqrt(s) terms, so it is expensive exactly where
training spends most of its time (small sigma). Poisson summation gives the
dual form, with a = s/8:

    K_s(theta) = e^a sqrt(pi/a) / (4 a sin theta)
                 * sum_k (theta + 2 pi k) exp(-(theta + 2 pi k)^2 / (4a)),

which converges in ~3 terms for small s (the k = 0 Gaussian has width
sqrt(s)/2 in theta, i.e. sqrt(s) in |omega| -- the flat-space limit, as it
must be). Dispatch: dual below s = 1, characters above. The two agree to
~1e-9 in the overlap (tested).

The exact conditional score of U_t = exp(i (omega.sigma)/2) U_0 in the
left-tangent coordinates used everywhere in this package is

    score_a = (1/2) (d/dtheta log K_s)(theta) n_hat_a,

because the derivative of the class angle along T_a is D_a theta = n_hat_a/2.
All entry points accept a per-sample sigma tensor so training never loops.
"""

import math

import torch

from . import group

# Crossover chosen inside the region where the two representations agree to
# ~1e-12; BELOW s ~ 0.5 the character sum is not merely slow but WRONG in
# float64 (it must produce e^{-theta^2/4a} ~ e^{-900} by cancelling terms of
# size 1e3), so the dual form is the only correct branch there.
_DUAL_MAX_S = 2.0
_K_WIND = 3


def _as_tensor(s, like: torch.Tensor) -> torch.Tensor:
    if not torch.is_tensor(s):
        return torch.full_like(like, float(s))
    return s.to(like.dtype).expand_as(like) if s.numel() == 1 else s


def _j2_max(s_min: float) -> int:
    return max(6, int(math.ceil(14.0 / math.sqrt(max(s_min, 1e-8)))))


def _log_kernel_character(theta: torch.Tensor, s: torch.Tensor) -> torch.Tensor:
    n_max = _j2_max(float(s.min()))
    n = torch.arange(1, n_max + 2, dtype=theta.dtype, device=theta.device)
    n = n.view(*([1] * theta.dim()), -1)
    th = theta.unsqueeze(-1)
    ss = s.unsqueeze(-1)
    terms = n * torch.sin(n * th) / torch.sin(th) * torch.exp(-ss * (n**2 - 1) / 8.0)
    return torch.log(terms.sum(dim=-1).clamp_min(1e-300))


def _log_kernel_dual(theta: torch.Tensor, s: torch.Tensor) -> torch.Tensor:
    a = s / 8.0
    k = torch.arange(-_K_WIND, _K_WIND + 1, dtype=theta.dtype, device=theta.device)
    k = k.view(*([1] * theta.dim()), -1)
    th = theta.unsqueeze(-1)
    aa = a.unsqueeze(-1)
    shifted = th + 2.0 * math.pi * k
    # factor out the k = 0 Gaussian so nothing underflows at tiny s
    expo = -(shifted**2 - th**2) / (4.0 * aa)
    bracket = (shifted * torch.exp(expo)).sum(dim=-1)
    return (a
            + 0.5 * torch.log(math.pi / a)
            - torch.log(4.0 * a)
            - torch.log(torch.sin(theta))
            - theta**2 / (4.0 * a)
            + torch.log(bracket.abs().clamp_min(1e-300)))


def log_kernel(theta: torch.Tensor, s) -> torch.Tensor:
    theta = theta.clamp(1e-6, math.pi - 1e-6)
    s = _as_tensor(s, theta).clamp_min(1e-8)
    small = s < _DUAL_MAX_S
    if bool(small.all()):
        return _log_kernel_dual(theta, s)
    if not bool(small.any()):
        return _log_kernel_character(theta, s)
    return torch.where(small, _log_kernel_dual(theta, s), _log_kernel_character(theta, s))


def kernel_value(theta: torch.Tensor, s) -> torch.Tensor:
    return torch.exp(log_kernel(theta, s))


def dlog_kernel_dtheta(theta: torch.Tensor, s) -> torch.Tensor:
    """d/dtheta log K_s(theta), by autograd through whichever representation
    is active (cheap: the dual form is 7 terms)."""
    with torch.enable_grad():
        t = theta.detach().clone().requires_grad_(True)
        (grad,) = torch.autograd.grad(log_kernel(t, s).sum(), t)
    return grad


def sample_angle(s, shape, generator: torch.Generator | None = None) -> torch.Tensor:
    """Sample the class angle from the density prop to K_s(theta) sin^2(theta).

    s is a scalar or a tensor of shape [B] matching shape[0] -- ONE diffusion
    time per configuration, not per link. Only B inverse-CDF grids are built
    and every link of a configuration is drawn from its own grid in a single
    batched searchsorted (building a grid per link would be ~500x the work at
    L = 16).
    """
    n_grid = 1024
    grid = torch.linspace(1e-5, math.pi - 1e-5, n_grid, dtype=torch.float64)
    shape = tuple(shape)
    n_total = 1
    for d in shape:
        n_total *= d
    if torch.is_tensor(s) and s.numel() > 1:
        s_vec = s.reshape(-1).double()
        assert s_vec.numel() == shape[0], "sample_angle expects one sigma per configuration"
        per = n_total // shape[0]
    else:
        # a single diffusion time shared by everything: ONE grid, not one per
        # element (the sampler and the tests both call it this way)
        val = float(s) if not torch.is_tensor(s) else float(s.reshape(-1)[0])
        s_vec = torch.full((1,), val, dtype=torch.float64)
        per = n_total
    b = s_vec.numel()

    g = grid.view(1, -1).expand(b, -1)
    dens = kernel_value(g, s_vec.view(-1, 1).expand_as(g)) * torch.sin(g) ** 2
    cdf = torch.cumsum(dens.clamp_min(0.0), dim=-1)
    cdf = (cdf / cdf[:, -1:].clamp_min(1e-300)).contiguous()

    u = torch.rand(b, per, generator=generator, dtype=torch.float64)
    idx = torch.searchsorted(cdf, u).clamp(1, n_grid - 1)
    c0 = torch.gather(cdf, 1, idx - 1)
    c1 = torch.gather(cdf, 1, idx)
    lo, hi = grid[idx - 1], grid[idx]
    frac = ((u - c0) / (c1 - c0).clamp_min(1e-30)).clamp(0.0, 1.0)
    return (lo + frac * (hi - lo)).reshape(shape).float()


def exact_conditional_score(u_t: torch.Tensor, u_0: torch.Tensor, sigma) -> torch.Tensor:
    """Score of the heat-kernel conditional at u_t given u_0, in the
    left-multiplication tangent coordinates (curves e^{i t sigma_a/2} U) used
    by the HMC, the score head and the sampler: [..., 3].

    The relative element must be the LEFT one, X = u_t u_0^-1 (the class angle
    is the same either way, but the axis differs by Ad(u_t)). sigma may be a
    per-sample tensor broadcastable over the leading dimensions.
    """
    x = group.mul(u_t, group.inverse(u_0))
    omega = group.logmap(x)
    norm = omega.norm(dim=-1, keepdim=True)
    theta = (norm / 2.0).clamp(1e-5, math.pi - 1e-5)
    n_hat = omega / norm.clamp_min(1e-12)
    if torch.is_tensor(sigma):
        s = (sigma**2).reshape(*sigma.shape, *([1] * (theta.dim() - sigma.dim())))
        s = s.expand_as(theta)
    else:
        s = float(sigma) ** 2
    return 0.5 * dlog_kernel_dtheta(theta, s) * n_hat
