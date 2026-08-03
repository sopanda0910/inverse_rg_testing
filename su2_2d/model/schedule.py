"""Geometric noise schedule with the beta-aware floor and small-sigma bias
carried over from the U(1) study.

sigma_max ~ 2.5 saturates the group (the heat kernel is within ~1e-3 of
Haar-uniform there). The FLOOR must scale with the coupling: equilibrium link
fluctuations are ~1/sqrt(beta), so a fixed floor is far above the physical
scale at large beta and the endgame is never trained where it matters. U(1)
found this to be the fix for its raw-seed wall, plus oversampling small sigma
at large beta (high_beta_sigma_bias) -- both reproduced here.
"""

import math

import torch


class GeometricNoiseSchedule:
    def __init__(self, sigma_min: float = 0.05, sigma_max: float = 2.5, n_steps: int = 60,
                 sigma_min_beta_coef: float | None = 0.3):
        self.sigma_min = sigma_min
        self.sigma_max = sigma_max
        self.n_steps = n_steps
        self.sigma_min_beta_coef = sigma_min_beta_coef

    def effective_sigma_min(self, beta=None):
        """min(sigma_min, coef / sqrt(beta)) -- the physical fluctuation scale."""
        if beta is None or self.sigma_min_beta_coef is None:
            return torch.as_tensor(self.sigma_min, dtype=torch.float32)
        b = torch.as_tensor(beta, dtype=torch.float32).clamp_min(1e-6)
        return torch.minimum(torch.full_like(b, self.sigma_min),
                             self.sigma_min_beta_coef / b.sqrt())

    def sigmas(self, descending: bool = True, beta=None) -> torch.Tensor:
        lo = float(self.effective_sigma_min(beta).min())
        s = torch.logspace(math.log10(self.sigma_max), math.log10(lo), self.n_steps)
        return s if descending else s.flip(0)

    def sample_sigma(self, n: int, generator: torch.Generator | None = None,
                     beta=None, high_beta_bias: float = 0.0) -> torch.Tensor:
        """Log-uniform in [effective_sigma_min(beta), sigma_max].

        high_beta_bias > 0 skews the draw toward the small-sigma end, more
        strongly at large beta (u -> u^(1+bias*log10(beta)/2)); the endgame is
        where the deployed density gap lives.
        """
        u = torch.rand(n, generator=generator)
        lo = self.effective_sigma_min(beta)
        if lo.dim() == 0:
            lo = lo.expand(n)
        if high_beta_bias > 0 and beta is not None:
            b = torch.as_tensor(beta, dtype=torch.float32).clamp_min(1.0).expand(n)
            u = u ** (1.0 + high_beta_bias * torch.log10(b) / 2.0)
        log_min = torch.log(lo)
        log_max = math.log(self.sigma_max)
        return torch.exp(log_min + u * (log_max - log_min))
