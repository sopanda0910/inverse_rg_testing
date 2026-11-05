"""Stage 17: the non-learned prolongators, and t_therm against them.

The gap this closes. Stage 08 measures the diffusion seed against cold, hot and
cold+winding starts. All three throw the coarse configuration away, while the
seed is handed it -- so any of the measured advantage could in principle be
bought by ANY map from coarse to fine, with no model in it at all. Until that is
tested the baselines are strawmen, and it is the first thing a referee says.

The ablation is exact here in a way it is not in u1_2d. One inverse-RG step
factorizes as p(psi, q) = p(psi) p(q | psi), and only the psi half is learned:
`naive_su2_inverse_block` seeds SU(2) and `conditional_su2_sweeps` is an EXACT
sampler for p(q | psi). So swapping `lift_determinant` for a non-learned map from
coarse psi to fine psi, with every other stage byte-identical, isolates the
learned contribution and nothing else. That is the cleanest form of this
experiment available in either study.

Q is a functional of psi alone, and psi is an honest compact U(1) field in the
[B, 2, L, L] layout, so the three geometric prolongators are `u1_2d`'s verbatim:

  tile    replicate the coarse psi 2x2. NOT blocking-consistent; its determinant
          plaquettes are distributed like the coarse theory.
  halve   the exact deterministic inverse of the determinant blocking rule.
          Blocking-consistent, so it carries the coarse sector exactly, but cold
          in every fine plaquette blocking does not constrain.
  flux    blocking-consistent AND flux-spreading: the coarse cell's determinant
          plaquette angle shared evenly over its four fine plaquettes instead of
          piled onto one. The strongest prolongator with nothing learned in it.
  smear   `flux`, then N extra heatbath + overrelaxation sweeps with N TUNED PER
          COUPLING to match the exact plaquette. This is the U(2) analogue of the
          Endres-style prolong-then-smooth arm, and it is the honest competitor:
          a fixed count would hand it an over- or under-ordered configuration and
          beat a strawman. Its tuning cost is measured and reported, never hidden.

Every arm -- including the diffusion one -- then gets IDENTICAL post-processing:
coarse-charge enforcement on psi, `n_su2_sweeps` conditional SU(2) sweeps, and
`n_retherm_sweeps` rethermalization sweeps. Whatever differs afterwards is the
lift and only the lift.

t_therm is `u1_2d/scripts/05_hmc_thermalization.py`'s criterion, unchanged, so
the numbers drop straight into the same table: the first trajectory at which the
across-chain |z| against the EXACT value is <= 2 for five consecutive
trajectories. A non-converging arm is reported against its own budget, never as
"never".

    python u2_2d/scripts/17_prolongator_baseline.py --n-traj 400
"""

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u1_2d.lgt.lattice import plaquette_angles as u1_plaquette_angles
from u1_2d.lgt.lattice import topological_charge as u1_charge
from u1_2d.lgt.lattice import wrap as u1_wrap
from u1_2d.pipeline.ladder import apply_coarse_charge
from u2_2d.lgt.actions import WilsonU2Action
from u2_2d.lgt.exact import det_character_exact, plaquette_exact, wilson_loop_exact
from u2_2d.lgt.hmc import BatchedHMCU2, adapted_hmc_params
from u2_2d.lgt.lattice import det_links, half_retr, plaquette, topological_charge, wilson_loop
from u2_2d.lgt.local_updates import conditional_su2_sweeps, retherm_sweeps
from u2_2d.model.su2_lift import assemble_links, naive_su2_inverse_block
from u2_2d.validate.stats import integrated_autocorrelation_time
from u2_2d.utils import (
    configure_device,
    ensemble_path,
    load_config,
    load_ensemble,
    resolve_device,
    save_json,
    set_seed,
)

LOOPS = {"plaquette": (1, 1), "wilson_2x2": (2, 2), "wilson_4x4": (4, 4),
         "wilson_8x8": (8, 8)}


# --------------------------------------------------------------------------
# the three geometric maps, on the determinant field
# --------------------------------------------------------------------------

def tile(psi: torch.Tensor) -> torch.Tensor:
    """[B,2,Lc,Lc] -> [B,2,2Lc,2Lc] by periodic 2x2 replication."""
    return psi.repeat(1, 1, 2, 2).clone()


def halve(psi: torch.Tensor) -> torch.Tensor:
    """Exact inverse of the determinant blocking rule, cold where unconstrained.

    The coarse determinant link is the SUM of the two fine ones it was built
    from (det is a homomorphism, so the abelian rule survives the non-abelian
    group). Splitting it evenly reproduces that sum exactly.
    """
    b, _, lc, _ = psi.shape
    fine = torch.zeros(b, 2, 2 * lc, 2 * lc, dtype=psi.dtype, device=psi.device)
    half = u1_wrap(psi) / 2.0
    fine[:, 0, 0::2, 0::2] = half[:, 0]
    fine[:, 0, 1::2, 0::2] = half[:, 0]
    fine[:, 1, 0::2, 0::2] = half[:, 1]
    fine[:, 1, 0::2, 1::2] = half[:, 1]
    return u1_wrap(fine)


def flux(psi: torch.Tensor) -> torch.Tensor:
    """Blocking-consistent, with the cell's coarse flux spread over its four
    fine plaquettes instead of concentrated on one.

    Adding a constant to the links blocking never reads moves flux between the
    plaquettes of a cell without touching the coarse configuration, so one shift
    per cell equalizes them. Identical to `u1_2d/scripts/37_tiling_baseline.py`,
    which is the point: the determinant sector is the same theory.
    """
    fine = halve(psi)
    with torch.no_grad():
        cell = u1_plaquette_angles(fine)
        want = (cell[:, 0::2, 0::2] + cell[:, 1::2, 0::2]
                + cell[:, 0::2, 1::2] + cell[:, 1::2, 1::2]) / 4.0
        fine[:, 0, 0::2, 1::2] += cell[:, 0::2, 0::2] - want
        fine[:, 0, 1::2, 1::2] += cell[:, 1::2, 0::2] - want
        cell = u1_plaquette_angles(fine)
        fine[:, 1, 1::2, 1::2] += want - cell[:, 0::2, 1::2]
    return u1_wrap(fine)


