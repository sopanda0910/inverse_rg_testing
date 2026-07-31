"""Geometric (variance-exploding) noise schedule for wrapped diffusion.

sigma(t) = sigma_min * (sigma_max / sigma_min)^t for t in [0, 1]. sigma_max is chosen
large enough that the wrapped Gaussian is uniform on the circle to high accuracy
(the q-th Fourier coefficient is exp(-q^2 sigma^2 / 2); sigma = 6 gives ~1e-8).

With sigma_min_beta_coef set, the floor becomes beta-aware:
sigma_min(beta) = min(sigma_min, coef / sqrt(beta)). Physical link fluctuations
scale like 1/sqrt(beta), so a fixed floor stops resolving the target distribution
once 1/sqrt(beta) approaches sigma_min (beta ~ 200 for the 0.03 default); the
beta-scaled floor keeps sigma_min a fixed fraction of the physical width instead.
"""

import math

import torch


class GeometricNoiseSchedule:
    def __init__(
        self,
        sigma_min: float = 0.02,
        sigma_max: float = 6.0,
        sigma_min_beta_coef: float | None = None,
    ) -> None:
        if sigma_min <= 0 or sigma_max <= sigma_min:
            raise ValueError("Require 0 < sigma_min < sigma_max")
        self.sigma_min = sigma_min
        self.sigma_max = sigma_max
        self.sigma_min_beta_coef = sigma_min_beta_coef

    def effective_sigma_min(self, beta=None):
        """Scalar or per-sample floor; beta may be None, float, or a tensor."""
        if self.sigma_min_beta_coef is None or beta is None:
            return self.sigma_min
        if isinstance(beta, torch.Tensor):
            scaled = self.sigma_min_beta_coef / beta.float().sqrt()
            return scaled.clamp(max=self.sigma_min)
        return min(self.sigma_min, self.sigma_min_beta_coef / math.sqrt(beta))

    def sigma(self, t: torch.Tensor, beta=None) -> torch.Tensor:
        low = self.effective_sigma_min(beta)
        if isinstance(low, torch.Tensor):
            low = low.to(t.device)
        return low * (self.sigma_max / low) ** t

    def sample_sigma(self, batch: int, device, beta=None, high_beta_bias: float = 0.0) -> torch.Tensor:
        """Draw training noise levels sigma(t), t ~ U[0, 1].

        high_beta_bias > 0 oversamples small sigma where beta is large: t is
        raised to the power k(beta) = 1 + bias * log1p(beta / 4), concentrating
        draws near t = 0 (the small-sigma end). Rationale: the v6 raw-seed wall
        was traced to small-sigma score accuracy at high beta, where the target
        distribution is narrow (width ~ 1/sqrt(beta)) but uniform-t training
        rarely visits the sigmas that resolve it.
        """
        t = torch.rand(batch, device=device)
        if isinstance(beta, torch.Tensor):
            beta = beta.to(device)
        if high_beta_bias > 0.0 and beta is not None:
            if isinstance(beta, torch.Tensor):
                b = beta.float()
            else:
                b = torch.full((batch,), float(beta), device=device)
            k = 1.0 + high_beta_bias * torch.log1p(b / 4.0)
            t = t ** k
        return self.sigma(t, beta=beta)

    def discrete_sigmas(self, n_steps: int, device=None, beta=None) -> torch.Tensor:
        """Descending sigmas for ancestral sampling, sigma_max -> sigma_min(beta)."""
        low = self.effective_sigma_min(beta)
        if isinstance(low, torch.Tensor):
            low = float(low)
        ratios = torch.linspace(1.0, 0.0, n_steps, device=device)
        log_range = math.log(self.sigma_max) - math.log(low)
        return torch.exp(math.log(low) + ratios * log_range)
