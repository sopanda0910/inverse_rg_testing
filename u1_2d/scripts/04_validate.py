"""Full validation: ladder ensembles vs exact results and held-out direct HMC,
including the topological-freezing comparison at the top rung.

    python u1_2d/scripts/04_validate.py --config u1_2d/configs/default.yaml
"""

import argparse
import glob
import time
from pathlib import Path

import numpy as np
import torch

from u1_2d.lgt import make_action, run_hmc_ensemble
from u1_2d.lgt.hmc import adapted_hmc_params
from u1_2d.lgt.lattice import topological_charge
from u1_2d.pipeline.ladder import LadderRungResult
from u1_2d.validate import validate_ladder, write_report
from u1_2d.validate.report import freezing_diagnostics
from u1_2d.validate.stats import chain_tau_int
from u1_2d.utils import (
    configure_device,
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
    parser.add_argument("--config", default="u1_2d/configs/default.yaml")
    parser.add_argument("--skip-reference", action="store_true", help="validate against exact results only")
    parser.add_argument("--device", default=None, help="override config device (cpu | cuda)")
    args = parser.parse_args()
    config = load_config(args.config)
    set_seed(int(config["seed"]) + 2)
    if args.device is not None:
        config["device"] = args.device
    device = resolve_device(config)
    print(f"device: {configure_device(device)}")
    action_type = config["action_type"]
    val_cfg = config["validate"]
    data_cfg = config["data"]
    out_dir = Path(val_cfg["out_dir"])

    rungs, raw_rungs = [], []
    pattern = str(Path(config["ladder"]["out_dir"]) / f"ladder_rung*_{action_type}_*.pt")
    for path in sorted(glob.glob(pattern)):
        configs, meta = load_ensemble(path)
        rung = LadderRungResult(
            beta=float(meta["beta"]),
            lattice_size=int(meta["lattice_size"]),
            configs=configs,
            observables=meta.get("observables", {}),
        )
        (raw_rungs if "_raw_" in Path(path).name else rungs).append(rung)
        print(f"loaded {path}")
    if not rungs:
        raise SystemExit(f"no ladder ensembles found under {pattern}; run 03_run_ladder.py first")

    reference_map = {}
    if not args.skip_reference:
        for rung in rungs:
            reference_map[(rung.lattice_size, rung.beta)] = get_reference(
                rung.lattice_size, rung.beta, config, device
            )

    n_chains = int(data_cfg["n_chains"])
    summary = validate_ladder(rungs, action_type, reference_map, out_dir,
                              n_chains=n_chains, ref_n_chains=n_chains)

    # Raw pre-enforcement pass: the default rungs carry the deterministic
    # charge-transport step, so their Q columns validate the transport
    # machinery (coarse histogram + instanton map) as much as the model. The
    # raw ensembles 03 saves alongside are the model's own topology; a labeled
    # second pass keeps both stories in one report.
    if raw_rungs:
        raw_summary = validate_ladder(
            raw_rungs, action_type, reference_map,
            out_dir / "raw_preenforcement",
            n_chains=n_chains, ref_n_chains=n_chains,
        )
        for label, rows in raw_summary["rows"].items():
            summary["rows"][f"{label}_RAW_preenforcement"] = rows

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
            # Per chain: the ensemble is chain-major per draw, so the
            # interleaved series puts correlated samples n_chains apart and a
            # windowed tau_int on it reads ~0.5 regardless of the truth. Fine
            # configs inherit the coarse chain's autocorrelation through
            # conditioning -- they are NOT i.i.d. across the ensemble.
            freezing["ladder_tau_int_Q"] = chain_tau_int(q_ladder, n_chains)
        print(f"  tau_int(Q) HMC = {freezing['tau_int_Q']:.1f} +- {freezing['tau_int_Q_err']:.1f}")
        save_json(out_dir / "freezing.json", freezing)

    header_lines = [
        f"Action: {action_type}. Rungs validated: "
        + ", ".join(f"L={r.lattice_size} beta={r.beta:g}" for r in rungs)
    ]
    if freezing:
        ladder_tau = freezing.get("ladder_tau_int_Q")
        ladder_tau_s = (f"; ladder ensemble per-chain tau_int(Q) = {ladder_tau:.1f} "
                        "(inherited from the coarse HMC base through conditioning)"
                        if ladder_tau is not None else "")
        header_lines.append(
            f"\nTopological freezing: {freezing['label']}: tau_int(Q) = "
            f"{freezing['tau_int_Q']:.1f} +- {freezing['tau_int_Q_err']:.1f}"
            f"{ladder_tau_s}."
        )
    write_report(summary["rows"], out_dir / "report.md", header="\n".join(header_lines))
    print(f"report: {out_dir / 'report.md'}")
    for drift in summary["drift"]:
        print(drift)


if __name__ == "__main__":
    main()