def _staples(psi):
    """Forward and backward staple angles for both link directions.

    Verbatim from `u1_2d/scripts/37_tiling_baseline.py`: psi is a compact U(1)
    field in the same [B, 2, L, L] layout, so the determinant sector reuses it
    unchanged.
    """
    ux, uy = psi[:, 0], psi[:, 1]
    fx = uy + ux.roll(-1, dims=-1) - uy.roll(-1, dims=-2)
    bx = (-uy.roll(1, dims=-1) + ux.roll(1, dims=-1)
          + uy.roll(-1, dims=-2).roll(1, dims=-1))
    fy = ux + uy.roll(-1, dims=-2) - ux.roll(-1, dims=-1)
    by = (-ux.roll(1, dims=-2) + uy.roll(1, dims=-2)
          + ux.roll(-1, dims=-1).roll(1, dims=-2))
    return (torch.stack([fx, fy], dim=1), torch.stack([bx, by], dim=1))


def ape_smear(psi, alpha: float = 0.5, n_iter: int = 20):
    """Blend each link with its staples, project back by taking the angle.

    DETERMINISTIC. This is the point of the arm: unlike heatbath it samples
    nothing, so it is a genuine interpolation kernel rather than local
    thermalization in disguise. U(1) makes the group projection trivial, which
    is why it stands in for the SU(N) APE/HYP kernel of Endres-style
    multiscale thermalization.
    """
    out = u1_wrap(psi)
    for _ in range(n_iter):
        fwd, bwd = _staples(out)
        z = ((1.0 - alpha) * torch.exp(1j * out)
             + (alpha / 2.0) * (torch.exp(1j * fwd) + torch.exp(1j * bwd)))
        out = torch.angle(z)
    return u1_wrap(out)


def ape(psi):
    """Endres-style prolong-then-smooth: `flux`, then APE to the exact target.

    The smearing count is TUNED, not fixed. Smearing is monotone in <cos p> and
    runs past equilibrium if left alone, so a fixed count hands the arm an
    over-ordered configuration and beats a strawman. The target is the exact
    determinant-sector plaquette `det_character_exact(beta)` -- the determinant
    analogue of the U(1) mean plaquette -- and beta is bound in at call time.
    """
    raise RuntimeError("ape() is beta-dependent; use ape_for(beta)")


def ape_for(beta: float):
    """`ape` with the target bound in, so it fits the GEOMETRIC signature."""
    target = det_character_exact(beta)

    def _ape(psi):
        fine = flux(psi)
        best = fine
        best_gap = abs(float(torch.cos(u1_plaquette_angles(fine)).mean()) - target)
        cur = fine
        for _ in range(40):
            cur = ape_smear(cur, n_iter=1)
            gap = abs(float(torch.cos(u1_plaquette_angles(cur)).mean()) - target)
            if gap < best_gap:
                best, best_gap = cur, gap
            else:
                break
        return best

    return _ape


def cold_psi(psi: torch.Tensor) -> torch.Tensor:
    """[B,2,Lc,Lc] -> [B,2,2Lc,2Lc] of zeros: ordered, Q = 0, carrying NO coarse
    information at all.

    The control for "does the coarse configuration contribute anything beyond
    its topological charge?". `assemble` still enforces the coarse charge on it,
    so this arm has the correct sector and nothing else -- the fine determinant
    phase is the bare instanton field. Paired with `tune_smear` it answers the
    question in one number: if it tunes to the same sweep count as `flux`, the
    coarse long-distance structure is doing no work that cheap exact local
    updates cannot, and the inverse-RG framing reduces to imposing Q on a
    smoothed ordered start.

    Cold rather than hot deliberately. At the benchmark coupling the equilibrium
    is highly ordered (plaquette 0.9988); a hot start is ~100% away and would
    mostly measure how long heatbath takes to order a random field, which is a
    different question.
    """
    b, _, lc, _ = psi.shape
    return torch.zeros(b, 2, 2 * lc, 2 * lc, dtype=psi.dtype, device=psi.device)


GEOMETRIC = {"tile": tile, "halve": halve, "flux": flux}


# --------------------------------------------------------------------------
# assembly: identical to the ladder's own, with the lift swapped out
# --------------------------------------------------------------------------

def assemble(psi_fine: torch.Tensor, coarse: torch.Tensor, beta: float,
             n_su2_sweeps: int, n_retherm_sweeps: int, device: str,
             enforce_charge: bool = True) -> tuple[torch.Tensor, float]:
    """psi -> full U(2) configuration, through the ladder's own post-processing.

    Returns the configuration and its PRE-rethermalization mean plaquette. That
    second number is the one NARRATIVE section 22 insists on: the rethermalization
    sweeps are a local-update repair that will look healthy past the point where
    the lift stopped working, so a post-retherm column alone cannot separate a
    good model from a good repair.
    """
    if enforce_charge:
        psi_fine = apply_coarse_charge(psi_fine, u1_charge(det_links(coarse)))
    su2_seed = naive_su2_inverse_block(coarse[..., 1:])
    fine = assemble_links(psi_fine, su2_seed).to(device)
    action = WilsonU2Action(beta)
    with torch.no_grad():
        fine = conditional_su2_sweeps(fine, action, n_su2_sweeps)
        pre = float(half_retr(plaquette(fine)).mean())
        fine = retherm_sweeps(fine, action, n_retherm_sweeps,
                              topological_updates=False)
    return fine.cpu(), pre


def _plaq_gap(links: torch.Tensor, target: float) -> tuple[float, float]:
    """|mean plaquette - exact| and the ACROSS-CHAIN standard error of that mean.

    Per-chain means, not a batch mean: the chains are the independent replicas,
    so they are what sets the resolution this comparison can actually claim.
    """
    per_chain = half_retr(plaquette(links)).mean(dim=(-2, -1))
    mean = float(per_chain.mean())
    sem = float(per_chain.std(unbiased=True)) / math.sqrt(per_chain.shape[0])
    return abs(mean - target), sem


