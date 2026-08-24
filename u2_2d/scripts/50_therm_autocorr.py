"""Thermalization AND autocorrelation, per starting point, scored honestly.

Opened 2026-08-24. `17_prolongator_baseline.py` compares starting points on
`t_therm` alone, and two things found the same day say that is not enough.

**1. `t_therm` has a resolution floor.** Calibrated against synthetic series
drawn under the null -- correct mean, correct errors, AR(1) autocorrelation --
at this study's own 64-chain shape (`u1_2d/scripts/65_therm_criterion_calibration.py`,
results in `out/u2_2d/therm_calibration/`): a PERFECTLY thermalized ensemble
reports `t_therm = 0` only 78-85% of the time, with a 90th percentile of
**3-4**. So `t_therm <= 4` is consistent with "already at equilibrium" and
differences inside that band are not measurements. NARRATIVE's headline
prolongator claim -- `diffusion_tuned` thermalizing in "0-1 trajectories
against 5-6" for `smear` -- sits almost entirely inside that band. Its
companion claim, the TUNED SWEEP COUNT (5 against 35 and 15), is not a
`t_therm` and is unaffected; that is the half that survives.

**2. `t_therm` divides by the arm's OWN measured spread, so an arm with the
wrong spread gets the wrong score.** Measured in u1 the same day
(`u1_2d/scripts/66_prolongator_dispersion.py`): against the exact
per-configuration sigma, `ape` is OVER-dispersed by 1.8-5.1x and the purely
geometric maps by up to 310x. An inflated spread inflates the SEM, which
SHRINKS |z| -- so an arm can pass the criterion by having error bars that are
too wide. At beta_f = 14.15 `ape` reached t_therm = 136 while sitting at
|z| = 23.4 against the exact sigma, where `smear` sat at 0.23.

This script therefore reports three things per arm rather than one:

  * `t_therm`, with the calibrated floor printed beside it;
  * the DISPERSION ratio -- across-chain sigma at t = 0 divided by the same
    arm's own equilibrated-tail sigma, plus, for the plaquette, a check of that
    tail sigma against the EXACT per-configuration sigma from the free energy
    (log Z''(beta) = Var(sum of plaquettes), so
    sigma_1config(mean plaq) = sqrt(P'(beta) / V));
  * `tau_int` on the equilibrated tail, for every observable and for Q^2 --
    the "interval time" between independent configurations, which is the metric
    the flow and winding-HMC literature reports and which this study has only
    ever measured for the cost calculation.

**Read tau_int(Q^2) with the standing warning.** CLAUDE.md records that it
reports HEALTHY on a parity-frozen chain: the joint move shuffles Q by +-2
quickly inside one parity class, so Q^2 decorrelates in 0.55 draws while the
chain never crosses the monodromy. Parity flips are counted here alongside it
for exactly that reason -- a small tau_int(Q^2) with zero flips is a frozen
chain, not a fast one.

    .venv/Scripts/python.exe u2_2d/scripts/50_therm_autocorr.py \
        --arms diffusion_raw diffusion_tuned smear ape flux cold \
        --n-traj 2000 --winding
"""

import argparse
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from u2_2d.lgt.exact import plaquette_exact, wilson_loop_exact
from u2_2d.lgt.hmc import BatchedHMCU2, adapted_hmc_params
from u2_2d.lgt.actions import WilsonU2Action
from u2_2d.utils import load_config, resolve_device, save_json, set_seed

# The floor measured by u1_2d/scripts/65_therm_criterion_calibration.py at this
# study's 64-chain shape. Printed beside every t_therm so the reader cannot
# quote a difference that the metric cannot resolve.
T_THERM_FLOOR_P90 = 4.0


