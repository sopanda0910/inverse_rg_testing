"""Local heatbath / overrelaxation / Metropolis updates and the winding move, 2D U(2).

Every link sits in exactly two plaquettes, whose contribution to the action is
`beta * (1/2) ReTr(U Sigma)` with `Sigma` the staple sum of `lattice.staples`.
Writing U = e^{i phi} q and n = q Sigma (a complex quaternion), that local weight
splits into two conditionals that are each exactly sampleable:

    (1/2) ReTr(U Sigma) = Re(e^{i phi} n_0) = |n_0| cos(phi + arg n_0)

so the CENTRAL PHASE is von Mises with concentration beta |n_0|; and, at fixed
phi, with s = e^{i phi} Sigma,

    (1/2) ReTr(U Sigma) = k . q,   k = (Re s_0, -Re s_1, -Re s_2, -Re s_3)

so the SU(2) PART is the standard heatbath p(q) proportional to exp(beta k . q).
Alternating the two is a Gibbs sampler on U(2) -- the U(2) analogue of
Cabibbo-Marinari, exact here because U(1) x SU(2) covers the group.

That second conditional is also the workhorse of the whole project:
`conditional_su2_sweeps` samples the SU(2) sector at a FROZEN determinant sector,
which is exactly p(q | psi) in the factorization p(psi, q) = p(psi) p(q | psi).

Overrelaxation is microcanonical in both sectors: reflect phi about -arg n_0, and
reflect q about the axis k-hat (q -> 2 (q . k-hat) k-hat - q, an element of O(4),
hence Haar-preserving on the unit-quaternion sphere, and exactly k . q preserving).

Checkerboarding: an x-link's staple contains x-links only at y +- 1, so x-links
are updated on even/odd y sublattices and y-links on even/odd x sublattices --
identical to `u1_2d.lgt.local_updates`.
"""

import math

import torch

from .lattice import (
    TWO_PI,
    u2_conj,
    det_links,
    half_retr,
    plaquette,
    quat_mul,
    quat_normalize,
    staples,
    to_complex_quaternion,
    u2_normalize,
    wrap,
)

_MAX_REJECTION_ROUNDS = 200
# Above this concentration the Kennedy-Pendleton gamma envelope beats plain
# rejection against the Haar measure, and below it the reverse; both are exact,
# so the threshold only trades acceptance rate.
_KP_THRESHOLD = 1.5


def _parity_mask(lattice_size: int, mu: int, parity: int, device) -> torch.Tensor:
    coords = torch.arange(lattice_size, device=device)
    line = coords % 2 == parity
    if mu == 0:
        return line.view(1, -1).expand(lattice_size, lattice_size)
    return line.view(-1, 1).expand(lattice_size, lattice_size)


def sample_su2_scalar(concentration: torch.Tensor) -> torch.Tensor:
    """w0 ~ p(w0) proportional to sqrt(1 - w0^2) exp(a w0) on [-1, 1], a >= 0.

    Two exact rejection samplers, selected per element by `_KP_THRESHOLD`:

    * Kennedy-Pendleton, for large a: substituting w0 = 1 - d gives a density
      proportional to sqrt(d (2 - d)) e^{-a d}, bounded by the Gamma(3/2, a)
      envelope sqrt(2 d) e^{-a d}; drawing d = -(log r1 + cos^2(2 pi r2) log r3)/a
      from that Gamma and accepting with probability sqrt(1 - d/2) is exact.
    * Plain rejection against Haar, for small a: draw w0 from sqrt(1 - w0^2) (the
      first component of a uniform unit quaternion) and accept with e^{a (w0 - 1)}.

    The loop reruns only the not-yet-accepted entries, so it terminates in a few
    rounds at every coupling instead of leaving a tail of unsampled links.
    """
    a = concentration.clamp_min(1e-12)
    use_kp = a >= _KP_THRESHOLD
    out = torch.zeros_like(a)
    done = torch.zeros_like(a, dtype=torch.bool)
    for _ in range(_MAX_REJECTION_ROUNDS):
        r1, r2, r3, r4 = (torch.rand_like(a).clamp_min(1e-30) for _ in range(4))
        delta = -(torch.log(r1) + torch.cos(TWO_PI * r2).square() * torch.log(r3)) / a
        kp_ok = r4.square() <= (1.0 - 0.5 * delta)
        kp_value = 1.0 - delta

        gauss = torch.randn(a.shape + (4,), device=a.device, dtype=a.dtype)
        haar_value = quat_normalize(gauss)[..., 0]
        haar_ok = torch.rand_like(a).clamp_min(1e-30).log() < a * (haar_value - 1.0)

        candidate = torch.where(use_kp, kp_value, haar_value)
        accept = torch.where(use_kp, kp_ok, haar_ok) & ~done
        out = torch.where(accept, candidate, out)
        done = done | accept
        if bool(done.all()):
            break
    return out.clamp(-1.0, 1.0)


