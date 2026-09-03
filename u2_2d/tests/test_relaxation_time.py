"""Regression tests for the exponential relaxation-time thermalization
estimator (`28_crossover_scan.py`'s `fit_relaxation_time` /
`fit_joint_relaxation_time`), which replaced the discrete threshold-crossing
`thermalization_time` on 2026-09-03.

These pin down several real failure modes found while building and running
the estimator, not hypothetical edge cases:

  * an "already at target" test that requires EVERY record to pass a 2-sigma
    band fails from pure multiple-testing noise over ~100 records;
  * a fixed initial guess for tau sends the nonlinear fit into a bad local
    minimum whenever the true decay is much faster than the guess;
  * a delta-chi2 goodness-of-fit test alone is fooled by autocorrelated
    Monte Carlo time series -- verified on REAL HMC output (a genuinely
    equilibrated seed's plaquette series, chi2/dof=1.28, fit to a fictitious
    tau~186 by the chi2 test alone; caught only by the chain-bootstrap
    significance gate). That real series is reproduced synthetically below
    (same shape: flat mean, small per-record noise, no true decay);
  * a fit that saturates its search bound (the optimizer settling ~1e-4
    short of the exact boundary) must report inf, not a huge finite number
    that looks like a real measurement -- caught live in the first ~8
    minutes of the full matrix run;
  * "no resolved decay" was conflated with "already at target" -- but a
    series that is flat and stuck significantly AWAY from target, with no
    detectable trend inside the window, also has no decay to resolve, and
    the old code called that tau=0.0 (instantly thermalized) instead of the
    correct tau=inf (never converged) -- found via the sanity monitor on a
    live run (cov60 beta=414.90, cold start, chi2_flat/dof=463.6).

Methodology reference: Detmold & Endres, "Multiscale Monte Carlo
equilibration" (PRD 92, 114516 (2015); PRD 94, 114502 (2016)) -- coupled
multi-exponential fits across observables with a shared exponent, reporting
chi2/dof as the fit-quality diagnostic.
"""
import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load(name: str):
    path = SCRIPTS / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def stage28():
    return _load("28_crossover_scan.py")


def _make_series(rng, n_records, n_chains, target, amplitude, tau, noise):
    t = np.arange(n_records) * 2.0
    if tau is None:
        mean_traj = np.full(n_records, target + amplitude)
    else:
        mean_traj = target + amplitude * np.exp(-t / tau)
    return mean_traj[:, None] + rng.normal(0, noise, size=(n_records, n_chains))


def test_already_equilibrated_returns_zero(stage28):
    """A seed that starts at (noisy) equilibrium must fit tau=0, not a
    discrete 0/1/2 -- and not the fictitious large tau the naive
    'every record within 2 sigma' test produced before the delta-chi2 +
    bootstrap-significance gate was added."""
    rng = np.random.default_rng(0)
    series = _make_series(rng, 100, 64, target=0.5, amplitude=0.0, tau=None, noise=0.01)
    tau, err = stage28.fit_relaxation_time(series, 0.5, record_every=2, n_boot=100, seed=1)
    assert tau == 0.0
    assert err < 5.0  # tight, not the ~160-280 the pre-fix version returned


def test_genuine_slow_decay_recovered(stage28):
    rng = np.random.default_rng(0)
    series = _make_series(rng, 100, 64, target=0.5, amplitude=0.8, tau=10.0, noise=0.02)
    tau, err = stage28.fit_relaxation_time(series, 0.5, record_every=2, n_boot=100, seed=2)
    assert abs(tau - 10.0) < 1.0
    assert err < 1.0


def test_genuine_fast_decay_recovered(stage28):
    """The case a fixed (t[-1]/4-scale) initial guess got badly wrong (fit
    tau=0.045 against a true tau=1) before the data-driven log-linear guess
    was added."""
    rng = np.random.default_rng(0)
    series = _make_series(rng, 100, 64, target=0.5, amplitude=0.8, tau=1.0, noise=0.02)
    tau, err = stage28.fit_relaxation_time(series, 0.5, record_every=2, n_boot=100, seed=4)
    assert abs(tau - 1.0) < 0.5


