"""Batched HMC for 2D U(2), on the group manifold.

Same shape as `u1_2d.lgt.hmc`: an Omelyan integrator running many independent
chains vectorized over the batch, with per-chain Metropolis accept/reject. The
differences are all group-theoretic:

* momenta live in u(2) = R^4 per link (one central u(1) direction, three su(2)),
  drawn as unit Gaussians. The coordinates are orthonormal for the metric
  <X, Y> = -(1/2) Tr(XY), so the kinetic term is the plain sum of squares;
* the position update is left multiplication U -> exp(eps p) U, not addition;
* the force is dS/da at a = 0 of S(exp(a) U), computed ANALYTICALLY from the
  staple environment M = U Sigma (see `lattice.link_environment`):

      F_0 = beta Im M_0,   F_j = beta Re M_j,   j = 1, 2, 3

  in complex-quaternion coordinates, using Tr M = 2 M_0 and Tr(sigma_j M) =
  2 i M_j. This is exact -- it agrees with autograd to 1e-15 -- and avoids
  building a graph through the whole plaquette chain every leapfrog step.

The optional `topological_updates` flag adds the determinant winding move of
`local_updates.winding_update`, which is what keeps <Q^2> correct at couplings
where the local dynamics is frozen.
"""

import math
from dataclasses import dataclass, field

import numpy as np
import torch

from .lattice import (
    identity_links,
    link_environment,
    mean_plaquette,
    random_links,
    topological_charge,
    u2_exp,
    u2_mul,
    u2_normalize,
)

OMELYAN_LAMBDA = 0.1931833


def adapted_hmc_params(
    beta: float,
    base_step_size: float = 0.2,
    base_n_steps: int = 5,
    reference_beta: float = 8.0,
) -> tuple[float, int]:
    """Scale the step with the force magnitude (~sqrt(beta)) at fixed trajectory
    length, so acceptance stays high at any coupling. `reference_beta` is twice
    the U(1) value because the U(2) coupling is roughly four times the U(1) one
    (see `lgt.exact.matched_u1_beta`) while the force also carries the extra
    three su(2) directions."""
    scale = min(1.0, math.sqrt(reference_beta / max(beta, reference_beta)))
    return base_step_size * scale, int(round(base_n_steps / scale))


@dataclass
class HMCStats:
    acceptance_rate: float = 0.0
    winding_acceptance_rate: float | None = None
    plaquette_history: list[float] = field(default_factory=list)
    topological_charge_history: list[np.ndarray] = field(default_factory=list)


def u2_force(links: torch.Tensor, beta: float) -> torch.Tensor:
    """+dS/da for S = -beta sum_p (1/2) ReTr P; shape [..., 2, L, L, 4]."""
    m = link_environment(links)
    return beta * torch.stack([m[..., 0].imag, m[..., 1].real,
                               m[..., 2].real, m[..., 3].real], dim=-1)


