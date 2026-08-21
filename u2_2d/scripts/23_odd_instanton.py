"""Stage 23: candidate delta-Q = +-1 moves for U(2), and what each one costs.

THE PROBLEM. The U(1) instanton generalizes to U(2) only in its EVEN form. A
purely central shift U -> e^{i lam} U with lam the winding-1 U(1) instanton moves
psi = arg det U by 2 lam, hence Q by 2, and costs 2 pi^2 beta / V -- a ladder
invariant, always cheap. Getting Q by 1 requires HALF that shift, and the halving
is what breaks:

  `instanton_field` gives every plaquette angle 2 pi / V *except* one corner,
  whose raw angle is 2 pi / V - 2 pi (the raw alternating sum over plaquettes
  telescopes to zero, so one plaquette must absorb the winding). Halving sends
  that corner to pi / V - pi, so cos(phi_p) flips sign there and the joint action
  pays 2 beta on a single plaquette -- dS = 37 at beta = 20, L = 8.

That cost is NOT topological. The U(2) plaquette is q0_p cos(phi_p), so a -1 in
the SU(2) plaquette at the same corner cancels the -1 in the cosine exactly. The
obstruction is only that Z_2 curvature must have an EVEN number of -1 plaquettes,
so one cannot flip that corner alone.

THE CANDIDATES. Three ideas, all measured here rather than argued:

  half_central   halve the central instanton, leave SU(2) alone. The known
                 failure, kept as the scale.
  u1_t           the U(1)_T subgroup element diag(e^{i lam}, 1) = e^{i lam/2}
                 exp(i lam n.sigma / 2). ALGEBRAICALLY this is exactly
                 "half-instanton on phi AND the same half-instanton on SU(2)
                 about a fixed axis", and the SU(2) half carries a -1 at the same
                 corner -- so on a COLD background the two -1s cancel and the cost
                 is O(beta / V). On a thermalized background the fixed axis does
                 not commute with the local SU(2) field, which is where the
                 measured O(beta L) comes from.
  *_relaxed      any of the above followed by conditional SU(2) sweeps. The
                 sampler is exact at frozen psi and cannot change Q, so this is
                 free to do and repairs the non-commutativity.

THE MARGINAL ROUTE, which is the one that should win. In 2D the SU(2) sector
integrates out exactly per plaquette (`DetSectorAction`), so the psi-marginal is
known in closed form. A move that proposes psi -> psi + lam, accepts on the
MARGINAL action alone, and then resamples q ~ p(q | psi') with the exact
conditional sampler is valid MCMC -- and its acceptance never sees the 2 beta,
because that cost is paid by an SU(2) sector which is about to be resampled
anyway. Its price is the det-sector cost of a winding-1 U(1) instanton,
2 pi^2 beta_det / V, which is the same order as the even move.

This script measures all of it: delta Q actually achieved (must be exactly +-1),
delta S joint, delta S after relaxation, and delta S in the marginal.

    python u2_2d/scripts/23_odd_instanton.py --cases 8:14 16:28
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

from u1_2d.lgt.lattice import topological_charge as u1_charge
from u2_2d.lgt.actions import DetSectorAction, WilsonU2Action
from u2_2d.lgt.exact import matched_u1_beta
from u2_2d.lgt.lattice import (det_links, half_retr, plaquette, su2_exp,
                               topological_charge, u2_mul, u2_normalize)
from u2_2d.lgt.local_updates import (central_winding_field,
                                     conditional_su2_sweeps, winding_field)
from u2_2d.utils import (configure_device, ensemble_path, load_config,
                         load_ensemble, resolve_device, save_json, set_seed)


def _as_u2(phi: torch.Tensor, quat: torch.Tensor) -> torch.Tensor:
    """Assemble a [2, L, L, 5] shift field from a phase field and a quaternion."""
    return torch.cat([phi.unsqueeze(-1), quat], dim=-1)


def shift_half_central(size, device, dtype):
    """Half the central instanton on phi, SU(2) untouched. The known failure."""
    lam = central_winding_field(size, device=device, dtype=dtype)
    quat = torch.zeros(lam.shape + (4,), device=device, dtype=dtype)
    quat[..., 0] = 1.0
    return _as_u2(0.5 * lam, quat)


def shift_u1_t(size, device, dtype, axis=None):
    """The U(1)_T subgroup element, i.e. the existing odd `winding_field`."""
    return winding_field(size, charge=1, axis=axis, device=device, dtype=dtype)


def shift_spread_twist(size, device, dtype, axis=None):
    """Half-instanton on phi AND the matching half-instanton on SU(2).

    Written out explicitly rather than via `winding_field` so the two halves are
    visible as separate objects: phi gets lam/2, and SU(2) gets the rotation
    exp(i (lam/2) n.sigma), whose plaquette carries cos(lam_p / 2) -- negative at
    exactly the corner where cos(phi_p) is negative, so the product is positive
    plaquette by plaquette. On a cold background this is the free odd move.
    """
    lam = central_winding_field(size, device=device, dtype=dtype)
    if axis is None:
        axis = torch.tensor([0.0, 0.0, 1.0], device=device, dtype=dtype)
    axis = axis / axis.norm()
    half = 0.5 * lam
    quat = torch.zeros(lam.shape + (4,), device=device, dtype=dtype)
    quat[..., 0] = torch.cos(half)
    for a in range(3):
        quat[..., 1 + a] = torch.sin(half) * axis[a]
    return _as_u2(half, quat)


CANDIDATES = {
    "half_central": shift_half_central,
    "u1_t": shift_u1_t,
    "spread_twist": shift_spread_twist,
}


def apply_shift(links: torch.Tensor, shift: torch.Tensor) -> torch.Tensor:
    return u2_normalize(u2_mul(shift.unsqueeze(0).expand_as(links), links))


def joint_action(links: torch.Tensor, beta: float) -> torch.Tensor:
    """-beta sum_p (1/2) ReTr P, per configuration."""
    return -beta * half_retr(plaquette(links)).sum(dim=(-2, -1))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="u2_2d/configs/default.yaml")
    parser.add_argument("--cases", nargs="+", default=["8:14", "16:28"],
                        help="L:beta pairs, taken from the stage-01 ensembles")
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--out-dir", default="out/u2_2d/odd_instanton")
    parser.add_argument("--n-configs", type=int, default=64)
    parser.add_argument("--relax-sweeps", type=int, default=25)
    parser.add_argument("--device", default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    if args.device:
        config["device"] = args.device
    device = resolve_device(config)
    print(configure_device(device))
    set_seed(int(config.get("seed", 0)) + 2323)
    data_dir = Path(args.data_dir or config["data"].get("out_dir", "out/u2_2d/data"))

    results = []
    for case in args.cases:
        size_s, beta_s = case.split(":")
        size, beta = int(size_s), float(beta_s)
        path = ensemble_path(data_dir, size, beta)
        if not path.exists():
            print(f"missing {path.name} -- skipping")
            continue
        links, _ = load_ensemble(path)
        links = links[: args.n_configs].to(device)
        n = links.shape[0]
        det_action = DetSectorAction(beta)
        beta_det = matched_u1_beta(beta)
        v = size * size

        q0 = topological_charge(links)
        s0 = joint_action(links, beta)
        d0 = det_action.per_config(det_links(links))
        print(f"\n=== L={size} beta={beta:g}  ({n} configs, "
              f"beta_det={beta_det:.3f}, V={v}) ===")
        print(f"  predicted even move   dS = 2 pi^2 beta_det / V = "
              f"{2 * math.pi**2 * beta_det / v:.3f}")

        rows = []

        # The even move, for scale: this is the one that works.
        lam = central_winding_field(size, device=device, dtype=links.dtype)
        quat = torch.zeros(lam.shape + (4,), device=device, dtype=links.dtype)
        quat[..., 0] = 1.0
        even = apply_shift(links, _as_u2(lam, quat))
        rows.append({
            "candidate": "central_2 (even, reference)",
            "delta_q": float((topological_charge(even) - q0).abs().float().mean()),
            "delta_s": float((joint_action(even, beta) - s0).mean()),
            "delta_s_relaxed": None,
            "delta_s_marginal": float(
                (det_action.per_config(det_links(even)) - d0).mean()),
            "seconds": 0.0,
        })

        for name, fn in CANDIDATES.items():
            t0 = time.time()
            shift = fn(size, device, links.dtype)
            moved = apply_shift(links, shift)
            dq = (topological_charge(moved) - q0).float()
            ds = (joint_action(moved, beta) - s0)
            dmarg = (det_action.per_config(det_links(moved)) - d0)
            with torch.no_grad():
                relaxed = conditional_su2_sweeps(moved, WilsonU2Action(beta),
                                                 args.relax_sweeps)
            ds_rel = (joint_action(relaxed, beta) - s0)
            # The conditional sampler must not move Q -- it runs at frozen psi.
            dq_rel = (topological_charge(relaxed) - q0).float()
            rows.append({
                "candidate": name,
                "delta_q": float(dq.abs().mean()),
                "delta_q_after_relax": float(dq_rel.abs().mean()),
                "delta_q_exactly_one": bool(torch.all(dq.abs() == 1)),
                "delta_s": float(ds.mean()),
                "delta_s_relaxed": float(ds_rel.mean()),
                "delta_s_marginal": float(dmarg.mean()),
                "seconds": time.time() - t0,
            })

        for r in rows:
            rel = ("--" if r["delta_s_relaxed"] is None
                   else f"{r['delta_s_relaxed']:9.2f}")
            print(f"  {r['candidate']:<28} |dQ| {r['delta_q']:.3f}  "
                  f"dS {r['delta_s']:9.2f}  relaxed {rel}  "
                  f"marginal {r['delta_s_marginal']:8.3f}")

        results.append({"lattice_size": size, "beta": beta, "beta_det": beta_det,
                        "n_configs": n, "relax_sweeps": args.relax_sweeps,
                        "even_move_prediction": 2 * math.pi**2 * beta_det / v,
                        "candidates": rows})

    if results:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        save_json(out_dir / "odd_instanton.json", results)
        print(f"\nwrote {out_dir / 'odd_instanton.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
