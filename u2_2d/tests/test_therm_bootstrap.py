"""The chain bootstrap on the equilibration crossing.

`t_therm` is a first-crossing index, so its point value hides two things: the
record spacing quantizes it, and the last chain to settle sets it. The bootstrap
exists to make the second visible. These tests pin the properties the figure
relies on, including the one failure mode the point estimate cannot express --
a crossing that exists in some resamples and not others.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from u2_2d.validate.stats import bootstrap_thermalization, thermalization_crossing


def _series(n_records: int, n_chains: int, target: float, *, decay: float,
            amplitude: float, noise: float, seed: int = 0) -> np.ndarray:
    """[n_records, n_chains] relaxing toward `target` with per-chain noise."""
    rng = np.random.default_rng(seed)
    t = np.arange(n_records)[:, None]
    mean = target + amplitude * np.exp(-t / decay) if decay > 0 else \
        np.full((n_records, 1), target)
    return mean + rng.normal(0.0, noise, size=(n_records, n_chains))


class TestCrossing:
    def test_already_at_target_returns_zero(self):
        s = _series(80, 64, 1.0, decay=0.0, amplitude=0.0, noise=0.01)
        assert thermalization_crossing({"o": s}, {"o": 1.0}) == 0.0

    def test_never_arrives_returns_infinity(self):
        s = _series(80, 64, 1.0, decay=0.0, amplitude=0.0, noise=0.01) + 5.0
        assert math.isinf(thermalization_crossing({"o": s}, {"o": 1.0}))

    def test_record_every_converts_to_trajectories(self):
        s = _series(80, 64, 1.0, decay=6.0, amplitude=1.0, noise=0.02, seed=3)
        one = thermalization_crossing({"o": s}, {"o": 1.0}, record_every=1.0)
        two = thermalization_crossing({"o": s}, {"o": 1.0}, record_every=2.0)
        assert two == pytest.approx(2.0 * one)

    def test_maximises_over_observables(self):
        fast = _series(80, 64, 1.0, decay=2.0, amplitude=1.0, noise=0.02, seed=1)
        slow = _series(80, 64, 1.0, decay=20.0, amplitude=1.0, noise=0.02, seed=2)
        both = thermalization_crossing({"f": fast, "s": slow}, {"f": 1.0, "s": 1.0})
        only_fast = thermalization_crossing({"f": fast}, {"f": 1.0})
        assert both >= only_fast


class TestBootstrap:
    def test_point_estimate_is_unchanged_by_bootstrapping(self):
        s = _series(80, 64, 1.0, decay=8.0, amplitude=1.0, noise=0.02, seed=4)
        out = bootstrap_thermalization({"o": s}, {"o": 1.0}, n_boot=100)
        assert out["t_therm"] == thermalization_crossing({"o": s}, {"o": 1.0})

    def test_band_brackets_the_point_estimate(self):
        s = _series(120, 64, 1.0, decay=10.0, amplitude=1.0, noise=0.03, seed=5)
        out = bootstrap_thermalization({"o": s}, {"o": 1.0}, n_boot=200, seed=7)
        assert out["lo"] <= out["median"] <= out["hi"]
        assert out["never_fraction"] == 0.0

    def test_one_lagging_chain_widens_the_band(self):
        """The failure the point estimate hides: the crossing is set by the
        slowest chain, so a single laggard moves it without any warning."""
        clean = _series(120, 64, 1.0, decay=5.0, amplitude=1.0, noise=0.02, seed=8)
        lagged = clean.copy()
        lagged[:, 0] += 3.0 * np.exp(-np.arange(120) / 60.0)
        tight = bootstrap_thermalization({"o": clean}, {"o": 1.0}, n_boot=200, seed=9)
        wide = bootstrap_thermalization({"o": lagged}, {"o": 1.0}, n_boot=200, seed=9)
        assert (wide["hi"] - wide["lo"]) > (tight["hi"] - tight["lo"])

    def test_marginal_crossing_reports_a_never_fraction(self):
        """A crossing that survives only some resamples is not the same
        measurement as one that survives all of them, and must say so."""
        rng = np.random.default_rng(11)
        noise, n_chains = 0.02, 64
        s = np.full((60, n_chains), 1.0) + rng.normal(0.0, noise, size=(60, n_chains))
        # a bias near the 2-sigma gate itself: whether the band is cleared at all
        # then depends on which chains the resample happens to draw
        s += 1.9 * noise / math.sqrt(n_chains)
        out = bootstrap_thermalization({"o": s}, {"o": 1.0}, n_boot=300, seed=2)
        assert 0.0 < out["never_fraction"] < 1.0

    def test_is_reproducible_for_a_fixed_seed(self):
        s = _series(80, 64, 1.0, decay=7.0, amplitude=1.0, noise=0.02, seed=12)
        a = bootstrap_thermalization({"o": s}, {"o": 1.0}, n_boot=150, seed=3)
        b = bootstrap_thermalization({"o": s}, {"o": 1.0}, n_boot=150, seed=3)
        assert a == b
