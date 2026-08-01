"""Exact-in-principle observables via ODE sampling + reweighting / independence M-H.

Unlike 15_model_ess.py (stochastic sampler, flow density as diagnostic), this
script samples the probability-flow ODE itself, so each fine config comes with
the exact density of the process that produced it (up to Heun discretization
and Hutchinson probe noise). The resulting weights
    log w = -S_f(x) + S_matched(c) - log q(x | c)
are valid SNIS weights against the fine Wilson target with the coarse HMC base
as part of the proposal, and feed two asymptotically exact estimators:

  * self-normalized reweighted observables (with linearized errors), and
  * an independence-Metropolis chain over the proposal ensemble.

This is the "M-H or reweighting" exactness route the diffusion-for-LGT
literature flags as missing. No charge projection and no retherm are applied
(both are non-diffeomorphic / density-breaking); topological-sector errors are
paid for through the weights instead.

    python diffusion_v2/scripts/19_ode_reweighting.py --config diffusion_v2/configs/v2.yaml \
        --cases 16:14.1464 16:55.0237 32:55.0237 --n-configs 64
"""

import argparse
import json
import time
from pathlib import Path

import torch

from diffusion_v2.lgt import make_action, run_hmc_ensemble
from diffusion_v2.lgt.blocking import approx_matched_coarse_beta
from diffusion_v2.lgt.hmc import adapted_hmc_params
from diffusion_v2.lgt.lattice import plaquette_angles, topological_charge
from diffusion_v2.model.likelihood import (
    conditional_ode_sample,
    importance_ess,
    independence_metropolis,
    reweighted_mean,
    snis_log_weights,
)
from diffusion_v2.model.schedule import GeometricNoiseSchedule
from diffusion_v2.model.train import load_checkpoint
from diffusion_v2.utils import load_config, resolve_device, set_seed, save_json


def per_config_observables(configs: torch.Tensor) -> dict[str, torch.Tensor]:
    with torch.no_grad():
        plaq = torch.cos(plaquette_angles(configs.float())).mean(dim=(-2, -1))
        q = topological_charge(configs.float())
    return {"plaquette": plaq, "Q": q, "Q^2": q**2}


def unweighted_mean(values: torch.Tensor) -> tuple[float, float]:
    n = values.numel()
    return float(values.mean()), float(values.std() / max(n, 2) ** 0.5)


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
    fine, log_q = conditional_ode_sample(
        model, schedule, coarse, fine_beta,
        n_steps=args.ode_steps, n_probes=args.n_probes,
        consistency_weight=args.consistency_weight,
        physics_blend_coef=args.physics_blend,
        physics_blend_beta_min=args.physics_blend_beta_min,
        batch_size=args.batch_size, device=device, seed=args.seed,
    )
    t_ode = time.time() - t0

    log_w = snis_log_weights(fine, log_q, fine_beta, action_type,
                             coarse=coarse, coarse_beta_matched=coarse_beta)
    diag = importance_ess(fine, log_q, fine_beta, action_type,
                          coarse=coarse, coarse_beta_matched=coarse_beta)
    diag.pop("log_weights", None)
    imh_idx, imh_accept = independence_metropolis(log_w, seed=args.seed)

    obs = per_config_observables(fine)
    obs_out = {}
    for name, values in obs.items():
        raw_mu, raw_err = unweighted_mean(values)
        rw_mu, rw_err = reweighted_mean(values, log_w)
        imh_mu, imh_err = unweighted_mean(values[imh_idx])
        obs_out[name] = {
            "raw": [raw_mu, raw_err],
            "reweighted": [rw_mu, rw_err],
            "imh": [imh_mu, imh_err],
        }

    if args.hmc_ref:
        f_step, f_nsteps = adapted_hmc_params(fine_beta, 0.2, 5)
        f_burn = 200 if fine_beta < 5 else (2000 if fine_beta >= 20 else 600)
        t0 = time.time()
        ref, _ = run_hmc_ensemble(
            fine_L, make_action(action_type, fine_beta),
            n_configs=args.n_configs, n_chains=16, burn_in=f_burn, thin=5,
            n_steps=f_nsteps, step_size=f_step, device=device,
            topological_updates=True, hot_start=fine_beta < 5,
        )
        t_ref = time.time() - t0
        for name, values in per_config_observables(ref).items():
            obs_out[name]["hmc_ref"] = list(unweighted_mean(values))
        diag["seconds_hmc_ref"] = round(t_ref, 1)

    diag.update({
        "fine_L": fine_L, "fine_beta": fine_beta,
        "coarse_L": coarse_L, "coarse_beta": coarse_beta,
        "imh_acceptance": imh_accept,
        "observables": obs_out,
        "seconds_hmc_base": round(t_hmc, 1),
        "seconds_ode_sample": round(t_ode, 1),
        "ode_steps": args.ode_steps, "n_probes": args.n_probes,
    })
    return diag