def tune_smear(fine: torch.Tensor, beta: float, device: str, max_sweeps: int = 400,
               check_every: int = 1, n_sem: float = 2.0) -> dict:
    """Heatbath + overrelaxation sweeps until the plaquette is INDISTINGUISHABLE
    from exact at this ensemble's own resolution. Returns the first crossing.

    THE CRITERION IS A RESOLUTION-AWARE THRESHOLD CROSSING, NOT AN ARGMIN, and
    the previous version being an argmin on a stride of five is why the tuned
    count was unreproducible (`smear` returned 50 / 25 / 15 / 10 across four runs
    at the SAME coupling). Two defects, both fixed here:

      * `check_every = 5` quantized every count to a multiple of five, so the
        learned lift's "5" was the FIRST GRID POINT -- floor-limited, possibly
        truly 1 -- and no margin finer than a factor of two was resolvable. Now
        every sweep is checked.
      * the old rule kept the count with the smallest |gap| over the whole scan.
        Once a configuration is inside the ensemble's standard error the gap is
        pure noise, so that argmin selected wherever noise happened to dip --
        the same failure mode `docs` records for the discrete `t_therm`, which
        was replaced by a fitted estimator for exactly this reason.

    The replacement stops at the first `n` with `gap <= n_sem * sem`, both
    measured across chains. `n = 0` is a real answer and means the lift needed no
    local updating at all. `None` means it never got there within `max_sweeps`.

    `sem` is reported so a margin can be read against the resolution that
    produced it: two arms whose gaps differ by less than one SEM are not
    separated by this measurement, however different their counts look.
    """
    target = plaquette_exact(beta, fine.shape[-3])
    action = WilsonU2Action(beta)
    links = fine.to(device)
    t0 = time.time()
    gap, sem = _plaq_gap(links, target)
    history = [{"n": 0, "gap": gap, "sem": sem}]
    hit, n_hit = gap <= n_sem * sem, 0
    with torch.no_grad():
        n = 0
        while not hit and n < max_sweeps:
            links = retherm_sweeps(links, action, 1, topological_updates=False)
            n += 1
            if n % check_every:
                continue
            gap, sem = _plaq_gap(links, target)
            history.append({"n": n, "gap": gap, "sem": sem})
            if gap <= n_sem * sem:
                hit, n_hit = True, n
    return {
        "links": links.cpu(),
        "n_sweeps": n_hit if hit else None,
        "gap": gap,
        "sem": sem,
        "n_sem": n_sem,
        "target": target,
        "max_sweeps": max_sweeps,
        "seconds": time.time() - t0,
        "history": history,
    }


def fixed_smear(fine: torch.Tensor, beta: float, device: str, n_sweeps: int) -> dict:
    """`n_sweeps` sweeps, chosen WITHOUT reference to the exact plaquette.

    The transfer control. `tune_smear` consumes `plaquette_exact`, which exists
    only because 2D U(2) is solvable -- so a practitioner in 4D SU(3) cannot run
    it, and the only way they could use a classical prolongator is to carry a
    count over from somewhere else. This arm is that: one count, applied
    unchanged at every coupling, with the resulting gap reported rather than
    minimized.
    """
    target = plaquette_exact(beta, fine.shape[-3])
    action = WilsonU2Action(beta)
    links = fine.to(device)
    t0 = time.time()
    with torch.no_grad():
        links = retherm_sweeps(links, action, n_sweeps, topological_updates=False)
    gap, sem = _plaq_gap(links, target)
    return {
        "links": links.cpu(),
        "n_sweeps": n_sweeps,
        "gap": gap,
        "sem": sem,
        "n_sem": None,
        "target": target,
        "max_sweeps": None,
        "seconds": time.time() - t0,
        "history": [],
    }


# --------------------------------------------------------------------------
# t_therm, u1_2d's criterion verbatim
# --------------------------------------------------------------------------

def thermalization_time(series: np.ndarray, target: float,
                        z_threshold: float = 2.0, n_consecutive: int = 5) -> float:
    """First t with |z(across-chain mean)| <= threshold for n_consecutive steps."""
    mean = series.mean(axis=1)
    sem = series.std(axis=1, ddof=1) / math.sqrt(series.shape[1])
    z = np.abs((mean - target) / np.maximum(sem, 1e-12))
    ok = z <= z_threshold
    run_end = min(len(ok), len(ok) - n_consecutive + 1)
    for t in range(max(run_end, 1)):
        if ok[t:t + n_consecutive].all():
            return float(t)
    return float("inf")


def measure(links: torch.Tensor, size: int) -> dict:
    with torch.no_grad():
        out = {}
        for name, (a, b) in LOOPS.items():
            if a < size:
                loop = plaquette(links) if name == "plaquette" else wilson_loop(links, a, b)
                out[name] = half_retr(loop).mean(dim=(-2, -1)).cpu().numpy().copy()
        out["charge"] = topological_charge(links).cpu().numpy().copy()
        return out


