"""Single-chain thermalization traces for higher-order observables, seeded from
the generalization-study ensembles.

Extends 08_plaquette_traces.py from the plaquette to Wilson loops (2x2, 4x4,
6x6) and Q^2, and swaps the thermalization-benchmark rungs for the generated
ensembles of 06_generalization_study.py -- by default the low-beta matched
pairs (beta_f ~ 1.5 ... 6.1), where a fresh hot start can actually thermalize
instead of freezing into a random topological sector, plus A_bc4
(beta_f = 14.1464) as the frozen high-beta contrast.

Unlike 08 (which replots series saved by the benchmark), this script runs its
own plain HMC (no topological updates): for each case it relaxes
  (a) chains seeded from the generalization generated ensemble,
  (b) fresh cold-start chains,
  (c) fresh hot-start chains,
records every observable per trajectory, measures t_therm with the same
ensemble |z| <= 2 criterion as 05_hmc_thermalization.py, and draws one
08-style figure per observable: a single chain's trace, blue up to t_therm,
orange after, red dashed exact value. Series and summaries are cached under
<gen-dir>/thermalization, so replotting is free (--plot-only).

Caveat: 06 saves its generated ensembles after 16 rethermalization sweeps
(with Q-hops), so the seeds here are not raw diffusion output; the seed rows
measure how much residual relaxation the shipped ensembles still need.

    .venv/Scripts/python.exe diffusion/scripts/09_observable_traces.py
    .venv/Scripts/python.exe diffusion/scripts/09_observable_traces.py --cases A_bc1 --n-traj 200
    .venv/Scripts/python.exe diffusion/scripts/09_observable_traces.py --plot-only
"""

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import torch

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from diffusion.lgt import exact, make_action
from diffusion.lgt.hmc import BatchedHMC, adapted_hmc_params
from diffusion.lgt.lattice import plaquette_angles, topological_charge
from diffusion.utils import load_ensemble, save_json, set_seed
from inverserg.lattice import wilson_loop_angles

THERM_COLOR = "#2440b3"
PROD_COLOR = "#f5a623"
EXACT_COLOR = "#d62728"
INK = "#0b0b0b"
GRID_COLOR = "#e1e0d9"

STARTS = ["diffusion seed", "cold start", "hot start"]
OBS_LOOPS = {"wilson_2x2": (2, 2), "wilson_4x4": (4, 4), "wilson_6x6": (6, 6)}
OBS_FILENAME = {"Q^2": "Q2"}
DEFAULT_CASES = "A_bc0.25,A_bc0.5,A_bc1,A_bc2,A_bc4"


def chain_observables(theta: torch.Tensor) -> dict[str, np.ndarray]:
    out = {"plaquette": torch.cos(plaquette_angles(theta)).mean(dim=(-2, -1)).cpu().numpy()}
    for name, (r, t) in OBS_LOOPS.items():
        if max(r, t) <= theta.shape[-1] // 2:
            out[name] = torch.cos(wilson_loop_angles(theta, r, t)).mean(dim=(-2, -1)).cpu().numpy()
    out["Q^2"] = topological_charge(theta).square().cpu().numpy()
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
    action, initial: torch.Tensor, n_traj: int, step_size: float, n_steps: int, device: str
) -> tuple[dict[str, np.ndarray], float]:
    sampler = BatchedHMC(
        initial.shape[-1], action, n_chains=initial.shape[0],
        n_steps=n_steps, step_size=step_size, device=device,
    )
    theta = initial.clone().to(device)
    series = {k: [v] for k, v in chain_observables(theta).items()}
    accepted, total = 0, 0
    with torch.no_grad():
        for _ in range(n_traj):
            theta, accept = sampler.metropolis_step(theta)
            accepted += int(accept.sum())
            total += accept.numel()
            for k, v in chain_observables(theta).items():
                series[k].append(v)
    return {k: np.stack(v) for k, v in series.items()}, accepted / max(total, 1)


