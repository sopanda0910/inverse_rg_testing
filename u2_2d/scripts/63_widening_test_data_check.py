"""Closed-form sanity check for the widening-coverage-test raw HMC data
(`out/u2_2d/data_widening_test/`, `configs/widening_test.yaml`).

This is CPU-only work queued to use idle CPU while the GPU relaxation matrix
runs -- it does not commit to the (separate, not-yet-decided) retrain on this
data. It is useful either way: before spending a training run on these 12
rungs, confirm the raw HMC itself landed on the right distribution, with a
real error bar, not just the single-point plaquette printed by
01_generate_data.py at generation time.

Reuses the project's own chain-resampling bootstrap (`chain_bootstrap` in
07_pq_sampling.py / 34_marginal_move_bias.py) rather than inventing a new
estimator, and the exact closed forms in u2_2d.lgt.exact -- both per the
CLAUDE.md rule to prefer existing, already-validated machinery.

    python u2_2d/scripts/63_widening_test_data_check.py
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u2_2d.lgt.exact import det_topological_susceptibility, plaquette_exact
from u2_2d.lgt.lattice import half_retr, plaquette, topological_charge
from u2_2d.utils import load_ensemble


def _load_chain_bootstrap():
    path = Path(__file__).resolve().parent / "07_pq_sampling.py"
    spec = importlib.util.spec_from_file_location("_pq07", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.chain_bootstrap


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="out/u2_2d/data_widening_test")
    parser.add_argument("--n-boot", type=int, default=2000)
    parser.add_argument("--n-configs-before-augment", type=int, default=256,
                        help="matches widening_test.yaml's data.rungs n_configs -- "
                             "sector_augment appends int(fraction * this) extra configs "
                             "AFTER this many. Slicing by this KNOWN count, not by "
                             "divisibility with n_chains, because that heuristic silently "
                             "fails here: 256*1.5=384=6*64, still evenly divisible, so it "
                             "let the non-chain-structured augmented tail through "
                             "undetected (found 2026-09-03 building the u1 twin of this "
                             "script, which had the identical bug -- both are fixed now)")
    args = parser.parse_args()

    chain_bootstrap = _load_chain_bootstrap()

    paths = sorted(glob.glob(f"{args.data_dir}/*.pt"),
                    key=lambda p: float(Path(p).stem.split("beta")[1]))
    if not paths:
        print(f"no ensembles found under {args.data_dir}")
        return 1

    print(f"{'beta':>8} {'model_beta':>10} {'n_cfg':>6} {'n_chains':>8}  "
          f"{'plaq':>9} {'exact':>9} {'z':>7}   {'<Q^2>':>7} {'exact':>7} {'z':>7}")

    n_flagged = 0
    for p in paths:
        configs, meta = load_ensemble(p)
        beta = meta["beta"]
        size = meta["lattice_size"]
        n_chains = meta["n_chains"]
        n_cfg = configs.shape[0]
        # sector_augment appends non-chain-structured configs at the end --
        # slice them off by the KNOWN pre-augment count (see the CLI arg's
        # help for why divisibility-with-n_chains alone does not catch this).
        n_pre_aug = min(args.n_configs_before_augment, n_cfg)
        n_pre_aug = (n_pre_aug // n_chains) * n_chains
        if n_pre_aug == 0:
            print(f"  ! {p}: n_configs={n_cfg} < n_chains={n_chains}, skipping")
            continue
        n_draws = n_pre_aug // n_chains

        plaq_per_config = half_retr(plaquette(configs)).mean(dim=(1, 2)).numpy()[:n_pre_aug]
        q_per_config = topological_charge(configs).numpy()[:n_pre_aug]
        q2_per_config = q_per_config**2

        # Chain-major ordering (index = draw*n_chains + chain), the same
        # convention `chain_bootstrap`'s callers already rely on elsewhere
        # in this project.
        plaq_chains = plaq_per_config.reshape(n_draws, n_chains)
        q2_chains = q2_per_config.reshape(n_draws, n_chains)

        plaq_val, plaq_err = chain_bootstrap(plaq_chains, np.mean, n_boot=args.n_boot)
        q2_val, q2_err = chain_bootstrap(q2_chains, np.mean, n_boot=args.n_boot)

        plaq_exact = plaquette_exact(beta, size)
        q2_exact = det_topological_susceptibility(beta, size) * size * size
        model_beta = beta / 4.0  # asymptotic; fine at this beta range (CLAUDE.md)

        plaq_z = (plaq_val - plaq_exact) / plaq_err if plaq_err > 0 else float("nan")
        q2_z = (q2_val - q2_exact) / q2_err if q2_err > 0 else float("nan")

        flag = ""
        if math.isfinite(plaq_z) and abs(plaq_z) > 3:
            flag += " !PLAQ"
        if math.isfinite(q2_z) and abs(q2_z) > 3:
            flag += " !Q2"
        if flag:
            n_flagged += 1

        print(f"{beta:8.1f} {model_beta:10.1f} {n_cfg:6d} {n_chains:8d}  "
              f"{plaq_val:9.6f} {plaq_exact:9.6f} {plaq_z:7.2f}   "
              f"{q2_val:7.4f} {q2_exact:7.4f} {q2_z:7.2f}{flag}")

    print()
    if n_flagged:
        print(f"{n_flagged} rung(s) flagged (|z| > 3) -- review before using "
              "this data for a retrain")
        return 1
    print("all rungs consistent with the closed form (|z| <= 3 on both "
          "plaquette and <Q^2>)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
