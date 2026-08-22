"""Statistics used by `07_pq_sampling.py` to decide whether P(Q) is sampled.

These guard two corrections made on 2026-08-22, both of which changed published
verdicts, and one optimization that a verdict now depends on being exact.
"""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load(name: str):
    """Import a numerically-named script by path."""
    path = SCRIPTS / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def stage07():
    return _load("07_pq_sampling.py")


def _reference_bootstrap(per_chain, statistic, n_boot, seed):
    """The general chain bootstrap, written out, as the thing to match."""
    rng = np.random.default_rng(seed)
    n_chains = per_chain.shape[1]
    value = statistic(per_chain.reshape(-1))
    draws = np.empty(n_boot)
    for i in range(n_boot):
        pick = rng.integers(0, n_chains, n_chains)
        draws[i] = statistic(per_chain[:, pick].reshape(-1))
    return float(value), float(draws.std())


def test_mean_fast_path_matches_the_general_bootstrap(stage07):
    """The O(n_boot * n_chains) mean path is an IDENTITY, not an approximation.

    Every chain has the same length, so the mean over a resampled set of chains
    is the mean of those chains' means. If that ever stops holding -- ragged
    chains, a weighted mean -- the fast path must go, because `07`'s error bars
    and therefore its verdicts are computed through it.
    """
    rng = np.random.default_rng(11)
    per_chain = rng.normal(size=(120, 64))
    fast = stage07.chain_bootstrap(per_chain, np.mean, n_boot=500, seed=3)
    slow = _reference_bootstrap(per_chain, np.mean, n_boot=500, seed=3)
    assert fast[0] == pytest.approx(slow[0], rel=1e-12)
    assert fast[1] == pytest.approx(slow[1], rel=1e-9)


def test_bootstrap_error_tracks_chain_count_not_configuration_count(stage07):
    """A FROZEN chain must count as one independent charge however long it ran.

    This is the whole reason the bootstrap resamples chains: above the freezing
    threshold a chain never leaves its starting sector, so a naive SEM over
    configurations understates the error by sqrt(n_draws).
    """
    rng = np.random.default_rng(5)
    frozen_value = rng.integers(0, 2, size=(1, 32)).astype(float)
    long_run = np.repeat(frozen_value, 400, axis=0)
    short_run = np.repeat(frozen_value, 10, axis=0)
    _, err_long = stage07.chain_bootstrap(long_run, np.mean, n_boot=800, seed=1)
    _, err_short = stage07.chain_bootstrap(short_run, np.mean, n_boot=800, seed=1)
    # Same 32 independent charges either way, so the same error bar.
    assert err_long == pytest.approx(err_short, rel=1e-9)
    naive = long_run.std(ddof=1) / np.sqrt(long_run.size)
    assert err_long > 5 * naive


def test_odd_weight_error_is_not_a_quadrature_sum(stage07):
    """P(odd) must be bootstrapped directly, not summed in quadrature.

    The sector cells are multinomial and hence NEGATIVELY correlated, so adding
    their errors in quadrature overstates the error on their sum and shrinks
    every |odd_z| the script prints -- which made `PARITY-STUCK` too forgiving in
    exactly the regime it exists to catch. The direct bootstrap must come out
    SMALLER than the quadrature sum on data with several occupied sectors.
    """
    rng = np.random.default_rng(7)
    q_values = np.array([-2, -1, 0, 1, 2])
    probs = np.array([0.1, 0.2, 0.4, 0.2, 0.1])
    history = rng.choice(q_values, size=(200, 64), p=probs).astype(float)
    record = stage07.analyse(history, beta=28.0, size=16, seed=0)

    quadrature = np.sqrt(sum(s["err"] ** 2 for s in record["sectors"]
                             if int(s["q"]) % 2))
    assert record["odd_err"] > 0
    assert record["odd_err"] < quadrature
    assert record["odd_error_model"].startswith("chain bootstrap")


def test_parity_indicator_counts_negative_odd_charges(stage07):
    """-3 is odd. A parity built with a C-style remainder would call it even."""
    history = np.full((40, 8), -3.0)
    record = stage07.analyse(history, beta=28.0, size=16, seed=0)
    assert record["odd_measured"] == pytest.approx(1.0)


