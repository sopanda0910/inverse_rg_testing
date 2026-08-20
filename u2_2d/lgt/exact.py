"""Exact analytic results for 2D U(2) on a periodic L x L lattice.

2D lattice gauge theory is exactly solvable for any compact group: in axial
gauge the plaquettes are independent up to one global constraint, and the torus
partition function is the character sum

    Z = sum_r (c_r / d_r)^V ,   V = L^2,
    c_r = int dU chi_r(U)^* exp(beta (1/2) ReTr U),   d_r = dim r.

(The general genus-g formula carries d_r^{2-2g}; the torus has g = 1, so that
factor is 1 -- which is why this reduces to `u1_2d.lgt.exact`'s sum_q c_q^V when
every d_r = 1.)

IRREPS OF U(2) IN THE SPLIT COORDINATES. Because U(2) = (U(1) x SU(2)) / Z_2, an
irrep is a pair (j, k): SU(2) spin j and central U(1) charge k, subject to
k = 2j (mod 2). Its character on U = e^{i phi} q is

    chi_{(j,k)}(U) = e^{i k phi} chi_j(q),   d_{(j,k)} = 2j + 1.

With the SU(2) one-link integral (from sin w sin(n w) = [cos((n-1)w) -
cos((n+1)w)]/2 and I_{n-1} - I_{n+1} = (2n/a) I_n)

    int dq chi_j(q) e^{a q0} = (2j + 1) * 2 I_{2j+1}(a) / a = d_j g_j(a),

the character coefficient collapses to a single one-dimensional quadrature,

    c_{j,k}(beta) = d_j int_0^{2pi} (d phi / 2 pi) e^{-i k phi} g_j(beta cos phi),
    g_j(a) = 2 I_{2j+1}(a) / a.

Note d_j appears in c_r and cancels from c_r / d_r, so the torus partition sum is
built from the bare quadrature while Wilson loops need the factor restored.

Since g_j(-a) = (-1)^{2j} g_j(a), the integral vanishes unless k = 2j (mod 2) --
the Z_2 constraint drops out of the arithmetic rather than being imposed by hand.

DETERMINANT SECTOR. det: U(2) -> U(1) is a homomorphism, so the field
psi = wrap(2 phi) is a compact U(1) gauge field carrying all the topology, and
its exact single-plaquette marginal weight is

    w_det(alpha) = 2 I_1(beta cos(alpha/2)) / (beta cos(alpha/2)),  alpha in (-pi, pi].

Every U(1) formula of `u1_2d.lgt.exact` -- P(Q), chi_t, character ratios,
blocked densities -- then applies verbatim with `plaquette_weight` replaced by
w_det. The functions named `det_*` below do exactly that.
"""

import math

import numpy as np
from scipy.optimize import brentq
from scipy.special import ive

TWO_PI = 2.0 * math.pi


# --------------------------------------------------------------------------
# full U(2): character expansion
# --------------------------------------------------------------------------

def _g_scaled(order: int, z: np.ndarray, beta: float) -> np.ndarray:
    """g_nu(z) e^{-beta} with g_nu(z) = 2 I_nu(z) / z, evaluated for |z| <= beta.

    Peeling e^{beta} keeps the quadrature finite at any coupling: the integrand
    peaks at z = beta, so every value returned is bounded by g_nu(beta) e^{-beta}.
    """
    z = np.asarray(z, dtype=float)
    az = np.abs(z)
    small = az < 1e-10
    safe = np.where(small, 1.0, az)
    # ive(nu, x) = e^{-x} I_nu(x). Continuing to z < 0 picks up TWO signs:
    # I_nu(-x) = (-1)^nu I_nu(x) and the explicit 1/z, giving (-1)^(nu+1) overall.
    # That combination is what makes g_j even for integer j and odd for half-integer
    # j, hence what enforces the U(2) parity constraint k = 2j (mod 2).
    value = 2.0 * ive(order, safe) * np.exp(safe - beta) / safe
    value = np.where(z < 0, (-1) ** (order + 1) * value, value)
    limit = math.exp(-beta) if order == 1 else 0.0
    return np.where(small, limit, value)


