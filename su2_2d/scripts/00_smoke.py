"""End-to-end smoke: HMC ensemble vs exact references, plus the
score-approximation gap (proxy vs exact DSM target across sigma).

    .venv/Scripts/python.exe su2_2d/scripts/00_smoke.py
"""

import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import torch

from su2_2d.lgt import group, mean_plaquette, plaquette_exact, run_hmc_ensemble, wilson_loop_trace_half
from su2_2d.lgt.exact import wilson_loop_exact
from su2_2d.model.noise import exact_score_target, noise_links, proxy_score_target


def main() -> None:
    beta, l = 2.0, 8
    t0 = time.time()
    configs, acc = run_hmc_ensemble(l, beta, n_configs=128, n_chains=8,
                                    burn_in=400, thin=5, seed=0)
    plaq = mean_plaquette(configs)
    w22 = wilson_loop_trace_half(configs, 2, 2).mean()
    print(f"HMC L={l} beta={beta}: {time.time() - t0:.0f}s, acceptance {acc:.2f}")
    print(f"  plaquette {float(plaq.mean()):+.4f} ± {float(plaq.std() / math.sqrt(plaq.numel())):.4f}"
          f" (naive sem, autocorrelation-blind)   exact {plaquette_exact(beta):+.4f}")
    print(f"  W(2x2)    {float(w22):+.4f}                exact {wilson_loop_exact(beta, 4):+.4f}")

    print("\nscore-approximation gap (relative L2 error of proxy vs exact target):")
    gen = torch.Generator().manual_seed(1)
    u0 = group.random_haar((2048,), generator=gen)
    for sigma in (0.1, 0.3, 0.6, 1.0, 1.5):
        ut, omega = noise_links(u0, sigma, generator=gen)
        exact = exact_score_target(ut, u0, sigma)
        proxy = proxy_score_target(omega, sigma)
        rel = float((proxy - exact).norm(dim=-1).mean() / exact.norm(dim=-1).mean().clamp_min(1e-9))
        print(f"  sigma {sigma:4.1f}: {100 * rel:6.2f} %")


if __name__ == "__main__":
    main()
