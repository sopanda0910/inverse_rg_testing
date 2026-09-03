"""Closed-form sanity check for the u1 widening-coverage-test raw HMC data
(`out/u1_2d/data_widening_test/`, `configs/widening_test.yaml`).

The u1 twin of `u2_2d/scripts/63_widening_test_data_check.py`, built the same
day for the same reason: before spending a training run on these 7 new
fixed rungs (beta 300-2000), confirm the raw HMC itself landed on the right
distribution, with a real chain-resampling error bar, not just the single
point-value plaquette 01_generate_data.py prints at generation time.

Reuses the closed forms in u1_2d.lgt.exact and the same chain-resampling
bootstrap convention already established in u2_2d/scripts/07_pq_sampling.py
(u1 does not have its own copy of this helper, so a small self-contained one
is defined here rather than importing across studies).

    python u1_2d/scripts/69_widening_test_data_check.py
"""
from __future__ import annotations

import argparse
import glob
import math
from pathlib import Path

import numpy as np
import torch

from u1_2d.lgt.exact import plaquette_exact, topological_susceptibility_exact
from u1_2d.lgt.lattice import plaquette_angles, topological_charge
from u1_2d.utils import load_ensemble


def chain_bootstrap(per_chain: np.ndarray, n_boot: int = 2000,
                    seed: int = 0) -> tuple[float, float]:
    """(mean, standard error) resampling whole CHAINS with replacement.
    `per_chain` is [n_draws, n_chains]. Same convention as u2_2d/scripts/
    07_pq_sampling.py's chain_bootstrap, restricted to the mean statistic."""
    rng = np.random.default_rng(seed)
    n_chains = per_chain.shape[1]
    value = float(per_chain.mean())
    chain_means = per_chain.mean(axis=0)
    picks = rng.integers(0, n_chains, size=(n_boot, n_chains))
    draws = chain_means[picks].mean(axis=1)
    return value, float(draws.std())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="out/u1_2d/data_widening_test")
    parser.add_argument("--n-chains", type=int, default=16,
                        help="chains per rung, matching widening_test.yaml's data.n_chains "
                             "-- needed because sector_augment appends non-chain-structured "
                             "configs at the end, which are excluded from the bootstrap the "
                             "same way u2's check script excludes its augmented tail")
    parser.add_argument("--n-boot", type=int, default=2000)
    parser.add_argument("--n-configs-before-augment", type=int, default=448,
                        help="matches widening_test.yaml's data.n_configs -- sector_augment "
                             "appends int(fraction * this) extra configs AFTER this many, so "
                             "slicing by pre-augment count (not by divisibility with n_chains, "
                             "which can accidentally still divide evenly, as it does here: "
                             "448*1.5=672=42*16) is the only reliable way to exclude them")
    args = parser.parse_args()

    paths = sorted(glob.glob(f"{args.data_dir}/*.pt"),
                    key=lambda p: float(Path(p).stem.split("beta")[1]))
    if not paths:
        print(f"no ensembles found under {args.data_dir}")
        return 1

    print(f"{'beta':>8} {'n_cfg':>6} {'n_pre_aug':>10}  "
          f"{'plaq':>9} {'exact':>9} {'z':>7}   {'<Q^2>':>7} {'exact':>7} {'z':>7}")

    n_flagged = 0
    for p in paths:
        configs, meta = load_ensemble(p)
        beta = meta["beta"]
        size = meta["lattice_size"]
        action_type = meta.get("action_type", "wilson")
        n_chains = args.n_chains
        n_cfg = configs.shape[0]

        plaq_per_config = torch.cos(plaquette_angles(configs)).mean(dim=(1, 2)).numpy()
        q_per_config = topological_charge(configs).numpy()
        q2_per_config = q_per_config ** 2

        # sector_augment appends non-chain-structured configs at the end --
        # exclude them from the chain-resampling bootstrap, matching u2's
        # check script's own caveat about the same mechanism. Sliced by the
        # KNOWN pre-augment count, not by divisibility with n_chains: that
        # heuristic silently fails here (448*1.5=672=42*16, still evenly
        # divisible, so it let the augmented tail through undetected).
        n_pre_aug = min(args.n_configs_before_augment, n_cfg)
        n_pre_aug = (n_pre_aug // n_chains) * n_chains
        if n_pre_aug == 0:
            print(f"  ! {p}: n_configs={n_cfg} < n_chains={n_chains}, skipping")
            continue
        n_draws = n_pre_aug // n_chains
        plaq_chains = plaq_per_config[:n_pre_aug].reshape(n_draws, n_chains)
        q2_chains = q2_per_config[:n_pre_aug].reshape(n_draws, n_chains)

        plaq_val, plaq_err = chain_bootstrap(plaq_chains, n_boot=args.n_boot, seed=0)
        q2_val, q2_err = chain_bootstrap(q2_chains, n_boot=args.n_boot, seed=1)

        plaq_ex = plaquette_exact(beta, action_type, size)
        q2_ex = topological_susceptibility_exact(beta, action_type, size) * size * size

        plaq_z = (plaq_val - plaq_ex) / plaq_err if plaq_err > 0 else float("nan")
        q2_z = (q2_val - q2_ex) / q2_err if q2_err > 0 else float("nan")

        flag = ""
        if math.isfinite(plaq_z) and abs(plaq_z) > 3:
            flag += " !PLAQ"
        if math.isfinite(q2_z) and abs(q2_z) > 3:
            flag += " !Q2"
        if flag:
            n_flagged += 1

        print(f"{beta:8.1f} {n_cfg:6d} {n_pre_aug:10d}  "
              f"{plaq_val:9.6f} {plaq_ex:9.6f} {plaq_z:7.2f}   "
              f"{q2_val:7.4f} {q2_ex:7.4f} {q2_z:7.2f}{flag}")

    print()
    if n_flagged:
        print(f"{n_flagged} rung(s) flagged (|z| > 3) -- review before using "
              "this data for a retrain")
        return 1
    print("all rungs consistent with the closed form (|z| <= 3 on both "
          "plaquette and <Q^2>, pre-augmentation configs only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
