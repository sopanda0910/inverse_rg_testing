"""Run the inverse-RG ladder: HMC at the coarse base, then iterated generation.

    python inverserg/diffusion/scripts/03_run_ladder.py --config inverserg/diffusion/configs/default.yaml
"""

import argparse
from pathlib import Path

from diffusion.lgt import make_action, run_hmc_ensemble
from diffusion.model.train import load_checkpoint
from diffusion.pipeline import generate_ladder
from diffusion.utils import (
    load_config,
    resolve_device,
    set_seed,
    save_ensemble,
    load_ensemble,
    ensemble_path,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="inverserg/diffusion/configs/default.yaml")
    args = parser.parse_args()
    config = load_config(args.config)
    set_seed(int(config["seed"]) + 1)
    device = resolve_device(config)
    action_type = config["action_type"]
    ladder_cfg = config["ladder"]
    data_cfg = config["data"]
    out_dir = Path(ladder_cfg["out_dir"])

    base = ladder_cfg["base"]
    base_path = ensemble_path(out_dir, action_type, base["lattice_size"], base["beta"])
    if base_path.exists():
        base_configs, _ = load_ensemble(base_path)
        print(f"loaded base ensemble {base_path}")
    else:
        print(f"simulating base rung L={base['lattice_size']} beta={base['beta']} ...")
        action = make_action(action_type, float(base["beta"]))
        base_configs, stats = run_hmc_ensemble(
            int(base["lattice_size"]),
            action,
            n_configs=int(ladder_cfg["n_base_configs"]),
            n_chains=int(data_cfg["n_chains"]),
            burn_in=int(data_cfg["burn_in"]),
            thin=int(data_cfg["thin"]),
            device=device,
            topological_updates=bool(data_cfg.get("topological_updates", True)),
            hot_start=bool(data_cfg.get("hot_start", True)),
        )
        print(f"  acceptance {stats.acceptance_rate:.3f}")
        save_ensemble(
            base_path,
            base_configs,
            {
                "beta": float(base["beta"]),
                "lattice_size": int(base["lattice_size"]),
                "action_type": action_type,
                "provenance": "direct HMC base rung",
            },
        )

    model, schedule = load_checkpoint(config["train"]["checkpoint"], device)
    results = generate_ladder(
        base_configs,
        [float(b) for b in ladder_cfg["beta_schedule"]],
        model,
        schedule,
        n_retherm_sweeps=int(ladder_cfg["n_retherm_sweeps"]),
        action_type=action_type,
        n_sampler_steps=int(ladder_cfg["n_sampler_steps"]),
        n_corrector_steps=int(ladder_cfg["n_corrector_steps"]),
        batch_size=int(ladder_cfg["sample_batch_size"]),
        device=device,
        consistency_weight=float(ladder_cfg.get("consistency_weight", 1.0)),
        enforce_coarse_charge=bool(ladder_cfg.get("enforce_coarse_charge", True)),
        retherm_topological_updates=bool(ladder_cfg.get("retherm_topological_updates", False)),
    )

    for i, rung in enumerate(results):
        path = out_dir / f"ladder_rung{i}_{action_type}_L{rung.lattice_size}_beta{rung.beta:g}.pt"
        save_ensemble(
            path,
            rung.configs,
            {
                "beta": rung.beta,
                "lattice_size": rung.lattice_size,
                "action_type": action_type,
                "provenance": f"ladder rung {i}: conditional diffusion + {ladder_cfg['n_retherm_sweeps']} retherm sweeps",
                "observables": rung.observables,
            },
        )
        print(f"saved {path}")
        if rung.raw_configs is not None:
            raw_path = out_dir / f"ladder_rung{i}_raw_{action_type}_L{rung.lattice_size}_beta{rung.beta:g}.pt"
            save_ensemble(
                raw_path,
                rung.raw_configs,
                {
                    "beta": rung.beta,
                    "lattice_size": rung.lattice_size,
                    "action_type": action_type,
                    "provenance": f"ladder rung {i}: raw conditional diffusion sample, pre-retherm",
                },
            )
            print(f"saved {raw_path}")


if __name__ == "__main__":
    main()
