"""Annealed-importance-sampling correction of ODE transport samples.

The ESS program's converged diagnosis: the fiber log-weight spread is a bulk,
smooth, action-like density offset of 0.02-0.07 nats/site that no fine-tune
removed. AIS is the one mechanism that attacks the spread without touching the
model: split one large importance-sampling gap into many small increments, each
paid at a bridge distribution the samples have been RELAXED INTO by exact MCMC.

Construction (validity is standard AIS, Neal 2001, with a known-density
initial proposal):

  * Each ODE sample x_0 ~ q(.|c) arrives with its exact log q (probability-flow
    sampling). q itself cannot be evaluated at new points cheaply, so the
    bridge does not interpolate q -> p directly. Instead a TRACTABLE surrogate
    captures q's offset from the target:

        log q~(x) = -S_f(x) + G(x),   G(x) = sum_k g_k O_k(x) + const,

    with O_k differentiable lattice observables (the matched coarse action of
    the blocked field -- the fiber term -- plus fine/blocked plaquette
    characters, rectangles, and a smooth topological-charge surrogate) and g
    fit by least squares of [log q + S_f] on O at the initial samples.

  * Bridge distributions pi_t proportional to exp(-S_f(x) + (1 - t) G(x)),
    t: 0 -> 1. pi_0 = q~, pi_1 = the exact target. Every pi_t is tractable and
    autograd-differentiable, so HMC + instanton Q-hops leave it exactly
    invariant.

  * Weights (self-normalized; constants cancel):

        log w = [log pi_0(x_0) - log q(x_0 | c_0)]        <- surrogate fit residual
              + sum_k (t_{k-1} - t_k) G(x_{k-1})          <- AIS increments

    moving x_{k-1} -> x_k by a pi_{t_k}-invariant kernel after accumulating
    increment k. Unbiasedness: E over c ~ pi_matched, x_0 ~ q(.|c) of
    w * h(x_K) telescopes to the pi_1 expectation of h -- the per-sample
    conditional density is known pointwise, so the coarse mixture integrates
    out exactly (no S_matched(c) term needed; the blocked-action FEATURE plays
    that role on the fine side).

  * Variance budget: Var[log w] = Var[fit residual] + sum of increment
    variances. The increments shrink with more bridge steps and better mixing;
    the fit residual is the irreducible floor -- measured by the regression
    R^2, which is exactly what scripts/27_matching_residual.py reports. The
    free-energy certificate here is even simpler than the fiber one:
    E[w] = (2 pi)^{2 L^2} Z_haar(beta_f, L), directly checkable against the
    character expansion.

Honesty caveats:
  * Fitting g on the same samples that get weighted biases the estimator
    (selection); use split_fit to fit on one half and quote the other.
  * log q at sigma_min is the density of the sigma_min-smeared model; the
    surrogate absorbs the smooth part of that smearing offset like any other
    bulk term, but cross-beta comparisons of the fit constant are
    reference-measure-dependent.
  * Topological-sector mismatch does not regress onto smooth features and must
    anneal through the bridge's Q-hops; expect this to be the residual failure
    mode at large beta * V.
"""

import math

import torch

from ..lgt.actions import make_action
from ..lgt.blocking import block_links
from ..lgt.hmc import BatchedHMC
from ..lgt.lattice import (
    plaquette_angles,
    rectangle_x_angles,
    rectangle_y_angles,
    wilson_loop_angles,
)
from ..lgt.local_updates import topological_update

TWO_PI = 2.0 * math.pi

COARSE_FEATURE_NAMES = [
    "sum_cos_P", "sum_cos_2P", "sum_cos_3P", "sum_cos_rect", "Q_c", "Q_c^2",
]

FEATURE_NAMES = [
    "S_matched(blocked)",
    "sum_cos_p",
    "sum_cos_2p",
    "sum_cos_3p",
    "sum_cos_rect",
    "sum_cos_2P_blocked",
    "Q_float^2",
]

RICH_EXTRA_FEATURE_NAMES = [
    "sum_cos_4p",
    "sum_cos_W22",
    "plaq_nn_corr",
    "sum_cos_3P_blocked",
]

RICH_FEATURE_NAMES = FEATURE_NAMES + RICH_EXTRA_FEATURE_NAMES

BASIS_FEATURE_NAMES = {
    "final7": FEATURE_NAMES,
    "rich11": RICH_FEATURE_NAMES,
}

DEFAULT_BASIS = "final7"


def _feature_names_for_width(width: int) -> list[str]:
    for names in (FEATURE_NAMES, RICH_FEATURE_NAMES, COARSE_FEATURE_NAMES):
        if len(names) == width:
            return list(names)
    return [f"feature_{i}" for i in range(width)]


