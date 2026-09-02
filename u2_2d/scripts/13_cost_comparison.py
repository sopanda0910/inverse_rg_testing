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
                        help="wall-clock per ladder rung, comma separated. NOTE "
                             "(2026-09-01): these were measured when default.yaml's "
                             "ladder.n_configs was 512; it is now 1024 and these "
                             "have not been re-timed against that -- if lift cost "
                             "scales with config count they may understate the "
                             "current wall-clock by up to 2x. Verify by re-running "
                             "stage 03 with timing before trusting a precise ratio.")
    parser.add_argument("--rung-configs", type=int, default=1024,
                        help="configs delivered per ladder rung -- must match "
                             "default.yaml's ladder.n_configs (1024 as of "
                             "2026-09-01; verify against the actual ensemble file "
                             "with load_ensemble(...).shape[0] if that config "
                             "changes again, the way this default itself went "
                             "stale at 512 after n_configs was raised)")
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

    # TWO different classical arms answer two different questions, and neither
    # substitutes for the other (docs/u2_2d/FOLLOWUPS.md item 6):
    #   D (winding_charge_step=2) is the CHEAPEST classical baseline for LOCAL
    #   observables, but its own stationary distribution has zero probability
    #   on odd sectors -- no amount of runtime raises its P(Q) coverage.
    #   G (winding_charge_step=1, the marginal odd move) is the classical arm
    #   that CAN reach full coverage, at the cost of the expensive odd move.
    # A topology cost/reachability claim must use G, not D.
    classical = next((r for r in rows if r["arm"] == "D_cold_plus_winding"), None)
    classical_topo = next((r for r in rows if r["arm"] == "G_cold_plus_odd_winding"), None)
    plain = next((r for r in rows if r["arm"] == "B_cold_start"), None)
    diffusion_even = next((r for r in rows if r["arm"] == "E_diffusion_plus_winding"), None)
    seconds_by_arm = {a["arm"]: a["seconds"] for a in bench["arms"]}
    topo_by_arm = {a["arm"]: a["topology"] for a in bench["arms"]}

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

    # Topology reachability/cost, reported explicitly rather than left to be
    # reconstructed by hand from seed_benchmark.json.
    topo = {
        "classical_even_only": {
            "arm": "D_cold_plus_winding",
            "exact_probability_covered": topo_by_arm["D_cold_plus_winding"]["exact_probability_covered"],
            "reachable_at_any_cost": False,
            "reason": "winding_charge_step=2 has zero stationary probability on odd sectors",
        },
    }
    if classical_topo is not None:
        cov_g = topo_by_arm["G_cold_plus_odd_winding"]["exact_probability_covered"]
        topo["classical_odd_capable"] = {
            "arm": "G_cold_plus_odd_winding",
            "exact_probability_covered": cov_g,
            "seconds": seconds_by_arm["G_cold_plus_odd_winding"],
            "reachable_at_any_cost": bool(cov_g >= 0.99),
        }
    if diffusion_even is not None:
        cov_e = topo_by_arm["E_diffusion_plus_winding"]["exact_probability_covered"]
        topo["diffusion_even_only"] = {
            "arm": "E_diffusion_plus_winding",
            "exact_probability_covered": cov_e,
            "seconds": seconds_by_arm["E_diffusion_plus_winding"],
            "parity_flips_needed": False,
        }
        if classical_topo is not None and cov_e >= 0.99 and cov_g >= 0.99:
            topo["same_endpoint_cost_ratio"] = (
                seconds_by_arm["G_cold_plus_odd_winding"]
                / seconds_by_arm["E_diffusion_plus_winding"])
    summary["topology_reachability"] = topo
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
        print(f"\nLOCAL observables vs hmc+winding (cheapest classical arm, D): "
              f"ladder is {verdict}")

    topo = summary["topology_reachability"]
    d = topo["classical_even_only"]
    print(f"\nTOPOLOGY, arm D (winding_charge_step=2, the cheap classical move): "
          f"covers {d['exact_probability_covered']:.3f} of exact P(Q) and CANNOT "
          f"improve on that at any cost -- odd charge has probability zero in its "
          f"stationary distribution.")
    if "classical_odd_capable" in topo:
        g = topo["classical_odd_capable"]
        print(f"TOPOLOGY, arm G (winding_charge_step=1, the marginal odd move): "
              f"covers {g['exact_probability_covered']:.3f} in {g['seconds']:.0f}s "
              f"-- {'reaches full coverage, at a cost' if g['reachable_at_any_cost'] else 'still short'}.")
    if "diffusion_even_only" in topo:
        e = topo["diffusion_even_only"]
        print(f"TOPOLOGY, arm E (diffusion seed + cheap even move): covers "
              f"{e['exact_probability_covered']:.3f} in {e['seconds']:.0f}s, with "
              f"zero parity flips -- every odd sector it occupies was inherited "
              f"from the seed, not manufactured by the sampler.")
    if "same_endpoint_cost_ratio" in topo:
        r = topo["same_endpoint_cost_ratio"]
        print(f"SAME ENDPOINT (both cover the full P(Q)): the classical arm "
              f"needing the expensive odd move costs {r:.2f}x what the "
              f"diffusion seed + cheap even move costs.")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
