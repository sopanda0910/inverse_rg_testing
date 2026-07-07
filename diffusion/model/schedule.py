"""Geometric (variance-exploding) noise schedule for wrapped diffusion.

sigma(t) = sigma_min * (sigma_max / sigma_min)^t for t in [0, 1]. sigma_max is chosen
large enough that the wrapped Gaussian is uniform on the circle to high accuracy
(the q-th Fourier coefficient is exp(-q^2 sigma^2 / 2); sigma = 6 gives ~1e-8).
"""

import math

import torch


class GeometricNoiseSchedule:
    def __init__(self, sigma_min: float = 0.02, sigma_max: float = 6.0) -> None:
        if sigma_min <= 0 or sigma_max <= sigma_min:
            raise ValueError("Require 0 < sigma_min < sigma_max")
        self.sigma_min = sigma_min
        self.sigma_max = sigma_max

    def sigma(self, t: torch.Tensor) -> torch.Tensor:
        return self.sigma_min * (self.sigma_max / self.sigma_min) ** t

    def sample_sigma(self, batch: int, device) -> torch.Tensor:
        t = torch.rand(batch, device=device)
        return self.sigma(t)

    def discrete_sigmas(self, n_steps: int, device=None) -> torch.Tensor:
        """Descending sigmas for ancestral sampling, sigma_max -> sigma_min."""
        ratios = torch.linspace(1.0, 0.0, n_steps, device=device)
        log_range = math.log(self.sigma_max) - math.log(self.sigma_min)
        return torch.exp(math.log(self.sigma_min) + ratios * log_range)
