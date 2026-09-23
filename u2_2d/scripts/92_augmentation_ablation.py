"""Does the symmetry augmentation, or the high-beta noise bias, explain cov60?

cov60 is the dense-coverage checkpoint, and it beats the deployed one inside
coverage. It also happens to have been trained WITHOUT three settings the other
three checkpoints carry: `sym_augment`, `high_beta_sigma_bias` and the
beta-aware sigma floor. Coverage and those settings are therefore confounded in
every cov60-vs-default comparison, and neither the figure nor the table can
separate them.

`configs/cov60_aug.yaml` is cov60's training set with exactly those three
settings restored, so this script's comparison isolates them: same rungs, same
data, same architecture, same optimiser, same epoch budget.

The endpoint is the one the coverage tables report, and it is computed the same
way as 84_raw_seed_quality.py: the raw lift before any trajectory, scored
against the closed form, worst case over the plaquette, W(2x2) and W(4x4), in
units of its own standard error (Z) and in relative deviation (PPM). Both are
reported because they answer different questions -- at fixed coupling the ratio
is meaningful, across couplings Z is.

No HMC runs here. Only the lift is rebuilt, at the same couplings, with the same
sampler settings 28_crossover_scan.py used (64 chains, 200 sampler steps, one
corrector step, 30 conditional SU(2) sweeps, no physics blend).

    python u2_2d/scripts/92_augmentation_ablation.py
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "u2_2d" / "scripts"))

from u2_2d.lgt.blocking import topology_matched_fine_beta  # noqa: E402
from u2_2d.lgt.exact import plaquette_exact, wilson_loop_exact  # noqa: E402
from u2_2d.lgt.lattice import half_retr, plaquette, wilson_loop  # noqa: E402
from u2_2d.model.det_lift import load_det_model  # noqa: E402
from u2_2d.pipeline.ladder import generate_fine_from_coarse  # noqa: E402
from u2_2d.utils import (configure_device, load_ensemble, resolve_device,  # noqa: E402
                         save_json)

OBS = ("plaquette", "wilson_2x2", "wilson_4x4")
AREA = {"plaquette": 1, "wilson_2x2": 4, "wilson_4x4": 16}


def targets(beta: float, size: int) -> dict[str, float]:
    return {"plaquette": plaquette_exact(beta, size),
            "wilson_2x2": wilson_loop_exact(beta, 4),
            "wilson_4x4": wilson_loop_exact(beta, 16)}


def measure(fine: torch.Tensor) -> dict[str, np.ndarray]:
    """Per-configuration value of each scored loop.

    The loop operators return U(2) matrices in the split representation, so each
    must go through `half_retr` before averaging over sites; this is the same
    measurement 28_crossover_scan.py makes, and averaging the raw matrices
    instead puts every deviation at order 10^6 ppm.
    """
    out = {}
    with torch.no_grad():
        for name in OBS:
            if name == "plaquette":
                loop = plaquette(fine)
            else:
                r = int(round(math.sqrt(AREA[name])))
                loop = wilson_loop(fine, r, r)
            out[name] = half_retr(loop).mean(dim=(1, 2)).cpu().numpy()
    return out


def score(per_config: dict[str, np.ndarray], exact: dict[str, float]):
    """Worst-case Z and PPM over the scored loops, as 84_raw_seed_quality does."""
    zs, ppms = [], []
    for name in OBS:
        s = np.asarray(per_config[name], dtype=np.float64)
        sem = s.std(ddof=1) / math.sqrt(len(s))
        bias = abs(float(s.mean()) - exact[name])
        zs.append(bias / sem if sem > 0 else float("inf"))
        ppms.append(bias / abs(exact[name]) * 1e6)
    return max(zs), max(ppms)


def couplings(reference: Path) -> list[float]:
    """The base couplings the published scan evaluated, in its own order."""
    rows = json.loads(reference.read_text())
    return [r["base_beta"] for r in rows]


def run(ckpt: str, base_betas, data_dir: Path, coarse_size: int, n_chains: int,
        sampler_steps: int, n_su2: int, device: str) -> dict:
    model, sched = load_det_model(ckpt, device=device)
    out = {}
    for base_beta in base_betas:
        beta = topology_matched_fine_beta(base_beta, coarse_size)
        coarse, _ = load_ensemble(data_dir / f"u2_L{coarse_size}_beta{base_beta:g}.pt")
        fine = generate_fine_from_coarse(
            model, sched, coarse[:n_chains], beta, n_su2_sweeps=n_su2,
            device=device, n_sampler_steps=sampler_steps, n_corrector_steps=1,
            batch_size=n_chains, consistency_weight=1.0, physics_blend_coef=0.0)
        z, ppm = score(measure(fine), targets(beta, 2 * coarse_size))
        out[round(beta, 3)] = {"beta": beta, "base_beta": base_beta,
                               "Z": z, "PPM": ppm}
        print(f"  beta_f={beta:9.3f}   Z={z:8.2f}   PPM={ppm:9.1f}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", default="out/u2_2d/checkpoints/det_score_net_cov60.pt")
    ap.add_argument("--challenger",
                    default="out/u2_2d/checkpoints/det_score_net_cov60_aug.pt")
    ap.add_argument("--reference",
                    default="out/u2_2d/coverage_scan_relaxation/cov60/crossover_topo.json",
                    help="scan record naming the couplings to score")
    ap.add_argument("--data-dir", default="out/u2_2d/data_v2")
    ap.add_argument("--fine-size", type=int, default=32)
    ap.add_argument("--n-chains", type=int, default=64)
    ap.add_argument("--sampler-steps", type=int, default=200)
    ap.add_argument("--n-su2", type=int, default=30)
    ap.add_argument("--device", default=None)
    ap.add_argument("--out", default="out/u2_2d/augmentation_ablation.json")
    args = ap.parse_args()

    device = resolve_device({"device": args.device or "auto"})
    print(configure_device(device))
    data_dir = Path(args.data_dir)
    coarse_size = args.fine_size // 2
    betas = couplings(Path(args.reference))
    print(f"{len(betas)} couplings, L_c = {coarse_size} -> L_f = {args.fine_size}, "
          f"{args.n_chains} configurations each, device {device}")

    res = {}
    for name, ckpt in (("cov60", args.baseline), ("cov60_aug", args.challenger)):
        print(f"\n{name}  ({ckpt})")
        res[name] = run(ckpt, betas, data_dir, coarse_size, args.n_chains,
                        args.sampler_steps, args.n_su2, device)

    print("\n  beta_f        cov60 Z   cov60_aug Z      ratio |    cov60 PPM  "
          "cov60_aug PPM      ratio")
    zr, pr = [], []
    for k in sorted(res["cov60"], key=float):
        a, b = res["cov60"][k], res["cov60_aug"][k]
        zr.append(a["Z"] / b["Z"])
        pr.append(a["PPM"] / b["PPM"])
        print(f"  {a['beta']:9.3f}  {a['Z']:9.2f}  {b['Z']:11.2f}  {zr[-1]:9.2f} | "
              f"{a['PPM']:11.1f}  {b['PPM']:13.1f}  {pr[-1]:9.2f}")
    wins_z = sum(1 for r in zr if r > 1)
    wins_p = sum(1 for r in pr if r > 1)
    print(f"\n  ratio > 1 means the augmented model is closer to exact.")
    print(f"  Z:   median {np.median(zr):.2f}, augmented better at {wins_z}/{len(zr)}")
    print(f"  PPM: median {np.median(pr):.2f}, augmented better at {wins_p}/{len(pr)}")

    save_json(Path(args.out), {"per_coupling": res,
                               "z_ratio_median": float(np.median(zr)),
                               "ppm_ratio_median": float(np.median(pr)),
                               "z_wins": wins_z, "ppm_wins": wins_p,
                               "n": len(zr)})
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