def coarse_only_features(coarse: torch.Tensor) -> torch.Tensor:
    """[B, 2, Lc, Lc] -> [B, 6] per-config COARSE observables, for regressing
    fiber log-weights on c-only functions (the matching-residual probe: a
    c-only component of the weight cannot be removed by any fine-score
    fine-tune)."""
    plaq = plaquette_angles(coarse.float())
    rect = 0.5 * (
        torch.cos(rectangle_x_angles(coarse.float())).sum(dim=(-2, -1))
        + torch.cos(rectangle_y_angles(coarse.float())).sum(dim=(-2, -1))
    )
    q = torch.round(plaq.sum(dim=(-2, -1)) / TWO_PI)
    return torch.stack([
        torch.cos(plaq).sum(dim=(-2, -1)),
        torch.cos(2.0 * plaq).sum(dim=(-2, -1)),
        torch.cos(3.0 * plaq).sum(dim=(-2, -1)),
        rect,
        q,
        q**2,
    ], dim=1)


def bridge_features(
    theta: torch.Tensor,
    coarse_beta_matched: float,
    action_type: str = "wilson",
    basis: str = DEFAULT_BASIS,
) -> torch.Tensor:
    """[B, 2, L, L] -> [B, n_features] differentiable per-config features.

    The first feature is the matched coarse action evaluated on the blocked
    field -- with coefficient ~1 the regression recovers the fiber correction
    S_matched(B(x)) automatically; the rest absorb the smooth model-error
    offset. All features flow gradients (wrap has derivative 1 a.e.), so the
    bridge Hamiltonian is HMC-able by autograd.

    basis: "final7" (default, the result of record) or "rich11". The wide
    basis raised in-sample R^2 but exploded the held-out AIS weights at 2 of 4
    cases (std 1120 and 18650) -- an under-regularized wide basis extrapolates
    wildly once the bridge dynamics move samples off the fit manifold. It is
    retained only to reproduce that recorded negative; do not deploy it.
    """
    if basis not in BASIS_FEATURE_NAMES:
        raise ValueError(f"unknown basis {basis!r}; expected one of {sorted(BASIS_FEATURE_NAMES)}")
    plaq = plaquette_angles(theta)
    blocked = block_links(theta)
    bplaq = plaquette_angles(blocked)
    coarse_action = make_action(action_type, float(coarse_beta_matched))
    rect = 0.5 * (
        torch.cos(rectangle_x_angles(theta)).sum(dim=(-2, -1))
        + torch.cos(rectangle_y_angles(theta)).sum(dim=(-2, -1))
    )
    q_float = plaq.sum(dim=(-2, -1)) / TWO_PI
    nn_corr = (
        torch.cos(plaq - torch.roll(plaq, 1, dims=-2)).sum(dim=(-2, -1))
        + torch.cos(plaq - torch.roll(plaq, 1, dims=-1)).sum(dim=(-2, -1))
    )
    feats = [
        -coarse_action.per_config(blocked),
        torch.cos(plaq).sum(dim=(-2, -1)),
        torch.cos(2.0 * plaq).sum(dim=(-2, -1)),
        torch.cos(3.0 * plaq).sum(dim=(-2, -1)),
        rect,
        torch.cos(2.0 * bplaq).sum(dim=(-2, -1)),
        q_float**2,
    ]
    if basis == "rich11":
        feats += [
            torch.cos(4.0 * plaq).sum(dim=(-2, -1)),
            torch.cos(wilson_loop_angles(theta, 2, 2)).sum(dim=(-2, -1)),
            nn_corr,
            torch.cos(3.0 * bplaq).sum(dim=(-2, -1)),
        ]
    return torch.stack(feats, dim=1)


def fit_surrogate(
    features: torch.Tensor, target: torch.Tensor, ridge: float = 1e-3
) -> dict:
    """Least squares target ~ const + features @ g (ridge-stabilized on
    standardized columns; the default 1e-3 fractional shrinkage is negligible
    bias but keeps few-sample fits from interpolating -- an interpolating fit
    extrapolates wildly on held-out configs and destroys the AIS weights).
    target should be log q + S_f at the initial samples, so that
    log q~ = -S_f + G approximates log q.

    Returns g, const, r2, resid_std, and per-feature standardized coefficients
    (feature importance in nats of log-weight std absorbed)."""
    x = features.double()
    y = target.double()
    x_mean, y_mean = x.mean(dim=0), y.mean()
    x_std = x.std(dim=0).clamp_min(1e-12)
    xs = (x - x_mean) / x_std
    ys = y - y_mean
    a = xs.T @ xs + ridge * x.shape[0] * torch.eye(x.shape[1], dtype=torch.float64)
    g_std = torch.linalg.solve(a, xs.T @ ys)
    g = g_std / x_std
    const = float(y_mean - (x_mean * g).sum())
    resid = ys - xs @ g_std
    var_y = float((ys**2).mean())
    r2 = 1.0 - float((resid**2).mean()) / max(var_y, 1e-300)
    return {
        "g": g,
        "const": const,
        "r2": r2,
        "resid_std": float(resid.std()),
        "target_std": float(y.std()),
        "std_coefficients": {
            n: float(c) for n, c in zip(_feature_names_for_width(g_std.numel()), g_std)
        },
    }


