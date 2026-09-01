"""Multilevel SMC ladder: per-level valid weights + resampling up the RG chain.

The ladder's levels are matched by construction (beta_schedule[l-1] is the
matched coarse coupling of beta_schedule[l]), so each lift carries a valid
per-level fiber weight
    log w_l = -S_{beta_l}(x_l) + S_{beta_{l-1}}(c_l) - log q(x_l | c_l),
with log q from probability-flow ODE sampling. Sequential-Monte-Carlo style,
two arms from one base HMC ensemble:

  * transport arm: plain lifts, no weighting -- what the pipeline does today;
  * SMC arm: after each lift, systematic resampling by the per-level weights,
    so the next level starts from an (asymptotically) corrected ensemble.
    Per-level ESS/N and the unique-ancestor fraction quantify how much
    correction each level can actually deliver at the given n.

Observables (plaquette, <Q^2>) per level per arm -- raw and SNIS-reweighted --
are z-scored against exact character-expansion references. The point: per-level
weights confine each level's importance-sampling burden to ONE lift's density
error instead of the compounding joint density, and resampling stops bias from
propagating up the ladder wherever the per-level ESS is usable.

    python u1_2d/scripts/24_smc_ladder.py --n-configs 192
"""

import argparse
import json
import math
import time
from pathlib import Path

import torch

from u1_2d.lgt import make_action, run_hmc_ensemble
from u1_2d.lgt.exact import plaquette_exact, topological_susceptibility_exact
from u1_2d.lgt.hmc import adapted_hmc_params
from u1_2d.lgt.lattice import plaquette_angles, topological_charge
from u1_2d.model.likelihood import (
    _ess_from_log_weights, conditional_ode_sample, free_energy_certificate,
    reweighted_mean, snis_log_weights,
)
from u1_2d.model.schedule import GeometricNoiseSchedule
from u1_2d.model.train import load_checkpoint
from u1_2d.utils import load_config, resolve_device, save_json, set_seed


def systematic_resample(log_w: torch.Tensor, generator: torch.Generator) -> torch.Tensor:
    """Systematic resampling indices; lowest-variance standard scheme."""
    w = torch.exp(log_w - log_w.max())
    w = w / w.sum()
    n = w.numel()
    positions = (torch.rand(1, generator=generator) + torch.arange(n)) / n
    cum = torch.cumsum(w, dim=0)
    return torch.searchsorted(cum, positions.clamp(max=float(cum[-1]) - 1e-9))


