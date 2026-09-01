"""Can stronger reconstruction guidance replace the charge projection?

Opened 2026-08-24, straight out of `51_transport_ablation.py`. That run showed
the RAW lift (charge projection off) carries `Q_fine - Q_coarse` with std 1.79
at L = 32 and 3.36 at L = 64 -- a sqrt(V) random walk -- because the model is
only SOFTLY guided toward blocking consistency. The obvious follow-up: turn the
guidance up.

**Why this is not obviously free, and why it is not the `physics_blend_coef`
mistake either.**

`blocking_consistency_score` is the gradient of
`-(cell_sum - coarse_plaq)^2 / (2 lambda(sigma))` with `lambda = 8 sigma^2`,
and that variance is CORRECT: at noise level sigma the eight boundary links of
a 2x2 cell each inject sigma^2 into the blocked plaquette. So
`consistency_weight = 1.0` is the exact Bayesian reconstruction-guidance
weight, not an arbitrary knob. Raising it asserts the constraint is known more
precisely than the noise allows, which biases the sample toward the centre of
the fiber -- in the limit, toward `flux`, the deterministic blocking-consistent
prolongator, which has PERFECT topology and catastrophic local structure
(over-dispersed ~310x against the exact per-configuration sigma, never
thermalizes within 400 trajectories).

But unlike `physics_blend_coef` -- which mixed in the psi MARGINAL score, the
wrong object, and degraded monotonically -- this term guides toward a constraint
the true conditional satisfies EXACTLY: `p(psi_f | psi_c)` is supported on the
fiber `block(psi_f) = psi_c`. So there is no a-priori reason the correct weight
is 1.0 at every sigma, and the trade-off has to be measured rather than argued.

**What must be measured, both halves.** The failure mode of a topology-only
scorecard is exactly the `physics_blend_coef` trap: a setting that fixes Q while
quietly wrecking the local physics. So every weight is scored on

  * TOPOLOGY  -- telescope residual, std(Q_f - Q_c), sector match, <Q^2>/exact;
  * LOCAL     -- plaquette and Wilson loops against the closed form, and the
                 per-configuration dispersion against the EXACT sigma from the
                 free energy (`flux` fails here by 310x while passing on Q).

Charge projection is OFF throughout -- the point is to see the topology the
model produces unaided -- and no rethermalization is applied, so this scores the
RAW lift.

    .venv/Scripts/python.exe u2_2d/scripts/53_consistency_weight_scan.py \
        --weights 1 2 5 10 30 --rung 0 --n-configs 256
"""

import argparse
import importlib.util
import math
import sys
import time
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from u1_2d.lgt.lattice import plaquette_angles as u1_plaq
from u1_2d.lgt.lattice import topological_charge as u1_charge
from u1_2d.lgt.lattice import wrap as u1_wrap
from u2_2d.lgt.actions import WilsonU2Action
from u2_2d.lgt.exact import (det_topological_charge_distribution, plaquette_exact,
                             wilson_loop_exact)
from u2_2d.lgt.lattice import det_links, half_retr, plaquette, topological_charge, wilson_loop
from u2_2d.lgt.local_updates import conditional_su2_sweeps
from u2_2d.model.su2_lift import assemble_links, naive_su2_inverse_block
from u2_2d.utils import (ensemble_path, load_config, load_ensemble, resolve_device,
                         save_json, set_seed)


