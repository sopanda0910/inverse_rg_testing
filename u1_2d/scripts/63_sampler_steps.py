"""The reverse-diffusion step count as a cost/accuracy dial.

The u1 counterpart of `u2_2d/scripts/14_sampler_steps.py`, closing the last
measurement gap in `docs/PARITY_U1_U2.md` section 2. u1 fixes 200 sampler steps
everywhere and has never measured what that buys; u2 measured that 25 steps is
about 3x cheaper at ~2.7x the extended-loop error, and that below 18 steps the
lift collapses. If u1 has a similar knee, the deployed setting is leaving a
factor of several on the table and the paper should say so.

THE SAMPLER MUST BE THE DEPLOYED ONE. The first version of this script called
`generate_fine_from_coarse` with its bare defaults, and those are NOT what the
pipeline runs: `v3_scale.yaml` sets `physics_blend_coef: 1.0`,
`physics_blend_beta_min: 5.0`, `sigma_min_beta_coef: 0.1` and
`charge_projection_*`, while the function defaults blend off
(`physics_blend_coef = 0.0`) and `03_run_ladder.py` rebuilds the noise schedule
with the beta-aware sigma floor before sampling. So the scan measured an
UNBLENDED sampler and its knee did not describe the deployed one -- verified end
to end: running the real ladder at the 18 steps that scan recommended left the
delivered ensemble fine (max |z| 2.07 -> 1.42, 1.74 -> 2.18, 1.28 -> 1.64 at the
three rungs) but degraded the RAW lift by 3-4x at every rung (top rung max |z|
12.3 -> 53.1). The blend and the step count interact, and a scan that omits the
blend cannot see it. Every knob is now read from the config.

WHAT IS MEASURED, at each step count, on the SAME coarse ensemble and the same
seed, so the arms differ only in the sampler:

  * wall-clock seconds for the lift,
  * |z| against the closed form for the RAW lift, and
  * |z| after the deployed rethermalization sweeps.

BOTH COLUMNS ARE CRITERIA, FOR DIFFERENT PRODUCTS, and that is the correction
the end-to-end check forced. The POST column scores the DELIVERED ensemble; the
RAW column scores the SEED, which is what the paper's seed-quality claims
(t_therm, N*, the prolongator ablation) are measured on. A step count that is
free on one can be expensive on the other, so the knee is reported for each and
the script no longer prints a single answer.

The second and third are both needed, and MEASUREMENT OVERTURNED THE EXPECTATION
HERE. The u2 study warned that tuning on the post-tail number picks a bad
setting; in u1 it is the RAW column that cannot be used. At beta_f = 55.02 the
raw bias changes SIGN between 12 and 18 steps (-13.5 -> +9.4), so raw |z| passes
through a cancellation and a raw-scored knee lands on it; at beta_f = 218.58 raw
|z| GROWS with step count (38.5 at 12 to 126 at 200), which would rank the
cheapest setting best. The deliverable is the post-tail ensemble, so the knee is
scored there, and the raw column is kept as a diagnostic rather than a
criterion.

Errors are tau_int-aware (NARRATIVE 25.7 / M4), and the z is the statistic of
record rather than a relative deviation, for the reason in section 5 item 4 of
the parity document.

    python u1_2d/scripts/63_sampler_steps.py --device cuda
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

from u1_2d.lgt import make_action, run_hmc_ensemble
from u1_2d.lgt.blocking import approx_matched_fine_beta
from u1_2d.lgt.exact import wilson_loop_exact
from u1_2d.lgt.hmc import adapted_hmc_params
from u1_2d.lgt.lattice import (plaquette_angles, topological_charge,
                               wilson_loop_angles)
from u1_2d.lgt.local_updates import retherm_sweeps
from u1_2d.model.schedule import GeometricNoiseSchedule
from u1_2d.model.train import load_checkpoint
from u1_2d.pipeline.ladder import generate_fine_from_coarse
from u1_2d.utils import load_config, save_json, set_seed
from u1_2d.validate.stats import autocorr_aware_mean_err

LOOPS = [(1, 1), (2, 2), (4, 4), (6, 6)]


def score(field, beta, size, n_chains):
    out = {}
    with torch.no_grad():
        for nx, ny in LOOPS:
            ang = (plaquette_angles(field) if (nx, ny) == (1, 1)
                   else wilson_loop_angles(field, nx, ny))
            v = torch.cos(ang).mean(dim=(-2, -1)).cpu().numpy().astype(float)
            exact = wilson_loop_exact(beta, nx * ny, "wilson", size)
            mean, err, _ = autocorr_aware_mean_err(v, n_chains)
            out[f"z_W{nx}x{ny}"] = float((mean - exact) / max(err, 1e-15))
        q = topological_charge(field).cpu().numpy().astype(float)
    out["q_squared"] = float((q ** 2).mean())
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="u1_2d/configs/v3_scale.yaml",
                    help="the sampler knobs are read from this config's "
                         "`ladder` block, so the scan matches deployment")
    ap.add_argument("--checkpoint", default=None)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--coarse-size", type=int, default=16)
    ap.add_argument("--coarse-betas", default="14.1464,55.0237")
    ap.add_argument("--steps", default="8,12,18,25,40,60,100,200")
    ap.add_argument("--n-configs", type=int, default=128)
    ap.add_argument("--n-chains", type=int, default=16)
    ap.add_argument("--burn-in", type=int, default=600)
    ap.add_argument("--thin", type=int, default=5)
    ap.add_argument("--retherm", type=int, default=None)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--out-dir", default="out/u1_2d/sampler_steps")
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Every sampler knob comes from the deployed config. Reading them here rather
    # than restating them is the whole point: a scan that drifts from the
    # pipeline measures a sampler nobody runs.
    cfg = load_config(args.config)
    lad = cfg["ladder"]
    checkpoint = args.checkpoint or cfg["train"]["checkpoint"]
    if args.retherm is None:
        args.retherm = int(lad["n_retherm_sweeps"])
    model, schedule = load_checkpoint(checkpoint, args.device)
    floor = lad.get("sigma_min_beta_coef")
    if floor is not None:
        schedule = GeometricNoiseSchedule(
            schedule.sigma_min, schedule.sigma_max,
            sigma_min_beta_coef=float(floor))
    sampler_kw = dict(
        n_corrector_steps=int(lad.get("n_corrector_steps", 1)),
        consistency_weight=float(lad.get("consistency_weight", 1.0)),
        enforce_coarse_charge=bool(lad.get("enforce_coarse_charge", True)),
        charge_projection_sigma=float(lad.get("charge_projection_sigma", 0.5)),
        charge_projection_interval=int(lad.get("charge_projection_interval", 10)),
        physics_blend_coef=float(lad.get("physics_blend_coef", 0.0)),
        physics_blend_beta_min=float(lad.get("physics_blend_beta_min", 0.0)),
        corrector_snr=float(lad.get("corrector_snr", 0.16)),
    )
    print(f"checkpoint {checkpoint}")
    print(f"retherm {args.retherm} sweeps, sigma_min_beta_coef {floor}, "
          + ", ".join(f"{k}={v}" for k, v in sampler_kw.items()))
    steps = [int(x) for x in args.steps.split(",")]
    rows = []

    for cb in [float(b) for b in args.coarse_betas.split(",")]:
        beta = approx_matched_fine_beta(cb, "wilson")
        size = args.coarse_size * 2
        set_seed(args.seed)
        action_c = make_action("wilson", cb)
        step_c, nst_c = adapted_hmc_params(cb)
        coarse, _ = run_hmc_ensemble(
            args.coarse_size, action_c, n_configs=args.n_configs,
            n_chains=args.n_chains, burn_in=args.burn_in, thin=args.thin,
            step_size=step_c, n_steps=nst_c, device=args.device,
            topological_updates=True)
        coarse = coarse.cpu()
        action_f = make_action("wilson", beta)
        print(f"\n{'='*78}\ncoarse beta={cb:g} -> fine beta={beta:.3f}, L={size}, "
              f"{coarse.shape[0]} configs")
        print(f"  {'steps':>6s} {'sec':>7s} "
              + "".join(f"raw z W{a}x{a}".rjust(13) for a, _ in LOOPS)
              + "".join(f"+10 z W{a}x{a}".rjust(13) for a, _ in LOOPS))
        for ns in steps:
            # SAME seed for every step count: the arms then share the coarse
            # ensemble AND the noise draw, so a difference is the sampler.
            set_seed(args.seed + 1)
            t0 = time.time()
            fine = generate_fine_from_coarse(
                model, schedule, coarse, beta, device=args.device,
                n_sampler_steps=ns, batch_size=64, **sampler_kw)
            secs = time.time() - t0
            raw = score(fine, beta, size, args.n_chains)
            post = score(retherm_sweeps(fine, action_f, args.retherm),
                         beta, size, args.n_chains)
            rows.append({"coarse_beta": cb, "beta": beta, "lattice_size": size,
                         "n_sampler_steps": ns, "seconds": secs,
                         "raw": raw, "post": post})
            save_json(out / "sampler_steps.json", rows)
            print(f"  {ns:6d} {secs:7.1f} "
                  + "".join(f"{raw[f'z_W{a}x{a}']:+13.2f}" for a, _ in LOOPS)
                  + "".join(f"{post[f'z_W{a}x{a}']:+13.2f}" for a, _ in LOOPS))

    # ---- where is the knee? -------------------------------------------------
    # TWO KNEES, NOT ONE. The POST column scores the DELIVERED ensemble and the
    # RAW column scores the SEED, and the paper sells both -- the delivered
    # ensemble in the validation tables, the seed in every t_therm and N* claim.
    # An end-to-end run at the post-scored knee (18 steps) reproduced the
    # delivered ensemble and degraded the raw lift 3-4x, so collapsing the two
    # into one recommendation is how that got missed. Both are printed and
    # neither is called "the" knee.
    #
    # The raw column is still a poor CRITERION on its own, for the reason the
    # docstring gives -- its bias can change sign with step count, so a
    # raw-scored minimum can sit on a cancellation. Read it as a floor: a step
    # count whose raw |z| is far above the reference's is degrading the seed
    # whatever the post column says.
    print("\n" + "=" * 78)
    print("KNEE, reported separately for the two products")
    worst_post = lambda r: max(abs(r["post"][f"z_W{a}x{a}"]) for a, _ in LOOPS)
    worst_raw = lambda r: max(abs(r["raw"][f"z_W{a}x{a}"]) for a, _ in LOOPS)
    for cb in sorted({r["coarse_beta"] for r in rows}):
        sub = sorted([r for r in rows if r["coarse_beta"] == cb],
                     key=lambda r: r["n_sampler_steps"])
        ref = sub[-1]
        print(f"\n  coarse beta={cb:g} -> fine {ref['beta']:.2f}: reference "
              f"{ref['n_sampler_steps']} steps, post worst |z| "
              f"{worst_post(ref):.2f}, raw worst |z| {worst_raw(ref):.2f}, "
              f"{ref['seconds']:.1f}s")
        print(f"    {'steps':>6} {'post |z|':>9} {'x ref':>7} {'raw |z|':>9} "
              f"{'x ref':>7} {'cheaper':>8}")
        for r in sub:
            print(f"    {r['n_sampler_steps']:6d} {worst_post(r):9.2f} "
                  f"{worst_post(r)/max(worst_post(ref),1e-9):7.2f} "
                  f"{worst_raw(r):9.2f} "
                  f"{worst_raw(r)/max(worst_raw(ref),1e-9):7.2f} "
                  f"{ref['seconds']/max(r['seconds'],1e-9):7.1f}x")
        for label, fn in (("DELIVERED ensemble", worst_post),
                          ("SEED (raw lift)", worst_raw)):
            ok = [r for r in sub if fn(r) <= 1.10 * fn(ref)]
            if ok:
                k = ok[0]
                print(f"    -> knee for the {label}: {k['n_sampler_steps']} "
                      f"steps, {ref['seconds']/max(k['seconds'],1e-9):.1f}x "
                      f"cheaper (within 10% of {ref['n_sampler_steps']})")
            else:
                print(f"    -> no knee for the {label}: no step count below "
                      f"{ref['n_sampler_steps']} stays within 10%")
    print("\n  Adopt the SMALLER of the two knees, or keep the two uses on"
          "\n  different settings and say so. The delivered-ensemble knee alone"
          "\n  is not a licence to move the deployed config.")
    print(f"\nwrote {out / 'sampler_steps.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