def sample_su2_heatbath(k: torch.Tensor, beta: float) -> torch.Tensor:
    """Draw q ~ exp(beta k . q) on SU(2). `k` is a real 4-vector field [..., 4].

    Sampled in the frame where the axis is the identity (w0 from
    `sample_su2_scalar`, the remaining three components uniform on the sphere of
    radius sqrt(1 - w0^2)), then rotated back by q = w k-hat, which works because
    (w k-hat) . k-hat = w0 for unit quaternions.
    """
    norm = k.norm(dim=-1, keepdim=True)
    axis = k / norm.clamp_min(1e-12)
    w0 = sample_su2_scalar(beta * norm.squeeze(-1))
    direction = quat_normalize(torch.randn(w0.shape + (3,), device=k.device, dtype=k.dtype))
    radius = (1.0 - w0.square()).clamp_min(0.0).sqrt()
    w = torch.cat([w0.unsqueeze(-1), radius.unsqueeze(-1) * direction], dim=-1)
    return quat_normalize(quat_mul(w, axis))


def _su2_axis(links_mu: torch.Tensor, staple_mu: torch.Tensor) -> torch.Tensor:
    """k such that (1/2) ReTr(U Sigma) = k . q at the link's current phase."""
    phase = links_mu[..., 0]
    rotated = torch.complex(torch.cos(phase), torch.sin(phase)).unsqueeze(-1) * staple_mu
    return torch.cat([rotated[..., :1].real, -rotated[..., 1:].real], dim=-1)


def _phase_environment(links_mu: torch.Tensor, staple_mu: torch.Tensor) -> torch.Tensor:
    """n_0 (complex) with (1/2) ReTr(U Sigma) = Re(e^{i phi} n_0)."""
    quat = links_mu[..., 1:].to(staple_mu.dtype)
    return quat_mul(quat, staple_mu)[..., 0]


def heatbath_sweep(links: torch.Tensor, beta: float, update_phase: bool = True,
                   update_su2: bool = True) -> torch.Tensor:
    """One full checkerboard Gibbs sweep. `links`: [B, 2, L, L, 5].

    With `update_phase=False` this is the CONDITIONAL SU(2) sampler at frozen
    determinant sector -- the p(q | psi) of the factorized lift.
    """
    links = links.clone()
    lattice_size = links.shape[-2]
    for mu in (0, 1):
        for parity in (0, 1):
            staple = staples(links, mu=mu)
            mask = _parity_mask(lattice_size, mu, parity, links.device)
            current = links[:, mu]
            updated = current.clone()
            if update_phase:
                n0 = _phase_environment(current, staple)
                loc = -torch.angle(n0)
                conc = (beta * n0.abs()).clamp_min(1e-8)
                new_phase = torch.distributions.VonMises(loc, conc).sample()
                updated = torch.cat([wrap(new_phase).unsqueeze(-1), updated[..., 1:]], dim=-1)
            if update_su2:
                k = _su2_axis(updated, staple)
                updated = torch.cat([updated[..., :1], sample_su2_heatbath(k, beta)], dim=-1)
            links[:, mu] = torch.where(mask.unsqueeze(-1), updated, current)
    return links


