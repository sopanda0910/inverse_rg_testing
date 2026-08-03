"""SU(2) group elements as unit quaternions [..., 4] = (w, v1, v2, v3).

Convention: U = w + i (v . sigma), i.e. the 2x2 matrix
    [[w + i v3,  v2 + i v1],
     [-v2 + i v1, w - i v3]].
In this parameterization the group product carries a MINUS cross term,
    (w1, v1)(w2, v2) = (w1 w2 - v1.v2,  w1 v2 + w2 v1 - v1 x v2),
opposite to the standard Hamilton quaternion orientation (the i*sigma
representation reverses it). tr U = 2 w.

Algebra coordinates: omega in R^3 with U = exp(i (omega . sigma) / 2), so the
half-angle is theta = |omega| / 2, w = cos(theta), v = sin(theta) omega_hat.
"""

import torch


def mul(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    wa, va = a[..., :1], a[..., 1:]
    wb, vb = b[..., :1], b[..., 1:]
    w = wa * wb - (va * vb).sum(dim=-1, keepdim=True)
    v = wa * vb + wb * va - torch.cross(va, vb, dim=-1)
    return torch.cat([w, v], dim=-1)


def inverse(a: torch.Tensor) -> torch.Tensor:
    return torch.cat([a[..., :1], -a[..., 1:]], dim=-1)


def normalize(a: torch.Tensor) -> torch.Tensor:
    return a / a.norm(dim=-1, keepdim=True).clamp_min(1e-12)


def trace_half(a: torch.Tensor) -> torch.Tensor:
    """(1/2) tr U = w."""
    return a[..., 0]


def to_matrix(a: torch.Tensor) -> torch.Tensor:
    """[..., 4] -> [..., 2, 2] complex, for cross-checks against matrix algebra."""
    w, v1, v2, v3 = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    m = torch.zeros(*a.shape[:-1], 2, 2, dtype=torch.complex128)
    m[..., 0, 0] = w + 1j * v3
    m[..., 0, 1] = v2 + 1j * v1
    m[..., 1, 0] = -v2 + 1j * v1
    m[..., 1, 1] = w - 1j * v3
    return m


def rotate_vector(g: torch.Tensor, s: torch.Tensor) -> torch.Tensor:
    """Adjoint action: g (i s.sigma) g^-1 = i s'.sigma.

    Closed form in this parameterization (note -2w(v x s), NOT +):
        s' = (w^2 - |v|^2) s + 2 (v.s) v - 2 w (v x s).
    """
    w, v = g[..., :1], g[..., 1:]
    return ((w**2 - (v**2).sum(dim=-1, keepdim=True)) * s
            + 2.0 * (v * s).sum(dim=-1, keepdim=True) * v
            - 2.0 * w * torch.cross(v, s, dim=-1))


def expmap(omega: torch.Tensor) -> torch.Tensor:
    """Algebra vector omega [..., 3] -> exp(i (omega.sigma)/2) as quaternion."""
    theta = omega.norm(dim=-1, keepdim=True) / 2.0
    w = torch.cos(theta)
    small = theta < 1e-8
    coef = torch.where(small, 0.5 - theta**2 / 12.0, torch.sin(theta) / (2.0 * theta.clamp_min(1e-30)))
    return torch.cat([w, coef * omega], dim=-1)


def logmap(a: torch.Tensor) -> torch.Tensor:
    """Quaternion -> algebra vector omega with |omega|/2 = half-angle in [0, pi]."""
    w = a[..., :1].clamp(-1.0, 1.0)
    v = a[..., 1:]
    vn = v.norm(dim=-1, keepdim=True)
    theta = torch.atan2(vn, w)
    small = vn < 1e-12
    coef = torch.where(small, 2.0, 2.0 * theta / vn.clamp_min(1e-30))
    return coef * v


def random_haar(shape, generator: torch.Generator | None = None) -> torch.Tensor:
    """Haar-uniform SU(2): normalized 4D Gaussian."""
    q = torch.randn(*shape, 4, generator=generator)
    return normalize(q)


def identity(shape) -> torch.Tensor:
    q = torch.zeros(*shape, 4)
    q[..., 0] = 1.0
    return q
