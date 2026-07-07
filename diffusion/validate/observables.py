"""Per-configuration observable extraction for validation."""

import numpy as np
import torch

from ..lgt.lattice import (
    plaquette_angles,
    topological_charge,
    plaquette_correlator,
)
from inverserg.lattice import wilson_loop_angles

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
    """Returns per-config arrays plus derived quantities.

    keys:
      plaquette [N], plaq_angles [N * L^2] (flattened sample of angles),
      wilson_{RxT} [N], topological_charge [N],
      creutz_{R} (scalar Creutz ratios chi(R, R)),
      plaq_correlator [max_corr_distance]
    """
    if configs.dim() == 3:
        configs = configs.unsqueeze(0)
    lattice_size = configs.shape[-1]
    if max_corr_distance is None:
        max_corr_distance = min(lattice_size // 2, 8)
    out: dict = {}
    with torch.no_grad():
        angles = plaquette_angles(configs)
        out["plaquette"] = torch.cos(angles).mean(dim=(-2, -1)).cpu().numpy()
        out["plaq_angles"] = angles.reshape(-1).cpu().numpy()
        out["topological_charge"] = topological_charge(configs).cpu().numpy()
        max_extent = lattice_size // 2
        for r, t in loops:
            if r <= max_extent and t <= max_extent:
                w = torch.cos(wilson_loop_angles(configs, r, t)).mean(dim=(-2, -1))
                out[f"wilson_{r}x{t}"] = w.cpu().numpy()
        out["plaq_correlator"] = plaquette_correlator(configs, max_corr_distance).cpu().numpy()

    max_square = max((int(k.split("_")[1].split("x")[0]) for k in out if k.startswith("wilson_")
                      and k.split("_")[1].split("x")[0] == k.split("_")[1].split("x")[1]), default=1)
    for r in range(2, max_square + 1):
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
    return out