def overrelaxation_sweep(links: torch.Tensor, update_phase: bool = True,
                         update_su2: bool = True) -> torch.Tensor:
    """One microcanonical overrelaxation sweep; exact for the Wilson U(2) action."""
    links = links.clone()
    lattice_size = links.shape[-2]
    for mu in (0, 1):
        for parity in (0, 1):
            staple = staples(links, mu=mu)
            mask = _parity_mask(lattice_size, mu, parity, links.device)
            current = links[:, mu]
            updated = current.clone()
            if update_phase:
                n0 = _phase_environment(current, staple)
                reflected = wrap(-2.0 * torch.angle(n0) - current[..., 0])
                updated = torch.cat([reflected.unsqueeze(-1), updated[..., 1:]], dim=-1)
            if update_su2:
                k = _su2_axis(updated, staple)
                axis = k / k.norm(dim=-1, keepdim=True).clamp_min(1e-12)
                quat = updated[..., 1:]
                projection = (quat * axis).sum(dim=-1, keepdim=True)
                updated = torch.cat(
                    [updated[..., :1], quat_normalize(2.0 * projection * axis - quat)], dim=-1
                )
            links[:, mu] = torch.where(mask.unsqueeze(-1), updated, current)
    return links


def metropolis_sweep(links: torch.Tensor, action, proposal_width: float | None = None,
                     update_phase: bool = True, update_su2: bool = True) -> torch.Tensor:
    """Local random-walk Metropolis sweep in the u(2) algebra; works for any action
    exposing `beta`, and is the fallback when a conditional is not available."""
    from .lattice import u2_exp, u2_mul

    links = links.clone()
    lattice_size = links.shape[-2]
    if proposal_width is None:
        proposal_width = 1.0 / math.sqrt(2.0 * action.beta + 1.0)
    for mu in (0, 1):
        for parity in (0, 1):
            staple = staples(links, mu=mu)
            current = links[:, mu]
            step = proposal_width * torch.randn(current.shape[:-1] + (4,),
                                                device=links.device, dtype=links.dtype)
            if not update_phase:
                step[..., 0] = 0.0
            if not update_su2:
                step[..., 1:] = 0.0
            proposal = u2_mul(u2_exp(step), current)
            old = quat_mul(to_complex_quaternion(current), staple)[..., 0].real
            new = quat_mul(to_complex_quaternion(proposal), staple)[..., 0].real
            accept = torch.rand_like(old).log() < action.beta * (new - old)
            mask = _parity_mask(lattice_size, mu, parity, links.device) & accept
            links[:, mu] = torch.where(mask.unsqueeze(-1), proposal, current)
    return links


# --------------------------------------------------------------------------
# global determinant winding moves
# --------------------------------------------------------------------------
#
# THE ONE FACT THAT ORGANIZES ALL OF THIS: the topological charge of a U(2)
# configuration depends ONLY on its determinant field. Q = sum_p wrap(arg det P_p)
# / 2 pi, det is a homomorphism, and det U = e^{2 i phi}, so Q is a functional of
# psi = wrap(2 phi) alone and the SU(2) sector cannot change it. That is why the
# inverse-RG ladder transports topology for free -- set psi and Q follows -- and
# it is exactly the U(1) statement this design started from.
#
# For a GLOBAL METROPOLIS MOVE inside a fixed configuration there is one extra
# wrinkle, and it is the Z_2 in U(2) = (U(1) x SU(2)) / Z_2. Multiplying the
# ordered product of all plaquettes gives e^{i sum_p phi_p} (ordered prod q_p) = 1,
# so
#
#       Q even  <=>  ordered product of SU(2) plaquettes = +1
#       Q odd   <=>  ordered product of SU(2) plaquettes = -1.
#
# An EVEN change of Q therefore needs nothing from the SU(2) sector: the plain
# U(1) instanton added to phi shifts every plaquette phase by 2 pi / V, costs
# O(beta / V), and gives delta Q = +-2. That is `central_winding_field`, and it is
# the U(1) move verbatim.
#
# An ODD change of Q cannot leave the SU(2) sector alone. Choosing the branch of
# phi = psi / 2 link by link is a Z_2 gauge field, and flipping one link flips two
# plaquettes, so the PARITY of the number of plaquettes carrying a spurious -1 is
# branch independent -- and it is odd. Concretely, halving the U(1) instanton
# leaves exactly one plaquette with an extra factor -1, costing 2 beta (measured:
# dS = 37 at beta = 20, L = 8, against the O(beta / V) = 0.31 an even move costs).
# The repair is to move inside the U(1) subgroup generated by the projector
# T = (I + n.sigma) / 2 -- diag(e^{i lam}, 1) in the n colour frame -- which
# spreads the required -1 SU(2) monodromy smoothly over the lattice. That is
# `winding_field` at odd charge. It is topologically correct, but its transition
# column does not commute with the SU(2) background, so its cost is O(beta L) in a
# generic gauge (measured 110 at beta = 20, L = 8) rather than O(beta / V), and
# gauge fixing does not remove it.
#
# So odd-Q global moves are intrinsically harder in U(2) than in U(1), and no
# fixed shift field avoids it. The generative route does not care: it sets psi
# directly and then samples p(q | psi) exactly with `conditional_su2_sweeps`. That
# asymmetry is a result of this project, not a limitation of it.

