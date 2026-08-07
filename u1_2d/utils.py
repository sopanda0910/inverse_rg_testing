"""Shared helpers for the diffusion scripts: config, seeding, ensemble I/O."""

import json
import os
import random
from pathlib import Path

import numpy as np
import torch
import yaml

_CU_WHEEL_HINT = (
    "install a matching wheel, e.g.\n"
    "  pip install --index-url https://download.pytorch.org/whl/cu128 "
    "torch torchvision torchaudio"
)


def load_config(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def resolve_device(config: dict) -> str:
    """U1_2D_DEVICE env override > config['device'] > auto-detect.

    The env override lets the campaign/scheduled-task launchers move a run between
    machines without editing every config. An explicit 'cuda' that cannot be honored
    is an error, not a silent fall back to CPU -- a run that quietly takes 40x longer
    than intended is worse than one that refuses to start.
    """
    device = os.environ.get("U1_2D_DEVICE") or config.get("device", "auto")
    if device == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if str(device).startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError(
            f"device='{device}' requested but torch.cuda.is_available() is False. "
            f"This torch ({torch.__version__}) is built for CUDA "
            f"{torch.version.cuda or 'nothing -- it is a CPU-only wheel'}; "
            + _CU_WHEEL_HINT
        )
    return device


def configure_device(device: str) -> str:
    """Turn on the CUDA fast paths this workload wants; return a one-line banner.

    TF32 is OFF by default and opt-in via U1_2D_TF32=1. Measured on the RTX 5060,
    it costs ~120x arithmetic accuracy (max relative error 3.1e-4 vs 2.5e-6 in
    fp32) -- the same order as the observable agreement this study reports
    (plaquette to ~2 parts in 1e4), and it moved the smoke run's validation loss
    by 40x the seed-to-seed spread. That is a precision budget this project does
    not have to spend on a model that is not compute-bound anyway.

    cudnn.benchmark stays on: it only picks among fp32 algorithms, and every rung
    runs one fixed [B, 2, L, L] shape for the whole run, so the warm-up amortizes.
    """
    if not str(device).startswith("cuda"):
        return f"{device} | torch {torch.__version__} | {torch.get_num_threads()} threads"

    tf32 = os.environ.get("U1_2D_TF32", "0") == "1"
    torch.backends.cuda.matmul.allow_tf32 = tf32
    torch.backends.cudnn.allow_tf32 = tf32
    torch.backends.cudnn.benchmark = True

    props = torch.cuda.get_device_properties(torch.device(device).index or 0)
    arch = f"sm_{props.major}{props.minor}"
    # A wheel older than the card reports is_available() == True and then dies at
    # the first kernel launch with "no kernel image is available for execution on
    # the device". Blackwell (sm_120) hits this on every pre-cu128 build.
    if arch not in torch.cuda.get_arch_list():
        raise RuntimeError(
            f"{props.name} is {arch}, but this torch ({torch.__version__}) only ships "
            f"kernels for {', '.join(torch.cuda.get_arch_list())}. Every kernel launch "
            f"would fail; " + _CU_WHEEL_HINT
        )
    return (
        f"{device} | {props.name} | {arch} | "
        f"{props.total_memory / 1024**3:.1f} GiB | "
        f"torch {torch.__version__}/cu{torch.version.cuda} | "
        f"tf32 {'on' if tf32 else 'off'}"
    )


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def save_ensemble(path: str | Path, configs: torch.Tensor, metadata: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    torch.save({"configs": configs.cpu(), "metadata": metadata}, tmp)
    tmp.replace(path)


def load_ensemble(path: str | Path) -> tuple[torch.Tensor, dict]:
    payload = torch.load(path, map_location="cpu", weights_only=True)
    return payload["configs"], payload["metadata"]


def ensemble_path(out_dir: str | Path, action_type: str, lattice_size: int, beta: float) -> Path:
    return Path(out_dir) / f"{action_type}_L{lattice_size}_beta{beta:g}.pt"


def save_json(path: str | Path, payload) -> None:
    """Write via a temp file + atomic rename so a kill mid-write can never leave a
    truncated/corrupt JSON file behind -- callers use this file's presence/validity
    to decide what's already done, so a torn write would silently break resume."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


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
