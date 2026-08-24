"""Do the classical prolongator arms get the FLUCTUATIONS right, not just the mean?

Opened 2026-08-24 by an anomaly in `37_tiling_baseline.py`. At beta_f = 218.58
the `smear` arm (flux + 285 tuned heatbath/overrelaxation sweeps) and the `ape`
arm start at essentially the SAME mean plaquette error -- -7.84e-05 against
-8.33e-05 -- yet `ape` reaches the t_therm criterion in 39 trajectories and
`smear` never does in 640.

`t_therm` is |mean - exact| / SEM, and the SEM is measured ACROSS
configurations. Two arms with the same mean error can therefore land on
opposite sides of the criterion if their ensembles have different spread. An
under-dispersed ensemble -- configurations too similar to each other -- has a
SEM that understates its own error, so |z| is large however close the mean is.

That is a hypothesis, and the standing lesson in this project is that a
mechanism built on a z without checking its numerator and denominator
separately is how the retracted W(8x8) "actionable defect" happened. So measure
the two parts:

  * the MEAN error, against the exact plaquette from the character expansion;
  * the SPREAD, against the EXACT per-configuration sigma, which is available
    in closed form and needs no simulation at all.

The exact spread: log Z' (beta) = <sum cos p> = V * P(beta), so
log Z'' (beta) = Var(sum cos p) = V^2 * Var(mean plaquette), giving

    sigma_1config(mean plaquette) = sqrt( P'(beta) / V )

with P' obtained by central difference on `plaquette_exact`. An ensemble whose
measured across-configuration std is far below this is under-dispersed and its
error bars are fiction.

No HMC is run: the arms are built and measured as they stand.

    .venv/Scripts/python.exe u1_2d/scripts/66_prolongator_dispersion.py
"""

import argparse
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import torch

from u1_2d.lgt.exact import plaquette_exact
from u1_2d.lgt.lattice import plaquette_angles
from u1_2d.utils import load_config, load_ensemble, resolve_device, save_json

REPO = Path(__file__).resolve().parents[2]


