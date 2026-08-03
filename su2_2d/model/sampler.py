"""Ancestral (SMLD) reverse-diffusion sampling on the SU(2) group manifold.

The Euclidean ancestral step transfers to the group through the exponential
map: the mean update and the injected noise both live in the right tangent
space,

    U_{i+1} = U_i exp( i/2 [ (s_i^2 - s_{i+1}^2) score + xi ] . sigma ),
    xi ~ heat-kernel noise at s = s_{i+1}^2 (s_i^2 - s_{i+1}^2) / s_i^2,

which is the exact conditional-Gaussian ancestral step of the U(1) narrative
(section 12) with the wrapped normal replaced by the group heat kernel. The
conditional version feeds blocked-field features of the coarse input, so the
sampler performs the inverse-RG lift once the network is trained
conditionally."""

import torch

from ..lgt import group
from ..lgt.heat_kernel import sample_angle
from .score_head import plaquette_features


def _heat_noise(shape, s, generator):
    theta = sample_angle(s, shape, generator=generator)
    axis = torch.randn(*shape, 3, generator=generator)
    axis = axis / axis.norm(dim=-1, keepdim=True).clamp_min(1e-12)
    return 2.0 * theta.unsqueeze(-1) * axis


def sample(model, schedule, n: int, lattice_size: int, beta: float,
           coarse: torch.Tensor | None = None,
           seed: int | None = None) -> torch.Tensor:
    """Unconditional (coarse=None) or conditional lift sampling."""
    gen = torch.Generator()
    if seed is not None:
        gen.manual_seed(seed)
    u = group.random_haar((n, 2, lattice_size, lattice_size), generator=gen)
    if coarse is not None:
        feats = plaquette_features(coarse)
        cond = torch.repeat_interleave(torch.repeat_interleave(feats, 2, dim=-2), 2, dim=-1)
    else:
        cond = None
    beta_t = torch.full((n,), float(beta))
    sigmas = schedule.sigmas(descending=True)
    with torch.no_grad():
        for i in range(len(sigmas) - 1):
            s_hi, s_lo = float(sigmas[i]), float(sigmas[i + 1])
            gap = s_hi * s_hi - s_lo * s_lo
            score = model.score(u, torch.full((n,), s_hi), beta_t, cond)
            step = gap * score
            noise_s = s_lo * s_lo * gap / (s_hi * s_hi)
            xi = _heat_noise(u.shape[:-1], noise_s, gen) if noise_s > 1e-12 else 0.0
            u = group.normalize(group.mul(group.expmap(step + xi), u))
    return u
