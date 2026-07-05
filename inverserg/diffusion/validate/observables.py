"""Per-configuration observable extraction for validation."""

import numpy as np
import torch

from ..lgt.lattice import (
    plaquette_angles,
    topological_charge,
    plaquette_correlator,
)
from ...lattice import wilson_loop_angles

DEFAULT_LOOPS = ((1, 1), (1, 2), (2, 2), (2, 3), (3, 3))


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
        for r, t in loops:
            if r < lattice_size and t < lattice_size:
                w = torch.cos(wilson_loop_angles(configs, r, t)).mean(dim=(-2, -1))
                out[f"wilson_{r}x{t}"] = w.cpu().numpy()
        out["plaq_correlator"] = plaquette_correlator(configs, max_corr_distance).cpu().numpy()

    for r in (2, 3):
        needed = [f"wilson_{r}x{r}", f"wilson_{r-1}x{r-1}", f"wilson_{r-1}x{r}", f"wilson_{r}x{r-1}"]
        alt = {f"wilson_{r}x{r-1}": f"wilson_{r-1}x{r}"}
        vals = {}
        ok = True
        for key in needed:
            source = key if key in out else alt.get(key)
            if source in out:
                vals[key] = out[source].mean()
            else:
                ok = False
        if ok and min(vals[f"wilson_{r-1}x{r}"], vals[f"wilson_{r}x{r-1}"]) > 0 and min(
            vals[f"wilson_{r}x{r}"], vals[f"wilson_{r-1}x{r-1}"]
        ) > 0:
            out[f"creutz_{r}"] = float(
                -np.log(
                    vals[f"wilson_{r}x{r}"]
                    * vals[f"wilson_{r-1}x{r-1}"]
                    / (vals[f"wilson_{r-1}x{r}"] * vals[f"wilson_{r}x{r-1}"])
                )
            )
    return out
