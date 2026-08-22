"""Is the marginal odd winding move exact? Scan its one approximation.

WHY. Under the marginal move (`--charge-step 1`), `07_pq_sampling.py` at L = 8
returns an odd-sector weight that is LOW at every coupling tested:

    beta      6        10        14        20
    odd/exact 0.9909   0.9897    0.9870    0.9923

Four independent couplings, same sign, ~1%. The closed form is not the culprit:
recomputing `det_topological_charge_distribution` with a 16x finer k grid, a 4x
wider k cut, a 4x finer alpha grid and 4x more sectors moves <Q^2> and P(odd) by
less than 1e-6 relative. So the deficit is in the sampler.

THE CANDIDATE, and it is the one the move's own docstring names. The composite
is (i) a Metropolis step on psi whose acceptance depends on psi alone, then
(ii) a resample of the SU(2) sector from its exact conditional p(q | psi). Step
(ii) is exact only in the limit of infinitely many conditional sweeps; it runs
`n_su2_sweeps` of them. Worse, it runs them ONLY on accepted configurations --
which is correct in exact arithmetic, because a rejected configuration's psi did
not move and its q is therefore still an equilibrium draw, but which at finite
sweeps makes the approximation ASYMMETRIC: every parity-flipping move lands
slightly out of equilibrium while every rejected one stays exactly in it. An
under-converged resample therefore penalises precisely the moves that flip
parity, and it does so in the direction observed.

That story makes a falsifiable prediction. Q is a functional of psi alone, so if
the conditional resample were exact the SU(2) sweep count could not touch P(Q)
at all -- the psi-marginal kernel would be stationary regardless. The deficit
must therefore SHRINK as `n_su2_sweeps` grows, and extrapolate to zero. If
instead it is flat in the sweep count, the cause is elsewhere (the proposal, the
acceptance, or the burn-in) and this script has eliminated the obvious suspect
rather than confirmed it.

Run at L = 8, where CPU beats GPU roughly two to one for U(2) HMC, so this
occupies the idle cores rather than competing with a GPU-bound queue.

    python u2_2d/scripts/34_marginal_move_bias.py --device cpu
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u2_2d.lgt.actions import WilsonU2Action
from u2_2d.lgt.exact import det_topological_charge_distribution
from u2_2d.lgt.hmc import BatchedHMCU2
from u2_2d.lgt.lattice import topological_charge
from u2_2d.utils import configure_device, resolve_device, save_json, set_seed


def chain_bootstrap(per_chain: np.ndarray, fn, n_boot: int = 400, seed: int = 0):
    """(value, standard error) resampling whole CHAINS with replacement.

    Same estimator as `07_pq_sampling.py`: resampling chains rather than
    configurations keeps the bar honest under freezing, because a chain that
    never moved contributes no spread.
    """
    rng = np.random.default_rng(seed)
    value = float(fn(per_chain))
    n_chains = per_chain.shape[1]
    draws = [float(fn(per_chain[:, rng.integers(0, n_chains, n_chains)]))
             for _ in range(n_boot)]
    return value, float(np.std(draws, ddof=1))


def run_one(size: int, beta: float, sweeps: int, args, device) -> dict:
    """One (coupling, sweep count) cell: hot start, marginal move, measure P(odd)."""
    set_seed(args.seed)
    action = WilsonU2Action(beta)
    step = args.step_size / math.sqrt(max(beta, 1.0))
    sampler = BatchedHMCU2(
        size, action, n_chains=args.n_chains, n_steps=args.n_steps,
        step_size=step, device=str(device), hot_start=True,
        topological_updates=True, winding_charge_step=1,
        winding_interval=args.winding_interval, winding_su2_sweeps=sweeps)
    t0 = time.time()
    configs, _ = sampler.sample(args.n_draws, burn_in=args.burn_in,
                                thin=args.thin,
                                initial_state=sampler.initialize(hot=True))
    # [n_draws, n_chains] charge history.
    q = topological_charge(configs.reshape(-1, *configs.shape[-4:])).round()
    q = q.reshape(args.n_draws, args.n_chains).cpu().numpy().astype(float)

    q_values, probs = det_topological_charge_distribution(beta, size)
    odd_exact = float(probs[q_values % 2 != 0].sum())
    q2_exact = float((q_values.astype(float) ** 2 * probs).sum())

    # P(odd) is a SINGLE binomial functional of the history, so it is bootstrapped
    # directly. 07_pq_sampling.py instead sums per-sector errors in quadrature,
    # which OVERstates the error on a subset of multinomial cells (they are
    # negatively correlated) and so understates every odd_z it reports.
    odd, odd_err = chain_bootstrap(np.abs(q) % 2, np.mean, seed=args.seed)
    q2, q2_err = chain_bootstrap(q ** 2, np.mean, seed=args.seed + 1)
    return {
        "lattice_size": size, "beta": beta, "winding_su2_sweeps": sweeps,
        "n_chains": args.n_chains, "n_draws": args.n_draws,
        "odd_measured": odd, "odd_err": odd_err, "odd_exact": odd_exact,
        "odd_ratio": odd / odd_exact,
        "odd_z": (odd - odd_exact) / odd_err if odd_err > 0 else float("inf"),
        "q_squared": q2, "q_squared_err": q2_err, "q_squared_exact": q2_exact,
        "q_squared_z": (q2 - q2_exact) / q2_err if q2_err > 0 else float("inf"),
        "sector_changes": int((np.diff(q, axis=0) != 0).sum()),
        "parity_flips": int((np.diff(np.abs(q) % 2, axis=0) != 0).sum()),
        "seconds": time.time() - t0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--lattice-size", type=int, default=8)
    parser.add_argument("--betas", default="10,14")
    parser.add_argument("--su2-sweeps", default="5,25,100,400",
                        help="conditional SU(2) sweeps after an ACCEPTED "
                             "winding move -- the quantity under test")
    parser.add_argument("--n-chains", type=int, default=256)
    parser.add_argument("--n-draws", type=int, default=600)
    parser.add_argument("--n-steps", type=int, default=10)
    parser.add_argument("--step-size", type=float, default=0.6)
    parser.add_argument("--burn-in", type=int, default=600)
    parser.add_argument("--thin", type=int, default=5)
    parser.add_argument("--winding-interval", type=int, default=5)
    parser.add_argument("--seed", type=int, default=917)
    parser.add_argument("--out-dir", default="out/u2_2d/marginal_move_bias")
    args = parser.parse_args()

    device = resolve_device({"device": args.device})
    print(configure_device(device))
    betas = [float(b) for b in args.betas.split(",")]
    sweeps = [int(s) for s in args.su2_sweeps.split(",")]
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"\nL = {args.lattice_size}, marginal move (charge_step 1), "
          f"{args.n_chains} chains x {args.n_draws} draws")
    print("If the conditional resample were exact, P(Q) could not depend on the "
          "sweep count at all.\n")
    header = (f"{'beta':>7s} {'sweeps':>7s} {'odd':>9s} {'exact':>9s} "
              f"{'ratio':>8s} {'z':>7s} {'<Q^2> z':>8s} {'flips':>8s} {'s':>6s}")
    records = []
    for beta in betas:
        print(header)
        for n in sweeps:
            r = run_one(args.lattice_size, beta, n, args, device)
            records.append(r)
            print(f"{beta:7g} {n:7d} {r['odd_measured']:9.5f} "
                  f"{r['odd_exact']:9.5f} {r['odd_ratio']:8.5f} "
                  f"{r['odd_z']:+7.2f} {r['q_squared_z']:+8.2f} "
                  f"{r['parity_flips']:8d} {r['seconds']:6.0f}")
            save_json(out / "marginal_move_bias.json", records)
        print()

    print("=" * 78)
    for beta in betas:
        rows = [r for r in records if r["beta"] == beta]
        first, last = rows[0], rows[-1]
        d0 = 100.0 * (first["odd_ratio"] - 1.0)
        d1 = 100.0 * (last["odd_ratio"] - 1.0)
        print(f"beta {beta:g}: odd deficit {d0:+.2f}% at "
              f"{first['winding_su2_sweeps']} sweeps -> {d1:+.2f}% at "
              f"{last['winding_su2_sweeps']} sweeps")
    print("\nA deficit that shrinks with the sweep count confirms the finite "
          "conditional resample.\nA deficit flat in the sweep count "
          "EXONERATES it and the cause is elsewhere.")
    print(f"\nwrote {out / 'marginal_move_bias.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
