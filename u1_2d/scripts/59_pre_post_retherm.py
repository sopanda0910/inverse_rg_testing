"""u1 Fig. 40 -- the scale profile of the lift, BEFORE and AFTER rethermalization.

WHY THIS EXISTS. u1's Fig. 38 (`54_seed_accuracy_figures.py`) shows std(z)
growing with Wilson-loop area and reads it as "the residual lives in
long-wavelength modes, which is exactly what local rethermalization relaxes
slowest". That reading is CORRECT and this script does not contradict it. But it
was measured only on the DELIVERED, post-rethermalization ensembles, so the
causal half -- that rethermalization is what leaves the residual in the infrared
-- is asserted rather than shown.

u2 measured the missing half (`u2_2d/scripts/31_division_of_labour.py`) and found
that ten local sweeps improve W(1x1) by 47x, leave W(4x4) untouched, and make
W(8x8) FOUR TIMES WORSE. If the same holds in u1 then Fig. 38's residual is not
what the model left behind -- it is what rethermalization put there, and the
sweep count is a knob that trades ultraviolet accuracy against infrared accuracy
rather than a free repair.

WHAT IS REPORTED, and in which order of authority:

  z = (mean - exact) / SEM is the statistic of record, as everywhere else in u1.
  Large loops genuinely fluctuate more per configuration, so the same absolute
  error legitimately shows as less significant on them, and z says so.

  Beside it, and as DISCUSSION only: the relative deviation (the bias with the
  error bar divided out), and

      N* = (sigma / bias)^2

  the number of configurations usable before the model's systematic exceeds the
  user's own statistical error. N* is independent of how many configurations
  this script happened to generate, which z is not -- z scales as sqrt(N). If
  N* at the largest loop falls below the size of the ensembles u1 actually
  ships, that is a concrete defect rather than a stylistic point.

    python u1_2d/scripts/59_pre_post_retherm.py --device cuda
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
from u1_2d.lgt.hmc import adapted_hmc_params
from u1_2d.lgt.lattice import plaquette_angles, wilson_loop_angles
from u1_2d.lgt.local_updates import retherm_sweeps
from u1_2d.lgt.exact import wilson_loop_exact
from u1_2d.model.train import load_checkpoint
from u1_2d.pipeline.ladder import generate_fine_from_coarse
from u1_2d.utils import save_json, set_seed
from u1_2d.validate.stats import autocorr_aware_mean_err

# Loop extents scored on both sides of the tail. 8x8 is the largest that stays
# comfortably inside L = 32 (area 64 of 1024) and it is where u2 found the
# damage, so it must be present.
LOOPS = [(1, 1), (2, 2), (4, 4), (6, 6), (8, 8)]


def loop_means(field: torch.Tensor) -> dict:
    """Per-configuration mean of cos(loop angle), one entry per loop size."""
    out = {}
    with torch.no_grad():
        for nx, ny in LOOPS:
            ang = (plaquette_angles(field) if (nx, ny) == (1, 1)
                   else wilson_loop_angles(field, nx, ny))
            out[f"wilson_{nx}x{ny}"] = torch.cos(ang).mean(dim=(-2, -1)).cpu().numpy()
    return out


def score(stats: dict, beta: float, size: int, n_chains: int) -> dict:
    """TAU_INT-AWARE errors, per u1's own convention (NARRATIVE 25.7, item M4).

    The configurations descend from `n_chains` HMC chains and are correlated, so
    a naive across-configuration sem understates the error and inflates |z|. The
    first version of this script used the naive sem; `autocorr_aware_mean_err`
    is the same estimator the rest of u1 uses -- binned error as a floor, raised
    to naive * sqrt(2 tau_int) when per-chain tau is measurable.

    N* is deliberately left on the SINGLE-CONFIGURATION sigma: inter-config
    correlation changes how well this ensemble measures the bias, not how large
    the bias is against one configuration's spread, which is what N* asks.
    """
    rec = {"z": {}, "relative_deviation": {}, "relative_sem": {}, "relative_sigma_1config": {}, "n_star": {},
           "tau_int": {}}
    for nx, ny in LOOPS:
        key = f"wilson_{nx}x{ny}"
        v = np.asarray(stats[key], dtype=float)
        exact = wilson_loop_exact(beta, nx * ny, "wilson", size)
        mean, err, tau = autocorr_aware_mean_err(v, n_chains)
        sem = err
        bias = mean - exact
        rec["tau_int"][key] = float(tau)
        rec["z"][key] = float(bias / max(sem, 1e-15))
        rec["relative_deviation"][key] = float(bias / exact)
        rec["relative_sem"][key] = float(sem / abs(exact))
        rec["relative_sigma_1config"][key] = float(v.std(ddof=1) / abs(exact))
        # N* = (sigma / bias)^2 with sigma the SINGLE-CONFIGURATION spread, so
        # the answer does not depend on how many configurations were generated
        # here. sem = sigma / sqrt(N)  =>  sigma = sem * sqrt(N).
        sigma_1 = v.std(ddof=1)
        rec["n_star"][key] = (float((sigma_1 / bias) ** 2) if bias != 0
                              else float("inf"))
    return rec


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", default="out/u1_2d/checkpoints/score_net.pt")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--coarse-size", type=int, default=16)
    parser.add_argument("--coarse-betas", default="14.1464,55.0237")
    parser.add_argument("--n-configs", type=int, default=256)
    parser.add_argument("--n-chains", type=int, default=16)
    parser.add_argument("--burn-in", type=int, default=800)
    parser.add_argument("--thin", type=int, default=5)
    parser.add_argument("--sampler-steps", type=int, default=200)
    # The sweep counts to profile. 10 is the deployed setting; 0 is the raw
    # lift; the rest bracket it so the trade can be seen rather than assumed.
    parser.add_argument("--sweeps", default="0,2,5,10,20,40")
    parser.add_argument("--seed", type=int, default=707)
    parser.add_argument("--out-dir", default="out/u1_2d/pre_post_retherm")
    args = parser.parse_args()

    device = args.device
    set_seed(args.seed)
    model, schedule = load_checkpoint(args.checkpoint, device)
    print(f"checkpoint {args.checkpoint} on {device}")

    sweeps = [int(s) for s in args.sweeps.split(",")]
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    records = []

    for coarse_beta in [float(b) for b in args.coarse_betas.split(",")]:
        t0 = time.time()
        fine_size = args.coarse_size * 2
        fine_beta = approx_matched_fine_beta(coarse_beta, "wilson")

        # The coarse base. u1's .pt ensembles were pruned in 2026-08, so it is
        # regenerated here rather than loaded; at L = 16 that is cheap.
        action_c = make_action("wilson", coarse_beta)
        step, n_steps = adapted_hmc_params(coarse_beta)
        coarse, _ = run_hmc_ensemble(
            args.coarse_size, action_c, n_configs=args.n_configs,
            n_chains=args.n_chains, burn_in=args.burn_in, thin=args.thin,
            step_size=step, n_steps=n_steps, device=device,
            topological_updates=True)
        coarse = coarse.cpu()
        base_s = time.time() - t0

        fine = generate_fine_from_coarse(
            model, schedule, coarse, fine_beta, device=device,
            n_sampler_steps=args.sampler_steps, n_corrector_steps=1,
            batch_size=64, consistency_weight=1.0)
        lift_s = time.time() - t0 - base_s

        action_f = make_action("wilson", fine_beta)
        rec = {"coarse_beta": coarse_beta, "fine_beta": fine_beta,
               "lattice_size": fine_size, "n_configs": int(fine.shape[0]),
               "base_seconds": base_s, "lift_seconds": lift_s, "by_sweeps": {}}
        print(f"\ncoarse beta={coarse_beta:g} -> fine beta={fine_beta:.4f} "
              f"L={fine_size}, {fine.shape[0]} configs "
              f"[base {base_s:.0f}s, lift {lift_s:.0f}s]")

        # Rethermalize CUMULATIVELY from the raw lift, so every row is the same
        # configurations carried further rather than an independent draw. The
        # comparison is then paired and the differences are not sampling noise.
        state = fine.to(device)
        done = 0
        for n in sweeps:
            if n > done:
                state = retherm_sweeps(state, action_f, n - done,
                                       topological_updates=False)
                done = n
            rec["by_sweeps"][str(n)] = score(loop_means(state), fine_beta, fine_size, args.n_chains)
            r = rec["by_sweeps"][str(n)]
            zs = " ".join(f"{r['z'][f'wilson_{a}x{a}']:+7.2f}" for a, _ in
                          [(x, y) for x, y in LOOPS])
            print(f"  {n:3d} sweeps   z: {zs}")
        records.append(rec)
        save_json(out / "pre_post_retherm.json", records)

    # The summary the whole script exists for.
    print("\n" + "=" * 78)
    for rec in records:
        print(f"\nL={rec['lattice_size']}, fine beta={rec['fine_beta']:.4f}, "
              f"N={rec['n_configs']}")
        hdr = "".join(f"W{a}x{a}".rjust(11) for a, _ in LOOPS)
        for title, field, fmt in (
                ("relative deviation, ppm", "relative_deviation", "%11.4g"),
                ("N* (configs before bias > stat err)", "n_star", "%11.4g")):
            print(f"  {title}")
            print(f"    {'sweeps':>7s}{hdr}")
            for n in sweeps:
                r = rec["by_sweeps"][str(n)][field]
                vals = [abs(r[f"wilson_{a}x{a}"]) * (1e6 if field ==
                        "relative_deviation" else 1.0) for a, _ in LOOPS]
                print(f"    {n:7d}" + "".join(fmt % v for v in vals))
    print(f"\nwrote {out / 'pre_post_retherm.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