def _multinomial_history(rng, q_values, probs, n_draws, n_chains):
    return rng.choice(q_values, size=(n_draws, n_chains), p=probs).astype(float)


def test_goodness_of_fit_is_calibrated_on_its_own_null(stage07):
    """On data drawn FROM the target distribution the p-value must not reject.

    The statistic this replaced -- `sum_q z_q^2` compared against `n_sectors` --
    rejected 10% of true-null datasets at its own threshold, which is what made
    `DISAGREES` appear at L = 16, beta = 51.75 between two couplings that passed.
    A loose bound is used here so the test is about calibration rather than about
    the seed: at 60 replicas the 1% rejection rate has a wide binomial spread.
    """
    rng = np.random.default_rng(19)
    q_values = np.array([-2, -1, 0, 1, 2])
    probs = np.array([0.08, 0.22, 0.4, 0.22, 0.08])
    rejects = 0
    for _ in range(60):
        history = _multinomial_history(rng, q_values, probs, 150, 96)
        gof = stage07.sector_goodness_of_fit(history, q_values, probs,
                                             n_boot=300, seed=0)
        assert 0.0 < gof["gof_p"] <= 1.0
        rejects += gof["gof_p"] < 0.05
    assert rejects <= 9  # 5% nominal, generous headroom at 60 replicas


def test_goodness_of_fit_detects_a_wrong_distribution(stage07):
    """It must still have power, or calibration was bought by blindness."""
    rng = np.random.default_rng(23)
    q_values = np.array([-2, -1, 0, 1, 2])
    target = np.array([0.08, 0.22, 0.4, 0.22, 0.08])
    wrong = np.array([0.02, 0.16, 0.64, 0.16, 0.02])
    history = _multinomial_history(rng, q_values, wrong, 150, 96)
    gof = stage07.sector_goodness_of_fit(history, q_values, target,
                                         n_boot=300, seed=0)
    assert gof["gof_p"] < 0.01


def test_parity_stuck_is_a_flip_count_not_a_significance_gate(stage07):
    """The pathology is structural: a chain that never crosses the monodromy.

    Guards the 2026-08-22 rebuild. The old rule declared `PARITY-STUCK` from
    `|odd_z| > 2`, which at 256 chains x 300 draws fired on a 0.8% deviation in
    P(odd) measured on a chain with 45909 sector changes and no frozen chains --
    the opposite of stuck. Mobility and accuracy are different questions.
    """
    rng = np.random.default_rng(29)
    # Every chain pinned to even charges: sectors change constantly, parity never.
    history = rng.choice([-2.0, 0.0, 2.0], size=(200, 64), p=[0.25, 0.5, 0.25])
    record = stage07.analyse(history, beta=28.0, size=16, seed=0, gof_boot=200)
    assert record["parity_flips"] == 0
    assert record["parity_frozen_fraction"] == 1.0
    assert record["sector_changes"] > 0
    assert stage07.verdict(record) == "PARITY-STUCK"

    # A mobile chain with a tiny, even highly significant, odd-weight deviation
    # must NOT be called stuck.
    mobile = rng.choice([-1.0, 0.0, 1.0], size=(200, 64), p=[0.25, 0.5, 0.25])
    rec = stage07.analyse(mobile, beta=28.0, size=16, seed=0, gof_boot=200)
    assert rec["parity_flips"] > 0
    assert stage07.verdict(rec) != "PARITY-STUCK"


def test_verdict_reports_frozen_before_anything_else(stage07):
    """A chain that never leaves its sector cannot be evidence about P(Q)."""
    history = np.repeat(np.arange(64, dtype=float)[None, :] % 3 - 1, 200, axis=0)
    record = stage07.analyse(history, beta=28.0, size=16, seed=0, gof_boot=200)
    assert record["sector_changes"] == 0
    assert stage07.verdict(record) == "FROZEN"


