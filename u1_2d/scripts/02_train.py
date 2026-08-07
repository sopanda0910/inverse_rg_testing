"""Train the conditional score model across all training rungs.

    python u1_2d/scripts/02_train.py --config u1_2d/configs/default.yaml
"""

import argparse
from pathlib import Path

from u1_2d.lgt import block_links
from u1_2d.model.train import RungData, TrainConfig, train_score_model
from u1_2d.utils import (
    configure_device,
    load_config,
    resolve_device,
    set_seed,
    load_ensemble,
    ensemble_path,
    save_json,
    expand_rungs,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="u1_2d/configs/default.yaml")
    parser.add_argument("--epochs", type=int, default=None, help="override config epochs")
    parser.add_argument("--device", default=None, help="override config device (cpu | cuda)")
    parser.add_argument("--resume", action="store_true",
                        help="continue from the .resume snapshot next to the checkpoint")
    args = parser.parse_args()
    config = load_config(args.config)
    set_seed(int(config["seed"]))
    if args.device is not None:
        config["device"] = args.device
    device = resolve_device(config)
    print(f"device: {configure_device(device)}")
    action_type = config["action_type"]
    data_cfg, train_cfg = config["data"], config["train"]
    out_dir = Path(data_cfg["out_dir"])
    val_fraction = float(train_cfg.get("val_fraction", 0.1))

    train_rungs, val_rungs = [], []
    for rung in expand_rungs(data_cfg, int(config["seed"])):
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
        cond_channels=int(train_cfg.get("cond_channels", 4)),
        sigma_min_beta_coef=(
            float(train_cfg["sigma_min_beta_coef"])
            if train_cfg.get("sigma_min_beta_coef") is not None else None
        ),
        device=device,
        seed=int(config["seed"]),
        topo_weight=float(train_cfg.get("topo_weight", 0.0)),
        early_stop_patience=int(train_cfg.get("early_stop_patience", 0)),
        resume=bool(args.resume),
        checkpoint_path=train_cfg["checkpoint"],
        ema_decay=float(train_cfg.get("ema_decay", 0.999)),
        cosine_lr=bool(train_cfg.get("cosine_lr", True)),
        min_learning_rate=float(train_cfg.get("min_learning_rate", 1e-6)),
        grad_clip_norm=(
            float(train_cfg["grad_clip_norm"])
            if train_cfg.get("grad_clip_norm") is not None else 1.0
        ),
        snapshot_every=int(train_cfg.get("snapshot_every", 10)),
        log_every=int(train_cfg.get("log_every", 1)),
        high_beta_sigma_bias=float(train_cfg.get("high_beta_sigma_bias", 0.0)),
        sym_augment=float(train_cfg.get("sym_augment", 0.0)),
        norm_type=str(train_cfg.get("norm_type", "group")),
        cond_film=bool(train_cfg.get("cond_film", False)),
    )
    model, history = train_score_model(train_rungs, val_rungs, cfg)

    heldout_rungs = []
    for rung in data_cfg.get("heldout", []) or []:
        path = ensemble_path(out_dir, action_type, rung["lattice_size"], rung["beta"])
        if not path.exists():
            print(f"heldout ensemble missing, skipping: {path}")
            continue
        configs, _ = load_ensemble(path)
        heldout_rungs.append(
            RungData(f"heldout_L{rung['lattice_size']}_beta{rung['beta']:g}",
                     configs, block_links(configs), float(rung["beta"]))
        )
    if heldout_rungs:
        import torch as _torch
        from u1_2d.model.schedule import GeometricNoiseSchedule
        from u1_2d.model.train import denoising_loss, _prepare_rung
        schedule = GeometricNoiseSchedule(
            cfg.sigma_min, cfg.sigma_max, sigma_min_beta_coef=cfg.sigma_min_beta_coef
        )
        heldout_record = {}
        with _torch.no_grad():
            for r in heldout_rungs:
                data = _prepare_rung(r, cfg.device, cfg.cond_channels)
                gen = _torch.Generator(device="cpu").manual_seed(54321)
                sigma = schedule.sigma(
                    _torch.rand(data["fine"].shape[0], generator=gen).to(cfg.device),
                    beta=data["beta"],
                )
                heldout_record[data["name"]] = float(denoising_loss(
                    model, data["fine"], data["cond"], data["beta"], schedule,
                    sigma=sigma, topo_weight=cfg.topo_weight,
                ))
        history.append({"heldout": heldout_record})
        print("heldout losses:", heldout_record)

    save_json(train_cfg["history"], history)
    print(f"checkpoint: {train_cfg['checkpoint']}")
    print(f"history:    {train_cfg['history']}")


if __name__ == "__main__":
    main()
