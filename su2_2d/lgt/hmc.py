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


def adapted_hmc_params(beta: float, lattice_size: int = 8, traj_length: float = 2.0):
    """Initial (step, n_leapfrog) at fixed trajectory length.

    The integrator error per link grows with the force (~beta) and the
    accept/reject compares a TOTAL dH summed over 2 L^2 links, so the usable
    step shrinks with BOTH coupling and volume: dH ~ step^4 * V * beta^2 for a
    2nd-order integrator, hence step ~ (V beta^2)^(-1/4). Ignoring the volume
    factor is what produced 3% acceptance at L=16, beta=16 (measured); these
    are only starting values -- `run_hmc_ensemble` tunes from here.
    """
    volume = 2.0 * lattice_size * lattice_size
    step = 0.25 * ((128.0 / volume) * (2.0 / max(beta, 0.5)) ** 2) ** 0.25
    step = min(step, 0.25)
    n = max(4, int(round(traj_length / step)))
    return step, n


def tune_step_size(field, beta, step_size, n_steps, generator, target=0.75,
                   n_probe=12, n_rounds=8, traj_length=2.0):
    """Adapt the step to a target acceptance, keeping trajectory length fixed.

    Returns (step, n_leapfrog, field, measured_acceptance). Tuning happens
    during burn-in and is frozen before production, so the production chain is
    a fixed exact-MCMC kernel (adapting on the fly would break detailed
    balance)."""
    for _ in range(n_rounds):
        accs = []
        for _ in range(n_probe):
            field, acc = hmc_step(field, beta, step_size, n_steps, generator)
            accs.append(float(acc.float().mean()))
        measured = sum(accs) / len(accs)
        if measured > target + 0.15:
            step_size *= 1.3
        elif measured < target - 0.10:
            step_size *= 0.7
        else:
            return step_size, n_steps, field, measured
        step_size = min(step_size, 0.25)
        n_steps = max(4, int(round(traj_length / step_size)))
    return step_size, n_steps, field, measured


def run_hmc_ensemble(lattice_size, beta, n_configs, n_chains=8, burn_in=200,
                     thin=5, step_size=None, n_steps=None, seed=None,
                     hot_start=True, tune=True, min_acceptance=0.5):
    """Returns ([n_configs, 2, L, L, 4], acceptance_rate) from parallel chains.

    hot_start (Haar-random links) is the DEFAULT here, unlike the U(1)
    package: from a cold start at large beta the initial forces are large
    enough that acceptance collapses (measured 0.00-0.38 at L=16, beta=16) and
    the chain never leaves the ordered corner, silently producing
    non-equilibrium "data". Hot chains relax onto the exact plaquette within
    ~100 trajectories at the same coupling.

    Raises if the post-burn-in acceptance falls below min_acceptance: bad
    ensembles must fail loudly rather than reach a training set.
    """
    gen = torch.Generator()
    if seed is not None:
        gen.manual_seed(seed)
    if step_size is None or n_steps is None:
        step_size, n_steps = adapted_hmc_params(beta, lattice_size)
    field = (group.random_haar((n_chains, 2, lattice_size, lattice_size), generator=gen)
             if hot_start else group.identity((n_chains, 2, lattice_size, lattice_size)))
    if tune:
        step_size, n_steps, field, _ = tune_step_size(
            field, beta, step_size, n_steps, gen)
    for _ in range(burn_in):
        field, _ = hmc_step(field, beta, step_size, n_steps, gen)
    accs, out = [], []
    while len(out) * n_chains < n_configs:
        for _ in range(thin):
            field, acc = hmc_step(field, beta, step_size, n_steps, gen)
            accs.append(acc.float().mean())
        out.append(field.clone())
    acceptance = float(torch.stack(accs).mean())
    if acceptance < min_acceptance:
        raise RuntimeError(
            f"HMC acceptance {acceptance:.2f} < {min_acceptance} at L={lattice_size}, "
            f"beta={beta} (step {step_size:.4f}, {n_steps} leapfrog): ensemble "
            "is not trustworthy, refusing to return it")
    configs = torch.cat(out, dim=0)[:n_configs]
    return configs, acceptance
