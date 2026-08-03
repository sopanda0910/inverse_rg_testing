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
    `ode_sample_with_likelihood` / `conditional_ode_sample` close that gap:
    sampling the probability-flow ODE itself yields the sample AND its density
    in one pass, making the importance weights valid for the actual samples
    (up to Heun discretization error and Hutchinson probe noise; n_probes=0
    computes the exact divergence for calibration on small lattices). With
    valid weights, self-normalized reweighting and independence Metropolis
    give asymptotically exact estimates -- the M-H/reweighting exactness route
    diffusion models are usually said to lack. Caveat: Hutchinson noise is
    unbiased in log q but exponentiation makes the WEIGHTS biased upward
    (Jensen), and the trapezoid divergence integral approximates the discrete
    Heun map's true log-Jacobian; both are biases that shrink with
    probes/steps, not with sample count. Quote exactness results only after a
    probe/step stability check (or with n_probes=0).
"""

import math

import torch

from ..lgt.actions import make_action


def _divergence_hutchinson(
    score_fn, theta, sigma, n_probes: int = 1, generator: torch.Generator | None = None
) -> torch.Tensor:
    """E_v [ v . d(s . v)/dtheta ] per config, Rademacher probes."""
    div = torch.zeros(theta.shape[0], device=theta.device)
    for _ in range(n_probes):
        with torch.enable_grad():
            x = theta.detach().requires_grad_(True)
            s = score_fn(x, sigma)
            v = torch.randint(
                0, 2, theta.shape, device=theta.device, dtype=theta.dtype, generator=generator
            ) * 2 - 1
            sv = (s * v).sum()
            (grad,) = torch.autograd.grad(sv, x)
        div = div + (grad * v).flatten(1).sum(dim=1)
    return div / n_probes


def _divergence_exact(score_fn, theta, sigma) -> torch.Tensor:
    """Exact trace of ds/dtheta per config, one vjp per degree of freedom."""
    batch = theta.shape[0]
    n_dof = theta[0].numel()
    div = torch.zeros(batch, device=theta.device)
    with torch.enable_grad():
        x = theta.detach().requires_grad_(True)
        s = score_fn(x, sigma).reshape(batch, -1)
        for j in range(n_dof):
            (grad,) = torch.autograd.grad(
                s[:, j].sum(), x, retain_graph=(j < n_dof - 1)
            )
            div = div + grad.reshape(batch, -1)[:, j]
    return div


def _divergence(
    score_fn, theta, sigma, n_probes: int, generator: torch.Generator | None = None
) -> torch.Tensor:
    if n_probes <= 0:
        return _divergence_exact(score_fn, theta, sigma)
    return _divergence_hutchinson(score_fn, theta, sigma, n_probes=n_probes, generator=generator)


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
    gen = None
    if seed is not None:
        gen = torch.Generator(device=x0.device)
        gen.manual_seed(seed)
    from .wrapped import wrap

    x = x0.clone()
    batch = x.shape[0]
    n_dof = x[0].numel()
    delta_logq = torch.zeros(batch, device=x.device)

    def drift_and_div(theta, sigma):
        with torch.no_grad():
            s = score_fn(theta, sigma)
        div = _divergence(score_fn, theta, sigma, n_probes, generator=gen)
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


def ode_sample_with_likelihood(
    score_fn,
    shape: tuple[int, ...],
    sigmas_descending: torch.Tensor,
    n_probes: int = 1,
    device: str = "cpu",
    seed: int | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Sample the probability-flow ODE from the uniform torus prior; return
    (x0, log_q) where log_q is the density of the produced sample under the
    SAME discretized flow -- sample and likelihood in one pass, so importance
    weights against a known action are valid for these samples.

    Accumulating along the descending trajectory, int_{max}^{min} div f dsigma
    is minus the ascending integral in `ode_log_likelihood`, hence the sign.
    """
    gen = None
    if seed is not None:
        gen = torch.Generator(device=device)
        gen.manual_seed(seed)
    from .wrapped import wrap

    x = torch.rand(shape, device=device, generator=gen) * (2.0 * math.pi) - math.pi
    batch = shape[0]
    n_dof = x[0].numel()
    acc = torch.zeros(batch, device=device)

    def drift_and_div(theta, sigma):
        with torch.no_grad():
            s = score_fn(theta, sigma)
        div = _divergence(score_fn, theta, sigma, n_probes, generator=gen)
        return -sigma * s, -sigma * div

    for i in range(len(sigmas_descending) - 1):
        sig0 = sigmas_descending[i]
        sig1 = sigmas_descending[i + 1]
        h = sig1 - sig0
        f0, d0 = drift_and_div(x, sig0)
        x_pred = wrap(x + h * f0)
        f1, d1 = drift_and_div(x_pred, sig1)
        x = wrap(x + 0.5 * h * (f0 + f1))
        acc = acc + 0.5 * h * (d0 + d1)

    log_prior = -n_dof * math.log(2.0 * math.pi)
    return x, log_prior - acc


