"""Generate SU(2) HMC training ensembles at the configured rungs.

    .venv/Scripts/python.exe su2_2d/scripts/01_generate_data.py --config su2_2d/configs/su2.yaml
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import os

import torch

torch.set_num_threads(int(os.environ.get("SU2_2D_TORCH_THREADS", "8")))
import yaml

from su2_2d.lgt import mean_plaquette, plaquette_exact, run_hmc_ensemble


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="su2_2d/configs/su2.yaml")
    args = parser.parse_args()
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    data = config["data"]
    out_dir = Path(data["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    for l, beta in data["rungs"]:
        path = out_dir / f"wilson_L{l}_beta{beta:g}.pt"
        if path.exists():
            print(f"{path} exists, skipping")
            continue
        t0 = time.time()
        configs, acc = run_hmc_ensemble(
            l, beta, n_configs=data["n_configs"], n_chains=data["n_chains"],
            burn_in=data["burn_in"], thin=data["thin"], seed=config["seed"])
        per_config = mean_plaquette(configs)
        plaq = float(per_config.mean())
        exact = plaquette_exact(beta)
        rel = abs(plaq - exact) / abs(exact)
        # Equilibrium gate: the exact plaquette is known, so a non-thermalized
        # ensemble must never reach the training set (the first SU(2) run
        # trained on cold-start data sitting 2.5% high at beta=16). Judged on
        # BOTH scales -- a flat relative tolerance false-positives at weak
        # coupling where fluctuations are large, a pure z-score false-positives
        # at strong coupling where the sem is tiny. The naive sem is inflated
        # by a conservative autocorrelation factor since configs are thinned,
        # not independent.
        sem = float(per_config.std() / max(per_config.numel(), 2) ** 0.5) * 3.0
        z = abs(plaq - exact) / max(sem, 1e-12)
        tol = data.get("plaquette_tolerance", 0.02)
        bad = rel > tol and z > 5.0
        status = "FAIL" if bad else ("OK" if rel < tol / 4 else "marginal")
        print(f"L={l} beta={beta}: {configs.shape[0]} configs, acc {acc:.2f}, "
              f"plaq {plaq:+.5f} (exact {exact:+.5f}, rel {100 * rel:.2f}%, "
              f"z {z:.1f}) {status}, {time.time() - t0:.0f}s")
        if bad:
            raise SystemExit(
                f"ensemble at L={l}, beta={beta} deviates {100 * rel:.2f}% "
                f"({z:.1f} sigma) from the exact plaquette — not thermalized; "
                "increase burn_in or check the sampler before training on it")
        torch.save({"configs": configs, "beta": beta, "lattice_size": l}, path)
        print(f"  -> {path}")


if __name__ == "__main__":
    main()
