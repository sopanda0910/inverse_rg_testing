"""tau_int-aware benchmark against the published classical remedies.

Referee objection 5 (docs/NARRATIVE.md sec 25): every speed claim in this study
is measured against periodic HMC, with and without instanton/winding updates.
The literature's actual remedies for topological freezing are open boundary
conditions (Luscher & Schaefer 2011) and parallel tempering in boundary
conditions (Hasenbusch 2017; Bonanno, Bonati & D'Elia 2021, which reports two
orders of magnitude in tau(Q^2)). If PTBC removes the freezing this method
exists to avoid, a referee can argue the method is not needed. So it has to be
measured, not cited.

Four arms at matched beta and volume, all on the same lattice:

  hmc         periodic HMC, no topological moves          -- the frozen baseline
  hmc+inst    periodic HMC + instanton/winding update     -- the study's baseline
  ptbc        R replicas, defect coupling 1 -> 0, swaps   -- Hasenbusch
  open        open boundary in x                          -- Luscher-Schaefer

Scored on **seconds per independent configuration**, which is the only
comparison that is fair across methods with different per-trajectory costs:

    cost = 2 * tau_int(Q^2) * (wall seconds / trajectory)

PTBC's per-trajectory cost is charged for ALL R replicas, since they must all
be evolved; quoting the physical replica alone would flatter it by R.

Two honesty notes carried from the rest of the study:
  * tau_int has a floor of 0.5 (an uncorrelated series). A frozen chain does
    not report a large tau_int -- it reports a *small* one, because a constant
    series has no fluctuation to decorrelate. Q-variance is therefore reported
    alongside, and a chain that never changed sector is flagged rather than
    credited.
  * Open boundaries change the theory: Q is not an integer and the periodic
    exact P(Q) does not apply. That arm is reported for tau_int only.

    .venv/Scripts/python.exe u1_2d/scripts/43_ptbc_benchmark.py \
        --betas 14.1464 55.0237 --L 32 --n-traj 3000
"""

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import torch

from u1_2d.lgt.actions import WilsonAction
from u1_2d.lgt.hmc import BatchedHMC, adapted_hmc_params
from u1_2d.lgt.lattice import topological_charge, topological_charge_float
from u1_2d.lgt.ptbc import (
    OpenBoundaryWilsonAction,
    StackedDefectWilsonAction,
    calibrated_c_ladder,
    geometric_c_ladder,
    refine_ladder_bottom,
    swap_replicas_stacked,
)
from u1_2d.utils import resolve_device, save_json
from u1_2d.validate.stats import integrated_autocorrelation_time

REPO = Path(__file__).resolve().parents[2]


