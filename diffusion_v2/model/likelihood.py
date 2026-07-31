"""Probability-flow ODE log-likelihood and importance-sampling ESS.

Motivation: flow-based samplers for this system (e.g. Q-shift flows, Lattice
2026) report unbiased estimators with ESS/N as the headline quality number.
Score-based diffusion has no cheap exact likelihood, but the probability-flow
ODE that shares the reverse process's marginals does: for the VE process the
flow is dx/dsigma = -sigma * s(x, sigma), and the instantaneous
change-of-variables gives

    log q(x_0) = log p_prior(x(sigma_max)) - int_{sigma_min}^{sigma_max}
                 sigma * div s(x(sigma), sigma) dsigma,

with p_prior uniform on the torus (log p = -N log 2pi, N = 2 L^2; the wrapped
Gaussian at sigma_max = 6 is uniform to ~1e-8). The divergence is estimated by
Hutchinson probes (Rademacher v, div s ~ E[v . d(s.v)/dx]) and the ODE is
integrated with Heun's method on the schedule's log-spaced sigma grid.

Scope and honesty:
  * The likelihood is that of the probability-flow model driven by the SAME
    effective score used at sampling time (model + exact-score blend +
    blocking-consistency guidance, per coarse config). It does NOT include the
    deterministic charge projection (a non-diffeomorphic map) or the retherm
    sweeps; it therefore measures raw model transport quality.
  * ESS weights are conditional, w_i = exp(-S(x_i)) / q(x_i | c_i), i.e. the
    coarse marginal is taken as given (the base ensemble is unbiased HMC with
    Q-hops). This is the per-level quantity multilevel flow papers report.
  * The stochastic sampler is not the ODE, so q is the flow's density for the
    shared marginals -- exact for a perfect score, a diagnostic otherwise.
"""

import math

import torch

from ..lgt.actions import make_action


def _divergence_hutchinson(score_fn, theta, sigma, n_probes: int = 1) -> torch.Tensor:
    """E_v [ v . d(s . v)/dtheta ] per config, Rademacher probes."""
    div = torch.zeros(theta.shape[0], device=theta.device)
    for _ in range(n_probes):
        with torch.enable_grad():
            x = theta.detach().requires_grad_(True)
            s = score_fn(x, sigma)
            v = torch.randint(0, 2, theta.shape, device=theta.device, dtype=theta.dtype) * 2 - 1
            sv = (s * v).sum()
            (grad,) = torch.autograd.grad(sv, x)
        div = div + (grad * v).flatten(1).sum(dim=1)
    return div / n_probes


def ode_log_likelihood(
    score_fn,
    x0: torch.Tensor,
    sigmas_ascending: torch.Tensor,
    n_probes: int = 1,
    seed: int | None = None,
) -> torch.Tensor:
    """log q(x0) per config under the probability-flow ODE.

    score_fn(theta, sigma_scalar_tensor) -> score [B, 2, L, L] (the TRUE score,
    not the sigma-scaled network output). sigmas_ascending: [n_steps] grid from
    ~sigma_min to sigma_max. Heun integration; each step costs 2 score evals and
    2 * n_probes vjps. States stay wrapped -- wrapping is an isometry of the
    torus, so it changes neither the flow nor the density.
    """
    if seed is not None:
        torch.manual_seed(seed)
    from .wrapped import wrap

    x = x0.clone()
    batch = x.shape[0]
    n_dof = x[0].numel()
    delta_logq = torch.zeros(batch, device=x.device)

    def drift_and_div(theta, sigma):
        with torch.no_grad():
            s = score_fn(theta, sigma)
        div = _divergence_hutchinson(score_fn, theta, sigma, n_probes=n_probes)
        return -sigma * s, -sigma * div

    for i in range(len(sigmas_ascending) - 1):
        sig0 = sigmas_ascending[i]
        sig1 = sigmas_ascending[i + 1]
        h = sig1 - sig0
        f0, d0 = drift_and_div(x, sig0)
        x_pred = wrap(x + h * f0)
        f1, d1 = drift_and_div(x_pred, sig1)
        x = wrap(x + 0.5 * h * (f0 + f1))
        delta_logq = delta_logq + 0.5 * h * (d0 + d1)

    log_prior = -n_dof * math.log(2.0 * math.pi)
    # log q(x_0) = log_prior + int (div f) dsigma with div f = -sigma div s;
    # delta_logq accumulated exactly that integrand.
    return log_prior + delta_logq


