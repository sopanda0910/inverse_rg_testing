"""Reconcile the two rethermalization measurements that disagree.

THE DISAGREEMENT. At L = 64, beta = 416.524 -- the same coupling, the same
configuration count, the same ten sweeps:

  * `31_division_of_labour.py` reports the seed's relative deviation at W(8x8)
    going 378 -> 1581 ppm across ten sweeps: rethermalization makes the largest
    loop FOUR TIMES WORSE. That finding is the sole motivation for the
    `n_retherm` scan, and it is the mechanism `docs/` credits for u1's Fig. 38.
  * `33_retherm_scan.py` reports bias/sigma at W(8x8) going 0.1059 -> 0.0464
    across the same ten sweeps: rethermalization makes it 2.3x BETTER.

Both cannot be right, and the difference is load-bearing: one of them says the
delivered L = 64 ensemble is already past the point where its own W(8x8)
systematic exceeds its statistical error.

WHAT THIS SCRIPT DOES. It measures BOTH statistics on the SAME configurations,
in one pass, so the comparison cannot be confounded by the lift, the seed, the
ensemble or the sweep implementation. For every sweep count it reports

    relative deviation (ppm)     -- 31's statistic
    bias / sigma_1config         -- 33's statistic
    sigma_1config itself         -- the term that differs between them

The third column is the point. The two statistics differ by exactly one factor,
the single-configuration spread, and `sigma` is NOT fixed across the sweep axis:
rethermalization changes the ensemble's dispersion as well as its mean. If sigma
grows with sweeps then a bias that is flat in ppm still falls in bias/sigma, and
the two scripts can both be arithmetically right while telling opposite stories.
If sigma is flat, one of them has a bug.

    python u2_2d/scripts/42_retherm_reconcile.py --device cuda
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

from u2_2d.lgt.actions import WilsonU2Action
from u2_2d.lgt.blocking import topology_matched_fine_beta
from u2_2d.lgt.exact import plaquette_exact, wilson_loop_exact
from u2_2d.lgt.lattice import half_retr, plaquette, topological_charge, wilson_loop
from u2_2d.lgt.local_updates import retherm_sweeps
from u2_2d.model.det_lift import load_det_model
from u2_2d.pipeline.ladder import generate_fine_from_coarse
from u2_2d.utils import (configure_device, load_ensemble, resolve_device,
                         save_json, set_seed)

LOOPS = [(1, 1), (2, 2), (4, 4), (6, 6), (8, 8)]


def measure(links, beta, size):
    out = {}
    with torch.no_grad():
        for nx, ny in LOOPS:
            v = (half_retr(plaquette(links)) if (nx, ny) == (1, 1)
                 else half_retr(wilson_loop(links, nx, ny)))
            v = v.mean(dim=(1, 2)).cpu().numpy().astype(float)
            exact = (plaquette_exact(beta, size) if (nx, ny) == (1, 1)
                     else wilson_loop_exact(beta, nx * ny))
            bias = v.mean() - exact
            sigma = v.std(ddof=1)
            out[f"W{nx}x{ny}"] = {
                "rel_dev_ppm": float(1e6 * bias / exact),
                "bias_over_sigma": float(abs(bias) / max(sigma, 1e-18)),
                "sigma_1config_rel_ppm": float(1e6 * sigma / abs(exact)),
                "n_star": float((sigma / bias) ** 2) if bias else float("inf"),
            }
        q = topological_charge(links).round()
        out["q_squared"] = float((q ** 2).mean())
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--config", default="u2_2d/configs/default.yaml")
    ap.add_argument("--checkpoint",
                    default="out/u2_2d/checkpoints/det_score_net.pt")
    ap.add_argument("--data-dir", default="out/u2_2d/data_v2")
    ap.add_argument("--coarse-size", type=int, default=32)
    ap.add_argument("--coarse-beta", type=float, default=105.651)
    ap.add_argument("--n-configs", type=int, default=256)
    ap.add_argument("--sampler-steps", type=int, default=200)
    ap.add_argument("--n-su2", type=int, default=30)
    ap.add_argument("--sweeps", default="0,2,5,10,20,40")
    ap.add_argument("--seed", type=int, default=4242)
    ap.add_argument("--out-dir", default="out/u2_2d/retherm_reconcile")
    args = ap.parse_args()

    device = resolve_device({"device": args.device})
    print(configure_device(device))
    set_seed(args.seed)
    model, sched = load_det_model(args.checkpoint, device=device)

    path = Path(args.data_dir) / f"u2_L{args.coarse_size}_beta{args.coarse_beta:g}.pt"
    if not path.exists():
        print(f"missing {path}")
        return 1
    coarse, _ = load_ensemble(path)
    coarse = coarse[:args.n_configs]
    beta = topology_matched_fine_beta(args.coarse_beta, args.coarse_size)
    size = args.coarse_size * 2
    t0 = time.time()
    fine = generate_fine_from_coarse(
        model, sched, coarse, beta, n_su2_sweeps=args.n_su2, device=device,
        n_sampler_steps=args.sampler_steps, n_corrector_steps=1, batch_size=64,
        consistency_weight=1.0, physics_blend_coef=0.0)
    print(f"\nL={size}, beta={beta:.3f}, {fine.shape[0]} configs "
          f"[lift {time.time()-t0:.0f}s]\n")

    action = WilsonU2Action(beta)
    sweeps = [int(x) for x in args.sweeps.split(",")]
    state = fine.to(device)
    done = 0
    rows = []
    for n in sweeps:
        if n > done:
            state = retherm_sweeps(state, action, n - done)
            done = n
        rows.append({"sweeps": n, **measure(state, beta, size)})

    hdr = "".join(f"W{a}x{a}".rjust(11) for a, _ in LOOPS)
    for title, key, scale in (
            ("relative deviation (ppm)  -- 31's statistic", "rel_dev_ppm", 1.0),
            ("bias / sigma_1config      -- 33's statistic", "bias_over_sigma", 1.0),
            ("sigma_1config (ppm)       -- THE TERM THAT DIFFERS", "sigma_1config_rel_ppm", 1.0)):
        print(title)
        print(f"  {'sweeps':>7s}{hdr}")
        for r in rows:
            print(f"  {r['sweeps']:7d}"
                  + "".join(f"{r[f'W{a}x{a}'][key] * scale:11.4g}" for a, _ in LOOPS))
        print()

    # The reconciliation itself, at the loop where the two disagree.
    r0 = next(r for r in rows if r["sweeps"] == 0)
    r10 = next((r for r in rows if r["sweeps"] == 10), None)
    if r10:
        print("=" * 74)
        print("W(8x8), 0 -> 10 sweeps, both statistics on the SAME configurations:")
        a0, a1 = abs(r0["W8x8"]["rel_dev_ppm"]), abs(r10["W8x8"]["rel_dev_ppm"])
        b0, b1 = r0["W8x8"]["bias_over_sigma"], r10["W8x8"]["bias_over_sigma"]
        s0, s1 = r0["W8x8"]["sigma_1config_rel_ppm"], r10["W8x8"]["sigma_1config_rel_ppm"]
        print(f"  relative deviation  {a0:9.1f} -> {a1:9.1f} ppm   "
              f"({'WORSE' if a1 > a0 else 'better'} by {max(a1,a0)/max(min(a1,a0),1e-9):.2f}x)")
        print(f"  bias / sigma        {b0:9.4f} -> {b1:9.4f}       "
              f"({'WORSE' if b1 > b0 else 'better'} by {max(b1,b0)/max(min(b1,b0),1e-9):.2f}x)")
        print(f"  sigma_1config       {s0:9.1f} -> {s1:9.1f} ppm   "
              f"(x{s1/max(s0,1e-9):.2f})")
        print()
        if (a1 > a0) != (b1 > b0):
            print("  VERDICT: the two statistics genuinely point OPPOSITE ways on")
            print("  the same configurations. Both scripts are arithmetically right;")
            print("  the disagreement is which denominator is used, and sigma_1config")
            print(f"  moves by x{s1/max(s0,1e-9):.2f} across the tail. Report the ppm")
            print("  column -- it is the model's systematic -- and say so explicitly.")
        else:
            print("  VERDICT: both statistics agree in DIRECTION here, so the")
            print("  original disagreement was not a metric artefact. One of the")
            print("  two source measurements has a real defect -- chase the inputs")
            print("  (which ensemble was lifted, and with which checkpoint).")

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    save_json(out / "retherm_reconcile.json",
              {"lattice_size": size, "beta": beta,
               "n_configs": int(fine.shape[0]), "rows": rows})
    print(f"\nwrote {out / 'retherm_reconcile.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
