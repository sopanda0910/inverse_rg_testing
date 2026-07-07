"""Batched HMC for 2D compact U(1).

Same Omelyan integrator and conventions as `inverserg.hmc.HMCU1Sampler`, but runs
many independent Markov chains vectorized over the batch dimension (essential on
CPU) with per-chain Metropolis accept/reject.
"""

import math
from dataclasses import dataclass, field

import numpy as np
import torch

from .lattice import wrap, mean_plaquette, topological_charge

OMELYAN_LAMBDA = 0.1931833


def adapted_hmc_params(
    beta: float,
    base_step_size: float = 0.1,
    base_n_steps: int = 10,
    reference_beta: float = 4.0,
) -> tuple[float, int]:
    """Scale the leapfrog step with the force magnitude (~sqrt(beta)) at large beta,
    keeping trajectory length constant, so acceptance stays high at any coupling."""
    scale = min(1.0, math.sqrt(reference_beta / max(beta, reference_beta)))
    return base_step_size * scale, int(round(base_n_steps / scale))


@dataclass
class HMCStats:
    acceptance_rate: float = 0.0
    plaquette_history: list[float] = field(default_factory=list)
    topological_charge_history: list[np.ndarray] = field(default_factory=list)


class BatchedHMC:
    def __init__(
        self,
        lattice_size: int,
        action,
        n_chains: int = 8,
        n_steps: int = 10,
        step_size: float = 0.1,
        device: str = "cpu",
        hot_start: bool = False,
        topological_updates: bool = False,
    ) -> None:
        self.lattice_size = lattice_size
        self.action = action
        self.n_chains = n_chains
        self.n_steps = n_steps
        self.step_size = step_size
        self.device = torch.device(device)
        self.hot_start = hot_start
        self.topological_updates = topological_updates

    def initialize(self, hot: bool | None = None) -> torch.Tensor:
        if hot is None:
            hot = self.hot_start
        shape = (self.n_chains, 2, self.lattice_size, self.lattice_size)
        if hot:
            return torch.rand(shape, device=self.device) * (2 * torch.pi) - torch.pi
        return torch.zeros(shape, device=self.device)

    def force(self, theta: torch.Tensor) -> torch.Tensor:
        with torch.enable_grad():
            theta = theta.detach().clone().requires_grad_(True)
            total = self.action.per_config(theta).sum()
            (grad,) = torch.autograd.grad(total, theta)
        return grad.detach()

    def omelyan(self, theta: torch.Tensor, pi: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        lam, dt = OMELYAN_LAMBDA, self.step_size
        pi = pi - lam * dt * self.force(theta)
        for step in range(self.n_steps):
            theta = theta + 0.5 * dt * pi
            pi = pi - (1.0 - 2.0 * lam) * dt * self.force(theta)
            theta = theta + 0.5 * dt * pi
            if step != self.n_steps - 1:
                pi = pi - 2.0 * lam * dt * self.force(theta)
        pi = pi - lam * dt * self.force(theta)
        return wrap(theta), pi

    def metropolis_step(self, theta: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        pi = torch.randn_like(theta)
        old_h = self.action.per_config(theta) + 0.5 * pi.square().sum(dim=(1, 2, 3))
        theta_new, pi_new = self.omelyan(theta.clone(), pi)
        new_h = self.action.per_config(theta_new) + 0.5 * pi_new.square().sum(dim=(1, 2, 3))
        accept = torch.rand(theta.shape[0], device=self.device) < torch.exp(old_h - new_h)
        mask = accept.view(-1, 1, 1, 1)
        theta = torch.where(mask, theta_new, theta)
        if self.topological_updates:
            from .local_updates import topological_update

            theta, _ = topological_update(theta, self.action)
        return theta, accept

    def sample(
        self,
        n_samples_per_chain: int,
        burn_in: int = 100,
        thin: int = 5,
        initial_state: torch.Tensor | None = None,
        record_history: bool = False,
    ) -> tuple[torch.Tensor, HMCStats]:
        """Returns ([n_samples_per_chain * n_chains, 2, L, L], stats).

        Samples are ordered chain-major within each draw so that per-chain time series
        can be recovered as samples.view(n_draws, n_chains, ...).
        """
        theta = self.initialize() if initial_state is None else initial_state.clone().to(self.device)
        stats = HMCStats()
        accepted = 0
        total = 0
        draws = []
        with torch.no_grad():
            for _ in range(burn_in):
                theta, accept = self.metropolis_step(theta)
                accepted += int(accept.sum())
                total += accept.numel()
            for _ in range(n_samples_per_chain):
                for _ in range(thin):
                    theta, accept = self.metropolis_step(theta)
                    accepted += int(accept.sum())
                    total += accept.numel()
                draws.append(theta.clone())
                if record_history:
                    stats.plaquette_history.append(float(mean_plaquette(theta)))
                    stats.topological_charge_history.append(
                        topological_charge(theta).cpu().numpy()
                    )
        stats.acceptance_rate = accepted / max(total, 1)
        return torch.cat(draws, dim=0), stats


def run_hmc_ensemble(
    lattice_size: int,
    action,
    n_configs: int,
    n_chains: int = 8,
    burn_in: int = 100,
    thin: int = 5,
    n_steps: int = 10,
    step_size: float = 0.1,
    device: str = "cpu",
    record_history: bool = False,
    topological_updates: bool = False,
    hot_start: bool = False,
) -> tuple[torch.Tensor, HMCStats]:
    n_per_chain = (n_configs + n_chains - 1) // n_chains
    sampler = BatchedHMC(
        lattice_size,
        action,
        n_chains=n_chains,
        n_steps=n_steps,
        step_size=step_size,
        device=device,
        hot_start=hot_start,
        topological_updates=topological_updates,
    )
    configs, stats = sampler.sample(
        n_per_chain, burn_in=burn_in, thin=thin, record_history=record_history
    )
    return configs[:n_configs], stats