def run_arm(name: str, sampler: BatchedHMCU2, start: torch.Tensor, n_traj: int,
            size: int) -> dict:
    """One trajectory-resolved chain per configuration, recorded every step.

    Every trajectory is recorded rather than every fifth: t_therm for a good seed
    is O(1), and a stride of five cannot resolve the difference between 0 and 4.
    """
    links = start.clone().to(sampler.device)
    series = {k: [] for k in LOOPS if k == "plaquette" or LOOPS[k][0] < size}
    charges, t0 = [], time.time()
    with torch.no_grad():
        for step in range(n_traj + 1):
            rec = measure(links, size)
            for k in series:
                series[k].append(rec[k])
            charges.append(rec["charge"])
            if step < n_traj:
                links, _ = sampler.metropolis_step(links)
    return {
        "name": name,
        "series": {k: np.stack(v) for k, v in series.items()},
        "charge": np.stack(charges),
        "seconds": time.time() - t0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="u2_2d/configs/default.yaml")
    parser.add_argument("--device", default=None)
    parser.add_argument("--out-dir", default="out/u2_2d/prolongator")
    parser.add_argument("--n-traj", type=int, default=400)
    parser.add_argument("--n-chains", type=int, default=64)
    parser.add_argument("--rung", type=int, default=-1,
                        help="ladder rung to test (-1 = the top one)")
    parser.add_argument("--coarse-path", default=None,
                        help="lift THIS coarse ensemble instead of a ladder "
                             "rung, so the comparison can be run at any "
                             "coupling rather than only at the two the deployed "
                             "ladder happens to have. Requires --beta. The "
                             "`diffusion` arm is unavailable (it loads stage "
                             "03's output); use diffusion_raw.")
    parser.add_argument("--beta", type=float, default=None,
                        help="fine beta, with --coarse-path. Omit to take the "
                             "topology-matched value for the coarse ensemble.")
    parser.add_argument("--save-series", action="store_true",
                        help="write out-dir/series/<arm>.npz with the raw "
                             "[n_records, n_chains] history of every observable, "
                             "so a later change to t_therm or tau_int is a "
                             "reanalysis instead of a re-run.")
    parser.add_argument("--fixed-sweeps", type=int, default=25,
                        help="sweep count for the *_fixed arms, applied "
                             "unchanged at every coupling. These are the "
                             "TRANSFER controls: tune_smear consumes the exact "
                             "plaquette, which only exists because 2D U(2) is "
                             "solvable, so a fixed transferred count is what a "
                             "practitioner without a closed form could run.")
    parser.add_argument("--checkpoint", default=None,
                        help="score-net checkpoint for the `diffusion_raw` arm "
                             "(default: the config's)")
    parser.add_argument("--n-su2", type=int, default=None,
                        help="conditional SU(2) sweeps (default: ladder config)")
    parser.add_argument("--n-retherm", type=int, default=None,
                        help="rethermalization sweeps (default: ladder config). "
                             "Pass 0 to measure the LIFT alone, which is what "
                             "u1_2d's 37_tiling_baseline.py does -- the default "
                             "10 sweeps repair a bad lift and saturate t_therm.")
    parser.add_argument("--arms", nargs="+",
                        default=["diffusion", "tile", "halve", "flux", "smear",
                                 "cold", "hot"],
                        help="`diffusion` loads stage 03's saved output, which "
                             "already carries the ladder's retherm sweeps; "
                             "`diffusion_raw` regenerates the lift here so it "
                             "gets exactly the same post-processing as the "
                             "geometric arms. Use diffusion_raw with "
                             "--n-retherm 0.")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.device:
        config["device"] = args.device
    device = resolve_device(config)
    print(configure_device(device))
    set_seed(int(config.get("seed", 0)) + 1717)

    ladder_cfg = config["ladder"]
    base = ladder_cfg["base"]
    schedule = [float(b) for b in ladder_cfg["beta_schedule"]]
    sizes = [int(base["lattice_size"]) * 2 ** (i + 1) for i in range(len(schedule))]
    ladder_dir = Path(ladder_cfg.get("out_dir", "out/u2_2d/ladder"))

    if args.coarse_path:
        # ARBITRARY COUPLING. The ladder has exactly two rungs, so --rung alone
        # cannot scan beta, and a scaling claim needs more than two points. Any
        # L=16 ensemble in the data directory serves as a coarse input; the fine
        # coupling comes from the same topology-matched relation the ladder
        # itself uses, so each point is a legitimate inverse-RG step rather than
        # an arbitrary pairing.
        from u2_2d.lgt.blocking import topology_matched_fine_beta

        coarse_path = Path(args.coarse_path)
        if not coarse_path.exists():
            print(f"missing {coarse_path}")
            return 1
        coarse, meta = load_ensemble(coarse_path)
        coarse_size = int(coarse.shape[-3])
        coarse_beta = float((meta or {}).get("beta", 0.0)) or _beta_from_name(
            coarse_path)
        if coarse_beta is None:
            print(f"cannot determine the coarse beta of {coarse_path.name}; "
                  "pass --beta")
            return 1
        size = 2 * coarse_size
        beta = (args.beta if args.beta is not None
                else topology_matched_fine_beta(coarse_beta, coarse_size))
        generated = None
        rung = None
        n_chains = min(args.n_chains, coarse.shape[0])
        coarse = coarse[:n_chains]
        print(f"arbitrary coupling: L={size} beta={beta:g} "
              f"(from L={coarse_size} beta={coarse_beta:g}), {n_chains} chains, "
              f"{args.n_traj} trajectories per arm")
        print(f"  coarse from {coarse_path.name}  ({coarse_size}^2)")
        if "diffusion" in args.arms:
            print("  `diffusion` needs stage 03's output; use diffusion_raw")
            args.arms = [a for a in args.arms if a != "diffusion"]
    else:
        rung = args.rung if args.rung >= 0 else len(schedule) - 1
        beta, size = schedule[rung], sizes[rung]

        # the coarse ensemble this rung was lifted FROM -- the base for rung 0,
        # the previous rung's own output above it, exactly as `generate_ladder`
        # chains them
        if rung == 0:
            coarse_path = ensemble_path(config["data"]["out_dir"],
                                        int(base["lattice_size"]),
                                        float(base["beta"]))
        else:
            coarse_path = ensemble_path(ladder_dir, sizes[rung - 1],
                                        schedule[rung - 1], tag="ladder")
        fine_path = ensemble_path(ladder_dir, size, beta, tag="ladder")
        for p in (coarse_path, fine_path):
            if not p.exists():
                print(f"missing {p} -- run stage 03 first")
                return 1

        coarse, _ = load_ensemble(coarse_path)
        generated, _ = load_ensemble(fine_path)
        n_chains = min(args.n_chains, coarse.shape[0], generated.shape[0])
        coarse, generated = coarse[:n_chains], generated[:n_chains]
        print(f"rung {rung}: L={size} beta={beta:g}, {n_chains} chains, "
              f"{args.n_traj} trajectories per arm")
        print(f"  coarse from {coarse_path.name}  ({coarse.shape[-3]}^2)")

    # Both sweep counts are overridable, and --n-retherm 0 is the setting that
    # makes this ablation comparable to u1_2d's `37_tiling_baseline.py`.
    #
    # THE DEFAULT IS NOT A NEUTRAL COMPARISON. `retherm_sweeps` is heatbath plus
    # two overrelaxations on BOTH sectors, so ten of them equilibrate local
    # structure from almost any start -- which is why every arm here lands at
    # t_therm = 0 while u1_2d's geometric arms, fed straight to HMC with no
    # rethermalization, need 49-696 trajectories. The saturation is the repair
    # stage, not evidence that the arms are equally good lifts.
    #
    # Note it is NOT the conditional SU(2) sampler that repairs a bad psi: that
    # runs with update_phase=False and returns psi bit-for-bit unchanged, which
    # is why `halve` is still -18.8% wrong in the pre-retherm column measured
    # after those 30 sweeps.
    n_su2 = int(args.n_su2 if args.n_su2 is not None
                else ladder_cfg.get("n_su2_sweeps", 30))
    n_retherm = int(args.n_retherm if args.n_retherm is not None
                    else ladder_cfg.get("n_retherm_sweeps", 10))
    print(f"  post-processing: {n_su2} conditional SU(2) sweeps, "
          f"{n_retherm} rethermalization sweeps")
    action = WilsonU2Action(beta)
    step_size, n_steps = adapted_hmc_params(beta)
    sampler = BatchedHMCU2(size, action, n_chains=n_chains, n_steps=n_steps,
                           step_size=step_size, device=device,
                           topological_updates=False)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    psi_coarse = det_links(coarse)
    starts, build_cost, smear_count, pre_plaq, tune_info = {}, {}, {}, {}, {}
    _diffusion_lift_cache = {}
    raw_pre = _load_raw_pre_retherm(ladder_dir, size, beta)
    for name in args.arms:
        t0 = time.time()
        if name == "diffusion":
            starts[name] = generated
            pre_plaq[name] = raw_pre
        elif name == "diffusion_raw":
            # Regenerate rather than load, so this arm receives the same
            # n_su2/n_retherm every other arm does. Loading stage 03's output
            # would silently import ten rethermalization sweeps the geometric
            # arms did not get.
            from u2_2d.model.det_lift import load_det_model
            from u2_2d.pipeline.ladder import generate_fine_from_coarse

            ckpt = args.checkpoint or config["train"].get(
                "checkpoint_path", "out/u2_2d/checkpoints/det_score_net.pt")
            if not Path(ckpt).exists():
                print(f"  missing checkpoint {ckpt}, skipping diffusion_raw")
                continue
            model, sched = load_det_model(ckpt, device=device)
            fine = generate_fine_from_coarse(
                model, sched, coarse, beta,
                n_su2_sweeps=n_su2, device=device,
                n_sampler_steps=int(ladder_cfg.get("n_sampler_steps", 200)),
                n_corrector_steps=int(ladder_cfg.get("n_corrector_steps", 1)),
                batch_size=int(ladder_cfg.get("batch_size", 64)),
                consistency_weight=float(ladder_cfg.get("consistency_weight", 1.0)),
                physics_blend_coef=float(ladder_cfg.get("physics_blend_coef", 0.0)),
            )
            with torch.no_grad():
                pre_plaq[name] = float(half_retr(plaquette(fine.to(device))).mean())
                if n_retherm:
                    fine = retherm_sweeps(fine.to(device), WilsonU2Action(beta),
                                          n_retherm, topological_updates=False)
            starts[name] = fine.cpu()
            _diffusion_lift_cache["fine"] = fine.cpu()
        elif name == "diffusion_tuned":
            # The matched competitor to `smear`: identical tune_smear, applied to
            # the LEARNED lift instead of `flux`. The tuned sweep count is then a
            # direct measure of lift quality -- how much local updating each
            # starting point needs to reach the exact plaquette. Requires
            # diffusion_raw earlier in --arms so the lift is generated once.
            base = _diffusion_lift_cache.get("fine")
            if base is None:
                print("  diffusion_tuned needs `diffusion_raw` listed first, "
                      "skipping")
                continue
            info = tune_smear(base, beta, device)
            starts[name] = info["links"]
            smear_count[name] = info["n_sweeps"]
            tune_info[name] = info
            pre_plaq[name] = pre_plaq.get("diffusion_raw")
            _report_tuning(name, info)
        elif name == "diffusion_fixed":
            # The learned lift on the SAME untuned budget the classical transfer
            # arms get, so the comparison at a fixed count is like-for-like.
            base = _diffusion_lift_cache.get("fine")
            if base is None:
                print("  diffusion_fixed needs `diffusion_raw` listed first, "
                      "skipping")
                continue
            info = fixed_smear(base, beta, device, args.fixed_sweeps)
            starts[name] = info["links"]
            smear_count[name] = info["n_sweeps"]
            tune_info[name] = info
            pre_plaq[name] = pre_plaq.get("diffusion_raw")
            _report_tuning(name, info)
        elif name in GEOMETRIC:
            starts[name], pre_plaq[name] = assemble(
                GEOMETRIC[name](psi_coarse), coarse, beta, n_su2, n_retherm, device)
        elif name == "ape":
            # Deterministic staple-blend interpolation, the true u1_2d analogue.
            # It goes through assemble() like any geometric arm, so it receives
            # exactly n_retherm sweeps -- no more.
            starts[name], pre_plaq[name] = assemble(
                ape_for(beta)(psi_coarse), coarse, beta, n_su2, n_retherm, device)
        elif name == "smear":
            # n_retherm=0 INSIDE assemble: the tuned count below is this arm's
            # entire local-update budget. Previously it got n_retherm on top,
            # which is why it always carried ~25 more sweeps than every other
            # arm and won comparisons it was not entitled to win.
            fine, pre = assemble(flux(psi_coarse), coarse, beta, n_su2, 0, device)
            info = tune_smear(fine, beta, device)
            starts[name] = info["links"]
            smear_count[name] = info["n_sweeps"]
            tune_info[name] = info
            pre_plaq[name] = pre
            _report_tuning(name, info)
        elif name == "smear_fixed":
            # `flux` on a transferred count: the classical arm as a practitioner
            # without a closed form would have to run it.
            fine, pre = assemble(flux(psi_coarse), coarse, beta, n_su2, 0, device)
            info = fixed_smear(fine, beta, device, args.fixed_sweeps)
            starts[name] = info["links"]
            smear_count[name] = info["n_sweeps"]
            tune_info[name] = info
            pre_plaq[name] = pre
            _report_tuning(name, info)
        elif name == "cold_tuned":
            # The coarse-information control. Same charge enforcement, same
            # conditional SU(2) sweeps, same tuning procedure as `smear` -- and
            # a fine determinant phase that is identically zero before the
            # charge is imposed. n_retherm=0 inside assemble for the same reason
            # `smear` uses it: the tuned count is this arm's entire budget.
            fine, pre = assemble(cold_psi(psi_coarse), coarse, beta, n_su2, 0,
                                 device)
            info = tune_smear(fine, beta, device)
            starts[name] = info["links"]
            smear_count[name] = info["n_sweeps"]
            tune_info[name] = info
            pre_plaq[name] = pre
            _report_tuning(name, info)
        elif name == "cold_fixed":
            # The whole classical route with NO closed form anywhere in it: an
            # ordered field, the coarse charge, and a transferred sweep count.
            # If this arm competes, the method reduces to imposing Q on a
            # smoothed ordered start and needs neither a model nor a coarse
            # ensemble beyond a charge draw.
            fine, pre = assemble(cold_psi(psi_coarse), coarse, beta, n_su2, 0,
                                 device)
            info = fixed_smear(fine, beta, device, args.fixed_sweeps)
            starts[name] = info["links"]
            smear_count[name] = info["n_sweeps"]
            tune_info[name] = info
            pre_plaq[name] = pre
            _report_tuning(name, info)
        elif name == "cold":
            starts[name] = sampler.initialize(hot=False).cpu()
        elif name == "hot":
            starts[name] = sampler.initialize(hot=True).cpu()
        else:
            print(f"  unknown arm {name}, skipping")
            continue
        build_cost[name] = time.time() - t0

    # FINITE VOLUME on every observable. The simulation is at finite L, so the
    # finite-volume value is simply the correct reference; the infinite-volume
    # area law is what would need defending. `plaquette_exact` always took
    # `size`; `wilson_loop_exact` was being called without `lattice_size` and so
    # fell back to the infinite-volume law, which made the plaquette and the
    # loops disagree about which theory they were scored against. The gap is
    # 1e-12 to 1e-8 relative here, far below the measurement, so no result moves
    # -- but the two columns should not answer different questions.
    exact = {n: (plaquette_exact(beta, size) if n == "plaquette"
                 else wilson_loop_exact(beta, a * b, lattice_size=size))
             for n, (a, b) in LOOPS.items() if a < size}

    rows = []
    for name, start in starts.items():
        arm = run_arm(name, sampler, start, args.n_traj, size)
        if args.save_series:
            # [n_records, n_chains] per observable, plus the charge history and
            # the exact references, so any later change to t_therm or tau_int is
            # a reanalysis rather than a re-run. The project learned this the
            # expensive way when a t_therm redefinition cost a full re-run of
            # the coverage matrix; this script had not yet been brought up to it.
            series_dir = out_dir / "series"
            series_dir.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(
                series_dir / f"{name}.npz",
                charge=arm["charge"],
                beta=np.array(beta), lattice_size=np.array(size),
                n_chains=np.array(n_chains),
                **{f"obs_{k}": v for k, v in arm["series"].items()},
                **{f"exact_{k}": np.array(v) for k, v in exact.items()},
            )
        t_therm = {k: thermalization_time(v, exact[k]) for k, v in arm["series"].items()}
        initial = {k: float(v[0].mean()) for k, v in arm["series"].items()}
        final = {k: float(v[-1].mean()) for k, v in arm["series"].items()}
        # Local-update sweeps this arm actually received. `tune_info` carries it
        # for the tuned and fixed-count arms (None there means the tuning never
        # reached the resolution threshold, which is NOT zero sweeps); every
        # other arm got exactly what `assemble` applied, and the cold/hot arms
        # bypass `assemble` entirely.
        if name in tune_info:
            local_sweeps = tune_info[name]["n_sweeps"]
        elif name in ("cold", "hot"):
            local_sweeps = 0
        elif name == "diffusion":
            local_sweeps = int(ladder_cfg.get("n_retherm_sweeps", 10))
        else:
            local_sweeps = n_retherm
        slowest = (max(t_therm.values()) if all(
            math.isfinite(v) for v in t_therm.values()) else None)
        row = {
            "arm": name,
            "lattice_size": size,
            "beta": beta,
            "n_chains": n_chains,
            "n_traj": args.n_traj,
            "build_seconds": build_cost.get(name),
            "tuned_sweeps": smear_count.get(name),
            "local_sweeps": local_sweeps,
            "tuning_converged": (None if name not in tune_info
                                 else tune_info[name]["n_sweeps"] is not None),
            "plaquette_gap": (None if name not in tune_info
                              else tune_info[name]["gap"]),
            "plaquette_gap_sem": (None if name not in tune_info
                                  else tune_info[name]["sem"]),
            "plaquette_gap_in_sem": (
                None if name not in tune_info or not tune_info[name]["sem"]
                else tune_info[name]["gap"] / tune_info[name]["sem"]),
            "tuning_seconds": (None if name not in tune_info
                               else tune_info[name]["seconds"]),
            "tuning_history": (None if name not in tune_info
                               else tune_info[name]["history"]),
            # cost in one currency; see SWEEP_TOUCHES for why this is needed
            "hmc_n_steps": n_steps,
            "sweep_touches": SWEEP_TOUCHES,
            "link_touches": _link_touches(local_sweeps, slowest, n_steps),
            # NOT folded into the total: the conditional SU(2) sweeps act on the
            # q sector at frozen psi, are identical for every arm that goes
            # through `assemble`, and are a different move from a retherm sweep.
            "su2_sweeps": 0 if name in ("cold", "hot") else n_su2,
            "hmc_seconds": arm["seconds"],
            "t_therm": {k: (v if math.isfinite(v) else None) for k, v in t_therm.items()},
            "t_therm_budget": args.n_traj,
            "t_therm_slowest": slowest,
            "rel_err_initial": {k: (initial[k] - exact[k]) / abs(exact[k]) for k in exact},
            "rel_err_final": {k: (final[k] - exact[k]) / abs(exact[k]) for k in exact},
            "plaquette_pre_retherm": pre_plaq.get(name),
            "rel_err_pre_retherm": (
                None if pre_plaq.get(name) is None
                else (pre_plaq[name] - exact["plaquette"]) / abs(exact["plaquette"])),
            "exact": exact,
            # the project's standard seed score, fit-free, at record 0
            "z_initial": {k: _raw_seed_z(v, exact[k])[0]
                          for k, v in arm["series"].items()},
            "tau_int_tail": {k: _tail_tau_int(v) for k, v in arm["series"].items()},
            "q_squared_initial": float((arm["charge"][0] ** 2).mean()),
            "q_squared_final": float((arm["charge"][-1] ** 2).mean()),
        }
        rows.append(row)
        slow = row["t_therm_slowest"]
        print(f"  {name:10s} t_therm(plaq)="
              f"{_fmt(t_therm['plaquette'], args.n_traj):>7s}"
              f"  slowest={_fmt(slow if slow is not None else float('inf'), args.n_traj):>7s}"
              f"  |dP/P| t=0 {abs(row['rel_err_initial']['plaquette']):.2e}"
              f"  build {build_cost.get(name, 0):.0f}s", flush=True)
        save_json(out_dir / "prolongator.json", rows)

    _write_report(out_dir / "report.md", rows, n_su2, n_retherm)
    print(f"\nwrote {out_dir / 'prolongator.json'} and report.md")
    return 0


