"""Diffusion pipeline vs instanton-HMC: the strongest classical baseline.

Script 13 established that instanton-update HMC (the volume-independent uniform
Q-shift move, dS ~ 2 pi^2 beta / V) keeps tunneling where standard HMC froze at
beta >= 16 -- so instanton HMC, not standard HMC, is the honest classical
baseline for the diffusion ladder. This script runs the missing head-to-head:

  Arm A (instanton HMC): batched chains at the fine coupling with the Q-hop
      move, burn-in + production, per-chain time-average statistics, tau_int,
      and measured seconds/trajectory.
  Arm B (diffusion): matched-coarse HMC base (with Q-hops, unbiased) -> one
      inverse-RG step (conditional diffusion + charge transport) -> retherm
      (honest default: no Q-hops), timed end to end.

Verdict per case: observable quality (z vs exact character expansion) and
wall-clock seconds per independent configuration for each arm.

    python diffusion_v2/scripts/14_diffusion_vs_instanton_hmc.py \
        --config diffusion_v2/configs/v2.yaml [--smoke]
"""

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import torch

from diffusion_v2.lgt import make_action
from diffusion_v2.lgt import exact
from diffusion_v2.lgt.blocking import approx_matched_coarse_beta
from diffusion_v2.lgt.hmc import BatchedHMC, adapted_hmc_params, run_hmc_ensemble
from diffusion_v2.lgt.lattice import plaquette_angles, topological_charge, wilson_loop_angles
from diffusion_v2.lgt.local_updates import retherm_sweeps, topological_update
from diffusion_v2.model.schedule import GeometricNoiseSchedule
from diffusion_v2.model.train import load_checkpoint
from diffusion_v2.pipeline.ladder import generate_fine_from_coarse
from diffusion_v2.validate.stats import integrated_autocorrelation_time
from diffusion_v2.utils import load_config, resolve_device, set_seed, save_json, save_ensemble

OBS_LOOPS = {"wilson_2x2": (2, 2), "wilson_4x4": (4, 4)}


def config_observables(theta: torch.Tensor) -> dict[str, np.ndarray]:
    out = {}
    with torch.no_grad():
        out["plaquette"] = torch.cos(plaquette_angles(theta)).mean(dim=(-2, -1)).cpu().numpy()
        for name, (r, t) in OBS_LOOPS.items():
            if max(r, t) <= theta.shape[-1] // 2:
                out[name] = torch.cos(wilson_loop_angles(theta, r, t)).mean(dim=(-2, -1)).cpu().numpy()
        q = topological_charge(theta).cpu().numpy()
        out["Q"] = q
        out["Q^2"] = q**2
    return out


def exact_targets(beta: float, action_type: str, lattice_size: int) -> dict[str, float]:
    targets = {"plaquette": exact.plaquette_exact(beta, action_type, lattice_size)}
    for name, (r, t) in OBS_LOOPS.items():
        if max(r, t) <= lattice_size // 2:
            targets[name] = exact.wilson_loop_exact(beta, r * t, action_type, lattice_size)
    chi = exact.topological_susceptibility_exact(beta, action_type, lattice_size)
    targets["Q^2"] = chi * lattice_size**2
    return targets


def chain_stats(series: np.ndarray, discard_frac: float = 0.25) -> tuple[float, float]:
    """Per-chain time-averages -> mean +- SEM over chains (never pools time x chain:
    pooling gives overconfident errors once chains decorrelate slowly)."""
    t0 = int(series.shape[0] * discard_frac)
    means = series[t0:].mean(axis=0)
    return float(means.mean()), float(means.std(ddof=1) / math.sqrt(len(means)))


def sem_stats(values: np.ndarray) -> tuple[float, float]:
    return float(values.mean()), float(values.std(ddof=1) / math.sqrt(len(values)))


