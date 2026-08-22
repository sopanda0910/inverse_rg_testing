"""Is the topological charge transported EXACTLY through the lift?

The pipeline's central structural claim is that Q is not modelled but TRANSPORTED:
the abelian telescope makes the coarse determinant plaquette the exact wrapped sum
of its four fine children, so `enforce_coarse_charge` can impose the coarse charge
on the fine configuration and the lift cannot alter it. Everything downstream
depends on that -- it is why the deployed ladder can carry a P(Q) sampled at a
coupling where HMC is ergodic up to a coupling where it is frozen, which is the
one thing a high-beta HMC chain cannot do at any cost.

It is asserted throughout and, as far as the scripts go, never checked
CONFIGURATION BY CONFIGURATION on the deployed lift. `09_verify_identities.py`
checks the telescope on the blocking map; this checks the generative path.

Reported per coupling: the fraction of configurations whose fine Q equals their
coarse Q exactly, plus <Q^2> on both sides. A match rate below 100% is a bug, not
a statistic.

    python u2_2d/scripts/36_transport_check.py --device cuda
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u2_2d.lgt.blocking import topology_matched_fine_beta
from u2_2d.lgt.lattice import topological_charge
from u2_2d.model.det_lift import load_det_model, model_beta
from u2_2d.pipeline.ladder import generate_fine_from_coarse
from u2_2d.utils import (configure_device, load_ensemble, resolve_device,
                         save_json, set_seed)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--device", default="cuda")
    p.add_argument("--checkpoint", default="out/u2_2d/checkpoints/det_score_net.pt")
    p.add_argument("--data-dir", default="out/u2_2d/data_v2")
    p.add_argument("--coarse-size", type=int, default=16)
    p.add_argument("--coarse-betas", default="23.6203,105.244,135.861,199.229")
    p.add_argument("--n-configs", type=int, default=64)
    p.add_argument("--sampler-steps", type=int, default=200)
    p.add_argument("--n-su2", type=int, default=30)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--out-dir", default="out/u2_2d/transport_check")
    args = p.parse_args()

    dev = resolve_device({"device": args.device})
    print(configure_device(dev), flush=True)
    set_seed(args.seed)
    model, sched = load_det_model(args.checkpoint, device=dev)
    out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
    records = []
    print(f"\n{'coarse b':>10s} {'model_b':>8s} {'Qc^2':>8s} {'Qf^2':>8s} {'match':>8s}",
          flush=True)
    for cb in [float(b) for b in args.coarse_betas.split(",")]:
        path = Path(args.data_dir) / f"u2_L{args.coarse_size}_beta{cb:g}.pt"
        if not path.exists():
            print(f"(skip) missing {path}", flush=True); continue
        coarse, _ = load_ensemble(path)
        coarse = coarse[:args.n_configs]
        bf = topology_matched_fine_beta(cb, args.coarse_size)
        qc = topological_charge(coarse).round().cpu().numpy()
        fine = generate_fine_from_coarse(
            model, sched, coarse, bf, n_su2_sweeps=args.n_su2, device=dev,
            n_sampler_steps=args.sampler_steps, n_corrector_steps=1,
            batch_size=32, consistency_weight=1.0, physics_blend_coef=0.0)
        qf = topological_charge(fine.to(dev)).round().cpu().numpy()
        match = float((qc == qf).mean())
        rec = {"coarse_beta": cb, "fine_beta": bf, "model_beta": model_beta(bf),
               "q_squared_coarse": float((qc ** 2).mean()),
               "q_squared_fine": float((qf ** 2).mean()),
               "match_fraction": match, "n_configs": int(len(qc))}
        records.append(rec); save_json(out / "transport_check.json", records)
        print(f"{cb:10g} {rec['model_beta']:8.2f} {rec['q_squared_coarse']:8.4f} "
              f"{rec['q_squared_fine']:8.4f} {100*match:7.1f}%", flush=True)
        if match < 1.0:
            bad = np.nonzero(qc != qf)[0][:10]
            print(f"    MISMATCH idx {bad.tolist()}: coarse {qc[bad].astype(int).tolist()}"
                  f" -> fine {qf[bad].astype(int).tolist()}", flush=True)
    print(f"\nwrote {out / 'transport_check.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
