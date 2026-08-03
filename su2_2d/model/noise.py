"""Heat-kernel noising of SU(2) links and the DSM targets.

LEFT noising, matching the tangent convention used by the HMC, the score
head, and the sampler (curves e^{i t sigma_a/2} U):

    U_t = exp(i (omega.sigma)/2) U_0,

with |omega| = 2 theta, theta drawn from the exact class-angle density
K_s sin^2, axis uniform, s = sigma^2. The exact DSM target is the conditional
heat-kernel score; the small-sigma proxy is the flat-space -omega/sigma^2
(their gap grows with sigma — ~0.1% at sigma 0.1 up to ~30% at 1.5)."""

import torch

from ..lgt import group
from ..lgt.heat_kernel import exact_conditional_score, sample_angle


def noise_links(u0: torch.Tensor, sigma: float,
                generator: torch.Generator | None = None) -> tuple[torch.Tensor, torch.Tensor]:
    """Returns (u_t, omega) with omega the sampled algebra displacement."""
    s = sigma * sigma
    theta = sample_angle(s, u0.shape[:-1], generator=generator)
    axis = torch.randn(*u0.shape[:-1], 3, generator=generator)
    axis = axis / axis.norm(dim=-1, keepdim=True).clamp_min(1e-12)
    omega = 2.0 * theta.unsqueeze(-1) * axis
    u_t = group.normalize(group.mul(group.expmap(omega), u0))
    return u_t, omega


def proxy_score_target(omega: torch.Tensor, sigma: float) -> torch.Tensor:
    return -omega / (sigma * sigma)


def exact_score_target(u_t: torch.Tensor, u_0: torch.Tensor, sigma: float) -> torch.Tensor:
    return exact_conditional_score(u_t, u_0, sigma)
