"""Wrapped-Gaussian (heat-kernel) diffusion primitives on the circle.

The forward process perturbs each angle with wrapped Gaussian noise:
    theta_t = wrap(theta_0 + sigma(t) * z),  z ~ N(0, 1).

The transition kernel is the wrapped normal
    K_sigma(d) = sum_k N(d + 2 pi k; 0, sigma^2),  d = wrap(theta_t - theta_0),
whose score (d/d theta_t) log K is a winding-weighted average:
    score = -sum_k w_k (d + 2 pi k) / sigma^2,  w_k = softmax_k(-(d + 2 pi k)^2 / (2 sigma^2)).

As sigma -> large the kernel converges to the uniform distribution on the circle,
so the terminal distribution of the forward process is uniform (no data information).
"""

import math

import torch

TWO_PI = 2.0 * math.pi


def wrap(theta: torch.Tensor) -> torch.Tensor:
    return torch.atan2(torch.sin(theta), torch.cos(theta))


def _windings(sigma_max: float, device, dtype) -> torch.Tensor:
    n_wind = max(1, int(math.ceil((4.0 * sigma_max + math.pi) / TWO_PI)))
    return torch.arange(-n_wind, n_wind + 1, device=device, dtype=dtype) * TWO_PI


def sample_wrapped_normal(mean: torch.Tensor, sigma: torch.Tensor) -> torch.Tensor:
    return wrap(mean + sigma * torch.randn_like(mean))


def wrapped_normal_score(delta: torch.Tensor, sigma: torch.Tensor) -> torch.Tensor:
    """d/d(delta) log K_sigma(delta). `sigma` broadcasts against `delta`."""
    ks = _windings(float(torch.as_tensor(sigma).max()), delta.device, delta.dtype)
    shifted = delta.unsqueeze(-1) + ks
    sigma_e = torch.as_tensor(sigma, device=delta.device, dtype=delta.dtype)
    while sigma_e.dim() < delta.dim():
        sigma_e = sigma_e.unsqueeze(-1)
    log_w = -shifted.square() / (2.0 * sigma_e.unsqueeze(-1).square())
    weights = torch.softmax(log_w, dim=-1)
    return -(weights * shifted).sum(dim=-1) / sigma_e.square()


def wrapped_normal_log_density(delta: torch.Tensor, sigma: torch.Tensor) -> torch.Tensor:
    ks = _windings(float(torch.as_tensor(sigma).max()), delta.device, delta.dtype)
    shifted = delta.unsqueeze(-1) + ks
    sigma_e = torch.as_tensor(sigma, device=delta.device, dtype=delta.dtype)
    while sigma_e.dim() < delta.dim():
        sigma_e = sigma_e.unsqueeze(-1)
    log_norm = -0.5 * math.log(TWO_PI) - torch.log(sigma_e)
    return torch.logsumexp(-shifted.square() / (2.0 * sigma_e.unsqueeze(-1).square()), dim=-1) + log_norm