def conditional_log_likelihood(
    model,
    schedule,
    coarse: torch.Tensor,
    fine: torch.Tensor,
    beta_target: float,
    n_steps: int = 60,
    n_probes: int = 1,
    consistency_weight: float = 1.0,
    physics_blend_coef: float = 0.0,
    physics_blend_beta_min: float = 0.0,
    batch_size: int = 16,
    device: str = "cpu",
    seed: int | None = None,
) -> torch.Tensor:
    """log q(fine_i | coarse_i) for paired configs, using the sampling-time
    effective score (model + blend + consistency guidance, no charge projection)."""
    from ..lgt.lattice import plaquette_angles
    from ..pipeline.ladder import blocking_consistency_score, wilson_exact_score
    from .score_net import coarse_conditioning_channels

    model.eval()
    fine_size = fine.shape[-1]
    sigmas_desc = schedule.discrete_sigmas(n_steps, device=device, beta=beta_target)
    sigmas_asc = torch.flip(sigmas_desc, dims=[0])
    out = []
    for start in range(0, fine.shape[0], batch_size):
        chunk_c = coarse[start : start + batch_size].to(device).float()
        chunk_f = fine[start : start + batch_size].to(device).float()
        cond = coarse_conditioning_channels(
            chunk_c, fine_size, n_channels=getattr(model, "cond_channels", 4)
        )
        coarse_plaq = plaquette_angles(chunk_c)
        beta = torch.full((chunk_f.shape[0],), float(beta_target), device=device)

        def score_fn(theta, sigma):
            sig = sigma.expand(theta.shape[0])
            score = model.score(theta, sig, beta[: theta.shape[0]], cond[: theta.shape[0]])
            if physics_blend_coef > 0:
                sigma_c = physics_blend_coef / math.sqrt(beta_target)
                w = 1.0 / (1.0 + (sigma / sigma_c) ** 2)
                if physics_blend_beta_min > 0:
                    w = w / (1.0 + (physics_blend_beta_min / beta_target) ** 2)
                beta_eff = beta_target / (1.0 + 4.0 * beta_target * sigma**2)
                score = (1.0 - w) * score + w * wilson_exact_score(theta, beta_eff)
            if consistency_weight > 0:
                score = score + consistency_weight * blocking_consistency_score(
                    theta, coarse_plaq[: theta.shape[0]], sigma
                )
            return score

        out.append(ode_log_likelihood(score_fn, chunk_f, sigmas_asc, n_probes=n_probes, seed=seed).cpu())
    return torch.cat(out, dim=0)


def importance_ess(
    fine: torch.Tensor,
    log_q: torch.Tensor,
    beta: float,
    action_type: str = "wilson",
) -> dict:
    """Self-normalized importance-sampling diagnostics against the Boltzmann target.

    log w_i = -S(x_i) - log q_i up to the unknown log Z, which cancels in the
    self-normalized ESS/N = (sum w)^2 / (N sum w^2). Also reports the weight
    log-spread, a scale-free indicator of proposal quality.
    """
    action = make_action(action_type, float(beta))
    with torch.no_grad():
        neg_s = -action.per_config(fine.float())
    log_w = neg_s.cpu() - log_q.cpu()
    log_w = log_w - log_w.max()
    w = torch.exp(log_w)
    n = w.numel()
    ess = float(w.sum() ** 2 / (n * (w**2).sum()))
    return {
        "n": n,
        "ess_per_n": ess,
        "log_weight_std": float(log_w.std()),
        "log_weight_range": float(log_w.max() - log_w.min()),
        "log_weights": log_w.tolist(),
    }