def fit_surrogate_cv(
    features: torch.Tensor,
    target: torch.Tensor,
    ridges: tuple[float, ...] = (1e-3, 3e-3, 1e-2, 3e-2, 0.1, 0.3, 1.0),
    k_folds: int = 4,
) -> dict:
    """Ridge chosen by k-fold cross-validation on the fit set.

    The bridge features are strongly collinear (plaquette characters,
    rectangles, the blocked action); weakly-regularized least squares finds
    huge canceling coefficients that interpolate the initial samples and then
    explode on configs the HMC transitions move OFF the fit manifold --
    observed as AIS increments that never shrink. Any g gives VALID AIS
    weights; g only controls variance, so the right selection target is
    out-of-fold residual variance, not in-sample R^2."""
    n = features.shape[0]
    perm = torch.randperm(n)
    folds = [perm[i::k_folds] for i in range(k_folds)]
    cv = {}
    for ridge in ridges:
        sq = 0.0
        for i in range(k_folds):
            hold = folds[i]
            train = torch.cat([folds[j] for j in range(k_folds) if j != i])
            f = fit_surrogate(features[train], target[train], ridge=ridge)
            pred = features[hold].double() @ f["g"] + f["const"]
            sq += float(((target[hold].double() - pred) ** 2).sum())
        cv[ridge] = math.sqrt(sq / n)
    best = min(cv, key=cv.get)
    fit = fit_surrogate(features, target, ridge=best)
    fit["ridge"] = best
    fit["cv_resid_std"] = cv[best]
    fit["cv_table"] = {f"{r:g}": round(v, 3) for r, v in cv.items()}
    return fit


def sector_resolved_estimate(
    values: torch.Tensor,
    log_w: torch.Tensor,
    q_sample: torch.Tensor,
    q_values,
    probs,
    min_count: int = 2,
) -> dict:
    """E[obs] = sum_Q P_exact(Q) E[obs | Q], with each conditional expectation
    estimated by WITHIN-SECTOR self-normalized importance sampling.

    The global weights degenerate because the proposal's relative sector
    frequencies are wrong -- an error that is a single number per sector.
    Conditioning on Q (a weight-measurable event) preserves the importance
    identity within each sector, and the exact finite-volume P(Q) replaces the
    badly-estimated sector masses. Theory-specific (needs exact P(Q)); the
    U(1)-only crutch, stated as such wherever quoted.

    Sectors with fewer than min_count samples fall back to the
    coverage-weighted mean of estimated sectors; their exact mass is reported
    as uncovered_mass so the reader can bound the fallback's influence.
    """
    values = values.float().cpu()
    log_w = log_w.double().cpu()
    q_sample = q_sample.float().cpu()
    per_sector = {}
    est_pairs = []
    for q, p in zip(q_values, probs):
        p = float(p)
        if p < 1e-12:
            continue
        idx = (q_sample == float(q)).nonzero(as_tuple=True)[0]
        rec = {"prob_exact": p, "count": int(idx.numel())}
        if idx.numel() >= min_count:
            lw = log_w[idx] - log_w[idx].max()
            w = torch.exp(lw)
            w = w / w.sum()
            mu = float((w * values[idx].double()).sum())
            err = float(torch.sqrt((w**2 * (values[idx].double() - mu) ** 2).sum()))
            rec.update({"mean": mu, "err": err, "ess": float(1.0 / (w**2).sum() / idx.numel())})
            est_pairs.append((p, mu, err))
        per_sector[f"{int(q):+d}"] = rec
    covered = sum(p for p, _, _ in est_pairs)
    if not est_pairs:
        return {"mean": float("nan"), "err": float("nan"), "covered_mass": 0.0,
                "uncovered_mass": 1.0, "per_sector": per_sector}
    fallback = sum(p * m for p, m, _ in est_pairs) / covered
    mean = sum(p * m for p, m, _ in est_pairs) + (1.0 - covered) * fallback
    err = math.sqrt(sum((p / covered) ** 2 * e**2 for p, _, e in est_pairs))
    return {
        "mean": mean, "err": err,
        "covered_mass": covered, "uncovered_mass": 1.0 - covered,
        "fallback_mean": fallback,
        "per_sector": per_sector,
    }


