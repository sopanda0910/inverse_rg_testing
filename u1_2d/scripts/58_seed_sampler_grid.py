"""Stage 58: the seed x sampler grid, {plain HMC, instanton HMC} x {diffusion,
cold, hot}.

The gap this closes. Stage 05 compares the diffusion seed against fresh hot and
cold starts under PLAIN HMC, and stage 14 compares an instanton-HMC chain against
the diffusion pipeline's cost per configuration. Neither runs the diffusion seed
under instanton HMC, so the only cross-sampler statement available is "diffusion
seed under plain HMC vs cold start under instanton HMC" -- which varies the seed
AND the algorithm at once and isolates neither.

It also handicaps the seed. The instanton update is a genuine global move in
U(1): a classical arm that starts in the wrong topological sector can hop out,
and denying the diffusion arm the same move means a seed whose Q distribution is
slightly off has no way to correct while its competitor does.

So run the full grid and report the two samplers as separate blocks. Within a
block only the starting configuration varies, which is the claim being made:

              diffusion      cold      hot
  plain HMC       A            B         C
  instanton       D            E         F

READ BY ROW, NEVER DIAGONALLY.

Arm D is also the sharper diagnostic. Under plain HMC a seed's Q never moves at
large beta, so arm A cannot distinguish "the model got P(Q) right" from "the
chain is frozen wherever the model put it". Under instanton HMC the charge is
free to move, so if <Q^2> holds steady over the run the distribution was right,
and if it drifts it was not.

This is deliberately a separate script rather than a change to stage 05: 05
feeds several tracked appendix figures, and this grid is additive.

    python u1_2d/scripts/58_seed_sampler_grid.py --cases 32:14.1464 32:55.0237
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u1_2d.lgt.actions import WilsonAction
from u1_2d.lgt.exact import topological_charge_distribution
from u1_2d.lgt.hmc import BatchedHMC, adapted_hmc_params
from u1_2d.lgt.lattice import topological_charge
from u1_2d.utils import (configure_device, load_config, load_ensemble,
                         resolve_device, save_json, set_seed)


def _load_stage05():
    """Import stage 05 for run_relaxation / thermalization_time / exact_targets.

    Same trick `37_tiling_baseline.py` uses: the module name starts with a digit,
    so it cannot be imported normally, and reimplementing t_therm here would let
    the two drift apart -- which is the whole point of reusing 05's criterion.
    """
    path = Path(__file__).resolve().parent / "05_hmc_thermalization.py"
    spec = importlib.util.spec_from_file_location("stage05", path)
    mod = importlib.util.module_from_spec(spec)
    saved, sys.argv = sys.argv, ["stage05"]
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.argv = saved
    return mod


def _q_stats(theta: torch.Tensor) -> tuple[float, float]:
    q = topological_charge(theta).double()
    return float(q.mean()), float((q**2).mean())


def run_grid_arm(m5, name: str, lattice_size: int, action, initial: torch.Tensor,
                 n_traj: int, step_size: float, n_steps: int, device: str,
                 topological: bool, targets: dict) -> dict:
    """One cell of the grid. `topological` selects the sampler row."""
    sampler = BatchedHMC(lattice_size, action, n_chains=initial.shape[0],
                         n_steps=n_steps, step_size=step_size, device=device,
                         topological_updates=topological)
    theta = initial.clone().to(device)
    series = {k: [v] for k, v in m5.chain_observables(theta).items()}
    q_series = [topological_charge(theta).double().cpu().numpy()]
    accepted = total = 0
    t0 = time.time()
    with torch.no_grad():
        for _ in range(n_traj):
            theta, accept = sampler.metropolis_step(theta)
            accepted += int(accept.sum())
            total += accept.numel()
            for k, v in m5.chain_observables(theta).items():
                series[k].append(v)
            q_series.append(topological_charge(theta).double().cpu().numpy())
    secs = time.time() - t0
    series = {k: np.stack(v) for k, v in series.items()}
    q_series = np.stack(q_series)

    t_therm = {}
    for obs, target in targets.items():
        if obs in series:
            t = m5.thermalization_time(series[obs], target)
            t_therm[obs] = None if math.isinf(t) else float(t)
    finite = [v for v in t_therm.values() if v is not None]

    q_mean, q_sq = _q_stats(theta)
    # Q mobility: how often the charge actually moved. Under plain HMC at large
    # beta this is zero by construction, which is exactly why the plain row
    # cannot certify a seed's P(Q).
    changes = int((np.diff(q_series.round(), axis=0) != 0).sum())
    return {
        "arm": name,
        "topological_updates": topological,
        "n_chains": int(initial.shape[0]),
        "n_traj": n_traj,
        "t_therm": t_therm,
        "t_therm_slowest": (None if len(finite) < len(t_therm) else max(finite)),
        "acceptance": accepted / max(total, 1),
        "seconds": secs,
        "q_mean_final": q_mean,
        "q_squared_final": q_sq,
        "q_squared_initial": float((q_series[0] ** 2).mean()),
        "q_changes": changes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="u1_2d/configs/v3_scale.yaml")
    parser.add_argument("--cases", nargs="+", default=["32:14.1464", "32:55.0237"],
                        help="L:beta pairs; the ladder ensemble supplies the seed")
    parser.add_argument("--seed-dirs", nargs="+",
                        default=["out/u1_2d/ladder",
                                 "out/u1_2d/generalization/generated",
                                 "out/u1_2d/thermalization_volume"],
                        help="searched in order for a generated ensemble at "
                             "the case's (L, beta); the u1 ladder ensembles "
                             "were pruned in 2026-08-18, so the generalization "
                             "outputs are the surviving diffusion seeds")
    parser.add_argument("--out-dir", default="out/u1_2d/seed_sampler_grid")
    parser.add_argument("--n-traj", type=int, default=400)
    parser.add_argument("--n-chains", type=int, default=64)
    parser.add_argument("--device", default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    if args.device:
        config["device"] = args.device
    device = resolve_device(config)
    print(configure_device(device))
    set_seed(int(config.get("seed", 0)) + 5858)

    m5 = _load_stage05()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    seed_dirs = [Path(d) for d in args.seed_dirs]

    results = []
    for case in args.cases:
        size_s, beta_s = case.split(":")
        size, beta = int(size_s), float(beta_s)
        action = WilsonAction(beta)
        step_size, n_steps = adapted_hmc_params(beta, 0.2, 5)
        targets = m5.exact_targets(beta, "wilson", size)

        seed_path = None
        for d in seed_dirs:
            if not d.exists():
                continue
            cands = sorted(c for c in d.rglob(f"*L{size}_beta{beta:g}*.pt")
                           if "final" not in c.name)
            if cands:
                seed_path = cands[0]
                break
        if seed_path is None:
            print(f"no generated ensemble for L={size} beta={beta:g} in "
                  + ", ".join(str(d) for d in seed_dirs) + " -- skipping")
            continue
        seed, _ = load_ensemble(seed_path)
        n = min(args.n_chains, seed.shape[0])
        seed = seed[:n]

        print(f"\n=== L={size} beta={beta:g}  ({n} chains x {args.n_traj} traj) ===")
        print(f"  seed from {seed_path.name}")

        base = BatchedHMC(size, action, n_chains=n, device=device)
        starts = {
            "diffusion": lambda: seed,
            "cold": lambda: base.initialize(hot=False),
            "hot": lambda: base.initialize(hot=True),
        }

        case_rows = []
        for topological in (False, True):
            row = "instanton" if topological else "plain"
            for seed_name, start_fn in starts.items():
                name = f"{row}_{seed_name}"
                cache = out_dir / f"L{size}_beta{beta:g}_{name}.json"
                if cache.exists():
                    rec = json.loads(cache.read_text(encoding="utf-8"))
                    print(f"  {name:<22} reused from {cache.name}")
                else:
                    rec = run_grid_arm(m5, name, size, action, start_fn(),
                                       args.n_traj, step_size, n_steps, device,
                                       topological, targets)
                    cache.write_text(json.dumps(rec, indent=2), encoding="utf-8")
                slow = rec["t_therm_slowest"]
                shown = f"> {args.n_traj}" if slow is None else f"{slow:.0f}"
                print(f"  {name:<22} t_therm {shown:<7} "
                      f"acc {rec['acceptance']:.3f}  "
                      f"<Q^2> {rec['q_squared_initial']:.3f} -> "
                      f"{rec['q_squared_final']:.3f}  "
                      f"Q-changes {rec['q_changes']}")
                case_rows.append(rec)

        q_vals, q_probs = topological_charge_distribution(beta, size, "wilson")
        results.append({
            "lattice_size": size,
            "beta": beta,
            "seed_source": seed_path.name,
            "q_squared_exact": float((q_vals.astype(float) ** 2 * q_probs).sum()
                                     / q_probs.sum()),
            "arms": case_rows,
        })

    if results:
        save_json(out_dir / "seed_sampler_grid.json", results)
        (out_dir / "report.md").write_text(_render(results), encoding="utf-8")
        print(f"\nwrote {out_dir / 'seed_sampler_grid.json'} and report.md")
    return 0


def _render(results: list) -> str:
    lines = [
        "# Seed x sampler grid",
        "",
        "{plain HMC, instanton HMC} x {diffusion seed, cold, hot}. Within a "
        "sampler block only the starting configuration varies; **read by row, "
        "never diagonally**. Comparing the diffusion seed under plain HMC "
        "against a cold start under instanton HMC changes the seed and the "
        "algorithm at once and isolates neither.",
        "",
    ]
    for rec in results:
        lines += [
            f"## $L = {rec['lattice_size']}$, "
            r"$\beta$ = " f"{rec['beta']:g}",
            "",
            f"Seed ensemble `{rec['seed_source']}`. Exact "
            r"$\langle Q^2\rangle$ = " f"{rec['q_squared_exact']:.4f}.",
            "",
            "| sampler | seed | $t_{\\rm therm}$ | acceptance | "
            r"$\langle Q^2\rangle$ start | end | $Q$ changes |",
            "|---|---|---|---|---|---|---|",
        ]
        for a in rec["arms"]:
            row, seed = a["arm"].split("_", 1)
            slow = a["t_therm_slowest"]
            shown = f"> {a['n_traj']}" if slow is None else f"{slow:.0f}"
            bold = "**" if seed == "diffusion" else ""
            lines.append(
                f"| {row} | {bold}{seed}{bold} | {shown} | "
                f"{a['acceptance']:.3f} | {a['q_squared_initial']:.3f} | "
                f"{a['q_squared_final']:.3f} | {a['q_changes']} |")
        lines += [
            "",
            "The `Q changes` column is the point of the instanton block: under "
            "plain HMC at these couplings the charge never moves, so that row "
            "cannot certify a seed's $P(Q)$ -- it can only report where the seed "
            "started. Under instanton HMC the charge is free, so a seed whose "
            r"$\langle Q^2\rangle$ holds steady had the distribution right, and "
            "one that drifts did not.",
            "",
        ]
    lines.append("Source: `u1_2d/scripts/58_seed_sampler_grid.py`.")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
