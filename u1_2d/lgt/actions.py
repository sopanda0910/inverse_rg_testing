"""Plaquette actions for 2D compact U(1).

Both actions expose:
    per_config(theta)      -> [B] (or scalar for unbatched input)
    __call__(theta)        -> scalar total (sum over batch), usable as HMC action
    plaquette_log_weight(p) -> elementwise log of the single-plaquette Boltzmann factor
                               (used by local Metropolis updates and exact formulas)
"""

import math

import torch

from .lattice import plaquette_angles

TWO_PI = 2.0 * math.pi


class WilsonAction:
    """S = -beta * sum_p cos(theta_p)."""

    name = "wilson"

    def __init__(self, beta: float) -> None:
        self.beta = float(beta)

    def plaquette_log_weight(self, plaq: torch.Tensor) -> torch.Tensor:
        return self.beta * torch.cos(plaq)

    def per_config(self, theta: torch.Tensor) -> torch.Tensor:
        plaq = plaquette_angles(theta)
        return -self.plaquette_log_weight(plaq).sum(dim=(-2, -1))

    def __call__(self, theta: torch.Tensor) -> torch.Tensor:
        return self.per_config(theta).sum()


# The villain action is used as a verification of the model and machinery/pipeline.
# The Wilson Action's coarse/fine beta values are numerically determined, and therefore
# there isn't a precise target that the machinery/model can be tested on, while the villain action
# has a simple scaling (beta --> beta/4 under blocking).
class VillainAction:
    """S = -sum_p log sum_n exp(-beta/2 (theta_p + 2 pi n)^2).

    The heat-kernel / Villain action; renormalizes exactly within its family
    under 2x2 blocking (beta -> beta/4).
    """

    name = "villain"

    def __init__(self, beta: float, n_windings: int | None = None) -> None:
        self.beta = float(beta)
        if n_windings is None:
            sigma = 1.0 / math.sqrt(self.beta)
            n_windings = max(2, int(math.ceil(4.0 * sigma / TWO_PI)) + 2)
        self.n_windings = n_windings

    def plaquette_log_weight(self, plaq: torch.Tensor) -> torch.Tensor:
        ns = torch.arange(
            -self.n_windings, self.n_windings + 1, device=plaq.device, dtype=plaq.dtype
        )
        shifted = plaq.unsqueeze(-1) + TWO_PI * ns
        return torch.logsumexp(-0.5 * self.beta * shifted.square(), dim=-1)

    def per_config(self, theta: torch.Tensor) -> torch.Tensor:
        plaq = plaquette_angles(theta)
        return -self.plaquette_log_weight(plaq).sum(dim=(-2, -1))

    def __call__(self, theta: torch.Tensor) -> torch.Tensor:
        return self.per_config(theta).sum()


def make_action(action_type: str, beta: float):
    if action_type == "wilson":
        return WilsonAction(beta)
    if action_type == "villain":
        return VillainAction(beta)
    raise ValueError(f"Unknown action type: {action_type}")