def exact_sigma_1config_plaquette(beta: float, size: int, h: float = 1e-3) -> float:
    dp = (plaquette_exact(beta + h * beta, size)
          - plaquette_exact(beta - h * beta, size)) / (2.0 * h * beta)
    return math.sqrt(max(dp, 0.0) / (size * size))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="u2_2d/configs/default.yaml")
    ap.add_argument("--device", default=None)
    ap.add_argument("--out-dir", default="out/u2_2d/consistency_weight_scan")
    ap.add_argument("--rung", type=int, default=0)
    ap.add_argument("--n-configs", type=int, default=256)
    ap.add_argument("--weights", type=float, nargs="+", default=[1, 2, 5, 10, 30])
    ap.add_argument("--checkpoint", default=None)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    config = load_config(args.config)
    if args.device:
        config["device"] = args.device
    device = resolve_device(config)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    lc = config["ladder"]
    base = lc["base"]
    schedule = [float(b) for b in lc["beta_schedule"]]
    sizes = [int(base["lattice_size"]) * 2 ** (i + 1) for i in range(len(schedule))]
    rung = args.rung if args.rung >= 0 else len(schedule) - 1
    beta, size = schedule[rung], sizes[rung]
    ladder_dir = Path(lc.get("out_dir", "out/u2_2d/ladder"))
    coarse_path = (ensemble_path(config["data"]["out_dir"],
                                 int(base["lattice_size"]), float(base["beta"]))
                   if rung == 0 else
                   ensemble_path(ladder_dir, sizes[rung - 1], schedule[rung - 1],
                                 tag="ladder"))
    coarse, _ = load_ensemble(coarse_path)
    # The ladder subsamples the base by taking the LAST n (CLAUDE.md), so match
    # that here or the coarse partners are not the ones the pipeline would use.
    coarse = coarse[-args.n_configs:]
    psi_coarse = det_links(coarse)
    q_coarse = u1_charge(psi_coarse).numpy().astype(int)

    from u2_2d.model.det_lift import load_det_model
    from u2_2d.pipeline.ladder import generate_fine_from_coarse

    ckpt = args.checkpoint or config["train"].get(
        "checkpoint_path", "out/u2_2d/checkpoints/det_score_net.pt")
    model, sched = load_det_model(ckpt, device=device)

    exact_plaq = plaquette_exact(beta, size)
    sigma_exact = exact_sigma_1config_plaquette(beta, size)
    eq, ep = det_topological_charge_distribution(beta, size)
    exact_q2 = float((ep * eq.astype(float) ** 2).sum())
    loops = {"wilson_2x2": 4, "wilson_4x4": 16}
    exact_loops = {k: wilson_loop_exact(beta, a, lattice_size=size) for k, a in loops.items()}
    n_su2 = int(lc.get("n_su2_sweeps", 30))

    print(f"rung {rung}: L={size} beta={beta:g}, {coarse.shape[0]} configs")
    print(f"exact: plaq={exact_plaq:.8f}  sigma_1config={sigma_exact:.3e}  "
          f"<Q^2>={exact_q2:.4f}\n", flush=True)

    rows = []
    for w in args.weights:
        set_seed(args.seed)
        t0 = time.time()
        # The pipeline's OWN entry point, so the SU(2) assembly and the exact
        # conditional sweeps are exactly what the ladder would do. Only
        # `consistency_weight` and `enforce_coarse_charge` differ from deployment.
        # enforce_coarse_charge=False THROUGHOUT: the question is what topology
        # the guidance alone produces, so the projection must not mask it.
        links = generate_fine_from_coarse(
            model, sched, coarse, beta, n_su2_sweeps=n_su2, device=device,
            n_sampler_steps=int(lc.get("n_sampler_steps", 200)),
            n_corrector_steps=int(lc.get("n_corrector_steps", 1)),
            batch_size=int(lc.get("batch_size", 64)),
            consistency_weight=float(w),
            enforce_coarse_charge=False,
            physics_blend_coef=float(lc.get("physics_blend_coef", 0.0)),
        )
        with torch.no_grad():
            # The conditional SU(2) sampler leaves psi -- and therefore Q --
            # bit-for-bit unchanged, so reading psi off the assembled links is
            # the same psi the lift produced.
            psi_fine = det_links(links)
            fp = u1_plaq(psi_fine)
            cell = (fp[:, 0::2, 0::2] + fp[:, 1::2, 0::2]
                    + fp[:, 0::2, 1::2] + fp[:, 1::2, 1::2])
            # TWO residuals, and the distinction is the whole diagnostic.
            # `blocking_consistency_score`'s own docstring: "a wrapped residual
            # is blind to a cell sum landing 2 pi away from its coarse target,
            # which lets spurious winding defects freeze in". The WRAPPED
            # residual measures local accuracy; the RAW one counts the winding
            # defects that actually move Q. At w = 1 the wrapped residual is
            # 0.046 rad over 256 cells -- far too small to produce the observed
            # std(dQ) = 1.5 -- so the charge error lives entirely in the rare
            # defects a wrapped metric cannot see.
            raw_resid = cell - u1_plaq(psi_coarse)
            tel = u1_wrap(raw_resid)
            defects = raw_resid.abs() > math.pi
            q_fine = u1_charge(psi_fine).numpy().astype(int)

            # No rethermalization: this scores the RAW lift.
            links = links.to(device)
            per_cfg = half_retr(plaquette(links)).mean(dim=(-2, -1)).cpu().numpy()
            # half_retr FIRST: wilson_loop returns the U(2) loop itself, and
            # averaging its raw components is meaningless (it read -99% before
            # this was fixed). `17.measure` uses the same half_retr(...).mean().
            loop_vals = {k: float(half_retr(wilson_loop(links, a, a)).mean())
                         for k, a in (("wilson_2x2", 2), ("wilson_4x4", 4))}

        d = q_fine - q_coarse
        q2 = float((q_fine.astype(float) ** 2).mean())
        rec = {
            "consistency_weight": w, "seconds": time.time() - t0,
            "telescope_abs_mean": float(tel.abs().mean()),
            "telescope_frac_gt_half": float((tel.abs() > 0.5).float().mean()),
            "raw_residual_abs_mean": float(raw_resid.abs().mean()),
            "defects_per_config": float(defects.float().sum(dim=(-2, -1)).mean()),
            # Sum_cells raw_resid = 2 pi (Q_f - Q_c) EXACTLY, so decomposing the
            # per-cell residual into a coherent part (its signed mean within a
            # configuration) and an incoherent part (its spread) says which
            # mechanism moves the charge. Coherent -> the error scales with the
            # CELL COUNT; incoherent -> with its square root. Guessing between
            # these was wrong twice; this measures it.
            "resid_coherent_mean": float(raw_resid.mean(dim=(-2, -1)).abs().mean()),
            "resid_incoherent_std": float(raw_resid.std(dim=(-2, -1)).mean()),
            "sum_resid_over_2pi_std": float(
                (raw_resid.sum(dim=(-2, -1)) / (2 * math.pi)).std()),
            "dq_std": float(d.std()), "dq_mean": float(d.mean()),
            "sector_match": float((d == 0).mean()),
            "q_squared": q2, "q_squared_over_exact": q2 / exact_q2,
            "plaq_mean": float(per_cfg.mean()),
            "plaq_rel_err": (float(per_cfg.mean()) - exact_plaq) / abs(exact_plaq),
            "plaq_sigma_over_exact": float(per_cfg.std(ddof=1)) / sigma_exact,
            "loops": {k: {"value": v, "rel_err": (v - exact_loops[k]) / abs(exact_loops[k])}
                      for k, v in loop_vals.items()},
        }
        rows.append(rec)
        print(f"  w={w:<5g} wrap|.|={rec['telescope_abs_mean']:.4f}  "
              f"defects/cfg={rec['defects_per_config']:6.2f}  "
              f"std(dQ)={rec['dq_std']:5.2f}  match={rec['sector_match']:.3f}  "
              f"<Q^2>/exact={rec['q_squared_over_exact']:6.2f}  || "
              f"plaq rel={rec['plaq_rel_err']:+.2e}  "
              f"sigma/exact={rec['plaq_sigma_over_exact']:5.2f}  "
              f"W4x4 rel={rec['loops']['wilson_4x4']['rel_err']:+.2e}  "
              f"[{rec['seconds']:.0f}s]", flush=True)

    save_json(out_dir / "consistency_weight_scan.json",
              {"lattice_size": size, "beta": beta, "n_configs": int(coarse.shape[0]),
               "exact_plaquette": exact_plaq, "exact_sigma_1config": sigma_exact,
               "exact_q_squared": exact_q2, "rows": rows})

    print("\n## Topology (charge projection OFF throughout)\n")
    print("| weight | coherent resid | incoherent resid | defects/cfg | "
          "sum/2pi std | std(dQ) | sector match | <Q^2>/exact |")
    print("|---|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['consistency_weight']:g} | {r['resid_coherent_mean']:.5f} | "
              f"{r['resid_incoherent_std']:.4f} | "
              f"{r['defects_per_config']:.2f} | "
              f"{r['sum_resid_over_2pi_std']:.2f} | "
              f"{r['dq_std']:.2f} | {r['sector_match']:.3f} | "
              f"{r['q_squared_over_exact']:.2f} |")

    print("\n## Local physics -- the half that catches a `physics_blend_coef`\n")
    print("| weight | plaq rel err | sigma/exact (1.0 correct) | W2x2 rel | W4x4 rel |")
    print("|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['consistency_weight']:g} | {r['plaq_rel_err']:+.2e} | "
              f"{r['plaq_sigma_over_exact']:.2f} | "
              f"{r['loops']['wilson_2x2']['rel_err']:+.2e} | "
              f"{r['loops']['wilson_4x4']['rel_err']:+.2e} |")
    print("\nRead BOTH tables. A weight that fixes topology while driving "
          "sigma/exact away from 1.0 is turning the model into `flux`, which "
          "has perfect Q and unusable local structure.")
    print(f"\nwrote {(out_dir / 'consistency_weight_scan.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