def test_never_converges_returns_inf(stage28):
    rng = np.random.default_rng(0)
    series = _make_series(rng, 100, 64, target=0.5, amplitude=0.5, tau=None, noise=0.01)
    tau, err = stage28.fit_relaxation_time(series, 0.5, record_every=2, n_boot=100, seed=3)
    assert math.isinf(tau)


def test_flat_series_with_scattered_noise_excursions_is_not_fooled(stage28):
    """Reproduces the real-data failure mode synthetically: a flat, already-
    equilibrated series with chi2/dof close to 1 (a handful of records
    exceed 2 sigma by chance, scattered across the whole window, exactly as
    expected from multiple testing) must still return tau=0. This is the
    case where the delta-chi2 test alone was fooled (fit tau ~ 186 on real
    HMC data) and the significance gate was added specifically to catch it.
    """
    rng = np.random.default_rng(42)
    # Tuned to reproduce chi2/dof ~= 1.0-1.5 with 75 records, matching the
    # real measured series (chi2/dof = 1.28).
    series = _make_series(rng, 75, 64, target=0.9886, amplitude=0.0, tau=None,
                          noise=0.0003)
    tau, err = stage28.fit_relaxation_time(series, 0.9886, record_every=2,
                                           n_boot=100, seed=6)
    assert tau == 0.0, (
        f"got tau={tau} -- a flat series should never fit a resolved decay, "
        "regardless of scattered per-record noise excursions")


def test_boundary_saturation_is_reported_as_inf_not_a_huge_finite_number(stage28):
    """A SECOND real-data failure, found live in the first ~8 minutes of the
    full matrix run this estimator was built for: the optimizer's own
    convergence tolerance settles ~8.9e-5 SHORT of the exact upper search
    bound (tau=3979.9999115 against a bound of 3980.0 for a 400-trajectory
    coupling), which an absolute `tau >= bound - 1e-6` saturation check does
    not catch -- it shipped a nonsensical "seed thermalizes in ~3980
    trajectories" (more than the entire trajectory budget) into a live run
    before being caught. Fixed with a RELATIVE tolerance
    (`tau >= bound * (1 - 1e-3)`). This fixture is the exact real series
    (checkpoint det_score_net_cov60, beta=13.856, diffusion-seed arm,
    400-trajectory plain round) that triggered it.
    """
    from u2_2d.lgt.exact import plaquette_exact, wilson_loop_exact

    npz = np.load(FIXTURES / "boundary_saturation_case.npz")
    names = ("plaquette", "wilson_2x2", "wilson_4x4")
    series = {name: npz[f"diffusion seed__{name}"] for name in names}
    beta = 13.856006078289337
    targets = {"plaquette": plaquette_exact(beta, 32),
              "wilson_2x2": wilson_loop_exact(beta, 4),
              "wilson_4x4": wilson_loop_exact(beta, 16)}
    result = stage28.fit_joint_relaxation_time(series, targets, record_every=2,
                                               names=names, n_boot=50, seed=0)
    assert math.isinf(result["tau"]), (
        f"got tau={result['tau']} -- a fit that saturates its search bound "
        "must report inf (unresolved), never a huge finite number that "
        "looks like a real measurement")