def observables(configs: torch.Tensor, L: int, beta: float, action_type: str,
                log_w: torch.Tensor | None = None, n_eff: int | None = None) -> dict:
    """n_eff: effective independent count for the sem. Post-resampling ensembles
    carry duplicated ancestors, so their sem must use the unique-ancestor count,
    not the particle count."""
    with torch.no_grad():
        plaq = torch.cos(plaquette_angles(configs.float())).mean(dim=(-2, -1))
        q2 = topological_charge(configs.float()) ** 2
    ex_p = plaquette_exact(beta, action_type, L)
    ex_q2 = topological_susceptibility_exact(beta, action_type, L) * L**2
    out = {}
    for name, vals, ex in (("plaquette", plaq, ex_p), ("Q^2", q2, ex_q2)):
        if log_w is None:
            n = n_eff if n_eff is not None else vals.numel()
            mu, err = float(vals.mean()), float(vals.std() / max(n, 2) ** 0.5)
        else:
            mu, err = reweighted_mean(vals, log_w)
        out[name] = {"value": mu, "err": err, "exact": ex,
                     "z": (mu - ex) / err if err > 0 else float("nan")}
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="u1_2d/configs/v2.yaml")
    parser.add_argument("--checkpoint", default=None,
                        help="default: out/u1_2d/checkpoints/score_net_rkl2.pt")
    parser.add_argument("--base", default="8:1.3472", help="L:beta of the HMC base")
    parser.add_argument("--schedule", nargs="+", type=float, default=[4.0, 14.1464],
                        help="target betas; each level doubles L")
    parser.add_argument("--n-configs", type=int, default=192)
    parser.add_argument("--ode-steps", type=int, default=120)
    parser.add_argument("--n-probes", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--sigma-min-coef", type=float, default=0.03)
    parser.add_argument("--seed", type=int, default=20260802)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    set_seed(args.seed)
    device = resolve_device(config)
    action_type = config["action_type"]
    ladder_cfg = config.get("ladder", {})
    cw = float(ladder_cfg.get("consistency_weight", 1.0))
    blend = float(ladder_cfg.get("physics_blend_coef", 0.0))
    blend_min = float(ladder_cfg.get("physics_blend_beta_min", 0.0))

    ckpt = args.checkpoint or "out/u1_2d/checkpoints/score_net_rkl2.pt"
    model, schedule = load_checkpoint(ckpt, device)
    schedule = GeometricNoiseSchedule(
        schedule.sigma_min, schedule.sigma_max, sigma_min_beta_coef=args.sigma_min_coef
    )
    out_dir = Path(args.out or "out/u1_2d/ess_chain/smc_ladder")
    out_dir.mkdir(parents=True, exist_ok=True)

    base_L, base_beta = args.base.split(":")
    base_L, base_beta = int(base_L), float(base_beta)
    step_size, n_steps = adapted_hmc_params(base_beta, 0.2, 5)
    base, _ = run_hmc_ensemble(
        base_L, make_action(action_type, base_beta),
        n_configs=args.n_configs, n_chains=16, burn_in=200, thin=5,
        n_steps=n_steps, step_size=step_size, device=device,
        topological_updates=True, hot_start=True,
    )
    print(f"base: L={base_L} beta={base_beta} x {base.shape[0]}", flush=True)

    gen = torch.Generator().manual_seed(args.seed)
    arms = {"transport": base.clone(), "smc": base.clone()}
    prev_beta = base_beta
    levels = []
    for li, beta_f in enumerate(args.schedule):
        fine_L = base_L * 2 ** (li + 1)
        rec = {"level": li + 1, "L": fine_L, "beta_f": beta_f, "coarse_beta": prev_beta}
        for arm in ("transport", "smc"):
            t0 = time.time()
            coarse = arms[arm]
            fine, log_q = conditional_ode_sample(
                model, schedule, coarse, beta_f,
                n_steps=args.ode_steps, n_probes=args.n_probes,
                consistency_weight=cw, physics_blend_coef=blend,
                physics_blend_beta_min=blend_min,
                batch_size=args.batch_size, device=device,
                seed=args.seed + 100 * li + (0 if arm == "transport" else 50),
            )
            log_w = snis_log_weights(fine, log_q, beta_f, action_type,
                                     coarse=coarse, coarse_beta_matched=prev_beta)
            ess, std, _ = _ess_from_log_weights(log_w)
            cert = free_energy_certificate(log_w, fine_L, beta_f, prev_beta, action_type)
            # E[w] = exact exp(-dF) requires coarse ~ exp(-S_matched): true at
            # level 1 for both arms, asymptotically true for the SMC arm's
            # resampled coarse at deeper levels, false for the transport arm
            # there (unweighted lift with unknown density).
            cert["valid"] = (li == 0) or (arm == "smc")
            a = {
                "ess_per_n": ess, "log_w_std": std,
                "free_energy_certificate": cert,
                "raw": observables(fine, fine_L, beta_f, action_type),
                "snis": observables(fine, fine_L, beta_f, action_type, log_w=log_w),
                "seconds": round(time.time() - t0, 1),
            }
            if arm == "smc":
                idx = systematic_resample(log_w, gen)
                n_unique = int(idx.unique().numel())
                a["unique_fraction"] = n_unique / idx.numel()
                arms[arm] = fine[idx]
                a["resampled"] = observables(arms[arm], fine_L, beta_f, action_type,
                                             n_eff=n_unique)
            else:
                arms[arm] = fine
            rec[arm] = a
            print(json.dumps({"level": li + 1, "arm": arm,
                              "ess": round(ess, 4), "log_w_std": round(std, 2),
                              "sec": a["seconds"]}), flush=True)
        levels.append(rec)
        prev_beta = beta_f
        save_json(out_dir / "smc_results.json", levels)

    lines = [
        "# SMC ladder: per-level weights + resampling vs plain transport",
        "",
        f"base {base_L}:{base_beta:g}, n = {args.n_configs}, checkpoint `{ckpt}`",
        "",
        "| level | arm | ESS/N | log-w std | uniq | obs | raw z | SNIS z | resampled z |",
        "|-------|-----|-------|-----------|------|-----|-------|--------|-------------|",
    ]
    for rec in levels:
        for arm in ("transport", "smc"):
            a = rec[arm]
            uniq = f"{a.get('unique_fraction', float('nan')):.2f}" if arm == "smc" else "--"
            first = True
            for name in ("plaquette", "Q^2"):
                rz = a["resampled"][name]["z"] if arm == "smc" else None
                head = (f"| {rec['L']}@{rec['beta_f']:g} | {arm} | {a['ess_per_n']:.3f} | "
                        f"{a['log_w_std']:.1f} | {uniq} " if first else "| | | | | ")
                lines.append(
                    head + f"| {name} | {a['raw'][name]['z']:+.1f} | "
                    f"{a['snis'][name]['z']:+.1f} | "
                    + (f"{rz:+.1f} |" if rz is not None and math.isfinite(rz) else "-- |")
                )
                first = False
    lines += [
        "",
        "z-scores vs exact character-expansion references (finite volume).",
        "The SMC arm resamples by the per-level fiber weights before each next",
        "lift; unique-ancestor fraction shows how much genuine diversity",
        "survives resampling at this n (resampled sems use the unique count).",
        "Validity per arm: at level 1 both arms' per-level weights are exact,",
        "so SNIS there is noisy rather than biased. At level >= 2 that holds",
        "only for the SMC arm (asymptotically, through resampling); the",
        "transport arm's coarse ensemble is an unweighted lift with unknown",
        "density, so its per-level SNIS corrects only the last lift and is",
        "BIASED, not merely noisy.",
        "",
        "## Free-energy certificate",
        "",
        "log E[w] must equal the exact 2 L_f^2 log(2 pi) + log Z(beta_f, L_f)",
        "- log Z(beta_c, L_c) from the character expansion (valid where the",
        "coarse ensemble follows exp(-S_matched); see `valid` flags in",
        "smc_results.json). Heavy-tailed weights bias the estimate low.",
        "",
        "| level | arm | valid | log mean w | exact dF | gap | sem |",
        "|-------|-----|-------|------------|----------|-----|-----|",
    ] + [
        (lambda c: f"| {rec['L']}@{rec['beta_f']:g} | {arm} | {c['valid']} | "
                   f"{c['log_mean_w']:.2f} | {c['exact_delta_F']:.2f} | "
                   f"{c['gap']:+.2f} | {c['sem']:.2f} |")(rec[arm]["free_energy_certificate"])
        for rec in levels for arm in ("transport", "smc")
    ]
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_dir / 'report.md'}", flush=True)


if __name__ == "__main__":
    main()
