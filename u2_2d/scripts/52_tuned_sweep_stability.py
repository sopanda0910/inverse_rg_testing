"""Is the tuned sweep count -- u2's surviving prolongator claim -- stable across seeds?

Opened 2026-08-24, and it is a direct consequence of two other findings the same
day.

NARRATIVE's prolongator ablation makes two claims for the learned lift:

  (a) it thermalizes in 0-1 trajectories against `smear`'s 5-6;
  (b) it needs 5 TUNED SWEEPS against `smear`'s 35 and 15 -- "7x and 3x less
      repair".

Claim (a) is now known to sit inside the resolution floor of `t_therm`: at this
study's 64-chain shape a PERFECTLY thermalized ensemble already reports
`t_therm = 0` only 78-85% of the time, with a 90th percentile of 3-4
(`u1_2d/scripts/65_therm_criterion_calibration.py`,
`out/u2_2d/therm_calibration/`). So (b) is the half that carries the ablation.

Then `50_therm_autocorr.py`, which seeds differently from
`17_prolongator_baseline.py` (`seed` against `seed + 1717`) and is therefore an
independent draw, returned **15 tuned sweeps for `diffusion_tuned` at the top
rung -- the same as `smear`**, where 17 reported 5 against 15. One seed
disagreeing with another is exactly the situation
`docs/PARITY_U1_U2.md` section 5 item 11 says to resolve with more seeds rather
than a hedge in the write-up.

Two things make the count fragile a priori, and both are worth stating because
they bound how precise the claim can ever be:

  * `tune_smear` checks the plaquette every 5 sweeps, so the count is QUANTIZED
    to multiples of 5. "5 against 15" is two check-points, not a smooth 3x.
  * it stops on the first crossing of a stochastic quantity, so it is a
    first-passage time and has a heavy right tail by construction.

This script re-runs the lift and the tuning at several seeds and reports the
distribution of the count for both arms, so the ratio can be quoted with a
spread or withdrawn.

    .venv/Scripts/python.exe u2_2d/scripts/52_tuned_sweep_stability.py \
        --seeds 0 1 2 3 4 --rung -1
"""

import argparse
import importlib.util
import statistics
import sys
import time
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from u2_2d.lgt.actions import WilsonU2Action
from u2_2d.utils import (ensemble_path, load_config, load_ensemble,
                         resolve_device, save_json, set_seed)


def _load_17():
    spec = importlib.util.spec_from_file_location(
        "prolong17", REPO / "u2_2d" / "scripts" / "17_prolongator_baseline.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["prolong17"] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="u2_2d/configs/default.yaml")
    ap.add_argument("--device", default=None)
    ap.add_argument("--out-dir", default="out/u2_2d/tuned_sweep_stability")
    ap.add_argument("--rung", type=int, default=-1)
    ap.add_argument("--n-chains", type=int, default=64)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    ap.add_argument("--checkpoint", default=None)
    ap.add_argument("--check-every", type=int, default=5,
                    help="tune_smear's own granularity; 1 removes the "
                         "quantization that makes '5 vs 15' two check-points")
    args = ap.parse_args()

    m17 = _load_17()
    config = load_config(args.config)
    if args.device:
        config["device"] = args.device
    device = resolve_device(config)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ladder_cfg = config["ladder"]
    base = ladder_cfg["base"]
    schedule = [float(b) for b in ladder_cfg["beta_schedule"]]
    sizes = [int(base["lattice_size"]) * 2 ** (i + 1) for i in range(len(schedule))]
    rung = args.rung if args.rung >= 0 else len(schedule) - 1
    beta, size = schedule[rung], sizes[rung]
    ladder_dir = Path(ladder_cfg.get("out_dir", "out/u2_2d/ladder"))
    coarse_path = (ensemble_path(config["data"]["out_dir"],
                                 int(base["lattice_size"]), float(base["beta"]))
                   if rung == 0 else
                   ensemble_path(ladder_dir, sizes[rung - 1], schedule[rung - 1],
                                 tag="ladder"))
    coarse, _ = load_ensemble(coarse_path)
    coarse = coarse[: args.n_chains]
    n_su2 = int(ladder_cfg.get("n_su2_sweeps", 30))

    from u2_2d.model.det_lift import load_det_model
    from u2_2d.pipeline.ladder import generate_fine_from_coarse

    ckpt = args.checkpoint or config["train"].get(
        "checkpoint_path", "out/u2_2d/checkpoints/det_score_net.pt")
    model, sched = load_det_model(ckpt, device=device)
    psi_coarse = m17.det_links(coarse)

    print(f"rung {rung}: L={size} beta={beta:g}, {coarse.shape[0]} configs, "
          f"check_every={args.check_every}, seeds={args.seeds}", flush=True)

    rows = []
    for seed in args.seeds:
        set_seed(seed)
        t0 = time.time()
        fine = generate_fine_from_coarse(
            model, sched, coarse, beta, n_su2_sweeps=n_su2, device=device,
            n_sampler_steps=int(ladder_cfg.get("n_sampler_steps", 200)),
            n_corrector_steps=int(ladder_cfg.get("n_corrector_steps", 1)),
            batch_size=int(ladder_cfg.get("batch_size", 64)),
            consistency_weight=float(ladder_cfg.get("consistency_weight", 1.0)),
            physics_blend_coef=float(ladder_cfg.get("physics_blend_coef", 0.0)),
        )
        _, n_diff, _ = m17.tune_smear(fine, beta, device,
                                      check_every=args.check_every)
        # `smear` gets a fresh flux prolongation + the ladder's conditional SU(2)
        # sweeps, exactly as in 17: n_retherm=0 inside assemble, so the tuned
        # count below is its entire local-update budget.
        set_seed(seed)
        base_fine, _ = m17.assemble(m17.flux(psi_coarse), coarse, beta,
                                    n_su2, 0, device)
        _, n_smear, _ = m17.tune_smear(base_fine, beta, device,
                                       check_every=args.check_every)
        rows.append({"seed": seed, "diffusion_tuned": n_diff, "smear": n_smear,
                     "ratio": (n_smear / n_diff) if n_diff else None,
                     "seconds": time.time() - t0})
        print(f"  seed {seed}: diffusion_tuned = {n_diff:<4} "
              f"smear = {n_smear:<4} ratio = "
              f"{rows[-1]['ratio'] if rows[-1]['ratio'] is None else round(rows[-1]['ratio'], 2)}",
              flush=True)

    save_json(out_dir / "tuned_sweep_stability.json",
              {"lattice_size": size, "beta": beta, "check_every": args.check_every,
               "rows": rows})

    d = [r["diffusion_tuned"] for r in rows]
    s = [r["smear"] for r in rows]
    print(f"\n## {len(rows)} seeds, L = {size}, beta = {beta:g}\n")
    print("| arm | counts | median | min-max |")
    print("|---|---|---|---|")
    print(f"| diffusion_tuned | {d} | {statistics.median(d):g} | {min(d)}-{max(d)} |")
    print(f"| smear | {s} | {statistics.median(s):g} | {min(s)}-{max(s)} |")
    ratios = [r["ratio"] for r in rows if r["ratio"]]
    if ratios:
        print(f"\nratio smear/diffusion_tuned: median "
              f"{statistics.median(ratios):.2f}, range "
              f"{min(ratios):.2f}-{max(ratios):.2f}")
    print("\nIf the ranges overlap, the '3-7x less repair' claim does not "
          "survive seed variation and must be restated as a spread or dropped.")
    print(f"\nwrote {(out_dir / 'tuned_sweep_stability.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
