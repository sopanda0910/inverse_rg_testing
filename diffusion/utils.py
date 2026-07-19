"""Shared helpers for the diffusion scripts: config, seeding, ensemble I/O."""

import json
import random
from pathlib import Path

import numpy as np
import torch
import yaml


def load_config(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def resolve_device(config: dict) -> str:
    device = config.get("device", "auto")
    if device == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return device


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def save_ensemble(path: str | Path, configs: torch.Tensor, metadata: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"configs": configs.cpu(), "metadata": metadata}, path)


def load_ensemble(path: str | Path) -> tuple[torch.Tensor, dict]:
    payload = torch.load(path, map_location="cpu", weights_only=True)
    return payload["configs"], payload["metadata"]


def ensemble_path(out_dir: str | Path, action_type: str, lattice_size: int, beta: float) -> Path:
    return Path(out_dir) / f"{action_type}_L{lattice_size}_beta{beta:g}.pt"


def save_json(path: str | Path, payload) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def expand_rungs(data_cfg: dict, seed: int) -> list[dict]:
    """Fixed rungs plus deterministic log-uniform draws from data.random_rungs.

    Each random_rungs spec {n, beta_min, beta_max, lattice_size, n_configs?} expands
    to n rungs with betas drawn log-uniformly (deterministic in the config seed and
    the spec's position), carrying the established start policy: hot below beta = 5,
    cold with burn-in 600 up to beta = 20, cold with burn-in 2000 above.
    """
    rungs = [dict(r) for r in data_cfg.get("rungs", [])]
    for index, spec in enumerate(data_cfg.get("random_rungs", [])):
        rng = np.random.default_rng(seed + 1000 * (index + 1))
        betas = np.exp(rng.uniform(np.log(float(spec["beta_min"])),
                                   np.log(float(spec["beta_max"])), int(spec["n"])))
        for beta in np.sort(betas):
            beta = round(float(beta), 4)
            rung = {
                "beta": beta,
                "lattice_size": int(spec["lattice_size"]),
                "hot_start": beta < 5.0,
                "burn_in": 200 if beta < 5.0 else (2000 if beta >= 20.0 else 600),
            }
            if "n_configs" in spec:
                rung["n_configs"] = int(spec["n_configs"])
            rungs.append(rung)
    return rungs
