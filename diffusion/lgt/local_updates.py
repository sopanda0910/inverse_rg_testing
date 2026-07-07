"""Local heatbath / overrelaxation / Metropolis updates for 2D compact U(1).

Every link theta sits in exactly two plaquettes. Writing the local action as
    lw(theta) = w(theta + c1) + w(c2 - theta)
with w the single-plaquette log-weight and c1, c2 the link-independent parts:

    x-link ux(x,y):   p(x,y)   =  ux + c1,  c1 = uy(x+1,y) - ux(x,y+1) - uy(x,y)
                      p(x,y-1) = -ux + c2,  c2 = ux(x,y-1) + uy(x+1,y-1) - uy(x,y-1)
    y-link uy(x,y):   p(x-1,y) =  uy + c1,  c1 = ux(x-1,y) - ux(x-1,y+1) - uy(x-1,y)
                      p(x,y)   = -uy + c2,  c2 = ux(x,y) + uy(x+1,y) - ux(x,y+1)

Heatbath (Wilson): the conditional is von Mises with
    R e^{i theta0} = e^{-i c1} + e^{i c2},  p(theta) ~ exp(beta R cos(theta - theta0)).

Overrelaxation (any plaquette action): theta -> wrap(c2 - c1 - theta) swaps the two
plaquette angles, so it is exactly microcanonical and always accepted.

Checkerboarding: the x-link staple contains x-links only at y+-1, so x-links are
updated on even/odd y sublattices; y-links on even/odd x sublattices (4 passes/sweep).
"""

import math

import torch

from .lattice import wrap
from .actions import WilsonAction

TWO_PI = 2.0 * math.pi


def _staple_parts(field: torch.Tensor, mu: int) -> tuple[torch.Tensor, torch.Tensor]:
    ux, uy = field[:, 0], field[:, 1]
    if mu == 0:
        c1 = torch.roll(uy, -1, dims=-2) - torch.roll(ux, -1, dims=-1) - uy
        c2_at_site = ux + torch.roll(uy, -1, dims=-2) - uy
        c2 = torch.roll(c2_at_site, 1, dims=-1)
    else:
        c1_at_site = ux - torch.roll(ux, -1, dims=-1) - uy
        c1 = torch.roll(c1_at_site, 1, dims=-2)
        c2 = ux + torch.roll(uy, -1, dims=-2) - torch.roll(ux, -1, dims=-1)
    return c1, c2


def _parity_mask(lattice_size: int, mu: int, parity: int, device) -> torch.Tensor:
    coords = torch.arange(lattice_size, device=device)
    if mu == 0:
        line = (coords % 2 == parity)
        return line.view(1, -1).expand(lattice_size, lattice_size)
    line = (coords % 2 == parity)
    return line.view(-1, 1).expand(lattice_size, lattice_size)


def heatbath_sweep(field: torch.Tensor, beta: float) -> torch.Tensor:
    """One full von Mises heatbath sweep for the Wilson action. field: [B, 2, L, L]."""
    field = field.clone()
    lattice_size = field.shape[-1]
    for mu in (0, 1):
        for parity in (0, 1):
            c1, c2 = _staple_parts(field, mu)
            re = torch.cos(c1) + torch.cos(c2)
            im = torch.sin(c2) - torch.sin(c1)
            radius = torch.sqrt(re.square() + im.square()).clamp_min(1e-8)
            loc = torch.atan2(im, re)
            new_links = torch.distributions.VonMises(loc, beta * radius).sample()
            mask = _parity_mask(lattice_size, mu, parity, field.device)
            field[:, mu] = torch.where(mask, wrap(new_links), field[:, mu])
    return field


def overrelaxation_sweep(field: torch.Tensor) -> torch.Tensor:
    """One microcanonical overrelaxation sweep, exact for any plaquette action."""
    field = field.clone()
    lattice_size = field.shape[-1]
    for mu in (0, 1):
        for parity in (0, 1):
            c1, c2 = _staple_parts(field, mu)
            reflected = wrap(c2 - c1 - field[:, mu])
            mask = _parity_mask(lattice_size, mu, parity, field.device)
            field[:, mu] = torch.where(mask, reflected, field[:, mu])
    return field


