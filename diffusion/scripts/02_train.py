"""Train the conditional score model across all training rungs.

    python diffusion/scripts/02_train.py --config diffusion/configs/default.yaml
"""

import argparse
from pathlib import Path

from diffusion.lgt import block_links
from diffusion.model.train import RungData, TrainConfig, train_score_model
from diffusion.utils import (
    load_config,
    resolve_device,
    set_seed,
    load_ensemble,
    ensemble_path,
    save_json,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="diffusion/configs/default.yaml")
    parser.add_argument("--epochs", type=int, default=None, help="override config epochs")
    args = parser.parse_args()
    config = load_config(args.config)
    set_seed(int(config["seed"]))
    device = resolve_device(config)
    action_type = config["action_type"]
    data_cfg, train_cfg = config["data"], config["train"]
    out_dir = Path(data_cfg["out_dir"])
    val_fraction = float(train_cfg.get("val_fraction", 0.1))

    train_rungs, val_rungs = [], []
    for rung in data_cfg["rungs"]:
        configs, meta = load_ensemble(
            ensemble_path(out_dir, action_type, rung["lattice_size"], rung["beta"])
        )
        coarse = block_links(configs)
        n_val = max(1, int(val_fraction * configs.shape[0]))
        name = f"L{rung['lattice_size']}_beta{rung['beta']:g}"
        train_rungs.append(
            RungData(name, configs[:-n_val], coarse[:-n_val], float(rung["beta"]))
        )
        val_rungs.append(RungData(name, configs[-n_val:], coarse[-n_val:], float(rung["beta"])))
        print(f"rung {name}: {configs.shape[0] - n_val} train / {n_val} val configs")

    cfg = TrainConfig(
        epochs=int(args.epochs if args.epochs is not None else train_cfg["epochs"]),
        batch_size=int(train_cfg["batch_size"]),
        learning_rate=float(train_cfg["learning_rate"]),
        sigma_min=float(train_cfg["sigma_min"]),
        sigma_max=float(train_cfg["sigma_max"]),
        hidden=int(train_cfg["hidden"]),
        depth=int(train_cfg["depth"]),
        kernel_size=int(train_cfg.get("kernel_size", 3)),
        device=device,
        seed=int(config["seed"]),
        topo_weight=float(train_cfg.get("topo_weight", 0.0)),
        checkpoint_path=train_cfg["checkpoint"],
    )
    model, history = train_score_model(train_rungs, val_rungs, cfg)
    save_json(train_cfg["history"], history)
    print(f"checkpoint: {train_cfg['checkpoint']}")
    print(f"history:    {train_cfg['history']}")


if __name__ == "__main__":
    main()
