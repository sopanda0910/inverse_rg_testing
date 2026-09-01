"""AIS-corrected transport: anneal ODE samples into the exact target.

The one mechanism the ESS program never tried (audit section 6.1): instead of
making the model's density gap smaller (five converged negatives), split the
gap into many small importance-sampling increments paid along a tractable
surrogate bridge, with exact HMC + instanton-hop transitions relaxing the
samples between increments. Machinery in u1_2d/model/ais.py; validity
is standard AIS with a known-density initial proposal.

Honesty protocol:
  * split fit -- surrogate coefficients fit on the even-index half, headline
    ESS quoted on the held-out odd half (in-sample numbers reported alongside);
  * exact-reference z-scores with the same degenerate-weight suppression as
    script 19 (ess_count < 4);
  * free-energy certificate: for AIS weights E[w] = (2 pi)^{2 L^2}
    Z_haar(beta_f, L) exactly -- checked per case;
  * expectation set by the audit: wins at moderate beta; topological-sector
    mismatch must anneal through the bridge's Q-hops and is expected to remain
    the failure mode at large beta * V.

    python u1_2d/scripts/28_ais_transport.py --cases 16:14.1464 16:55.0237 32:55.0237
"""

import argparse
import json
import math
import time
from pathlib import Path

import torch

from u1_2d.lgt import make_action, run_hmc_ensemble
from u1_2d.lgt.blocking import approx_matched_coarse_beta
from u1_2d.lgt.exact import (
    log_partition,
    plaquette_exact,
    topological_charge_distribution,
    topological_susceptibility_exact,
)
from u1_2d.lgt.hmc import adapted_hmc_params
from u1_2d.lgt.lattice import plaquette_angles, topological_charge
from u1_2d.model.ais import (
    BASIS_FEATURE_NAMES,
    COARSE_FEATURE_NAMES,
    ais_correct,
    bridge_features,
    coarse_only_features,
    fit_surrogate_cv,
    sector_resolved_estimate,
)
from u1_2d.model.likelihood import (
    _ess_from_log_weights,
    conditional_ode_sample,
    reweighted_mean,
    snis_log_weights,
)
from u1_2d.model.schedule import GeometricNoiseSchedule
from u1_2d.model.train import load_checkpoint
from u1_2d.utils import load_config, resolve_device, save_json, set_seed


def per_config_observables(configs: torch.Tensor) -> dict[str, torch.Tensor]:
    with torch.no_grad():
        plaq = torch.cos(plaquette_angles(configs.float())).mean(dim=(-2, -1))
        q = topological_charge(configs.float())
    return {"plaquette": plaq, "Q": q, "Q^2": q**2}


