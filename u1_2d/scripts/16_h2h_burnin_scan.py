"""Instanton-HMC burn-in scan: how much entry cost buys a passing baseline?

The head-to-head (script 14) showed instanton HMC failing Wilson-observable
quality at beta >= 55 with a fixed 500-trajectory burn-in -- an
under-thermalization artifact a referee will immediately probe. This scan runs
the SAME instanton-HMC arm at increasing burn-ins and reports quality vs
entry cost, turning "the baseline failed" into the quantitative claim: the
baseline's one-time entry cost grows with beta while the diffusion pipeline's
per-config cost stays flat.

    python u1_2d/scripts/16_h2h_burnin_scan.py --config u1_2d/configs/v2.yaml
"""

import argparse
import importlib.util
import json
import math
import time
from pathlib import Path

import numpy as np

from u1_2d.utils import load_config, resolve_device, set_seed, save_json

_spec = importlib.util.spec_from_file_location(
    "h2h", Path(__file__).parent / "14_diffusion_vs_instanton_hmc.py")
h2h = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h2h)


def scan_point(beta, lattice_size, n_chains, burn_in, n_prod, device, seed, action_type):
    targets = h2h.exact_targets(beta, action_type, lattice_size)
    inst = h2h.run_instanton_hmc(lattice_size, beta, action_type,
                                 n_chains, burn_in, n_prod, device, seed)
    rec = {"beta": beta, "burn_in": burn_in,
           "burn_seconds": round(inst["burn_seconds"], 1),
           "prod_seconds": round(inst["prod_seconds"], 1),
           "tunnelings": inst["tunnelings"],
           "instanton_acceptance": inst["instanton_acceptance"]}
    for name, target in targets.items():
        if name in inst["series"]:
            mean, err = h2h.chain_stats(inst["series"][name])
            rec[f"{name}_z"] = (mean - target) / max(err, 1e-12)
            rec[f"{name}_mean"] = mean
            rec[f"{name}_err"] = err
    wilson = [abs(rec[f"{n}_z"]) for n in ("plaquette", "wilson_2x2", "wilson_4x4")
              if f"{n}_z" in rec and math.isfinite(rec[f"{n}_z"])]
    rec["max_wilson_abs_z"] = max(wilson) if wilson else float("nan")
    return rec


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="u1_2d/configs/v2.yaml")
    parser.add_argument("--betas", default="55.0237,218.58")
    parser.add_argument("--burn-ins", default="2000,8000")
    parser.add_argument("--lattice-size", type=int, default=32)
    parser.add_argument("--n-chains", type=int, default=32)
    parser.add_argument("--n-prod", type=int, default=640)
    parser.add_argument("--seed", type=int, default=20260731)
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--baseline-summary",
                        default="out/u1_2d/diffusion_vs_instanton/summary.json",
                        help="pull the burn-in 500 points and diffusion costs from here")
    args = parser.parse_args()
    config = load_config(args.config)
    device = resolve_device(config)
    action_type = config["action_type"]
    out_dir = Path(args.out_dir or "out/u1_2d/diffusion_vs_instanton/burnin_scan")
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "summary.json"
    records = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else []
    done = {(r["beta"], r["burn_in"]) for r in records}

    baseline = []
    base_path = Path(args.baseline_summary)
    if base_path.exists():
        for rec in json.loads(base_path.read_text(encoding="utf-8")):
            a = rec.get("instanton_hmc", {})
            wilson = [abs(a.get(f"{n}_z", float("nan")))
                      for n in ("plaquette", "wilson_2x2", "wilson_4x4")]
            wilson = [z for z in wilson if math.isfinite(z)]
            baseline.append({"beta": rec["beta"], "burn_in": 500,
                             "burn_seconds": a.get("burn_seconds"),
                             "tunnelings": a.get("tunnelings"),
                             "max_wilson_abs_z": max(wilson) if wilson else float("nan"),
                             "Q^2_z": a.get("Q^2_z"),
                             "diffusion_s_per_config":
                                 rec.get("diffusion", {}).get("seconds_per_independent_config")})

    set_seed(args.seed)
    for beta in (float(v) for v in args.betas.split(",")):
        for burn in (int(v) for v in args.burn_ins.split(",")):
            if (beta, burn) in done:
                print(f"beta={beta:g} burn={burn}: cached", flush=True)
                continue
            print(f"beta={beta:g} burn-in={burn} ...", flush=True)
            t0 = time.time()
            rec = scan_point(beta, args.lattice_size, args.n_chains, burn,
                             args.n_prod, device, args.seed + burn, action_type)
            rec["scan_seconds"] = round(time.time() - t0, 1)
            records.append(rec)
            save_json(summary_path, records)
            print(f"  max wilson |z|={rec['max_wilson_abs_z']:.1f}, "
                  f"Q^2 z={rec.get('Q^2_z', float('nan')):+.1f}, "
                  f"{rec['scan_seconds']:.0f}s", flush=True)

    rows = baseline + records
    rows.sort(key=lambda r: (r["beta"], r["burn_in"]))
    lines = [
        "# Instanton-HMC burn-in scan (entry cost vs quality)",
        "",
        "Same instanton-HMC arm as the head-to-head; only the burn-in varies.",
        "Quality pass = all Wilson-observable |z| <= 2.5 vs exact. The diffusion",
        "pipeline's per-config cost at the same coupling is shown for contrast:",
        "it has no burn-in and does not grow with beta.",
        "",
        "| beta | burn-in traj | max Wilson |z| | Q^2 z | quality | burn-in s "
        "(entry cost) | diffusion s/config |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        z = r.get("max_wilson_abs_z", float("nan"))
        quality = "pass" if (math.isfinite(z) and z <= 2.5) else "FAIL"
        diff = r.get("diffusion_s_per_config")
        diff_s = f"{diff:.2f}" if diff else "--"
        q2z = r.get("Q^2_z")
        q2s = f"{q2z:+.1f}" if isinstance(q2z, float) and math.isfinite(q2z) else "--"
        burn_s = r.get("burn_seconds")
        lines.append(f"| {r['beta']:g} | {r['burn_in']} | {z:.1f} | {q2s} | {quality} | "
                     f"{burn_s if burn_s is not None else '--'} | {diff_s} |")
    lines += ["", "Production window: 640 trajectories x 32 chains in every row; "
              "per-chain time-average statistics, first 25% discarded."]
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"report: {out_dir / 'report.md'}")


if __name__ == "__main__":
    main()
