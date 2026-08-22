"""Stage 03: climb the inverse-RG ladder.

Starts from an equilibrated coarse U(2) ensemble and repeatedly doubles L while
quadrupling beta. Each rung lifts the determinant sector with the diffusion model,
seeds the SU(2) sector by naive inverse blocking, equilibrates it exactly at
frozen determinant, and rethermalizes both sectors briefly.

Every rung records the observables before and after rethermalization, so it stays
visible how much of the agreement the model earned and how much the sweeps
repaired.
"""

import argparse
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u2_2d.lgt.exact import det_topological_susceptibility, plaquette_exact
from u2_2d.model.det_lift import load_det_model
from u2_2d.pipeline.ladder import generate_ladder
from u2_2d.utils import (
    configure_device,
    ensemble_path,
    load_config,
    load_ensemble,
    resolve_device,
    save_ensemble,
    save_json,
    set_seed,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="u2_2d/configs/smoke.yaml")
    parser.add_argument("--device", default=None)
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--no-resume", action="store_true",
                        help="regenerate every rung even if one is already on disk")
    # Base overrides, so a control ladder from a different base does not need a
    # duplicated config file that then drifts from the one of record.
    parser.add_argument("--base-beta", type=float, default=None)
    parser.add_argument("--base-size", type=int, default=None)
    parser.add_argument("--beta-schedule", nargs="+", type=float, default=None,
                        help="override the fine couplings; with --base-beta and "
                             "no schedule, the topology-matched one is derived")
    parser.add_argument("--n-configs", type=int, default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    if args.device:
        config["device"] = args.device
    if args.base_beta is not None or args.base_size is not None:
        base_cfg = config["ladder"]["base"]
        if args.base_beta is not None:
            base_cfg["beta"] = args.base_beta
        if args.base_size is not None:
            base_cfg["lattice_size"] = args.base_size
        if args.beta_schedule is None:
            from u2_2d.lgt.blocking import topology_matched_schedule

            config["ladder"]["beta_schedule"] = topology_matched_schedule(
                float(base_cfg["beta"]), int(base_cfg["lattice_size"]),
                len(config["ladder"]["beta_schedule"]),
            )
    if args.beta_schedule is not None:
        config["ladder"]["beta_schedule"] = list(args.beta_schedule)
    if args.n_configs is not None:
        config["ladder"]["n_configs"] = args.n_configs
    device = resolve_device(config)
    print(configure_device(device))
    set_seed(int(config.get("seed", 0)))

    ladder_cfg = config["ladder"]
    data_dir = Path(args.data_dir or config["data"].get("out_dir", "out/u2_2d/data"))
    out_dir = Path(args.out_dir or ladder_cfg.get("out_dir", "out/u2_2d/ladder"))
    out_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = args.checkpoint or config["train"].get(
        "checkpoint_path", "out/u2_2d/checkpoints/det_score_net.pt"
    )

    base = ladder_cfg["base"]
    base_path = ensemble_path(data_dir, int(base["lattice_size"]), float(base["beta"]))
    if not base_path.exists():
        print(f"missing base ensemble {base_path} -- run stage 01 first")
        return 1
    coarse, base_meta = load_ensemble(base_path)
    n_configs = int(ladder_cfg.get("n_configs", coarse.shape[0]))
    # STRIDE, do not truncate. `run_hmc_ensemble` stacks draw-major -- the
    # ensemble views as [n_draws, n_chains, ...] -- so the first N configurations
    # are the first few draws of EVERY chain, i.e. the least equilibrated and most
    # mutually correlated slice available. That was harmless while the base held
    # 4 draws per chain and n_configs took all of them; it stops being harmless
    # the moment the base is run longer to relax its parity balance, because
    # truncation would then throw away exactly the part that relaxed. A uniform
    # stride keeps the whole sampling window represented.
    base_chains = int(base_meta.get("n_chains", 0))
    if coarse.shape[0] > n_configs:
        if base_chains and coarse.shape[0] % base_chains == 0:
            # CHAIN-AWARE. A plain stride is actively wrong here: the ensemble views
            # as [n_draws, n_chains] and flattens draw-major, so index i has chain
            # i % n_chains. When the stride divides n_chains -- which it does
            # whenever both are powers of two, i.e. always in this study -- every
            # selected index lands on the same residue class and the subsample keeps
            # n_chains / stride DISTINCT CHAINS while looking like it kept
            # n_configs. Since parity is frozen at the base, distinct chains are
            # exactly the independent topological draws, so that would quietly
            # discard three quarters of the quantity the ladder cannot regenerate.
            # Take the latest draw of each chain instead, walking backwards.
            n_draws = coarse.shape[0] // base_chains
            index = torch.arange(coarse.shape[0]).view(n_draws, base_chains)
            picked, draw = [], n_draws - 1
            while sum(t.numel() for t in picked) < n_configs and draw >= 0:
                need = n_configs - sum(t.numel() for t in picked)
                picked.append(index[draw][:need])
                draw -= 1
            coarse = coarse[torch.cat(picked)]
        else:
            stride = coarse.shape[0] // n_configs
            coarse = coarse[::stride][:n_configs]
        print(f"base subsample: {coarse.shape[0]} configs from "
              f"{min(base_chains, n_configs) if base_chains else '?'} distinct chains")
    print(f"base: L={base['lattice_size']} beta={base['beta']:g}  {coarse.shape[0]} configs")

    model, schedule = load_det_model(checkpoint, device=device)

    beta_schedule = [float(b) for b in ladder_cfg["beta_schedule"]]
    rung_sizes = [int(base["lattice_size"]) * 2 ** (i + 1) for i in range(len(beta_schedule))]

    # RESUME. A rung is minutes of work and the ladder is sequential, so a failure
    # on the top rung used to discard every finished rung below it. They are now
    # written as they land, and the longest already-complete PREFIX is reused: the
    # last of them becomes the coarse input and only the rungs above it are run.
    # Only a prefix qualifies -- rung k is generated from rung k-1, so a gap
    # cannot be filled from disk.
    done = []
    if not args.no_resume:
        for size, beta in zip(rung_sizes, beta_schedule):
            path = ensemble_path(out_dir, size, beta, tag="ladder")
            if not path.exists():
                break
            configs, meta = load_ensemble(path)
            if configs.shape[0] != n_configs:
                print(f"  ignoring {path.name}: {configs.shape[0]} configs, expected {n_configs}")
                break
            done.append((size, beta, configs, meta))

    if done:
        size, beta, coarse, _ = done[-1]
        print(f"resuming: {len(done)} rung(s) on disk, restarting from L={size} beta={beta:g}")
        beta_schedule = beta_schedule[len(done):]
        if not beta_schedule:
            print("every rung already present; nothing to generate (use --no-resume to force)")

    def record_for(result) -> dict:
        record = dict(result.observables)
        record.update({
            "beta": result.beta,
            "lattice_size": result.lattice_size,
            "plaquette_exact": plaquette_exact(result.beta, result.lattice_size),
            "q_squared_exact": det_topological_susceptibility(result.beta, result.lattice_size)
            * result.lattice_size * result.lattice_size,
            # Carried so downstream scoring can use tau_int-AWARE error bars.
            # Every rung inherits the BASE ensemble's chain structure: the lift
            # is per-configuration and order-preserving, so configuration i of a
            # rung descends from configuration i of the base, and the base's
            # chain-major ordering (index = draw * n_chains + chain) survives.
            # Without this, `04_validate` falls back to a naive SEM, which is
            # too small and inflates every |z| built on it.
            "n_chains": base_chains or None,
        })
        return record

    def save_rung(result) -> None:
        record = record_for(result)
        save_ensemble(
            ensemble_path(out_dir, result.lattice_size, result.beta, tag="ladder"),
            result.configs, record,
        )

    results = generate_ladder(
        coarse,
        beta_schedule,
        model,
        schedule,
        n_su2_sweeps=int(ladder_cfg.get("n_su2_sweeps", 20)),
        n_retherm_sweeps=int(ladder_cfg.get("n_retherm_sweeps", 10)),
        batch_size=int(ladder_cfg.get("batch_size", 64)),
        device=device,
        consistency_weight=float(ladder_cfg.get("consistency_weight", 1.0)),
        enforce_coarse_charge=bool(ladder_cfg.get("enforce_coarse_charge", True)),
        physics_blend_coef=float(ladder_cfg.get("physics_blend_coef", 0.0)),
        n_sampler_steps=int(ladder_cfg.get("n_sampler_steps", 200)),
        n_corrector_steps=int(ladder_cfg.get("n_corrector_steps", 1)),
        retherm_topological_updates=bool(ladder_cfg.get("retherm_topological_updates", False)),
        on_rung=save_rung,
    )

    summary = [dict(meta) for _, _, _, meta in done]
    for record in summary:
        print(f"L={record['lattice_size']:4d} beta={record['beta']:9.3f}  "
              f"plaq={record['plaquette']:.5f} (from disk)")
    for result in results:
        size, beta = result.lattice_size, result.beta
        record = record_for(result)
        summary.append(record)
        print(f"L={size:4d} beta={beta:9.3f}  plaq={record['plaquette']:.5f} "
              f"(exact {record['plaquette_exact']:.5f}, "
              f"rel {record['plaquette'] / record['plaquette_exact'] - 1:+.2e})  "
              f"<Q^2>={record['q_squared']:.3f} (exact {record['q_squared_exact']:.3f})")
    save_json(out_dir / "summary.json", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
