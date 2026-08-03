"""Exact references for 2D SU(2) via plaquette decoupling.

In 2D on a torus (with free boundary counting; finite-volume corrections are
exponentially small at the couplings used) plaquettes decouple exactly as in
U(1). With half-angle theta in [0, pi], tr U = 2 cos(theta), Haar class
measure (2/pi) sin^2(theta) dtheta, the single-plaquette weight is
exp(beta cos theta), giving

    <(1/2) tr P> = I_2(beta) / I_1(beta),

and the R x T Wilson loop obeys the exact area law W = (I_2/I_1)^(R T).
Everything here is computed by dense quadrature so the Bessel identities can
be used as *tests* rather than assumptions.
"""

import math

import numpy as np
from scipy.special import ive

_N_GRID = 4096


def _grid():
    theta = np.linspace(0.0, math.pi, _N_GRID)
    weight = np.sin(theta) ** 2
    return theta, weight


def plaquette_exact(beta: float) -> float:
    theta, w = _grid()
    boltz = np.exp(beta * (np.cos(theta) - 1.0))
    return float((w * boltz * np.cos(theta)).sum() / (w * boltz).sum())


def plaquette_exact_bessel(beta: float) -> float:
    return float(ive(2, beta) / ive(1, beta))


def wilson_loop_exact(beta: float, area: int) -> float:
    return plaquette_exact(beta) ** area


def char_moment(beta: float, j2: int) -> float:
    """< chi_j(P) > with j2 = 2j: character expectation under the plaquette
    weight, by quadrature. chi_j(theta) = sin((2j+1) theta) / sin(theta)."""
    theta, w = _grid()
    boltz = np.exp(beta * (np.cos(theta) - 1.0))
    with np.errstate(invalid="ignore", divide="ignore"):
        chi = np.sin((j2 + 1) * theta) / np.sin(theta)
    chi[0], chi[-1] = j2 + 1.0, (j2 + 1.0) * (-1.0) ** j2
    return float((w * boltz * chi).sum() / (w * boltz).sum())
