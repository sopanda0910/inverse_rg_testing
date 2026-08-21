"""Generate the CLASSICAL arms at a frozen coupling, unseeded, and save them.

WHY THIS EXISTS. Every HMC reference in `out/u2_2d/data/` above the parity
boundary carries `seed_exact_sectors: true` -- its chains are STARTED from
sectors drawn out of the exact P(Q). That is deliberate and it is the right
choice for a reference used to score Wilson loops, but it makes the ensemble
useless for the one question this study is actually about:

    when standard HMC is FROZEN, is a diffusion configuration a good seed?

A seeded reference cannot show freezing, because its topology was installed
rather than sampled. Comparing a generated P(Q) against it proves nothing, and
labelling its bar "HMC reference" in a figure invites precisely the wrong
conclusion. `06_figures.py` now hatches that bar for the same reason.

So this script builds the honest classical arms at a frozen coupling: cold start,
NO sector seeding, and the three sampler strengths that matter.

    frozen        plain HMC. At L = 64, beta = 416.5 this does not change sector
                  even once -- measured, 0 changes in 400 trajectories, <Q^2>
                  identically 0.000 against an exact 1.0012 (stage 08 arm B).
                  This is the failure the method exists to address.
    winding       HMC + the central (dQ = 2) move. Mobile in charge, but it
                  CANNOT change parity by construction, so it reaches even
                  sectors and stops: coverage 0.507 with zero odd sectors.
    winding_odd   HMC + the marginal odd move (docs/INSTANTON.md). Genuinely
                  ergodic -- this is the strongest classical baseline that
                  exists for this theory, and the one the method must be
                  compared against for the comparison to be honest.

The ensembles are written to disk so the distribution figures can use them
directly instead of the seeded reference.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u2_2d.lgt.actions import WilsonU2Action
from u2_2d.lgt.exact import (
    det_topological_charge_distribution,
    plaquette_exact,
)
from u2_2d.lgt.hmc import BatchedHMCU2, adapted_hmc_params
from u2_2d.lgt.lattice import half_retr, plaquette, topological_charge
from u2_2d.utils import configure_device, resolve_device, save_ensemble, save_json, set_seed

ARMS = {
    "frozen": dict(topological_updates=False, winding_charge_step=2, winding_interval=1),
    "winding": dict(topological_updates=True, winding_charge_step=2, winding_interval=1),
    "winding_odd": dict(topological_updates=True, winding_charge_step=1, winding_interval=5),
}


def run_arm(name: str, size: int, beta: float, args, device: str) -> dict:
    action = WilsonU2Action(beta)
    step_size, n_steps = adapted_hmc_params(beta)
    cfg = ARMS[name]
    sampler = BatchedHMCU2(size, action, n_chains=args.n_chains, n_steps=n_steps,
                           step_size=step_size, device=device, hot_start=False,
                           **cfg)
    links = sampler.initialize(hot=False)

    q_trace, t0 = [], time.time()
    changes = flips = 0
    prev = topological_charge(links).round()
    for step in range(args.n_traj):
        links, _ = sampler.metropolis_step(links)
        if step % args.record_every == 0:
            q = topological_charge(links).round()
            changes += int((q != prev).sum())
            flips += int(((q.long() % 2) != (prev.long() % 2)).sum())
            prev = q
            q_trace.append(q.cpu().tolist())

    # Draw the ensemble from the equilibrated tail.
    configs = []
    for _ in range(max(1, args.n_configs // args.n_chains)):
        for _ in range(args.thin):
            links, _ = sampler.metropolis_step(links)
        configs.append(links.detach().cpu().clone())
    ensemble = torch.cat(configs, dim=0)[:args.n_configs]

    with torch.no_grad():
        q = topological_charge(ensemble).round()
        plaq = float(half_retr(plaquette(ensemble)).mean())
    exact = plaquette_exact(beta, size)
    qs, ps = det_topological_charge_distribution(beta, size)
    q2_exact = float((qs ** 2 * ps).sum())

    record = {
        "arm": name,
        "lattice_size": size,
        "beta": beta,
        "n_configs": int(ensemble.shape[0]),
        "n_chains": args.n_chains,
        "n_traj": args.n_traj,
        "seconds": time.time() - t0,
        "plaquette": plaq,
        "plaquette_exact": exact,
        "plaquette_rel_err": plaq / exact - 1.0,
        "q_squared": float((q ** 2).mean()),
        "q_squared_exact": q2_exact,
        "sector_changes": changes,
        "parity_flips": flips,
        "sectors_visited": sorted({int(v) for row in q_trace for v in row}),
        "q_trace": q_trace,
    }
    print(f"  {name:12s} plaq {plaq:.6f} (rel {record['plaquette_rel_err']:+.2e})  "
          f"<Q^2> {record['q_squared']:.3f} (exact {q2_exact:.3f})  "
          f"changes {changes}  parity flips {flips}  "
          f"[{record['seconds']:.0f}s]", flush=True)
    return record, ensemble


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default=None)
    parser.add_argument("--lattice-size", type=int, default=64)
    parser.add_argument("--beta", type=float, default=416.524)
    parser.add_argument("--n-chains", type=int, default=64)
    parser.add_argument("--n-traj", type=int, default=400)
    parser.add_argument("--n-configs", type=int, default=256)
    parser.add_argument("--thin", type=int, default=5)
    parser.add_argument("--record-every", type=int, default=5)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--arms", nargs="+", default=list(ARMS))
    parser.add_argument("--out-dir", default="out/u2_2d/freezing_arms")
    args = parser.parse_args()

    device = resolve_device({"device": args.device or "auto"})
    print(configure_device(device))
    set_seed(args.seed)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    size, beta = args.lattice_size, args.beta
    print(f"classical arms at L={size}, beta={beta:g}, cold start, NO sector seeding")

    records = []
    for name in args.arms:
        record, ensemble = run_arm(name, size, beta, args, device)
        save_ensemble(out / f"u2_L{size}_beta{beta:g}_{name}.pt", ensemble,
                      {"arm": name, "beta": beta, "lattice_size": size})
        records.append(record)
    save_json(out / "freezing_arms.json", records)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