def metropolis_sweep(field: torch.Tensor, action, proposal_width: float | None = None) -> torch.Tensor:
    """One local random-walk Metropolis sweep for any plaquette action (used for Villain)."""
    field = field.clone()
    lattice_size = field.shape[-1]
    if proposal_width is None:
        proposal_width = 1.0 / math.sqrt(2.0 * action.beta + 1.0)
    for mu in (0, 1):
        for parity in (0, 1):
            c1, c2 = _staple_parts(field, mu)
            theta = field[:, mu]
            proposal = theta + proposal_width * torch.randn_like(theta)
            log_w_old = action.plaquette_log_weight(wrap(theta + c1)) + action.plaquette_log_weight(
                wrap(c2 - theta)
            )
            log_w_new = action.plaquette_log_weight(wrap(proposal + c1)) + action.plaquette_log_weight(
                wrap(c2 - proposal)
            )
            accept = torch.rand_like(theta).log() < (log_w_new - log_w_old)
            mask = _parity_mask(lattice_size, mu, parity, field.device) & accept
            field[:, mu] = torch.where(mask, wrap(proposal), theta)
    return field


def instanton_field(lattice_size: int, device=None, dtype=torch.float32) -> torch.Tensor:
    """Smooth Q = +1 configuration on the torus: every plaquette angle is 2 pi / L^2.

        theta_y(x, y) = 2 pi x / L^2
        theta_x(L-1, y) = -2 pi y / L   (transition-function correction on the last column)
    """
    coords = torch.arange(lattice_size, device=device, dtype=dtype)
    theta_y = (TWO_PI / lattice_size**2) * coords.view(-1, 1).expand(lattice_size, lattice_size)
    theta_x = torch.zeros(lattice_size, lattice_size, device=device, dtype=dtype)
    theta_x[-1, :] = -(TWO_PI / lattice_size) * coords
    return torch.stack([theta_x, theta_y.clone()], dim=0)


def topological_update(field: torch.Tensor, action) -> tuple[torch.Tensor, torch.Tensor]:
    """Global Metropolis move Q -> Q +- 1 by adding a smooth instanton. field: [B, 2, L, L].

    The proposal is symmetric (sign chosen uniformly), so acceptance is min(1, e^{-dS});
    dS is O(beta / V) for the smooth instanton, so acceptance stays high even at large
    beta where local updates and HMC are topologically frozen.
    """
    batch = field.shape[0]
    inst = instanton_field(field.shape[-1], device=field.device, dtype=field.dtype)
    signs = torch.where(
        torch.rand(batch, device=field.device) < 0.5, 1.0, -1.0
    ).view(-1, 1, 1, 1)
    proposal = wrap(field + signs * inst)
    delta_s = action.per_config(proposal) - action.per_config(field)
    accept = torch.rand(batch, device=field.device) < torch.exp(-delta_s)
    mask = accept.view(-1, 1, 1, 1)
    return torch.where(mask, proposal, field), accept


def retherm_sweeps(
    field: torch.Tensor,
    action,
    n_sweeps: int,
    n_overrelax_per_sweep: int = 2,
    topological_updates: bool = False,
) -> torch.Tensor:
    """Local rethermalization: per sweep, one ergodic update (heatbath for Wilson,
    Metropolis for Villain) followed by overrelaxation sweeps. field: [B, 2, L, L].

    `topological_updates` is off by default: rethermalization after conditional
    generation is meant to fix UV modes only, and enabling Q-hops here would mask
    whether the generative model reproduces topology by itself.
    """
    squeeze = field.dim() == 3
    if squeeze:
        field = field.unsqueeze(0)
    with torch.no_grad():
        for _ in range(n_sweeps):
            if isinstance(action, WilsonAction):
                field = heatbath_sweep(field, action.beta)
            else:
                field = metropolis_sweep(field, action)
            for _ in range(n_overrelax_per_sweep):
                field = overrelaxation_sweep(field)
            if topological_updates:
                field, _ = topological_update(field, action)
    return field.squeeze(0) if squeeze else field
