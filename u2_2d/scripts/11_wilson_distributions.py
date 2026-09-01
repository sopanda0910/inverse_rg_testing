"""Stage 11: per-configuration Wilson-loop distributions, generated vs HMC.

Mean observables are a weak test and the U(1) study says so explicitly: agreement
to two parts in 10^4 on the plaquette coexisted with a density gap of hundreds of
nats. Two ensembles can match every mean and still differ in the WIDTH of the
distribution those means came from, and the width is what a claim about the
density rests on.

So this dumps the per-configuration values rather than their averages, for the
generated ensemble and for an HMC reference at the same coupling, and records the
standard deviations alongside. The comparison to watch is not whether the
histograms overlap -- they will -- but whether the generated spread matches the
reference spread as the loop grows, since residual model error concentrates in
extended observables.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u2_2d.lgt.exact import wilson_loop_exact
from u2_2d.lgt.lattice import half_retr, wilson_loop
from u2_2d.utils import ensemble_path, load_config, load_ensemble, save_json

LOOPS = {"wilson_1x1": (1, 1), "wilson_2x2": (2, 2), "wilson_4x4": (4, 4),
         "wilson_8x8": (8, 8)}


def per_config(links: torch.Tensor, a: int, b: int) -> np.ndarray:
    """One number per configuration: the spatial mean of (1/2)ReTr W(a, b)."""
    with torch.no_grad():
        w = half_retr(wilson_loop(links, a, b))
        return w.mean(dim=tuple(range(1, w.dim()))).cpu().numpy()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="u2_2d/configs/default.yaml")
    parser.add_argument("--out", default="out/u2_2d/validation/wilson_distributions.json")
    parser.add_argument("--rung", type=int, default=0,
                        help="ladder rung index; default 0, the one with a reference")
    args = parser.parse_args()

    config = load_config(args.config)
    ladder_cfg = config["ladder"]
    base = ladder_cfg["base"]
    schedule = [float(b) for b in ladder_cfg["beta_schedule"]]
    sizes = [int(base["lattice_size"]) * 2 ** (i + 1) for i in range(len(schedule))]
    beta, size = schedule[args.rung], sizes[args.rung]

    ladder_dir = Path(ladder_cfg.get("out_dir", "out/u2_2d/ladder"))
    gen_path = ensemble_path(ladder_dir, size, beta, tag="ladder")
    if not gen_path.exists():
        print(f"missing {gen_path} -- run stage 03 first")
        return 1
    generated, _ = load_ensemble(gen_path)

    data_dir = Path(config["data"].get("out_dir", "out/u2_2d/data"))
    ref_path = ensemble_path(data_dir, size, beta)
    reference = None
    if ref_path.exists():
        reference, _ = load_ensemble(ref_path)
        print(f"reference: {ref_path.name} ({reference.shape[0]} configs)")
    else:
        print(f"no HMC reference at L={size} beta={beta:g}; exact mean only")

    loops = [n for n, (a, _) in LOOPS.items() if a < size]
    out = {
        "beta": beta, "lattice_size": size, "loops": loops,
        "n_generated": int(generated.shape[0]),
        "generated": {}, "reference": {} if reference is not None else None,
        "exact": {}, "std": {},
    }
    for name in loops:
        a, b = LOOPS[name]
        g = per_config(generated, a, b)
        out["generated"][name] = g.tolist()
        out["exact"][name] = wilson_loop_exact(beta, a * b, lattice_size=size)
        entry = {"generated": float(g.std())}
        if reference is not None:
            r = per_config(reference, a, b)
            out["reference"][name] = r.tolist()
            entry["reference"] = float(r.std())
            entry["ratio"] = float(g.std() / r.std()) if r.std() > 0 else float("nan")
        out["std"][name] = entry

    save_json(Path(args.out), out)
    print(f"\nL={size} beta={beta:g}   per-configuration spread")
    print(f"{'loop':14s} {'generated':>12s} {'HMC':>12s} {'ratio':>8s}")
    for name in loops:
        e = out["std"][name]
        print(f"{name:14s} {e['generated']:12.3e} "
              f"{e.get('reference', float('nan')):12.3e} "
              f"{e.get('ratio', float('nan')):8.3f}")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
