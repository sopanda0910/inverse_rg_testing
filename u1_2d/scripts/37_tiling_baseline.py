"""The warm-start baseline the referee asks for (NARRATIVE sec 25, experiment 3).

The headline claim is that an HMC chain started from a diffusion sample
thermalizes far faster than one started fresh. Fresh hot/cold starts are the
wrong control for part of that: they throw away the coarse configuration
entirely, while the diffusion seed is handed it. Some of the measured speedup
could therefore be bought by ANY map from coarse to fine, with no model in it
at all. That has never been tested here.

Three non-learned prolongators, all given exactly the same coarse ensemble the
model gets, then measured with 05's own t_therm criterion so the numbers drop
straight into the same table:

  tile      -- replicate the coarse L_c configuration 2x2 to fill the fine
               lattice. The naive baseline named in sec 25. It is NOT
               blocking-consistent and its plaquettes are distributed like the
               COARSE theory (beta_c = beta_f / 4), i.e. four times too
               disordered.

  halve     -- the exact deterministic inverse of the blocking rule
               Theta_x(X,Y) = theta_x(2X,2Y) + theta_x(2X+1,2Y): split each
               coarse link evenly over the two fine links it was built from,
               and set the links blocking never reads to zero. Blocking-
               consistent by construction, so it carries the coarse sector
               exactly, but it is locally cold -- every plaquette inside a
               2x2 cell that blocking does not constrain is set to zero.

  flux      -- blocking-consistent AND flux-spreading: as `halve`, but the
               unread links are chosen so the coarse plaquette angle is shared
               evenly over the four fine plaquettes of its cell instead of
               piled onto one. This is the strongest prolongator available
               without learning anything, and is the honest competitor.

If the model's seed is not much better than `flux`, the learned part of this
pipeline is doing less than the headline implies.

    .venv/Scripts/python.exe u1_2d/scripts/37_tiling_baseline.py \
        --cases 32:14.1464 32:55.0237 --n-configs 64
"""

import argparse
import importlib.util
import json
import math
import time
from pathlib import Path

import numpy as np
import torch

from u1_2d.lgt import make_action
from u1_2d.lgt.blocking import block_links
from u1_2d.lgt.hmc import adapted_hmc_params
from u1_2d.lgt.lattice import plaquette_angles, wrap
from u1_2d.lgt.local_updates import retherm_sweeps
from u1_2d.utils import load_config, load_ensemble, resolve_device, save_json

REPO = Path(__file__).resolve().parents[2]


