"""Differentiable probability-flow ODE likelihood for score fine-tuning.

Two training objectives built on one differentiable Heun integrator:

  * Tier 2 (maximum likelihood, `ml_conditional_log_likelihood`): maximize
    E_data[log q(fine | coarse)] over HMC pairs -- FFJORD-style CNF training
    of the pretrained score. This directly optimizes the quantity the ESS
    weights measure (log q enters the weights as -log q), so every log-unit
    of improvement in mean log q is a log-unit off the weight spread.
  * Tier 3 (reverse KL, `reverse_kl_terms`): sample the flow differentiably
    and minimize E_q[S(x) + log q(x)] = KL(q || p) + const. Needs no data,
    directly maximizes ESS, but is mode-seeking (can collapse Q sectors) --
    keep a DSM anchor and monitor P(Q) symmetry.

The gradient of the divergence term is second-order (grad of a vjp), so the
integrator builds the full graph: memory scales with n_steps * batch * net
size. With the campaign net (hidden 56, depth 4) at L=16, batch 4 and ~24
steps fit comfortably in RAM without gradient checkpointing; halve the batch
before reaching for fancier machinery. Fine-tuning uses FEWER, hence coarser,
steps than evaluation -- the gradient signal survives discretization error
that would matter for quoting likelihoods.

The score trained here is the same *effective* score deployed at sampling
time (model + exact-score blend + consistency guidance): the blend/guidance
terms carry no parameters but shape where the model's own output matters, so
training through them optimizes exactly the deployed proposal q.
"""

import math

import torch

from .likelihood import _effective_score_fn
from .wrapped import wrap


def _drift_and_div_diff(score_fn, x, sigma, n_probes: int):
    """Differentiable (drift, -sigma * div s): Hutchinson vjps with
    create_graph=True so the divergence carries parameter gradients."""
    s = score_fn(x, sigma)
    div = torch.zeros(x.shape[0], device=x.device)
    for _ in range(n_probes):
        v = torch.randint(0, 2, x.shape, device=x.device, dtype=x.dtype) * 2 - 1
        (grad_x,) = torch.autograd.grad((s * v).sum(), x, create_graph=True)
        div = div + (grad_x * v).flatten(1).sum(dim=1)
    div = div / n_probes
    return -sigma * s, -sigma * div


def integrate_with_divergence(
    score_fn, x_init: torch.Tensor, sigmas: torch.Tensor, n_probes: int = 1
) -> tuple[torch.Tensor, torch.Tensor]:
    """Differentiable Heun integration along `sigmas` (ascending OR descending).

    Returns (x_final, acc) with acc = int (div f) dsigma along the traversal
    direction. Gradients flow through both the trajectory and the divergence."""
    x = x_init if x_init.requires_grad else x_init.detach().requires_grad_(True)
    acc = torch.zeros(x.shape[0], device=x.device)
    for i in range(len(sigmas) - 1):
        sig0 = sigmas[i]
        sig1 = sigmas[i + 1]
        h = sig1 - sig0
        f0, d0 = _drift_and_div_diff(score_fn, x, sig0, n_probes)
        x_pred = wrap(x + h * f0)
        f1, d1 = _drift_and_div_diff(score_fn, x_pred, sig1, n_probes)
        x = wrap(x + 0.5 * h * (f0 + f1))
        acc = acc + 0.5 * h * (d0 + d1)
    return x, acc


def ml_conditional_log_likelihood(
    model,
    schedule,
    coarse: torch.Tensor,
    fine: torch.Tensor,
    beta_target: float,
    n_steps: int = 24,
    n_probes: int = 1,
    consistency_weight: float = 1.0,
    physics_blend_coef: float = 0.0,
    physics_blend_beta_min: float = 0.0,
    device: str = "cpu",
) -> torch.Tensor:
    """Differentiable log q(fine_i | coarse_i) per config (Tier 2 objective:
    minimize -mean of this, typically normalized per degree of freedom)."""
    chunk_c = coarse.to(device).float()
    chunk_f = fine.to(device).float()
    fine_size = chunk_f.shape[-1]
    score_fn = _effective_score_fn(
        model, chunk_c, fine_size, beta_target,
        consistency_weight, physics_blend_coef, physics_blend_beta_min, device,
    )
    sigmas_desc = schedule.discrete_sigmas(n_steps, device=device, beta=beta_target)
    sigmas_asc = torch.flip(sigmas_desc, dims=[0])
    _, acc = integrate_with_divergence(score_fn, chunk_f, sigmas_asc, n_probes=n_probes)
    n_dof = chunk_f[0].numel()
    return -n_dof * math.log(2.0 * math.pi) + acc


def reverse_kl_terms(
    model,
    schedule,
    coarse: torch.Tensor,
    beta_target: float,
    n_steps: int = 24,
    n_probes: int = 1,
    consistency_weight: float = 1.0,
    physics_blend_coef: float = 0.0,
    physics_blend_beta_min: float = 0.0,
    device: str = "cpu",
) -> tuple[torch.Tensor, torch.Tensor]:
    """Differentiable (x0, log_q) sampled from the flow conditioned on
    `coarse` (Tier 3 objective: minimize mean(S(x0) + log_q), reparameterized
    through the deterministic ODE)."""
    chunk_c = coarse.to(device).float()
    fine_size = chunk_c.shape[-1] * 2
    score_fn = _effective_score_fn(
        model, chunk_c, fine_size, beta_target,
        consistency_weight, physics_blend_coef, physics_blend_beta_min, device,
    )
    sigmas_desc = schedule.discrete_sigmas(n_steps, device=device, beta=beta_target)
    shape = (chunk_c.shape[0], 2, fine_size, fine_size)
    x_prior = torch.rand(shape, device=device) * (2.0 * math.pi) - math.pi
    x0, acc = integrate_with_divergence(score_fn, x_prior, sigmas_desc, n_probes=n_probes)
    n_dof = x0[0].numel()
    log_q = -n_dof * math.log(2.0 * math.pi) - acc
    return x0, log_q
