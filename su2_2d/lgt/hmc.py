"""Group-manifold HMC for SU(2) links: Gaussian momenta in the algebra,
expmap leapfrog with left multiplication, autograd forces, exact Metropolis."""

import math

import torch

from . import group
from .lattice import wilson_action, wilson_force


def _kinetic(pi: torch.Tensor) -> torch.Tensor:
    return 0.5 * (pi**2).sum(dim=(-4, -3, -2, -1))


def leapfrog(field, pi, beta, step_size, n_steps):
    pi = pi + 0.5 * step_size * wilson_force(field, beta)
    for k in range(n_steps):
        field = group.normalize(group.mul(group.expmap(step_size * pi), field))
        force = wilson_force(field, beta)
        pi = pi + (step_size if k < n_steps - 1 else 0.5 * step_size) * force
    return field, pi


def hmc_step(field, beta, step_size, n_steps, generator=None):
    pi = torch.randn(*field.shape[:-1], 3, generator=generator)
    h0 = _kinetic(pi) + wilson_action(field, beta)
    new_field, new_pi = leapfrog(field, pi, beta, step_size, n_steps)
    h1 = _kinetic(new_pi) + wilson_action(new_field, beta)
    accept = torch.rand(h0.shape, generator=generator) < torch.exp((h0 - h1).clamp(max=0.0))
    mask = accept.view(-1, *([1] * (field.dim() - 1)))
    out = torch.where(mask, new_field, field)
    return out, accept


def adapted_hmc_params(beta: float, base_step: float = 0.25, base_steps: int = 8):
    """Shrink the step with the fluctuation scale ~ 1/sqrt(beta)."""
    scale = min(1.0, math.sqrt(2.0 / max(beta, 2.0)))
    return base_step * scale, max(base_steps, int(round(base_steps / scale)))


def run_hmc_ensemble(lattice_size, beta, n_configs, n_chains=8, burn_in=200,
                     thin=5, step_size=None, n_steps=None, seed=None):
    """Returns ([n_configs, 2, L, L, 4], acceptance_rate) from parallel chains,
    cold start (identity links)."""
    gen = torch.Generator()
    if seed is not None:
        gen.manual_seed(seed)
    if step_size is None or n_steps is None:
        step_size, n_steps = adapted_hmc_params(beta)
    field = group.identity((n_chains, 2, lattice_size, lattice_size))
    accs = []
    for _ in range(burn_in):
        field, acc = hmc_step(field, beta, step_size, n_steps, gen)
    out = []
    while len(out) * n_chains < n_configs:
        for _ in range(thin):
            field, acc = hmc_step(field, beta, step_size, n_steps, gen)
            accs.append(acc.float().mean())
        out.append(field.clone())
    configs = torch.cat(out, dim=0)[:n_configs]
    return configs, float(torch.stack(accs).mean())
