"""HMC thermalization benchmark: diffusion-generated configs as HMC starting points.

For each ladder rung this compares
  (a) HMC chains started from the diffusion-generated ensemble,
  (b) fresh hot- and cold-start HMC chains at the same coupling,
recording per-trajectory observables, and measures the equilibrated regular-HMC
chain's integrated autocorrelation time -- the 'interval' a regular chain needs
between two independent configs (2 tau_int trajectories). The claim under test:
a generated config thermalizes in fewer trajectories than that interval, i.e.
generation + a short HMC tail is cheaper per independent config than running the
chain itself. All chains here run WITHOUT topological updates (plain HMC).

    python diffusion/scripts/05_hmc_thermalization.py --config diffusion/configs/demo.yaml
"""

import argparse
import glob
import json
import math
import time
from pathlib import Path

import numpy as np
import torch

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from diffusion.lgt import make_action
from diffusion.lgt.hmc import BatchedHMC, adapted_hmc_params
from diffusion.lgt.lattice import plaquette_angles, topological_charge
from diffusion.lgt import exact
from diffusion.validate.report import validate_ensemble, freezing_diagnostics
from diffusion.validate.stats import integrated_autocorrelation_time
from diffusion.utils import (
    load_config,
    resolve_device,
    set_seed,
    load_ensemble,
    ensemble_path,
    save_json,
)
from inverserg.lattice import wilson_loop_angles

GEN_COLOR = "#2a78d6"
HOT_COLOR = "#d64550"
COLD_COLOR = "#8a63c9"
INK = "#0b0b0b"
GRID_COLOR = "#e1e0d9"

OBS_LOOPS = {"wilson_2x2": (2, 2), "wilson_4x4": (4, 4)}


def chain_observables(theta: torch.Tensor) -> dict[str, np.ndarray]:
    out = {}
    with torch.no_grad():
        out["plaquette"] = torch.cos(plaquette_angles(theta)).mean(dim=(-2, -1)).cpu().numpy()
        for name, (r, t) in OBS_LOOPS.items():
            if max(r, t) <= theta.shape[-1] // 2:
                out[name] = torch.cos(wilson_loop_angles(theta, r, t)).mean(dim=(-2, -1)).cpu().numpy()
        out["Q"] = topological_charge(theta).cpu().numpy()
    return out


def exact_targets(beta: float, action_type: str, lattice_size: int) -> dict[str, float]:
    targets = {"plaquette": exact.plaquette_exact(beta, action_type, lattice_size)}
    for name, (r, t) in OBS_LOOPS.items():
        if max(r, t) <= lattice_size // 2:
            targets[name] = exact.wilson_loop_exact(beta, r * t, action_type, lattice_size)
    chi = exact.topological_susceptibility_exact(beta, action_type, lattice_size)
    targets["Q^2"] = chi * lattice_size**2
    return targets


def run_relaxation(
    lattice_size: int,
    action,
    initial: torch.Tensor,
    n_traj: int,
    step_size: float,
    n_steps: int,
    device: str,
) -> tuple[dict[str, np.ndarray], torch.Tensor, float, float]:
    """Returns (series {obs: [n_traj + 1, B]}, final state, acceptance, sec/trajectory)."""
    sampler = BatchedHMC(
        lattice_size,
        action,
        n_chains=initial.shape[0],
        n_steps=n_steps,
        step_size=step_size,
        device=device,
    )
    theta = initial.clone().to(device)
    series = {k: [v] for k, v in chain_observables(theta).items()}
    accepted, total = 0, 0
    t0 = time.time()
    with torch.no_grad():
        for _ in range(n_traj):
            theta, accept = sampler.metropolis_step(theta)
            accepted += int(accept.sum())
            total += accept.numel()
            for k, v in chain_observables(theta).items():
                series[k].append(v)
    sec_per_traj = (time.time() - t0) / max(n_traj, 1)
    series = {k: np.stack(v) for k, v in series.items()}
    return series, theta, accepted / max(total, 1), sec_per_traj