def _load_37():
    spec = importlib.util.spec_from_file_location(
        "tiling37", REPO / "u1_2d" / "scripts" / "37_tiling_baseline.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def exact_sigma_1config(beta: float, lattice_size: int, action_type: str,
                        h: float = 1e-3) -> float:
    """Exact per-configuration std of the mean plaquette, from the free energy."""
    v = 2.0 * h * beta
    dpdbeta = (plaquette_exact(beta + h * beta, action_type, lattice_size)
               - plaquette_exact(beta - h * beta, action_type, lattice_size)) / v
    volume = lattice_size * lattice_size
    return math.sqrt(max(dpdbeta, 0.0) / volume)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="u1_2d/configs/v2.yaml")
    ap.add_argument("--cases", nargs="+",
                    default=["32:14.1464", "32:55.0237", "32:218.58"])
    ap.add_argument("--n-configs", type=int, default=64)
    ap.add_argument("--device", default=None)
    ap.add_argument("--smear-sweeps", type=int, default=0,
                    help="0 = tune against the exact plaquette, as 37 does")
    ap.add_argument("--out", default="out/u1_2d/prolongator_dispersion")
    args = ap.parse_args()

    m37 = _load_37()
    config = load_config(args.config)
    if args.device:
        config["device"] = args.device
    device = resolve_device(config)
    action_type = config["action_type"]
    out_dir = REPO / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    from u1_2d.lgt.blocking import approx_matched_coarse_beta

    results = []
    for case in args.cases:
        fine_L, fine_beta = case.split(":")
        fine_L, fine_beta = int(fine_L), float(fine_beta)
        coarse_L = fine_L // 2
        coarse_beta = approx_matched_coarse_beta(fine_beta, action_type)

        base_dir = REPO / "out" / "u1_2d" / "generalization" / "bases"
        coarse = None
        for cand in base_dir.glob(f"{action_type}_L{coarse_L}_beta*.pt"):
            try:
                b = float(cand.stem.split("beta")[1])
            except ValueError:
                continue
            if abs(b - coarse_beta) <= 1e-3 * max(1.0, abs(coarse_beta)):
                coarse, _ = load_ensemble(cand)
                break
        if coarse is None:
            from u1_2d.lgt import make_action, run_hmc_ensemble
            from u1_2d.lgt.hmc import adapted_hmc_params
            ss, ns = adapted_hmc_params(coarse_beta,
                                        float(config["data"]["hmc_step_size"]),
                                        int(config["data"]["hmc_steps"]))
            print(f"  simulating coarse L={coarse_L} beta={coarse_beta:g}", flush=True)
            coarse, _ = run_hmc_ensemble(
                coarse_L, make_action(action_type, coarse_beta),
                n_configs=args.n_configs, n_chains=16, burn_in=600, thin=5,
                step_size=ss, n_steps=ns, device=device, hot_start=True,
                topological_updates=True)
            coarse = coarse.cpu()
        coarse = coarse[: args.n_configs]

        target = plaquette_exact(fine_beta, action_type, fine_L)
        sigma_exact = exact_sigma_1config(fine_beta, fine_L, action_type)
        n = coarse.shape[0]
        print(f"\n=== {fine_L}:{fine_beta:g} ===  exact P = {target:.8f}  "
              f"exact sigma_1config = {sigma_exact:.3e}  n = {n}", flush=True)

        row = {"fine_L": fine_L, "fine_beta": fine_beta, "n_configs": n,
               "exact_plaquette": target, "exact_sigma_1config": sigma_exact,
               "arms": {}}

        arms = {}
        for name in ("tile", "halve", "flux"):
            arms[name] = m37.PROLONGATORS[name](coarse)
        arms["ape"] = m37.ape(coarse, target)
        if args.smear_sweeps > 0:
            arms["smear"], _, _ = m37.local_repair(
                m37.flux(coarse), fine_beta, action_type, args.smear_sweeps,
                device, mode="heatbath")
            # The arm that turned out to be STRONGER than `smear` at stiff
            # coupling (RESULT 8): identical but for the ergodic move. Included
            # here so the t_therm inversion can be checked against the exact
            # per-configuration sigma rather than against a measured SEM.
            arms["smear_mh"], _, _ = m37.local_repair(
                m37.flux(coarse), fine_beta, action_type, args.smear_sweeps,
                device, mode="metropolis")
        else:
            arms["smear"], sw, _ = m37.tune_smear(
                m37.flux(coarse), fine_beta, action_type, target, device)
            print(f"  (smear tuned to {sw} sweeps)", flush=True)

        for name, fine0 in arms.items():
            with torch.no_grad():
                per_cfg = plaquette_angles(fine0).cos().mean(dim=(-2, -1)).cpu().numpy()
            mean = float(per_cfg.mean())
            std = float(per_cfg.std(ddof=1))
            sem = std / math.sqrt(n)
            # z as t_therm forms it, from the arm's OWN measured spread ...
            z_measured = (mean - target) / max(sem, 1e-300)
            # ... and as it would be with the EXACT spread, which is the honest
            # denominator when the arm's own spread is not to be trusted.
            z_exact_sem = (mean - target) / (sigma_exact / math.sqrt(n))
            row["arms"][name] = {
                "mean": mean, "rel_err": (mean - target) / abs(target),
                "std_across_configs": std, "std_ratio_to_exact": std / sigma_exact,
                "z_from_measured_sem": z_measured, "z_from_exact_sem": z_exact_sem,
            }
            print(f"  {name:<6} rel err = {(mean - target) / abs(target):+.3e}   "
                  f"std/exact = {std / sigma_exact:7.3f}   "
                  f"|z| measured = {abs(z_measured):9.2f}   "
                  f"|z| exact-sigma = {abs(z_exact_sem):8.2f}", flush=True)
        results.append(row)

    save_json(out_dir / "prolongator_dispersion.json", results)

    print("\n## std(across configs) / exact sigma_1config -- 1.0 is correct\n")
    names = [n for n in ("tile", "halve", "flux", "ape", "smear", "smear_mh") if n in results[0]["arms"]]
    print("| beta_f | " + " | ".join(names) + " |")
    print("|---|" + "---|" * len(names))
    for r in results:
        cells = [f"{r['arms'][nm]['std_ratio_to_exact']:.2f}" for nm in names]
        print(f"| {r['fine_beta']:g} | " + " | ".join(cells) + " |")
    print("\nA ratio far below 1 means the arm's configurations are too similar "
          "to each other, so its SEM understates its own error and any z built "
          "from it is inflated. A ratio far above 1 means the opposite.")
    print(f"\nwrote {(out_dir / 'prolongator_dispersion.json').relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
