"""Stage 13: seconds per independent configuration, ladder vs the classical baseline.

This is the number the U(1) study led with and the first thing a referee asks for.
It has to be stated carefully, because the two arms are not comparable on every
observable and pretending otherwise would be the easiest way to overclaim here.

WHAT IS COMPARABLE. For LOCAL observables — the plaquette and small Wilson loops —
both arms produce correct samples, so cost per independent configuration is a fair
head-to-head. For a Markov chain that cost is

    t_indep = 2 tau_int * seconds_per_trajectory / n_chains,

since n_chains advance together and each yields one independent configuration
every 2 tau_int trajectories. tau_int is measured on the EQUILIBRATED TAIL only:
including the burn-in transient inflates it by counting a one-way relaxation as
autocorrelation.

WHAT IS NOT COMPARABLE. Topology. At the couplings the ladder exists for, the
classical arm cannot produce a correct sector distribution at ANY cost — the
winding update reaches even charge only, so the odd sectors have probability zero
in its stationary distribution rather than merely long autocorrelation. A ratio of
seconds is meaningless against an arm that never gets there. That case is reported
as a coverage statement, not a speed-up.

THE LADDER'S COST is charged in full and honestly: the base ensemble, every rung
below the target, and the target rung, divided by the configurations delivered at
the top. Amortization matters — the base is generated once and lifted many times —
so both the amortized and the un-amortized numbers are printed.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def tau_int_tail(series: np.ndarray, c: float = 5.0, tail: float = 0.5) -> float:
    """tau_int on the equilibrated tail of a scalar series.

    `tail` keeps the final fraction of the series. A relaxing chain's early
    samples are a one-way drift, not fluctuation, and Sokal windowing reads that
    drift as enormous autocorrelation -- which would flatter the ladder by
    inflating the baseline's cost.
    """
    x = np.asarray(series, dtype=float)
    x = x[int(len(x) * (1.0 - tail)):]
    if x.size < 8 or x.var() == 0:
        return float("nan")
    x = x - x.mean()
    acf = np.correlate(x, x, mode="full")[x.size - 1:] / (x.var() * x.size)
    tau = 0.5
    for w in range(1, x.size):
        tau += acf[w]
        if w >= c * tau:
            break
    return float(max(tau, 0.5))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", default="out/u2_2d/seed_benchmark/seed_benchmark.json")
    parser.add_argument("--out", default="out/u2_2d/seed_benchmark/cost.json")
    parser.add_argument("--base-seconds", type=float, default=115.0,
                        help="wall-clock for the base ensemble (stage 01)")
    parser.add_argument("--base-configs", type=int, default=1024)
    parser.add_argument("--rung-seconds", default="59,246",
                        help="wall-clock per ladder rung, comma separated")
    parser.add_argument("--rung-configs", type=int, default=512)
    args = parser.parse_args()

    bench = json.loads(Path(args.benchmark).read_text(encoding="utf-8"))
    n_chains = bench["n_chains"]
    record_every = bench["arms"][0]["history"][1]["trajectory"] - \
        bench["arms"][0]["history"][0]["trajectory"]

    rows = []
    for arm in bench["arms"]:
        plaq = [h["plaquette"] for h in arm["history"]]
        # tau_int comes back in units of RECORDED samples; convert to trajectories.
        tau = tau_int_tail(plaq) * record_every
        sec_per_traj = arm["seconds_per_trajectory"]
        t_indep = 2.0 * tau * sec_per_traj / n_chains if np.isfinite(tau) else float("nan")
        topo = arm["topology"]
        rows.append({
            "arm": arm["arm"],
            "tau_int_plaquette_trajectories": tau,
            "seconds_per_trajectory": sec_per_traj,
            "seconds_per_independent_config_local": t_indep,
            "exact_probability_covered": topo["exact_probability_covered"],
            "odd_sectors_visited": len(topo["odd_sectors_visited"]),
        })

    rung_seconds = [float(x) for x in args.rung_seconds.split(",")]
    ladder_total = args.base_seconds + sum(rung_seconds)
    per_config_full = ladder_total / args.rung_configs
    per_config_amortized = sum(rung_seconds) / args.rung_configs
    top_rung_only = rung_seconds[-1] / args.rung_configs

    classical = next((r for r in rows if r["arm"] == "D_cold_plus_winding"), None)
    plain = next((r for r in rows if r["arm"] == "B_cold_start"), None)

    summary = {
        "lattice_size": bench["lattice_size"],
        "beta": bench["beta"],
        "n_chains": n_chains,
        "arms": rows,
        "ladder": {
            "base_seconds": args.base_seconds,
            "rung_seconds": rung_seconds,
            "total_seconds": ladder_total,
            "configs_delivered": args.rung_configs,
            "seconds_per_config_including_base": per_config_full,
            "seconds_per_config_amortized_base": per_config_amortized,
            "seconds_per_config_top_rung_only": top_rung_only,
        },
    }
    if classical and np.isfinite(classical["seconds_per_independent_config_local"]):
        summary["speedup_local_vs_hmc_winding"] = (
            classical["seconds_per_independent_config_local"] / per_config_full)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"L = {bench['lattice_size']}, beta = {bench['beta']:g}, "
          f"{n_chains} chains\n")
    print(f"{'arm':22s} {'tau_int(P)':>11s} {'s/traj':>8s} {'s/indep cfg':>12s} "
          f"{'P(Q) cov':>9s} {'odd':>4s}")
    for r in rows:
        print(f"{r['arm']:22s} {r['tau_int_plaquette_trajectories']:11.1f} "
              f"{r['seconds_per_trajectory']:8.3f} "
              f"{r['seconds_per_independent_config_local']:12.4f} "
              f"{r['exact_probability_covered']:9.3f} {r['odd_sectors_visited']:4d}")

    print(f"\nladder: base {args.base_seconds:.0f}s + rungs {rung_seconds} "
          f"-> {args.rung_configs} configurations at L = {bench['lattice_size']}")
    print(f"  including base generation : {per_config_full:.4f} s / configuration")
    print(f"  base amortized away      : {per_config_amortized:.4f} s / configuration")
    print(f"  top rung only            : {top_rung_only:.4f} s / configuration")
    if "speedup_local_vs_hmc_winding" in summary:
        s = summary["speedup_local_vs_hmc_winding"]
        verdict = f"{s:.2f}x FASTER" if s > 1 else f"{1/s:.2f}x SLOWER"
        print(f"\nLOCAL observables vs hmc+winding: ladder is {verdict}")
    print("\nTOPOLOGY is not a speed-up, it is a reachability statement: the "
          "classical arm\ncovers "
          f"{classical['exact_probability_covered']:.3f} of the exact P(Q) with "
          f"{classical['odd_sectors_visited']} odd sectors and cannot improve on "
          "that at any\ncost, because odd charge has probability zero in its "
          "stationary distribution.")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
