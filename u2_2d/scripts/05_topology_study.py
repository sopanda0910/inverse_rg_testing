"""Stage 05: the economics of topology in 2D U(2).

Reproduces the study's U(2)-specific result. Four measurements, all against the
exact determinant-sector answers:

  A. exact P(Q) vs local sampling -- validates `lgt.exact` and the charge definition.
  B. global winding acceptance at charge step 2 (purely central, O(beta/V)) and at
     charge step 1 (must drag the SU(2) sector across a -1 monodromy).
  C. the cost of a forced sector change: the action defect left by
     `set_topological_charge`, and what the EXACT conditional SU(2) sampler
     removes from it. This is the route the diffusion ladder takes.
  D. topological freezing of plain HMC, with and without the winding move.

The headline is B vs C: the classical global move at odd charge is intrinsically
expensive in U(2) (and is not in U(1)), while the generative route pays only the
physical free-energy cost of the sector.

Run:  python u2_2d/scripts/05_topology_study.py --out-dir out/u2_2d/topology
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u2_2d.lgt.actions import WilsonU2Action
from u2_2d.lgt.exact import det_topological_charge_distribution, det_topological_susceptibility
from u2_2d.lgt.hmc import BatchedHMCU2, adapted_hmc_params
from u2_2d.lgt.lattice import identity_links, topological_charge
from u2_2d.lgt.local_updates import (
    conditional_su2_sweeps,
    retherm_sweeps,
    set_topological_charge,
    winding_update,
)
from u2_2d.utils import configure_device, save_json, set_seed


def sector_histogram(beta: float, size: int, n_chains: int, n_draws: int,
                     burn_in: int) -> dict:
    action = WilsonU2Action(beta)
    state = retherm_sweeps(identity_links(size, batch=n_chains), action, burn_in,
                           topological_updates=True)
    charges = []
    for _ in range(n_draws):
        state = retherm_sweeps(state, action, 2, topological_updates=True)
        charges.append(topological_charge(state).numpy())
    charges = np.concatenate(charges)
    q_values, probs = det_topological_charge_distribution(beta, size)
    rows = []
    for q, p in zip(q_values, probs):
        if p < 1e-4:
            continue
        measured = float(np.mean(charges == q))
        # Binomial error under the NULL probability p, not under the observed
        # frequency: an unobserved rare sector has zero observed variance and would
        # otherwise report an arbitrarily large z.
        error = float(np.sqrt(max(p * (1 - p), 1e-12) / len(charges)))
        rows.append({"Q": int(q), "measured": measured, "error": error, "exact": float(p)})
    return {
        "beta": beta, "lattice_size": size, "n_samples": int(len(charges)),
        "q_squared": float((charges**2).mean()),
        "q_squared_exact": float((q_values.astype(float) ** 2 * probs).sum()),
        "sectors": rows,
    }


def winding_economics(beta: float, size: int, n_chains: int, burn_in: int) -> dict:
    action = WilsonU2Action(beta)
    state = retherm_sweeps(identity_links(size, batch=n_chains, dtype=torch.float64),
                           action, burn_in)
    record = {"beta": beta, "lattice_size": size,
              "expected_central_cost": 2.0 * np.pi**2 * beta / size**2}
    for step in (2, 1):
        proposed, accept = winding_update(state, action, charge_step=step)
        delta_q = topological_charge(proposed) - topological_charge(state)
        forced = set_topological_charge(state, topological_charge(state) + step)
        cost = float((action.per_config(forced) - action.per_config(state)).mean())
        record[f"charge_step_{step}"] = {
            "acceptance": float(accept.double().mean()),
            "sectors_reached": sorted({int(v) for v in delta_q.tolist()}),
            "forced_cost": cost,
        }
    # C: what the exact conditional SU(2) sampler removes from a forced odd move.
    forced = set_topological_charge(state, topological_charge(state) + 1)
    before = float((action.per_config(forced) - action.per_config(state)).mean())
    relaxed = conditional_su2_sweeps(forced, action, 25)
    after = float((action.per_config(relaxed) - action.per_config(state)).mean())
    record["ladder_route"] = {
        "cost_before_conditional_su2": before,
        "cost_after_conditional_su2": after,
        "sector_preserved": bool(torch.equal(topological_charge(relaxed),
                                             topological_charge(forced))),
    }
    return record


def freezing(beta: float, size: int, n_chains: int, n_traj: int, device: str) -> dict:
    out = {"beta": beta, "lattice_size": size,
           "q_squared_exact": det_topological_susceptibility(beta, size) * size * size}
    step_size, n_steps = adapted_hmc_params(beta)
    for label, topological in (("hmc", False), ("hmc+winding", True)):
        sampler = BatchedHMCU2(size, WilsonU2Action(beta), n_chains=n_chains,
                               n_steps=n_steps, step_size=step_size, device=device,
                               topological_updates=topological)
        state = sampler.initialize()
        for _ in range(n_traj // 4):
            state, _ = sampler.metropolis_step(state)
        series, accepted = [], 0
        for _ in range(n_traj):
            state, accept = sampler.metropolis_step(state)
            accepted += int(accept.sum())
            series.append(topological_charge(state).cpu().numpy())
        series = np.stack(series)
        changes = int((np.diff(series, axis=0) != 0).sum())
        out[label] = {
            "acceptance": accepted / (n_traj * n_chains),
            "sector_changes": changes,
            "changes_per_trajectory": changes / (n_traj * n_chains),
            "q_squared": float((series**2).mean()),
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="out/u2_2d/topology")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--quick", action="store_true", help="smaller statistics")
    args = parser.parse_args()

    print(configure_device(args.device))
    set_seed(2026)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    scale = 0.25 if args.quick else 1.0

    results: dict = {}
    t0 = time.time()

    print("\nA. exact P(Q) vs local sampling")
    results["sector_histograms"] = []
    for beta, size in ((2.0, 6), (5.0, 6), (8.0, 6)):
        record = sector_histogram(beta, size, n_chains=48,
                                  n_draws=int(200 * scale), burn_in=150)
        results["sector_histograms"].append(record)
        worst = max(abs(r["measured"] - r["exact"]) / max(r["error"], 1e-9)
                    for r in record["sectors"])
        print(f"  beta={beta:5g} L={size}: <Q^2> {record['q_squared']:.4f} vs exact "
              f"{record['q_squared_exact']:.4f}   worst sector z = {worst:.2f}")

    print("\nB/C. winding economics (even is central and cheap; odd is not)")
    results["winding"] = []
    for beta, size in ((8.0, 8), (20.0, 8), (20.0, 16)):
        record = winding_economics(beta, size, n_chains=32, burn_in=120)
        results["winding"].append(record)
        even, odd, route = (record["charge_step_2"], record["charge_step_1"],
                            record["ladder_route"])
        print(f"  beta={beta:5g} L={size:2d}: dQ=2 accept {even['acceptance']:.3f} "
              f"(forced cost {even['forced_cost']:6.1f}, expected "
              f"{record['expected_central_cost']:.1f}) | "
              f"dQ=1 accept {odd['acceptance']:.3f} (forced cost {odd['forced_cost']:6.1f}) | "
              f"ladder route {route['cost_before_conditional_su2']:6.1f} -> "
              f"{route['cost_after_conditional_su2']:5.1f}")

    print("\nD. topological freezing of HMC")
    results["freezing"] = []
    for beta, size in ((8.0, 8), (20.0, 8), (56.0, 8)):
        record = freezing(beta, size, n_chains=16, n_traj=int(400 * scale),
                          device=args.device)
        results["freezing"].append(record)
        plain, winding = record["hmc"], record["hmc+winding"]
        print(f"  beta={beta:5g} L={size}: plain HMC {plain['sector_changes']:5d} changes, "
              f"<Q^2>={plain['q_squared']:.3f} | +winding "
              f"{winding['sector_changes']:5d} changes, <Q^2>={winding['q_squared']:.3f} | "
              f"exact {record['q_squared_exact']:.3f}")

    results["seconds"] = time.time() - t0
    save_json(out_dir / "topology_study.json", results)
    print(f"\nwrote {out_dir / 'topology_study.json'}  [{results['seconds']:.0f}s]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
