"""What does `t_therm` report on an ensemble that is ALREADY thermalized?

`docs/PARITY_U1_U2.md` section 5 item 10 records this as an OPEN u1 audit
obligation: `07_pq_sampling.py`'s categorical verdicts turned out to be
uncalibrated in u2 -- misfiring 13% of the time on exact data while having
essentially no power on the pathology they existed to catch -- and the same
question was never asked of u1's `t_therm`, which is the headline metric of the
seed-quality claim (Table S6b, Fig. 12).

The rule (`05_hmc_thermalization.py::thermalization_time`) is: the first record
`t` at which |z| <= 2 and stays there for 5 consecutive records, where z is the
across-chain mean against the exact value divided by a NAIVE across-chain SEM.

The null is not obviously zero. For a perfectly equilibrated ensemble each z is
standard normal, so P(|z| <= 2) = 0.954 per record and a run of five requires
five successes -- which fails about a fifth of the time at the first record even
though nothing is wrong. Records are also autocorrelated along the chain, which
makes the failures sticky rather than independent.

This script measures the resulting distribution directly, with NO simulation:
it draws synthetic z-series under the null (correct mean, correct errors) at a
range of autocorrelation times and reads off what `t_therm` reports. The point
is to establish the resolution floor of the metric, so that a claimed
difference can be checked against it.

    .venv/Scripts/python.exe u1_2d/scripts/65_therm_criterion_calibration.py

Runs in seconds.
"""

import argparse
import importlib.util
import json
import math
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]


def _load_05():
    spec = importlib.util.spec_from_file_location(
        "therm05", REPO / "u1_2d" / "scripts" / "05_hmc_thermalization.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ar1_series(rng, n_traj: int, n_chains: int, tau: float) -> np.ndarray:
    """[n_traj, n_chains] AR(1) noise with unit marginal variance.

    tau is the integrated autocorrelation time in the Madras-Sokal convention,
    tau = (1 + phi) / (1 - phi) for AR(1), so phi = (tau - 1) / (tau + 1).
    tau = 1 gives independent records.
    """
    phi = (tau - 1.0) / (tau + 1.0)
    x = np.empty((n_traj, n_chains))
    x[0] = rng.standard_normal(n_chains)
    scale = math.sqrt(1.0 - phi * phi)
    for t in range(1, n_traj):
        x[t] = phi * x[t - 1] + scale * rng.standard_normal(n_chains)
    return x


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-chains", type=int, default=64,
                    help="Table S6b and Fig. 12 both use 64.")
    ap.add_argument("--n-traj", type=int, default=640)
    ap.add_argument("--n-replicas", type=int, default=2000)
    ap.add_argument("--taus", type=float, nargs="+", default=[1.0, 2.0, 5.0, 10.0])
    ap.add_argument("--bias-sigmas", type=float, nargs="+",
                    default=[0.0, 0.5, 1.0, 2.0, 4.0],
                    help="offset of the ensemble mean, in units of the SEM; "
                         "0 is the true null, the rest measure POWER.")
    ap.add_argument("--seed", type=int, default=20260824)
    ap.add_argument("--out", default="out/u1_2d/therm_calibration")
    args = ap.parse_args()

    m5 = _load_05()
    rng = np.random.default_rng(args.seed)
    out_dir = REPO / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    # thermalization_time consumes a [n_traj, n_chains] series of the OBSERVABLE
    # and forms z itself, so feed it a series whose across-chain mean sits the
    # requested number of standard errors away from `target`. With unit
    # per-configuration variance the SEM is 1/sqrt(n_chains).
    sem = 1.0 / math.sqrt(args.n_chains)
    rows = []
    for tau in args.taus:
        for bias in args.bias_sigmas:
            vals = []
            for _ in range(args.n_replicas):
                series = ar1_series(rng, args.n_traj, args.n_chains, tau)
                series = series + bias * sem
                vals.append(m5.thermalization_time(series, 0.0))
            arr = np.array(vals, dtype=float)
            finite = arr[np.isfinite(arr)]
            rows.append({
                "tau_int": tau,
                "bias_sems": bias,
                "frac_t0": float((arr == 0).mean()),
                "median": float(np.median(finite)) if finite.size else None,
                "p90": float(np.percentile(finite, 90)) if finite.size else None,
                "max": float(finite.max()) if finite.size else None,
                "frac_never": float((~np.isfinite(arr)).mean()),
            })
            print(f"  tau={tau:<5} bias={bias:<4} t_therm=0 in "
                  f"{rows[-1]['frac_t0']:.1%}  median={rows[-1]['median']}  "
                  f"p90={rows[-1]['p90']}  never={rows[-1]['frac_never']:.1%}",
                  flush=True)

    (out_dir / "therm_calibration.json").write_text(
        json.dumps({"config": vars(args), "rows": rows}, indent=2), encoding="utf-8")

    null = [r for r in rows if r["bias_sems"] == 0.0]
    print("\n## The null: a PERFECTLY thermalized ensemble\n")
    print("| tau_int | t_therm = 0 | median | 90th pct |")
    print("|---|---|---|---|")
    for r in null:
        print(f"| {r['tau_int']:g} | {r['frac_t0']:.1%} | {r['median']:g} | {r['p90']:g} |")
    print("\nRead the 90th percentile as the resolution floor: a t_therm at or "
          "below it is consistent with an ensemble that was already in "
          "equilibrium, so differences inside that range are not measurements.")
    print(f"\nwrote {(out_dir / 'therm_calibration.json').relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