def ais_certificate(log_w: torch.Tensor, fine_L: int, fine_beta: float,
                    action_type: str) -> dict:
    """For AIS weights E[w] = (2 pi)^{2 L^2} Z_haar(beta_f, L): the coarse level
    integrates out exactly (module docstring), so no coarse Z appears."""
    lw = log_w.double()
    m = lw.max()
    w = torch.exp(lw - m)
    est = float(m + torch.log(w.mean()))
    sem = float(w.std() / (math.sqrt(w.numel()) * w.mean()))
    exact = 2 * fine_L * fine_L * math.log(2.0 * math.pi) + log_partition(
        fine_beta, fine_L, action_type
    )
    kl = float(exact - lw.mean())
    return {"log_mean_w": est, "exact_delta_F": exact, "gap": est - exact,
            "sem": sem, "n": int(w.numel()),
            "kl_from_mean_log_w": kl,
            "kl_sem": float(lw.std() / math.sqrt(w.numel())),
            "kl_per_site": kl / (2 * fine_L * fine_L)}


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
    # run_hmc_ensemble is the one function that returns on its `device`; every
    # consumer below (snis_log_weights, coarse_only_features, the bridge-feature
    # fits) is CPU-side, matching conditional_ode_sample's CPU return. Without
    # this the case dies as soon as coarse meets fine on cuda.
    coarse = coarse.cpu()
    fine, log_q = conditional_ode_sample(
        model, schedule, coarse, fine_beta,
        n_steps=args.ode_steps, n_probes=args.n_probes,
        consistency_weight=args.consistency_weight,
        physics_blend_coef=args.physics_blend,
        batch_size=args.batch_size, device=device, seed=args.seed,
    )
    t_ode = time.time() - t0

    log_w_fiber = snis_log_weights(fine, log_q, fine_beta, action_type,
                                   coarse=coarse, coarse_beta_matched=coarse_beta)
    ess0, std0, _ = _ess_from_log_weights(log_w_fiber)
    # Deployment-settings matching-residual probe (free from these samples):
    # fiber log-weight variance explained by coarse-only observables. The
    # blend-free controlled version lives in script 27.
    coarse_reg = fit_surrogate_cv(coarse_only_features(coarse), log_w_fiber)

    action_f = make_action(action_type, float(fine_beta))
    with torch.no_grad():
        target = (log_q.double() + action_f.per_config(fine.float()).cpu().double()).float()
        feats = bridge_features(fine.float(), coarse_beta, action_type, args.basis)
    n = fine.shape[0]
    fit_idx = torch.arange(0, n, 2)
    hold_idx = torch.arange(1, n, 2)
    fit = fit_surrogate_cv(feats[fit_idx], target[fit_idx],
                           ridge_floor=args.ridge_floor)
    pred_hold = feats[hold_idx].double() @ fit["g"] + fit["const"]
    fit["resid_std_heldout"] = float((target[hold_idx].double() - pred_hold).std())

    t1 = time.time()
    x_final, log_w_ais, diag = ais_correct(
        fine, log_q, fine_beta, coarse_beta, fit["g"], fit["const"],
        action_type=action_type, basis=args.basis, n_bridge=args.n_bridge,
        n_hmc_per_step=args.n_hmc_per_step, q_hops=not args.no_q_hops,
        seed=args.seed + 7, device=device,
    )
    t_ais = time.time() - t1

    ess_all, std_all, _ = _ess_from_log_weights(log_w_ais)
    ess_hold, std_hold, _ = _ess_from_log_weights(log_w_ais[hold_idx])
    ess_fit, std_fit, _ = _ess_from_log_weights(log_w_ais[fit_idx])

    refs = {
        "plaquette": plaquette_exact(fine_beta, action_type, fine_L),
        "Q^2": topological_susceptibility_exact(fine_beta, action_type, fine_L) * fine_L**2,
        "Q": 0.0,
    }
    ess_count = ess_hold * hold_idx.numel()
    obs_out = {}
    raw_obs = per_config_observables(fine)
    ais_obs = per_config_observables(x_final)
    for name in refs:
        raw_mu = float(raw_obs[name].mean())
        raw_err = float(raw_obs[name].std() / max(n, 2) ** 0.5)
        mu, err = reweighted_mean(ais_obs[name], log_w_ais)
        ex = refs[name]
        obs_out[name] = {
            "raw": [raw_mu, raw_err],
            "ais": [mu, err],
            "exact": ex,
            "z_raw": (raw_mu - ex) / raw_err if raw_err > 0 else float("nan"),
            "z_ais": ((mu - ex) / err if err > 0 and ess_count >= 4.0 else float("nan")),
        }

    # Sector-resolved estimates: within-sector SNIS + exact P(Q). The global
    # weights degenerate on the sector-frequency mismatch (one number per
    # sector); conditioning removes it and P(Q)_exact supplies the masses.
    # E[Q^2] via sectors is exact by construction, so plaquette is the
    # informative row. U(1)-only crutch; labeled as such in the report.
    q_vals, q_probs = topological_charge_distribution(fine_beta, fine_L, action_type)
    sector_out = {}
    for label, obs, lw in (("ais", ais_obs, log_w_ais),
                           ("baseline", raw_obs, log_w_fiber)):
        sec = sector_resolved_estimate(
            obs["plaquette"], lw, obs["Q"], q_vals, q_probs, min_count=6)
        ex = refs["plaquette"]
        sec["exact"] = ex
        sec["z"] = ((sec["mean"] - ex) / sec["err"]
                    if sec.get("err") and sec["err"] > 0 else float("nan"))
        sector_out[label] = sec

    return {
        "fine_L": fine_L, "fine_beta": fine_beta,
        "coarse_L": coarse_L, "coarse_beta": coarse_beta,
        "n": n,
        "baseline": {"ess_per_n_fiber": ess0, "log_weight_std_fiber": std0},
        "coarse_regression": {
            "r2": coarse_reg["r2"], "cv_resid_std": coarse_reg["cv_resid_std"],
            "explained_std": (max(coarse_reg["r2"], 0.0) ** 0.5) * std0,
            "ridge": coarse_reg["ridge"],
            "std_coefficients": {n: c for n, c in zip(
                COARSE_FEATURE_NAMES, coarse_reg["std_coefficients"].values())},
        },
        "surrogate_fit": {
            "r2": fit["r2"], "resid_std": fit["resid_std"],
            "resid_std_heldout": fit["resid_std_heldout"],
            "target_std": fit["target_std"],
            "ridge": fit["ridge"], "cv_resid_std": fit["cv_resid_std"],
            "cv_table": fit["cv_table"],
            "std_coefficients": fit["std_coefficients"],
        },
        "ais": {
            "ess_per_n": ess_all, "log_weight_std": std_all,
            "ess_per_n_heldout": ess_hold, "log_weight_std_heldout": std_hold,
            "ess_per_n_insample": ess_fit, "log_weight_std_insample": std_fit,
            **diag,
        },
        "free_energy_certificate": ais_certificate(log_w_ais, fine_L, fine_beta, action_type),
        "observables": obs_out,
        "sector_resolved_plaquette": sector_out,
        "seconds_ode": round(t_ode, 1), "seconds_ais": round(t_ais, 1),
    }


