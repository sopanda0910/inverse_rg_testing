"""Can the ANALYTIC score rescue the lift past the top training rung?

THE PROBLEM. `28_crossover_scan.py` finds the diffusion seed dead -- t_therm inf
on every local observable -- at every coupling more than ~29% in model beta above
the highest training rung (104.13). It is alive and often far better than any
classical arm below that. So the method currently has a hard coverage ceiling,
and raising it by training higher is exactly the move that is suspect: every
training rung above model beta 12.9 carries `seed_exact_sectors: true`, i.e. its
topology is INSTALLED from the closed form because HMC is frozen there. That
crutch exists only because 2D U(2) is solvable.

THE CHEAP ALTERNATIVE, already implemented and switched off everywhere.
`pipeline/ladder.py` accepts `physics_blend_coef`, which mixes the EXACT
det-sector score into the learned one with weight w = 1/(1 + (sigma/sigma_c)^2),
sigma_c = coef / sqrt(beta_model) -- so the analytic term dominates at small
sigma and the network at large sigma. The analytic score is exact at ANY beta and
has no training range. If the failure past the ceiling is the learned score going
wrong in the near-deterministic regime, the blend should recover it for free.

WHAT THIS MEASURES, and why it is not the scan. Running the full t_therm scan
costs hours per coupling. The raw lift is the thing the blend can actually
change, so it is measured directly: relative deviation of the plaquette and the
small Wilson loops against the closed form, PRE-rethermalization, blend off vs
blend on. If the blend does not move the raw lift there is nothing for the full
scan to find, and this costs minutes instead of hours.

Couplings: two past the ceiling (where the seed is dead), one just inside it as a
control (the blend must not DAMAGE a coupling that already works), and one
out-of-sample mid-gap point.

    python u2_2d/scripts/35_physics_blend_probe.py --device cuda
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u2_2d.lgt.blocking import topology_matched_fine_beta
from u2_2d.lgt.exact import plaquette_exact, wilson_loop_exact
from u2_2d.lgt.lattice import half_retr, plaquette, topological_charge, wilson_loop
from u2_2d.model.det_lift import load_det_model, model_beta
from u2_2d.pipeline.ladder import generate_fine_from_coarse
from u2_2d.utils import (configure_device, load_ensemble, resolve_device,
                         save_json, set_seed)

LOOPS = [(1, 1), (2, 2), (4, 4)]


def score_lift(links: torch.Tensor, beta: float, size: int) -> dict:
    out = {}
    with torch.no_grad():
        for nx, ny in LOOPS:
            v = (half_retr(plaquette(links)) if (nx, ny) == (1, 1)
                 else half_retr(wilson_loop(links, nx, ny)))
            v = v.mean(dim=(1, 2)).cpu().numpy().astype(float)
            exact = (plaquette_exact(beta, size) if (nx, ny) == (1, 1)
                     else wilson_loop_exact(beta, nx * ny))
            out[f"W{nx}x{ny}"] = float(v.mean() / exact - 1.0)
        q = topological_charge(links).round()
        out["q_squared"] = float((q ** 2).mean())
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--device", default="cuda")
    p.add_argument("--checkpoint",
                   default="out/u2_2d/checkpoints/det_score_net.pt")
    p.add_argument("--data-dir", default="out/u2_2d/data_v2")
    p.add_argument("--coarse-size", type=int, default=16)
    # Coarse betas whose matched fine beta lands: 264 (model 66, out of sample,
    # seed alive at t_therm 50), 415 (model 104, ON the top rung, the control),
    # 537 (model 134, +29% past it, seed DEAD), 791 (model 198, +90%, DEAD).
    p.add_argument("--coarse-betas", default="67.4077,105.244,135.861,199.229")
    p.add_argument("--blends", default="0.0,0.5,1.0,2.0")
    p.add_argument("--n-configs", type=int, default=64)
    p.add_argument("--sampler-steps", type=int, default=200)
    p.add_argument("--n-su2", type=int, default=30)
    p.add_argument("--seed", type=int, default=1234)
    p.add_argument("--out-dir", default="out/u2_2d/physics_blend_probe")
    args = p.parse_args()

    device = resolve_device({"device": args.device})
    print(configure_device(device))
    set_seed(args.seed)
    model, sched = load_det_model(args.checkpoint, device=device)
    print(f"checkpoint {args.checkpoint}\n")

    blends = [float(b) for b in args.blends.split(",")]
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    records = []

    for cb in [float(b) for b in args.coarse_betas.split(",")]:
        path = Path(args.data_dir) / f"u2_L{args.coarse_size}_beta{cb:g}.pt"
        if not path.exists():
            print(f"(skip) missing {path}")
            continue
        coarse, _ = load_ensemble(path)
        coarse = coarse[:args.n_configs]
        beta = topology_matched_fine_beta(cb, args.coarse_size)
        size = args.coarse_size * 2
        mb = model_beta(beta)
        # 104.132 is the highest training rung of the deployed checkpoint.
        print(f"L={size}  beta_f={beta:.2f}  model_beta={mb:.2f}  "
              f"({100*(mb/104.132-1):+.0f}% vs top training rung)")
        print(f"    {'blend':>7s} {'W1x1':>11s} {'W2x2':>11s} {'W4x4':>11s} "
              f"{'<Q^2>':>8s} {'s':>5s}")
        for coef in blends:
            t0 = time.time()
            fine = generate_fine_from_coarse(
                model, sched, coarse, beta, n_su2_sweeps=args.n_su2,
                device=device, n_sampler_steps=args.sampler_steps,
                n_corrector_steps=1, batch_size=32, consistency_weight=1.0,
                physics_blend_coef=coef)
            m = score_lift(fine.to(device), beta, size)
            m.update({"coarse_beta": cb, "beta": beta, "model_beta": mb,
                      "lattice_size": size, "physics_blend_coef": coef,
                      "seconds": time.time() - t0})
            records.append(m)
            save_json(out / "physics_blend_probe.json", records)
            print(f"    {coef:7.2f} {m['W1x1']:+11.3e} {m['W2x2']:+11.3e} "
                  f"{m['W4x4']:+11.3e} {m['q_squared']:8.3f} "
                  f"{m['seconds']:5.0f}")
        print()

    print("=" * 74)
    print("Relative deviation of the RAW lift (no rethermalization) against the")
    print("closed form. blend = 0 is the deployed setting. A blend that helps")
    print("past the ceiling AND does not damage the on-rung control is worth a")
    print("full t_therm scan; anything else is not.")
    print(f"\nwrote {out / 'physics_blend_probe.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