def _effective_score_fn(
    model,
    chunk_c: torch.Tensor,
    fine_size: int,
    beta_target: float,
    consistency_weight: float,
    physics_blend_coef: float,
    physics_blend_beta_min: float,
    device: str,
):
    """The sampling-time effective score (model + exact-score blend + blocking
    consistency guidance, no charge projection) for one coarse chunk."""
    from ..lgt.lattice import plaquette_angles
    from ..pipeline.ladder import blocking_consistency_score, wilson_exact_score
    from .score_net import coarse_conditioning_channels

    cond = coarse_conditioning_channels(
        chunk_c, fine_size, n_channels=getattr(model, "cond_channels", 4)
    )
    coarse_plaq = plaquette_angles(chunk_c)
    beta = torch.full((chunk_c.shape[0],), float(beta_target), device=device)

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

    return score_fn


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
    model.eval()
    fine_size = fine.shape[-1]
    sigmas_desc = schedule.discrete_sigmas(n_steps, device=device, beta=beta_target)
    sigmas_asc = torch.flip(sigmas_desc, dims=[0])
    out = []
    for start in range(0, fine.shape[0], batch_size):
        chunk_c = coarse[start : start + batch_size].to(device).float()
        chunk_f = fine[start : start + batch_size].to(device).float()
        score_fn = _effective_score_fn(
            model, chunk_c, fine_size, beta_target,
            consistency_weight, physics_blend_coef, physics_blend_beta_min, device,
        )
        out.append(ode_log_likelihood(
            score_fn, chunk_f, sigmas_asc, n_probes=n_probes,
            seed=None if seed is None else seed + start,
        ).cpu())
    return torch.cat(out, dim=0)


