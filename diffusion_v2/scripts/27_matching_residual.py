"""Matching residual vs model error: decompose the fiber log-weight spread.

The fiber weight decomposes as log w = f(c) + e(x, c) + const, where a c-only
term f(c) -- the Wilson-family projection residual of the true blocked action
-- CANNOT be removed by any fine-score fine-tune. This script measures how much
of the observed spread is c-only:

  1. Regression probe: regress unshifted fiber log-weights on coarse
     observables (plaquette characters, rectangles, topology). The explained
     variance R^2_c bounds the matching-residual-like floor FROM ABOVE a
     c-dependent model error also lands here; an honest upper bound).
  2. Fine-side regression: regress log q + S_f on the differentiable
     bridge-feature basis (model/ais.py) -- the surrogate quality that sets the
     floor of the AIS correction (script 28). Reported per-site.
  3. Villain control (--action-type villain): beta/4 coarse matching is EXACT
     for the Villain action, so the Villain fiber spread is pure model error;
     Wilson minus Villain isolates the matching floor by construction.

Control-protocol note: the Villain arm cannot use the physics blend (it
injects the WILSON exact score), so for a clean subtraction BOTH arms run
blend-free -- and blend-free sampling must stay at the TRAINED sigma floor
(--sigma-min-coef 0.3): below it the network extrapolates into sigmas it never
saw and the spread measures that artifact, not the model (audit section 4.3;
in deployment the blend covers that region). The deployment-settings
decomposition (blend on, sigmin 0.03) comes from script 28's samples instead.

    python diffusion_v2/scripts/27_matching_residual.py --sigma-min-coef 0.3 \
        --cases 16:14.1464 16:55.0237 32:55.0237
    python diffusion_v2/scripts/27_matching_residual.py --sigma-min-coef 0.3 \
        --action-type villain --cases 16:14.1464 16:55.0237 32:55.0237
"""

import argparse
import json
import time
from pathlib import Path

import torch

from diffusion_v2.lgt import make_action, run_hmc_ensemble
from diffusion_v2.lgt.blocking import approx_matched_coarse_beta
from diffusion_v2.lgt.hmc import adapted_hmc_params
from diffusion_v2.model.ais import (
    COARSE_FEATURE_NAMES,
    bridge_features,
    coarse_only_features,
    fit_surrogate_cv,
)
from diffusion_v2.model.likelihood import (
    _ess_from_log_weights,
    conditional_ode_sample,
    free_energy_certificate,
    snis_log_weights,
)
from diffusion_v2.model.schedule import GeometricNoiseSchedule
from diffusion_v2.model.train import load_checkpoint
from diffusion_v2.utils import load_config, resolve_device, save_json, set_seed

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
    fine, log_q = conditional_ode_sample(
        model, schedule, coarse, fine_beta,
        n_steps=args.ode_steps, n_probes=args.n_probes,
        consistency_weight=args.consistency_weight,
        physics_blend_coef=args.physics_blend,
        batch_size=args.batch_size, device=device, seed=args.seed,
    )
    log_w = snis_log_weights(fine, log_q, fine_beta, action_type,
                             coarse=coarse, coarse_beta_matched=coarse_beta)
    ess, std, _ = _ess_from_log_weights(log_w)

    n_sites = 2 * fine_L * fine_L
    coarse_fit = fit_surrogate_cv(coarse_only_features(coarse), log_w)
    coarse_fit.pop("g")
    with torch.no_grad():
        action_f = make_action(action_type, float(fine_beta))
        fine_target = log_q.double() + action_f.per_config(fine.float()).cpu().double()
        fine_fit = fit_surrogate_cv(
            bridge_features(fine.float(), coarse_beta, action_type), fine_target.float()
        )
    fine_fit.pop("g")

    return {
        "fine_L": fine_L, "fine_beta": fine_beta,
        "coarse_L": coarse_L, "coarse_beta": coarse_beta,
        "action_type": action_type,
        "n": int(log_w.numel()),
        "ess_per_n_fiber": ess,
        "log_weight_std_fiber": std,
        "per_site_std": std / n_sites,
        "coarse_regression": {
            "r2": coarse_fit["r2"],
            "explained_std": (coarse_fit["r2"] ** 0.5) * std if coarse_fit["r2"] > 0 else 0.0,
            "residual_std": coarse_fit["resid_std"],
            "cv_residual_std": coarse_fit["cv_resid_std"],
            "ridge": coarse_fit["ridge"],
            "std_coefficients": {n: c for n, c in zip(
                COARSE_FEATURE_NAMES, coarse_fit["std_coefficients"].values())},
        },
        "fine_surrogate_regression": {
            "r2": fine_fit["r2"],
            "target_std": fine_fit["target_std"],
            "residual_std": fine_fit["resid_std"],
            "cv_residual_std": fine_fit["cv_resid_std"],
            "residual_std_per_site": fine_fit["cv_resid_std"] / n_sites,
            "ridge": fine_fit["ridge"],
            "std_coefficients": fine_fit["std_coefficients"],
        },
        "free_energy_certificate": free_energy_certificate(
            log_w, fine_L, fine_beta, coarse_beta, action_type
        ),
        "seconds": round(time.time() - t0, 1),
    }


