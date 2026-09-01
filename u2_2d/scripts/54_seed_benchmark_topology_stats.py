"""Stage 54: chain-aware significance for the seed-benchmark's topology claim.

`08_hmc_seed_benchmark.py` reports raw <Q^2> and sector coverage with no error
bars, which is not enough to say "the seed matches the exact P(Q) and the
classical arms do not" -- it only says what each arm's point estimate was.
This reuses the CALIBRATED machinery already built and calibrated for exactly
this (`07_pq_sampling.py`'s `chain_bootstrap` and `sector_goodness_of_fit`,
`48_verdict_calibration.py`) and applies it to every arm in the seed-benchmark
output: <Q^2> mean +- SEM +- z against the closed form, a charge-conjugation
check (mean(sign Q), which needs no closed form at all), and a sector
goodness-of-fit against the exact P(Q) histogram.

Deliberately scoped to topology only. Wilson-loop MEANS are not chain-aware
error-barred here because `08_hmc_seed_benchmark.py`'s `measure()` only
records the batch mean at each step, not a per-chain series -- doing that
properly needs a code change to `measure()` and a full rerun of all 8 arms,
which is a separate, larger task.

    python u2_2d/scripts/54_seed_benchmark_topology_stats.py
"""

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u2_2d.lgt.exact import det_topological_charge_distribution

_spec = importlib.util.spec_from_file_location(
    "pq07", Path(__file__).parent / "07_pq_sampling.py")
pq07 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pq07)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", default="out/u2_2d/seed_benchmark/seed_benchmark.json")
    parser.add_argument("--out", default="out/u2_2d/seed_benchmark/topology_stats.json")
    parser.add_argument("--tail", type=float, default=0.5,
                        help="fraction of the trajectory history kept (discards burn-in)")
    args = parser.parse_args()

    bench = json.loads(Path(args.benchmark).read_text(encoding="utf-8"))
    beta, size = bench["beta"], bench["lattice_size"]
    q_values, probs = det_topological_charge_distribution(beta, size)
    q_values = np.asarray(q_values)
    exact_q2 = float(np.sum(probs * q_values**2))

    rows = []
    for arm in bench["arms"]:
        charge = np.stack([h["charge"] for h in arm["history"]])  # [n_records, n_chains]
        t0 = int(charge.shape[0] * (1.0 - args.tail))
        tail = charge[t0:]

        q2_mean, q2_sem = pq07.chain_bootstrap(tail**2, np.mean)
        q2_z = (q2_mean - exact_q2) / max(q2_sem, 1e-12)

        casym_mean, casym_sem = pq07.chain_bootstrap(np.sign(tail), np.mean)
        casym_z = casym_mean / max(casym_sem, 1e-12)

        gof = pq07.sector_goodness_of_fit(np.round(tail), q_values, probs)

        rows.append({
            "arm": arm["arm"],
            "q_squared_mean": q2_mean,
            "q_squared_sem": q2_sem,
            "q_squared_exact": exact_q2,
            "q_squared_z": q2_z,
            "charge_conjugation_asymmetry_z": casym_z,
            "sector_gof_chi2": gof["gof_chi2"],
            "sector_gof_dof": gof["gof_dof"],
            "sector_gof_p": gof["gof_p"],
            "sector_gof_bins": gof["gof_bins"],
            "exact_probability_covered": arm["topology"]["exact_probability_covered"],
            "odd_sectors_visited": len(arm["topology"]["odd_sectors_visited"]),
            "n_chains_bootstrapped": tail.shape[1],
            "n_draws_kept": tail.shape[0],
        })

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(
        {"beta": beta, "lattice_size": size, "tail_fraction": args.tail,
         "exact_q_squared": exact_q2, "arms": rows}, indent=2), encoding="utf-8")

    print(f"L = {size}, beta = {beta:g}, exact <Q^2> = {exact_q2:.4f}, "
          f"tail = last {args.tail:.0%} of {bench['n_trajectories']} trajectories\n")
    print(f"{'arm':30s} {'<Q^2>':>9s} {'SEM':>7s} {'z':>7s}  {'C-asym z':>9s}  "
          f"{'gof p':>7s} {'P(Q) cov':>9s} {'odd':>4s}")
    for r in rows:
        print(f"{r['arm']:30s} {r['q_squared_mean']:9.4f} {r['q_squared_sem']:7.4f} "
              f"{r['q_squared_z']:+7.2f}  {r['charge_conjugation_asymmetry_z']:+9.2f}  "
              f"{r['sector_gof_p']:7.3f} {r['exact_probability_covered']:9.3f} "
              f"{r['odd_sectors_visited']:4d}")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