class BatchedHMCU2:
    def __init__(
        self,
        lattice_size: int,
        action,
        n_chains: int = 8,
        n_steps: int = 5,
        step_size: float = 0.2,
        device: str = "cpu",
        hot_start: bool = False,
        topological_updates: bool = False,
        winding_charge_step: int = 2,
        winding_interval: int = 1,
        winding_su2_sweeps: int = 25,
    ) -> None:
        self.lattice_size = lattice_size
        self.action = action
        self.n_chains = n_chains
        self.n_steps = n_steps
        self.step_size = step_size
        self.device = torch.device(device)
        self.hot_start = hot_start
        self.topological_updates = topological_updates
        self.winding_charge_step = winding_charge_step
        self.winding_interval = max(1, int(winding_interval))
        # The ONE approximation in the marginal odd move: after an accepted
        # winding the SU(2) sector is resampled from its exact conditional,
        # but only for finitely many sweeps, and only on ACCEPTED
        # configurations. Rejected ones keep an equilibrium sample, so an
        # under-converged resample penalises exactly the moves that flip
        # parity. Exposed so it can be scanned rather than assumed.
        self.winding_su2_sweeps = int(winding_su2_sweeps)
        self._step_counter = 0
        self.last_winding_accept: torch.Tensor | None = None

    def initialize(self, hot: bool | None = None) -> torch.Tensor:
        if hot is None:
            hot = self.hot_start
        if hot:
            return random_links(self.lattice_size, batch=self.n_chains, device=self.device)
        return identity_links(self.lattice_size, batch=self.n_chains, device=self.device)

    def force(self, links: torch.Tensor) -> torch.Tensor:
        return u2_force(links, self.action.beta)

    def omelyan(self, links: torch.Tensor, momenta: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        lam, dt = OMELYAN_LAMBDA, self.step_size
        momenta = momenta - lam * dt * self.force(links)
        for step in range(self.n_steps):
            links = u2_mul(u2_exp(0.5 * dt * momenta), links)
            momenta = momenta - (1.0 - 2.0 * lam) * dt * self.force(links)
            links = u2_mul(u2_exp(0.5 * dt * momenta), links)
            if step != self.n_steps - 1:
                momenta = momenta - 2.0 * lam * dt * self.force(links)
        momenta = momenta - lam * dt * self.force(links)
        return u2_normalize(links), momenta

    def metropolis_step(self, links: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        momenta = torch.randn(links.shape[:-1] + (4,), device=links.device, dtype=links.dtype)
        old_h = self.action.per_config(links) + 0.5 * momenta.square().sum(dim=(1, 2, 3, 4))
        new_links, new_momenta = self.omelyan(links.clone(), momenta)
        new_h = self.action.per_config(new_links) + 0.5 * new_momenta.square().sum(dim=(1, 2, 3, 4))
        accept = torch.rand(links.shape[0], device=links.device) < torch.exp(old_h - new_h)
        links = torch.where(accept.view(-1, 1, 1, 1, 1), new_links, links)
        self.last_winding_accept = None
        self._step_counter += 1
        if self.topological_updates and self._step_counter % self.winding_interval == 0:
            from .local_updates import winding_update

            links, winding_accept = winding_update(
                links, self.action, charge_step=self.winding_charge_step,
                n_su2_sweeps=self.winding_su2_sweeps)
            self.last_winding_accept = winding_accept
        return links, accept

    def sample(
        self,
        n_samples_per_chain: int,
        burn_in: int = 100,
        thin: int = 5,
        initial_state: torch.Tensor | None = None,
        record_history: bool = False,
    ) -> tuple[torch.Tensor, HMCStats]:
        """Returns ([n_samples_per_chain * n_chains, 2, L, L, 5], stats).

        Samples are chain-major within each draw, so per-chain time series come
        back as samples.view(n_draws, n_chains, ...) -- same contract as `u1_2d`.
        """
        links = (self.initialize() if initial_state is None
                 else initial_state.clone().to(self.device))
        stats = HMCStats()
        accepted = total = 0
        winding_accepted = winding_total = 0
        draws = []
        with torch.no_grad():
            for _ in range(burn_in):
                links, _ = self.metropolis_step(links)
            for _ in range(n_samples_per_chain):
                for _ in range(thin):
                    links, accept = self.metropolis_step(links)
                    accepted += int(accept.sum())
                    total += accept.numel()
                    if self.last_winding_accept is not None:
                        winding_accepted += int(self.last_winding_accept.sum())
                        winding_total += self.last_winding_accept.numel()
                draws.append(links.clone())
                if record_history:
                    stats.plaquette_history.append(float(mean_plaquette(links)))
                    stats.topological_charge_history.append(
                        topological_charge(links).cpu().numpy()
                    )
        stats.acceptance_rate = accepted / max(total, 1)
        if winding_total > 0:
            stats.winding_acceptance_rate = winding_accepted / winding_total
        return torch.cat(draws, dim=0), stats


def run_hmc_ensemble(
    lattice_size: int,
    action,
    n_configs: int,
    n_chains: int = 8,
    burn_in: int = 100,
    thin: int = 5,
    n_steps: int = 5,
    step_size: float = 0.2,
    device: str = "cpu",
    record_history: bool = False,
    topological_updates: bool = False,
    hot_start: bool = False,
    winding_charge_step: int = 2,
    winding_interval: int = 1,
    winding_su2_sweeps: int = 25,
    initial_state: torch.Tensor | None = None,
) -> tuple[torch.Tensor, HMCStats]:
    """Convenience wrapper. NOTE (device convention, inherited from `u1_2d`): this
    is the one function that returns tensors on its `device`; ensembles everywhere
    else are CPU-resident. Normalize the output before it meets anything else."""
    n_per_chain = (n_configs + n_chains - 1) // n_chains
    sampler = BatchedHMCU2(
        lattice_size,
        action,
        n_chains=n_chains,
        n_steps=n_steps,
        step_size=step_size,
        device=device,
        hot_start=hot_start,
        topological_updates=topological_updates,
        winding_charge_step=winding_charge_step,
        winding_interval=winding_interval,
        winding_su2_sweeps=winding_su2_sweeps,
    )
    configs, stats = sampler.sample(
        n_per_chain, burn_in=burn_in, thin=thin, record_history=record_history,
        initial_state=initial_state,
    )
    return configs[:n_configs], stats