def test_charge_conjugation_asymmetry_is_measured(stage07):
    """P(Q) must be exactly even in Q, and the test must not need a closed form.

    The action is invariant under U -> U*, which sends Q -> -Q, so any asymmetry
    is a sampler defect that cannot be blamed on the reference distribution.
    This is the sharpest diagnostic in the script for exactly that reason, and it
    is what resolved a p = 0.022 goodness-of-fit flag at L = 16, beta = 56 into a
    coherently signed residual (-1 low while +1 high) that no single sector
    showed at more than 1.6 sigma.
    """
    rng = np.random.default_rng(31)
    q_values = np.array([-2, -1, 0, 1, 2])

    symmetric = np.array([0.08, 0.22, 0.4, 0.22, 0.08])
    history = rng.choice(q_values, size=(300, 128), p=symmetric).astype(float)
    record = stage07.analyse(history, beta=28.0, size=16, seed=0, gof_boot=200)
    assert abs(record["charge_asymmetry_z"]) < 3.0

    skewed = np.array([0.04, 0.16, 0.4, 0.28, 0.12])
    history = rng.choice(q_values, size=(300, 128), p=skewed).astype(float)
    record = stage07.analyse(history, beta=28.0, size=16, seed=0, gof_boot=200)
    assert record["charge_asymmetry_z"] > 5.0


def test_goodness_of_fit_drops_the_sum_to_one_redundancy(stage07):
    """A near-null direction must not be inverted into a huge statistic.

    Sector frequencies are multinomial and sum to a constant, so the all-ones
    direction carries essentially no variance. A pseudo-inverse with a small
    `rcond` inverts it anyway, dividing a tiny mean offset by a tinier variance.
    Measured at L = 16, beta = 56 this produced X^2 = 51.6 (p = 0.0002) on data
    where no individual sector deviated by more than 1.2 sigma -- a `DISAGREES`
    with no disagreement in it, reproduced on a second independent seed. The fix
    is to drop one bin, which removes the redundancy exactly.

    The guard: on data drawn from the target, the reported bin count must be one
    more than the dimension actually used, and the statistic must stay of order
    its degrees of freedom rather than exploding.
    """
    rng = np.random.default_rng(37)
    q_values = np.array([-2, -1, 0, 1, 2])
    probs = np.array([0.009, 0.203, 0.575, 0.203, 0.010])
    probs = probs / probs.sum()
    worst = 0.0
    for _ in range(25):
        history = _multinomial_history(rng, q_values, probs, 300, 256)
        gof = stage07.sector_goodness_of_fit(history, q_values, probs,
                                             n_boot=400, seed=0)
        assert gof["gof_dof"] <= gof["gof_bins"] - 1
        worst = max(worst, gof["gof_chi2"])
    # Comfortably bounded: with the redundancy left in, this reached 51.6 on
    # real data of exactly this shape.
    assert worst < 40.0


def test_independent_draws_keep_the_naive_sem():
    """One draw per chain means the configurations ARE independent.

    A u2 ladder ensemble is 1024 configurations from 1024 chains, so `tau_int` is
    not measurable and there is nothing to correct: `sigma / sqrt(N)` is exact.
    Falling through to the 20-bin binned estimator instead cost 6-10% in the
    error bar on the deployed ladder -- noise in the estimator, not physics --
    and every z shrank with it, pushing `mean |z|` further below the half-normal
    null. Guard that the independent case returns the naive SEM.
    """
    import math

    from u2_2d.validate.stats import autocorr_aware_mean_err

    rng = np.random.default_rng(41)
    values = rng.normal(size=1024)
    naive = values.std(ddof=1) / math.sqrt(len(values))
    _, err, tau = autocorr_aware_mean_err(values, n_chains=1024)
    assert tau == 0.5
    assert err == pytest.approx(naive, rel=1e-12)


def test_autocorrelated_chains_still_inflate_the_error():
    """The correction must survive for ensembles that really are correlated.

    The u1-style measurement scripts run 16 chains with many draws each, which is
    where `sqrt(2 tau)` earns its keep. Removing the binned fallback for
    independent data must not weaken that path.
    """
    from u2_2d.validate.stats import autocorr_aware_mean_err

    rng = np.random.default_rng(43)
    n_chains, n_draws = 16, 128
    series = np.empty((n_draws, n_chains))
    series[0] = rng.normal(size=n_chains)
    for d in range(1, n_draws):                      # AR(1), rho = 0.8
        series[d] = 0.8 * series[d - 1] + rng.normal(size=n_chains) * 0.6
    values = series.reshape(-1)                      # chain-major
    naive = values.std(ddof=1) / np.sqrt(len(values))
    _, err, tau = autocorr_aware_mean_err(values, n_chains=n_chains)
    assert tau > 1.0
    assert err > 1.5 * naive
