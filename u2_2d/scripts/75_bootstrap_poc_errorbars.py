import sys, math
import numpy as np, torch
sys.path.insert(0, ".")
from u2_2d.lgt.exact import plaquette_exact, wilson_loop_exact
from u2_2d.lgt.lattice import half_retr, plaquette, wilson_loop, topological_charge
from u2_2d.utils import load_ensemble

BETA, L = 3273.5552785050186, 128
targets = {"plaquette": plaquette_exact(BETA, L),
           "wilson_2x2": wilson_loop_exact(BETA, 4),
           "wilson_4x4": wilson_loop_exact(BETA, 16)}

for tag, path in [("15 sweeps", "out/u2_2d/data_bootstrap_poc/u2_L128_beta3273.56.pt"),
                  ("40 sweeps", "out/u2_2d/data_bootstrap_poc_deepretherm/u2_L128_beta3273.56.pt")]:
    links, meta = load_ensemble(path)
    with torch.no_grad():
        per_cfg = {
            "plaquette": half_retr(plaquette(links)).mean(dim=(1,2)).numpy().astype(float),
            "wilson_2x2": half_retr(wilson_loop(links,2,2)).mean(dim=(1,2)).numpy().astype(float),
            "wilson_4x4": half_retr(wilson_loop(links,4,4)).mean(dim=(1,2)).numpy().astype(float),
        }
        qsq = (topological_charge(links).round()**2).numpy().astype(float)
    n = len(per_cfg["plaquette"])
    rng = np.random.default_rng(0)
    print(f"\n=== {tag}  (n={n} configs, each from an independent base chain) ===")
    for name, v in per_cfg.items():
        boots = np.array([v[rng.integers(0,n,n)].mean() for _ in range(10000)])
        lo, hi = np.percentile(boots, [2.5, 97.5])
        naive_sem = v.std(ddof=1)/math.sqrt(n)
        boot_sem = boots.std(ddof=1)
        z_naive = (v.mean()-targets[name])/naive_sem
        z_boot = (v.mean()-targets[name])/boot_sem
        print(f"  {name:<12s} mean={v.mean():.7f} exact={targets[name]:.7f}")
        print(f"     z(naive SEM)={z_naive:+6.2f}   z(bootstrap)={z_boot:+6.2f}   "
              f"boot 95% CI on mean [{lo:.7f}, {hi:.7f}]")
    qb = np.array([qsq[rng.integers(0,n,n)].mean() for _ in range(10000)])
    print(f"  <Q^2> = {qsq.mean():.4f}  boot 95% CI [{np.percentile(qb,2.5):.4f}, {np.percentile(qb,97.5):.4f}]")