def thermalization_time(
    series: np.ndarray, target: float, z_threshold: float = 2.0, n_consecutive: int = 5
) -> float:
    """First trajectory t at which |z(ensemble mean vs target)| <= threshold and stays
    there for n_consecutive trajectories; inf when that never happens."""
    mean = series.mean(axis=1)
    sem = series.std(axis=1, ddof=1) / math.sqrt(series.shape[1])
    z = np.abs((mean - target) / np.maximum(sem, 1e-12))
    ok = z <= z_threshold
    run_end = min(len(ok), len(ok) - n_consecutive + 1)
    for t in range(max(run_end, 1)):
        if ok[t : t + n_consecutive].all():
            return float(t)
    return float("inf")


def find_generated(gen_dir: Path, run_id: str) -> Path:
    matches = sorted((gen_dir / "generated").glob(f"{run_id}_*.pt"))
    if not matches:
        raise SystemExit(f"no generated ensemble for {run_id} under {gen_dir / 'generated'}; "
                         "run 06_generalization_study.py first")
    return matches[0]


def run_case(
    run_id: str, gen_dir: Path, out_dir: Path, n_traj: int, n_chains: int,
    action_type: str, device: str,
) -> dict:
    configs, meta = load_ensemble(find_generated(gen_dir, run_id))
    beta, lattice_size = float(meta["beta"]), int(meta["lattice_size"])
    action = make_action(action_type, beta)
    step_size, n_steps = adapted_hmc_params(beta)
    targets = exact_targets(beta, action_type, lattice_size)
    n_chains = min(n_chains, configs.shape[0])
    print(f"=== {run_id}: L={lattice_size} beta={beta:g}, {n_chains} chains x {n_traj} "
          f"trajectories per start (step {step_size:.4f}, {n_steps} steps) ===", flush=True)

    sampler = BatchedHMC(lattice_size, action, n_chains=n_chains, device=device)
    initials = {
        "diffusion seed": configs[:n_chains],
        "cold start": sampler.initialize(hot=False),
        "hot start": sampler.initialize(hot=True),
    }
    all_series: dict[str, dict[str, np.ndarray]] = {}
    acceptance: dict[str, float] = {}
    for start in STARTS:
        t0 = time.time()
        all_series[start], acceptance[start] = run_relaxation(
            action, initials[start], n_traj, step_size, n_steps, device
        )
        print(f"    {start}: acceptance {acceptance[start]:.3f}, "
              f"{time.time() - t0:.0f}s", flush=True)

    t_therm = {
        start: {name: thermalization_time(series[name], targets[name])
                for name in targets if name in series}
        for start, series in all_series.items()
    }
    summary = {
        "run_id": run_id,
        "beta": beta,
        "lattice_size": lattice_size,
        "action_type": action_type,
        "n_traj": n_traj,
        "n_chains": n_chains,
        "hmc": {"step_size": step_size, "n_steps": n_steps, "acceptance": acceptance},
        "targets": targets,
        "t_therm": t_therm,
        "seed_provenance": meta.get("provenance", ""),
    }
    np.savez_compressed(
        out_dir / f"{run_id}_series.npz",
        **{f"{start}|{name}": series for start, obs in all_series.items()
           for name, series in obs.items()},
    )
    save_json(out_dir / f"{run_id}_summary.json", summary)
    return summary


