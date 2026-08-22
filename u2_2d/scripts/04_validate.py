"""Stage 04: validate ladder output against HMC reference and exact results.

For every ladder rung, compares the generated ensemble to (a) a direct HMC
ensemble at the same (L, beta) when one exists, and (b) the closed-form 2D U(2)
results, which exist for the plaquette, every Wilson loop, the string tension and
the whole determinant-sector P(Q).

Device: CPU, as in the U(1) study -- the reference HMC dominates and is
launch-bound at these volumes.
"""

import argparse
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u2_2d.lgt.actions import WilsonU2Action
from u2_2d.lgt.hmc import adapted_hmc_params, run_hmc_ensemble
from u2_2d.utils import (
    configure_device,
    ensemble_path,
    load_config,
    load_ensemble,
    resolve_device,
    save_json,
    set_seed,
    to_cpu,
)
from u2_2d.validate.report import compare, render_markdown


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="u2_2d/configs/smoke.yaml")
    parser.add_argument("--device", default=None)
    parser.add_argument(
        "--generated-n-chains", type=int, default=None,
        help="chain count of the ladder base, for tau_int-aware error bars on "
             "the generated ensemble. Ensembles written before 2026-08 do not "
             "carry n_chains in their metadata; supply it here rather than "
             "letting the naive SEM stand, which is too small and inflates "
             "every |z| built on it.")
    parser.add_argument("--ladder-dir", default=None)
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--reference-configs", type=int, default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    if args.device:
        config["device"] = args.device
    device = resolve_device(config)
    print(configure_device(device))
    set_seed(int(config.get("seed", 0)) + 7919)

    ladder_dir = Path(args.ladder_dir or config["ladder"].get("out_dir", "out/u2_2d/ladder"))
    data_dir = Path(args.data_dir or config["data"].get("out_dir", "out/u2_2d/data"))
    out_dir = Path(args.out_dir or config.get("validate", {}).get("out_dir", "out/u2_2d/validation"))
    out_dir.mkdir(parents=True, exist_ok=True)
    validate_cfg = config.get("validate", {})
    n_reference = int(args.reference_configs or validate_cfg.get("n_reference_configs", 256))

    # Validate the rungs the CONFIG asks for, not whatever is lying in the
    # directory. Changing the beta schedule leaves the previous schedule's
    # ensembles behind -- stage 03 overwrites by name, so a renamed rung is
    # orphaned rather than replaced -- and a glob then reports those stale files
    # as current results, in the same report directory, with no marker saying
    # which run they came from. Ensembles that are not in the schedule are listed
    # and skipped so the mismatch is visible instead of silent.
    base = config["ladder"]["base"]
    wanted = {}
    size = int(base["lattice_size"])
    for beta in config["ladder"]["beta_schedule"]:
        size *= 2
        wanted[ensemble_path(ladder_dir, size, float(beta), tag="ladder").name] = True

    paths, skipped = [], []
    for path in sorted(ladder_dir.glob("ladder_L*_beta*.pt")):
        (paths if path.name in wanted else skipped).append(path)
    if skipped:
        print(f"skipping {len(skipped)} ensemble(s) not in the configured schedule: "
              + ", ".join(p.name for p in skipped))
    missing = [n for n in wanted if n not in {p.name for p in paths}]
    if missing:
        print(f"WARNING: configured rung(s) absent from {ladder_dir}: " + ", ".join(missing))

    summaries = []
    for path in paths:
        generated, metadata = load_ensemble(path)
        beta, size = float(metadata["beta"]), int(metadata["lattice_size"])
        reference_path = ensemble_path(data_dir, size, beta)
        if reference_path.exists():
            reference, _ = load_ensemble(reference_path)
            source = "stage-01 ensemble"
        elif (validate_cfg.get("generate_reference", True)
              and size <= int(validate_cfg.get("max_reference_lattice_size", 32))):
            step_size, n_steps = adapted_hmc_params(beta)
            reference, _ = run_hmc_ensemble(
                size, WilsonU2Action(beta), n_reference,
                n_chains=int(validate_cfg.get("n_chains", 16)),
                burn_in=int(validate_cfg.get("burn_in", 400)),
                thin=int(validate_cfg.get("thin", 4)),
                n_steps=n_steps, step_size=step_size, device=device,
                topological_updates=True,
            )
            reference = to_cpu(reference)
            source = f"fresh HMC ({n_reference} configs)"
        else:
            # No HMC reference: either disabled, or above
            # max_reference_lattice_size. The top ladder rung is meant to be an
            # extrapolation -- direct HMC there is what the whole method exists to
            # avoid, and at those couplings it would be topologically frozen
            # anyway, so a "reference" built from it would be worse than none.
            reference, source = None, "exact only (no HMC reference)"

        # tau_int-AWARE ERRORS (2026-08-22). The reference's chain count is
        # known exactly here. The generated ensemble's comes from the ladder
        # base and is recorded in its metadata by 03_run_ladder; when absent we
        # pass None and fall back to the naive SEM rather than guess, because a
        # wrong chain count silently returns tau ~ 0.5 and looks like a result.
        # NOTE the ordering contract is satisfied: u2's `sample` concatenates
        # per-draw blocks of all chains, so index = draw * n_chains + chain.
        gen_chains = args.generated_n_chains
        if gen_chains is None and isinstance(metadata, dict):
            gen_chains = metadata.get("n_chains")
        if gen_chains is None:
            print("    (no n_chains in metadata: naive SEM, |z| will be "
                  "optimistic -- pass --generated-n-chains)")
        summary = compare(generated, reference, beta, size,
                          n_chains=gen_chains,
                          reference_n_chains=int(validate_cfg.get("n_chains", 16)))
        summary["reference_source"] = source
        summaries.append(summary)
        name = f"L{size}_beta{beta:g}"
        (out_dir / f"report_{name}.md").write_text(
            render_markdown(summary, title=f"U(2) validation: L={size}, beta={beta:g}"),
            encoding="utf-8",
        )
        plaq = next(r for r in summary["rows"] if r["observable"] == "plaquette")
        print(f"L={size:4d} beta={beta:9.3f}  plaq {plaq['generated']:.6f} "
              f"vs exact {plaq.get('exact', float('nan')):.6f} "
              f"(z {plaq.get('z_vs_exact', float('nan')):+.2f})  "
              f"<Q^2> {summary['q_squared']:.3f} vs {summary['q_squared_exact']:.3f}"
              + (f"  max Wilson z {summary['max_wilson_z']:.2f}"
                 if "max_wilson_z" in summary else ""))

    if summaries:
        save_json(out_dir / "summary.json", summaries)
        print(f"reports in {out_dir}")
    else:
        print(f"no ladder ensembles found in {ladder_dir} -- run stage 03 first")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
