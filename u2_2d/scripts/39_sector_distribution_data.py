"""Build the two training sets for the sector-distribution experiment.

THE QUESTION. Every training rung above model beta ~13 carries
`seed_exact_sectors`: its topology is INSTALLED from the closed-form P(Q)
because HMC is frozen there. That has been recorded as the method's hard
dependency on 2D U(2) being exactly solvable, and therefore as the thing that
closes in 4D SU(3) where no closed-form P(Q) exists.

Reading `lgt/sector_seed.py`, that is too strong. The closed form enters at
exactly one point:

    Q ~ P(Q) exact  ->  set_topological_charge (deterministic)
                    ->  conditional_su2_sweeps (exact sampler for p(q | psi))

and all it does there is choose the sector FREQUENCIES of the training data. At
deployment those frequencies are OVERRIDDEN: the fine charge is imposed from the
coarse ensemble by `enforce_coarse_charge`, and `36_transport_check.py` measures
that transport as exact, configuration by configuration, at every coupling
tested. So the network should only need the training data to COVER the sectors,
not to weight them correctly -- and coverage needs no closed form, since charges
can be imposed by any means.

THE TEST. Build two training sets from the SAME source ensembles through the
SAME code path, differing only in the distribution the target charges are drawn
from:

  * arm EXACT   -- Q ~ P(Q), the deployed recipe.
  * arm UNIFORM -- Q ~ Uniform over the support of P(Q). Identical COVERAGE,
    deliberately and badly wrong FREQUENCIES (it flattens a distribution whose
    exact weights fall off by orders of magnitude into the tails).

Then train an identical network on each and compare lift quality. If the two
agree, the exactly-solvable dependency is out of the METHOD and survives only in
the training-data recipe and the scoring -- which is the difference between
"this transfers to 4D" and "this does not".

Both arms are re-seeded, including the control, so the comparison is not
confounded by one arm having been through an extra pass. The five honestly
sampled low-beta rungs (`seed_exact_sectors: false` in `v2.yaml`) are copied
byte-for-byte into both arms and never touched.

    python u2_2d/scripts/39_sector_distribution_data.py --device cuda
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u2_2d.lgt.actions import WilsonU2Action
from u2_2d.lgt.exact import det_topological_charge_distribution
from u2_2d.lgt.lattice import topological_charge
from u2_2d.lgt.local_updates import conditional_su2_sweeps, set_topological_charge
from u2_2d.utils import (configure_device, load_ensemble, resolve_device,
                         save_ensemble, save_json, set_seed)

# The rungs v2.yaml marks `seed_exact_sectors: false` -- honestly sampled, and
# identical in both arms.
UNSEEDED = {(8, 3.5), (8, 7.0), (8, 14.0), (16, 14.0), (16, 28.0)}


def parse_name(path: Path):
    stem = path.stem              # u2_L16_beta105.244
    try:
        _, ell, beta = stem.split("_", 2)
        return int(ell[1:]), float(beta[4:])
    except Exception:
        return None, None


def draw_targets(mode, n, beta, size, rng, support_floor=1e-4):
    q_values, probs = det_topological_charge_distribution(beta, size)
    keep = probs > support_floor
    q_keep = q_values[keep].astype(float)
    if q_keep.size == 0:
        q_keep = np.array([0.0])
    if mode == "exact":
        p = probs[keep] / probs[keep].sum()
        draws = rng.choice(q_keep, size=n, p=p)
    else:                                   # uniform over the SAME support
        draws = rng.choice(q_keep, size=n)
    # what the arm actually asked for, so the "wrongness" is on the record
    exact_odd = float(probs[q_values % 2 != 0].sum())
    exact_q2 = float((q_values.astype(float) ** 2 * probs).sum())
    return draws, {"exact_odd": exact_odd, "exact_q_squared": exact_q2,
                   "support": int(q_keep.size)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--src", default="out/u2_2d/data_v2")
    ap.add_argument("--out-exact", default="out/u2_2d/data_sector_exact")
    ap.add_argument("--out-uniform", default="out/u2_2d/data_sector_uniform")
    ap.add_argument("--n-su2", type=int, default=25)
    ap.add_argument("--seed", type=int, default=606)
    ap.add_argument("--report", default="out/u2_2d/sector_experiment/data_report.json")
    args = ap.parse_args()

    device = resolve_device({"device": args.device})
    print(configure_device(device))
    set_seed(args.seed)
    src = Path(args.src)
    files = sorted(src.glob("*.pt"))
    if not files:
        print(f"no ensembles under {src}")
        return 1

    outs = {"exact": Path(args.out_exact), "uniform": Path(args.out_uniform)}
    for d in outs.values():
        d.mkdir(parents=True, exist_ok=True)
    for extra in src.glob("*.json"):
        for d in outs.values():
            shutil.copy2(extra, d / extra.name)

    records = []
    t0 = time.time()
    for i, f in enumerate(files):
        size, beta = parse_name(f)
        if size is None:
            continue
        if (size, beta) in UNSEEDED:
            for d in outs.values():
                shutil.copy2(f, d / f.name)
            print(f"[{i+1:3d}/{len(files)}] {f.name:34s} COPIED (honestly sampled)")
            continue

        links, meta = load_ensemble(f)
        n = links.shape[0]
        action = WilsonU2Action(beta)
        rec = {"file": f.name, "lattice_size": size, "beta": beta, "n": n}
        for mode, d in outs.items():
            rng = np.random.default_rng(abs(hash((mode, f.name))) % (2**31))
            draws, info = draw_targets(mode, n, beta, size, rng)
            targets = torch.from_numpy(draws).to(links.dtype)
            moved = set_topological_charge(links.to(device), targets.to(device))
            relaxed = conditional_su2_sweeps(moved, action, args.n_su2)
            q = topological_charge(relaxed).round().cpu().numpy().astype(float)
            save_ensemble(d / f.name, relaxed.cpu(), meta)
            rec[mode] = {
                "odd_fraction": float((np.abs(q) % 2).mean()),
                "q_squared": float((q ** 2).mean()),
                "hit_rate": float((q == draws).mean()),
                **info,
            }
        records.append(rec)
        save_json(Path(args.report), records)
        e, u = rec["exact"], rec["uniform"]
        print(f"[{i+1:3d}/{len(files)}] {f.name:34s} "
              f"odd exact {e['odd_fraction']:.3f} / uniform {u['odd_fraction']:.3f}   "
              f"<Q^2> {e['q_squared']:7.3f} / {u['q_squared']:7.3f}   "
              f"(closed form {e['exact_q_squared']:7.3f})")

    if records:
        dq2 = [r["uniform"]["q_squared"] / max(r["exact"]["q_squared"], 1e-9)
               for r in records]
        print(f"\n{len(records)} ensembles re-seeded in both arms "
              f"[{time.time()-t0:.0f}s]")
        print(f"uniform/exact <Q^2> ratio: median {np.median(dq2):.2f}, "
              f"max {np.max(dq2):.2f}  -- the arms must differ, or there is "
              f"nothing to test")
        print(f"wrote {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
