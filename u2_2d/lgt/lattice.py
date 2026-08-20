"""Lattice utilities for 2D U(2) in the split phase-quaternion representation.

Representation (identical to the sibling NTHMC `src/nthmc/u2` code, so
configurations and conventions are interchangeable between the two projects):

    U = e^{i phi} q,   q = q0 I + i sum_a q_a sigma_a  in SU(2)

stored as a real tensor whose last dimension is 5,

    links[..., 0]   = phi          (wrapped to (-pi, pi])
    links[..., 1:5] = (q0, q1, q2, q3),  |q| = 1

so the complex matrix is

    U = e^{i phi} [[q0 + i q3, q2 + i q1], [-q2 + i q1, q0 - i q3]].

Because U(2) = (U(1) x SU(2)) / Z_2, the pair (phi, q) and (phi + pi, -q) denote
the SAME group element. Everything below is invariant under that flip; the code
keeps a representative by wrapping phi and normalizing q.

Index convention (mirrors `u1_2d.lgt.lattice`, shifted by the trailing group axis):
    links[mu, x, y, :] or links[B, mu, x, y, :]; mu = 0 are x-links, mu = 1 are
    y-links; dim -3 is x, dim -2 is y.
    P(x, y) = U_0(x,y) U_1(x+1,y) U_0(x,y+1)^dag U_1(x,y)^dag.

The DETERMINANT SECTOR is the single most useful structure here. det is a group
homomorphism U(2) -> U(1), and det U = e^{2 i phi}, so

    psi_{x,mu} = wrap(2 phi_{x,mu})

is an honest compact U(1) lattice gauge field: an SU(2)-valued gauge
transformation leaves it alone, a U(2) gauge transformation acts on it as a U(1)
gauge transformation, and `det_links` returns it in exactly the [B, 2, L, L]
layout that every `u1_2d.lgt` routine already consumes. All of the topology of
2D U(2) lives there (pi_1(U(2)) = Z, carried by the determinant; pi_1(SU(2)) = 0),
and because det is multiplicative the determinant phase of a plaquette is the
plain SUM of link phases -- the abelian telescope of `u1_2d` survives verbatim
even though the group does not commute.
"""

import math

import torch

TWO_PI = 2.0 * math.pi


# --------------------------------------------------------------------------
# group operations on the split representation
# --------------------------------------------------------------------------

def wrap(phase: torch.Tensor) -> torch.Tensor:
    """Map angles to (-pi, pi] (same convention as `u1_2d.lgt.lattice.wrap`)."""
    return torch.atan2(torch.sin(phase), torch.cos(phase))


def quat_normalize(q: torch.Tensor, eps: float = 1e-12) -> torch.Tensor:
    return q / q.norm(dim=-1, keepdim=True).clamp_min(eps)


def quat_conj(q: torch.Tensor) -> torch.Tensor:
    return torch.cat([q[..., :1], -q[..., 1:]], dim=-1)


