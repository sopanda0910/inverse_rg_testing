"""Per-configuration observable extraction for 2D U(2) validation.

Two families, kept separate on purpose:

* FULL U(2) observables -- (1/2)ReTr of Wilson loops, Creutz ratios, the
  plaquette correlator. These test the whole theory, including the SU(2) sector
  that the lift samples exactly.
* DETERMINANT-SECTOR observables -- prefixed `det_`. These test only psi, which
  is the only thing the model generates, and they are the ones with closed-form
  exact references (`lgt.exact.det_*`). Topological charge lives here.

Reporting them together is what makes it possible to say which half of the
factorization any disagreement came from. The U(1) study's caveat carries over:
observable-level agreement on small loops does not constrain the density, so
large-loop dispersion is reported, not just the plaquette.
"""

import math

import numpy as np
import torch

from ..lgt.lattice import (
    det_links,
    det_phase,
    half_retr,
    plaquette,
    plaquette_correlator,
    topological_charge,
    wilson_loop,
)

DEFAULT_LOOPS = (
    (1, 1), (1, 2), (2, 2), (2, 3), (3, 3), (3, 4), (4, 4), (4, 5), (5, 5),
    (5, 6), (6, 6), (6, 7), (7, 7), (7, 8), (8, 8), (8, 10), (10, 10),
    (10, 12), (12, 12),
)


def measure_ensemble(
    configs: torch.Tensor,
    loops: tuple[tuple[int, int], ...] = DEFAULT_LOOPS,
    max_corr_distance: int | None = None,
) -> dict:
    """Returns per-config arrays plus derived scalars.

    keys:
      plaquette [N]                    <(1/2) ReTr P> per configuration
      det_plaquette [N]                <cos alpha_p> per configuration
      det_plaq_angles [N * L^2]        flattened determinant plaquette angles
      wilson_{RxT} [N]                 <(1/2) ReTr W(R, T)>
      det_wilson_{RxT} [N]             <cos(determinant winding of W(R, T))>
      topological_charge [N]
      creutz_{R}                       Creutz ratio chi(R, R) with a jackknife error
      plaq_correlator [max_corr_distance]
    """
    if configs.dim() == 4:
        configs = configs.unsqueeze(0)
    lattice_size = configs.shape[-2]
    if max_corr_distance is None:
        max_corr_distance = min(lattice_size // 2, 8)
    out: dict = {}
    with torch.no_grad():
        plaq = plaquette(configs)
        alpha = det_phase(plaq)
        out["plaquette"] = half_retr(plaq).mean(dim=(-2, -1)).cpu().numpy()
        out["det_plaquette"] = torch.cos(alpha).mean(dim=(-2, -1)).cpu().numpy()
        out["det_plaq_angles"] = alpha.reshape(-1).cpu().numpy()
        out["topological_charge"] = topological_charge(configs).cpu().numpy()
        max_extent = lattice_size // 2
        for r, t in loops:
            if r > max_extent or t > max_extent:
                continue
            loop = wilson_loop(configs, r, t)
            out[f"wilson_{r}x{t}"] = half_retr(loop).mean(dim=(-2, -1)).cpu().numpy()
            out[f"det_wilson_{r}x{t}"] = (
                torch.cos(det_phase(loop)).mean(dim=(-2, -1)).cpu().numpy()
            )
        out["plaq_correlator"] = plaquette_correlator(configs, max_corr_distance).cpu().numpy()

    _add_creutz_ratios(out)
    return out


def _add_creutz_ratios(out: dict) -> None:
    squares = [int(k.split("_")[1].split("x")[0]) for k in out
               if k.startswith("wilson_") and len(set(k.split("_")[1].split("x"))) == 1]
    for r in range(2, max(squares, default=1) + 1):
        needed = [f"wilson_{r}x{r}", f"wilson_{r-1}x{r-1}", f"wilson_{r-1}x{r}", f"wilson_{r}x{r-1}"]
        alt = {f"wilson_{r}x{r-1}": f"wilson_{r-1}x{r}"}
        arrays = []
        for key in needed:
            source = key if key in out else alt.get(key)
            if source not in out:
                arrays = None
                break
            arrays.append(np.asarray(out[source], dtype=float))
        if arrays is None:
            continue
        means = [a.mean() for a in arrays]
        if min(means) <= 0:
            continue
        out[f"creutz_{r}"] = float(-np.log(means[0] * means[1] / (means[2] * means[3])))
        n = len(arrays[0])
        if n > 3:
            loo = [(a.sum() - a) / (n - 1) for a in arrays]
            if min(l.min() for l in loo) > 0:
                chi = -np.log(loo[0] * loo[1] / (loo[2] * loo[3]))
                out[f"creutz_{r}_err"] = float(np.sqrt((n - 1) * chi.var()))


def exact_reference(beta: float, lattice_size: int, loops=DEFAULT_LOOPS) -> dict:
    """Closed-form targets for everything `measure_ensemble` can be compared against.

    Every entry is FINITE VOLUME. In 2D the Wilson loop average depends on the loop
    only through the enclosed area, exactly and for all areas -- there is no
    perimeter contribution -- but on a torus a loop of area A is also a loop of
    area V - A traversed backwards, which contributes corrections of relative order
    exp(-sigma (V - A)). Those are negligible on the matched ladder, where sigma V
    is an invariant (~20 at every deployed rung, giving ~3e-8 at L = 32), and reach
    7e-3 at W(8x8) at the top of the off-ladder coupling scan, where sigma V falls
    to ~1.6. Using the infinite-volume area law there would put a systematic in the
    REFERENCE and score it against the model.

    For the same reason Creutz ratios are built from the finite-volume loops rather
    than set to the infinite-volume string tension: at finite V, chi(R,T) != sigma.
    (`u1_2d` has always done this; u2 did not until 2026-09-01.)

    Note that the Creutz ratios are exact algebraic functions of the Wilson loops
    above them and carry no information the loops do not -- they are a physics
    summary, not an independent test, and should not be counted as separate
    observables in any `mean |z|`.
    """
    from ..lgt.exact import (
        det_character_exact,
        det_topological_charge_distribution,
        det_wilson_loop_exact,
        plaquette_exact,
        wilson_loop_exact,
    )

    q_values, probs = det_topological_charge_distribution(beta, lattice_size)
    reference = {
        "plaquette": plaquette_exact(beta, lattice_size),
        "plaquette_infinite_volume": plaquette_exact(beta),
        "det_plaquette": det_character_exact(beta, 1),
        "topological_charge_squared": float((q_values.astype(float) ** 2 * probs).sum()),
    }
    half = lattice_size // 2
    for r, t in loops:
        if r <= half and t <= half:
            reference[f"wilson_{r}x{t}"] = wilson_loop_exact(
                beta, r * t, lattice_size=lattice_size)
            reference[f"det_wilson_{r}x{t}"] = det_wilson_loop_exact(
                beta, r * t, lattice_size=lattice_size)

    def _w(area):
        return wilson_loop_exact(beta, area, lattice_size=lattice_size)

    for r in range(2, half + 1):
        if r * r >= lattice_size * lattice_size:
            continue
        reference[f"creutz_{r}"] = -math.log(
            _w(r * r) * _w((r - 1) * (r - 1)) / _w(r * (r - 1)) ** 2)
    return reference