class _BridgeAction:
    """S_t(x) = S_f(x) - (1 - t) G(x); per_config API so BatchedHMC's autograd
    force and the instanton Q-hop apply to the bridge Hamiltonian unchanged."""

    def __init__(self, action_fine, g: torch.Tensor, const: float,
                 coarse_beta_matched: float, action_type: str,
                 basis: str = DEFAULT_BASIS) -> None:
        self.action_fine = action_fine
        self.g = g.float()
        self.const = const
        self.coarse_beta_matched = coarse_beta_matched
        self.action_type = action_type
        self.basis = basis
        self.t = 0.0

    def g_of(self, theta: torch.Tensor) -> torch.Tensor:
        feats = bridge_features(theta, self.coarse_beta_matched, self.action_type, self.basis)
        # Follow theta's device as well as its dtype: g is the surrogate fit,
        # which is produced CPU-side, while theta lives on whatever device the
        # bridge HMC runs on.
        return feats @ self.g.to(device=theta.device, dtype=theta.dtype) + self.const

    def per_config(self, theta: torch.Tensor) -> torch.Tensor:
        return self.action_fine.per_config(theta) - (1.0 - self.t) * self.g_of(theta)


def ais_correct(
    fine0: torch.Tensor,
    log_q: torch.Tensor,
    fine_beta: float,
    coarse_beta_matched: float,
    g: torch.Tensor,
    const: float,
    action_type: str = "wilson",
    basis: str = DEFAULT_BASIS,
    n_bridge: int = 48,
    n_hmc_per_step: int = 2,
    step_size: float | None = None,
    n_leapfrog: int = 5,
    q_hops: bool = True,
    seed: int | None = None,
    device: str = "cpu",
) -> tuple[torch.Tensor, torch.Tensor, dict]:
    """Run the surrogate-bridge AIS chain from ODE samples with known log q.

    Returns (x_final, log_w, diagnostics). log_w are UNSHIFTED, so
    free_energy_certificate applies with exact
    dF = 2 L^2 log(2 pi) + log Z_haar(beta_f, L) (see module docstring).
    """
    if seed is not None:
        torch.manual_seed(seed)
    lattice_size = fine0.shape[-1]
    action_f = make_action(action_type, float(fine_beta))
    bridge = _BridgeAction(action_f, g, const, coarse_beta_matched, action_type, basis)
    if step_size is None:
        from ..lgt.hmc import adapted_hmc_params

        step_size, n_leapfrog = adapted_hmc_params(fine_beta, 0.2, n_leapfrog)
    sampler = BatchedHMC(
        lattice_size, bridge, n_chains=fine0.shape[0], n_steps=n_leapfrog,
        step_size=step_size, device=device, topological_updates=False,
    )

    x = fine0.clone().to(device).float()
    with torch.no_grad():
        log_w = (-action_f.per_config(x) + bridge.g_of(x)).cpu().double() - log_q.cpu().double()

    ts = torch.linspace(0.0, 1.0, n_bridge + 1)
    accept_hist, hop_hist, inc_stds = [], [], []
    for k in range(1, n_bridge + 1):
        with torch.no_grad():
            inc = (float(ts[k - 1]) - float(ts[k])) * bridge.g_of(x).cpu().double()
        log_w = log_w + inc
        inc_stds.append(float(inc.std()))
        bridge.t = float(ts[k])
        accs = []
        with torch.no_grad():
            for _ in range(n_hmc_per_step):
                x, acc = sampler.metropolis_step(x)
                accs.append(float(acc.float().mean()))
                if q_hops:
                    x, hop_acc = topological_update(x, bridge)
                    hop_hist.append(float(hop_acc.float().mean()))
        step_acc = sum(accs) / len(accs)
        accept_hist.append(step_acc)
        # Adapting the kernel from PREVIOUS steps' acceptance is valid (each
        # transition still leaves its own pi_t invariant); the surrogate term
        # stiffens the force, so the beta-adapted step can run hot.
        if step_acc < 0.5 and sampler.step_size > step_size / 8:
            sampler.step_size *= 0.6

    diagnostics = {
        "n_bridge": n_bridge,
        "n_hmc_per_step": n_hmc_per_step,
        "step_size": step_size,
        "final_step_size": sampler.step_size,
        "hmc_acceptance_mean": sum(accept_hist) / max(len(accept_hist), 1),
        "hmc_acceptance_min": min(accept_hist) if accept_hist else float("nan"),
        "q_hop_acceptance_mean": (sum(hop_hist) / len(hop_hist)) if hop_hist else None,
        "increment_std_per_step": inc_stds,
        "increment_std_total": float(sum(s**2 for s in inc_stds) ** 0.5),
    }
    return x, log_w.float(), diagnostics
