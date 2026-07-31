"""Ancestral (SMLD) sampling on the torus with optional Langevin correction.

The sampler is generic: it takes any callable score_fn(theta, sigma) -> score with
sigma a scalar tensor, so it serves both the toy 1D problem and the lattice model.
All states are wrapped to (-pi, pi] after every update; this is exact because both
the transition kernels and the score are periodic.
"""

import math

import torch

from .wrapped import wrap


@torch.no_grad()
def sample_ancestral(
    score_fn,
    shape: tuple[int, ...],
    sigmas: torch.Tensor,
    device="cpu",
    n_corrector_steps: int = 1,
    corrector_snr: float = 0.16,
    initial_state: torch.Tensor | None = None,
    step_callback=None,
) -> torch.Tensor:
    """sigmas: descending [n_steps] from ~sigma_max to sigma_min.

    step_callback(theta, sigma_next) -> theta, applied after each predictor +
    corrector block; use for deterministic projections that must act during the
    trajectory (e.g. topological-sector enforcement) rather than only at the end.
    """
    if initial_state is None:
        theta = torch.rand(shape, device=device) * (2 * math.pi) - math.pi
    else:
        theta = initial_state.clone().to(device)

    for i in range(len(sigmas)):
        sigma = sigmas[i]
        score = score_fn(theta, sigma)
        sigma_next = sigmas[i + 1] if i + 1 < len(sigmas) else sigmas[i] * 0.0
        step = sigma**2 - sigma_next**2
        noise_scale = torch.sqrt(torch.clamp(step * sigma_next**2 / sigma**2, min=0.0))
        theta = wrap(theta + step * score + noise_scale * torch.randn_like(theta))

        for _ in range(n_corrector_steps):
            score = score_fn(theta, sigma_next if sigma_next > 0 else sigma)
            z = torch.randn_like(theta)
            grad_norm = score.flatten(1).norm(dim=1).mean().clamp_min(1e-12)
            noise_norm = z.flatten(1).norm(dim=1).mean()
            eps = 2.0 * (corrector_snr * noise_norm / grad_norm) ** 2
            theta = wrap(theta + eps * score + torch.sqrt(2.0 * eps) * z)

        if step_callback is not None:
            theta = step_callback(theta, sigma_next)

    return theta