def format_report(results: list[dict]) -> str:
    lines = [
        "# Reweighted observables via probability-flow ODE sampling",
        "",
        "| L | beta_f | ESS/N (fiber) | i-MH acc | obs | raw | reweighted | i-MH | HMC ref |",
        "|---|--------|---------------|----------|-----|-----|------------|------|---------|",
    ]
    for r in results:
        fib = r.get("ess_per_n_fiber")
        fib_s = f"{fib:.3f}" if fib is not None else "--"
        first = True
        for name, o in r["observables"].items():
            def fmt(pair):
                return f"{pair[0]:.5g} ({pair[1]:.2g})" if pair else "--"
            head = (f"| {r['fine_L']} | {r['fine_beta']:g} | {fib_s} | "
                    f"{r['imh_acceptance']:.2f} " if first else "| | | | ")
            lines.append(
                head + f"| {name} | {fmt(o['raw'])} | {fmt(o['reweighted'])} | "
                f"{fmt(o['imh'])} | {fmt(o.get('hmc_ref'))} |"
            )
            first = False
    lines += [
        "",
        "Samples drawn from the probability-flow ODE (no charge projection, no",
        "retherm); log q is the density of the ACTUAL samples, so the SNIS and",
        "independence-Metropolis columns are asymptotically exact estimators of",
        "the fine Wilson target. Errors: raw/i-MH naive sem (i-MH ignores chain",
        "autocorrelation), reweighted linearized SNIS error. Low ESS/N or i-MH",
        "acceptance means the exact estimators are noisy, not biased -- raw",
        "columns stay the (biased) high-precision numbers.",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="diffusion_v2/configs/v2.yaml")
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--cases", nargs="+", default=["16:14.1464", "16:55.0237", "32:55.0237"],
                        help="fine_L:fine_beta per case")
    parser.add_argument("--n-configs", type=int, default=64)
    parser.add_argument("--ode-steps", type=int, default=120)
    parser.add_argument("--n-probes", type=int, default=2,
                        help="Hutchinson probes per divergence eval; 0 = exact "
                        "divergence (one vjp per link, small lattices only)")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--seed", type=int, default=20260801)
    parser.add_argument("--hmc-ref", action="store_true",
                        help="also run direct fine-level HMC as reference "
                        "(slow and topologically unreliable at large beta)")
    parser.add_argument("--out", default=None)
    parser.add_argument("--consistency-weight", type=float, default=None,
                        dest="consistency_override")
    args = parser.parse_args()
    config = load_config(args.config)
    set_seed(args.seed)
    device = resolve_device(config)
    action_type = config["action_type"]
    ladder_cfg = config.get("ladder", {})
    args.consistency_weight = (
        args.consistency_override if args.consistency_override is not None
        else float(ladder_cfg.get("consistency_weight", 1.0))
    )
    args.physics_blend = float(ladder_cfg.get("physics_blend_coef", 0.0))
    args.physics_blend_beta_min = float(ladder_cfg.get("physics_blend_beta_min", 0.0))

    checkpoint = args.checkpoint or config["train"]["checkpoint"]
    model, schedule = load_checkpoint(checkpoint, device)
    coef = ladder_cfg.get("sigma_min_beta_coef")
    if coef is not None:
        schedule = GeometricNoiseSchedule(
            schedule.sigma_min, schedule.sigma_max, sigma_min_beta_coef=float(coef)
        )

    out_dir = Path(args.out or (Path(config["validate"]["out_dir"]).parent / "ode_reweighting"))
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for spec in args.cases:
        L, beta = spec.split(":")
        case = (int(L), float(beta))
        print(f"case L={case[0]} beta={case[1]} ...")
        diag = run_case(model, schedule, case, args, action_type, device)
        keep = {k: v for k, v in diag.items() if k != "observables"}
        print("  " + json.dumps(keep))
        results.append(diag)
        save_json(out_dir / "reweighting_results.json", results)

    (out_dir / "report.md").write_text(format_report(results), encoding="utf-8")
    print(f"wrote {out_dir / 'report.md'}")


if __name__ == "__main__":
    main()
