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
