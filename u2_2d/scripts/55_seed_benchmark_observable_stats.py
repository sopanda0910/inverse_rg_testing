"""Stage 55: chain-aware significance for the seed-benchmark's Wilson-loop means.

Companion to `54_seed_benchmark_topology_stats.py`, same reasoning applied to
the plaquette and W(2x2)/W(4x4)/W(8x8) instead of charge. `08_hmc_seed_benchmark.py`
used to report only a batch mean per step, with no error bar at all --
`measure()` now also records a per-chain mean (`<name>_chain`) at every step, so
a proper per-chain time-average -> SEM-over-chains estimate (the same
`chain_bootstrap` primitive `54_` uses, and the same construction as u1's
`chain_stats` in `14_diffusion_vs_instanton_hmc.py`) is possible here too.

Requires arm_*.json produced by the rerun `08_hmc_seed_benchmark.py` after the
`measure()` change that adds `<name>_chain` -- caches from before that change
do not have it and this script will say so per-arm rather than fail silently.

    python u2_2d/scripts/55_seed_benchmark_observable_stats.py
"""

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u2_2d.lgt.exact import plaquette_exact, wilson_loop_exact

_spec = importlib.util.spec_from_file_location(
    "pq07", Path(__file__).parent / "07_pq_sampling.py")
pq07 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pq07)

LOOPS = {"plaquette": 1, "wilson_2x2": 4, "wilson_4x4": 16, "wilson_8x8": 64}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", default="out/u2_2d/seed_benchmark/seed_benchmark.json")
    parser.add_argument("--arm-dir", default=None)
    parser.add_argument("--out", default="out/u2_2d/seed_benchmark/observable_stats.json")
    parser.add_argument("--tail", type=float, default=0.5,
                        help="fraction of the trajectory history kept (discards burn-in)")
    args = parser.parse_args()

    bench = json.loads(Path(args.benchmark).read_text(encoding="utf-8"))
    beta, size = bench["beta"], bench["lattice_size"]
    arm_dir = Path(args.arm_dir) if args.arm_dir else Path(args.benchmark).parent

    exact = {"plaquette": plaquette_exact(beta, size)}
    for name, area in LOOPS.items():
        if name == "plaquette":
            continue
        if area <= (size // 2) ** 2:
            exact[name] = wilson_loop_exact(beta, area)

    rows = []
    for arm in bench["arms"]:
        raw = json.loads((arm_dir / f"arm_{arm['arm']}.json").read_text(encoding="utf-8"))
        n_records = len(raw["history"])
        t0 = int(n_records * (1.0 - args.tail))

        entry = {"arm": arm["arm"]}
        for name in exact:
            key = f"{name}_chain"
            if key not in raw["history"][0]:
                entry[name] = {"error": "no per-chain series in cache -- rerun stage 08"}
                continue
            series = np.stack([np.asarray(h[key]) for h in raw["history"][t0:]])  # [n_draws, n_chains]
            mean, sem = pq07.chain_bootstrap(series, np.mean)
            z = (mean - exact[name]) / sem if sem > 1e-12 else (
                0.0 if abs(mean - exact[name]) < 1e-12 else float("inf"))
            entry[name] = {"mean": mean, "sem": sem, "exact": exact[name], "z": z}
        rows.append(entry)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(
        {"beta": beta, "lattice_size": size, "tail_fraction": args.tail,
         "exact": exact, "arms": rows}, indent=2), encoding="utf-8")

    names = list(exact)
    header = "arm".ljust(30) + "".join(f"{n:>16s}" for n in names)
    print(f"L = {size}, beta = {beta:g}, tail = last {args.tail:.0%} of "
          f"{bench['n_trajectories']} trajectories\n")
    print(header)
    for r in rows:
        cells = []
        for n in names:
            v = r.get(n, {})
            cells.append("   n/a (no data)" if "error" in v else f"{v['z']:+16.2f}")
        print(r["arm"].ljust(30) + "".join(cells))
    print("\n(cells are z-scores against the exact closed-form value)")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
