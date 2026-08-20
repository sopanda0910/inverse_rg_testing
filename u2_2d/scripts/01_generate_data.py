"""Stage 01: generate reference U(2) ensembles by HMC.

One ensemble per configured rung, saved as [N, 2, L, L, 5] CPU tensors. These are
both the training data for the determinant score net (stage 02) and the reference
distributions validation compares against (stage 04).

DEVICE -- and the U(2) rule is NOT the U(1) rule. Measured on this machine
(Ryzen 7 260 single thread vs RTX 5060), GPU/CPU trajectory rate:

    L=8/32ch 0.52x | L=16/32ch 1.34x | L=32/32ch 4.67x | L=32/64ch 8.30x | L=64 40x

The crossover is L=16, not L=64 as it is for U(1), because a quaternion link
carries roughly six times the arithmetic of an angle, so each kernel launch does
enough work to pay for itself two factors of two earlier. GPU throughput is flat
at ~5 traj/s from L=16 to L=64 -- purely launch-bound -- so on the GPU the large
lattices are almost free. Run the L=8 rungs on CPU and everything else on GPU:
`--only-sizes 8 --device cpu` alongside `--only-sizes 16,32 --device cuda`.

Topological updates default ON at charge step 2, which is the cheap purely central
winding move. It cannot change the parity of Q; where odd sectors matter, raise
`winding_charge_step` to 1 and expect a much lower acceptance (see the module
comment in `lgt/local_updates.py` for why that is intrinsic to U(2)).

THERMALIZATION. HMC burn-in is the dominant cost of this stage and it is the
wrong tool for the job: local modes are what need equilibrating, and heatbath
plus overrelaxation equilibrates them far faster per unit of work than HMC
trajectories do. `thermalize_sweeps` runs that first (each sweep is one heatbath
plus two overrelaxation passes, all exact for the same action), after which the
HMC burn-in only has to put the chain into its own stationary regime rather than
do the thermalizing. Measured trade at L = 32: 60 sweeps plus 200 trajectories
replaces 2000 trajectories, about 7x cheaper. Composing exact updates of one
action is valid MCMC, and the check is printed every run -- the measured
plaquette against the closed form.

Topology is NOT what this equilibrates: local updates do not tunnel above the
freezing threshold. That is what `seed_exact_sectors` is for, and it runs first
so the sweeps inherit the seeded sectors and preserve them.

Sharding follows the contract in `u1_2d/scripts/shard_runner.py`: `--shard I/N`
takes rungs with `index % N == I` (round-robin, because burn_in and L cluster by
family and interleaving is what balances the shards), each shard writes its own
`summary.shard<I>.json`, and `--merge-shards` folds them into `summary.json`.
Batched HMC here is latency-bound, so the way to use the machine is one
single-threaded process per physical core -- set U2_2D_TORCH_THREADS=1 and fan
out. Threads inside one shard make it slower, not faster.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u2_2d.lgt.actions import WilsonU2Action
from u2_2d.lgt.exact import det_topological_susceptibility, plaquette_exact
from u2_2d.lgt.hmc import BatchedHMCU2, adapted_hmc_params, run_hmc_ensemble
from u2_2d.lgt.lattice import half_retr, plaquette, topological_charge
from u2_2d.lgt.local_updates import retherm_sweeps
from u2_2d.lgt.sector_seed import seed_exact_sectors
from u2_2d.utils import (
    configure_device,
    ensemble_path,
    load_config,
    resolve_device,
    save_ensemble,
    save_json,
    set_seed,
    to_cpu,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="u2_2d/configs/smoke.yaml")
    parser.add_argument("--device", default=None)
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--shard", default=None,
                        help="I/N: take rungs with index %% N == I (after --only-sizes)")
    parser.add_argument("--only-sizes", default=None,
                        help="comma-separated lattice sizes to keep, e.g. 16,32")
    parser.add_argument("--merge-shards", action="store_true",
                        help="fold summary.shard*.json into summary.json and delete them")
    parser.add_argument("--only-betas", default=None,
                        help="comma-separated couplings to generate; combines with "
                             "--only-sizes. Lets one rung be regenerated on its own "
                             "recipe without touching the ensembles of record.")
    parser.add_argument("--overwrite", action="store_true",
                        help="regenerate rungs whose ensemble is already on disk")
    args = parser.parse_args()

    threads = os.environ.get("U2_2D_TORCH_THREADS") or os.environ.get("U1_2D_TORCH_THREADS")
    if threads:
        torch.set_num_threads(int(threads))

    config = load_config(args.config)
    if args.device:
        config["device"] = args.device
    device = resolve_device(config)
    print(configure_device(device))
    set_seed(int(config.get("seed", 0)))

    data_cfg = config["data"]
    out_dir = Path(args.out_dir or data_cfg.get("out_dir", "out/u2_2d/data"))
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.merge_shards:
        return merge_shards(out_dir)

    rungs = list(data_cfg["rungs"])
    shard_index = None
    if args.only_sizes:
        keep = {int(v) for v in args.only_sizes.split(",")}
        rungs = [r for r in rungs if int(r["lattice_size"]) in keep]
    if args.only_betas:
        keep_b = {float(v) for v in args.only_betas.split(",")}
        rungs = [r for r in rungs
                 if any(abs(float(r["beta"]) - b) < 1e-9 for b in keep_b)]
    if args.overwrite:
        data_cfg["overwrite"] = True
    if args.shard:
        shard_index, n_shards = (int(v) for v in args.shard.split("/"))
        rungs = [r for i, r in enumerate(rungs) if i % n_shards == shard_index]
        print(f"shard {shard_index}/{n_shards}: "
              + ", ".join(f"L{r['lattice_size']}b{r['beta']:g}" for r in rungs))

    summary = []
    for rung in rungs:
        beta = float(rung["beta"])
        size = int(rung["lattice_size"])
        path = ensemble_path(out_dir, size, beta)
        if path.exists() and not data_cfg.get("overwrite", False):
            print(f"skip  L={size} beta={beta:g} (exists)")
            continue
        step_size, n_steps = adapted_hmc_params(beta)
        # Per-rung override: where topology is SAMPLED rather than seeded, the
        # number of independent charges is what the sector claim rests on, and
        # chains are the cheap axis at small L.
        n_chains = int(rung.get("n_chains", data_cfg.get("n_chains", 16)))
        t0 = time.time()
        # Above the freezing threshold no local dynamics equilibrates P(Q) in U(2)
        # -- the only cheap global move is even-charge -- so the chains are started
        # from sectors drawn out of the exact determinant P(Q). See
        # lgt/sector_seed.py for why this is exact and for what it forfeits.
        action = WilsonU2Action(beta)
        seeded = None
        do_seed = bool(rung.get("seed_exact_sectors",
                                data_cfg.get("seed_exact_sectors", False)))
        n_therm = int(rung.get("thermalize_sweeps", data_cfg.get("thermalize_sweeps", 0)))
        if do_seed or n_therm:
            sampler = BatchedHMCU2(size, action, n_chains=n_chains, device=device,
                                   hot_start=bool(rung.get("hot_start", beta < 4.0)))
            seeded = sampler.initialize().cpu()
            if do_seed:
                seeded = seed_exact_sectors(seeded, beta)
            if n_therm:
                seeded = retherm_sweeps(seeded, action, n_therm)
                print(f"  L={size} beta={beta:g}: {n_therm} thermalization sweeps -> "
                      f"plaq {float(half_retr(plaquette(seeded)).mean()):.5f} "
                      f"(exact {plaquette_exact(beta, size):.5f}), "
                      f"<Q^2> {float(topological_charge(seeded).square().mean()):.3f}",
                      flush=True)
            seeded = seeded.to(device)
        configs, stats = run_hmc_ensemble(
            size,
            action,
            int(rung.get("n_configs", data_cfg.get("n_configs", 512))),
            n_chains=n_chains,
            burn_in=int(rung.get("burn_in", data_cfg.get("burn_in", 300))),
            thin=int(data_cfg.get("thin", 4)),
            n_steps=n_steps,
            step_size=step_size,
            device=device,
            topological_updates=bool(data_cfg.get("topological_updates", True)),
            winding_charge_step=int(data_cfg.get("winding_charge_step", 2)),
            hot_start=bool(rung.get("hot_start", beta < 4.0)),
            initial_state=seeded,
        )
        configs = to_cpu(configs)
        measured = float(half_retr(plaquette(configs)).mean())
        q_squared = float(topological_charge(configs).square().mean())
        metadata = {
            "beta": beta,
            "lattice_size": size,
            "n_configs": int(configs.shape[0]),
            # The chain axis is not recoverable from the tensor -- `sample` stacks
            # draw-major and flattens -- but downstream stages need it: the number of
            # INDEPENDENT topological charges is n_chains, and subsampling that is
            # blind to the chain layout can silently keep a quarter of them.
            "n_chains": n_chains,
            "acceptance_rate": stats.acceptance_rate,
            "winding_acceptance_rate": stats.winding_acceptance_rate,
            "plaquette": measured,
            "plaquette_exact": plaquette_exact(beta, size),
            "q_squared": q_squared,
            "q_squared_exact": det_topological_susceptibility(beta, size) * size * size,
            "seconds": time.time() - t0,
            "sector_seeded": do_seed,
            "thermalize_sweeps": n_therm,
        }
        save_ensemble(path, configs, metadata)
        summary.append(metadata)
        print(f"wrote L={size} beta={beta:g}  plaq={measured:.5f} "
              f"(exact {metadata['plaquette_exact']:.5f})  "
              f"<Q^2>={q_squared:.3f} (exact {metadata['q_squared_exact']:.3f})  "
              f"acc={stats.acceptance_rate:.3f}  [{metadata['seconds']:.0f}s]")

    if summary:
        tag = "" if not args.only_sizes else "L" + args.only_sizes.replace(",", "-")
        name = ("summary.json" if shard_index is None
                else f"summary.shard{tag}_{shard_index}.json")
        if shard_index is None:
            # MERGE, do not replace. A filtered run (`--only-sizes`) still lands on
            # the canonical name, so writing it straight through silently discards
            # every rung the filter excluded -- which is most of them, and which is
            # how the L = 16 base's generation record was lost once already. Rows
            # are keyed by (L, beta) so a rerun of a rung supersedes its own entry
            # and nothing else. Carried-over rows are printed, because the cost of
            # this policy is that a row from a superseded config survives until
            # something overwrites it.
            existing = {}
            path = out_dir / name
            if path.exists():
                import json as _json
                for row in _json.loads(path.read_text(encoding="utf-8")):
                    existing[(int(row["lattice_size"]), float(row["beta"]))] = row
            fresh = {(int(r["lattice_size"]), float(r["beta"])) for r in summary}
            carried = [k for k in existing if k not in fresh]
            if carried:
                print("carried over " + ", ".join(f"L{L}b{b:g}" for L, b in sorted(carried)))
            for r in summary:
                existing[(int(r["lattice_size"]), float(r["beta"]))] = r
            summary = [existing[k] for k in sorted(existing)]
        save_json(out_dir / name, summary)
    return 0


def merge_shards(out_dir: Path) -> int:
    """Fold per-shard summaries into the canonical one and delete them.

    Aggregates are deferred to here on purpose: a shard sees a fraction of the
    rungs, and a summary built from that fraction looks perfectly valid.
    """
    canonical = out_dir / "summary.json"
    merged = json.loads(canonical.read_text(encoding="utf-8")) if canonical.exists() else []
    seen = {(row["lattice_size"], row["beta"]) for row in merged}
    shards = sorted(out_dir.glob("summary.shard*.json"))
    for path in shards:
        for row in json.loads(path.read_text(encoding="utf-8")):
            key = (row["lattice_size"], row["beta"])
            if key not in seen:
                merged.append(row)
                seen.add(key)
    merged.sort(key=lambda row: (row["lattice_size"], row["beta"]))
    save_json(canonical, merged)
    for path in shards:
        path.unlink()
    print(f"merged {len(shards)} shard summaries -> {canonical} ({len(merged)} rungs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
