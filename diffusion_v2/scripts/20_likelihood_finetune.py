"""Tier 2: maximum-likelihood fine-tune of the score through the flow ODE.

Warm-starts from the campaign checkpoint and minimizes
    L = -E_pairs[log q(fine | coarse)] / n_dof  +  dsm_weight * L_DSM
over existing HMC data pairs (fine ensembles + their blocked coarse partners,
high-beta rungs only by default). The ML term is the FFJORD objective for the
deployed proposal; the DSM anchor keeps the score matched to the noised
marginals everywhere the ML minibatches do not reach. NOT a retrain: a few
hundred optimizer steps on a warm model; the pretrained checkpoint is never
overwritten (output goes to score_net_mlft.pt by default).

Validation tracks mean log q / dof on held-out pairs via the evaluation-grade
integrator; the best-val state is saved. Verify with 19_ode_reweighting.py
--checkpoint <out> afterwards: success = log_weight_std_fiber drops.

    .venv/Scripts/python.exe diffusion_v2/scripts/20_likelihood_finetune.py \
        --config diffusion_v2/configs/v2.yaml --steps 300
"""

import argparse
import math
import time
from pathlib import Path

import torch

from diffusion_v2.lgt import block_links
from diffusion_v2.model.likelihood import conditional_log_likelihood
from diffusion_v2.model.likelihood_train import ml_conditional_log_likelihood
from diffusion_v2.model.schedule import GeometricNoiseSchedule
from diffusion_v2.model.train import denoising_loss, load_checkpoint, _prepare_rung, RungData
from diffusion_v2.utils import (
    ensemble_path, expand_rungs, load_config, load_ensemble,
    resolve_device, save_json, set_seed,
)


def load_pairs(config, args, device):
    """(train, val) lists of dicts {fine, coarse, beta, name}; high-beta rungs."""
    data_cfg = config["data"]
    out_dir = Path(data_cfg["out_dir"])
    action_type = config["action_type"]
    train, val = [], []
    for rung in expand_rungs(data_cfg, int(config["seed"])):
        if float(rung["beta"]) < args.beta_min:
            continue
        path = ensemble_path(out_dir, action_type, rung["lattice_size"], rung["beta"])
        if not path.exists():
            continue
        configs, _ = load_ensemble(path)
        configs = configs[: args.configs_per_rung + args.val_per_rung]
        coarse = block_links(configs)
        name = f"L{rung['lattice_size']}_beta{rung['beta']:g}"
        n_v = args.val_per_rung
        train.append({"fine": configs[:-n_v], "coarse": coarse[:-n_v],
                      "beta": float(rung["beta"]), "name": name})
        val.append({"fine": configs[-n_v:], "coarse": coarse[-n_v:],
                    "beta": float(rung["beta"]), "name": name})
        if args.max_rungs and len(train) >= args.max_rungs:
            break
    if not train:
        raise SystemExit(f"no rungs with beta >= {args.beta_min} under {out_dir}")
    return train, val


