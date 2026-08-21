"""Stage 02: train the determinant-sector score network.

The model never sees the SU(2) sector. It is trained by denoising score matching
on psi = wrap(2 phi), the determinant U(1) gauge field of the U(2) ensembles from
stage 01, conditioned on the blocked psi -- so the entire U(1) training stack is
reused unchanged and only the data are new.

The network is conditioned on `model_beta(beta_u2)`, the minimum-KL U(1)
projection of the determinant sector, NOT on beta / 4. Those differ by 23% at
beta = 4 and by 0.003% at beta = 220; the conditioning coupling is what the
network's beta embedding and its gated analytic Wilson hint see, and the residual
between that Wilson hint and the true determinant weight is exactly what the
score net is there to learn.

Device: cuda. Training and model sampling always want the GPU.
"""

import argparse
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u1_2d.model.train import TrainConfig
from u2_2d.lgt.exact import det_matching_residuals
from u2_2d.model.det_lift import det_rung_data, model_beta, train_det_model
from u2_2d.utils import (
    configure_device,
    ensemble_path,
    expand_rungs,
    load_config,
    load_ensemble,
    resolve_device,
    save_json,
    set_seed,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="u2_2d/configs/smoke.yaml")
    parser.add_argument("--device", default=None)
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--checkpoint", default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    if args.device:
        config["device"] = args.device
    device = resolve_device(config)
    print(configure_device(device))
    set_seed(int(config.get("seed", 0)))

    data_dir = Path(args.data_dir or config["data"].get("out_dir", "out/u2_2d/data"))
    train_cfg = config["train"]
    checkpoint = args.checkpoint or train_cfg.get(
        "checkpoint_path", "out/u2_2d/checkpoints/det_score_net.pt"
    )

    val_fraction = float(train_cfg.get("val_fraction", 0.1))
    train_rungs, val_rungs = [], []
    # expand_rungs, NOT data["rungs"] -- stage 01 generates the random-beta draws
    # too, and reading the fixed list here would silently train on 12 couplings
    # out of 114 while every log line said the data was there. A rung whose
    # ensemble is absent is SKIPPED rather than fatal: with ~100 draws a single
    # failed shard should cost one coupling, not the whole retrain.
    all_rungs = expand_rungs(config["data"], int(config.get("seed", 0)))
    missing = 0
    for rung in all_rungs:
        beta, size = float(rung["beta"]), int(rung["lattice_size"])
        # A rung marked `train: false` is a REFERENCE, not training data. The
        # L = 64 top-rung ensemble is the control the ladder's own output is
        # scored against; training on it would make every `z vs reference`
        # column at that rung circular. Nothing else in the pipeline reads this
        # flag, so it has to be honoured here or not at all.
        if not bool(rung.get("train", True)):
            print(f"rung L{size}_b{beta:g}: reference only, excluded from training")
            continue
        path = ensemble_path(data_dir, size, beta)
        if not path.exists():
            missing += 1
            continue
        configs, _ = load_ensemble(path)
        n_val = max(1, int(round(val_fraction * configs.shape[0])))
        name = f"L{size}_b{beta:g}"
        train_rungs.append(det_rung_data(name, configs[n_val:], beta))
        val_rungs.append(det_rung_data(name, configs[:n_val], beta))
        residual = det_matching_residuals(beta)
        print(f"rung {name}: model beta = {model_beta(beta):.4f} "
              f"(beta/4 = {beta / 4:.4f}, ratio {residual['tree_level_ratio']:.4f}), "
              f"chi_t residual {residual['chi_t_residual']:+.2e}, "
              f"{train_rungs[-1].fine.shape[0]} train / {n_val} val")

    if not train_rungs:
        print(f"no training ensembles found under {data_dir} -- run stage 01 first")
        return 1
    print(f"\n{len(train_rungs)} training rungs of {len(all_rungs)} configured"
          f"{f' ({missing} ensembles missing)' if missing else ''}; "
          f"model beta {min(model_beta(float(r['beta'])) for r in all_rungs):.2f} .. "
          f"{max(model_beta(float(r['beta'])) for r in all_rungs):.2f}\n")

    train_config = TrainConfig(
        epochs=int(train_cfg.get("epochs", 40)),
        batch_size=int(train_cfg.get("batch_size", 32)),
        learning_rate=float(train_cfg.get("learning_rate", 2e-4)),
        sigma_min=float(train_cfg.get("sigma_min", 0.02)),
        sigma_max=float(train_cfg.get("sigma_max", 6.0)),
        hidden=int(train_cfg.get("hidden", 64)),
        depth=int(train_cfg.get("depth", 4)),
        kernel_size=int(train_cfg.get("kernel_size", 3)),
        cond_channels=int(train_cfg.get("cond_channels", 5)),
        sigma_min_beta_coef=train_cfg.get("sigma_min_beta_coef"),
        device=device,
        seed=int(config.get("seed", 0)),
        topo_weight=float(train_cfg.get("topo_weight", 0.0)),
        checkpoint_path=checkpoint,
        ema_decay=float(train_cfg.get("ema_decay", 0.999)),
        early_stop_patience=int(train_cfg.get("early_stop_patience", 0)),
        resume=bool(train_cfg.get("resume", False)),
        high_beta_sigma_bias=float(train_cfg.get("high_beta_sigma_bias", 0.0)),
        sym_augment=float(train_cfg.get("sym_augment", 0.0)),
        norm_type=str(train_cfg.get("norm_type", "channel")),
        cond_film=bool(train_cfg.get("cond_film", True)),
    )
    _, history = train_det_model(train_rungs, val_rungs, train_config)
    save_json(Path(checkpoint).with_suffix(".history.json"), history)
    print(f"checkpoint: {checkpoint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
