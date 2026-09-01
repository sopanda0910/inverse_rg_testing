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

    python u1_2d/scripts/19_ode_reweighting.py --config u1_2d/configs/v2.yaml \
        --cases 16:14.1464 16:55.0237 32:55.0237 --n-configs 64
"""

import argparse
import json
import math
import time
from pathlib import Path

import torch

from u1_2d.lgt import make_action, run_hmc_ensemble
from u1_2d.lgt.blocking import approx_matched_coarse_beta
from u1_2d.lgt.exact import plaquette_exact, topological_susceptibility_exact
from u1_2d.lgt.hmc import adapted_hmc_params
from u1_2d.lgt.lattice import plaquette_angles, topological_charge
from u1_2d.model.likelihood import (
    conditional_ode_sample,
    free_energy_certificate,
    importance_ess,
    independence_metropolis,
    reweighted_mean,
    snis_log_weights,
)
from u1_2d.model.schedule import GeometricNoiseSchedule
from u1_2d.model.train import load_checkpoint
from u1_2d.utils import load_config, resolve_device, set_seed, save_json
from u1_2d.validate.stats import integrated_autocorrelation_time


def per_config_observables(configs: torch.Tensor) -> dict[str, torch.Tensor]:
    with torch.no_grad():
        plaq = torch.cos(plaquette_angles(configs.float())).mean(dim=(-2, -1))
        q = topological_charge(configs.float())
    return {"plaquette": plaq, "Q": q, "Q^2": q**2}


def unweighted_mean(values: torch.Tensor) -> tuple[float, float]:
    n = values.numel()
    return float(values.mean()), float(values.std() / max(n, 2) ** 0.5)


def chain_aware_mean(values: torch.Tensor, n_chains: int) -> tuple[float, float]:
    """Mean and tau_int-corrected sem for an HMC ensemble ordered chain-major
    per draw (run_hmc_ensemble contract). With fewer than 8 draws per chain the
    windowed tau_int is unusable; fall back to the naive sem, which is then a
    LOWER BOUND wherever thinning does not decorrelate (topology at high beta)."""
    n_draws = values.numel() // n_chains
    mu = float(values.mean())
    if n_draws < 8:
        return mu, float(values.std() / max(values.numel(), 2) ** 0.5)
    per_chain = values[: n_draws * n_chains].reshape(n_draws, n_chains).cpu().numpy()
    taus = [integrated_autocorrelation_time(per_chain[:, c])[0] for c in range(n_chains)]
    tau = max(sum(taus) / len(taus), 0.5)
    n_eff = max(values.numel() / (2.0 * tau), 2.0)
    return mu, float(values.std() / n_eff**0.5)


def run_case(model, schedule, case, args, action_type, device):
    fine_L, fine_beta = case
    coarse_L = fine_L // 2
    # Pass action_type: the default is "wilson", which would silently mismatch
    # the coarse coupling under --action-type villain (see scripts/27).
    coarse_beta = approx_matched_coarse_beta(fine_beta, action_type)
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
    # Free-energy certificate: log E[w] vs the exact character-expansion
    # Delta F. Valid because the coarse base IS HMC at the same matched
    # coupling that enters the weights. Unshifted weights required.
    diag["free_energy_certificate"] = free_energy_certificate(
        log_w, fine_L, fine_beta, coarse_beta, action_type
    )
    imh_idx, imh_accept = independence_metropolis(log_w, seed=args.seed)

    obs = per_config_observables(fine)
    # Repeated i-MH states autocorrelate the chain: with acceptance a the
    # naive sem understates by ~sqrt((2 - a) / a) (n_eff = n a / (2 - a)).
    acc_floor = max(imh_accept, 1.0 / max(len(log_w), 2))
    imh_err_factor = ((2.0 - acc_floor) / acc_floor) ** 0.5
    obs_out = {}
    for name, values in obs.items():
        raw_mu, raw_err = unweighted_mean(values)
        rw_mu, rw_err = reweighted_mean(values, log_w)
        imh_mu, imh_err = unweighted_mean(values[imh_idx])
        imh_err *= imh_err_factor
        obs_out[name] = {
            "raw": [raw_mu, raw_err],
            "reweighted": [rw_mu, rw_err],
            "imh": [imh_mu, imh_err],
        }

    if args.exact_ref:
        refs = {
            "plaquette": plaquette_exact(fine_beta, action_type, fine_L),
            "Q^2": topological_susceptibility_exact(fine_beta, action_type, fine_L) * fine_L**2,
            "Q": 0.0,
        }
        # With degenerate weights the linearized SNIS error collapses and its
        # z-score becomes noise dressed as precision; suppress weighted-column
        # z-scores below a minimal effective count.
        ess_count = diag.get("ess_per_n_fiber", 0.0) * log_w.numel()
        for name, o in obs_out.items():
            ex = refs.get(name)
            if ex is None:
                continue
            o["exact"] = ex
            for est in ("raw", "reweighted", "imh"):
                mu, err = o[est]
                z = (mu - ex) / err if err > 0 else float("nan")
                if est in ("reweighted", "imh") and ess_count < 4.0:
                    z = float("nan")
                o[f"z_{est}"] = z

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
            obs_out[name]["hmc_ref"] = list(chain_aware_mean(values, 16))
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
    has_exact = any("exact" in o for r in results for o in r["observables"].values())
    ref_head = "exact | z(raw) | z(rw)" if has_exact else "HMC ref"
    lines = [
        "# Reweighted observables via probability-flow ODE sampling",
        "",
        f"| L | beta_f | ESS/N (fiber) | i-MH acc | obs | raw | reweighted | i-MH | {ref_head} |",
        "|---|--------|---------------|----------|-----|-----|------------|------|---------|"
        + ("--|--|" if has_exact else ""),
    ]
    for r in results:
        fib = r.get("ess_per_n_fiber")
        fib_s = f"{fib:.3f}" if fib is not None else "--"
        first = True
        for name, o in r["observables"].items():
            def fmt(pair):
                return f"{pair[0]:.5g} ({pair[1]:.2g})" if pair else "--"
            def fmtz(key):
                z = o.get(key)
                return f"{z:+.1f}" if z is not None and math.isfinite(z) else "--"
            head = (f"| {r['fine_L']} | {r['fine_beta']:g} | {fib_s} | "
                    f"{r['imh_acceptance']:.2f} " if first else "| | | | ")
            if has_exact:
                ex = o.get("exact")
                ref_cells = (f"{ex:.5g} | {fmtz('z_raw')} | {fmtz('z_reweighted')}"
                             if ex is not None else "-- | -- | --")
            else:
                ref_cells = fmt(o.get("hmc_ref"))
            lines.append(
                head + f"| {name} | {fmt(o['raw'])} | {fmt(o['reweighted'])} | "
                f"{fmt(o['imh'])} | {ref_cells} |"
            )
            first = False
    lines += [
        "",
        "Samples drawn from the probability-flow ODE (no charge projection, no",
        "retherm); log q is the density of the ACTUAL samples, so the SNIS and",
        "independence-Metropolis columns are exact estimators of the fine Wilson",
        "target in the n_steps -> inf, exact-divergence limit. At finite",
        "settings two residual biases remain (they shrink with steps/probes,",
        "NOT with more samples): the Heun trapezoid approximates the discrete",
        "map's true log-Jacobian, and Hutchinson noise is unbiased in log q but",
        "biases the exponentiated weights (Jensen). Check stability under",
        "doubled --ode-steps and increased --n-probes (or --n-probes 0) before",
        "quoting. Errors: raw naive sem; i-MH sem inflated by the",
        "low-acceptance autocorrelation factor sqrt((2-a)/a); reweighted",
        "linearized SNIS error. Low ESS/N or i-MH acceptance makes the exact",
        "estimators noisy -- raw columns stay the (biased) high-precision",
        "numbers.",
    ]
    if any("free_energy_certificate" in r for r in results):
        lines += [
            "",
            "## Free-energy certificate",
            "",
            "log E[w] vs the exact character-expansion Delta F",
            "(2 L_f^2 log 2pi + log Z_f - log Z_c). An independent end-to-end",
            "check of the weight chain against the solvable theory; heavy",
            "tails bias the estimate LOW (rare dominant weights undersampled),",
            "so agreement within a few sem certifies, disagreement of tens of",
            "nats quantifies the same density gap the ESS sees.",
            "",
            "| L | beta_f | log mean w | exact dF | gap | sem |",
            "|---|--------|------------|----------|-----|-----|",
        ]
        for r in results:
            c = r.get("free_energy_certificate")
            if c:
                lines.append(f"| {r['fine_L']} | {r['fine_beta']:g} | "
                             f"{c['log_mean_w']:.2f} | {c['exact_delta_F']:.2f} | "
                             f"{c['gap']:+.2f} | {c['sem']:.2f} |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="u1_2d/configs/v2.yaml")
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--correction", default=None,
                        help="path to a score-correction file (see script 25); "
                        "loads its stored base checkpoint and overrides --checkpoint")
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
    parser.add_argument("--exact-ref", action="store_true",
                        help="add exact character-expansion references "
                        "(finite-volume plaquette, <Q^2>, <Q>=0) and z-scores "
                        "for every estimator")
    parser.add_argument("--out", default=None)
    parser.add_argument("--action-type", default=None,
                        help="override config action_type. `villain` is the "
                        "matching-residual control: beta/4 coarse matching is "
                        "EXACT for the Villain action (lgt/blocking.py), so "
                        "the fiber log-weight spread there is pure model "
                        "error; Wilson minus Villain isolates the matching "
                        "floor")
    parser.add_argument("--consistency-weight", type=float, default=None,
                        dest="consistency_override")
    parser.add_argument("--physics-blend", type=float, default=None,
                        dest="physics_blend_override",
                        help="override ladder.physics_blend_coef")
    parser.add_argument("--physics-blend-beta-min", type=float, default=None,
                        dest="physics_blend_beta_min_override",
                        help="override ladder.physics_blend_beta_min")
    parser.add_argument("--sigma-min-coef", type=float, default=0.03,
                        help="terminal sigma_min(beta) = coef / sqrt(beta). "
                        "Lower = the ODE integrates closer to sigma=0, "
                        "shrinking the endgame offset between the sampled "
                        "(noised) and target density. Default 0.03 is the "
                        "2026-08-01 sweep winner (ladder default 0.1 gave "
                        "log-w std 42 vs 24 at L=16 beta=55); pass the ladder "
                        "value explicitly to reproduce pre-sweep numbers")
    args = parser.parse_args()
    config = load_config(args.config)
    set_seed(args.seed)
    device = resolve_device(config)
    action_type = args.action_type or config["action_type"]
    ladder_cfg = config.get("ladder", {})
    args.consistency_weight = (
        args.consistency_override if args.consistency_override is not None
        else float(ladder_cfg.get("consistency_weight", 1.0))
    )
    args.physics_blend = (
        args.physics_blend_override if args.physics_blend_override is not None
        else float(ladder_cfg.get("physics_blend_coef", 0.0))
    )
    args.physics_blend_beta_min = (
        args.physics_blend_beta_min_override
        if args.physics_blend_beta_min_override is not None
        else float(ladder_cfg.get("physics_blend_beta_min", 0.0))
    )
    if action_type == "villain" and args.physics_blend > 0:
        print("villain control: the physics blend injects the WILSON exact score; "
              "disabling it. Run the Wilson arm with --physics-blend 0 too for a "
              "clean matching-floor comparison.")
        args.physics_blend = 0.0

    if args.correction:
        from u1_2d.model.score_correction import load_corrected_checkpoint

        model, schedule = load_corrected_checkpoint(args.correction, device)
    else:
        checkpoint = args.checkpoint or config["train"]["checkpoint"]
        model, schedule = load_checkpoint(checkpoint, device)
    coef = (args.sigma_min_coef if args.sigma_min_coef is not None
            else ladder_cfg.get("sigma_min_beta_coef"))
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