def plot_case_observable(
    out_dir: Path, summary: dict, series: np.lib.npyio.NpzFile, name: str, chain: int
) -> Path:
    beta, lattice_size = summary["beta"], summary["lattice_size"]
    target = summary["targets"][name]
    fig, axes = plt.subplots(len(STARTS), 1, figsize=(10.5, 9.5))
    for ax, start in zip(axes, STARTS):
        trace = series[f"{start}|{name}"][:, chain]
        t_therm = summary["t_therm"][start][name]
        x = np.arange(len(trace))
        if t_therm is None or math.isinf(t_therm):
            ax.plot(x, trace, lw=0.9, color=THERM_COLOR,
                    label="thermalization (never completes)")
            note = "never thermalizes within the budget"
        else:
            split = int(t_therm)
            ax.plot(x[: split + 1], trace[: split + 1], lw=0.9, color=THERM_COLOR,
                    label="thermalization")
            ax.plot(x[split:], trace[split:], lw=0.9, color=PROD_COLOR,
                    label="production")
            note = f"$t_{{therm}}$ = {split} trajectories"
        ax.axhline(target, color=EXACT_COLOR, ls="--", lw=1.3, label="theoretical value")
        ax.set_title(f"{start} — {note}", fontsize=10, color=INK)
        ax.set_ylabel(name, fontsize=9)
        ax.legend(fontsize=8, frameon=False,
                  loc="lower right" if start == "hot start" else "upper right")
        ax.grid(color=GRID_COLOR, lw=0.7)
        ax.set_axisbelow(True)
        for spine in ax.spines.values():
            spine.set_color(GRID_COLOR)
    axes[0].set_ylim(axes[1].get_ylim())
    axes[-1].set_xlabel("HMC trajectory", fontsize=9)
    fig.suptitle(
        f"{name} vs. trajectory, single chain (L={lattice_size}, "
        rf"$\beta$={beta:g}, exact = {target:.4g})",
        fontsize=12,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    out = out_dir / f"{summary['run_id']}_{OBS_FILENAME.get(name, name)}_trace.png"
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out


def plot_case(out_dir: Path, run_id: str, chain: int) -> None:
    summary = json.loads((out_dir / f"{run_id}_summary.json").read_text(encoding="utf-8"))
    series = np.load(out_dir / f"{run_id}_series.npz")
    for name in summary["targets"]:
        print(plot_case_observable(out_dir, summary, series, name, chain), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gen-dir", default="out/diffusion/demo/generalization",
                        help="generalization study output directory (06)")
    parser.add_argument("--out", default=None,
                        help="output directory (default <gen-dir>/thermalization)")
    parser.add_argument("--cases", default=DEFAULT_CASES,
                        help="comma-separated 06 run_ids")
    parser.add_argument("--n-traj", type=int, default=600, dest="n_traj")
    parser.add_argument("--n-chains", type=int, default=32, dest="n_chains")
    parser.add_argument("--chain", type=int, default=0, help="chain index to trace")
    parser.add_argument("--action-type", default="wilson", dest="action_type")
    parser.add_argument("--plot-only", action="store_true",
                        help="rebuild figures from cached series/summaries")
    args = parser.parse_args()
    gen_dir = Path(args.gen_dir)
    out_dir = Path(args.out) if args.out else gen_dir / "thermalization"
    out_dir.mkdir(parents=True, exist_ok=True)
    cases = [v.strip() for v in args.cases.split(",") if v.strip()]

    for i, run_id in enumerate(cases):
        if not args.plot_only and not (out_dir / f"{run_id}_series.npz").exists():
            set_seed(4321 + i)
            run_case(run_id, gen_dir, out_dir, args.n_traj, args.n_chains,
                     args.action_type, "cpu")
        elif not args.plot_only:
            print(f"=== {run_id}: cached series found, replotting only ===", flush=True)
        plot_case(out_dir, run_id, args.chain)

    for run_id in cases:
        summary = json.loads((out_dir / f"{run_id}_summary.json").read_text(encoding="utf-8"))
        t = summary["t_therm"]
        fmt = lambda v: "never" if v is None or math.isinf(v) else f"{v:.0f}"
        print(f"{run_id} (L={summary['lattice_size']}, beta={summary['beta']:g}): "
              + "; ".join(f"{name}: seed {fmt(t['diffusion seed'][name])} / "
                          f"cold {fmt(t['cold start'][name])} / hot {fmt(t['hot start'][name])}"
                          for name in summary["targets"]))


if __name__ == "__main__":
    main()
