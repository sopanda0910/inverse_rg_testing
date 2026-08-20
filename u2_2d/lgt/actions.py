"""Plaquette actions for 2D U(2), and the exact determinant-sector effective action.

Two actions live here and they are NOT the same theory:

`WilsonU2Action` is the real target,

    S(U) = -beta sum_p (1/2) ReTr P_p = -beta sum_p q0_p cos(phi_p),

written without the additive constant beta V that the sibling NTHMC code carries,
so it matches the `u1_2d.lgt.actions` sign convention (`per_config` = -sum of
`plaquette_log_weight`). Note what this expression is NOT: a sum of a U(1) piece
and an SU(2) piece. It is a PRODUCT of the determinant-sector cosine and the
SU(2) trace -- (1/2)ReTr P = cos(omega_p) cos(phi_p), which near the identity is
1 - phi_p^2/2 - omega_p^2/2 + phi_p^2 omega_p^2/4. The two sectors decouple at
Gaussian order and couple at quartic order; nothing about the split
representation makes them independent.

`DetSectorAction` is the exact consequence of that fact. Integrating the SU(2)
part out of one plaquette with normalized Haar measure,

    int dq exp(beta q0 cos phi_p) = 2 I_1(beta cos phi_p) / (beta cos phi_p),

and since 2D plaquettes are independent up to the single global constraint, the
MARGINAL distribution of the determinant field psi = wrap(2 phi) is a compact
U(1) lattice gauge theory with the single-plaquette weight

    w_det(alpha) = 2 I_1(z) / z,   z = beta cos(alpha/2),   alpha in (-pi, pi]

(so z >= 0 throughout). This is the theory a determinant-sector diffusion model
must reproduce -- not U(1) Wilson at beta/4. Expanding at large beta,
-log w_det = const + (beta/8) alpha^2 + (3/2) log cos(alpha/2) + ..., whose
leading term is Wilson U(1) at beta_1 = beta/4, recovering the tree-level
normalization guide of `docs/Field_transform.html`; the log cos piece is the
measure factor from the three integrated-out SU(2) directions and is what keeps
the determinant sector from being Wilson at any coupling.
"""

import math

import torch

from ..lgt.lattice import det_phase, half_retr, plaquette

TWO_PI = 2.0 * math.pi

# Below this argument the ratio 2 I_1(z) / z is taken from its Taylor series;
# i1e(z)/z is 0/0 at the origin in floating point.
_SMALL_Z = 1e-4


class _LogG0(torch.autograd.Function):
    """log(2 I_1(z) / z) for z >= 0, with the analytic derivative I_2(z) / I_1(z).

    torch.special.i1e is not differentiable, and this factor sits inside the
    determinant-sector force, so the derivative is supplied by hand. It comes
    from d/dz [z^-nu I_nu(z)] = z^-nu I_{nu+1}(z) with nu = 1, which gives
    d/dz log(2 I_1/z) = I_2(z) / I_1(z) exactly.
    """

    @staticmethod
    def forward(ctx, z: torch.Tensor) -> torch.Tensor:
        ctx.save_for_backward(z)
        small = z < _SMALL_Z
        safe = z.clamp_min(_SMALL_Z)
        value = torch.log(2.0 * torch.special.i1e(safe) / safe) + safe
        series = z.square() / 8.0 - z.square().square() / 384.0
        return torch.where(small, series, value)

    @staticmethod
    def backward(ctx, grad_out: torch.Tensor) -> torch.Tensor:
        (z,) = ctx.saved_tensors
        small = z < _SMALL_Z
        safe = z.clamp_min(_SMALL_Z)
        # i1e / i0e-style scaling cancels in the ratio, so use the scaled forms.
        i1 = torch.special.i1e(safe)
        i2 = torch.special.i0e(safe) - 2.0 * i1 / safe  # I_2 = I_0 - 2 I_1 / z
        ratio = torch.where(small, z / 4.0, i2 / i1)
        return grad_out * ratio


def log_g0(z: torch.Tensor) -> torch.Tensor:
    """log of the SU(2) one-link integral int dq exp(z q0) = 2 I_1(z) / z, z >= 0."""
    return _LogG0.apply(z)


class WilsonU2Action:
    """S = -beta sum_p (1/2) ReTr P_p."""

    name = "wilson_u2"

    def __init__(self, beta: float) -> None:
        self.beta = float(beta)

    def plaquette_log_weight(self, plaq: torch.Tensor) -> torch.Tensor:
        """`plaq` is a loop in split representation [..., L, L, 5]."""
        return self.beta * half_retr(plaq)

    def per_config(self, links: torch.Tensor) -> torch.Tensor:
        return -self.plaquette_log_weight(plaquette(links)).sum(dim=(-2, -1))

    def __call__(self, links: torch.Tensor) -> torch.Tensor:
        return self.per_config(links).sum()


class DetSectorAction:
    """Exact SU(2)-integrated effective action for the determinant field psi.

    Acts on a [B, 2, L, L] U(1) field in the `u1_2d` layout, so it plugs straight
    into `u1_2d.lgt.local_updates.metropolis_sweep` and friends. `beta` is the
    U(2) coupling, not a U(1) one.
    """

    name = "det_sector"

    def __init__(self, beta: float) -> None:
        self.beta = float(beta)

    def plaquette_log_weight(self, alpha: torch.Tensor) -> torch.Tensor:
        return log_g0(self.beta * torch.cos(0.5 * alpha).clamp_min(0.0))

    def per_config(self, psi: torch.Tensor) -> torch.Tensor:
        from u1_2d.lgt.lattice import plaquette_angles

        return -self.plaquette_log_weight(plaquette_angles(psi)).sum(dim=(-2, -1))

    def __call__(self, psi: torch.Tensor) -> torch.Tensor:
        return self.per_config(psi).sum()


def det_sector_plaquette_score(alpha: torch.Tensor, beta: float) -> torch.Tensor:
    """d/d(alpha) log w_det(alpha) = -(beta/2) sin(alpha/2) I_2(z) / I_1(z).

    The determinant-sector analogue of the Wilson `-beta sin(theta_p)` that
    `u1_2d`'s score head and physics blend use. At large beta the Bessel ratio
    tends to 1 and this becomes -(beta/2) sin(alpha/2), the derivative of
    beta cos(alpha/2).
    """
    z = (beta * torch.cos(0.5 * alpha)).clamp_min(0.0)
    small = z < _SMALL_Z
    safe = z.clamp_min(_SMALL_Z)
    i1 = torch.special.i1e(safe)
    i2 = torch.special.i0e(safe) - 2.0 * i1 / safe
    ratio = torch.where(small, z / 4.0, i2 / i1)
    return -0.5 * beta * torch.sin(0.5 * alpha) * ratio


def make_action(action_type: str, beta: float):
    if action_type in ("wilson_u2", "wilson"):
        return WilsonU2Action(beta)
    if action_type == "det_sector":
        return DetSectorAction(beta)
    raise ValueError(f"Unknown action type: {action_type}")