def character_coefficients(
    beta: float, two_j_max: int = 12, k_max: int | None = None, n_quad: int = 4096
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Scaled coefficients c_{j,k}(beta) e^{-beta} on the (j, k) grid.

    Returns (two_j, k, c_scaled) as flat arrays over the irreps satisfying the
    parity constraint k = 2j (mod 2). Multiply by e^{beta} for the true c_{j,k};
    every downstream formula uses ratios or logs, so the scaling never needs undoing.
    The dimension factor d_j from the SU(2) one-link integral IS included here.
    """
    if k_max is None:
        k_max = two_j_max + 12
    phi = np.arange(n_quad) * TWO_PI / n_quad
    cos_phi = np.cos(phi)
    two_js, ks, coeffs = [], [], []
    for two_j in range(two_j_max + 1):
        g = _g_scaled(two_j + 1, beta * cos_phi, beta)
        for k in range(-k_max, k_max + 1):
            if (k - two_j) % 2:
                continue
            two_js.append(two_j)
            ks.append(k)
            coeffs.append((two_j + 1.0) * float(np.mean(g * np.cos(k * phi))))
    return np.array(two_js), np.array(ks), np.array(coeffs)


def log_partition(beta: float, lattice_size: int, two_j_max: int = 12) -> float:
    """Exact log Z on the periodic L x L lattice with normalized Haar measure."""
    volume = lattice_size * lattice_size
    two_j, _, coeffs = character_coefficients(beta, two_j_max)
    ratio = coeffs / (two_j + 1.0)
    keep = np.abs(ratio) > 0.0
    signs = np.sign(ratio[keep]) ** volume
    terms = volume * (np.log(np.abs(ratio[keep])) + beta)
    peak = terms.max()
    total = float((signs * np.exp(terms - peak)).sum())
    return float(peak + math.log(total))


def plaquette_exact(beta: float, lattice_size: int | None = None) -> float:
    """<(1/2) ReTr P>.

    Infinite volume (single plaquette, Weyl integration over U(2)):
        Z_1 = I_0(x)^2 - I_1(x)^2,  <(1/2)ReTr> = I_1(x)(I_0(x) - I_2(x)) / (2 Z_1)
    with x = beta / 2. Finite volume: (1/V) d log Z / d beta by central difference.
    """
    if lattice_size is None:
        x = 0.5 * beta
        i0, i1, i2 = ive(0, x), ive(1, x), ive(2, x)
        return float(0.5 * i1 * (i0 - i2) / (i0 * i0 - i1 * i1))
    volume = lattice_size * lattice_size
    step = 1e-4 * max(beta, 1.0)
    hi = log_partition(beta + step, lattice_size)
    lo = log_partition(beta - step, lattice_size)
    return float((hi - lo) / (2.0 * step * volume))


def wilson_loop_exact(beta: float, area: int, two_j: int = 1, charge: int = 1,
                      two_j_max: int = 12) -> float:
    """Infinite-volume <chi_r(W(A))> / d_r for the irrep r = (j, k = charge).

    In 2D the plaquettes inside the loop are independent, so each contributes one
    factor of the normalized character ratio r_r = c_r / (d_r c_0). Defaults give
    the fundamental (j = 1/2, k = 1), for which this is <(1/2) ReTr W(A)>; at
    A = 1 it reproduces `plaquette_exact`.
    """
    js, ks, coeffs = character_coefficients(beta, two_j_max)
    ref = float(coeffs[(js == 0) & (ks == 0)][0])
    sel = (js == two_j) & (ks == charge)
    if not sel.any():
        raise ValueError(f"irrep (2j={two_j}, k={charge}) violates the U(2) parity constraint")
    return float((coeffs[sel][0] / ((two_j + 1.0) * ref)) ** area)


def string_tension_exact(beta: float) -> float:
    """sigma = -log r_fund; the 2D area law <W(A)> = e^{-sigma A} is exact."""
    return -math.log(wilson_loop_exact(beta, 1))


# --------------------------------------------------------------------------
# determinant sector: an exactly known compact U(1) theory
# --------------------------------------------------------------------------

def det_plaquette_weight(alpha: np.ndarray, beta: float) -> np.ndarray:
    """w_det(alpha) = 2 I_1(z) / z with z = beta cos(alpha/2), scaled by e^{-beta}.

    The scaling is a constant per beta, so it cancels from every normalized
    quantity below; it exists only so the weight stays finite at large coupling.
    """
    z = beta * np.cos(0.5 * np.asarray(alpha, dtype=float))
    return _g_scaled(1, np.clip(z, 0.0, None), beta)


def det_plaquette_angle_density(alpha: np.ndarray, beta: float) -> np.ndarray:
    """Normalized infinite-volume marginal density of the plaquette determinant phase."""
    grid = np.linspace(-math.pi, math.pi, 4001)
    norm = np.trapezoid(det_plaquette_weight(grid, beta), grid)
    return det_plaquette_weight(alpha, beta) / norm


def det_character_exact(beta: float, q: int = 1) -> float:
    """r_q = <cos(q alpha)> under the determinant-sector single-plaquette weight.

    r_1 is the determinant-sector analogue of the U(1) mean plaquette, and
    <exp(i q * winding)> for a charge-q determinant Wilson loop of area A is r_q^A.
    """
    if q == 0:
        return 1.0
    grid = np.linspace(-math.pi, math.pi, 8001)
    w = det_plaquette_weight(grid, beta)
    return float(np.trapezoid(w * np.cos(q * grid), grid) / np.trapezoid(w, grid))


def _det_psi(k_values: np.ndarray, beta: float) -> np.ndarray:
    grid = np.linspace(-math.pi, math.pi, 8001)
    w = det_plaquette_weight(grid, beta)
    norm = np.trapezoid(w, grid)
    return np.array([np.trapezoid(w * np.cos(k * grid), grid) / norm for k in k_values])


def det_topological_susceptibility(beta: float, lattice_size: int | None = None) -> float:
    """chi_t = <Q^2> / V for the determinant winding number."""
    if lattice_size is None:
        grid = np.linspace(-math.pi, math.pi, 8001)
        w = det_plaquette_weight(grid, beta)
        return float(np.trapezoid((grid / TWO_PI) ** 2 * w, grid) / np.trapezoid(w, grid))
    q_values, probs = det_topological_charge_distribution(beta, lattice_size)
    return float((q_values.astype(float) ** 2 * probs).sum() / (lattice_size * lattice_size))


def det_topological_charge_distribution(
    beta: float, lattice_size: int, q_max: int | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """Exact finite-volume P(Q), by the same constrained-sum representation as
    `u1_2d.lgt.exact.topological_charge_distribution`: plaquette determinant
    phases are i.i.d. with density w_det, conditioned on summing to 2 pi Q, so
    P(Q) is proportional to int dk exp(-2 pi i k Q) psi(k)^V."""
    volume = lattice_size * lattice_size
    chi_inf = det_topological_susceptibility(beta)
    width = math.sqrt(max(volume * chi_inf, 1e-12))
    if q_max is None:
        q_max = max(3, int(math.ceil(6.0 * width)))
    k_star = math.sqrt(2.0 * 400.0 / (volume * TWO_PI**2 * max(chi_inf, 1e-300)))
    k_cut = min(k_star, 10.0)
    dk = min(k_cut / 400.0, 0.05 / max(1, q_max))
    ks = np.arange(0.0, k_cut + dk, dk)
    psi = _det_psi(ks, beta)
    log_abs = np.log(np.clip(np.abs(psi), 1e-300, None))
    weights = np.sign(psi) ** volume * np.exp(volume * log_abs)
    q_values = np.arange(-q_max, q_max + 1)
    probs = np.array([np.trapezoid(weights * np.cos(TWO_PI * ks * q), ks) for q in q_values])
    probs = np.clip(probs, 0.0, None)
    probs /= probs.sum()
    return q_values, probs


def det_blocked_angle_density(alpha: np.ndarray, beta: float, n_plaquettes: int = 4) -> np.ndarray:
    """Density of the wrapped sum of `n_plaquettes` i.i.d. determinant phases.

    Wrapped convolution multiplies character coefficients, so
    f(alpha) = (1 + 2 sum_q r_q^n cos(q alpha)) / 2 pi. One 2x2 blocking step sums
    four, and -- because det is a homomorphism -- this is EXACT for U(2) despite
    the group being non-abelian: the coarse plaquette determinant is the product
    of the four fine plaquette determinants regardless of ordering.
    """
    alpha = np.asarray(alpha, dtype=float)
    qs = np.arange(1, 41)
    coeffs = np.array([det_character_exact(beta, int(q)) ** n_plaquettes for q in qs])
    series = np.tensordot(coeffs, np.cos(np.multiply.outer(qs, alpha)), axes=1)
    return np.clip((1.0 + 2.0 * series) / TWO_PI, 0.0, None)


# --------------------------------------------------------------------------
# bridges to the U(1) machinery
# --------------------------------------------------------------------------

def matched_u1_beta(beta: float, action_type: str = "wilson") -> float:
    """The U(1) coupling whose plaquette character r_1 matches the U(2) determinant
    sector's. This is the minimum-KL projection of the determinant sector onto the
    one-parameter U(1) family (same exponential-family argument as
    `u1_2d.lgt.blocking.match_coarse_beta`), so it is the right coupling to hand
    `u1_2d` routines that require a Wilson/Villain beta.

    It is a PROJECTION, not an identity: `det_matching_residuals` reports what the
    single coupling cannot reproduce. At large beta it approaches beta / 4, the
    tree-level normalization guide.
    """
    from u1_2d.lgt.exact import plaquette_exact as u1_plaquette_exact

    target = det_character_exact(beta, 1)
    return float(brentq(lambda b: u1_plaquette_exact(b, action_type) - target,
                        1e-6, 4.0 * beta + 10.0, xtol=1e-10))


def det_matching_residuals(beta: float, action_type: str = "wilson",
                           n_characters: int = 3) -> dict:
    """Exactly how wrong it is to call the determinant sector "U(1) at beta/4".

    Reports, for the r_1-matched U(1) coupling: the ratio beta_1 / (beta / 4), the
    residuals in the higher characters r_q (q >= 2), the topological-susceptibility
    residual, and the sup-norm CDF distance between the two plaquette-angle
    densities. All vanish as beta -> infinity and are largest at strong coupling.
    """
    from u1_2d.lgt.exact import (
        plaquette_angle_density,
        plaquette_character_exact,
        topological_susceptibility_exact,
    )

    matched = matched_u1_beta(beta, action_type)
    grid = np.linspace(-math.pi, math.pi, 8001)
    f_det = det_plaquette_angle_density(grid, beta)
    f_u1 = plaquette_angle_density(grid, matched, action_type)
    step = grid[1] - grid[0]
    cdf_det = np.cumsum(f_det) * step
    cdf_u1 = np.cumsum(f_u1) * step
    return {
        "matched_u1_beta": matched,
        "tree_level_ratio": matched / (beta / 4.0),
        "character_residuals": {
            q: plaquette_character_exact(matched, q, action_type) / det_character_exact(beta, q) - 1.0
            for q in range(2, n_characters + 1)
        },
        "chi_t_residual": (topological_susceptibility_exact(matched, action_type)
                           / det_topological_susceptibility(beta) - 1.0),
        "ks_distance": float(np.abs(cdf_det / cdf_det[-1] - cdf_u1 / cdf_u1[-1]).max()),
    }
