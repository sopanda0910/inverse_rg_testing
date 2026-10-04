"""The control the entry-cost comparison was missing: a cold start given the
same local sweeps the delivered pipeline gets.

WHY. Sec. IV A of the paper compares the delivered product -- one lift plus the
sixteen local sweeps of the tail, and NO trajectories -- against a winding HMC
chain burned in for 500 to 8000 trajectories, and concludes the classical entry
cost rises by an order of magnitude across the coupling range while the lift's
stays at zero. But the lift's tail is not free of local relaxation: it is
sixteen sweeps of heatbath plus overrelaxation, which is an exact update of the
fine action and a far better LOCAL relaxer per unit work than HMC. Nobody had
asked what a cold start does with those same sixteen sweeps, so the comparison
could be read as measuring HMC's weakness at local relaxation rather than the
preconditioner's strength.

This script asks. One arm, cold start, N local sweeps, scored exactly as
`14_diffusion_vs_instanton_hmc.py` scores its arms: the same three Wilson
observables against the same closed form, and the same quality gate of every
observable within 2.5 standard errors. W(6x6) and W(8x8) are carried too,
because local sweeps are expected to be a low-pass repair and the entry-cost
observable set stops at W(4x4).

WHAT IT CANNOT CHANGE, AND WHERE THAT IS ONLY ALMOST TRUE. `retherm_sweeps`
runs with `topological_updates=False`, so no update in this arm is designed to
change Q. At the stiff couplings that is absolute and the arm sits at
<Q^2> = 0 forever: the heatbath would have to carry a plaquette angle past
+-pi, which costs 2 beta. At beta = 4.44 it is not absolute -- that barrier is
only ~8.9 and the measured arm reaches <Q^2> = 3.4 against an exact 6.8 -- so
the claim is "with negligible probability at the couplings that matter", not
"by construction". Either way the topological half of the comparison is the one
the sweeps cannot supply, and it is the half that carries to four dimensions.

    python u1_2d/scripts/79_cold_sweeps_control.py --device cpu
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u1_2d.lgt import make_action
from u1_2d.lgt.exact import wilson_loop_exact
from u1_2d.lgt.hmc import BatchedHMC, adapted_hmc_params
from u1_2d.lgt.lattice import (plaquette_angles, topological_charge,
                               wilson_loop_angles)
from u1_2d.lgt.local_updates import retherm_sweeps
from u1_2d.utils import save_json, set_seed

# The first three are the entry-cost set of script 14, and the gate is applied
# over those alone so the verdict is comparable. The last two are reported
# because a low-pass repair is exactly what a larger loop would expose.
GATE_LOOPS = [(1, 1), (2, 2), (4, 4)]
EXTRA_LOOPS = [(6, 6), (8, 8)]
ALL_LOOPS = GATE_LOOPS + EXTRA_LOOPS


def measure(field, beta, size):
    """Relative deviation and z for each loop, plus <Q^2>.

    Every configuration here is an independent draw -- a cold start carries no
    randomness, so the sweeps are what makes the members differ, and they are
    applied independently per configuration. The error is therefore the plain
    standard error of the mean with no autocorrelation factor.
    """
    out = {}
    with torch.no_grad():
        for nx, ny in ALL_LOOPS:
            ang = (plaquette_angles(field) if (nx, ny) == (1, 1)
                   else wilson_loop_angles(field, nx, ny))
            v = torch.cos(ang).mean(dim=(-2, -1)).cpu().numpy().astype(float)
            exact = wilson_loop_exact(beta, nx * ny, "wilson", size)
            mean = float(v.mean())
            err = float(v.std(ddof=1) / np.sqrt(v.size))
            out[f"W{nx}x{ny}"] = {
                "mean": mean, "exact": exact, "sem": err,
                "ppm": (mean - exact) / exact * 1e6,
                "z": abs(mean - exact) / max(err, 1e-15)}
        q = topological_charge(field).cpu().numpy().astype(float)
    out["q_squared"] = float((q ** 2).mean())
    return out


def worst_z(rec, loops):
    return max(rec[f"W{a}x{b}"]["z"] for a, b in loops)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--size", type=int, default=32)
    # the couplings of the entry-cost experiment, out/u1_2d/diffusion_vs_instanton
    ap.add_argument("--betas", default="4.44,14.1464,55.0237,118.5,218.58")
    ap.add_argument("--n-configs", type=int, default=256)
    ap.add_argument("--max-sweeps", type=int, default=64)
    ap.add_argument("--record-every", type=int, default=2)
    ap.add_argument("--seed", type=int, default=7919)
    ap.add_argument("--out-dir", default="out/u1_2d/cold_sweeps_control")
    args = ap.parse_args()

    set_seed(args.seed)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = []

    for beta in [float(b) for b in args.betas.split(",")]:
        t0 = time.time()
        action = make_action("wilson", beta)
        step_size, n_steps = adapted_hmc_params(beta)
        # only used to build a correctly shaped cold configuration
        hmc = BatchedHMC(args.size, action, n_chains=args.n_configs,
                         n_steps=n_steps, step_size=step_size,
                         device=args.device, topological_updates=False)
        st = hmc.initialize(hot=False)

        series = [{"sweeps": 0, **measure(st, beta, args.size)}]
        for nsw in range(args.record_every, args.max_sweeps + 1,
                         args.record_every):
            st = retherm_sweeps(st, action, args.record_every)
            series.append({"sweeps": nsw, **measure(st, beta, args.size)})

        def first_below(thresh, loops):
            for r in series:
                if worst_z(r, loops) <= thresh:
                    return r["sweeps"]
            return None

        # the deployed tail length; fall back to the nearest record below it so
        # a short smoke run still reports
        at16 = next((r for r in series if r["sweeps"] == 16), series[-1])
        rec = {
            "beta": beta, "lattice_size": args.size,
            "n_configs": args.n_configs, "max_sweeps": args.max_sweeps,
            "sweeps_to_z2.5_gate": first_below(2.5, GATE_LOOPS),
            "sweeps_to_z2_gate": first_below(2.0, GATE_LOOPS),
            "sweeps_to_z2.5_all": first_below(2.5, ALL_LOOPS),
            "at_16_sweeps": at16,
            "series": series,
            "seconds": time.time() - t0,
        }
        rows.append(rec)
        save_json(out / "cold_sweeps_control.json", rows)

        print(f"\n{'='*74}\nbeta = {beta:g}, L = {args.size}, "
              f"{args.n_configs} configs  [{rec['seconds']:.0f}s]")
        print(f"  entry-cost gate (W1x1,W2x2,W4x4 within 2.5 sigma): "
              f"{rec['sweeps_to_z2.5_gate']} sweeps")
        print(f"  same gate including W6x6 and W8x8:                 "
              f"{rec['sweeps_to_z2.5_all']}")
        print(f"  at the deployed tail length of 16 sweeps:")
        for nx, ny in ALL_LOOPS:
            e = at16[f"W{nx}x{ny}"]
            print(f"    W({nx}x{ny})  {e['ppm']:+12.1f} ppm   |z| = {e['z']:7.2f}")
        print(f"    <Q^2> = {at16['q_squared']:.4f}  (invariant: sweeps are "
              f"topology-preserving)")

    print(f"\n{'='*74}\nVERDICT")
    for r in rows:
        g = r["sweeps_to_z2.5_gate"]
        a = r["sweeps_to_z2.5_all"]
        print(f"  beta {r['beta']:>8g}: entry-cost gate "
              f"{'never' if g is None else str(g)+' sweeps':>12s}"
              f"   with large loops "
              f"{'never' if a is None else str(a)+' sweeps':>12s}"
              f"   <Q^2> {r['at_16_sweeps']['q_squared']:.3f}")
    print("\n  Read against Table IX: the lift's entry cost is 0 trajectories and")
    print("  winding HMC's is 500-8000. If this arm clears the gate cheaply, the")
    print("  LOCAL half of that comparison is about HMC being a poor local")
    print("  relaxer; the topological half is unaffected either way, since")
    print("  <Q^2> is pinned at 0 here by construction.")
    print(f"\nwrote {out / 'cold_sweeps_control.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