def _fmt(v: float, budget: int) -> str:
    return f"> {budget}" if v is None or not math.isfinite(v) else f"{v:.0f}"


def _raw_seed_z(series: np.ndarray, exact: float) -> tuple[float, float]:
    """|mean - exact| / SEM and the relative deviation, at RECORD 0.

    `84_raw_seed_quality.py`'s endpoint, which is the project's standard for
    scoring a starting configuration and is deliberately fit-free: a relaxation
    time is INVERTED for a good seed (a seed already at target has no transient
    to resolve, so the fit fails and scores it a failure), while this is just how
    far from exact the thing you were handed actually is.

    Both are reported because they answer different questions. `z = sqrt(N) *
    bias / sigma`, so a noisier arm scores a smaller z at equal bias; a relative
    deviation ignores that the theory's own spread moves by orders of magnitude
    across couplings. At FIXED coupling the ratio is comparable between arms
    (they face the identical spread); ACROSS couplings use z.
    """
    first = np.asarray(series[0], dtype=float)
    mean = float(first.mean())
    sem = float(first.std(ddof=1)) / math.sqrt(len(first)) if len(first) > 1 else 0.0
    z = abs(mean - exact) / sem if sem > 0 else float("inf")
    return z, (mean - exact) / abs(exact)


def _tail_tau_int(series: np.ndarray) -> float:
    """Mean per-chain tau_int of the second half of the history.

    The second half so the transient is excluded, and PER CHAIN because the
    chains are the independent replicas -- pooling them first would measure the
    across-chain mean's autocorrelation, which is not what an interval between
    independent configurations means.
    """
    tail = np.asarray(series, dtype=float)[len(series) // 2:]
    if tail.shape[0] < 8:
        return float("nan")
    taus = [integrated_autocorrelation_time(tail[:, c])[0]
            for c in range(tail.shape[1])]
    return float(np.mean(taus))


def _report_tuning(name: str, info: dict) -> None:
    n = info["n_sweeps"]
    count = f"> {info['max_sweeps']}" if n is None else str(n)
    ratio = info["gap"] / info["sem"] if info["sem"] > 0 else float("inf")
    print(f"  {name}: {count} sweeps, gap {info['gap']:.2e} = {ratio:.1f} SEM "
          f"({info['seconds']:.0f}s)", flush=True)


# One retherm sweep is heatbath plus two overrelaxations, so it touches every
# link three times; one leapfrog trajectory touches every link `n_steps` times.
# This is `44_sweeps_vs_trajectories.py`'s convention verbatim, and without it
# the sweep column and the t_therm column cannot be added together at all --
# at beta = 416.524 one trajectory costs twelve sweeps, so an arm that saves
# five sweeps and spends four extra trajectories is five times WORSE, not
# better. It prices only local updates and HMC; the reverse-diffusion sampler
# is not expressible in link touches and is charged in `build_seconds`.
SWEEP_TOUCHES = 3


def _link_touches(tuned_sweeps, t_therm_slowest, n_steps: int):
    """Total local-update + HMC cost in link touches, or None if either part
    never finished (an unconverged arm has no total, and writing one would
    quietly turn a failure into a number)."""
    if tuned_sweeps is None or t_therm_slowest is None:
        return None
    return int(SWEEP_TOUCHES * tuned_sweeps + n_steps * t_therm_slowest)


def _beta_from_name(path: Path):
    """Recover the coupling from an ensemble filename, `u2_L16_beta105.244.pt`.

    The metadata is authoritative where it exists; this is the fallback for the
    older ensembles that predate it.
    """
    stem = path.stem
    if "beta" not in stem:
        return None
    try:
        return float(stem.split("beta")[-1])
    except ValueError:
        return None


def _load_raw_pre_retherm(ladder_dir: Path, size: int, beta: float):
    """The diffusion arm's own pre-retherm plaquette, from stage 03's summary.

    Recomputing it here would mean re-running the lift; stage 03 already recorded
    it, and reading it back keeps the column comparable across arms.
    """
    path = Path(ladder_dir) / "summary.json"
    if not path.exists():
        return None
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    rows = rows if isinstance(rows, list) else rows.get("rungs", [])
    for r in rows:
        if int(r.get("lattice_size", -1)) == size and abs(
                float(r.get("beta", 0.0)) - beta) < 1e-6:
            return r.get("plaquette_pre_retherm")
    return None


ORDER = ["tile", "halve", "flux", "ape", "smear", "smear_fixed",
         "cold_tuned", "cold_fixed", "hot", "cold",
         "diffusion_raw", "diffusion_tuned", "diffusion_fixed", "diffusion"]


def _write_report(path: Path, rows: list, n_su2: int, n_retherm: int) -> None:
    rows = sorted(rows, key=lambda r: ORDER.index(r["arm"]) if r["arm"] in ORDER else 99)
    beta, size = rows[0]["beta"], rows[0]["lattice_size"]
    budget = rows[0]["n_traj"]
    obs = [k for k in LOOPS if k in rows[0]["t_therm"]]

    lines = [
        "# Non-learned prolongators, and t_therm against them",
        "",
        f"$L = {size}$, $\\beta = {beta:g}$, {rows[0]['n_chains']} chains, "
        f"{budget} trajectories per arm.",
        "",
        "Every arm receives IDENTICAL post-processing -- coarse-charge enforcement "
        f"on $\\psi$, {n_su2} conditional SU(2) sweeps, {n_retherm} rethermalization "
        "sweeps -- so what differs is the lift and only the lift. The SU(2) sampler "
        "is exact at frozen $\\psi$, which is what makes this ablation clean: the "
        "only learned object in the pipeline is the map from coarse $\\psi$ to fine "
        "$\\psi$, and it is the only thing being swapped.",
        "",
        "$t_{\\rm therm}$ is `u1_2d/scripts/05_hmc_thermalization.py`'s criterion: "
        "the first trajectory at which the across-chain $|z|$ against the EXACT "
        "value is $\\le 2$ for five consecutive trajectories. An arm that never "
        f"gets there is written `> {budget}`, against its own budget, never "
        "\"never\".",
        "",
        "Cost is reported in LINK TOUCHES, `44_sweeps_vs_trajectories.py`'s "
        f"convention: one retherm sweep touches every link {SWEEP_TOUCHES} times "
        f"and one trajectory touches it {rows[0].get('hmc_n_steps', 0)} times at "
        "this coupling. Without a common currency the sweep column and the "
        "$t_{\\rm therm}$ column cannot be added, and an arm that saves sweeps "
        "while spending trajectories looks cheaper when it is not. The "
        "reverse-diffusion sampler is NOT expressible in link touches and is "
        "charged in `build s` instead.",
        "",
        "`gap/SEM` is the plaquette's distance from exact in units of the "
        "across-chain standard error at the moment the arm was handed to HMC. "
        "Two arms within about one SEM of each other are not separated by this "
        "measurement however different their sweep counts look.",
        "",
        "| arm | sweeps | " + " | ".join(f"$t$ {o.replace('wilson_', 'W')}" for o in obs)
        + " | slowest | link touches | gap/SEM | rel err **pre**-retherm "
        "| $|\\Delta P/P|$ at $t=0$ | build s |",
        "|---|---|" + "---|" * (len(obs) + 6),
    ]
    for r in rows:
        cells = [_fmt(r["t_therm"][o], budget) for o in obs]
        slow = r["t_therm_slowest"]
        name = r["arm"]
        if r.get("tuning_converged") is False:
            name += " (never tuned in)"
        bold = "**" if r["arm"] == "diffusion" else ""
        pre = r.get("rel_err_pre_retherm")
        sweeps = r.get("local_sweeps")
        touches = r.get("link_touches")
        in_sem = r.get("plaquette_gap_in_sem")
        lines.append(
            f"| {bold}{name}{bold} | {'--' if sweeps is None else sweeps} | "
            + " | ".join(f"{bold}{c}{bold}" for c in cells)
            + f" | {bold}{_fmt(slow if slow is not None else float('inf'), budget)}{bold}"
            + f" | {'--' if touches is None else touches}"
            + f" | {'--' if in_sem is None else f'{in_sem:.1f}'}"
            + f" | {'--' if pre is None else f'{pre:+.2e}'}"
            + f" | {abs(r['rel_err_initial']['plaquette']):.2e}"
            + f" | {r['build_seconds']:.0f} |")

    geo = [r for r in rows if r["arm"] in GEOMETRIC]
    cold = next((r for r in rows if r["arm"] == "cold"), None)
    diff = next((r for r in rows if r["arm"] == "diffusion"), None)
    lines += ["", "## What to read off it", ""]
    if diff is not None and cold is not None:
        # Report BOTH columns and name the best geometric arm in each. Quoting
        # the diffusion-vs-cold margin alone made an earlier version of this
        # report self-undermining: it advertised a three-orders-of-magnitude win
        # over the weakest arm two lines above telling the reader not to compare
        # against that arm. The pre-retherm column is where the lift wins; the
        # t=0 column is where the exact SU(2) sampler erases the difference.
        def _pre(r):
            v = r.get("rel_err_pre_retherm")
            return None if v is None else abs(v)

        d_pre = _pre(diff)
        d_t0 = abs(diff["rel_err_initial"]["plaquette"])
        # Compare against every NON-LEARNED lift, not just GEOMETRIC. `smear` is
        # built outside that dict, and it is the strongest baseline at the top
        # rung (1.14e-06 vs tile's 7.24e-06 at t=0) as well as the arm this
        # report already calls "the arm that matters" -- omitting it understated
        # the baseline and flattered the model.
        baselines = [r for r in rows
                     if r["arm"] in GEOMETRIC or r["arm"] == "smear"]
        cand = [r for r in baselines if _pre(r) is not None]
        best_pre = min(cand, key=_pre) if cand else None
        best_t0 = (min(baselines,
                       key=lambda r: abs(r["rel_err_initial"]["plaquette"]))
                   if baselines else None)

        if d_pre is not None and best_pre is not None and d_pre > 0:
            b = _pre(best_pre)
            lines.append(
                f"**Pre-rethermalization the learned lift is {b / d_pre:.0f}x "
                f"closer to exact than the best geometric arm** "
                f"(`{best_pre['arm']}`): {d_pre:.2e} against {b:.2e}.")

        if best_t0 is not None:
            b0 = abs(best_t0["rel_err_initial"]["plaquette"])
            if b0 > 0 and d_t0 > 0:
                rel = d_t0 / b0
                def _x(v):
                    return f"{v:.1f}x" if v < 10 else f"{v:.0f}x"

                verdict = (
                    f"**{_x(rel)} WORSE than `{best_t0['arm']}`**" if rel > 1.05
                    else f"{_x(1 / rel)} better than `{best_t0['arm']}`"
                    if rel < 0.95 else f"level with `{best_t0['arm']}`")
                lines.append(
                    f"After the identical post-processing every arm receives, "
                    f"that margin is gone: at $t = 0$ the diffusion arm is "
                    f"{verdict} ({d_t0:.2e} against {b0:.2e}). The exact "
                    f"conditional SU(2) sampler repairs a bad determinant "
                    f"sector, so **local observables do not discriminate the "
                    f"lift.** Argue the model on topology and extended loops, "
                    f"not on the plaquette.")

        lines.append(
            f"For scale the cold start begins at "
            f"{abs(cold['rel_err_initial']['plaquette']):.2e}. It is the control "
            f"that gives the plot dynamic range, not the comparison that "
            f"supports the claim.")
    if geo and cold is not None:
        worse = [r["arm"] for r in geo
                 if (r["t_therm_slowest"] is None
                     or (cold["t_therm_slowest"] is not None
                         and r["t_therm_slowest"] > cold["t_therm_slowest"]))]
        if worse:
            lines.append(
                f"**{', '.join(worse)} are no better than a fresh cold start.** "
                "Prolonging by an obvious deterministic rule satisfies the coarse "
                "constraint while being wrong at short distances, and the chain "
                "then has to undo it -- so the advantage is specific to learning, "
                "not to having been handed the coarse configuration.")
        else:
            lines.append(
                "Every geometric prolongator beats a fresh cold start here, so "
                "the bulk of the seed's advantage over `cold` is available "
                "without a model at all -- which is why the cold margin must "
                "never be the headline number.")
    lines += [
        "",
        "`smear` is the arm that matters: `flux` plus heatbath + overrelaxation "
        "sweeps, the count chosen per coupling to match the exact plaquette rather "
        "than fixed. Its build cost is charged in the last column.",
        "",
        "Source: `u2_2d/scripts/17_prolongator_baseline.py`.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