def _load_05():
    spec = importlib.util.spec_from_file_location(
        "therm05", REPO / "u1_2d" / "scripts" / "05_hmc_thermalization.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def tile(coarse: torch.Tensor) -> torch.Tensor:
    """[B,2,Lc,Lc] -> [B,2,2Lc,2Lc] by periodic 2x2 replication."""
    return coarse.repeat(1, 1, 2, 2).clone()


def halve(coarse: torch.Tensor) -> torch.Tensor:
    """Exact inverse of block_links, cold in the unconstrained links."""
    b, _, lc, _ = coarse.shape
    fine = torch.zeros(b, 2, 2 * lc, 2 * lc, dtype=coarse.dtype, device=coarse.device)
    half = wrap(coarse) / 2.0
    # x-links: even rows carry half the coarse x-link, twice along the path.
    fine[:, 0, 0::2, 0::2] = half[:, 0]
    fine[:, 0, 1::2, 0::2] = half[:, 0]
    # y-links: even columns, same construction along y.
    fine[:, 1, 0::2, 0::2] = half[:, 1]
    fine[:, 1, 0::2, 1::2] = half[:, 1]
    return wrap(fine)


def flux(coarse: torch.Tensor) -> torch.Tensor:
    """Blocking-consistent, with the cell's coarse flux spread over its four
    fine plaquettes instead of concentrated.

    Starting from `halve`, the whole coarse plaquette angle sits on one fine
    plaquette of the cell and the other three are zero. Adding a constant to
    the interior x-links of a cell moves flux between its plaquettes without
    touching any link that blocking reads, so a single shift per cell
    equalizes them.
    """
    from u1_2d.lgt.lattice import plaquette_angles

    fine = halve(coarse)
    with torch.no_grad():
        cell = plaquette_angles(fine)
        # Cell total is the coarse plaquette angle (telescoping, guaranteed by
        # the blocking consistency of `halve`); each fine plaquette should
        # carry a quarter of it.
        want = (cell[:, 0::2, 0::2] + cell[:, 1::2, 0::2]
                + cell[:, 0::2, 1::2] + cell[:, 1::2, 1::2]) / 4.0
        # p(x,y) = ux(x,y) + uy(x+1,y) - ux(x,y+1) - uy(x,y). Raising the
        # x-link at odd y by d subtracts d from the plaquette below it and adds
        # d to the one above, both inside the same cell. Blocking never reads
        # odd-y x-links, so the coarse configuration is untouched.
        fine[:, 0, 0::2, 1::2] += cell[:, 0::2, 0::2] - want
        fine[:, 0, 1::2, 1::2] += cell[:, 1::2, 0::2] - want
        # That fixes the lower two plaquettes; the upper two now sum to 2*want
        # but are not individually equal. The y-link at odd x is likewise
        # unread by blocking and moves flux between them.
        cell = plaquette_angles(fine)
        fine[:, 1, 1::2, 1::2] += want - cell[:, 0::2, 1::2]
    return wrap(fine)


def _staples(theta: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Forward and backward staple angles for both link directions.

    With p(x,y) = ux(x,y) + uy(x+1,y) - ux(x,y+1) - uy(x,y), the staple is the
    three-link path that closes the plaquette with the link itself, so
    link + staple = plaquette angle for the forward case.
    """
    ux, uy = theta[:, 0], theta[:, 1]
    # x-links, perpendicular direction y
    fx = uy + ux.roll(-1, dims=-1) - uy.roll(-1, dims=-2)
    bx = (-uy.roll(1, dims=-1) + ux.roll(1, dims=-1)
          + uy.roll(-1, dims=-2).roll(1, dims=-1))
    # y-links, perpendicular direction x
    fy = ux + uy.roll(-1, dims=-2) - ux.roll(-1, dims=-1)
    by = (-ux.roll(1, dims=-2) + uy.roll(1, dims=-2)
          + ux.roll(1, dims=-2).roll(-1, dims=-1))
    return torch.stack([fx, fy], dim=1), torch.stack([bx, by], dim=1)


def ape_smear(theta: torch.Tensor, alpha: float = 0.5, n_iter: int = 20) -> torch.Tensor:
    """APE smearing for U(1): blend each link with its staples and project back
    onto the group by taking the angle of the complex sum.

    U(1) makes the projection trivial (normalize a complex number), which is
    why this is the natural stand-in for the SU(N) APE/HYP smearing used as
    the interpolation kernel in Endres-style multiscale thermalization.
    """
    out = wrap(theta)
    for _ in range(n_iter):
        fwd, bwd = _staples(out)
        z = ((1.0 - alpha) * torch.exp(1j * out)
             + (alpha / 2.0) * (torch.exp(1j * fwd) + torch.exp(1j * bwd)))
        out = torch.angle(z)
    return wrap(out)


def ape(coarse: torch.Tensor, target_plaquette: float | None = None) -> torch.Tensor:
    """Endres-style classical interpolation: prolongate, then smooth.

    The comparison the referee asks for (NARRATIVE sec 25, implied experiment
    2). Multiscale thermalization prolongs a coarse configuration with a
    smoothed/APE interpolation kernel rather than a learned one; this is that
    kernel applied to the best deterministic prolongator available here.
    Smearing deliberately breaks blocking consistency -- it is not required to
    preserve the coarse configuration, only to be a good starting point.

    The smearing count is CHOSEN TO MATCH THE TARGET, not fixed. Smearing is
    monotone in <cos p> and runs past equilibrium if left alone: 20 iterations
    reach 0.999 where beta_f = 55 equilibrates at 0.991, so a fixed count
    hands the baseline an over-ordered configuration and beats a strawman.
    Stopping at the first count whose mean plaquette reaches the exact value
    gives the classical arm its best available shot.
    """
    from u1_2d.lgt.lattice import plaquette_angles

    fine = flux(coarse)
    if target_plaquette is None:
        return ape_smear(fine, n_iter=20)
    best, best_gap = fine, abs(plaquette_angles(fine).cos().mean().item()
                               - target_plaquette)
    cur = fine
    for _ in range(40):
        cur = ape_smear(cur, n_iter=1)
        gap = abs(plaquette_angles(cur).cos().mean().item() - target_plaquette)
        if gap < best_gap:
            best, best_gap = cur, gap
        else:
            break
    return best


def local_repair(fine: torch.Tensor, beta: float, action_type: str,
                 n_sweeps: int, device, mode: str = "heatbath",
                 n_overrelax: int = 2) -> tuple[torch.Tensor, int, float]:
    """N sweeps of local updating, with the ERGODIC move selectable.

    THE DYNAMICAL-FERMION PROXY. `smear` is strong because compact U(1) admits
    an exact local heatbath: the local link weight is von Mises, so it can be
    sampled directly and equilibrates short distances in a few sweeps. That is a
    luxury of pure gauge theory. With dynamical fermions the determinant is
    non-local and NO local heatbath exists, so the classical prolongator loses
    exactly the tool that makes it competitive.

    Simulating fermions to test that is a separate project. This is the cheap
    proxy: keep the theory, the action and the exact references untouched, and
    change ONLY the ergodic move --

      mode="heatbath"    the exact local sampler (what `smear` uses)
      mode="metropolis"  the generic fallback available for ANY action

    Everything else is identical, including the two overrelaxation sweeps, so
    the pair isolates one variable: whether an exact local sampler is available.
    If the classical arm's advantage evaporates under Metropolis, that advantage
    was a property of pure gauge theory rather than of prolongation.
    """
    from u1_2d.lgt.local_updates import (heatbath_sweep, metropolis_sweep,
                                         overrelaxation_sweep)
    action = make_action(action_type, beta)
    cur = fine.to(device)
    t0 = time.time()
    with torch.no_grad():
        for _ in range(n_sweeps):
            if mode == "heatbath":
                cur = heatbath_sweep(cur, beta)
            elif mode == "metropolis":
                cur = metropolis_sweep(cur, action)
            else:
                raise ValueError(f"unknown mode {mode}")
            for _ in range(n_overrelax):
                cur = overrelaxation_sweep(cur)
    return cur.cpu(), n_sweeps, time.time() - t0


def fixed_smear(fine: torch.Tensor, beta: float, action_type: str,
                n_sweeps: int, device) -> tuple[torch.Tensor, int, float]:
    """`flux`, then a FIXED number of heatbath + overrelaxation sweeps.

    The tuned variant below stops when the PLAQUETTE crosses its exact value,
    which is the right protocol for `ape` -- APE smearing is monotone in
    <cos p> and overshoots if left alone, so it has to be stopped. Heatbath is
    an EXACT local sampler and cannot overshoot: it converges to the Boltzmann
    distribution and more sweeps are never worse, only costlier. Stopping it on
    the plaquette therefore under-runs the long-wavelength modes the plaquette
    cannot see, and hands the classical arm a worse configuration than it is
    capable of. Measured at beta_f = 55.02: the tuner stops at 10 sweeps with
    the plaquette at 2e-05 and the slowest Wilson loop still unconverged.

    Charging a fixed, generous count is the honest way to run this arm; the
    count is the arm's cost and is reported as such.
    """
    action = make_action(action_type, beta)
    cur = fine.to(device)
    t0 = time.time()
    with torch.no_grad():
        cur = retherm_sweeps(cur, action, n_sweeps, topological_updates=False)
    return cur.cpu(), n_sweeps, time.time() - t0


def tune_smear(fine: torch.Tensor, beta: float, action_type: str,
               target_plaquette: float, device, max_sweeps: int = 400,
               check_every: int = 5) -> tuple[torch.Tensor, int, float]:
    """`flux`, then heatbath + overrelaxation sweeps until the plaquette crosses exact.

    The arm `u2_2d/scripts/17_prolongator_baseline.py` has and this script did
    not, which is why the two studies appeared to disagree about whether a
    learned prolongator beats a classical one. `ape` smooths DETERMINISTICALLY;
    this samples the correct local Boltzmann weight at fixed topology, so
    wherever an exact local update exists it is the strictly stronger classical
    prolongator and it is the arm a lattice referee will ask for.

    `topological_updates=False`, so the arm cannot manufacture topology and
    inherits the coarse sector exactly as the geometric arms do -- the same
    condition every other arm here is held to.

    Stopping on the exact plaquette rather than a fixed count is what makes this
    a competitor rather than a strawman; the count and the seconds it needs are
    returned so the arm is charged for its own tuning.
    """
    action = make_action(action_type, beta)
    cur = fine.to(device)
    t0 = time.time()
    best, best_n = cur.clone(), 0
    best_err = abs(plaquette_angles(cur).cos().mean().item() - target_plaquette)
    with torch.no_grad():
        for n in range(1, max_sweeps + 1):
            cur = retherm_sweeps(cur, action, 1, topological_updates=False)
            if n % check_every:
                continue
            err = abs(plaquette_angles(cur).cos().mean().item() - target_plaquette)
            if err < best_err:
                best, best_n, best_err = cur.clone(), n, err
            elif err > 3.0 * best_err and best_n:
                break
    return best.cpu(), best_n, time.time() - t0


PROLONGATORS = {"tile": tile, "halve": halve, "flux": flux, "ape": ape}

# `smear`/`smear_mh` are not in PROLONGATORS because they need the coupling and
# the device, not just the coarse configuration. Order is the table's column order.
# `smear_mh` is `smear` with the exact heatbath replaced by Metropolis -- the
# dynamical-fermion proxy; see local_repair().
ARM_NAMES = ["tile", "halve", "flux", "ape", "smear", "smear_mh"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="u1_2d/configs/v2.yaml")
    ap.add_argument("--cases", nargs="+", default=["32:14.1464", "32:55.0237"],
                    help="fine_L:fine_beta, matched pairs")
    ap.add_argument("--n-configs", type=int, default=64)
    ap.add_argument("--n-traj", type=int, default=640)
    ap.add_argument("--device", default=None)
    ap.add_argument("--arms", nargs="+", default=ARM_NAMES,
                    help="subset of %s; run one arm without re-running the rest"
                         % ARM_NAMES)
    ap.add_argument("--smear-sweeps", type=int, default=0,
                    help="fixed heatbath+overrelaxation sweep count for the "
                         "`smear` arm; 0 tunes against the exact plaquette. "
                         "Heatbath cannot overshoot, so a fixed generous count "
                         "is the arm's honest best shot -- see fixed_smear().")
    ap.add_argument("--out", default="out/u1_2d/tiling_baseline")
    args = ap.parse_args()

    m5 = _load_05()
    config = load_config(args.config)
    if args.device:
        config["device"] = args.device
    device = resolve_device(config)
    action_type = config["action_type"]
    out_dir = REPO / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for case in args.cases:
        fine_L, fine_beta = case.split(":")
        fine_L, fine_beta = int(fine_L), float(fine_beta)
        coarse_L = fine_L // 2
        from u1_2d.lgt.blocking import approx_matched_coarse_beta
        coarse_beta = approx_matched_coarse_beta(fine_beta, action_type)

        # The matcher returns e.g. 3.99999 where the cached base is named
        # "beta4.pt", so match on value within tolerance, not on the formatted
        # name -- an exact-name lookup silently re-simulates instead.
        base_dir = REPO / "out" / "u1_2d" / "generalization" / "bases"
        base = None
        for cand in base_dir.glob(f"{action_type}_L{coarse_L}_beta*.pt"):
            try:
                b = float(cand.stem.split("beta")[1])
            except ValueError:
                continue
            if abs(b - coarse_beta) <= 1e-3 * max(1.0, abs(coarse_beta)):
                base = cand
                break
        if base is not None:
            print(f"  base: {base.name}", flush=True)
            coarse, _ = load_ensemble(base)
        else:
            from u1_2d.lgt import run_hmc_ensemble
            ss, ns = adapted_hmc_params(coarse_beta,
                                        float(config["data"]["hmc_step_size"]),
                                        int(config["data"]["hmc_steps"]))
            print(f"  no cached base; simulating coarse L={coarse_L} "
                  f"beta={coarse_beta:g}", flush=True)
            # run_hmc_ensemble returns (configs, stats); the old call unpacked
            # neither and had never fired, because every case had a cached base
            # until the 2026-08-18 prune removed them.
            # `topological_updates=True`: the coarse coupling is precisely where
            # topology still mixes, and the whole point of the ladder is that
            # the seed inherits P(Q) from there. t_therm below is a local
            # observable so this cannot flatter any arm.
            coarse, _ = run_hmc_ensemble(
                coarse_L, make_action(action_type, coarse_beta),
                n_configs=args.n_configs, n_chains=16, burn_in=600, thin=5,
                step_size=ss, n_steps=ns, device=device, hot_start=True,
                topological_updates=True,
            )
            coarse = coarse.cpu()
        coarse = coarse[: args.n_configs]

        action = make_action(action_type, fine_beta)
        step_size, n_steps = adapted_hmc_params(
            fine_beta, float(config["data"]["hmc_step_size"]),
            int(config["data"]["hmc_steps"]))
        targets = m5.exact_targets(fine_beta, action_type, fine_L)
        wilson = [n for n in ("plaquette", "wilson_2x2", "wilson_4x4") if n in targets]
        print(f"\n=== {fine_L}:{fine_beta:g} (coarse {coarse_L}:{coarse_beta:.4f}), "
              f"{coarse.shape[0]} configs ===", flush=True)

        row = {"fine_L": fine_L, "fine_beta": fine_beta,
               "coarse_L": coarse_L, "coarse_beta": coarse_beta,
               "n_configs": int(coarse.shape[0]), "arms": {}}
        for name in [a for a in ARM_NAMES if a in args.arms]:
            # Only the smoothing arms use the target; the purely geometric maps
            # take the coarse configuration alone.
            sweeps = None
            if name == "ape":
                t0 = time.time()
                fine0 = ape(coarse, targets["plaquette"])
                build_s = time.time() - t0
            elif name in ("smear", "smear_mh"):
                mode = "heatbath" if name == "smear" else "metropolis"
                if args.smear_sweeps > 0:
                    fine0, sweeps, build_s = local_repair(
                        flux(coarse), fine_beta, action_type,
                        args.smear_sweeps, device, mode=mode)
                elif mode == "heatbath":
                    fine0, sweeps, build_s = tune_smear(
                        flux(coarse), fine_beta, action_type,
                        targets["plaquette"], device)
                else:
                    raise SystemExit(
                        "smear_mh needs an explicit --smear-sweeps: tuning to "
                        "the exact plaquette can never terminate for an arm "
                        "that does not reach it.")
            else:
                t0 = time.time()
                fine0 = PROLONGATORS[name](coarse)
                build_s = time.time() - t0
            # Blocking consistency is the property that separates these arms,
            # so measure it rather than asserting it.
            err = (wrap(block_links(fine0) - wrap(coarse))).abs().max().item()
            # How far from exact the arm STARTS, before a single trajectory.
            # t_therm alone hides this: an arm can sit at t_therm = 0 while
            # being an order of magnitude further from exact than another.
            pre = (plaquette_angles(fine0).cos().mean().item()
                   - targets["plaquette"]) / abs(targets["plaquette"])
            series, _, acc, _ = m5.run_relaxation(
                fine_L, action, fine0, args.n_traj, step_size, n_steps, device)
            t_therm = {n: m5.thermalization_time(series[n], targets[n]) for n in wilson}
            slowest = max(t_therm.values())
            row["arms"][name] = {
                "t_therm": {k: (None if math.isinf(v) else v) for k, v in t_therm.items()},
                "t_therm_slowest": None if math.isinf(slowest) else slowest,
                "blocking_error": err,
                "acceptance": acc,
                "rel_err_at_t0": pre,
                "build_seconds": build_s,
                "smear_sweeps": sweeps,
            }
            shown = f"> {args.n_traj}" if math.isinf(slowest) else f"{slowest:.0f}"
            extra = "" if sweeps is None else f"  sweeps = {sweeps}"
            print(f"  {name:<6} t_therm(slowest Wilson) = {shown:<7} "
                  f"blocking |err| = {err:.2e}  acc = {acc:.3f}  "
                  f"rel err at t=0 = {pre:+.2e}  build = {build_s:.1f}s{extra}",
                  flush=True)
        results.append(row)

    save_json(out_dir / "tiling_baseline.json", results)

    names = [a for a in ARM_NAMES if a in args.arms]
    print("\n| case | " + " | ".join(names) + " | diffusion seed (Fig. 12) |")
    print("|---|" + "---|" * (len(names) + 1))
    therm_dir = REPO / "out" / "u1_2d" / "thermalization"
    for r in results:
        seed = "--"
        for sp in therm_dir.glob(f"L{r['fine_L']}_beta{r['fine_beta']:g}/*_summary.json"):
            s = json.loads(sp.read_text(encoding="utf-8"))
            vals = [s["t_therm"]["diffusion seed"][n]
                    for n in ("plaquette", "wilson_2x2", "wilson_4x4")
                    if n in s["t_therm"]["diffusion seed"]]
            if vals:
                seed = f"{max(vals):.0f}"
            break
        cells = []
        for name in names:
            v = r["arms"][name]["t_therm_slowest"]
            # Budget-limited, never "never" -- the 640-trajectory convention
            # already misreported three converging arms as failures once.
            cells.append(f"> {args.n_traj}" if v is None else f"{v:.0f}")
        print(f"| {r['fine_L']}:{r['fine_beta']:g} | " + " | ".join(cells)
              + f" | {seed} |")
    print(f"\nwrote {(out_dir / 'tiling_baseline.json').relative_to(REPO)}")


if __name__ == "__main__":
    main()