def quat_mul(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    """Quaternion product in the convention M(a) M(b) = M(quat_mul(a, b)) with
    M(q) = q0 I + i q_a sigma_a. Note the MINUS on the cross term: it follows
    from (q.sigma)(r.sigma) = (q.r) I + i (q x r).sigma and the explicit i's.
    Works unchanged on COMPLEX components, where it is matrix multiplication for
    arbitrary 2x2 matrices written as m0 I + i m_a sigma_a -- the identity is
    bilinear, so nothing about it needed the unit-norm or reality of a real
    quaternion. `staples` relies on that.
    """
    a0, a1, a2, a3 = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    b0, b1, b2, b3 = b[..., 0], b[..., 1], b[..., 2], b[..., 3]
    return torch.stack(
        [
            a0 * b0 - a1 * b1 - a2 * b2 - a3 * b3,
            a0 * b1 + b0 * a1 - (a2 * b3 - a3 * b2),
            a0 * b2 + b0 * a2 - (a3 * b1 - a1 * b3),
            a0 * b3 + b0 * a3 - (a1 * b2 - a2 * b1),
        ],
        dim=-1,
    )


def su2_exp(algebra: torch.Tensor) -> torch.Tensor:
    """exp(i a_a sigma_a) as a unit quaternion; series-stable at |a| -> 0."""
    r_sq = algebra.square().sum(dim=-1, keepdim=True)
    small = r_sq < 1e-12
    r = r_sq.clamp_min(1e-12).sqrt()
    scalar = torch.where(small, 1.0 - 0.5 * r_sq + r_sq.square() / 24.0, torch.cos(r))
    scale = torch.where(small, 1.0 - r_sq / 6.0 + r_sq.square() / 120.0, torch.sin(r) / r)
    return quat_normalize(torch.cat([scalar, scale * algebra], dim=-1))


def su2_log(q: torch.Tensor) -> torch.Tensor:
    """Inverse of `su2_exp` on the principal branch (|a| < pi)."""
    q = quat_normalize(q)
    q0 = q[..., :1]
    qv = q[..., 1:]
    norm = qv.norm(dim=-1, keepdim=True)
    angle = torch.atan2(norm, q0)
    scale = torch.where(norm > 1e-12, angle / norm.clamp_min(1e-12), torch.ones_like(norm))
    return scale * qv


def u2_normalize(links: torch.Tensor) -> torch.Tensor:
    return torch.cat([wrap(links[..., :1]), quat_normalize(links[..., 1:])], dim=-1)


def u2_mul(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    phase = wrap(a[..., :1] + b[..., :1])
    return torch.cat([phase, quat_mul(a[..., 1:], b[..., 1:])], dim=-1)


def u2_conj(links: torch.Tensor) -> torch.Tensor:
    """Hermitian conjugate / group inverse."""
    return torch.cat([wrap(-links[..., :1]), quat_conj(links[..., 1:])], dim=-1)


def u2_exp(algebra: torch.Tensor) -> torch.Tensor:
    """u(2) -> U(2). `algebra[..., 0]` is the central u(1) coefficient, `[..., 1:4]`
    the three su(2) coefficients: exp(i(d_phi I + d_a sigma_a))."""
    if algebra.shape[-1] != 4:
        raise ValueError(f"u(2) algebra needs 4 components, got {algebra.shape[-1]}")
    return torch.cat([wrap(algebra[..., :1]), su2_exp(algebra[..., 1:])], dim=-1)


def u2_log(links: torch.Tensor) -> torch.Tensor:
    """U(2) -> u(2) on the principal branch, inverse of `u2_exp`."""
    links = u2_normalize(links)
    return torch.cat([links[..., :1], su2_log(links[..., 1:])], dim=-1)


def identity_links(lattice_size: int, batch: int | None = None, device=None,
                   dtype=torch.float32) -> torch.Tensor:
    shape = ((2, lattice_size, lattice_size, 5) if batch is None
             else (batch, 2, lattice_size, lattice_size, 5))
    field = torch.zeros(shape, device=device, dtype=dtype)
    field[..., 1] = 1.0
    return field


def random_links(lattice_size: int, batch: int | None = None, device=None,
                 dtype=torch.float32, generator: torch.Generator | None = None) -> torch.Tensor:
    """Haar-random U(2) links (uniform phase x uniform unit quaternion)."""
    shape = ((2, lattice_size, lattice_size) if batch is None
             else (batch, 2, lattice_size, lattice_size))
    phase = torch.rand(shape + (1,), device=device, dtype=dtype,
                       generator=generator) * TWO_PI - math.pi
    quat = torch.randn(shape + (4,), device=device, dtype=dtype, generator=generator)
    return torch.cat([phase, quat_normalize(quat)], dim=-1)


def to_matrix(links: torch.Tensor) -> torch.Tensor:
    """Split representation -> complex 2x2 matrices [..., 2, 2] (tests / reference)."""
    links = u2_normalize(links)
    phase = links[..., 0]
    q0, q1, q2, q3 = links[..., 1], links[..., 2], links[..., 3], links[..., 4]
    matrix = torch.stack(
        [
            torch.stack([torch.complex(q0, q3), torch.complex(q2, q1)], dim=-1),
            torch.stack([torch.complex(-q2, q1), torch.complex(q0, -q3)], dim=-1),
        ],
        dim=-2,
    )
    factor = torch.complex(torch.cos(phase), torch.sin(phase))
    return factor[..., None, None] * matrix


def from_matrix(matrix: torch.Tensor) -> torch.Tensor:
    """Complex 2x2 U(2) matrices -> split representation (inverse of `to_matrix`)."""
    phase = 0.5 * torch.angle(torch.linalg.det(matrix))
    su2 = matrix * torch.complex(torch.cos(phase), -torch.sin(phase))[..., None, None]
    m00, m01, m10, m11 = su2[..., 0, 0], su2[..., 0, 1], su2[..., 1, 0], su2[..., 1, 1]
    quat = torch.stack(
        [
            0.5 * (m00.real + m11.real),
            0.5 * (m01.imag + m10.imag),
            0.5 * (m01.real - m10.real),
            0.5 * (m00.imag - m11.imag),
        ],
        dim=-1,
    )
    return torch.cat([wrap(phase)[..., None], quat_normalize(quat)], dim=-1)


# --------------------------------------------------------------------------
# lattice geometry
# --------------------------------------------------------------------------

def _as_batched(links: torch.Tensor) -> tuple[torch.Tensor, bool]:
    if links.dim() == 4:
        return links.unsqueeze(0), True
    if links.dim() != 5:
        raise ValueError(f"Expected [2, L, L, 5] or [B, 2, L, L, 5], got {tuple(links.shape)}")
    return links, False


def shift(field: torch.Tensor, dx: int = 0, dy: int = 0) -> torch.Tensor:
    """f(x + dx, y + dy) for a site field [..., L, L, C]."""
    return torch.roll(field, shifts=(-dx, -dy), dims=(-3, -2))


def plaquette(links: torch.Tensor) -> torch.Tensor:
    """P(x,y) = U_0(x,y) U_1(x+1,y) U_0(x,y+1)^dag U_1(x,y)^dag -> [..., L, L, 5]."""
    links, squeezed = _as_batched(links)
    u0, u1 = links[:, 0], links[:, 1]
    loop = u2_mul(u2_mul(u2_mul(u0, shift(u1, dx=1)), u2_conj(shift(u0, dy=1))), u2_conj(u1))
    return loop.squeeze(0) if squeezed else loop


def rectangle_x(links: torch.Tensor) -> torch.Tensor:
    """Closed 2x1 loop (two steps along x, one along y), based at (x, y)."""
    return wilson_loop(links, 2, 1)


def rectangle_y(links: torch.Tensor) -> torch.Tensor:
    """Closed 1x2 loop (one step along x, two along y), based at (x, y)."""
    return wilson_loop(links, 1, 2)


def wilson_loop(links: torch.Tensor, extent_x: int, extent_y: int) -> torch.Tensor:
    """Closed extent_x by extent_y rectangular Wilson loop based at every site."""
    links, squeezed = _as_batched(links)
    u0, u1 = links[:, 0], links[:, 1]
    loop = None
    for step in range(extent_x):
        term = shift(u0, dx=step)
        loop = term if loop is None else u2_mul(loop, term)
    for step in range(extent_y):
        term = shift(u1, dx=extent_x, dy=step)
        loop = term if loop is None else u2_mul(loop, term)
    for step in reversed(range(extent_x)):
        loop = u2_mul(loop, u2_conj(shift(u0, dx=step, dy=extent_y)))
    for step in reversed(range(extent_y)):
        loop = u2_mul(loop, u2_conj(shift(u1, dy=step)))
    return loop.squeeze(0) if squeezed else loop


def polyakov_loops(links: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Winding loops: x-direction loops (one per y) and y-direction loops (one per x)."""
    links, squeezed = _as_batched(links)
    size = links.shape[-2]
    u0, u1 = links[:, 0], links[:, 1]
    loop_x = u0[:, 0]
    for step in range(1, size):
        loop_x = u2_mul(loop_x, u0[:, step])
    loop_y = u1[:, :, 0]
    for step in range(1, size):
        loop_y = u2_mul(loop_y, u1[:, :, step])
    if squeezed:
        return loop_x.squeeze(0), loop_y.squeeze(0)
    return loop_x, loop_y


# --------------------------------------------------------------------------
# invariants
# --------------------------------------------------------------------------

def half_retr(loop: torch.Tensor) -> torch.Tensor:
    """(1/2) Re Tr C = q0 cos(phi). The normalized-trace invariant of a closed loop."""
    return loop[..., 1] * torch.cos(loop[..., 0])


def half_imtr(loop: torch.Tensor) -> torch.Tensor:
    """(1/2) Im Tr C = q0 sin(phi)."""
    return loop[..., 1] * torch.sin(loop[..., 0])


def det_phase(loop: torch.Tensor) -> torch.Tensor:
    """arg det C = wrap(2 phi). Gauge invariant for a closed loop, and additive
    over products because det is a homomorphism."""
    return wrap(2.0 * loop[..., 0])


def mean_plaquette(links: torch.Tensor) -> torch.Tensor:
    return half_retr(plaquette(links)).mean()


def det_links(links: torch.Tensor) -> torch.Tensor:
    """U(2) links -> the determinant U(1) gauge field psi = wrap(2 phi).

    Returns [2, L, L] or [B, 2, L, L] -- exactly the layout consumed by every
    `u1_2d.lgt` routine, which is the bridge the whole project is built on."""
    return wrap(2.0 * links[..., 0])


def set_det_links(links: torch.Tensor, psi: torch.Tensor) -> torch.Tensor:
    """Replace the determinant sector by `psi`, leaving the SU(2) sector untouched.

    Implemented as the left multiplication U -> e^{i d/2} U with d = wrap(psi -
    psi_old), which is the minimal central rotation realizing the requested
    determinant. (Adding 2 pi to d would flip the sign of the resulting matrix --
    the same determinant but a different group element -- so the wrapped branch is
    the canonical choice.)"""
    delta = wrap(psi - det_links(links))
    out = links.clone()
    out[..., 0] = wrap(links[..., 0] + 0.5 * delta)
    return out


def topological_charge_float(links: torch.Tensor) -> torch.Tensor:
    """Determinant winding number, sum of wrapped plaquette determinant phases / 2 pi."""
    return det_phase(plaquette(links)).sum(dim=(-2, -1)) / TWO_PI


def topological_charge(links: torch.Tensor) -> torch.Tensor:
    return torch.round(topological_charge_float(links))


# --------------------------------------------------------------------------
# gauge transformations
# --------------------------------------------------------------------------

def gauge_transform(links: torch.Tensor, gauge: torch.Tensor) -> torch.Tensor:
    """U_{x,mu} -> G_x U_{x,mu} G_{x+mu}^dag. `gauge` is a site field [..., L, L, 5]."""
    links, squeezed = _as_batched(links)
    if gauge.dim() == 3:
        gauge = gauge.unsqueeze(0)
    out = torch.stack(
        [
            u2_mul(u2_mul(gauge, links[:, 0]), u2_conj(shift(gauge, dx=1))),
            u2_mul(u2_mul(gauge, links[:, 1]), u2_conj(shift(gauge, dy=1))),
        ],
        dim=1,
    )
    return out.squeeze(0) if squeezed else out


def random_gauge_transform(links: torch.Tensor,
                           generator: torch.Generator | None = None) -> torch.Tensor:
    links_b, squeezed = _as_batched(links)
    batch, _, size, _, _ = links_b.shape
    phase = torch.rand((batch, size, size, 1), device=links.device, dtype=links.dtype,
                       generator=generator) * TWO_PI - math.pi
    quat = quat_normalize(torch.randn((batch, size, size, 4), device=links.device,
                                      dtype=links.dtype, generator=generator))
    out = gauge_transform(links_b, torch.cat([phase, quat], dim=-1))
    return out.squeeze(0) if squeezed else out


def plaquette_correlator(links: torch.Tensor, max_distance: int) -> torch.Tensor:
    """Connected two-point correlator of (1/2)ReTr P along x, averaged over sites."""
    plaq = half_retr(plaquette(links))
    if plaq.dim() == 2:
        plaq = plaq.unsqueeze(0)
    centered = plaq - plaq.mean()
    return torch.stack(
        [(centered * torch.roll(centered, -d, dims=-2)).mean()
         for d in range(1, max_distance + 1)]
    )


# --------------------------------------------------------------------------
# staples (the local environment of one link)
# --------------------------------------------------------------------------

def to_complex_quaternion(links: torch.Tensor) -> torch.Tensor:
    """Split U(2) -> complex 4-vector m with U = m0 I + i m_a sigma_a, m = e^{i phi} q.

    Every 2x2 complex matrix has such an expansion, and `quat_mul` is exactly
    matrix multiplication in these coordinates, so sums of group elements (which
    leave the group) stay in the same arithmetic. Handy invariants:
        Tr M = 2 m0,   Tr(sigma_j M) = 2 i m_j.
    """
    phase = torch.complex(torch.cos(links[..., 0]), torch.sin(links[..., 0]))
    quat = links[..., 1:].to(phase.dtype)
    return phase.unsqueeze(-1) * quat


def cquat_adjoint(m: torch.Tensor) -> torch.Tensor:
    """M -> M^dag in complex-quaternion coordinates."""
    return torch.cat([m[..., :1].conj(), -m[..., 1:].conj()], dim=-1)


def staples(links: torch.Tensor, mu: int | None = None) -> torch.Tensor:
    """Sum of the two staples attached to each link, as complex quaternions.

    Returns [B, 2, L, L, 4] complex `Sigma` such that

        sum over plaquettes containing link (x, mu) of ReTr P = ReTr(U_{x,mu} Sigma_{x,mu}),

    which is the whole local environment: force, heatbath, overrelaxation and
    Metropolis all read it and nothing else. The second staple of each link comes
    from the plaquette in which the link appears daggered; ReTr P = ReTr P^dag is
    used to bring it back to the form ReTr(U A).

    `mu` restricts the computation to one link direction and returns
    [B, L, L, 4]. The checkerboard sweeps update one direction at a time, so
    computing both and indexing one is exactly half of the work wasted -- and
    those sweeps are the inner loop of rethermalization and of the conditional
    SU(2) sampler.
    """
    links, squeezed = _as_batched(links)
    m = to_complex_quaternion(links)
    m0, m1 = m[:, 0], m[:, 1]
    d0, d1 = cquat_adjoint(m0), cquat_adjoint(m1)

    if mu is None or mu == 0:
        up_x = quat_mul(quat_mul(shift(m1, dx=1), shift(d0, dy=1)), d1)
        down_x = quat_mul(quat_mul(shift(d1, dx=1, dy=-1), shift(d0, dy=-1)),
                          shift(m1, dy=-1))
        sigma_x = up_x + down_x
        if mu == 0:
            return sigma_x.squeeze(0) if squeezed else sigma_x
    if mu is None or mu == 1:
        up_y = quat_mul(quat_mul(shift(m0, dy=1), shift(d1, dx=1)), d0)
        down_y = quat_mul(quat_mul(shift(d0, dx=-1, dy=1), shift(d1, dx=-1)),
                          shift(m0, dx=-1))
        sigma_y = up_y + down_y
        if mu == 1:
            return sigma_y.squeeze(0) if squeezed else sigma_y

    out = torch.stack([sigma_x, sigma_y], dim=1)
    return out.squeeze(0) if squeezed else out


def link_environment(links: torch.Tensor) -> torch.Tensor:
    """M = U Sigma per link, in complex-quaternion coordinates [B, 2, L, L, 4].

    (1/2)ReTr(U Sigma) = Re M0 is the local action density; the u(2) force and both
    local-update conditionals are read off M directly.
    """
    return quat_mul(to_complex_quaternion(links), staples(links))
