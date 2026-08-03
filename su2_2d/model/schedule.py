"""Geometric noise schedule. sigma_max ~ 2.5 saturates the group (the heat
kernel is within ~1e-3 of Haar-uniform there); sigma_min is the endgame floor
carried over from the U(1) study's conventions."""

import torch


class GeometricNoiseSchedule:
    def __init__(self, sigma_min: float = 0.05, sigma_max: float = 2.5, n_steps: int = 60):
        self.sigma_min = sigma_min
        self.sigma_max = sigma_max
        self.n_steps = n_steps

    def sigmas(self, descending: bool = True) -> torch.Tensor:
        s = torch.logspace(
            torch.log10(torch.tensor(self.sigma_max)),
            torch.log10(torch.tensor(self.sigma_min)),
            self.n_steps,
        )
        return s if descending else s.flip(0)

    def sample_sigma(self, n: int, generator: torch.Generator | None = None) -> torch.Tensor:
        u = torch.rand(n, generator=generator)
        log_min = torch.log(torch.tensor(self.sigma_min))
        log_max = torch.log(torch.tensor(self.sigma_max))
        return torch.exp(log_min + u * (log_max - log_min))