def _load_17():
    spec = importlib.util.spec_from_file_location(
        "prolong17", REPO / "u2_2d" / "scripts" / "17_prolongator_baseline.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["prolong17"] = mod
    spec.loader.exec_module(mod)
    return mod


def tau_int(series: np.ndarray, c: float = 5.0, tail: float = 0.5) -> float:
    """Madras-Sokal tau_int with automatic windowing, on the equilibrated tail.

    series is [n_steps, n_chains]; each chain is a replica, so the
    autocorrelation is estimated per chain and averaged. Returns tau in units
    of the recorded step (one trajectory here, since `run_arm` records every
    trajectory).
    """
    start = int(len(series) * (1.0 - tail))
    window = series[start:]
    n = len(window)
    if n < 16:
        return float("nan")
    taus = []
    n_constant = 0
    for b in range(window.shape[1]):
        x = window[:, b].astype(float)
        x = x - x.mean()
        var = float((x * x).mean())
        if var <= 0 or not np.isfinite(var):
            # A chain whose series never moves has not decorrelated at all.
            # Dropping it silently is what makes a frozen chain report a small
            # tau_int -- the exact failure mode CLAUDE.md warns about for
            # tau_int(Q^2). Count it and return inf if every chain is stuck.
            n_constant += 1
            continue
        # normalized autocorrelation via FFT
        f = np.fft.rfft(x, n=2 * n)
        acf = np.fft.irfft(f * np.conjugate(f))[:n].real
        acf /= acf[0]
        t = 0.5
        for w in range(1, n):
            t += acf[w]
            if w >= c * t:
                break
        taus.append(max(t, 0.5))
    if not taus:
        return float("inf")
    return float(np.mean(taus))


def _j(x):
    """inf/nan -> None, so the JSON stays valid for readers outside Python."""
    return None if x is None or not np.isfinite(x) else float(x)


def _fmt(x, width=6, prec=2):
    """Format a tau that may be None.

    `_j` maps a non-finite tau to None so the JSON stays valid, and a
    NEVER-DECORRELATING chain is exactly the case this study cares about -- a
    frozen Q^2 under no winding move. Formatting None with `:6.2f` crashed the
    whole no-winding round on its first arm, which is the scientifically
    interesting arm. Print it as `inf`, do not drop it.
    """
    return f"{'inf':>{width}}" if x is None else f"{x:{width}.{prec}f}"


def exact_sigma_1config_plaquette(beta: float, size: int, h: float = 1e-3) -> float:
    """Exact per-configuration std of the mean plaquette, from the free energy.

    S = -beta * sum_p (1/2)ReTr P, so d logZ/d beta = V * <plaq> and
    d^2 logZ/d beta^2 = Var(sum_p plaq) = V^2 * Var(mean plaq).
    """
    dp = (plaquette_exact(beta + h * beta, size)
          - plaquette_exact(beta - h * beta, size)) / (2.0 * h * beta)
    return math.sqrt(max(dp, 0.0) / (size * size))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", default="u2_2d/configs/default.yaml")
    p.add_argument("--device", default=None)
    p.add_argument("--out-dir", default="out/u2_2d/therm_autocorr")
    p.add_argument("--n-traj", type=int, default=2000,
                   help="long, because tau_int needs a tail; t_therm needs only O(10)")
    p.add_argument("--n-chains", type=int, default=64)
    p.add_argument("--rung", type=int, default=-1)
    p.add_argument("--checkpoint", default=None)
    p.add_argument("--n-su2", type=int, default=None)
    p.add_argument("--n-retherm", type=int, default=None)
    p.add_argument("--arms", nargs="+",
                   default=["diffusion_raw", "diffusion_tuned", "smear", "ape",
                            "flux", "cold"])
    p.add_argument("--winding", action="store_true",
                   help="give the HMC the marginal odd winding move -- the "
                        "honest classical baseline. Off reproduces 17's sampler.")
    p.add_argument("--charge-step", type=int, default=1)
    p.add_argument("--winding-interval", type=int, default=5)
    p.add_argument("--tail", type=float, default=0.5)
    args = p.parse_args()

    m17 = _load_17()
    config = load_config(args.config)
    if args.device:
        config["device"] = args.device
    device = resolve_device(config)
    set_seed(int(config.get("seed", 0)))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Rung selection mirrors 17's, and the ARMS are built with 17's own helper
    # functions rather than reimplemented -- building them a second way is how
    # two scripts end up disagreeing about the same arm.
    from u2_2d.utils import ensemble_path, load_ensemble

    ladder_cfg = config["ladder"]
    base = ladder_cfg["base"]
    schedule = [float(b) for b in ladder_cfg["beta_schedule"]]
    sizes = [int(base["lattice_size"]) * 2 ** (i + 1) for i in range(len(schedule))]
    rung = args.rung if args.rung >= 0 else len(schedule) - 1
    beta, size = schedule[rung], sizes[rung]
    ladder_dir = Path(ladder_cfg.get("out_dir", "out/u2_2d/ladder"))

    if rung == 0:
        coarse_path = ensemble_path(config["data"]["out_dir"],
                                    int(base["lattice_size"]), float(base["beta"]))
    else:
        coarse_path = ensemble_path(ladder_dir, sizes[rung - 1], schedule[rung - 1],
                                    tag="ladder")
    fine_path = ensemble_path(ladder_dir, size, beta, tag="ladder")
    for pth in (coarse_path, fine_path):
        if not pth.exists():
            print(f"missing {pth} -- run stage 03 first")
            return 1
    coarse, _ = load_ensemble(coarse_path)
    generated, _ = load_ensemble(fine_path)
    n_chains = min(args.n_chains, coarse.shape[0], generated.shape[0])
    coarse, generated = coarse[:n_chains], generated[:n_chains]

    n_su2 = int(args.n_su2 if args.n_su2 is not None
                else ladder_cfg.get("n_su2_sweeps", 30))
    # 0 by default here, NOT the ladder's 10: ten rethermalization sweeps
    # equilibrate local structure from almost any start, which saturates
    # t_therm at 0 for every arm and destroys the resolution of the comparison.
    # 17's docstring records the same trap.
    n_retherm = int(args.n_retherm if args.n_retherm is not None else 0)

    action = WilsonU2Action(beta)
    step_size, n_steps = adapted_hmc_params(beta)
    sampler = BatchedHMCU2(
        size, action, n_chains=n_chains, n_steps=n_steps,
        step_size=step_size, device=device,
        topological_updates=bool(args.winding),
        winding_charge_step=args.charge_step,
        winding_interval=args.winding_interval)

    print(f"rung {rung}: L={size} beta={beta:g}  n_traj={args.n_traj}  "
          f"chains={n_chains}  winding={bool(args.winding)}  "
          f"n_su2={n_su2}  n_retherm={n_retherm}", flush=True)

    psi_coarse = m17.det_links(coarse)
    starts, smear_count, lift_cache = {}, {}, {}
    for name in args.arms:
        if name == "diffusion":
            starts[name] = generated
        elif name in ("diffusion_raw", "diffusion_tuned"):
            if "fine" not in lift_cache:
                from u2_2d.model.det_lift import load_det_model
                from u2_2d.pipeline.ladder import generate_fine_from_coarse
                ckpt = args.checkpoint or config["train"].get(
                    "checkpoint_path", "out/u2_2d/checkpoints/det_score_net.pt")
                if not Path(ckpt).exists():
                    print(f"  missing checkpoint {ckpt}, skipping {name}")
                    continue
                model, sched = load_det_model(ckpt, device=device)
                fine = generate_fine_from_coarse(
                    model, sched, coarse, beta, n_su2_sweeps=n_su2, device=device,
                    n_sampler_steps=int(ladder_cfg.get("n_sampler_steps", 200)),
                    n_corrector_steps=int(ladder_cfg.get("n_corrector_steps", 1)),
                    batch_size=int(ladder_cfg.get("batch_size", 64)),
                    consistency_weight=float(ladder_cfg.get("consistency_weight", 1.0)),
                    physics_blend_coef=float(ladder_cfg.get("physics_blend_coef", 0.0)),
                )
                if n_retherm:
                    with torch.no_grad():
                        fine = m17.retherm_sweeps(fine.to(device), action,
                                                  n_retherm, topological_updates=False)
                lift_cache["fine"] = fine.cpu()
            if name == "diffusion_raw":
                starts[name] = lift_cache["fine"]
            else:
                tuned, count, secs = m17.tune_smear(lift_cache["fine"], beta, device)
                starts[name], smear_count[name] = tuned, count
                print(f"  diffusion_tuned: {count} tuned sweeps ({secs:.0f}s)", flush=True)
        elif name in m17.GEOMETRIC:
            starts[name], _ = m17.assemble(m17.GEOMETRIC[name](psi_coarse), coarse,
                                           beta, n_su2, n_retherm, device)
        elif name == "ape":
            starts[name], _ = m17.assemble(m17.ape_for(beta)(psi_coarse), coarse,
                                           beta, n_su2, n_retherm, device)
        elif name == "smear":
            fine, _ = m17.assemble(m17.flux(psi_coarse), coarse, beta, n_su2, 0, device)
            smeared, count, secs = m17.tune_smear(fine, beta, device)
            starts[name], smear_count[name] = smeared, count
            print(f"  smear: {count} tuned sweeps ({secs:.0f}s)", flush=True)
        elif name == "cold":
            starts[name] = sampler.initialize(hot=False).cpu()
        elif name == "hot":
            starts[name] = sampler.initialize(hot=True).cpu()
        else:
            print(f"  unknown arm {name}, skipping")

    exact = {n: (plaquette_exact(beta, size) if n == "plaquette"
                 else wilson_loop_exact(beta, a * b))
             for n, (a, b) in m17.LOOPS.items() if a < size or n == "plaquette"}
    sigma_exact_plaq = exact_sigma_1config_plaquette(beta, size)

    rows = []
    for name, start in starts.items():
        arm = m17.run_arm(name, sampler, start, args.n_traj, size)
        q = arm["charge"]
        q2 = (q.astype(float)) ** 2
        parity = (np.abs(q.astype(int)) % 2)
        flips = int((np.diff(parity, axis=0) != 0).sum())
        tail0 = int(len(q) * (1.0 - args.tail))

        rec = {"arm": name, "tuned_sweeps": smear_count.get(name),
               "seconds": arm["seconds"], "parity_flips": flips,
               "tau_int_q_squared": _j(tau_int(q2, tail=args.tail)),
               "mean_q_squared_tail": float(q2[tail0:].mean()),
               "observables": {}}
        for k, series in arm["series"].items():
            t_th = m17.thermalization_time(series, exact[k])
            sig0 = float(series[0].std(ddof=1))
            sig_tail = float(series[tail0:].std(ddof=1))
            rec["observables"][k] = {
                "t_therm": None if math.isinf(t_th) else t_th,
                "tau_int": _j(tau_int(series, tail=args.tail)),
                "sigma_t0": sig0,
                "sigma_tail": sig_tail,
                "dispersion_ratio_t0_over_tail": sig0 / sig_tail if sig_tail else None,
                "rel_err_t0": (float(series[0].mean()) - exact[k]) / abs(exact[k]),
                "rel_err_tail": (float(series[tail0:].mean()) - exact[k]) / abs(exact[k]),
            }
        if "plaquette" in rec["observables"]:
            rec["observables"]["plaquette"]["sigma_tail_over_exact"] = (
                rec["observables"]["plaquette"]["sigma_tail"] / sigma_exact_plaq)
            rec["observables"]["plaquette"]["sigma_t0_over_exact"] = (
                rec["observables"]["plaquette"]["sigma_t0"] / sigma_exact_plaq)
        rows.append(rec)

        o = rec["observables"]["plaquette"]
        tt = "> %d" % args.n_traj if o["t_therm"] is None else "%g" % o["t_therm"]
        print(f"  {name:<16} t_therm(plaq)={tt:<7} "
              f"tau_int(plaq)={_fmt(o['tau_int'])}  "
              f"sigma(t0)/exact={o['sigma_t0_over_exact']:7.2f}  "
              f"sigma(tail)/exact={o['sigma_tail_over_exact']:5.2f}  "
              f"tau_int(Q^2)={_fmt(rec['tau_int_q_squared'])}  "
              f"flips={flips}", flush=True)

    payload = {"config": vars(args), "lattice_size": size, "beta": beta,
               "exact": exact, "exact_sigma_1config_plaquette": sigma_exact_plaq,
               "t_therm_floor_p90": T_THERM_FLOOR_P90, "rows": rows}
    save_json(out_dir / "therm_autocorr.json", payload)

    obs_names = [k for k in m17.LOOPS if k in rows[0]["observables"]]
    print(f"\n## tau_int by observable (trajectories), tail {args.tail:.0%}\n")
    print("| arm | " + " | ".join(obs_names) + " | Q^2 | parity flips |")
    print("|---|" + "---|" * (len(obs_names) + 2))
    for r in rows:
        cells = [_fmt(r['observables'][k]['tau_int'], 0) for k in obs_names]
        print(f"| {r['arm']} | " + " | ".join(cells)
              + f" | {_fmt(r['tau_int_q_squared'], 0)} | {r['parity_flips']} |")

    print(f"\n## t_therm (floor: differences below ~{T_THERM_FLOOR_P90:g} "
          f"are not resolved)\n")
    print("| arm | " + " | ".join(obs_names) + " | tuned sweeps |")
    print("|---|" + "---|" * (len(obs_names) + 1))
    for r in rows:
        cells = []
        for k in obs_names:
            v = r["observables"][k]["t_therm"]
            cells.append(f"> {args.n_traj}" if v is None else f"{v:g}")
        sw = r["tuned_sweeps"]
        print(f"| {r['arm']} | " + " | ".join(cells)
              + f" | {'--' if sw is None else sw} |")

    print("\n## dispersion: sigma(t=0) / sigma(equilibrated tail) -- 1.0 is correct\n")
    print("| arm | " + " | ".join(obs_names) + " |")
    print("|---|" + "---|" * len(obs_names))
    for r in rows:
        cells = [f"{r['observables'][k]['dispersion_ratio_t0_over_tail']:.2f}"
                 for k in obs_names]
        print(f"| {r['arm']} | " + " | ".join(cells) + " |")
    print("\nA ratio far from 1 means the arm's starting ensemble has the wrong "
          "width, so the SEM that `t_therm` divides by is wrong and its score is "
          "not comparable to an arm with the right width.")
    print(f"\nwrote {(out_dir / 'therm_autocorr.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
