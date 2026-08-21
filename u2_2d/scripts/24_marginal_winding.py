"""Stage 24: the marginal odd-charge move, and whether it makes the CLASSICAL
arm ergodic.

This is the experiment that decides a headline claim. The U(2) study currently
says the classical arm "covers 0.507 of the exact P(Q) with zero odd sectors and
cannot improve at any cost, because odd charge has probability zero in its
stationary distribution rather than merely long autocorrelation". That rests
entirely on odd-charge winding being unaffordable, which §11.5 shows is an
artifact of proposing the move in the JOINT configuration:

  joint proposal, SU(2) held fixed :  dS = 24 to 278   (acceptance ~ 0)
  marginal proposal               :  dS = 0.53 to 0.79 (acceptance ~ 0.6)

THE MOVE. In 2D the SU(2) sector integrates out exactly per plaquette
(`DetSectorAction`), so the psi-marginal is known in closed form:

  1. propose psi' = psi +- lam, lam the winding-1 U(1) instanton. On links this
     is U -> e^{i s lam / 2} U, a pure phase multiply: phi shifts by s lam / 2 and
     psi = 2 phi by s lam, so delta Q = s exactly. Symmetric and involutive.
  2. accept with min(1, exp(-[S_det(psi') - S_det(psi)])) -- the MARGINAL action,
     ignoring q entirely. The 2 beta the joint move pays never appears, because
     it is charged to an SU(2) configuration that is about to be resampled.
  3. on acceptance, resample q ~ p(q | psi') with `conditional_su2_sweeps`, which
     is exact at frozen psi and cannot change Q.

VALIDITY, and the one approximation. Step 2 is a collapsed Metropolis step whose
acceptance depends on psi alone, so the psi-marginal evolves under a kernel with
pi(psi) stationary. Step 3 restores the conditional. The composite is stationary
for pi(psi, q) PROVIDED step 3 resamples to equilibrium; with a finite sweep count
it is approximate, controlled by `--su2-sweeps`. 2D SU(2) at frozen psi has no
topological obstruction and mixes fast, so this is expected to be a small effect
-- but it is an approximation, and the convergence check below is what tests it,
not an argument.

WHAT THIS SCRIPT MEASURES. Cold-start chains at couplings where the existing
charge_step=2 move is parity-frozen by construction, comparing:

  step2      the deployed move: delta Q = +-2, cannot change parity, ever
  step1      the deployed odd move: U(1)_T subgroup, joint acceptance ~ 0
  marginal   the move above

Reported per arm: parity flips, P(odd) against exact, <Q^2> against exact, and a
chi^2 over sectors. If `marginal` flips parity and converges to the exact P(Q),
the "unreachable at any cost" claim must be withdrawn.

    python u2_2d/scripts/24_marginal_winding.py --cases 8:20 16:28
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u1_2d.lgt.lattice import wrap as u1_wrap
from u1_2d.lgt.local_updates import instanton_field
from u2_2d.lgt.actions import DetSectorAction, WilsonU2Action
from u2_2d.lgt.exact import det_topological_charge_distribution
from u2_2d.lgt.hmc import BatchedHMCU2, adapted_hmc_params
from u2_2d.lgt.lattice import det_links, topological_charge
from u2_2d.lgt.local_updates import conditional_su2_sweeps
from u2_2d.utils import (configure_device, load_config, resolve_device,
                         save_json, set_seed)


def phase_shift(links: torch.Tensor, alpha: torch.Tensor) -> torch.Tensor:
    """U -> e^{i alpha} U, i.e. phi += alpha with the SU(2) part untouched.

    The whole odd move is this one line: psi = 2 phi picks up 2 alpha, so
    alpha = lam / 2 moves the determinant winding by exactly one.
    """
    out = links.clone()
    out[..., 0] = u1_wrap(out[..., 0] + alpha)
    return out


def marginal_winding_update(links: torch.Tensor, action, charge_step: int = 1,
                            n_su2_sweeps: int = 25,
                            generator: torch.Generator | None = None
                            ) -> tuple[torch.Tensor, torch.Tensor]:
    """delta Q = +- charge_step, accepted on the exact psi-marginal."""
    size = links.shape[-2]
    det_action = DetSectorAction(action.beta)
    lam = instanton_field(size, device=links.device, dtype=links.dtype)

    signs = torch.randint(0, 2, (links.shape[0],), device=links.device,
                          generator=generator, dtype=links.dtype) * 2 - 1
    alpha = 0.5 * charge_step * signs.view(-1, 1, 1, 1) * lam.unsqueeze(0)
    proposal = phase_shift(links, alpha)

    with torch.no_grad():
        ds = (det_action.per_config(det_links(proposal))
              - det_action.per_config(det_links(links)))
        u = torch.rand(ds.shape, device=ds.device, generator=generator)
        accept = u < torch.exp(-ds.clamp(max=60.0))
        out = torch.where(accept.view(-1, 1, 1, 1, 1), proposal, links)
        if bool(accept.any()) and n_su2_sweeps:
            # Only accepted configurations need their SU(2) sector refreshed;
            # resampling the rest would be valid but wasteful.
            out = torch.where(
                accept.view(-1, 1, 1, 1, 1),
                conditional_su2_sweeps(out, action, n_su2_sweeps),
                out)
    return out, accept


def sector_stats(q: np.ndarray, beta: float, size: int) -> dict:
    q_vals, q_probs = det_topological_charge_distribution(beta, size)
    exact = {int(v): float(p) for v, p in zip(q_vals, q_probs)}
    qi = q.round().astype(int)
    n = qi.size
    p_odd_exact = sum(p for s, p in exact.items() if s % 2)
    p_odd = float(np.mean(qi % 2 != 0))
    err = math.sqrt(max(p_odd_exact * (1 - p_odd_exact), 1e-12) / max(n, 1))
    chi2, dof = 0.0, 0
    for s, p in exact.items():
        if p * n < 5:
            continue
        obs = float(np.sum(qi == s))
        chi2 += (obs - p * n) ** 2 / (p * n)
        dof += 1
    return {
        "p_odd": p_odd,
        "p_odd_exact": float(p_odd_exact),
        "p_odd_z": (p_odd - p_odd_exact) / err if err > 0 else float("nan"),
        "q_squared": float((q.astype(float) ** 2).mean()),
        "q_squared_exact": float((q_vals.astype(float) ** 2 * q_probs).sum()
                                 / q_probs.sum()),
        "chi2_per_dof": chi2 / max(dof - 1, 1),
        "n_sectors": int(len(set(qi.tolist()))),
        "n_odd_sectors": int(len({s for s in qi.tolist() if s % 2})),
    }


def run_chain(mode: str, size: int, beta: float, n_chains: int, n_traj: int,
              device: str, su2_sweeps: int) -> dict:
    action = WilsonU2Action(beta)
    step_size, n_steps = adapted_hmc_params(beta)
    # The winding move is applied here, not inside the sampler, so all three arms
    # share one HMC implementation and differ only in the global move.
    sampler = BatchedHMCU2(size, action, n_chains=n_chains, n_steps=n_steps,
                           step_size=step_size, device=device,
                           topological_updates=False)
    links = sampler.initialize(hot=False)
    q_series, flips, accepts, total = [], 0, 0, 0
    prev = topological_charge(links).cpu().numpy().round()
    t0 = time.time()
    with torch.no_grad():
        for _ in range(n_traj):
            links, _ = sampler.metropolis_step(links)
            if mode == "marginal":
                links, acc = marginal_winding_update(
                    links, action, charge_step=1, n_su2_sweeps=su2_sweeps)
            else:
                from u2_2d.lgt.local_updates import winding_update
                links, acc = winding_update(
                    links, action, charge_step=(2 if mode == "step2" else 1))
            accepts += int(acc.sum())
            total += acc.numel()
            cur = topological_charge(links).cpu().numpy().round()
            flips += int(np.sum((cur % 2) != (prev % 2)))
            prev = cur
            q_series.append(cur)
    q = np.concatenate(q_series[len(q_series) // 2:])
    rec = {"mode": mode, "parity_flips": flips,
           "winding_acceptance": accepts / max(total, 1),
           "seconds": time.time() - t0, "n_chains": n_chains, "n_traj": n_traj}
    rec.update(sector_stats(q, beta, size))
    return rec


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="u2_2d/configs/default.yaml")
    parser.add_argument("--cases", nargs="+", default=["8:20", "16:28"])
    parser.add_argument("--modes", nargs="+",
                        default=["step2", "step1", "marginal"])
    parser.add_argument("--n-chains", type=int, default=128)
    parser.add_argument("--n-traj", type=int, default=400)
    parser.add_argument("--su2-sweeps", type=int, default=25)
    parser.add_argument("--out-dir", default="out/u2_2d/marginal_winding")
    parser.add_argument("--device", default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    if args.device:
        config["device"] = args.device
    device = resolve_device(config)
    print(configure_device(device))
    set_seed(int(config.get("seed", 0)) + 2424)

    results = []
    for case in args.cases:
        size_s, beta_s = case.split(":")
        size, beta = int(size_s), float(beta_s)
        print(f"\n=== L={size} beta={beta:g}  "
              f"({args.n_chains} chains x {args.n_traj} traj, cold start) ===")
        rows = []
        for mode in args.modes:
            rec = run_chain(mode, size, beta, args.n_chains, args.n_traj,
                            device, args.su2_sweeps)
            rows.append(rec)
            print(f"  {mode:<9} flips {rec['parity_flips']:>7}  "
                  f"acc {rec['winding_acceptance']:.3f}  "
                  f"P(odd) {rec['p_odd']:.4f} (exact {rec['p_odd_exact']:.4f}, "
                  f"z={rec['p_odd_z']:+.2f})  "
                  f"<Q^2> {rec['q_squared']:.3f} (exact "
                  f"{rec['q_squared_exact']:.3f})  "
                  f"chi2/dof {rec['chi2_per_dof']:.2f}  "
                  f"[{rec['seconds']:.0f}s]")
        results.append({"lattice_size": size, "beta": beta, "arms": rows})

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    save_json(out_dir / "marginal_winding.json", results)
    print(f"\nwrote {out_dir / 'marginal_winding.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
