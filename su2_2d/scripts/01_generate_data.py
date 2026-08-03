"""Generate SU(2) HMC training ensembles at the configured rungs.

    .venv/Scripts/python.exe su2_2d/scripts/01_generate_data.py --config su2_2d/configs/su2.yaml
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import torch
import yaml

from su2_2d.lgt import mean_plaquette, plaquette_exact, run_hmc_ensemble


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="su2_2d/configs/su2.yaml")
    args = parser.parse_args()
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    data = config["data"]
    out_dir = Path(data["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    for l, beta in data["rungs"]:
        path = out_dir / f"wilson_L{l}_beta{beta:g}.pt"
        if path.exists():
            print(f"{path} exists, skipping")
            continue
        t0 = time.time()
        configs, acc = run_hmc_ensemble(
            l, beta, n_configs=data["n_configs"], n_chains=data["n_chains"],
            burn_in=data["burn_in"], thin=data["thin"], seed=config["seed"])
        plaq = float(mean_plaquette(configs).mean())
        torch.save({"configs": configs, "beta": beta, "lattice_size": l}, path)
        print(f"L={l} beta={beta}: {configs.shape[0]} configs, acc {acc:.2f}, "
              f"plaq {plaq:+.4f} (exact {plaquette_exact(beta):+.4f}), "
              f"{time.time() - t0:.0f}s -> {path}")


if __name__ == "__main__":
    main()