def tau_of_series(q: np.ndarray) -> tuple[float, float, bool]:
    """tau_int of Q^2 per chain, averaged. Returns (tau, err, frozen).

    `frozen` marks a chain whose charge never moved: tau_int is meaningless
    there (a constant series has no autocorrelation to integrate) and must not
    be read as fast mixing.
    """
    taus, errs, moved = [], [], 0
    for b in range(q.shape[1]):
        s = q[:, b].astype(float) ** 2
        if s.std() > 0:
            moved += 1
            t, e = integrated_autocorrelation_time(s)
            taus.append(t)
            errs.append(e)
    if not taus:
        return float("nan"), float("nan"), True
    return (float(np.mean(taus)), float(np.mean(errs)),
            moved < q.shape[1] // 2)


def run_plain(L, beta, n_traj, n_chains, device, topological, seed):
    torch.manual_seed(seed)
    step, n_steps = adapted_hmc_params(beta, 0.2, 5)
    sampler = BatchedHMC(L, WilsonAction(beta), n_chains=n_chains, n_steps=n_steps,
                         step_size=step, device=device, hot_start=False,
                         topological_updates=topological)
    theta = sampler.initialize()
    qs = []
    t0 = time.time()
    with torch.no_grad():
        for _ in range(n_traj):
            theta, _ = sampler.metropolis_step(theta)
            qs.append(topological_charge(theta).cpu().numpy())
    return np.stack(qs), (time.time() - t0) / n_traj, 1


def run_open(L, beta, n_traj, n_chains, device, seed):
    torch.manual_seed(seed)
    step, n_steps = adapted_hmc_params(beta, 0.2, 5)
    sampler = BatchedHMC(L, OpenBoundaryWilsonAction(beta, L), n_chains=n_chains,
                         n_steps=n_steps, step_size=step, device=device,
                         hot_start=False, topological_updates=False)
    theta = sampler.initialize()
    qs = []
    t0 = time.time()
    with torch.no_grad():
        for _ in range(n_traj):
            theta, _ = sampler.metropolis_step(theta)
            # non-integer under open boundaries -- kept as float deliberately
            qs.append(topological_charge_float(theta).cpu().numpy())
    return np.stack(qs), (time.time() - t0) / n_traj, 1


def calibrate_ladder(L, beta, device, seed, n_replicas, defect_width,
                     n_grid=11, pilot_traj=200, defect_length=None,
                     refine_bottom=False):
    """Pilot the mean defect cos-sum on a c grid, then place the ladder.

    The whole c grid is piloted as one stacked ladder -- the grid points are
    independent, so there is no reason to run them one at a time.

    Costs a few percent of the benchmark and is the difference between a PTBC
    run that exchanges and one that does not.
    """
    torch.manual_seed(seed)
    step, n_steps = adapted_hmc_params(beta, 0.2, 5)
    c_grid = [i / (n_grid - 1) for i in range(n_grid)]
    action = StackedDefectWilsonAction(beta, L, c_grid, n_chains=2,
                                       defect_width=defect_width,
                                       defect_length=defect_length)
    sampler = BatchedHMC(L, action, n_chains=2 * n_grid, n_steps=n_steps,
                         step_size=step, device=device)
    th = sampler.initialize()
    vals = []
    with torch.no_grad():
        for t in range(pilot_traj):
            th, _ = sampler.metropolis_step(th)
            if t >= pilot_traj // 2:
                vals.append(action.defect_cos_sums(th).mean(dim=1).cpu().numpy())
    m_grid = list(np.mean(np.stack(vals), axis=0))
    cs = calibrated_c_ladder(c_grid, m_grid, n_replicas)
    if refine_bottom:
        cs = refine_ladder_bottom(cs, beta, defect_length or L)
    return cs, c_grid, m_grid


def run_ptbc(L, beta, n_traj, n_chains, device, seed, n_replicas, defect_width,
             translate, cs=None, defect_length=None):
    """Evolve the whole ladder in ONE batched HMC call per trajectory.

    The replica index is folded into the batch dimension (replica-major, so
    replica r owns rows r*n_chains : (r+1)*n_chains and the physical c = 1
    replica is the leading block). Advancing replicas one at a time, which is
    what this did originally, pays R kernel launches per trajectory for work
    that is latency-bound rather than throughput-bound at these volumes.
    """
    torch.manual_seed(seed)
    step, n_steps = adapted_hmc_params(beta, 0.2, 5)
    if cs is None:
        cs = geometric_c_ladder(n_replicas)
    R = len(cs)
    action = StackedDefectWilsonAction(beta, L, cs, n_chains=n_chains,
                                       defect_width=defect_width,
                                       defect_length=defect_length)
    sampler = BatchedHMC(L, action, n_chains=R * n_chains, n_steps=n_steps,
                         step_size=step, device=device, hot_start=False,
                         topological_updates=False)
    theta = sampler.initialize()
    qs, swap_acc = [], []
    t0 = time.time()
    with torch.no_grad():
        for t in range(n_traj):
            theta, _ = sampler.metropolis_step(theta)
            theta, acc = swap_replicas_stacked(theta, action, parity=t % 2)
            swap_acc.append(acc.mean(dim=1).cpu().numpy())
            if translate:
                # Move the defect so no site is permanently special; the
                # physical replica's action is unchanged by this (c = 1 there).
                action.move_defect_to((t + 1) % L)
            qs.append(topological_charge(theta[:n_chains]).cpu().numpy())
    # Pairs of the unproposed parity come back NaN, so this is an acceptance
    # per PROPOSAL, not per trajectory -- the quantity Hasenbusch's >30%
    # criterion refers to.
    return (np.stack(qs), (time.time() - t0) / n_traj, R,
            np.nanmean(np.stack(swap_acc), axis=0), cs)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--betas", nargs="+", type=float,
                    default=[14.1464, 55.0237, 218.58])
    ap.add_argument("--L", type=int, default=32)
    ap.add_argument("--n-traj", type=int, default=3000)
    ap.add_argument("--n-chains", type=int, default=4)
    ap.add_argument("--n-replicas", type=int, default=6)
    ap.add_argument("--defect-width", type=int, default=1)
    ap.add_argument("--defect-length", type=int, default=None,
                    help="l_d in Hasenbusch PRD 96 054504. None = full line "
                         "(the open-boundary limit), which that paper reports "
                         "as clearly outperformed by l_d ~ xi.")
    ap.add_argument("--refine-bottom", action="store_true",
                    help="resolve the last stretch of the ladder in beta*c "
                         "rather than c. Without it the final pair collapses "
                         "to ~0.05 acceptance at large beta however many "
                         "replicas the calibration is given.")
    ap.add_argument("--no-translate", action="store_true")
    ap.add_argument("--no-calibrate", action="store_true",
                    help="use the linear c ladder; it does not exchange at "
                         "these couplings and is here only for contrast")
    ap.add_argument("--arms", nargs="+",
                    default=["hmc", "hmc+inst", "ptbc", "open"],
                    choices=["hmc", "hmc+inst", "ptbc", "open"],
                    help="Arms differ in what hardware suits them -- the "
                         "single-replica arms are latency-bound on one small "
                         "batch and run faster on CPU, while the stacked PTBC "
                         "ladder saturates better on GPU. Run each on its own "
                         "best device and merge, rather than handicapping one.")
    ap.add_argument("--seed", type=int, default=20260815)
    ap.add_argument("--device", default=None)
    ap.add_argument("--out", default="out/u1_2d/ptbc_benchmark")
    args = ap.parse_args()

    device = resolve_device({"device": args.device or "auto"})
    out_dir = REPO / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []

    for beta in args.betas:
        print(f"\n=== L={args.L} beta={beta:g} ===", flush=True)
        arms = {}

        ladder_used = None
        if "hmc" in args.arms:
            q, spt, mult = run_plain(args.L, beta, args.n_traj, args.n_chains,
                                     device, False, args.seed)
            arms["hmc"] = (q, spt, mult, None)
        if "hmc+inst" in args.arms:
            q, spt, mult = run_plain(args.L, beta, args.n_traj, args.n_chains,
                                     device, True, args.seed + 1)
            arms["hmc+inst"] = (q, spt, mult, None)
        if "ptbc" in args.arms:
            cs = None
            if not args.no_calibrate:
                t_cal = time.time()
                cs, c_grid, m_grid = calibrate_ladder(
                    args.L, beta, device, args.seed + 9, args.n_replicas,
                    args.defect_width, defect_length=args.defect_length,
                    refine_bottom=args.refine_bottom)
                print(f"  calibrated ladder, {len(cs)} replicas "
                      f"({time.time() - t_cal:.0f}s): "
                      f"{[round(c, 4) for c in cs]}", flush=True)
            q, spt, mult, sacc, cs_used = run_ptbc(
                args.L, beta, args.n_traj, args.n_chains, device, args.seed + 2,
                args.n_replicas, args.defect_width, not args.no_translate, cs,
                defect_length=args.defect_length)
            arms["ptbc"] = (q, spt, mult, sacc)
            ladder_used = cs_used
        if "open" in args.arms:
            q, spt, mult = run_open(args.L, beta, args.n_traj, args.n_chains,
                                    device, args.seed + 3)
            arms["open"] = (q, spt, mult, None)

        for name, (q, spt, mult, sacc) in arms.items():
            tau, err, frozen = tau_of_series(q)
            cost = (2.0 * tau * spt * mult) if math.isfinite(tau) else float("nan")
            row = {
                "L": args.L, "beta": beta, "arm": name,
                "device": str(device), "n_chains": args.n_chains,
                "defect_length": (args.defect_length if name == "ptbc" else None),
                "refined_bottom": bool(args.refine_bottom) if name == "ptbc" else None,
                "tau_int_q2": tau, "tau_err": err,
                "frozen": bool(frozen),
                "q2_mean": float((q.astype(float) ** 2).mean()),
                "q_std": float(q.astype(float).std()),
                "n_sector_changes": int((np.diff(np.round(q), axis=0) != 0).sum()),
                "sec_per_traj": spt,
                "replicas_charged": mult,
                "sec_per_independent_config": cost,
                "swap_acceptance": (None if sacc is None
                                    else [round(float(x), 3) for x in sacc]),
                "c_ladder": ([round(float(c), 5) for c in ladder_used]
                             if name == "ptbc" else None),
            }
            rows.append(row)
            flag = "  [FROZEN - tau meaningless]" if frozen else ""
            print(f"  {name:9s} tau(Q^2)={tau:8.2f}  changes={row['n_sector_changes']:6d}"
                  f"  s/traj={spt:.4f}  s/indep={cost:8.2f}{flag}", flush=True)
            if sacc is not None:
                print(f"            swap acc per pair: "
                      f"{[round(float(x), 2) for x in sacc]}", flush=True)
        save_json(out_dir / "ptbc_benchmark.json", rows)

    print("\n| L | beta | arm | tau_int(Q^2) | sector changes | s/traj | "
          "replicas | s per independent config |")
    print("|---|---|---|---|---|---|---|---|")
    for r in rows:
        tau = "frozen" if r["frozen"] else f"{r['tau_int_q2']:.1f}"
        cost = "--" if r["frozen"] else f"{r['sec_per_independent_config']:.2f}"
        print(f"| {r['L']} | {r['beta']:g} | {r['arm']} | {tau} | "
              f"{r['n_sector_changes']} | {r['sec_per_traj']:.4f} | "
              f"{r['replicas_charged']} | {cost} |")
    print(f"\nwrote {(out_dir / 'ptbc_benchmark.json').relative_to(REPO)}")


if __name__ == "__main__":
    main()
