"""Generate HMC ensembles for all training + held-out rungs, plus beta matching.

    python inverserg/diffusion/scripts/01_generate_data.py --config inverserg/diffusion/configs/default.yaml
"""

import argparse
import time
from pathlib import Path

import torch

from inverserg.diffusion.lgt import make_action, run_hmc_ensemble, block_links, match_coarse_beta
from inverserg.diffusion.lgt.blocking import villain_blocked_beta
from inverserg.diffusion.lgt.hmc import adapted_hmc_params
from inverserg.diffusion.utils import (
    load_config,
    resolve_device,
    set_seed,
    save_ensemble,
    ensemble_path,
    save_json,
)


def generate_rung(rung: dict, data_cfg: dict, action_type: str, device: str) -> torch.Tensor:
    beta, lattice_size = float(rung["beta"]), int(rung["lattice_size"])
    action = make_action(action_type, beta)
    step_size, n_steps = adapted_hmc_params(
        beta, float(data_cfg["hmc_step_size"]), int(data_cfg["hmc_steps"])
    )
    step_size = float(rung.get("hmc_step_size", step_size))
    n_steps = int(rung.get("hmc_steps", n_steps))
    t0 = time.time()
    configs, stats = run_hmc_ensemble(
        lattice_size,
        action,
        n_configs=int(data_cfg["n_configs"]),
        n_chains=int(data_cfg["n_chains"]),
        burn_in=int(data_cfg["burn_in"]),
        thin=int(data_cfg["thin"]),
        n_steps=n_steps,
        step_size=step_size,
        device=device,
        topological_updates=bool(data_cfg.get("topological_updates", True)),
        hot_start=bool(data_cfg.get("hot_start", True)),
    )
    print(
        f"  L={lattice_size} beta={beta}: {configs.shape[0]} configs, "
        f"acceptance {stats.acceptance_rate:.3f}, {time.time()-t0:.0f}s"
    )
    return configs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="inverserg/diffusion/configs/default.yaml")
    args = parser.parse_args()
    config = load_config(args.config)
    set_seed(int(config["seed"]))
    device = resolve_device(config)
    action_type = config["action_type"]
    data_cfg = config["data"]
    out_dir = Path(data_cfg["out_dir"])

    matching = {}
    for rung in list(data_cfg["rungs"]) + list(data_cfg.get("heldout", [])):
        path = ensemble_path(out_dir, action_type, rung["lattice_size"], rung["beta"])
        if path.exists():
            print(f"skip existing {path}")
            continue
        print(f"generating {path} ...")
        configs = generate_rung(rung, data_cfg, action_type, device)
        save_ensemble(
            path,
            configs,
            {
                "beta": float(rung["beta"]),
                "lattice_size": int(rung["lattice_size"]),
                "action_type": action_type,
                "provenance": "direct HMC (Omelyan) + instanton updates",
                "n_configs": configs.shape[0],
                "sampler": {k: data_cfg[k] for k in ("n_chains", "burn_in", "thin", "hmc_steps", "hmc_step_size")},
                "seed": int(config["seed"]),
            },
        )
        if action_type == "villain":
            matched = villain_blocked_beta(float(rung["beta"]))
        else:
            matched = match_coarse_beta(block_links(configs), action_type)
        matching[f"L{rung['lattice_size']}_beta{rung['beta']:g}"] = {
            "fine_beta": float(rung["beta"]),
            "matched_coarse_beta": matched,
            "tree_level": float(rung["beta"]) / 4.0,
        }
        print(f"  matched coarse beta: {matched:.4f} (tree level {float(rung['beta'])/4.0:g})")

    if matching:
        save_json(out_dir / "matching.json", matching)
        print(f"wrote {out_dir / 'matching.json'}")


if __name__ == "__main__":
    main()
