"""SU(2) lattice geometry on a periodic 2D square lattice.

Link fields have shape [..., 2, L, L, 4]: index -4 is the direction mu
(0 = x, 1 = y), dims -3/-2 are the x/y sites, and the last dim is the
quaternion. Same site convention as u1_2d: the plaquette anchored at (x, y) is

    P(x, y) = Ux(x, y) Uy(x+1, y) Ux(x, y+1)^-1 Uy(x, y)^-1,

the non-abelian counterpart of the U(1) angle sum.
"""

import torch

from . import group

X_DIM, Y_DIM = -3, -2


def _as_batched(field: torch.Tensor) -> tuple[torch.Tensor, bool]:
    if field.dim() == 4:
        return field.unsqueeze(0), True
    return field, False


def _roll(t: torch.Tensor, shift: int, dim: int) -> torch.Tensor:
    return torch.roll(t, shifts=shift, dims=dim)


def plaquette_word(field: torch.Tensor) -> torch.Tensor:
    """[..., 2, L, L, 4] -> [..., L, L, 4] path-ordered plaquette."""
    field, squeezed = _as_batched(field)
    ux, uy = field[..., 0, :, :, :], field[..., 1, :, :, :]
    p = group.mul(ux, _roll(uy, -1, X_DIM))
    p = group.mul(p, group.inverse(_roll(ux, -1, Y_DIM)))
    p = group.mul(p, group.inverse(uy))
    return p.squeeze(0) if squeezed else p


def mean_plaquette(field: torch.Tensor) -> torch.Tensor:
    """<(1/2) tr P> per configuration."""
    p = plaquette_word(field)
    return group.trace_half(p).mean(dim=(-2, -1))


def wilson_action(field: torch.Tensor, beta: float) -> torch.Tensor:
    """S = -(beta/2) sum tr P, per configuration."""
    p = plaquette_word(field)
    return -beta * group.trace_half(p).sum(dim=(-2, -1))


def wilson_loop_trace_half(field: torch.Tensor, extent_x: int, extent_y: int) -> torch.Tensor:
    """(1/2) tr of the path-ordered extent_x by extent_y loop at every site."""
    field, squeezed = _as_batched(field)
    ux, uy = field[..., 0, :, :, :], field[..., 1, :, :, :]
    loop = None

    def acc(w, u):
        return u if w is None else group.mul(w, u)

    for k in range(extent_x):
        loop = acc(loop, _roll(ux, -k, X_DIM))
    for k in range(extent_y):
        loop = acc(loop, _roll(_roll(uy, -extent_x, X_DIM), -k, Y_DIM))
    for k in range(extent_x - 1, -1, -1):
        loop = acc(loop, group.inverse(_roll(_roll(ux, -k, X_DIM), -extent_y, Y_DIM)))
    for k in range(extent_y - 1, -1, -1):
        loop = acc(loop, group.inverse(_roll(uy, -k, Y_DIM)))
    out = group.trace_half(loop)
    return out.squeeze(0) if squeezed else out


def gauge_transform(field: torch.Tensor, g: torch.Tensor) -> torch.Tensor:
    """U_mu(x) -> g(x) U_mu(x) g(x + mu_hat)^-1; g has shape [..., L, L, 4]."""
    field, squeezed = _as_batched(field)
    if g.dim() == 3:
        g = g.unsqueeze(0)
    ux, uy = field[..., 0, :, :, :], field[..., 1, :, :, :]
    new_x = group.mul(group.mul(g, ux), group.inverse(_roll(g, -1, X_DIM)))
    new_y = group.mul(group.mul(g, uy), group.inverse(_roll(g, -1, Y_DIM)))
    out = torch.stack([new_x, new_y], dim=-4)
    return out.squeeze(0) if squeezed else out


def tangent_basis_grad(scalar: torch.Tensor, field: torch.Tensor) -> torch.Tensor:
    """Gradient of a scalar w.r.t. the right-tangent coordinates of every link.

    grad_a(link) = d/dt scalar(U -> exp(i t sigma_a / 2) U) at t = 0, computed
    by autograd through the 4 quaternion components followed by projection on
    the tangent directions T_a U = (1/2) (0, e_a) (x) U.
    field must require grad; scalar must be a single scalar tensor.
    """
    (dq,) = torch.autograd.grad(scalar, field, create_graph=False)
    return project_tangent(dq.detach(), field.detach())


def project_tangent(dq: torch.Tensor, field: torch.Tensor) -> torch.Tensor:
    """Project a raw 4-component gradient onto the 3 tangent coordinates."""
    grads = []
    for a in range(3):
        e = torch.zeros(4, dtype=field.dtype, device=field.device)
        e[1 + a] = 1.0
        t_a = 0.5 * group.mul(e.expand_as(field), field)
        grads.append((dq * t_a).sum(dim=-1))
    return torch.stack(grads, dim=-1)


def wilson_force(field: torch.Tensor, beta: float) -> torch.Tensor:
    """F = -grad S in tangent coordinates, [..., 2, L, L, 3]."""
    x = field.detach().requires_grad_(True)
    s = wilson_action(x, beta)
    return -tangent_basis_grad(s.sum(), x)
