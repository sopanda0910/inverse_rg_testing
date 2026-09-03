"""Regression tests for `fit_relaxation_time` (u1_2d/validate/stats.py),
ported verbatim from u2_2d/scripts/28_crossover_scan.py on 2026-09-03 so
u1 and u2 are evaluated with the SAME t_therm estimator rather than two
methods that happen to agree in spirit -- see u1_2d/scripts/05_hmc_thermalization.py's
`t_therm_threshold_old` comment and CLAUDE.md's "Thermalization /
relaxation-time definition" entry.

These mirror u2_2d/tests/test_relaxation_time.py's synthetic cases exactly
(same failure modes the estimator has to handle correctly, since the code is
identical): already-equilibrated, genuine decay at two timescales, never
converges, a flat series with scattered noise excursions that must not fool
the delta-chi2 test, and a flat-but-BIASED series that must report inf (not
0) via the chain-resampling tail-bias check. u2's copies of these tests are
partly built from REAL HMC output that exposed real bugs; u1 has not yet had
its own crossover-scan run under this estimator to produce equivalent real
fixtures, so these are synthetic reproductions of the same shapes. If a u1
run ever exposes its own real failure case, replace the relevant synthetic
test with that fixture, matching u2's convention.
"""
import math

import numpy as np
import pytest

from u1_2d.validate.stats import fit_relaxation_time


def _make_series(rng, n_records, n_chains, target, amplitude, tau, noise):
    t = np.arange(n_records)
    if tau is None:
        mean_traj = np.full(n_records, target + amplitude)
    else:
        mean_traj = target + amplitude * np.exp(-t / tau)
    return mean_traj[:, None] + rng.normal(0, noise, size=(n_records, n_chains))


def test_already_equilibrated_returns_zero():
    rng = np.random.default_rng(0)
    series = _make_series(rng, 100, 64, target=0.5, amplitude=0.0, tau=None, noise=0.01)
    tau, err = fit_relaxation_time(series, 0.5, n_boot=100, seed=1)
    assert tau == 0.0
    assert err < 5.0


def test_genuine_slow_decay_recovered():
    rng = np.random.default_rng(0)
    series = _make_series(rng, 100, 64, target=0.5, amplitude=0.8, tau=10.0, noise=0.02)
    tau, err = fit_relaxation_time(series, 0.5, n_boot=100, seed=2)
    assert abs(tau - 10.0) < 1.0
    assert err < 1.0


def test_genuine_fast_decay_recovered():
    rng = np.random.default_rng(0)
    series = _make_series(rng, 100, 64, target=0.5, amplitude=0.8, tau=1.0, noise=0.02)
    tau, err = fit_relaxation_time(series, 0.5, n_boot=100, seed=4)
    assert abs(tau - 1.0) < 0.5


def test_never_converges_returns_inf():
    rng = np.random.default_rng(0)
    series = _make_series(rng, 100, 64, target=0.5, amplitude=0.5, tau=None, noise=0.01)
    tau, err = fit_relaxation_time(series, 0.5, n_boot=100, seed=3)
    assert math.isinf(tau)


def test_flat_series_with_scattered_noise_excursions_is_not_fooled():
    """The delta-chi2 test alone is fooled by autocorrelated-looking chance
    structure in pure noise (verified on real HMC output in u2); the chain-
    bootstrap significance gate is the second, decisive defense. Reproduces
    the shape that fooled the chi2 test alone in u2 (chi2/dof ~= 1.0-1.5)."""
    rng = np.random.default_rng(42)
    series = _make_series(rng, 75, 64, target=0.9886, amplitude=0.0, tau=None,
                          noise=0.0003)
    tau, err = fit_relaxation_time(series, 0.9886, n_boot=100, seed=6)
    assert tau == 0.0, (
        f"got tau={tau} -- a flat series should never fit a resolved decay, "
        "regardless of scattered per-record noise excursions")


def test_flat_but_biased_series_is_inf_not_zero():
    """The bug found 2026-09-03 in u2 (cov60 beta=414.90 cold start): a
    series that is flat but stuck significantly AWAY from target the whole
    window also has no decay to resolve, and must report inf (never
    converged), not 0.0 (already converged) -- opposite conclusions. Ported
    fix: test the settled tail via chain-resampling bootstrap before
    accepting "no resolved decay" as "already at target"."""
    rng = np.random.default_rng(7)
    # Flat at 0.6, target 0.5 -- a persistent, resolved offset with no decay.
    series = _make_series(rng, 100, 64, target=0.6, amplitude=0.0, tau=None, noise=0.01)
    tau, err = fit_relaxation_time(series, 0.5, n_boot=100, seed=8)
    assert math.isinf(tau), (
        f"got tau={tau} -- a flat series sitting significantly away from "
        "target must report inf, not 0.0")


def test_boundary_saturation_is_reported_as_inf_not_a_huge_finite_number():
    """A fit that saturates its search bound (tau >= t[-1]*10) must report
    inf, never a huge finite number that looks like a real measurement --
    the RELATIVE tolerance fix ported from u2 (an absolute 1e-6 window missed
    a real case there: tau=3979.9999115 against bound 3980.0)."""
    rng = np.random.default_rng(9)
    # A very slow, barely-resolved decay that pushes the optimizer toward
    # the upper search bound.
    series = _make_series(rng, 50, 64, target=0.5, amplitude=0.3, tau=5000.0, noise=0.001)
    tau, err = fit_relaxation_time(series, 0.5, n_boot=50, seed=10)
    assert math.isinf(tau) or tau < 50.0 * 10.0 * (1.0 - 1e-3), (
        f"got tau={tau} -- must not report a value at/near the search bound "
        "as if it were a resolved measurement")