def eval_val_logq(model, schedule, val, args, device):
    """Mean log q / dof over held-out pairs, evaluation-grade integrator."""
    model.eval()
    total, n = 0.0, 0
    for r in val:
        log_q = conditional_log_likelihood(
            model, schedule, r["coarse"], r["fine"], r["beta"],
            n_steps=args.eval_ode_steps, n_probes=args.n_probes,
            consistency_weight=args.consistency_weight,
            physics_blend_coef=args.physics_blend,
            physics_blend_beta_min=args.physics_blend_beta_min,
            batch_size=args.ml_batch * 2, device=device, seed=args.seed,
        )
        n_dof = r["fine"][0].numel()
        total += float(log_q.sum()) / n_dof
        n += log_q.numel()
    model.train()
    return total / n


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="diffusion_v2/configs/v2.yaml")
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--out-checkpoint", default=None,
                        help="default: score_net_mlft.pt next to the input checkpoint")
    parser.add_argument("--steps", type=int, default=300)
    parser.add_argument("--lr", type=float, default=1e-5)
    parser.add_argument("--ml-batch", type=int, default=4)
    parser.add_argument("--ml-ode-steps", type=int, default=24)
    parser.add_argument("--eval-ode-steps", type=int, default=60)
    parser.add_argument("--n-probes", type=int, default=1)
    parser.add_argument("--dsm-weight", type=float, default=1.0)
    parser.add_argument("--dsm-batch", type=int, default=16)
    parser.add_argument("--beta-min", type=float, default=10.0,
                        help="fine-tune only on rungs at or above this beta")
    parser.add_argument("--configs-per-rung", type=int, default=48)
    parser.add_argument("--val-per-rung", type=int, default=8)
    parser.add_argument("--max-rungs", type=int, default=0,
                        help="cap number of rungs loaded (0 = all matching)")
    parser.add_argument("--eval-every", type=int, default=25)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=20260801)
    parser.add_argument("--consistency-weight", type=float, default=None)
    parser.add_argument("--physics-blend", type=float, default=None)
    parser.add_argument("--physics-blend-beta-min", type=float, default=None)
    parser.add_argument("--sigma-min-coef", type=float, default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    set_seed(args.seed)
    device = resolve_device(config)
    ladder_cfg = config.get("ladder", {})
    if args.consistency_weight is None:
        args.consistency_weight = float(ladder_cfg.get("consistency_weight", 1.0))
    if args.physics_blend is None:
        args.physics_blend = float(ladder_cfg.get("physics_blend_coef", 0.0))
    if args.physics_blend_beta_min is None:
        args.physics_blend_beta_min = float(ladder_cfg.get("physics_blend_beta_min", 0.0))

    ckpt_path = args.checkpoint or config["train"]["checkpoint"]
    out_path = Path(args.out_checkpoint or (Path(ckpt_path).parent / "score_net_mlft.pt"))
    model, schedule = load_checkpoint(ckpt_path, device)
    coef = (args.sigma_min_coef if args.sigma_min_coef is not None
            else ladder_cfg.get("sigma_min_beta_coef"))
    if coef is not None:
        schedule = GeometricNoiseSchedule(
            schedule.sigma_min, schedule.sigma_max, sigma_min_beta_coef=float(coef)
        )
    model.train()

    train, val = load_pairs(config, args, device)
    print(f"rungs: {[r['name'] for r in train]}")
    dsm_data = [
        _prepare_rung(
            RungData(r["name"], r["fine"], r["coarse"], r["beta"]),
            device, getattr(model, "cond_channels", 4),
        )
        for r in train
    ]

    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    gen = torch.Generator().manual_seed(args.seed)
    history = []
    val0 = eval_val_logq(model, schedule, val, args, device)
    best_val, best_state = val0, {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    print(f"initial val log q/dof: {val0:.4f}")

    for step in range(1, args.steps + 1):
        t0 = time.time()
        ri = int(torch.randint(len(train), (1,), generator=gen))
        r = train[ri]
        idx = torch.randperm(r["fine"].shape[0], generator=gen)[: args.ml_batch]
        log_q = ml_conditional_log_likelihood(
            model, schedule, r["coarse"][idx], r["fine"][idx], r["beta"],
            n_steps=args.ml_ode_steps, n_probes=args.n_probes,
            consistency_weight=args.consistency_weight,
            physics_blend_coef=args.physics_blend,
            physics_blend_beta_min=args.physics_blend_beta_min,
            device=device,
        )
        n_dof = r["fine"][0].numel()
        loss_ml = -log_q.mean() / n_dof

        loss = loss_ml
        loss_dsm = None
        if args.dsm_weight > 0:
            d = dsm_data[int(torch.randint(len(dsm_data), (1,), generator=gen))]
            j = torch.randperm(d["fine"].shape[0], generator=gen)[: args.dsm_batch]
            loss_dsm = denoising_loss(
                model, d["fine"][j], d["cond"][j], d["beta"][j], schedule
            )
            loss = loss + args.dsm_weight * loss_dsm

        optimizer.zero_grad()
        loss.backward()
        if args.grad_clip > 0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
        optimizer.step()

        rec = {"step": step, "rung": r["name"],
               "loss_ml_per_dof": float(loss_ml),
               "loss_dsm": None if loss_dsm is None else float(loss_dsm),
               "seconds": round(time.time() - t0, 1)}
        if step % args.eval_every == 0 or step == args.steps:
            rec["val_logq_per_dof"] = eval_val_logq(model, schedule, val, args, device)
            if rec["val_logq_per_dof"] > best_val:
                best_val = rec["val_logq_per_dof"]
                best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
                payload = torch.load(ckpt_path, map_location="cpu", weights_only=True)
                payload["model_state"] = best_state
                out_path.parent.mkdir(parents=True, exist_ok=True)
                torch.save(payload, out_path)
                rec["saved"] = str(out_path)
        history.append(rec)
        print(rec, flush=True)
        save_json(out_path.with_suffix(".history.json"), history)

    print(f"best val log q/dof: {best_val:.4f} (initial {val0:.4f})")
    print(f"checkpoint: {out_path}")


if __name__ == "__main__":
    main()
