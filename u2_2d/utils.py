"""Shared helpers for the U(2) scripts.

Config loading, seeding, device resolution and JSON writing are inherited
unchanged from `u1_2d.utils` -- including the CUDA-architecture guard that
refuses to start on a torch wheel older than the card (the Blackwell / sm_120
trap described in CLAUDE.md). Only the ensemble path naming is redefined, so U(2)
and U(1) ensembles never collide in a shared output directory.

The device override environment variable is `U2_2D_DEVICE`, falling back to
`U1_2D_DEVICE` so a campaign launcher can move both studies with one variable.
"""

import os
from pathlib import Path

import torch

from u1_2d.utils import (  # noqa: F401  (re-exported for the scripts)
    configure_device,
    load_config,
    load_ensemble,
    save_ensemble,
    save_json,
    set_seed,
)


def resolve_device(config: dict) -> str:
    """U2_2D_DEVICE > U1_2D_DEVICE > config['device'] > auto-detect."""
    from u1_2d.utils import resolve_device as _resolve

    override = os.environ.get("U2_2D_DEVICE")
    if override:
        config = dict(config)
        config["device"] = override
        os.environ.pop("U1_2D_DEVICE", None)
    return _resolve(config)


def ensemble_path(out_dir: str | Path, lattice_size: int, beta: float,
                  tag: str = "u2") -> Path:
    return Path(out_dir) / f"{tag}_L{lattice_size}_beta{beta:g}.pt"


def to_cpu(configs: torch.Tensor) -> torch.Tensor:
    """Normalize an HMC return value to the CPU-resident ensemble convention.

    `lgt.hmc.run_hmc_ensemble` is the one function that returns tensors on its
    `device`; everything else in the project assumes CPU ensembles. Call this on
    its output before the tensor meets anything else -- three real bugs in the
    U(1) study came from skipping exactly this step.
    """
    return configs.detach().cpu()


def expand_rungs(data_cfg: dict, seed: int) -> list[dict]:
    """Fixed rungs plus deterministic log-uniform draws from data.random_rungs.

    Ported from `u1_2d.utils.expand_rungs`, with the U(2) start policy: the base
    couplings are hot-started below beta = 15 and cold above, and thermalization
    is done with heatbath + overrelaxation sweeps rather than burn-in
    trajectories (7x cheaper at L = 32, see the stage-01 module comment).

    Each spec {n, beta_min, beta_max, lattice_size, n_configs?} expands to n
    rungs with betas drawn log-uniformly, deterministic in the config seed and
    the spec's position, so a rerun reproduces the same training set.
    """
    import numpy as np

    rungs = [dict(r) for r in data_cfg.get("rungs", [])]
    for index, spec in enumerate(data_cfg.get("random_rungs", [])):
        rng = np.random.default_rng(seed + 1000 * (index + 1))
        betas = np.exp(rng.uniform(np.log(float(spec["beta_min"])),
                                   np.log(float(spec["beta_max"])),
                                   int(spec["n"])))
        for beta in np.sort(betas):
            beta = round(float(beta), 4)
            rung = {
                "beta": beta,
                "lattice_size": int(spec["lattice_size"]),
                "hot_start": beta < 15.0,
                "burn_in": int(spec.get("burn_in", 300)),
                "thermalize_sweeps": int(spec.get("thermalize_sweeps", 60)),
                "seed_exact_sectors": bool(spec.get("seed_exact_sectors", False)),
            }
            for key in ("n_configs", "n_chains", "sector_augment"):
                if key in spec:
                    rung[key] = spec[key]
            rungs.append(rung)
    return rungs