def test_flat_but_biased_series_is_inf_not_zero(stage28):
    """A THIRD real-data failure, found 2026-09-03 via the sanity monitor
    flagging a diffusion-seed record at a DIFFERENT coupling, which led to
    checking the arm actually responsible: cov60 beta=414.90, COLD START.
    The delta-chi2 test only asks whether an exponential fits better than
    "already at target" -- when the series is flat but stuck significantly
    away from target, with no detectable time-trend inside the window, that
    question's honest answer is "no" (there is no trend to fit), and the old
    code took that as "already at target" (tau=0.0). It is the opposite
    conclusion: chi2_flat/dof = 463.6 here, and the independent old
    threshold method agrees this arm's plaquette never resolved at all
    (Infinity). A first fix attempt tested chi2_flat itself against a plain
    chi2 critical value and was WRONG the same way the original delta-chi2
    gate was: it flagged a genuinely-equilibrated synthetic series as
    "stuck" too (see test_already_equilibrated_returns_zero), because
    chi2_flat is fooled by within-chain autocorrelation just like chi2_exp
    is. The fix instead tests the settled TAIL (second half of the window)
    via the same chain-resampling bootstrap already used for tau_err
    (`_tail_is_biased`). This fixture is the exact real series that exposed
    the bug (checkpoint det_score_net_cov60, beta=414.897, cold start,
    200-trajectory plain round).
    """
    from u2_2d.lgt.exact import plaquette_exact, wilson_loop_exact

    npz = np.load(FIXTURES / "stuck_flat_bias_case.npz")
    names = ("plaquette", "wilson_2x2", "wilson_4x4")
    series = {name: npz[f"cold start__{name}"] for name in names}
    beta = 414.8972549121468
    targets = {"plaquette": plaquette_exact(beta, 32),
              "wilson_2x2": wilson_loop_exact(beta, 4),
              "wilson_4x4": wilson_loop_exact(beta, 16)}
    result = stage28.fit_joint_relaxation_time(series, targets, record_every=2,
                                               names=names, n_boot=50, seed=0)
    assert math.isinf(result["tau"]), (
        f"got tau={result['tau']} -- a flat series sitting significantly "
        "away from target, with no resolved decay, must report inf (never "
        "converged), not 0.0 (already converged) -- those are opposite "
        "conclusions")


def test_joint_fit_shared_tau_across_observables(stage28):
    """Detmold & Endres' coupled multi-exponential fit: three observables
    genuinely decaying with the SAME tau should recover it, with chi2/dof
    near 1 for a correctly-specified shared-tau model."""
    rng = np.random.default_rng(0)
    names = ("plaquette", "wilson_2x2", "wilson_4x4")
    targets = {"plaquette": 0.5, "wilson_2x2": 0.3, "wilson_4x4": 0.1}
    amps = {"plaquette": 0.8, "wilson_2x2": 0.5, "wilson_4x4": 0.2}
    series = {name: _make_series(rng, 100, 64, targets[name], amps[name], 10.0, 0.02)
              for name in names}
    result = stage28.fit_joint_relaxation_time(series, targets, record_every=2,
                                                names=names, n_boot=100, seed=1)
    assert abs(result["tau"] - 10.0) < 1.0
    assert 0.5 < result["chi2_per_dof"] < 2.5


def test_joint_fit_already_equilibrated_returns_zero(stage28):
    rng = np.random.default_rng(1)
    names = ("plaquette", "wilson_2x2", "wilson_4x4")
    targets = {"plaquette": 0.5, "wilson_2x2": 0.3, "wilson_4x4": 0.1}
    series = {name: _make_series(rng, 100, 64, targets[name], 0.0, None, 0.01)
              for name in names}
    result = stage28.fit_joint_relaxation_time(series, targets, record_every=2,
                                                names=names, n_boot=100, seed=2)
    assert result["tau"] == 0.0
    assert 0.5 < result["chi2_per_dof"] < 2.0


def test_joint_fit_never_converges_returns_inf(stage28):
    rng = np.random.default_rng(2)
    names = ("plaquette", "wilson_2x2", "wilson_4x4")
    targets = {"plaquette": 0.5, "wilson_2x2": 0.3, "wilson_4x4": 0.1}
    series = {name: _make_series(rng, 100, 64, targets[name], 0.3, None, 0.01)
              for name in names}
    result = stage28.fit_joint_relaxation_time(series, targets, record_every=2,
                                                names=names, n_boot=100, seed=3)
    assert math.isinf(result["tau"])
