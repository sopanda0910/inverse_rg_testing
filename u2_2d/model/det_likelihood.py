"""Density-gap machinery for the determinant lift: KL in nats per site.

Why this exists, and why the number it produces is the WHOLE pipeline's density
gap rather than one sector's. One inverse-RG step factorizes exactly as

    p(psi, q) = p(psi) p(q | psi),

and the pipeline samples the second factor EXACTLY -- at frozen phi the U(2)
local weight is exp(beta k . q), so `conditional_su2_sweeps` is an exact sampler
for p(q | psi) and leaves psi untouched. The model supplies only the first
factor. Writing the model's joint as m(psi) p(q | psi),

    KL( m(psi) p(q|psi) || p(psi) p(q|psi) ) = KL( m(psi) || p(psi) ),

identically -- the conditional cancels because it is the SAME distribution on
both sides. **The determinant sector's density gap IS the U(2) pipeline's
density gap**, with no inequality and no residual term. That is a stronger
statement than u1_2d could make about any of its sectors, and it is the reason
this measurement is worth making at all.

The instrument is `u1_2d.model.likelihood`'s probability-flow ODE, unchanged --
psi is an honest compact U(1) field in the [B, 2, L, L] layout, so
`ode_sample_with_likelihood` and `ode_log_likelihood` apply verbatim. Three
things are substituted, and they are exactly the three places the theory differs:

  * the score is conditioned on `model_beta(beta_u2)`, the minimum-KL U(1)
    projection, never beta / 4;
  * the action in the weights is `DetSectorAction`, the exact SU(2)-integrated
    weight w_det(alpha) = 2 I_1(z)/z with z = beta cos(alpha/2) -- NOT U(1)
    Wilson, which differs from it by a (3/2) log cos(alpha/2) measure term;
  * the free energy is `u2_2d.lgt.exact.log_partition`, the U(2) character
    expansion on the torus, which equals the psi-marginal's partition function
    exactly because integrating SU(2) out is what defines that marginal.

The identity that makes the number readable is u1_2d's:

    E[log w] - dF_exact = -KL(q_eff || p),

which stays finite and quantitative long after the ESS has bottomed out. The
`gap` field is the certificate (it must go to zero as ESS goes to one); the
`kl_*` fields are the measurement.
"""

import math

import torch

from ..lgt.actions import DetSectorAction, det_sector_plaquette_score
from ..lgt.exact import log_partition
from ..model.det_lift import model_beta


def det_exact_score(psi: torch.Tensor, beta_u2: float) -> torch.Tensor:
    """Curl of the exact determinant-sector plaquette score, as a link field."""
    from u1_2d.lgt.lattice import plaquette_angles
    from u1_2d.model.score_net import plaquette_curl

    return plaquette_curl(det_sector_plaquette_score(plaquette_angles(psi), beta_u2))


def _effective_score_fn(model, chunk_psi, fine_size, beta_u2, consistency_weight,
                        physics_blend_coef, device):
    """The sampling-time effective score, with NO charge projection.

    Charge projection is deliberately absent: it is not a diffeomorphism, so
    including it would invalidate the density the ODE reports. Sector
    correctness is carried by the importance weights instead, exactly as in
    `u1_2d.model.likelihood.conditional_ode_sample`.
    """
    from u1_2d.lgt.lattice import plaquette_angles
    from u1_2d.model.score_net import coarse_conditioning_channels
    from u1_2d.pipeline.ladder import blocking_consistency_score

    beta_m = model_beta(beta_u2)
    cond = coarse_conditioning_channels(
        chunk_psi, fine_size, n_channels=getattr(model, "cond_channels", 4)
    )
    coarse_plaq = plaquette_angles(chunk_psi)
    beta = torch.full((chunk_psi.shape[0],), float(beta_m), device=device)

    def score_fn(psi, sigma):
        sig = sigma.expand(psi.shape[0])
        score = model.score(psi, sig, beta[: psi.shape[0]], cond[: psi.shape[0]])
        if physics_blend_coef > 0:
            sigma_c = physics_blend_coef / math.sqrt(beta_m)
            w = 1.0 / (1.0 + (sigma / sigma_c) ** 2)
            beta_eff = beta_m / (1.0 + 4.0 * beta_m * float(sigma) ** 2)
            score = (1.0 - w) * score + w * det_exact_score(psi, 4.0 * beta_eff)
        if consistency_weight > 0:
            score = score + consistency_weight * blocking_consistency_score(
                psi, coarse_plaq[: psi.shape[0]], sigma
            )
        return score

    return score_fn


