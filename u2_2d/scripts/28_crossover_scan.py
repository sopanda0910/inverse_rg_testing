"""Beta scan of thermalization time -- the u2 port of u1's lead-figure scan.

This is `u1_2d/scripts/05_hmc_thermalization.py --generalization` followed by
`35_crossover_window.py`, ported rather than reinvented. What that pair does, and
why each piece is load-bearing:

  * `t_therm` is measured on LOCAL observables (plaquette, W2x2, W4x4) and is the
    SLOWEST of them, using u1's criterion: the first trajectory at which the
    across-chain |z| against the EXACT value stays <= 2 for five consecutive
    records. Topology is deliberately NOT in that list -- it is measured
    separately, because a chain can be perfectly thermalized locally while never
    tunnelling.

  * `interval` = 2 tau_int of the equilibrated plain chain: the number of
    trajectories a working HMC chain needs between two INDEPENDENT
    configurations. This is the yardstick, and the claim only means something
    against it. A seed that thermalizes in fewer trajectories than the chain
    needs to decorrelate is cheaper per independent configuration; a seed that
    thermalizes in more is not, however impressive the ratio against a cold
    start looks.

  * ALL ARMS RUN PLAIN HMC -- no topological updates. Adding a winding move to
    the baseline is a different experiment (that is `26_freezing_arms.py`), and
    mixing them makes the ratio uninterpretable.

  * The three REGIMES matter more than the ratio. u1 found, and u2 inherits,
    that a speedup only means something while the baseline still finishes:
      HMC healthy  fresh chains thermalize AND Q tunnels -- a ratio is honest
      Q frozen     chains thermalize locally, Q never tunnels -- the advantage
                   is partly "HMC cannot do topology", a different claim
      HMC dead     fresh chains never thermalize inside the budget -- the ratio
                   is a bound, not a measurement, and is reported as such

ONE PHYSICS CAVEAT THAT THE FIGURE MUST CARRY. At FIXED L, raising beta shrinks
the exact <Q^2> (approximately V / 4 pi^2 beta): at L = 32 it falls 1.00 at
beta = 105.7 to 0.04 at beta = 800. So the far right of this scan is not "hard
topology" -- it is a theory with almost no topology, where a frozen chain
reproduces P(Q) almost correctly by accident. Holding <Q^2> fixed while raising
beta is the LADDER direction (beta_f = 4 beta_c with L_f = 2 L_c), which is why
the top-rung L = 64 point is carried alongside. `q_squared_exact` is recorded per
coupling so this is visible rather than implied.

    python u2_2d/scripts/28_crossover_scan.py --device cuda
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import re
import sys
import time
from pathlib import Path

import numpy as np
import torch
from scipy.optimize import curve_fit, least_squares
from scipy.stats import chi2 as chi2_dist

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u1_2d.validate.stats import integrated_autocorrelation_time
from u2_2d.lgt.actions import WilsonU2Action
from u2_2d.lgt.blocking import topology_matched_fine_beta
from u2_2d.lgt.exact import (
    det_topological_charge_distribution,
    matched_u1_beta,
    plaquette_exact,
    wilson_loop_exact,
)
from u2_2d.lgt.hmc import BatchedHMCU2, adapted_hmc_params
from u2_2d.lgt.lattice import half_retr, plaquette, topological_charge, wilson_loop
from u2_2d.model.det_lift import load_det_model
from u2_2d.pipeline.ladder import generate_fine_from_coarse
from u2_2d.utils import (configure_device, load_config, load_ensemble, resolve_device,
                         save_ensemble, save_json, set_seed)

LOCAL = ("plaquette", "wilson_2x2", "wilson_4x4")


def thermalization_time(series: np.ndarray, target: float,
                        z_threshold: float = 2.0, n_consecutive: int = 5) -> float:
    """u1's criterion, verbatim (see 17_prolongator_baseline.thermalization_time).
    SUPERSEDED as the record's t_therm (see fit_relaxation_time below) -- kept
    only because it is cheap to also log for cross-checking against the old
    definition, not because it is trusted any more. The discrete
    threshold-crossing this computes is a noise-sensitive statistic: a single
    lagging chain among 64 can shift the crossing record by a lot, and the
    resulting t_therm was measured to be genuinely rugged in coupling (not an
    artifact of one run) -- see CLAUDE.md's u1 sampler-steps section. It is
    also unusable for the seed arm specifically once thermalization is O(1)
    trajectory: the discrete integer answer (0, 1, or 2) swings the derived
    cost-efficiency ratio by a large factor for no physical reason.
    """
    mean = series.mean(axis=1)
    sem = series.std(axis=1, ddof=1) / math.sqrt(series.shape[1])
    z = np.abs((mean - target) / np.maximum(sem, 1e-12))
    ok = z <= z_threshold
    run_end = min(len(ok), len(ok) - n_consecutive + 1)
    for t in range(max(run_end, 1)):
        if ok[t:t + n_consecutive].all():
            return float(t)
    return float("inf")


def _fit_exp_once(t: np.ndarray, mean: np.ndarray, sem: np.ndarray,
                  target: float) -> float:
    """One exponential relaxation-time fit: mean(t) ~= target + A*exp(-t/tau).
    Returns tau in the same units as t (trajectories), 0.0 if the series is
    already indistinguishable from target everywhere (nothing to fit -- the
    honest answer for a seed that thermalizes in ~0 trajectories, rather than
    forcing a discrete 0/1/2 integer), or inf if the fit cannot resolve any
    decay (never approaches target within the window -- same meaning as the
    old function's inf, consistent with the "HMC dead"/"Q frozen" regime
    logic downstream that already branches on isinf(seed)/isinf(cold)).
    """
    # LIKELIHOOD-RATIO (delta-chi2) test against the flat-at-target null,
    # not a pooled-window or per-record threshold. Verified necessary on real
    # HMC output, not just a hypothetical: a genuinely-equilibrated seed's
    # plaquette series (flat within noise the whole 150-trajectory window,
    # chi2/dof = 1.28) still has isolated records exceeding 2-sigma purely by
    # chance scattered THROUGHOUT the window (not just early on, since with
    # ~75 records at ~5% false-positive rate that is expected) -- both a
    # per-record test and a pooled-first-5-records test are fooled by this
    # and fit a fictitious tau ~ 185 to what is actually pure noise. The
    # delta-chi2 test is not fooled the same way because it looks at whether
    # the exponential's 2 EXTRA parameters buy a global fit improvement large
    # enough to not be explained by fitting noise (Wilks' theorem: under the
    # null, that improvement is chi2-distributed with 2 dof, so >~6 is the
    # justified threshold at 95% confidence).
    chi2_flat = float(np.sum(((mean - target) / sem) ** 2))

    bias = mean - target
    resolved = np.abs(bias) / sem >= 1.0
    idx = np.where(resolved & (np.abs(bias) > 0))[0]
    if len(idx) >= 2:
        slope, _ = np.polyfit(t[idx], np.log(np.abs(bias[idx])), 1)
        tau0 = min(max(-1.0 / slope, 0.1), float(t[-1]) * 10.0) if slope < 0 else max(float(t[-1]) / 4.0, 1.0)
    else:
        tau0 = max(float(t[-1]) / 4.0, 1.0)
    A0 = float(mean[0] - target)
    try:
        popt, _ = curve_fit(
            lambda tt, A, tau: target + A * np.exp(-tt / max(tau, 1e-6)),
            t, mean, p0=[A0, tau0], sigma=sem, absolute_sigma=True,
            bounds=([-np.inf, 0.0], [np.inf, float(t[-1]) * 10.0]),
            maxfev=2000)
    except (RuntimeError, ValueError):
        return 0.0

    pred = target + popt[0] * np.exp(-t / max(popt[1], 1e-6))
    chi2_exp = float(np.sum(((mean - pred) / sem) ** 2))
    if chi2_flat - chi2_exp < 6.0:
        return 0.0

    tau = float(popt[1])
    # A fit that saturates the upper bound is not a resolved decay -- treat
    # the same as a non-converging fit rather than reporting a number that is
    # really just "the optimizer hit the wall". RELATIVE tolerance (0.1%),
    # not an absolute 1e-6: verified on real HMC output that the optimizer's
    # own convergence tolerance settles ~1e-4 short of the exact boundary
    # (tau=3979.9999115 against a bound of 3980.0, i.e. ~8.9e-5 away), which
    # an absolute 1e-6 window does not catch -- that exact case shipped a
    # seed=3980.0 "thermalization time" into a live run before being caught.
    upper = float(t[-1]) * 10.0
    if tau >= upper * (1.0 - 1e-3):
        return float("inf")
    return max(tau, 0.0)


def fit_relaxation_time(series: np.ndarray, target: float, record_every: int,
                        n_boot: int = 100, seed: int = 0) -> tuple[float, float]:
    """Exponential relaxation-time replacement for `thermalization_time`.

    THE STANDARD DEFINITION (fit the transient decay of the observable mean
    toward its exact value and take the fitted time constant), not the
    discrete threshold-crossing above. This is the same class of estimator
    `integrated_autocorrelation_time` already uses for the `interval`
    denominator elsewhere in this script -- bringing t_therm up to that same
    standard, rather than introducing a new methodology, is the point.

    `series` is [n_records, n_chains]. Returns (tau_hat, tau_err), with
    tau_err from a chain-resampling bootstrap (same resampling unit as
    `chain_bootstrap` elsewhere in this project: chains, not configurations,
    since a chain stuck away from equilibrium should resample as one unit).
    """
    t = np.arange(series.shape[0], dtype=float) * record_every
    mean = series.mean(axis=1)
    sem = np.maximum(series.std(axis=1, ddof=1) / math.sqrt(series.shape[1]), 1e-12)
    tau_hat = _fit_exp_once(t, mean, sem, target)

    n_chains = series.shape[1]
    rng = np.random.default_rng(seed)
    boots = np.empty(n_boot)
    for i in range(n_boot):
        pick = rng.integers(0, n_chains, n_chains)
        sub = series[:, pick]
        m = sub.mean(axis=1)
        s = np.maximum(sub.std(axis=1, ddof=1) / math.sqrt(n_chains), 1e-12)
        boots[i] = _fit_exp_once(t, m, s, target)
    # IQR-based spread, not raw std: an occasional bootstrap resample can
    # spuriously trip the pooled-window threshold (a handful of chains drawn
    # together happen to sit >2 sigma from target) and return a large finite
    # tau against a true-zero point estimate -- a rare outlier the std is not
    # robust to, verified on synthetic already-equilibrated data.
    finite = boots[np.isfinite(boots)]
    if len(finite) > 3:
        q16, q84 = np.percentile(finite, [16, 84])
        tau_err = float((q84 - q16) / 2.0)
    elif len(finite) > 1:
        tau_err = float(finite.std())
    else:
        tau_err = float("nan")

    # SIGNIFICANCE GATE on the fitted tau itself, using the bootstrap spread
    # already computed. This is the second and decisive line of defense
    # (the delta-chi2 test in _fit_exp_once is the first, but is not
    # reliable alone -- verified on real HMC output): successive HMC records
    # are autocorrelated in Monte Carlo time, which the per-record chi2 test
    # does not model, so a slow spurious drift in what is actually flat noise
    # can beat the delta-chi2 threshold too (measured case: a genuinely
    # equilibrated seed's plaquette series, chi2/dof=1.28, no visible trend,
    # still fit to tau~186 by both defenses individually). But the CHAIN
    # bootstrap does not share that blind spot -- it resamples which chains
    # contribute, and a fictitious drift driven by chance temporal structure
    # in the pooled mean is unstable under that resampling, so its own
    # z-score (tau_hat / tau_err) collapses to O(1) exactly when the point
    # estimate is not real. Confirmed on that same measured series: point
    # tau=185.7, bootstrap tau_err=163.4, z=1.1 -- below the gate, correctly
    # overridden to 0. A genuine slow decay (synthetic tau=50 case) keeps
    # z~111 and is untouched.
    if math.isfinite(tau_hat) and tau_hat > 0 and math.isfinite(tau_err):
        if tau_err <= 0 or tau_hat / tau_err < 2.0:
            tau_hat = 0.0
    return tau_hat, tau_err


def _fit_joint_once(t: np.ndarray, means: dict, sems: dict, targets: dict,
                    names: tuple) -> tuple:
    """Coupled multi-exponential fit sharing ONE tau across observables --
    Detmold & Endres, "Multiscale Monte Carlo equilibration" (PRD 92, 114516
    (2015); PRD 94, 114502 (2016)): they fit rethermalization timescales the
    same way, coupled multi-exponential fits across observables and starting
    distributions with a common exponent, reporting chi2/dof (0.6-2.1 in
    their case) as the fit-quality diagnostic. Returns
    (tau, chi2_flat, chi2_fit, n_dof, n_params) so the caller can report
    chi2/dof exactly as they do, not just use it internally for a gate.
    """
    chi2_flat = 0.0
    n_dof = 0
    tau0_candidates = []
    for name in names:
        bias = means[name] - targets[name]
        z = np.abs(bias) / sems[name]
        chi2_flat += float(np.sum(z ** 2))
        n_dof += len(means[name])
        resolved = (z >= 1.0) & (np.abs(bias) > 0)
        idx = np.where(resolved)[0]
        if len(idx) >= 2:
            slope, _ = np.polyfit(t[idx], np.log(np.abs(bias[idx])), 1)
            if slope < 0:
                tau0_candidates.append(-1.0 / slope)
    tau0 = float(np.median(tau0_candidates)) if tau0_candidates else max(float(t[-1]) / 4.0, 1.0)
    tau0 = min(max(tau0, 0.1), float(t[-1]) * 10.0)
    A0 = [float(means[name][0] - targets[name]) for name in names]

    def residuals(params):
        tau = max(params[0], 1e-6)
        out = []
        for i, name in enumerate(names):
            pred = targets[name] + params[1 + i] * np.exp(-t / tau)
            out.append((means[name] - pred) / sems[name])
        return np.concatenate(out)

    n_params = 1 + len(names)
    lower = [0.0] + [-np.inf] * len(names)
    upper = [float(t[-1]) * 10.0] + [np.inf] * len(names)
    try:
        result = least_squares(residuals, [tau0] + A0, bounds=(lower, upper), max_nfev=4000)
    except (RuntimeError, ValueError):
        return 0.0, chi2_flat, chi2_flat, n_dof, n_params

    chi2_fit = float(np.sum(result.fun ** 2))
    # Critical delta-chi2 for n_params extra free parameters (Wilks'
    # theorem), not the fixed threshold of 6 the single-observable version
    # used (that value was specific to 2 params/1 observable) -- generalizes
    # correctly as more observables are fit jointly.
    if chi2_flat - chi2_fit < chi2_dist.ppf(0.95, n_params):
        return 0.0, chi2_flat, chi2_fit, n_dof, n_params

    tau = float(result.x[0])
    # RELATIVE tolerance -- see the matching comment in _fit_exp_once for the
    # measured case (tau=3979.9999115 against bound 3980.0) that an absolute
    # 1e-6 window missed and shipped into a live run.
    bound = float(t[-1]) * 10.0
    if tau >= bound * (1.0 - 1e-3):
        return float("inf"), chi2_flat, chi2_fit, n_dof, n_params
    return max(tau, 0.0), chi2_flat, chi2_fit, n_dof, n_params


def fit_joint_relaxation_time(series: dict, targets: dict, record_every: int,
                              names: tuple = LOCAL, n_boot: int = 100,
                              seed: int = 0) -> dict:
    """Joint relaxation-time fit across `names` sharing one tau, replacing
    both the discrete threshold-crossing t_therm AND the earlier
    per-observable-then-take-max version of the exponential fit. `series` is
    {name: [n_records, n_chains]}, `targets` is {name: exact value}.

    Returns a dict: tau, tau_err (chain-bootstrap, same resampling unit as
    `chain_bootstrap` elsewhere in this project), chi2_per_dof (from the
    FULL, non-bootstrapped fit -- report this in any table, per Detmold &
    Endres), n_dof.
    """
    n_records = series[names[0]].shape[0]
    n_chains = series[names[0]].shape[1]
    t = np.arange(n_records, dtype=float) * record_every

    def means_sems(sub: dict) -> tuple:
        m = {name: sub[name].mean(axis=1) for name in names}
        s = {name: np.maximum(sub[name].std(axis=1, ddof=1) / math.sqrt(sub[name].shape[1]), 1e-12)
             for name in names}
        return m, s

    m0, s0 = means_sems(series)
    tau_hat, chi2_flat, chi2_fit, n_dof, n_params = _fit_joint_once(t, m0, s0, targets, names)

    rng = np.random.default_rng(seed)
    boots = np.empty(n_boot)
    for i in range(n_boot):
        pick = rng.integers(0, n_chains, n_chains)
        sub = {name: series[name][:, pick] for name in names}
        m, s = means_sems(sub)
        boots[i] = _fit_joint_once(t, m, s, targets, names)[0]
    finite = boots[np.isfinite(boots)]
    if len(finite) > 3:
        q16, q84 = np.percentile(finite, [16, 84])
        tau_err = float((q84 - q16) / 2.0)
    elif len(finite) > 1:
        tau_err = float(finite.std())
    else:
        tau_err = float("nan")

    # Same significance gate as the single-observable version, and for the
    # same reason: autocorrelated MC-time residuals can beat the delta-chi2
    # test even jointly across observables, and the chain bootstrap is not
    # fooled the same way.
    if math.isfinite(tau_hat) and tau_hat > 0 and math.isfinite(tau_err):
        if tau_err <= 0 or tau_hat / tau_err < 2.0:
            tau_hat = 0.0

    # Report chi2/dof of the FLAT null (n_params=0) when no decay was
    # resolved (tau=0) or the fit saturated the bound (tau=inf) -- the
    # exponential fit's own chi2 is meaningless in both cases (respectively:
    # unused, since the flat model won; or a degenerate boundary fit), and
    # Detmold & Endres' quoted 0.6-2.1 range is for genuine resolved fits.
    if tau_hat == 0.0 or math.isinf(tau_hat):
        dof = max(n_dof, 1)
        chi2_per_dof = chi2_flat / dof
    else:
        dof = max(n_dof - n_params, 1)
        chi2_per_dof = chi2_fit / dof
    return {"tau": tau_hat, "tau_err": tau_err,
           "chi2_per_dof": chi2_per_dof, "n_dof": dof}


def observe(links: torch.Tensor) -> dict:
    with torch.no_grad():
        return {
            # half_retr collapses the group axis, so every observable is
            # [batch, L, L] and the per-configuration mean is over (1, 2).
            "plaquette": half_retr(plaquette(links)).mean(dim=(1, 2)),
            "wilson_2x2": half_retr(wilson_loop(links, 2, 2)).mean(dim=(1, 2)),
            "wilson_4x4": half_retr(wilson_loop(links, 4, 4)).mean(dim=(1, 2)),
            "charge": topological_charge(links),
        }


def run_arm(sampler, links, n_traj: int, record_every: int) -> dict:
    series = {k: [] for k in (*LOCAL, "charge")}
    for step in range(n_traj):
        links, _ = sampler.metropolis_step(links)
        if step % record_every == 0:
            obs = observe(links)
            for k in series:
                series[k].append(obs[k].cpu().numpy())
    return {k: np.asarray(v) for k, v in series.items()}, links


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="u2_2d/configs/default.yaml")
    parser.add_argument("--device", default=None)
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--data-dir", default="out/u2_2d/data_v2")
    parser.add_argument("--fine-size", type=int, default=32)
    parser.add_argument("--n-chains", type=int, default=64)
    parser.add_argument("--n-traj", type=int, default=400)
    # A UNIFORM budget is unaffordable here: n_steps scales as sqrt(beta), so the
    # top coupling costs 12x the bottom one and a flat 400 trajectories puts a
    # single round at 4.7 h. u1 has the precedent -- its own lead figure carries
    # TWO budget ceilings from two scans and draws each arm's non-convergence
    # against its own ceiling. The same is done here: the budget falls with beta,
    # every coupling records the budget it actually got, and the figure draws it.
    # Nothing is lost, because the arms this shortens are the ones that do not
    # converge at ANY budget in this regime -- shortening turns "> 400" into
    # "> 150", which is a weaker true statement, not a false one.
    parser.add_argument("--traj-schedule", default="100:400,600:200,inf:150",
                        help="beta_f:n_traj breakpoints; 'none' for a flat budget")
    parser.add_argument("--record-every", type=int, default=2)
    parser.add_argument("--n-su2", type=int, default=30)
    parser.add_argument("--sampler-steps", type=int, default=200)
    parser.add_argument("--n-couplings", type=int, default=14)
    parser.add_argument("--betas", default=None,
                        help="comma-separated COARSE betas, overriding the "
                             "log-uniform selection; used to split the scan "
                             "across processes")
    parser.add_argument("--seed", type=int, default=4242)
    parser.add_argument("--out-dir", default="out/u2_2d/crossover")
    # THE SECOND ROUND. Every arm above runs PLAIN HMC, because mixing a
    # topological move into the baseline makes the ratio uninterpretable. But
    # plain HMC is not the honest classical baseline either -- that is HMC plus
    # the marginal odd winding move (docs/INSTANTON.md), which is genuinely
    # ergodic. So the scan is run TWICE, once each way, and the figure decides
    # which pair to draw rather than the scan deciding for it. Same seed in both
    # rounds, so the cold and hot initialisations are PAIRED and the difference
    # between the two files is the winding move and nothing else.
    parser.add_argument("--topological-updates", action="store_true",
                        help="run the winding round instead of the plain round")
    parser.add_argument("--winding-charge-step", type=int, default=1, choices=(1, 2))
    parser.add_argument("--winding-interval", type=int, default=5)
    parser.add_argument("--tag", default=None,
                        help="output stem; defaults to crossover / crossover_topo")
    args = parser.parse_args()

    config = load_config(args.config)
    device = resolve_device({"device": args.device or "auto"})
    print(configure_device(device))
    set_seed(args.seed)

    ckpt = args.checkpoint or config["train"].get(
        "checkpoint_path", "out/u2_2d/checkpoints/det_score_net.pt")
    model, sched = load_det_model(ckpt, device=device)
    print(f"checkpoint {ckpt}")

    # Available coarse bases. The retrain's random-beta training set left 65
    # L = 16 ensembles on disk, so the scan needs NO new base generation -- which
    # is the single reason this costs ~1 h instead of ~4.
    coarse_size = args.fine_size // 2
    bases = sorted(float(re.search(r"beta([0-9.]+)\.pt", f).group(1))
                   for f in glob.glob(f"{args.data_dir}/u2_L{coarse_size}_*.pt"))
    if not bases:
        print(f"no L={coarse_size} ensembles under {args.data_dir}")
        return 1
    # Log-uniform selection across the available range, so the scan spans the
    # crossover instead of clustering where the draws happened to be dense.
    if args.betas:
        chosen = sorted(min(bases, key=lambda b: abs(b - float(t)))
                        for t in args.betas.split(","))
    else:
        targets = np.exp(np.linspace(np.log(min(bases)), np.log(max(bases)),
                                     args.n_couplings))
        chosen = sorted({min(bases, key=lambda b: abs(math.log(b) - math.log(t)))
                         for t in targets})
    print(f"L_c = {coarse_size} -> L_f = {args.fine_size}; "
          f"{len(chosen)} couplings: " + ", ".join(f"{b:g}" for b in chosen))
    if args.topological_updates:
        print(f"WINDING round: charge_step={args.winding_charge_step}, "
              f"interval={args.winding_interval}")
    else:
        print("PLAIN round: no topological updates in any arm")

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = args.tag or ("crossover_topo" if args.topological_updates else "crossover")
    size = args.fine_size
    rows = []

    schedule = []
    if args.traj_schedule and args.traj_schedule.lower() != "none":
        for part in args.traj_schedule.split(","):
            cut, n = part.split(":")
            schedule.append((float(cut), int(n)))

    for base_beta in chosen:
        beta = topology_matched_fine_beta(base_beta, coarse_size)
        n_traj = args.n_traj
        for cut, n in schedule:
            if beta <= cut:
                n_traj = n
                break
        t0 = time.time()
        # The lift is ~40% of a coupling's cost and is IDENTICAL in the plain and
        # the winding round -- the seed does not know which sampler will consume
        # it. Cache it, so the second round pays for it once between them and a
        # re-run of either pays nothing.
        cache = out / "seeds" / f"seed_L{size}_beta{beta:g}_n{args.n_chains}.pt"
        if cache.exists():
            fine, _ = load_ensemble(cache)
            build_s = 0.0
        else:
            coarse, _ = load_ensemble(
                Path(args.data_dir) / f"u2_L{coarse_size}_beta{base_beta:g}.pt")
            coarse = coarse[:args.n_chains]
            # Only n_chains configurations are needed -- the arms run that many
            # chains -- so the lift is 16x cheaper here than stage 03's 1024.
            fine = generate_fine_from_coarse(
                model, sched, coarse, beta, n_su2_sweeps=args.n_su2, device=device,
                n_sampler_steps=args.sampler_steps, n_corrector_steps=1,
                batch_size=args.n_chains, consistency_weight=1.0,
                physics_blend_coef=0.0)
            build_s = time.time() - t0
            cache.parent.mkdir(parents=True, exist_ok=True)
            save_ensemble(cache, fine.cpu(), {"beta": beta, "lattice_size": size,
                                              "base_beta": base_beta})

        action = WilsonU2Action(beta)
        step_size, n_steps = adapted_hmc_params(beta)
        # wilson_loop_exact takes AREA, not extents: <W(A)> = r_fund^A.
        targets_exact = {
            "plaquette": plaquette_exact(beta, size),
            "wilson_2x2": wilson_loop_exact(beta, 4),
            "wilson_4x4": wilson_loop_exact(beta, 16),
        }
        qs, ps = det_topological_charge_distribution(beta, size)
        q2_exact = float((np.asarray(qs) ** 2 * np.asarray(ps)).sum())

        record = {"lattice_size": size, "beta": beta, "base_beta": base_beta,
                  "model_beta": matched_u1_beta(beta), "q_squared_exact": q2_exact,
                  "build_seconds": build_s, "n_traj": n_traj,
                  "t_therm": {}, "q_changes": {},
                  "parity_flips": {},
                  "topological_updates": bool(args.topological_updates),
                  "winding_charge_step": int(args.winding_charge_step),
                  "winding_interval": int(args.winding_interval)}

        # ALL THREE ARMS IN ONE BATCH -- the single biggest speed-up available
        # here, and it is free. U(2) batched HMC on this GPU is KERNEL-LAUNCH
        # bound, not compute bound: CLAUDE.md measures throughput FLAT at ~5
        # traj/s from L = 16 to L = 64, and nvidia-smi reports 77% "utilization"
        # at 54 W on a card that pulls twice that, which is what a GPU idling
        # between tiny launches looks like. Three arms run sequentially at 64
        # chains issue 3x the launches for the same arithmetic; concatenated into
        # one 192-chain batch they issue the launches ONCE and the extra work
        # rides along in kernels that were mostly empty.
        #
        # This is EXACT, not an approximation. `BatchedHMCU2` draws momenta
        # per chain and accepts/rejects per chain, and `winding_update` proposes
        # per chain, so a chain's trajectory does not depend on which other
        # chains share its batch. The arms stay statistically independent; only
        # the RNG interleaving differs, and that is not a physical difference.
        arms = ("diffusion seed", "cold start", "hot start")
        n = args.n_chains
        sampler = BatchedHMCU2(size, action, n_chains=len(arms) * n,
                               n_steps=n_steps, step_size=step_size,
                               device=device,
                               topological_updates=args.topological_updates,
                               winding_charge_step=args.winding_charge_step,
                               winding_interval=args.winding_interval)
        start = torch.cat([fine.to(device)[:n],
                           sampler.initialize(hot=False)[:n],
                           sampler.initialize(hot=True)[:n]], dim=0)
        all_series, _ = run_arm(sampler, start, n_traj, args.record_every)

        series_to_save = {}
        for i, arm in enumerate(arms):
            series = {k: v[:, i * n:(i + 1) * n] for k, v in all_series.items()}
            # JOINT fit across plaquette/W2x2/W4x4 sharing one tau -- Detmold
            # & Endres' "coupled multi-exponential fits ... with common
            # exponents" (PRD 92, 114516; PRD 94, 114502), which also
            # supersedes the earlier per-observable-then-take-max version:
            # a single joint tau IS the record's t_therm now, not a dict of
            # three numbers reduced by max().
            fit = fit_joint_relaxation_time(series, targets_exact, args.record_every)
            record["t_therm"][arm] = fit["tau"]
            record.setdefault("t_therm_err", {})[arm] = fit["tau_err"]
            record.setdefault("t_therm_chi2_per_dof", {})[arm] = fit["chi2_per_dof"]
            # Cross-check against the old discrete definition and the earlier
            # per-observable exponential fit -- logged, not used for anything
            # downstream. Lets a spot-check compare all three without
            # re-running HMC.
            record.setdefault("t_therm_threshold_old", {})[arm] = {
                name: thermalization_time(series[name], targets_exact[name])
                for name in LOCAL
            }
            record.setdefault("t_therm_per_observable", {})[arm] = {
                name: fit_relaxation_time(series[name], targets_exact[name],
                                          args.record_every)[0]
                for name in LOCAL
            }
            for name in (*LOCAL, "charge"):
                series_to_save[f"{arm}__{name}"] = series[name]
            q = np.round(series["charge"])
            record["q_changes"][arm] = int((np.diff(q, axis=0) != 0).sum())
            # Parity flips separately: the even winding move is mobile in charge
            # while being unable to change parity, so q_changes alone reports a
            # sampler as healthy while the odd/even balance is stuck.
            record["parity_flips"][arm] = int(
                (np.diff(q.astype(np.int64) % 2, axis=0) != 0).sum())
            # tau_int on the tail of EVERY arm, not just the cold one. The
            # yardstick is 2 tau_int of an EQUILIBRATED chain, and in the regime
            # this study targets the cold chain is not equilibrated even at the
            # end of its budget -- so its "tail" is a drift, and an
            # autocorrelation time fitted to a drift is not a decorrelation time.
            # tau_int is a property of the SAMPLER at that (L, beta), not of the
            # starting configuration, so the equilibrated diffusion-seeded chain
            # measures the same quantity and is the estimator that survives into
            # the frozen regime. Which one was used is recorded, not assumed.
            tail = series["plaquette"][len(series["plaquette"]) // 2:]
            taus = [integrated_autocorrelation_time(tail[:, c])[0]
                    for c in range(tail.shape[1])]
            finite = [t for t in taus if np.isfinite(t)]
            record.setdefault("tau_int_plaquette", {})[arm] = (
                float(np.median(finite)) * args.record_every if finite else None)

        seed, cold, hot = (record["t_therm"]["diffusion seed"],
                           record["t_therm"]["cold start"],
                           record["t_therm"]["hot start"])

        taus = record["tau_int_plaquette"]
        # Prefer the cold chain where it genuinely equilibrated with room to
        # spare -- that is u1's estimator and keeps the two studies comparable --
        # and fall back to the seeded chain where it did not.
        cold_ok = math.isfinite(cold) and cold < 0.5 * n_traj and taus.get("cold start")
        source = "cold start" if cold_ok else "diffusion seed"
        tau = taus.get(source)
        record["interval_source"] = source
        record["interval"] = 2.0 * tau if tau else None
        record["q_frozen"] = record["q_changes"]["cold start"] == 0
        # In the winding round the charge moves by construction, so the question
        # that separates a healthy sampler from a stuck one is PARITY, not charge.
        record["parity_frozen"] = record["parity_flips"]["cold start"] == 0
        if math.isinf(hot) and math.isinf(cold):
            record["regime"] = "HMC dead"
        elif record["q_frozen"] or record["parity_frozen"]:
            record["regime"] = "Q frozen" if record["q_frozen"] else "parity frozen"
        else:
            record["regime"] = "HMC healthy"
        best = min(hot, cold)
        record["speedup"] = best / max(seed, 1.0)
        record["speedup_is_bound"] = math.isinf(best)
        record["seed"], record["cold"], record["hot"] = seed, cold, hot
        rows.append(record)

        # Raw per-trajectory series, saved so a future change to the
        # thermalization/relaxation-time definition (like this one, replacing
        # the discrete threshold-crossing t_therm) can be REANALYSED without
        # redoing the HMC -- the exact gap that made switching definitions
        # mid-project costly this time (07_pq_sampling.py's --reanalyse is
        # the precedent). Small: ~n_records * n_chains * 4 observables *
        # 3 arms floats, kilobytes not megabytes.
        series_dir = out / "series"
        series_dir.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(series_dir / f"{stem}_beta{beta:g}.npz",
                            record_every=args.record_every, **series_to_save)

        print(f"  b={beta:8.2f} (model {record['model_beta']:6.2f}) "
              f"<Q^2>ex={q2_exact:5.3f}  seed={seed:6.1f} cold={cold:6.1f} "
              f"hot={hot:6.1f}  n={n_traj:4d}  "
              f"iv={(record['interval'] or float('nan')):5.1f}"
              f"({record['interval_source'][:4]})  "
              f"flips={record['parity_flips']['cold start']:5d}  "
              f"{record['regime']:13s} [{time.time() - t0:.0f}s]", flush=True)
        save_json(out / f"{stem}.json", rows)

    save_json(out / f"{stem}.json", rows)
    print(f"wrote {out / (stem + '.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