def format_report(results: list[dict], args) -> str:
    lines = [
        "# AIS-corrected transport",
        "",
        f"basis {args.basis} ({len(BASIS_FEATURE_NAMES[args.basis])} features), "
        f"bridge steps {args.n_bridge}, {args.n_hmc_per_step} HMC updates/step, "
        f"Q-hops {'off' if args.no_q_hops else 'on'}, n = {args.n_configs}, "
        f"split fit (fit even / quote odd)",
        "",
        "| L | beta_f | fiber std (before) | ESS/N before | R^2_c (coarse) | "
        "surrogate R^2 | AIS std (held-out) | AIS ESS/N (held-out) | "
        "AIS ESS/N (all) | HMC acc | dF gap (sem) |",
        "|---|--------|--------------------|--------------|----------------|"
        "---------------|--------------------|----------------------|"
        "-----------------|---------|--------------|",
    ]
    for r in results:
        b, a, f, cert = r["baseline"], r["ais"], r["surrogate_fit"], r["free_energy_certificate"]
        lines.append(
            f"| {r['fine_L']} | {r['fine_beta']:g} "
            f"| {b['log_weight_std_fiber']:.1f} | {b['ess_per_n_fiber']:.4f} "
            f"| {r['coarse_regression']['r2']:.3f} "
            f"| {f['r2']:.3f} "
            f"| {a['log_weight_std_heldout']:.2f} | {a['ess_per_n_heldout']:.3f} "
            f"| {a['ess_per_n']:.3f} "
            f"| {a['hmc_acceptance_mean']:.2f} "
            f"| {cert['gap']:+.2f} ({cert['sem']:.2f}) |"
        )
    lines += [
        "",
        "## Measured mean density offset (free-energy identity)",
        "",
        "E[log w] - dF_exact = -KL(q_eff || p) exactly, so the certificate's",
        "KL fields are a direct unbiased measurement of the bulk offset the",
        "whole ESS program bounds (the `gap` itself only closes at healthy ESS):",
        "",
        "| L | beta_f | KL (nats) | sem | KL / site |",
        "|---|--------|-----------|-----|-----------|",
    ]
    for r in results:
        cert = r["free_energy_certificate"]
        if "kl_from_mean_log_w" in cert:
            lines.append(
                f"| {r['fine_L']} | {r['fine_beta']:g} "
                f"| {cert['kl_from_mean_log_w']:.1f} | {cert['kl_sem']:.1f} "
                f"| {cert['kl_per_site']:.4f} |"
            )
    lines += [
        "",
        "## Sector-resolved plaquette (within-sector SNIS x exact P(Q))",
        "",
        "The global weights degenerate on sector-frequency mismatch; conditioning",
        "on Q removes it and the exactly known finite-volume P(Q) supplies the",
        "sector masses (U(1)-specific -- labeled as the exact-P(Q) crutch).",
        "E[Q^2] through sectors is exact by construction; plaquette is the test.",
        "",
        "| L | beta_f | arm | estimate | err | z | covered mass | sectors used |",
        "|---|--------|-----|----------|-----|---|--------------|--------------|",
    ]
    for r in results:
        for label in ("baseline", "ais"):
            sec = r.get("sector_resolved_plaquette", {}).get(label)
            if sec is None:
                continue
            est_sectors = [v for v in sec["per_sector"].values() if "mean" in v]
            used = len(est_sectors)
            # a single dominating weight inside any used sector makes the
            # linearized err (hence z) meaningless -- same suppression rule
            # as the global table, applied per sector
            credible = est_sectors and all(
                v.get("ess", 0.0) * v["count"] >= 4.0 for v in est_sectors)
            zs = (f"{sec['z']:+.1f}"
                  if credible and math.isfinite(sec.get("z", float("nan"))) else "--")
            lines.append(
                f"| {r['fine_L']} | {r['fine_beta']:g} | {label} "
                f"| {sec['mean']:.6g} | {sec['err']:.2g} | {zs} "
                f"| {sec['covered_mass']:.3f} | {used} |"
            )
    lines += [
        "",
        "## Observables (AIS-weighted vs exact)",
        "",
        "| L | beta_f | obs | raw | z_raw | AIS | z_AIS | exact |",
        "|---|--------|-----|-----|-------|-----|-------|-------|",
    ]
    for r in results:
        first = True
        for name, o in r["observables"].items():
            def z(v):
                return f"{v:+.1f}" if math.isfinite(v) else "--"
            head = f"| {r['fine_L']} | {r['fine_beta']:g} " if first else "| | "
            lines.append(
                head + f"| {name} | {o['raw'][0]:.5g} ({o['raw'][1]:.2g}) | {z(o['z_raw'])} "
                f"| {o['ais'][0]:.5g} ({o['ais'][1]:.2g}) | {z(o['z_ais'])} | {o['exact']:.5g} |"
            )
            first = False
    lines += [
        "",
        "Weights are valid AIS weights (Neal 2001) from the exact ODE density;",
        "the surrogate fit residual on the held-out half is the irreducible",
        "floor, the bridge increments shrink with more steps. z_AIS suppressed",
        "when effective count < 4. The certificate's exact value here is",
        "2 L^2 log 2pi + log Z_haar(beta_f, L) -- no coarse term (the coarse",
        "level integrates out of the AIS estimator exactly).",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="u1_2d/configs/v2.yaml")
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--cases", nargs="+",
                        default=["16:14.1464", "16:55.0237", "32:55.0237", "32:218.58"])
    parser.add_argument("--n-configs", type=int, default=64)
    parser.add_argument("--ode-steps", type=int, default=120)
    parser.add_argument("--n-probes", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--n-bridge", type=int, default=48)
    parser.add_argument(
        "--basis", choices=["final7", "rich11"], default="final7",
        help="surrogate feature basis. final7 (default) reproduces the result of "
             "record; rich11 reproduces the recorded negative (held-out weights "
             "explode at 2 of 4 cases). See Table S7.",
    )
    parser.add_argument("--n-hmc-per-step", type=int, default=2)
    parser.add_argument("--no-q-hops", action="store_true")
    parser.add_argument("--seed", type=int, default=20260802)
    parser.add_argument(
        "--ridge-floor", type=float, default=None,
        help="lower bound on the surrogate ridge grid. Off by default (the "
             "recorded behaviour). Both divergences in Table S7b selected the "
             "grid's smallest ridge, 0.001, and no converged run did; use this "
             "to test whether that association is causal.",
    )
    parser.add_argument("--sigma-min-coef", type=float, default=0.03)
    parser.add_argument("--physics-blend", type=float, default=None)
    parser.add_argument("--consistency-weight", type=float, default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    set_seed(args.seed)
    device = resolve_device(config)
    action_type = config["action_type"]
    ladder_cfg = config.get("ladder", {})
    if args.consistency_weight is None:
        args.consistency_weight = float(ladder_cfg.get("consistency_weight", 1.0))
    if args.physics_blend is None:
        args.physics_blend = float(ladder_cfg.get("physics_blend_coef", 0.0))

    checkpoint = args.checkpoint or config["train"]["checkpoint"]
    model, schedule = load_checkpoint(checkpoint, device)
    schedule = GeometricNoiseSchedule(
        schedule.sigma_min, schedule.sigma_max, sigma_min_beta_coef=args.sigma_min_coef
    )

    # Default to gitignored scratch: out/u1_2d/ais_transport holds the Table S7
    # result of record, and a bare rerun must never overwrite it. Pass --out
    # explicitly to publish.
    out_dir = Path(args.out or "artifacts/u1_2d/ais_transport")
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for spec in args.cases:
        L, beta = spec.split(":")
        case = (int(L), float(beta))
        print(f"case L={case[0]} beta={case[1]} ...", flush=True)
        r = run_case(model, schedule, case, args, action_type, device)
        print("  " + json.dumps({
            "before_std": round(r["baseline"]["log_weight_std_fiber"], 1),
            "after_std_heldout": round(r["ais"]["log_weight_std_heldout"], 2),
            "ess_heldout": round(r["ais"]["ess_per_n_heldout"], 3),
            "r2": round(r["surrogate_fit"]["r2"], 3),
            "acc": round(r["ais"]["hmc_acceptance_mean"], 2),
            "sec": [r["seconds_ode"], r["seconds_ais"]],
        }), flush=True)
        results.append(r)
        save_json(out_dir / "ais_results.json", results)

    (out_dir / "report.md").write_text(format_report(results, args), encoding="utf-8")
    print(f"wrote {out_dir / 'report.md'}", flush=True)


if __name__ == "__main__":
    main()
