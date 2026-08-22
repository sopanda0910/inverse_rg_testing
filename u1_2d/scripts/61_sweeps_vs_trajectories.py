"""Which move repairs the raw lift -- local sweeps, or HMC trajectories?

The u1 half of a test pair; the u2 half is `u2_2d/scripts/44_sweeps_vs_-
trajectories.py`, which found local sweeps beating trajectories by a factor of
~800 in link-touches. u1 should be asked the same question, because the answer
decides how the paper describes the tail.

THE SETUP. One lift, one set of configurations, cloned, and the same budget
spent two ways:

  * heatbath + overrelaxation sweeps (`retherm_sweeps`), and
  * HMC trajectories at the same coupling,

with a third arm running HMC from a COLD start as the stiffness reference, so a
slow seed arm cannot be mistaken for a bad seed when the coupling itself is
simply hard. Costs are matched in LINK TOUCHES rather than wall clock: one
trajectory with `n_steps` leapfrog steps touches every link `n_steps` times, and
one retherm sweep with two overrelaxation passes touches every link 3 times.
Reporting both raw counts and matched budget keeps the comparison honest in
either currency.

WHY IT MATTERS BEYOND BOOKKEEPING. u2's answer implies that the repair for an
out-of-coverage lift is cheap exact local sweeps rather than more trajectories,
and that "the seed does not thermalize" statements are about the MOVE and not
about the model. If u1 agrees, that becomes a statement about the method; if it
does not, the difference is a statement about the two theories and needs to be
in the paper as such.

Errors are tau_int-aware, as everywhere in u1 (NARRATIVE 25.7 / M4).

    python u1_2d/scripts/61_sweeps_vs_trajectories.py --device cpu
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u1_2d.lgt import make_action, run_hmc_ensemble
from u1_2d.lgt.blocking import approx_matched_fine_beta
from u1_2d.lgt.exact import wilson_loop_exact
from u1_2d.lgt.hmc import BatchedHMC, adapted_hmc_params
from u1_2d.lgt.lattice import (plaquette_angles, topological_charge,
                               wilson_loop_angles)
from u1_2d.lgt.local_updates import retherm_sweeps
from u1_2d.model.train import load_checkpoint
from u1_2d.pipeline.ladder import generate_fine_from_coarse
from u1_2d.utils import save_json, set_seed
from u1_2d.validate.stats import autocorr_aware_mean_err

LOOPS = [(1, 1), (2, 2), (4, 4)]


def zscores(field, beta, size, n_chains):
    out = {}
    with torch.no_grad():
        for nx, ny in LOOPS:
            ang = (plaquette_angles(field) if (nx, ny) == (1, 1)
                   else wilson_loop_angles(field, nx, ny))
            v = torch.cos(ang).mean(dim=(-2, -1)).cpu().numpy().astype(float)
            exact = wilson_loop_exact(beta, nx * ny, "wilson", size)
            mean, err, _ = autocorr_aware_mean_err(v, n_chains)
            out[f"W{nx}x{ny}"] = float(abs(mean - exact) / max(err, 1e-15))
        q = topological_charge(field).cpu().numpy().astype(float)
    out["q_squared"] = float((q ** 2).mean())
    return out


def slowest(rec):
    return max(rec[f"W{a}x{b}"] for a, b in LOOPS)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--checkpoint", default="out/u1_2d/checkpoints/score_net.pt")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--coarse-size", type=int, default=16)
    # in coverage, near the top of the training range, and past it
    ap.add_argument("--coarse-betas", default="14.1464,25.0,55.0237")
    ap.add_argument("--n-configs", type=int, default=128)
    ap.add_argument("--n-chains", type=int, default=16)
    ap.add_argument("--burn-in", type=int, default=800)
    ap.add_argument("--thin", type=int, default=5)
    ap.add_argument("--sampler-steps", type=int, default=200)
    ap.add_argument("--units", type=int, default=60)
    ap.add_argument("--record-every", type=int, default=2)
    ap.add_argument("--seed", type=int, default=5151)
    ap.add_argument("--out-dir", default="out/u1_2d/sweeps_vs_trajectories")
    args = ap.parse_args()

    device = args.device
    set_seed(args.seed)
    model, schedule = load_checkpoint(args.checkpoint, device)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    for cb in [float(b) for b in args.coarse_betas.split(",")]:
        beta = approx_matched_fine_beta(cb, "wilson")
        size = args.coarse_size * 2
        t0 = time.time()
        action_c = make_action("wilson", cb)
        step_c, nst_c = adapted_hmc_params(cb)
        coarse, _ = run_hmc_ensemble(
            args.coarse_size, action_c, n_configs=args.n_configs,
            n_chains=args.n_chains, burn_in=args.burn_in, thin=args.thin,
            step_size=step_c, n_steps=nst_c, device=device,
            topological_updates=True)
        fine = generate_fine_from_coarse(
            model, schedule, coarse.cpu(), beta, device=device,
            n_sampler_steps=args.sampler_steps, n_corrector_steps=1,
            batch_size=64, consistency_weight=1.0)
        print(f"\n{'='*72}\ncoarse beta={cb:g} -> fine beta={beta:.3f}, "
              f"L={size}, {fine.shape[0]} configs [{time.time()-t0:.0f}s]")

        action = make_action("wilson", beta)
        step_size, n_steps = adapted_hmc_params(beta)
        cost = {"sweeps": 3.0, "trajectories": float(n_steps)}
        print(f"  HMC: n_steps={n_steps}, step_size={step_size:.4f}   "
              f"cost/unit: sweep 3, traj {n_steps} link-touches")

        hmc = BatchedHMC(args.coarse_size * 2, action,
                         n_chains=fine.shape[0], n_steps=n_steps,
                         step_size=step_size, device=device,
                         topological_updates=False)

        arms = {}
        st = fine.clone()
        series = [{"unit": 0, **zscores(st, beta, size, args.n_chains)}]
        for u in range(args.record_every, args.units + 1, args.record_every):
            st = retherm_sweeps(st, action, args.record_every)
            series.append({"unit": u, **zscores(st, beta, size, args.n_chains)})
        arms["seed_sweeps"] = series

        st = fine.clone()
        series = [{"unit": 0, **zscores(st, beta, size, args.n_chains)}]
        for u in range(args.record_every, args.units + 1, args.record_every):
            for _ in range(args.record_every):
                st, _ = hmc.metropolis_step(st)
            series.append({"unit": u, **zscores(st, beta, size, args.n_chains)})
        arms["seed_trajectories"] = series

        st = hmc.initialize(hot=False)
        series = [{"unit": 0, **zscores(st, beta, size, args.n_chains)}]
        for u in range(args.record_every, args.units + 1, args.record_every):
            for _ in range(args.record_every):
                st, _ = hmc.metropolis_step(st)
            series.append({"unit": u, **zscores(st, beta, size, args.n_chains)})
        arms["cold_trajectories"] = series

        def first_below(series, thresh=2.0):
            for r in series:
                if slowest(r) <= thresh:
                    return r["unit"]
            return None

        rec = {"coarse_beta": cb, "beta": beta, "lattice_size": size,
               "n_configs": int(fine.shape[0]), "n_chains": args.n_chains,
               "n_steps": n_steps, "cost_per_unit": cost, "arms": arms,
               "units_to_z2": {k: first_below(v) for k, v in arms.items()}}
        rows.append(rec)
        save_json(out / "sweeps_vs_trajectories.json", rows)

        print(f"  {'arm':<20s} {'units to |z|<=2':>15s} {'link-touches':>13s} "
              f"{'|z| at end':>11s}")
        for k, v in arms.items():
            u = rec["units_to_z2"][k]
            c = cost["sweeps"] if k.endswith("sweeps") else cost["trajectories"]
            print(f"  {k:<20s} {str(u) if u is not None else 'never':>15s} "
                  f"{(u * c) if u is not None else float('nan'):13.0f} "
                  f"{slowest(v[-1]):11.2f}")

    print(f"\n{'='*72}\nVERDICT")
    won = sum(1 for r in rows
              if r["units_to_z2"]["seed_sweeps"] is not None
              and (r["units_to_z2"]["seed_trajectories"] is None
                   or r["units_to_z2"]["seed_sweeps"] * r["cost_per_unit"]["sweeps"]
                   < r["units_to_z2"]["seed_trajectories"] * r["cost_per_unit"]["trajectories"]))
    print(f"  local sweeps cheaper than trajectories at {won}/{len(rows)} couplings")
    print("  Compare u2 (`44_sweeps_vs_trajectories.py`): 6 link-touches against")
    print("  4600. If u1 agrees, the statement is about the MOVE and belongs in")
    print("  the method section; if not, it is a difference between the theories.")
    print(f"\nwrote {out / 'sweeps_vs_trajectories.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