def run_instanton_hmc(lattice_size, beta, action_type, n_chains, burn_in, n_prod, device, seed):
    torch.manual_seed(seed)
    action = make_action(action_type, beta)
    step_size, n_steps = adapted_hmc_params(beta, 0.2, 5)
    sampler = BatchedHMC(lattice_size, action, n_chains=n_chains,
                         n_steps=n_steps, step_size=step_size, device=device)
    theta = sampler.initialize(hot=beta < 8)
    t0 = time.time()
    with torch.no_grad():
        for _ in range(burn_in):
            theta, _ = sampler.metropolis_step(theta)
            theta, _ = topological_update(theta, action)
    burn_seconds = time.time() - t0
    series = {k: [v] for k, v in config_observables(theta).items()}
    accepted = total = inst_accepted = inst_total = 0
    t0 = time.time()
    with torch.no_grad():
        for _ in range(n_prod):
            theta, acc = sampler.metropolis_step(theta)
            accepted += int(acc.sum()); total += acc.numel()
            theta, iacc = topological_update(theta, action)
            inst_accepted += int(iacc.sum()); inst_total += iacc.numel()
            for k, v in config_observables(theta).items():
                series[k].append(v)
    prod_seconds = time.time() - t0
    series = {k: np.stack(v) for k, v in series.items()}
    q_rounded = np.round(series["Q"])
    tunnelings = int(np.sum(np.abs(np.diff(q_rounded, axis=0)) > 0))
    return {
        "series": series,
        "acceptance": accepted / max(total, 1),
        "instanton_acceptance": inst_accepted / max(inst_total, 1),
        "tunnelings": tunnelings,
        "burn_seconds": burn_seconds,
        "prod_seconds": prod_seconds,
        "sec_per_traj": prod_seconds / max(n_prod, 1),
        "final": theta,
    }


def run_case(case_beta, lattice_size, model, schedule, ladder_cfg, action_type,
             n_chains, burn_in, n_prod, n_gen, device, seed, case_dir, smoke):
    targets = exact_targets(case_beta, action_type, lattice_size)
    result = {"beta": case_beta, "lattice_size": lattice_size, "targets": targets}

    # --- Arm A: instanton HMC ---
    print(f"  instanton HMC: {n_chains} chains, burn {burn_in}, prod {n_prod}", flush=True)
    inst = run_instanton_hmc(lattice_size, case_beta, action_type,
                             n_chains, burn_in, n_prod, device, seed)
    arm_a = {"acceptance": inst["acceptance"],
             "instanton_acceptance": inst["instanton_acceptance"],
             "tunnelings": inst["tunnelings"],
             "burn_seconds": round(inst["burn_seconds"], 2),
             "prod_seconds": round(inst["prod_seconds"], 2),
             "sec_per_traj": inst["sec_per_traj"]}
    taus = {}
    discard = int(n_prod * 0.25)
    for name in ("plaquette", "wilson_2x2", "wilson_4x4"):
        if name not in inst["series"]:
            continue
        window = inst["series"][name][discard:]
        per_chain = [integrated_autocorrelation_time(window[:, b])[0]
                     for b in range(window.shape[1])]
        taus[name] = float(np.mean(per_chain))
    q_window = inst["series"]["Q"][discard:]
    q_taus = [integrated_autocorrelation_time(q_window[:, b])[0]
              for b in range(q_window.shape[1])
              if np.std(q_window[:, b]) > 0]
    taus["Q"] = float(np.mean(q_taus)) if q_taus else float("inf")
    arm_a["tau_int"] = taus
    slowest = max(v for k, v in taus.items() if k != "Q" and math.isfinite(v))
    arm_a["interval_trajectories"] = 2.0 * slowest
    # a batch of n_chains yields n_chains configs per interval
    arm_a["seconds_per_independent_config"] = (
        2.0 * slowest * inst["sec_per_traj"] / n_chains
    )
    arm_a["burnin_seconds_amortized"] = inst["burn_seconds"]
    for name, target in targets.items():
        if name in inst["series"]:
            mean, err = chain_stats(inst["series"][name])
            arm_a[f"{name}_mean"] = mean
            arm_a[f"{name}_err"] = err
            arm_a[f"{name}_z"] = (mean - target) / max(err, 1e-12)
    result["instanton_hmc"] = arm_a

    # --- Arm B: diffusion pipeline ---
    coarse_beta = approx_matched_coarse_beta(case_beta, action_type)
    coarse_L = lattice_size // 2
    print(f"  diffusion: base L={coarse_L} beta={coarse_beta:.4f}, {n_gen} configs", flush=True)
    step_size, n_steps = adapted_hmc_params(coarse_beta, 0.2, 5)
    cb = 200 if coarse_beta < 5 else (500 if smoke else (2000 if coarse_beta >= 20 else 600))
    t0 = time.time()
    coarse, _ = run_hmc_ensemble(
        coarse_L, make_action(action_type, coarse_beta), n_configs=n_gen,
        n_chains=min(16, n_gen), burn_in=cb, thin=5, n_steps=n_steps,
        step_size=step_size, device=device, topological_updates=True,
        hot_start=coarse_beta < 5,
    )
    base_seconds = time.time() - t0
    t0 = time.time()
    fine = generate_fine_from_coarse(
        model, schedule, coarse, case_beta,
        n_sampler_steps=24 if smoke else int(ladder_cfg.get("n_sampler_steps", 200)),
        n_corrector_steps=int(ladder_cfg.get("n_corrector_steps", 1)),
        batch_size=int(ladder_cfg.get("sample_batch_size", 32)),
        device=device,
        consistency_weight=float(ladder_cfg.get("consistency_weight", 1.0)),
        enforce_coarse_charge=bool(ladder_cfg.get("enforce_coarse_charge", True)),
        physics_blend_coef=float(ladder_cfg.get("physics_blend_coef", 0.0)),
        physics_blend_beta_min=float(ladder_cfg.get("physics_blend_beta_min", 0.0)),
    )
    sample_seconds = time.time() - t0
    t0 = time.time()
    fine = retherm_sweeps(
        fine, make_action(action_type, case_beta),
        4 if smoke else int(ladder_cfg.get("n_retherm_sweeps", 16)),
        topological_updates=bool(ladder_cfg.get("retherm_topological_updates", False)),
    )
    retherm_seconds = time.time() - t0
    obs = config_observables(fine)
    arm_b = {
        "coarse_beta": coarse_beta,
        "n_configs": int(fine.shape[0]),
        "base_seconds": round(base_seconds, 2),
        "sample_seconds": round(sample_seconds, 2),
        "retherm_seconds": round(retherm_seconds, 2),
        "seconds_per_independent_config": (base_seconds + sample_seconds + retherm_seconds)
        / max(fine.shape[0], 1),
    }
    for name, target in targets.items():
        if name in obs:
            mean, err = sem_stats(obs[name])
            arm_b[f"{name}_mean"] = mean
            arm_b[f"{name}_err"] = err
            arm_b[f"{name}_z"] = (mean - target) / max(err, 1e-12)
    result["diffusion"] = arm_b
    save_ensemble(case_dir / f"diffusion_L{lattice_size}_beta{case_beta:g}.pt", fine, {
        "beta": case_beta, "lattice_size": lattice_size, "action_type": action_type,
        "provenance": "14_diffusion_vs_instanton_hmc arm B (one inverse step + retherm)",
    })
    np.savez_compressed(case_dir / f"instanton_series_L{lattice_size}_beta{case_beta:g}.npz",
                        **inst["series"])
    return result


