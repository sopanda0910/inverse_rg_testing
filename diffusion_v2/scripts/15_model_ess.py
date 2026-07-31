"""Importance-sampling ESS of the conditional diffusion model via ODE likelihood.

Computes, per (L, beta) case: sample fine configs from the model conditioned on
an HMC coarse ensemble (no charge enforcement, no retherm -- raw model
transport), evaluate log q(fine | coarse) with the probability-flow ODE, and
report the self-normalized ESS/N against the Wilson Boltzmann target. This is
the number flow-based samplers (Q-shift, multilevel) report as their headline
quality metric; parity means the diffusion transport is competitive BEFORE the
structural fixes (charge projection, retherm) that the full pipeline adds.

    python diffusion_v2/scripts/15_model_ess.py --config diffusion_v2/configs/v2.yaml \
        --cases 16:14.1464 16:55.0237 32:55.0237 --n-configs 64
"""

import argparse
import json
import time
from pathlib import Path

import torch

from diffusion_v2.lgt import make_action, run_hmc_ensemble, block_links
from diffusion_v2.lgt.blocking import approx_matched_coarse_beta
from diffusion_v2.lgt.hmc import adapted_hmc_params
from diffusion_v2.model.likelihood import conditional_log_likelihood, importance_ess
from diffusion_v2.model.schedule import GeometricNoiseSchedule
from diffusion_v2.model.train import load_checkpoint
from diffusion_v2.pipeline.ladder import generate_fine_from_coarse
from diffusion_v2.utils import load_config, resolve_device, set_seed, save_json


def run_case(model, schedule, case, args, action_type, device):
    fine_L, fine_beta = case
    coarse_L = fine_L // 2
    coarse_beta = approx_matched_coarse_beta(fine_beta)
    step_size, n_steps = adapted_hmc_params(coarse_beta, 0.2, 5)
    burn_in = 200 if coarse_beta < 5 else (2000 if coarse_beta >= 20 else 600)
    t0 = time.time()
    coarse, _ = run_hmc_ensemble(
        coarse_L, make_action(action_type, coarse_beta),
        n_configs=args.n_configs, n_chains=16, burn_in=burn_in, thin=5,
        n_steps=n_steps, step_size=step_size, device=device,
        topological_updates=True, hot_start=coarse_beta < 5,
    )
    t_hmc = time.time() - t0
    t0 = time.time()
    fine = generate_fine_from_coarse(
        model, schedule, coarse, fine_beta,
        n_sampler_steps=args.n_sampler_steps, batch_size=args.batch_size, device=device,
        consistency_weight=args.consistency_weight,
        enforce_coarse_charge=False,
        physics_blend_coef=args.physics_blend,
        physics_blend_beta_min=args.physics_blend_beta_min,
    )
    t_gen = time.time() - t0
    t0 = time.time()
    log_q = conditional_log_likelihood(
        model, schedule, coarse, fine, fine_beta,
        n_steps=args.ode_steps, n_probes=args.n_probes,
        consistency_weight=args.consistency_weight,
        physics_blend_coef=args.physics_blend,
        physics_blend_beta_min=args.physics_blend_beta_min,
        batch_size=args.batch_size, device=device, seed=args.seed,
    )
    t_ode = time.time() - t0
    diag = importance_ess(fine, log_q, fine_beta, action_type)
    diag.update({
        "fine_L": fine_L, "fine_beta": fine_beta,
        "coarse_L": coarse_L, "coarse_beta": coarse_beta,
        "seconds_hmc_base": round(t_hmc, 1),
        "seconds_generate": round(t_gen, 1),
        "seconds_ode": round(t_ode, 1),
    })
    return diag


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="diffusion_v2/configs/v2.yaml")
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--cases", nargs="+", default=["16:14.1464", "16:55.0237", "32:55.0237"],
                        help="fine_L:fine_beta per case")
    parser.add_argument("--n-configs", type=int, default=64)
    parser.add_argument("--ode-steps", type=int, default=60)
    parser.add_argument("--n-probes", type=int, default=1)
    parser.add_argument("--n-sampler-steps", type=int, default=200)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--seed", type=int, default=20260730)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    config = load_config(args.config)
    set_seed(args.seed)
    device = resolve_device(config)
    action_type = config["action_type"]
    ladder_cfg = config.get("ladder", {})
    args.consistency_weight = float(ladder_cfg.get("consistency_weight", 1.0))
    args.physics_blend = float(ladder_cfg.get("physics_blend_coef", 0.0))
    args.physics_blend_beta_min = float(ladder_cfg.get("physics_blend_beta_min", 0.0))

    checkpoint = args.checkpoint or config["train"]["checkpoint"]
    model, schedule = load_checkpoint(checkpoint, device)
    coef = ladder_cfg.get("sigma_min_beta_coef")
    if coef is not None:
        schedule = GeometricNoiseSchedule(
            schedule.sigma_min, schedule.sigma_max, sigma_min_beta_coef=float(coef)
        )

    out_dir = Path(args.out or (Path(config["validate"]["out_dir"]).parent / "model_ess"))
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for spec in args.cases:
        L, beta = spec.split(":")
        case = (int(L), float(beta))
        print(f"case L={case[0]} beta={case[1]} ...")
        diag = run_case(model, schedule, case, args, action_type, device)
        keep = {k: v for k, v in diag.items() if k != "log_weights"}
        print("  " + json.dumps(keep))
        results.append(diag)
        save_json(out_dir / "ess_results.json", results)

    lines = ["# Model ESS via probability-flow ODE likelihood", "",
             "| L | beta_f | ESS/N | log-w std | n | gen s | ODE s |",
             "|---|--------|-------|-----------|---|-------|-------|"]
    for r in results:
        lines.append(
            f"| {r['fine_L']} | {r['fine_beta']:g} | {r['ess_per_n']:.3f} | "
            f"{r['log_weight_std']:.2f} | {r['n']} | {r['seconds_generate']} | {r['seconds_ode']} |"
        )
    lines += ["", "Raw model transport (no charge enforcement, no retherm); weights",
              "w = exp(-S)/q(fine|coarse), self-normalized. Reference: Q-shift flows",
              "report ESS/N ~ 0.5-0.7 flat in volume (Lattice 2026)."]
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_dir / 'report.md'}")


if __name__ == "__main__":
    main()