def conditional_ode_sample(model, schedule, coarse_psi, beta_u2, n_steps=120,
                           n_probes=2, consistency_weight=1.0,
                           physics_blend_coef=0.0, batch_size=16, device="cpu",
                           seed=None):
    """Probability-flow ODE sample of fine psi, returning (psi, log_q)."""
    from u1_2d.model.likelihood import ode_sample_with_likelihood

    model.eval()
    fine_size = coarse_psi.shape[-1] * 2
    sigmas = schedule.discrete_sigmas(n_steps, device=device,
                                      beta=model_beta(beta_u2))
    psis, logqs = [], []
    for start in range(0, coarse_psi.shape[0], batch_size):
        chunk = coarse_psi[start:start + batch_size].to(device).float()
        score_fn = _effective_score_fn(model, chunk, fine_size, beta_u2,
                                       consistency_weight, physics_blend_coef,
                                       device)
        x, log_q = ode_sample_with_likelihood(
            score_fn, (chunk.shape[0], 2, fine_size, fine_size), sigmas,
            n_probes=n_probes, device=device,
            seed=None if seed is None else seed + start,
        )
        psis.append(x.cpu())
        logqs.append(log_q.cpu())
    return torch.cat(psis, dim=0), torch.cat(logqs, dim=0)


def det_log_weights(psi_fine, log_q, beta_fine, psi_coarse, beta_coarse):
    """log w = -S_det(psi_f; beta_f) + S_det(psi_c; beta_c) - log q(psi_f | psi_c).

    The fiber form. The proposal joint is pi_c(psi_c) q(psi_f | psi_c) with both
    factors known -- the coarse base is HMC at beta_coarse and its psi marginal
    IS exp(-S_det(beta_coarse))/Z by construction, which is what makes the
    coarse action the right thing to add back.
    """
    with torch.no_grad():
        fine_action = DetSectorAction(float(beta_fine))
        coarse_action = DetSectorAction(float(beta_coarse))
        log_w = -fine_action.per_config(psi_fine.float()).cpu() - log_q.cpu()
        log_w = log_w + coarse_action.per_config(psi_coarse.float()).cpu()
    return log_w


def det_free_energy_certificate(log_w, fine_L, beta_fine, beta_coarse) -> dict:
    """E[w] = (2 pi)^{N_f} Z(beta_f, L_f) / Z(beta_c, L_c), from the U(2)
    character expansion on the torus.

    Z here is the FULL U(2) partition function and that is not a slip: the
    psi-marginal is obtained by integrating SU(2) out of the U(2) measure, so
    the two partition functions are the same number. The (2 pi)^{N_f} converts
    the normalized angular measure the character expansion uses to the Lebesgue
    measure the ODE density is written against; the coarse side's volume cancels
    against Z_c's.
    """
    coarse_L = fine_L // 2
    lw = log_w.double()
    m = lw.max()
    w = torch.exp(lw - m)
    n = w.numel()
    est = float(m + torch.log(w.mean()))
    exact = (
        2 * fine_L * fine_L * math.log(2.0 * math.pi)
        + log_partition(float(beta_fine), fine_L)
        - log_partition(float(beta_coarse), coarse_L)
    )
    n_sites = 2 * fine_L * fine_L
    kl = float(exact - lw.mean())
    return {
        "log_mean_w": est,
        "exact_delta_F": exact,
        "gap": est - exact,
        "sem": float(w.std() / (math.sqrt(n) * w.mean())),
        "n": n,
        "kl_from_mean_log_w": kl,
        "kl_sem": float(lw.std() / math.sqrt(n)),
        "kl_per_site": kl / n_sites,
        "log_weight_std": float(lw.std()),
    }


def ess_per_n(log_w: torch.Tensor) -> float:
    lw = log_w.double() - log_w.double().max()
    w = torch.exp(lw)
    return float(w.sum() ** 2 / (w.numel() * (w ** 2).sum()))