def ensemble_z_series(series: np.ndarray, target: float) -> np.ndarray:
    """series [T+1, B] of per-chain values -> z-score of the ensemble mean vs target."""
    mean = series.mean(axis=1)
    sem = series.std(axis=1, ddof=1) / math.sqrt(series.shape[1])
    return (mean - target) / np.maximum(sem, 1e-12)


def thermalization_time(
    series: np.ndarray, target: float, z_threshold: float = 2.0, n_consecutive: int = 5
) -> float:
    """First trajectory count t at which |z(ensemble mean)| <= threshold and stays
    there for n_consecutive trajectories. t = 0 means thermalized before any HMC.
    Returns inf when the window never occurs."""
    z = np.abs(ensemble_z_series(series, target))
    ok = z <= z_threshold
    run_end = min(len(ok), len(ok) - n_consecutive + 1)
    for t in range(max(run_end, 1)):
        if ok[t : t + n_consecutive].all():
            return float(t)
    return float("inf")


def equilibrium_tau_int(series: np.ndarray, discard: int) -> tuple[float, float]:
    """Mean Madras-Sokal tau_int over chains, window after `discard` trajectories."""
    window = series[discard:]
    taus = [integrated_autocorrelation_time(window[:, b])[0] for b in range(window.shape[1])]
    return float(np.mean(taus)), float(np.std(taus) / math.sqrt(len(taus)))


def q_freezing(series: np.ndarray, discard: int, label: str) -> dict:
    window = np.asarray(series[discard:], dtype=float)
    n_tunnelings = int(np.sum(np.abs(np.diff(np.round(window), axis=0)) > 0))
    per_chain = [freezing_diagnostics(window[:, b]) for b in range(window.shape[1])]
    frozen = all(d["frozen"] for d in per_chain)
    taus = [d["tau_int_Q"] for d in per_chain if not d["frozen"]]
    return {
        "label": label,
        "frozen": frozen,
        "n_tunnelings": n_tunnelings,
        "window_length": int(window.shape[0]),
        "n_chains": int(window.shape[1]),
        "tau_int_Q": float(np.mean(taus)) if taus else float(window.shape[0]),
    }