def format_report(results: list[dict]) -> str:
    lines = [
        "# Matching residual vs model error",
        "",
        "R^2_c = fiber log-weight variance explained by COARSE-only observables",
        "(upper bound on the matching-residual floor: c-dependent model error",
        "lands here too). R^2_x = variance of [log q + S_f] explained by the",
        "differentiable fine-feature surrogate -- the floor of the AIS bridge",
        "(script 28). For `villain`, coarse matching is exact, so its fiber",
        "spread is pure model error; Wilson minus Villain at matched cases",
        "isolates the matching floor.",
        "",
        "| action | L | beta_f | log-w std | /site | R^2_c | c-explained std | "
        "R^2_x | surrogate resid std | resid /site | dF gap (sem) |",
        "|--------|---|--------|-----------|-------|-------|-----------------|"
        "-------|---------------------|-------------|--------------|",
    ]
    for r in results:
        c, f, cert = r["coarse_regression"], r["fine_surrogate_regression"], r["free_energy_certificate"]
        lines.append(
            f"| {r['action_type']} | {r['fine_L']} | {r['fine_beta']:g} "
            f"| {r['log_weight_std_fiber']:.1f} | {r['per_site_std']:.4f} "
            f"| {c['r2']:.3f} | {c['explained_std']:.1f} "
            f"| {f['r2']:.3f} | {f['residual_std']:.2f} | {f['residual_std_per_site']:.4f} "
            f"| {cert['gap']:+.1f} ({cert['sem']:.1f}) |"
        )
    lines += [
        "",
        "Standardized coefficients (nats of log-weight std absorbed per feature):",
        "",
    ]
    for r in results:
        lines.append(f"* {r['action_type']} {r['fine_L']}:{r['fine_beta']:g} "
                     f"coarse: {json.dumps({k: round(v, 2) for k, v in r['coarse_regression']['std_coefficients'].items()})}")
        lines.append(f"  fine surrogate: "
                     f"{json.dumps({k: round(v, 2) for k, v in r['fine_surrogate_regression']['std_coefficients'].items()})}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="diffusion_v2/configs/v2.yaml")
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--cases", nargs="+", default=["16:14.1464", "16:55.0237", "32:55.0237"])
    parser.add_argument("--n-configs", type=int, default=64)
    parser.add_argument("--ode-steps", type=int, default=120)
    parser.add_argument("--n-probes", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--seed", type=int, default=20260802)
    parser.add_argument("--sigma-min-coef", type=float, default=0.03)
    parser.add_argument("--action-type", default=None,
                        help="villain = exact-matching control (pure model error)")
    parser.add_argument("--physics-blend", type=float, default=0.0,
                        help="keep 0 in BOTH arms for a clean Wilson-vs-Villain "
                        "comparison (the blend injects the Wilson exact score)")
    parser.add_argument("--consistency-weight", type=float, default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    set_seed(args.seed)
    device = resolve_device(config)
    action_type = args.action_type or config["action_type"]
    ladder_cfg = config.get("ladder", {})
    if args.consistency_weight is None:
        args.consistency_weight = float(ladder_cfg.get("consistency_weight", 1.0))

    checkpoint = args.checkpoint or config["train"]["checkpoint"]
    model, schedule = load_checkpoint(checkpoint, device)
    schedule = GeometricNoiseSchedule(
        schedule.sigma_min, schedule.sigma_max, sigma_min_beta_coef=args.sigma_min_coef
    )

    out_dir = Path(args.out or f"out/diffusion_v2/matching_residual/{action_type}")
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for spec in args.cases:
        L, beta = spec.split(":")
        case = (int(L), float(beta))
        print(f"case {action_type} L={case[0]} beta={case[1]} ...", flush=True)
        r = run_case(model, schedule, case, args, action_type, device)
        print("  " + json.dumps({k: r[k] for k in
                                 ("log_weight_std_fiber", "per_site_std", "seconds")}
                                | {"r2_c": r["coarse_regression"]["r2"],
                                   "r2_x": r["fine_surrogate_regression"]["r2"]}), flush=True)
        results.append(r)
        save_json(out_dir / "results.json", results)

    (out_dir / "report.md").write_text(format_report(results), encoding="utf-8")
    print(f"wrote {out_dir / 'report.md'}", flush=True)


if __name__ == "__main__":
    main()