def conditional_ode_sample(
    model,
    schedule,
    coarse: torch.Tensor,
    beta_target: float,
    n_steps: int = 120,
    n_probes: int = 2,
    consistency_weight: float = 1.0,
    physics_blend_coef: float = 0.0,
    physics_blend_beta_min: float = 0.0,
    batch_size: int = 16,
    device: str = "cpu",
    seed: int | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Probability-flow ODE sample of fine configs conditioned on each coarse
    config, returning (fine, log_q) with log_q the density of the actual
    samples. No charge projection (a non-diffeomorphic map would invalidate
    the density); sector correctness is carried by the importance weights."""
    model.eval()
    fine_size = coarse.shape[-1] * 2
    sigmas_desc = schedule.discrete_sigmas(n_steps, device=device, beta=beta_target)
    fines, logqs = [], []
    for start in range(0, coarse.shape[0], batch_size):
        chunk_c = coarse[start : start + batch_size].to(device).float()
        score_fn = _effective_score_fn(
            model, chunk_c, fine_size, beta_target,
            consistency_weight, physics_blend_coef, physics_blend_beta_min, device,
        )
        x, log_q = ode_sample_with_likelihood(
            score_fn,
            (chunk_c.shape[0], 2, fine_size, fine_size),
            sigmas_desc,
            n_probes=n_probes,
            device=device,
            seed=None if seed is None else seed + start,
        )
        fines.append(x.cpu())
        logqs.append(log_q.cpu())
    return torch.cat(fines, dim=0), torch.cat(logqs, dim=0)


def _ess_from_log_weights(log_w: torch.Tensor) -> tuple[float, float, float]:
    log_w = log_w - log_w.max()
    w = torch.exp(log_w)
    n = w.numel()
    ess = float(w.sum() ** 2 / (n * (w**2).sum()))
    return ess, float(log_w.std()), float(log_w.max() - log_w.min())


def importance_ess(
    fine: torch.Tensor,
    log_q: torch.Tensor,
    beta: float,
    action_type: str = "wilson",
    coarse: torch.Tensor | None = None,
    coarse_beta_matched: float | None = None,
) -> dict:
    """Self-normalized importance-sampling diagnostics against the Boltzmann target.

    Two estimators:

    * joint (`ess_per_n`): log w = -S_f(x) - log q(x|c). Unbiased on the joint
      (coarse, fine) space, but maximally conservative -- the weight spread
      includes the full variability of the coarse fiber's probability mass, so
      even a PERFECT conditional model scores ~1/N (w_perfect = p(x)/p(x|c) =
      the blocked marginal p_c(B(x)), which fluctuates by O(e^V)).

    * fiber-corrected (`ess_per_n_fiber`): log w' = -S_f(x) + S_matched(c)
      - log q(x|c), where S_matched is the Wilson action at the matched coarse
      coupling -- this project's MLE/min-KL approximation of the true blocked
      action (see lgt.blocking). Dividing out the coarse level's density is
      exactly what multilevel-flow papers do with their exact per-level
      densities, so THIS is the number comparable to their reported ESS/N; the
      residual spread mixes model error with the (small) matching residual.
    """
    action = make_action(action_type, float(beta))
    with torch.no_grad():
        neg_s = -action.per_config(fine.float())
    log_w = neg_s.cpu() - log_q.cpu()
    ess, std, rng = _ess_from_log_weights(log_w)
    out = {
        "n": log_w.numel(),
        "ess_per_n": ess,
        "log_weight_std": std,
        "log_weight_range": rng,
        "log_weights": (log_w - log_w.max()).tolist(),
    }
    if coarse is not None and coarse_beta_matched is not None:
        coarse_action = make_action(action_type, float(coarse_beta_matched))
        with torch.no_grad():
            s_coarse = coarse_action.per_config(coarse.float())
        log_w_fiber = log_w + s_coarse.cpu()
        ess_f, std_f, rng_f = _ess_from_log_weights(log_w_fiber)
        out.update(ess_per_n_fiber=ess_f, log_weight_std_fiber=std_f,
                   log_weight_range_fiber=rng_f)
    return out


def snis_log_weights(
    fine: torch.Tensor,
    log_q: torch.Tensor,
    beta: float,
    action_type: str = "wilson",
    coarse: torch.Tensor | None = None,
    coarse_beta_matched: float | None = None,
) -> torch.Tensor:
    """Raw self-normalized importance-sampling log-weights.

    With coarse given: log w = -S_f(x) + S_matched(c) - log q(x|c). The
    proposal joint is pi_c^matched(c) * q(x|c) -- BOTH factors known exactly
    (the coarse base is HMC at the matched coupling, q is the flow density) --
    so against the target marginal exp(-S_f(x))/Z these weights make SNIS
    consistent with no approximation; normalization constants cancel under
    self-normalization. Without coarse, the maximally conservative joint
    weights (see `importance_ess`)."""
    action = make_action(action_type, float(beta))
    with torch.no_grad():
        log_w = -action.per_config(fine.float()).cpu() - log_q.cpu()
        if coarse is not None and coarse_beta_matched is not None:
            coarse_action = make_action(action_type, float(coarse_beta_matched))
            log_w = log_w + coarse_action.per_config(coarse.float()).cpu()
    return log_w


def free_energy_certificate(
    log_w_fiber: torch.Tensor,
    fine_L: int,
    fine_beta: float,
    coarse_beta_matched: float,
    action_type: str = "wilson",
) -> dict:
    """Independent exactness check of the whole weight chain against the
    solvable theory: for fiber weights w = exp(-S_f(x) + S_m(c) - log q(x|c))
    with c ~ exp(-S_m)/Z_c and x ~ q(.|c),

        E[w] = (2 pi)^{N_f} Z_haar(beta_f, L_f) / Z_haar(beta_c, L_c),

    (N_f = 2 L_f^2; the coarse Lebesgue volume cancels Z_c's (2 pi)^{N_c}).
    Both partition functions are exactly computable from the character
    expansion, so log-mean-exp of the stored weights must reproduce the exact
    free-energy difference -- a certificate no SU(2) successor will have.

    Reading the numbers: the log-mean-exp only closes the gap when the weights
    have usable ESS; with degenerate weights it sits near max(log w) and the
    gap reads roughly -KL. The IDENTITY that always holds is

        E[log w] - dF_exact = -KL(q_eff || p)     (q_eff = coarse x proposal),

    so `kl_from_mean_log_w` below is an unbiased direct MEASUREMENT of the
    model's mean density offset -- the number the whole ESS program bounds --
    with an honest sem (log-weight std / sqrt n). The `gap` is the certificate
    (must -> 0 as ESS -> 1); the KL fields are the measurement. Both per
    site = / (2 L_f^2)."""
    from ..lgt.exact import log_partition

    coarse_L = fine_L // 2
    lw = log_w_fiber.double()
    m = lw.max()
    w = torch.exp(lw - m)
    n = w.numel()
    est = float(m + torch.log(w.mean()))
    sem = float(w.std() / (math.sqrt(n) * w.mean()))
    exact = (
        2 * fine_L * fine_L * math.log(2.0 * math.pi)
        + log_partition(fine_beta, fine_L, action_type)
        - log_partition(coarse_beta_matched, coarse_L, action_type)
    )
    n_sites = 2 * fine_L * fine_L
    kl = float(exact - lw.mean())
    return {
        "log_mean_w": est,
        "exact_delta_F": exact,
        "gap": est - exact,
        "sem": sem,
        "n": n,
        "kl_from_mean_log_w": kl,
        "kl_sem": float(lw.std() / math.sqrt(n)),
        "kl_per_site": kl / n_sites,
    }


def reweighted_mean(values: torch.Tensor, log_w: torch.Tensor) -> tuple[float, float]:
    """Self-normalized importance estimate of E[values] and its linearized
    standard error sqrt(sum w_i^2 (v_i - mu)^2), w normalized."""
    lw = log_w - log_w.max()
    w = torch.exp(lw)
    w = w / w.sum()
    values = values.float().cpu()
    mu = float((w * values).sum())
    err = float(torch.sqrt((w**2 * (values - mu) ** 2).sum()))
    return mu, err


def independence_metropolis(
    log_w: torch.Tensor, seed: int | None = None
) -> tuple[torch.Tensor, float]:
    """Independence-Metropolis chain over the pre-drawn proposal ensemble.

    Proposals are iid draws from the (coarse, fine) proposal distribution, so
    accepting proposal i over current state c with prob min(1, w_i / w_c)
    yields a chain whose stationary law is the target, GIVEN exact weights
    (noisy Hutchinson weights leave a residual bias; see module docstring).
    The chain autocorrelates through repeated states: at acceptance a the
    effective sample count is ~ n a / (2 - a), so naive sems must be inflated
    by sqrt((2 - a) / a).
    Returns (state index per step [n], acceptance rate over steps 1..n-1)."""
    gen = torch.Generator()
    if seed is not None:
        gen.manual_seed(seed)
    log_w = log_w.float().cpu()
    n = log_w.numel()
    u = torch.rand(n, generator=gen)
    idx = torch.empty(n, dtype=torch.long)
    current = 0
    accepted = 0
    idx[0] = 0
    for i in range(1, n):
        if u[i] < torch.exp((log_w[i] - log_w[current]).clamp(max=0.0)):
            current = i
            accepted += 1
        idx[i] = current
    return idx, accepted / max(n - 1, 1)