def build_series_dict(raw: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    series = {k: v for k, v in raw.items() if k != "Q"}
    series["Q^2"] = raw["Q"] ** 2
    return series


def plot_relaxation(
    all_series: dict[str, dict[str, np.ndarray]],
    targets: dict[str, float],
    label: str,
    out_path: Path,
    x_max: int | None = None,
) -> None:
    names = [n for n in ("plaquette", "wilson_2x2", "wilson_4x4", "Q^2") if n in targets]
    colors = {"generated start": GEN_COLOR, "hot start": HOT_COLOR, "cold start": COLD_COLOR}
    fig, axes = plt.subplots(2, 2, figsize=(11, 7.5))
    for ax, name in zip(axes.flat, names):
        for start, series in all_series.items():
            if name not in series:
                continue
            data = series[name]
            mean = data.mean(axis=1)
            sem = data.std(axis=1, ddof=1) / math.sqrt(data.shape[1])
            x = np.arange(len(mean))
            ax.plot(x, mean, lw=1.4, color=colors[start], label=start)
            ax.fill_between(x, mean - sem, mean + sem, color=colors[start], alpha=0.25, lw=0)
        ax.axhline(targets[name], color=INK, ls="--", lw=1.1, label="exact")
        if x_max is not None:
            ax.set_xlim(0, x_max)
        ax.set_xlabel("HMC trajectories")
        ax.set_title(name, fontsize=10, color=INK)
        ax.grid(color=GRID_COLOR, lw=0.7)
        ax.set_axisbelow(True)
        for spine in ax.spines.values():
            spine.set_color(GRID_COLOR)
    axes.flat[0].legend(fontsize=8, frameon=False)
    fig.suptitle(f"{label}: ensemble-mean relaxation under plain HMC", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def rows_to_md(rows: list[dict]) -> list[str]:
    cols = ["observable", "value", "error", "exact", "z_exact",
            "reference", "ref_error", "z_ref", "ks_p", "chi2_p"]
    present = [c for c in cols if any(c in r for r in rows)]
    lines = ["| " + " | ".join(present) + " |", "|" + "---|" * len(present)]
    for r in rows:
        cells = []
        for c in present:
            v = r.get(c)
            if v is None:
                cells.append("")
            elif isinstance(v, float):
                cells.append("nan" if math.isnan(v) else f"{v:.4g}")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def fmt_t(t: float) -> str:
    return "never" if math.isinf(t) else f"{t:.0f}"


def run_rung(
    index: int,
    meta: dict,
    gen_configs: torch.Tensor,
    reference: torch.Tensor | None,
    config: dict,
    args,
    device: str,
    out_dir: Path,
) -> dict:
    beta = float(meta["beta"])
    lattice_size = int(meta["lattice_size"])
    action_type = config["action_type"]
    action = make_action(action_type, beta)
    data_cfg = config["data"]
    step_size, n_steps = adapted_hmc_params(
        beta, float(data_cfg["hmc_step_size"]), int(data_cfg["hmc_steps"])
    )
    label = f"rung{index}_L{lattice_size}_beta{beta:g}"
    targets = exact_targets(beta, action_type, lattice_size)
    print(f"\n=== {label}: step_size={step_size:.4f}, n_steps={n_steps} ===")

    n_traj_gen = int(args.n_traj_gen)
    n_traj_base = int(args.n_traj_baseline)
    n_chains_base = max(8, int(args.n_chains_baseline * (16 / lattice_size)))

    print(f"generated start: {gen_configs.shape[0]} chains x {n_traj_gen} trajectories")
    gen_raw, gen_final, gen_acc, gen_spt = run_relaxation(
        lattice_size, action, gen_configs, n_traj_gen, step_size, n_steps, device
    )
    baseline_sampler = BatchedHMC(lattice_size, action, n_chains=n_chains_base, device=device)
    print(f"hot start: {n_chains_base} chains x {n_traj_base} trajectories")
    hot_raw, _, hot_acc, hot_spt = run_relaxation(
        lattice_size, action, baseline_sampler.initialize(hot=True),
        n_traj_base, step_size, n_steps, device,
    )
    print(f"cold start: {n_chains_base} chains x {n_traj_base} trajectories")
    cold_raw, _, cold_acc, _ = run_relaxation(
        lattice_size, action, baseline_sampler.initialize(hot=False),
        n_traj_base, step_size, n_steps, device,
    )

    all_series = {
        "generated start": build_series_dict(gen_raw),
        "hot start": build_series_dict(hot_raw),
        "cold start": build_series_dict(cold_raw),
    }
    subsample = np.random.default_rng(int(config["seed"]) + index).choice(
        gen_configs.shape[0], size=min(n_chains_base, gen_configs.shape[0]), replace=False
    )
    t_therm_series = dict(all_series)
    t_therm_series["generated start"] = {
        k: v[:, subsample] for k, v in all_series["generated start"].items()
    }
    t_therm = {
        start: {name: thermalization_time(series[name], targets[name])
                for name in targets if name in series}
        for start, series in t_therm_series.items()
    }
    t_therm_full = {
        name: thermalization_time(all_series["generated start"][name], targets[name])
        for name in targets if name in all_series["generated start"]
    }

    discard = n_traj_base // 2
    tau = {}
    for name in targets:
        if name == "Q^2":
            continue
        tau[name] = equilibrium_tau_int(hot_raw[name], discard)
    freezing = q_freezing(hot_raw["Q"], discard, f"hot-start HMC L={lattice_size} beta={beta:g}")

    plot_relaxation(
        all_series, targets, label, out_dir / f"{label}_relaxation.png",
        x_max=min(n_traj_base, max(n_traj_gen, 4 * max(
            (t for obs in t_therm.values() for t in obs.values() if math.isfinite(t)), default=25,
        ))),
    )

    rows_pre = validate_ensemble(
        gen_configs, beta, action_type, reference_configs=reference,
        label=f"{label}_generated", output_dir=out_dir,
    )
    rows_post = validate_ensemble(
        gen_final.cpu(), beta, action_type, reference_configs=reference,
        label=f"{label}_after_hmc", output_dir=out_dir,
    )

    slowest = max(2.0 * tau[name][0] for name in tau)
    summary = {
        "label": label,
        "beta": beta,
        "lattice_size": lattice_size,
        "n_gen_chains": int(gen_configs.shape[0]),
        "n_baseline_chains": n_chains_base,
        "n_traj_gen": n_traj_gen,
        "n_traj_baseline": n_traj_base,
        "hmc": {"step_size": step_size, "n_steps": n_steps,
                "acceptance": {"generated": gen_acc, "hot": hot_acc, "cold": cold_acc},
                "sec_per_traj_gen_batch": gen_spt, "sec_per_traj_baseline_batch": hot_spt},
        "t_therm": t_therm,
        "t_therm_generated_full_batch": t_therm_full,
        "t_therm_subsample_size": int(len(subsample)),
        "tau_int": {name: {"value": v, "error": e} for name, (v, e) in tau.items()},
        "hmc_interval_trajectories": slowest,
        "q_freezing": freezing,
    }
    return {"summary": summary, "rows_pre": rows_pre, "rows_post": rows_post,
            "series": all_series, "targets": targets}


def write_thermalization_report(results: list[dict], action_type: str, path: Path) -> None:
    lines = [
        "# Diffusion-generated configs as HMC starting points",
        "",
        f"Action: {action_type}. All HMC in this report is plain HMC "
        "(Omelyan, adapted step size, **no** topological updates).",
        "",
        "**Question.** Does a config sampled from the conditional-diffusion ladder "
        "thermalize under HMC in fewer trajectories than a regular HMC chain needs "
        "between two independent configs (its interval, `2 tau_int`)?",
        "",
        "Thermalization time `t_therm` = first trajectory at which the ensemble-mean "
        "z-score vs the exact value satisfies |z| <= 2 and stays there for 5 "
        "consecutive trajectories (t = 0: already thermalized before any HMC). "
        "For the generated start, t_therm is computed on a random subsample of chains "
        "matched to the baseline chain count so all starts are compared at equal "
        "statistical power. `tau_int` is Madras-Sokal, measured on the second half "
        "of the hot-start chains, averaged over chains.",
        "",
        "## Summary",
        "",
        "| rung | L | beta | t_therm generated (plaq / W22 / W44 / Q^2) | "
        "t_therm hot | t_therm cold | HMC interval 2 tau_int (slowest non-topological) | tau_int(Q) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for res in results:
        s = res["summary"]
        obs_order = [n for n in ("plaquette", "wilson_2x2", "wilson_4x4", "Q^2")
                     if n in s["t_therm"]["generated start"]]

        def fmt_start(start):
            return " / ".join(fmt_t(s["t_therm"][start][n]) for n in obs_order)

        frz = s["q_freezing"]
        tau_q = (f"frozen ({frz['n_tunnelings']} tunnelings in "
                 f"{frz['window_length']} x {frz['n_chains']} traj)"
                 if frz["frozen"] else f"{frz['tau_int_Q']:.1f}")
        lines.append(
            f"| {s['label']} | {s['lattice_size']} | {s['beta']:g} | {fmt_start('generated start')} | "
            f"{fmt_start('hot start')} | {fmt_start('cold start')} | "
            f"{s['hmc_interval_trajectories']:.1f} | {tau_q} |"
        )
    lines += [
        "",
        "Reading the table: every `t_therm` for the generated start at or below the "
        "HMC interval means one generated config costs less HMC time to turn into an "
        "independent thermalized config than the chain's own decorrelation interval "
        "-- and unlike the fresh chains it arrives in the correct topological "
        "sector, which plain HMC cannot reach at all once tau_int(Q) is frozen.",
        "",
    ]
    for res in results:
        s = res["summary"]
        label = s["label"]
        acc = s["hmc"]["acceptance"]
        lines += [
            f"## {label}",
            "",
            f"HMC: step size {s['hmc']['step_size']:.4f}, {s['hmc']['n_steps']} leapfrog steps, "
            f"acceptance generated/hot/cold = {acc['generated']:.3f}/{acc['hot']:.3f}/{acc['cold']:.3f}. "
            f"Generated batch: {s['n_gen_chains']} chains x {s['n_traj_gen']} trajectories "
            f"({s['hmc']['sec_per_traj_gen_batch']:.2f} s/traj for the whole batch); baselines: "
            f"{s['n_baseline_chains']} chains x {s['n_traj_baseline']} trajectories.",
            "",
            f"![relaxation]({label}_relaxation.png)",
            "",
            "tau_int (hot-start chains, second half): "
            + ", ".join(f"{name} = {d['value']:.2f} +- {d['error']:.2f}"
                        for name, d in s["tau_int"].items())
            + f". Topology: {s['q_freezing']['label']} -> "
            + ("**frozen** (no tunneling)" if s["q_freezing"]["frozen"]
               else f"tau_int(Q) = {s['q_freezing']['tau_int_Q']:.1f}")
            + ".",
            "",
            "### Diagnostics: generated ensemble (before HMC)",
            "",
            *rows_to_md(res["rows_pre"]),
            "",
            f"![generated]({label}_generated.png)",
            "",
            f"### Diagnostics: generated ensemble after {s['n_traj_gen']} HMC trajectories",
            "",
            *rows_to_md(res["rows_post"]),
            "",
            f"![after_hmc]({label}_after_hmc.png)",
            "",
        ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="diffusion/configs/demo.yaml")
    parser.add_argument("--rungs", default=None, help="comma-separated rung indices (default: all)")
    parser.add_argument("--n-traj-gen", type=int, default=96, dest="n_traj_gen")
    parser.add_argument("--n-traj-baseline", type=int, default=384, dest="n_traj_baseline")
    parser.add_argument("--n-chains-baseline", type=int, default=64, dest="n_chains_baseline",
                        help="baseline chains at L=16; scaled by 16/L at larger L")
    parser.add_argument("--out", default=None)
    parser.add_argument("--run-dir", default=None, dest="run_dir",
                        help="override the run root (replaces the config's out_dir parents, "
                        "e.g. out/diffusion/demo when the config says artifacts/diffusion/demo)")
    args = parser.parse_args()
    config = load_config(args.config)
    set_seed(int(config["seed"]) + 5)
    device = resolve_device(config)
    action_type = config["action_type"]
    generated_dir = Path(config["ladder"]["out_dir"])
    reference_dir = Path(config["validate"]["out_dir"]) / "reference"
    if args.run_dir is not None:
        run_dir = Path(args.run_dir)
        generated_dir = run_dir / generated_dir.name
        reference_dir = run_dir / Path(config["validate"]["out_dir"]).name / "reference"
    out_dir = Path(args.out) if args.out else generated_dir.parent / "thermalization"
    out_dir.mkdir(parents=True, exist_ok=True)

    pattern = str(generated_dir / f"ladder_rung*_{action_type}_*.pt")
    paths = sorted(glob.glob(pattern))
    if not paths:
        raise SystemExit(f"no ladder ensembles under {pattern}; run 03_run_ladder.py first")
    wanted = None if args.rungs is None else {int(v) for v in args.rungs.split(",")}

    results = []
    for index, path in enumerate(paths):
        if wanted is not None and index not in wanted:
            continue
        gen_configs, meta = load_ensemble(path)
        ref_path = ensemble_path(
            reference_dir, action_type, int(meta["lattice_size"]), float(meta["beta"]),
        )
        reference = load_ensemble(ref_path)[0] if ref_path.exists() else None
        results.append(run_rung(index, meta, gen_configs, reference, config, args, device, out_dir))
        save_json(out_dir / f"{results[-1]['summary']['label']}_summary.json",
                  results[-1]["summary"])

    write_thermalization_report(results, action_type, out_dir / "report.md")
    print(f"\nreport: {out_dir / 'report.md'}")
    for res in results:
        s = res["summary"]
        print(json.dumps({k: s[k] for k in ("label", "t_therm", "hmc_interval_trajectories")}, indent=2))


if __name__ == "__main__":
    main()
