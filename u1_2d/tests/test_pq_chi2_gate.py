"""The P(Q) chi^2 gate must never disappear (review item M3).

The failure this pins down is a silent one: the old gate emitted no row unless
at least two bins had expected > 2 and observed counts landed in them, so an
ensemble whose charge sits outside the well-populated support produced a blank
cell that rendered as "-" -- read as "not applicable" when it meant "wrong".
Every test here is therefore about the row EXISTING and carrying a verdict, not
about the value of the statistic.
"""

import numpy as np

from u1_2d.lgt import exact
from u1_2d.validate.report import _pq_chi2_row, _q_histogram


def _setup(beta=14.1464, L=32, action="wilson"):
    q_values, q_probs = exact.topological_charge_distribution(beta, L, action)
    return q_values, q_probs


def _row(charges, q_values, q_probs, tau=0.5):
    charges = np.asarray(charges, dtype=float)
    counts = _q_histogram(charges, q_values)
    return _pq_chi2_row(charges, q_values, counts, q_probs * len(charges), tau)


def test_row_is_emitted_for_a_healthy_ensemble():
    q_values, q_probs = _setup()
    rng = np.random.default_rng(0)
    charges = rng.choice(q_values, size=4000, p=q_probs / q_probs.sum())
    row = _row(charges, q_values, q_probs)
    assert "chi2_p" in row and np.isfinite(row["chi2_p"])
    assert row["chi2_p"] > 1e-3, "a correctly drawn sample should not be rejected"


def test_all_charge_outside_support_fails_loudly_instead_of_vanishing():
    """The M3 case: every configuration in a sector the exact P(Q) never visits.

    The old gate emitted nothing here. The row must now exist and reject.
    """
    q_values, q_probs = _setup(beta=218.58)
    charges = np.full(500, float(q_values.max()) + 5.0)
    row = _row(charges, q_values, q_probs)
    assert "chi2_p" in row
    assert row["chi2_p"] == 0.0


def test_untestable_sample_size_says_so_explicitly():
    """Too few configurations for any bin to be testable -> a stated failure."""
    q_values, q_probs = _setup(beta=218.58)
    row = _row(np.zeros(2), q_values, q_probs)
    assert row["chi2_p"] == 0.0
    assert "FAIL" in row.get("chi2_note", "")


def test_out_of_support_charge_is_counted_not_discarded():
    """_q_histogram drops charge outside q_values; pooling must recover it."""
    q_values, q_probs = _setup()
    rng = np.random.default_rng(1)
    good = rng.choice(q_values, size=2000, p=q_probs / q_probs.sum())
    clean = _row(good, q_values, q_probs)
    contaminated = _row(np.concatenate([good, np.full(300, q_values.max() + 3.0)]),
                        q_values, q_probs)
    assert clean["chi2_p"] > contaminated["chi2_p"]
    assert contaminated["chi2_p"] < 1e-6, "300 impossible configurations must reject"


def test_many_small_expectation_bins_pool_into_a_verdict():
    """Individually untestable sectors are decisive in aggregate."""
    q_values, q_probs = _setup(beta=218.58)
    n = 400
    expected = q_probs * n
    tail = np.flatnonzero((expected > 0) & (expected < 2.0))
    assert tail.size >= 2, "fixture needs low-expectation bins to pool"
    # Pile counts into sectors the old gate would have dropped one by one.
    charges = np.concatenate([np.zeros(n - 60), np.full(60, float(q_values[tail[-1]]))])
    row = _row(charges, q_values, q_probs)
    assert np.isfinite(row["chi2_p"])
    assert row["chi2_p"] < 0.01


def test_dof_matches_the_number_of_cells_actually_used():
    q_values, q_probs = _setup()
    rng = np.random.default_rng(2)
    charges = rng.choice(q_values, size=3000, p=q_probs / q_probs.sum())
    row = _row(charges, q_values, q_probs)
    assert row["exact"] == len(row["chi2_bins"]) - 1


def test_autocorrelation_inflation_only_softens_the_verdict():
    """A deterministic, mild mismatch, so both p-values stay resolvable."""
    q_values, q_probs = _setup()
    n = 4000
    counts = np.floor(q_probs / q_probs.sum() * n).astype(int)
    mode = int(np.argmax(counts))
    counts[mode] -= 40
    counts[mode + 1] += 40
    charges = np.repeat(q_values, counts).astype(float)

    sharp = _row(charges, q_values, q_probs, tau=0.5)
    blunt = _row(charges, q_values, q_probs, tau=8.0)
    assert 0.0 < sharp["chi2_p"] < 1.0
    assert blunt["chi2_p"] > sharp["chi2_p"]
    assert blunt["value"] == sharp["value"], "tau must not change the statistic"
