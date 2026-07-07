"""Exact analytic results for 2D compact U(1) on a periodic L x L lattice.

Everything follows from the character expansion: the partition function factorizes
over plaquettes, Z = sum_q c_q(beta)^V with V = L^2, where c_q is the q-th Fourier
coefficient of the single-plaquette Boltzmann weight f(theta):

    Wilson  f(theta) = exp(beta cos theta)            -> c_q  proportional to I_q(beta)
    Villain f(theta) = sum_n exp(-beta/2 (theta+2 pi n)^2) -> c_q proportional to exp(-q^2 / (2 beta))

Only ratios r_q = c_q / c_0 ever enter observables.

Key formulas (A = loop area in plaquettes, V = L^2):
    <W(A)>   = sum_q r_q^(V-A) r_(q+1)^A / sum_q r_q^V     (finite volume)
             -> r_1^A                                        (infinite volume)
    <cos p>  = <W(1)>;  infinite volume Wilson: I_1(beta)/I_0(beta)
    sigma    = -log r_1  (exact string tension; all Creutz ratios equal sigma)
    P(Q)     from the constrained-sum representation: plaquette angles are i.i.d.
              with density f, constrained so that sum_p theta_p = 2 pi Q. Hence
              P(Q) proportional to  integral dk  exp(-2 pi i k Q) psi(k)^V,
              psi(k) = int f(theta) cos(k theta) dtheta / int f  (real k).
"""

import math

import numpy as np
from scipy.special import ive

TWO_PI = 2.0 * math.pi


def _log_r_q(beta: float, q_values: np.ndarray, action_type: str) -> np.ndarray:
    """log(c_q / c_0) for integer orders q."""
    if action_type == "wilson":
        vals = ive(np.abs(q_values), beta)
        ref = ive(0, beta)
        return np.log(vals / ref)
    if action_type == "villain":
        return -q_values.astype(float) ** 2 / (2.0 * beta)
    raise ValueError(f"Unknown action type: {action_type}")


def _q_cutoff(beta: float, volume: int) -> int:
    return int(20 + 4 * math.sqrt(max(beta, 1.0)))


def wilson_loop_exact(beta: float, area: int, action_type: str = "wilson", lattice_size: int | None = None) -> float:
    """<W(A)> for a Wilson loop enclosing `area` plaquettes."""
    if lattice_size is None:
        r1 = math.exp(float(_log_r_q(beta, np.array([1]), action_type)[0]))
        return r1 ** area
    volume = lattice_size * lattice_size
    if area >= volume:
        raise ValueError("Loop area must be smaller than the lattice volume")
    q_max = _q_cutoff(beta, volume)
    qs = np.arange(-q_max, q_max + 1)
    log_r = _log_r_q(beta, qs, action_type)
    log_r_plus = _log_r_q(beta, qs + 1, action_type)
    log_num = (volume - area) * log_r + area * log_r_plus
    log_den = volume * log_r
    num_max, den_max = log_num.max(), log_den.max()
    numerator = np.exp(log_num - num_max).sum()
    denominator = np.exp(log_den - den_max).sum()
    return float(np.exp(num_max - den_max) * numerator / denominator)


def plaquette_exact(beta: float, action_type: str = "wilson", lattice_size: int | None = None) -> float:
    """<cos theta_p>. Infinite-volume Wilson: I_1(beta)/I_0(beta); Villain: exp(-1/(2 beta))."""
    return wilson_loop_exact(beta, 1, action_type, lattice_size)


def string_tension_exact(beta: float, action_type: str = "wilson") -> float:
    return -float(_log_r_q(beta, np.array([1]), action_type)[0])


def creutz_ratio_exact(beta: float, action_type: str = "wilson") -> float:
    """In infinite volume the area law is exact, so every Creutz ratio equals sigma."""
    return string_tension_exact(beta, action_type)


def plaquette_weight(theta: np.ndarray, beta: float, action_type: str) -> np.ndarray:
    """Unnormalized single-plaquette Boltzmann weight f(theta), stable for large beta."""
    theta = np.asarray(theta, dtype=float)
    if action_type == "wilson":
        return np.exp(beta * (np.cos(theta) - 1.0))
    if action_type == "villain":
        n_max = max(2, int(math.ceil(4.0 / math.sqrt(beta) / TWO_PI)) + 2)
        ns = np.arange(-n_max, n_max + 1)
        shifted = theta[..., None] + TWO_PI * ns
        return np.exp(-0.5 * beta * shifted**2).sum(axis=-1)
    raise ValueError(f"Unknown action type: {action_type}")


def plaquette_angle_density(theta: np.ndarray, beta: float, action_type: str = "wilson") -> np.ndarray:
    """Normalized infinite-volume marginal density of a single plaquette angle."""
    grid = np.linspace(-math.pi, math.pi, 4001)
    norm = np.trapezoid(plaquette_weight(grid, beta, action_type), grid)
    return plaquette_weight(theta, beta, action_type) / norm


def _psi(k_values: np.ndarray, beta: float, action_type: str) -> np.ndarray:
    """Normalized characteristic function psi(k) = <cos(k theta)>_f for real k."""
    grid = np.linspace(-math.pi, math.pi, 4001)
    f = plaquette_weight(grid, beta, action_type)
    norm = np.trapezoid(f, grid)
    out = np.empty(len(k_values))
    for i, k in enumerate(k_values):
        out[i] = np.trapezoid(f * np.cos(k * grid), grid) / norm
    return out


def topological_charge_distribution(
    beta: float, lattice_size: int, action_type: str = "wilson", q_max: int | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """Exact finite-volume distribution P(Q). Returns (q_values, probabilities)."""
    volume = lattice_size * lattice_size
    chi_inf = topological_susceptibility_exact(beta, action_type)
    width = math.sqrt(max(volume * chi_inf, 1e-12))
    if q_max is None:
        q_max = max(3, int(math.ceil(6.0 * width)))
    k_star = math.sqrt(2.0 * 400.0 / (volume * TWO_PI**2 * max(chi_inf, 1e-300)))
    k_cut = min(k_star, 0.5 * math.sqrt(beta) if action_type == "villain" else 10.0)
    dk = min(k_cut / 400.0, 0.05 / max(1, q_max))
    ks = np.arange(0.0, k_cut + dk, dk)
    psi = _psi(ks, beta, action_type)
    log_abs = np.log(np.clip(np.abs(psi), 1e-300, None))
    weights = np.sign(psi) ** volume * np.exp(volume * log_abs)
    q_values = np.arange(-q_max, q_max + 1)
    probs = np.array([np.trapezoid(weights * np.cos(TWO_PI * ks * q), ks) for q in q_values])
    probs = np.clip(probs, 0.0, None)
    probs /= probs.sum()
    return q_values, probs


def topological_susceptibility_exact(
    beta: float, action_type: str = "wilson", lattice_size: int | None = None
) -> float:
    """chi_t = <Q^2> / V.

    Infinite volume: plaquettes are i.i.d., so chi_t = <(theta_p / 2 pi)^2>_f.
    Finite volume: computed from the exact P(Q).
    """
    if lattice_size is None:
        grid = np.linspace(-math.pi, math.pi, 4001)
        f = plaquette_weight(grid, beta, action_type)
        return float(np.trapezoid((grid / TWO_PI) ** 2 * f, grid) / np.trapezoid(f, grid))
    q_values, probs = topological_charge_distribution(beta, lattice_size, action_type)
    return float((q_values.astype(float) ** 2 * probs).sum() / (lattice_size * lattice_size))
