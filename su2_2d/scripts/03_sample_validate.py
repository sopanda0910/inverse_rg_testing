"""First inverse-RG lift for SU(2): sample fine configs conditioned on a
coarse HMC ensemble and compare observables against direct fine HMC and the
exact references.

    .venv/Scripts/python.exe su2_2d/scripts/03_sample_validate.py --config su2_2d/configs/su2.yaml
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import os

import torch

torch.set_num_threads(int(os.environ.get("SU2_2D_TORCH_THREADS", "8")))
import yaml

from su2_2d.lgt import (
    mean_plaquette,
    plaquette_exact,
    run_hmc_ensemble,
    wilson_loop_exact,
    wilson_loop_trace_half,
)
from su2_2d.model.sampler import sample
from su2_2d.model.train import load_checkpoint


def observe(configs) -> dict:
    plaq = mean_plaquette(configs)
    w22 = wilson_loop_trace_half(configs, 2, 2).mean(dim=(-2, -1))
    return {
        "plaquette": [float(plaq.mean()), float(plaq.std() / max(plaq.numel(), 2) ** 0.5)],
        "wilson_2x2": [float(w22.mean()), float(w22.std() / max(w22.numel(), 2) ** 0.5)],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="su2_2d/configs/su2.yaml")
    args = parser.parse_args()
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    sam = config["sample"]
    out_dir = Path(sam["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    model, schedule = load_checkpoint(config["train"]["checkpoint"])
    schedule.n_steps = sam["n_ode_steps"]
    coarse_L, fine_beta = sam["coarse_L"], sam["fine_beta"]
    fine_L = 2 * coarse_L

    t0 = time.time()
    coarse, _ = run_hmc_ensemble(
        coarse_L, sam["coarse_beta"], n_configs=sam["n_configs"],
        n_chains=config["data"]["n_chains"], burn_in=config["data"]["burn_in"],
        thin=config["data"]["thin"], seed=config["seed"] + 1)
    generated = sample(model, schedule, sam["n_configs"], fine_L, fine_beta,
                       coarse=coarse, seed=config["seed"] + 2)
    t_gen = time.time() - t0

    reference, _ = run_hmc_ensemble(
        fine_L, fine_beta, n_configs=sam["n_configs"],
        n_chains=config["data"]["n_chains"], burn_in=config["data"]["burn_in"],
        thin=config["data"]["thin"], seed=config["seed"] + 3)

    report = {
        "fine_L": fine_L, "fine_beta": fine_beta,
        "coarse_L": coarse_L, "coarse_beta": sam["coarse_beta"],
        "n": sam["n_configs"], "seconds_generate": round(t_gen, 1),
        "generated": observe(generated),
        "reference_hmc": observe(reference),
        "exact": {
            "plaquette": plaquette_exact(fine_beta),
            "wilson_2x2": wilson_loop_exact(fine_beta, 4),
        },
    }
    for name in ("plaquette", "wilson_2x2"):
        mu, err = report["generated"][name]
        report[f"z_{name}"] = (mu - report["exact"][name]) / max(err, 1e-12)

    torch.save({"generated": generated, "coarse": coarse}, out_dir / "lift.pt")
    (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
