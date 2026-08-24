"""Do the classical prolongators get TOPOLOGY right? (They do not.)

THE MISSING COLUMN, added 2026-08-24 after it inverted a day of conclusions.

`37_tiling_baseline.py` scores prolongator arms with `t_therm`, whose observable
set is plaquette / W(2x2) / W(4x4) -- all LOCAL. On that criterion the classical
arms look excellent and beat the diffusion seed: `flux` plus 200 Metropolis
sweeps reaches t_therm = 0 at beta_f = 218.58 and sits 0.07 sigma from the exact
plaquette with correct per-configuration dispersion.

Scored on topology the same arms collapse. `t_therm` never looked.

**The error this corrects, recorded because it is instructive.** It was argued --
not measured -- that `flux` "carries the coarse charge for free": it is
blocking-consistent, and spreading a coarse plaquette angle over the four fine
plaquettes of its cell should give each `Theta/4 < pi/4`, so nothing wraps and
the telescope gives `Q_fine = Q_coarse`. Measured, `flux`'s fine plaquettes reach
2.99 rad and the cell sum misses its coarse plaquette by up to 4 pi. It is
consistent at the LINK level while its PLAQUETTES wrap, which destroys Q
entirely: every `flux` configuration has Q = 0.

So the arms divide cleanly, and on exactly the axis this study is about:

  * LOCAL observables -- classical prolongation plus cheap local repair is
    excellent, and better than the learned lift;
  * TOPOLOGY -- classical prolongation is not merely worse, it is unusable, and
    the learned pipeline is exact by construction because Q is TRANSPORTED
    (`apply_coarse_charge`) rather than produced by the map.

That is the same "observable-level agreement does not certify the measure"
result the study already makes about generative samplers, now turned on the
classical baselines.

    .venv/Scripts/python.exe u1_2d/scripts/67_prolongator_topology.py
"""

import argparse
import importlib.util
import math
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[2]

from u1_2d.lgt.blocking import approx_matched_coarse_beta, block_links
from u1_2d.lgt.exact import topological_charge_distribution
from u1_2d.lgt.lattice import plaquette_angles, topological_charge, wrap
from u1_2d.utils import load_config, load_ensemble, resolve_device, save_json


def _load_37():
    spec = importlib.util.spec_from_file_location(
        "tiling37", REPO / "u1_2d" / "scripts" / "37_tiling_baseline.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def exact_q_squared(beta: float, size: int, action_type: str) -> float:
    q, p = topological_charge_distribution(beta, size, action_type)
    return float((p * q.astype(float) ** 2).sum())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="u1_2d/configs/v2.yaml")
    ap.add_argument("--cases", nargs="+",
                    default=["32:14.1464", "32:55.0237", "32:218.58"])
    ap.add_argument("--n-configs", type=int, default=64)
    ap.add_argument("--sweeps", type=int, default=200)
    ap.add_argument("--device", default=None)
    ap.add_argument("--out", default="out/u1_2d/prolongator_topology")
    args = ap.parse_args()

    m37 = _load_37()
    config = load_config(args.config)
    if args.device:
        config["device"] = args.device
    device = resolve_device(config)
    action_type = config["action_type"]
    out_dir = REPO / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

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
        q_coarse = topological_charge(coarse).numpy().astype(int)

        exact = exact_q_squared(fine_beta, fine_L, action_type)
        # The ladder invariant: exact <Q^2> is a fixed point of
        # (V, beta) -> (4V, 4beta), so the coarse ensemble's own <Q^2> is what a
        # correct lift must reproduce. Printed as the cross-check it is.
        exact_coarse = exact_q_squared(coarse_beta, coarse_L, action_type)

        base = m37.flux(coarse)
        arms = {
            "tile": m37.tile(coarse),
            "halve": m37.halve(coarse),
            "flux": base,
            "ape": m37.ape(coarse, None),
            "smear (heatbath)": m37.local_repair(
                base, fine_beta, action_type, args.sweeps, device,
                mode="heatbath")[0],
            "smear_mh (metropolis)": m37.local_repair(
                base, fine_beta, action_type, args.sweeps, device,
                mode="metropolis")[0],
        }

        print(f"\n=== L={fine_L} beta={fine_beta:g} "
              f"(coarse {coarse_L}:{coarse_beta:.4f}), n={coarse.shape[0]} ===")
        print(f"  exact <Q^2> fine = {exact:.4f}   exact <Q^2> coarse = "
              f"{exact_coarse:.4f}   measured coarse = {(q_coarse**2).mean():.4f}")
        row = {"fine_L": fine_L, "fine_beta": fine_beta, "coarse_beta": coarse_beta,
               "n_configs": int(coarse.shape[0]), "exact_q_squared": exact,
               "coarse_q_squared_measured": float((q_coarse ** 2).mean()),
               "arms": {}}

        print(f"  {'arm':<24}{'<Q^2>':>9}{'/exact':>9}{'Q=Qc':>8}"
              f"{'|Q|>0':>8}{'blk|err|':>10}")
        for name, cfg in arms.items():
            with torch.no_grad():
                q = topological_charge(cfg).numpy().astype(int)
                blk = float(wrap(block_links(cfg) - wrap(coarse)).abs().max())
            q2 = float((q.astype(float) ** 2).mean())
            row["arms"][name] = {
                "q_squared": q2, "ratio_to_exact": q2 / exact,
                "sector_match": float((q == q_coarse).mean()),
                "frac_nonzero": float((q != 0).mean()),
                "blocking_error": blk,
            }
            print(f"  {name:<24}{q2:>9.3f}{q2/exact:>9.2f}"
                  f"{100*(q==q_coarse).mean():>7.0f}%{100*(q!=0).mean():>7.0f}%"
                  f"{blk:>10.4f}")
        results.append(row)

    save_json(out_dir / "prolongator_topology.json", results)

    names = list(results[0]["arms"])
    print("\n## <Q^2> / exact -- 1.00 is correct; the diffusion pipeline is "
          "1.00 by construction (Q is transported)\n")
    print("| beta_f | " + " | ".join(names) + " |")
    print("|---|" + "---|" * len(names))
    for r in results:
        cells = [f"{r['arms'][n]['ratio_to_exact']:.2f}" for n in names]
        print(f"| {r['fine_beta']:g} | " + " | ".join(cells) + " |")
    print("\n`t_therm` scores plaquette / W(2x2) / W(4x4) only, so none of this "
          "enters it. An arm can be 0.07 sigma from the exact plaquette with "
          "correct dispersion and still have a topological charge distribution "
          "several times too narrow or too wide.")
    print(f"\nwrote {(out_dir / 'prolongator_topology.json').relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