def quality(arm, targets, threshold=2.5) -> str:
    zs = [abs(arm.get(f"{n}_z", float("nan"))) for n in targets]
    zs = [z for z in zs if math.isfinite(z)]
    return "pass" if zs and max(zs) <= threshold else f"max|z|={max(zs):.1f}" if zs else "n/a"


def write_report(records, out_dir, args):
    lines = [
        "# Diffusion pipeline vs instanton HMC",
        "",
        "Instanton HMC (global Q-hop Metropolis move, dS ~ 2 pi^2 beta / V -- the "
        "uniform Q-shift of Albandea-style topology moves) is the strongest "
        "classical baseline this project has: it keeps tunneling to beta = 256 "
        "where standard HMC froze at beta = 16 (script 13). The question here is "
        "whether the diffusion ladder still wins against *it* on wall-clock cost "
        "per independent configuration while matching exact observables.",
        "",
        "Arm B cost includes everything: matched-coarse HMC base (with Q-hops), "
        "conditional diffusion sampling, and rethermalization "
        "(honest default: no Q-hops during retherm). Arm A cost per config is "
        "2 tau_int x sec/traj / n_chains, i.e. its marginal equilibrium cost, "
        "with burn-in reported separately as the one-time entry fee.",
        "",
        "| beta_f | arm | quality (z vs exact) | <Q^2> (exact) | tau_int slowest | "
        "s / independent config | one-time cost s |",
        "|---|---|---|---|---|---|---|",
    ]
    for rec in records:
        t = rec["targets"]
        a, b = rec["instanton_hmc"], rec["diffusion"]
        qa = quality(a, t)
        qb = quality(b, t)
        exact_q2 = t.get("Q^2", float("nan"))
        slow_a = max(v for k, v in a["tau_int"].items() if k != "Q" and math.isfinite(v))
        lines.append(
            f"| {rec['beta']:g} | instanton HMC | {qa} | "
            f"{a.get('Q^2_mean', float('nan')):.3g} +- {a.get('Q^2_err', float('nan')):.2g} "
            f"({exact_q2:.3g}) | {slow_a:.1f} | {a['seconds_per_independent_config']:.3f} | "
            f"{a['burn_seconds']:.0f} (burn-in) |"
        )
        lines.append(
            f"| {rec['beta']:g} | diffusion | {qb} | "
            f"{b.get('Q^2_mean', float('nan')):.3g} +- {b.get('Q^2_err', float('nan')):.2g} "
            f"({exact_q2:.3g}) | n/a (independent draws) | "
            f"{b['seconds_per_independent_config']:.3f} | 0 (amortized in per-config) |"
        )
    lines += [
        "",
        "Notes. (1) Diffusion configs are conditionally independent given the "
        "coarse ensemble; residual correlation enters only through the thinned "
        "coarse HMC chains. (2) Instanton-HMC tau_int is per-observable "
        "Madras-Sokal on per-chain series, discarding the first 25%; its Q "
        "mixing is genuine (tunnelings counted), unlike the pipeline's "
        "structurally transported sector. (3) Quality threshold |z| <= 2.5. "
        "(4) The diffusion per-config cost amortizes the coarse base over the "
        "batch; scaling the batch up lowers it further, while the HMC interval "
        "cost is irreducible per config.",
        "",
        f"Settings: chains={args.n_chains}, burn-in={args.burn_in}, "
        f"production={args.n_prod} traj, n_gen={args.n_gen}, seed={args.seed}, "
        f"checkpoint={args.checkpoint}.",
    ]
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="diffusion_v2/configs/v2.yaml")
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--betas", default="4.44,14.1464,55.0237,118.5,218.58")
    parser.add_argument("--lattice-size", type=int, default=32)
    parser.add_argument("--n-chains", type=int, default=32)
    parser.add_argument("--burn-in", type=int, default=500)
    parser.add_argument("--n-prod", type=int, default=640)
    parser.add_argument("--n-gen", type=int, default=128)
    parser.add_argument("--seed", type=int, default=20260731)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    device = resolve_device(config)
    action_type = config["action_type"]
    ladder_cfg = config.get("ladder", {})
    args.checkpoint = args.checkpoint or config["train"]["checkpoint"]

    out_dir = Path(args.out_dir or
                   (Path(config["validate"]["out_dir"]).parent / "diffusion_vs_instanton"))
    if args.smoke:
        out_dir = out_dir / "smoke"
        args.betas = "4.44,16.0"
        args.n_chains, args.burn_in, args.n_prod, args.n_gen = 8, 60, 120, 16
        args.lattice_size = 16
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "summary.json"
    records = []
    if summary_path.exists():
        records = json.loads(summary_path.read_text(encoding="utf-8"))

    if not args.report_only:
        set_seed(args.seed)
        model, schedule = load_checkpoint(args.checkpoint, device)
        coef = ladder_cfg.get("sigma_min_beta_coef")
        if coef is not None:
            schedule = GeometricNoiseSchedule(
                schedule.sigma_min, schedule.sigma_max, sigma_min_beta_coef=float(coef)
            )
        betas = [float(v) for v in args.betas.split(",")]
        done = {r["beta"] for r in records}
        for beta in betas:
            if beta in done:
                print(f"beta={beta:g}: cached, skipping", flush=True)
                continue
            print(f"case L={args.lattice_size} beta={beta:g}", flush=True)
            case_dir = out_dir / f"L{args.lattice_size}_beta{beta:g}"
            case_dir.mkdir(parents=True, exist_ok=True)
            t0 = time.time()
            rec = run_case(beta, args.lattice_size, model, schedule, ladder_cfg,
                           action_type, args.n_chains, args.burn_in, args.n_prod,
                           args.n_gen, device, args.seed, case_dir, args.smoke)
            rec["case_seconds"] = round(time.time() - t0, 1)
            records.append(rec)
            save_json(summary_path, records)
            print(f"  done in {rec['case_seconds']:.0f}s", flush=True)

    write_report(records, out_dir, args)
    print(f"report: {out_dir / 'report.md'}")


if __name__ == "__main__":
    main()
