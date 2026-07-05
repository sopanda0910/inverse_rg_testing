"""Full validation: ladder ensembles vs exact results and held-out direct HMC,
including the topological-freezing comparison at the top rung.

    python inverserg/diffusion/scripts/04_validate.py --config inverserg/diffusion/configs/default.yaml
"""

import argparse
import glob
import time
from pathlib import Path

import numpy as np
import torch

from inverserg.diffusion.lgt import make_action, run_hmc_ensemble
from inverserg.diffusion.lgt.hmc import adapted_hmc_params
from inverserg.diffusion.lgt.lattice import topological_charge
from inverserg.diffusion.pipeline.ladder import LadderRungResult
from inverserg.diffusion.validate import validate_ladder, write_report
from inverserg.diffusion.validate.report import freezing_diagnostics
from inverserg.diffusion.validate.stats import integrated_autocorrelation_time
from inverserg.diffusion.utils import (
    load_config,
    resolve_device,
    set_seed,
    load_ensemble,
    save_ensemble,
    ensemble_path,
    save_json,
)


def get_reference(lattice_size, beta, config, device):
    """Direct-HMC reference ensemble at (L, beta), cached on disk.

    NOTE: run WITHOUT instanton updates -- this is the honest 'what plain HMC gives
    you' baseline; at large beta its topology is frozen, which is the point of the
    freezing comparison. Ensembles from 01_generate_data (with Q-hops) are used
    where they exist for the training rungs.
    """
    data_cfg = config["data"]
    val_cfg = config["validate"]
    path = ensemble_path(Path(val_cfg["out_dir"]) / "reference", config["action_type"], lattice_size, beta)
    if path.exists():
        configs, _ = load_ensemble(path)
        return configs
    print(f"simulating reference HMC at L={lattice_size} beta={beta} (no Q-hops) ...")
    action = make_action(config["action_type"], beta)
    step_size, n_steps = adapted_hmc_params(
        beta, float(data_cfg["hmc_step_size"]), int(data_cfg["hmc_steps"])
    )
    t0 = time.time()
    configs, stats = run_hmc_ensemble(
        lattice_size,
        action,
        n_configs=int(val_cfg["n_reference_configs"]),
        n_chains=int(data_cfg["n_chains"]),
        burn_in=int(data_cfg["burn_in"]),
        thin=int(data_cfg["thin"]),
        n_steps=n_steps,
        step_size=step_size,
        device=device,
        topological_updates=False,
        hot_start=bool(data_cfg.get("hot_start", True)),
    )
    print(f"  acceptance {stats.acceptance_rate:.3f}, {time.time()-t0:.0f}s")
    save_ensemble(path, configs, {"beta": beta, "lattice_size": lattice_size,
                                  "action_type": config["action_type"],
                                  "provenance": "reference HMC, no topological updates"})
    return configs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="inverserg/diffusion/configs/default.yaml")
    parser.add_argument("--skip-reference", action="store_true", help="validate against exact results only")
    args = parser.parse_args()
    config = load_config(args.config)
    set_seed(int(config["seed"]) + 2)
    device = resolve_device(config)
    action_type = config["action_type"]
    val_cfg = config["validate"]
    data_cfg = config["data"]
    out_dir = Path(val_cfg["out_dir"])

    rungs = []
    pattern = str(Path(config["ladder"]["out_dir"]) / f"ladder_rung*_{action_type}_*.pt")
    for path in sorted(glob.glob(pattern)):
        configs, meta = load_ensemble(path)
        rungs.append(
            LadderRungResult(
                beta=float(meta["beta"]),
                lattice_size=int(meta["lattice_size"]),
                configs=configs,
                observables=meta.get("observables", {}),
            )
        )
        print(f"loaded {path}")
    if not rungs:
        raise SystemExit(f"no ladder ensembles found under {pattern}; run 03_run_ladder.py first")

    reference_map = {}
    if not args.skip_reference:
        for rung in rungs:
            reference_map[(rung.lattice_size, rung.beta)] = get_reference(
                rung.lattice_size, rung.beta, config, device
            )

    summary = validate_ladder(rungs, action_type, reference_map, out_dir)

    freezing = {}
    frz = val_cfg.get("freezing_rung")
    if frz is not None:
        lattice_size, beta = int(frz["lattice_size"]), float(frz["beta"])
        print(f"freezing demo: direct HMC time series at L={lattice_size} beta={beta} ...")
        action = make_action(action_type, beta)
        length = int(val_cfg["freezing_hmc_length"])
        step_size, n_steps = adapted_hmc_params(
            beta, float(data_cfg["hmc_step_size"]), int(data_cfg["hmc_steps"])
        )
        configs, stats = run_hmc_ensemble(
            lattice_size, action, n_configs=length, n_chains=1, burn_in=100, thin=1,
            n_steps=n_steps, step_size=step_size,
            device=device, topological_updates=False, hot_start=True,
        )
        print(f"  freezing-chain acceptance {stats.acceptance_rate:.3f}")
        q_series = topological_charge(configs).cpu().numpy()
        freezing = freezing_diagnostics(q_series, label=f"direct HMC L={lattice_size} beta={beta}")
        freezing["q_series_std"] = float(np.std(q_series))
        ladder_match = [r for r in rungs if (r.lattice_size, r.beta) == (lattice_size, beta)]
        if ladder_match:
            q_ladder = topological_charge(ladder_match[0].configs).cpu().numpy()
            freezing["ladder_q_squared"] = float(np.mean(q_ladder**2))
            tau_ladder, _ = integrated_autocorrelation_time(q_ladder)
            freezing["ladder_tau_int_Q"] = tau_ladder
        print(f"  tau_int(Q) HMC = {freezing['tau_int_Q']:.1f} +- {freezing['tau_int_Q_err']:.1f}")
        save_json(out_dir / "freezing.json", freezing)

    header_lines = [
        f"Action: {action_type}. Rungs validated: "
        + ", ".join(f"L={r.lattice_size} beta={r.beta:g}" for r in rungs)
    ]
    if freezing:
        header_lines.append(
            f"\nTopological freezing: {freezing['label']}: tau_int(Q) = "
            f"{freezing['tau_int_Q']:.1f} +- {freezing['tau_int_Q_err']:.1f} "
            f"(ladder ensemble is i.i.d. across configs by construction)."
        )
    write_report(summary["rows"], out_dir / "report.md", header="\n".join(header_lines))
    print(f"report: {out_dir / 'report.md'}")
    for drift in summary["drift"]:
        print(drift)


if __name__ == "__main__":
    main()