def central_winding_field(lattice_size: int, device=None, dtype=torch.float32) -> torch.Tensor:
    """phi-shift giving delta Q = +2, as a [2, L, L] field. Purely central, so it
    commutes with everything and costs O(beta / V) -- the U(1) instanton, unchanged."""
    from u1_2d.lgt.local_updates import instanton_field

    return instanton_field(lattice_size, device=device, dtype=dtype)


def winding_field(lattice_size: int, charge: int = 2, axis: torch.Tensor | None = None,
                  device=None, dtype=torch.float32) -> torch.Tensor:
    """Shift field S with Q[S] = `charge`, as U(2) links [2, L, L, 5].

    Even charge: purely central, S = e^{i lam / 2} with lam = (charge / 2) times the
    U(1) instanton. Odd charge: the U(1)_T subgroup element exp(i lam T) with
    T = (I + n.sigma) / 2, which carries the -1 SU(2) monodromy odd sectors require.
    `axis` is the colour direction n (default sigma_3); randomizing it per proposal
    is free and avoids a fixed colour bias.
    """
    from u1_2d.lgt.local_updates import instanton_field
    from .lattice import su2_exp

    base = instanton_field(lattice_size, device=device, dtype=dtype)
    if charge % 2 == 0:
        lam = (charge // 2) * base
        quat = torch.zeros(lam.shape + (4,), device=device, dtype=dtype)
        quat[..., 0] = 1.0
        return torch.cat([wrap(lam).unsqueeze(-1), quat], dim=-1)
    if axis is None:
        axis = torch.tensor([0.0, 0.0, 1.0], device=device, dtype=dtype)
    lam = charge * base
    return torch.cat([wrap(0.5 * lam).unsqueeze(-1),
                      su2_exp(0.5 * lam.unsqueeze(-1) * axis)], dim=-1)


def apply_winding(links: torch.Tensor, delta_q: torch.Tensor,
                  axis: torch.Tensor | None = None) -> torch.Tensor:
    """Shift each configuration determinant winding by the integer `delta_q`.

    Even and odd parts are applied separately so the free even part never pays for
    the expensive odd one: delta_q = 2 m + r with r in {-1, 0, 1} becomes the
    central 2m-move composed with at most one odd move.
    """
    from .lattice import u2_mul

    size = links.shape[-2]
    delta_q = delta_q.to(links.device).round()
    out = links
    even = (delta_q / 2.0).trunc() * 2.0
    odd = delta_q - even
    if bool((even != 0).any()):
        field = central_winding_field(size, device=links.device, dtype=links.dtype)
        scale = (even / 2.0).view((-1,) + (1,) * (links.dim() - 2))
        out = out.clone()
        out[..., 0] = wrap(out[..., 0] + scale * field)
    if bool((odd != 0).any()):
        shift = winding_field(size, charge=1, axis=axis,
                              device=links.device, dtype=links.dtype).unsqueeze(0)
        forward = u2_mul(shift, out)
        backward = u2_mul(u2_conj(shift), out)
        mask = odd.view((-1,) + (1,) * (links.dim() - 1))
        out = torch.where(mask > 0, forward, torch.where(mask < 0, backward, out))
    return out


def set_topological_charge(links: torch.Tensor, target_q: torch.Tensor,
                           n_iterations: int = 4) -> torch.Tensor:
    """Move each configuration into the sector `target_q` with the winding map.

    The U(2) analogue of `u1_2d.pipeline.ladder.apply_coarse_charge`, and the
    mechanism that transports topology across an inverse-RG step. Iterated because
    a wrap event can make one pass land short. Whatever action defect the odd part
    of the move leaves in the SU(2) sector is removed EXACTLY by
    `conditional_su2_sweeps`, which is why the ladder can afford an odd-charge move
    that a Metropolis chain cannot.
    """
    from .lattice import topological_charge

    for _ in range(n_iterations):
        delta = target_q.to(links.device) - topological_charge(links)
        if not delta.any():
            break
        links = apply_winding(links, delta)
    return links


def marginal_winding_update(links: torch.Tensor, action, charge_step: int = 1,
                            n_su2_sweeps: int = 25,
                            generator: torch.Generator | None = None
                            ) -> tuple[torch.Tensor, torch.Tensor]:
    """Q -> Q +- charge_step, accepted on the EXACT psi-marginal.

    The proposal is a pure phase multiply U -> e^{i s lam / 2} U with lam the
    winding-1 U(1) instanton: phi shifts by s lam / 2, so psi = 2 phi shifts by
    s lam and delta Q = s exactly. Symmetric and involutive, so no Jacobian.

    THE POINT IS THE ACCEPTANCE, NOT THE PROPOSAL. Accepting on the joint action
    charges the move 2 beta for one plaquette whose cos(phi_p) flips sign -- an
    SU(2) sector that cannot follow. `DetSectorAction` is the SU(2)-integrated
    marginal, exact plaquette by plaquette in 2D, so accepting on it prices only
    the determinant sector; the SU(2) sector is then resampled from its exact
    conditional, which is where the flipped plaquette is absorbed for free.

    Validity: step one is a collapsed Metropolis step whose acceptance depends on
    psi alone, so the psi-marginal evolves under a kernel with pi(psi) stationary;
    the conditional resample restores p(q | psi). The composite is stationary for
    pi(psi, q) provided the resample reaches equilibrium -- at finite
    `n_su2_sweeps` it is approximate, and that is the one approximation here.
    2D SU(2) at frozen psi has no topological obstruction and mixes fast.
    """
    from u1_2d.lgt.local_updates import instanton_field

    from .actions import DetSectorAction
    from .lattice import det_links

    batch, size = links.shape[0], links.shape[-2]
    det_action = DetSectorAction(action.beta)
    lam = instanton_field(size, device=links.device, dtype=links.dtype)

    signs = torch.where(
        torch.rand(batch, device=links.device, generator=generator) < 0.5, 1.0, -1.0)
    alpha = 0.5 * charge_step * signs.view(-1, 1, 1, 1) * lam.unsqueeze(0)
    proposal = links.clone()
    proposal[..., 0] = wrap(proposal[..., 0] + alpha)

    delta_s = (det_action.per_config(det_links(proposal))
               - det_action.per_config(det_links(links)))
    u = torch.rand(batch, device=links.device, generator=generator)
    accept = u < torch.exp(-delta_s.clamp(max=60.0))
    out = torch.where(accept.view(-1, 1, 1, 1, 1), proposal, links)
    if n_su2_sweeps and bool(accept.any()):
        # Only accepted configurations need refreshing. Resampling the rest would
        # be valid but wasteful, and it would decorrelate SU(2) faster in the
        # rejected arm than in the accepted one for no reason.
        out = torch.where(accept.view(-1, 1, 1, 1, 1),
                          conditional_su2_sweeps(out, action, n_su2_sweeps),
                          out)
    return out, accept


def winding_update(links: torch.Tensor, action, charge_step: int = 2,
                   random_axis: bool = True, odd_mode: str = "marginal",
                   n_su2_sweeps: int = 25) -> tuple[torch.Tensor, torch.Tensor]:
    """Global Metropolis move Q -> Q +- charge_step; symmetric, so acceptance is
    min(1, e^{-dS}).

    `charge_step=2` (default) is the cheap central move: dS = O(beta / V) and high
    acceptance at any coupling. It cannot change the parity of Q.

    `charge_step` odd routes to `marginal_winding_update` unless
    `odd_mode="joint"`. The joint route is kept only to reproduce pre-2026-08-20
    results: it proposes a correct delta Q = +-1 and is accepted essentially
    never (measured 0.000 at L=16, beta=28), because it prices a 2 beta plaquette
    against an SU(2) sector it forbids to move. See `docs/INSTANTON.md`.
    """
    if charge_step % 2 and odd_mode == "marginal":
        return marginal_winding_update(links, action, charge_step=charge_step,
                                       n_su2_sweeps=n_su2_sweeps)
    batch = links.shape[0]
    signs = torch.where(torch.rand(batch, device=links.device) < 0.5, 1.0, -1.0)
    axis = None
    if random_axis and charge_step % 2:
        axis = torch.randn(3, device=links.device, dtype=links.dtype)
        axis = axis / axis.norm()
    proposal = apply_winding(links, signs * charge_step, axis=axis)
    delta_s = action.per_config(proposal) - action.per_config(links)
    accept = torch.rand(batch, device=links.device) < torch.exp(-delta_s)
    return torch.where(accept.view(-1, 1, 1, 1, 1), proposal, links), accept


def retherm_sweeps(
    links: torch.Tensor,
    action,
    n_sweeps: int,
    n_overrelax_per_sweep: int = 2,
    topological_updates: bool = False,
    update_phase: bool = True,
    update_su2: bool = True,
) -> torch.Tensor:
    """Local rethermalization: heatbath plus overrelaxation, optionally restricted
    to one sector. As in `u1_2d`, `topological_updates` is off by default so that
    rethermalization cannot mask whether the generative model reproduces topology.
    """
    squeeze = links.dim() == 4
    if squeeze:
        links = links.unsqueeze(0)
    with torch.no_grad():
        for _ in range(n_sweeps):
            links = heatbath_sweep(links, action.beta, update_phase=update_phase,
                                   update_su2=update_su2)
            for _ in range(n_overrelax_per_sweep):
                links = overrelaxation_sweep(links, update_phase=update_phase,
                                             update_su2=update_su2)
            if topological_updates:
                links, _ = winding_update(links, action)
    if update_phase:
        links = u2_normalize(links)
    else:
        # Re-wrapping phi through atan2 is not the identity in floating point, and
        # the whole point of the conditional sampler is that psi -- and therefore Q
        # -- comes back bit-for-bit unchanged. Renormalize only what was touched.
        links = torch.cat([links[..., :1], quat_normalize(links[..., 1:])], dim=-1)
    return links.squeeze(0) if squeeze else links


def conditional_su2_sweeps(links: torch.Tensor, action, n_sweeps: int,
                           n_overrelax_per_sweep: int = 2) -> torch.Tensor:
    """Sample p(q | psi): equilibrate the SU(2) sector at a frozen determinant sector.

    This is exact for the conditional -- the determinant field psi is untouched, so
    the topological charge (and every determinant observable) is preserved
    bit-for-bit -- and it mixes fast, because 2D SU(2) has no topological
    obstruction. It is the half of the factorized lift that needs no model.
    """
    return retherm_sweeps(links, action, n_sweeps,
                          n_overrelax_per_sweep=n_overrelax_per_sweep,
                          update_phase=False, update_su2=True)
