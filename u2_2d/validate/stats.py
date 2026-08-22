"""Autocorrelation-aware error bars, ported from `u1_2d.validate.stats`.

WHY THIS EXISTS. u2 scored everything with a naive across-configuration SEM,
`sigma / sqrt(N)`, which assumes independent draws. The configurations are not
independent: an ensemble comes from a small number of HMC chains, and a lifted
ensemble inherits whatever correlation its coarse input carried. A naive SEM is
then too SMALL, so every |z| computed from it is too LARGE.

That is not a cosmetic difference. u1 adopted the correction as NARRATIVE 25.7 /
M4 and it changed conclusions there; `docs/PARITY_U1_U2.md` section 5 item 3
records the u2 symptom -- extended-loop `mean |z|` of 0.187 in the capacity
comparisons, against a null value of `sqrt(2/pi) = 0.798` for a model that is
exactly right. A score four times "better than perfect" is not a good model, it
is a mis-specified error bar, and the sign of the discrepancy (too small, not
too large) is the opposite of what naive-SEM inflation predicts -- so BOTH
effects are present and they must be separated by fixing the estimator rather
than by arguing about it.

The two estimators combined here, exactly as in u1:

  * a BINNED error, which is robust to mild autocorrelation but blind to
    correlation longer than one bin; and
  * where chain structure is known, the naive SEM inflated by `sqrt(2 tau_int)`,
    using the mean per-chain `tau_int`.

The larger of the two is returned, so the binned value acts as a floor.

NOTE THE ORDERING CONTRACT. `chain_tau_int` assumes the series is chain-major
per draw (index = draw * n_chains + chain), which is what `run_hmc_ensemble`
produces. Computing `tau_int` on the interleaved ordering instead reads ~0.5
whatever the true autocorrelation is, because correlated samples sit `n_chains`
apart -- a silent failure that returns a plausible number.
"""
from __future__ import annotations

import math

import numpy as np


def integrated_autocorrelation_time(
    series: np.ndarray, c_window: float = 6.0
) -> tuple[float, float]:
    """Madras-Sokal windowed tau_int, window W the smallest with W >= c * tau(W).

    Returns (tau_int, error); tau_int = 0.5 for an uncorrelated series.
    """
    series = np.asarray(series, dtype=float)
    n = len(series)
    centered = series - series.mean()
    var = float(np.dot(centered, centered) / n) if n else 0.0
    if var == 0 or n < 8:
        return 0.5, 0.0
    max_lag = n // 4
    rho = np.empty(max_lag)
    for lag in range(1, max_lag + 1):
        rho[lag - 1] = np.dot(centered[:-lag], centered[lag:]) / ((n - lag) * var)
    tau = 0.5
    window = max_lag
    for lag in range(1, max_lag + 1):
        tau += rho[lag - 1]
        if lag >= c_window * tau:
            window = lag
            break
    err = tau * math.sqrt(2.0 * (2.0 * window + 1.0) / n)
    return float(max(tau, 0.5)), float(err)


def binned_mean_err(values: np.ndarray, n_bins: int = 20) -> tuple[float, float]:
    """Mean and error from binning. A floor, not a substitute: fixed `n_bins` is
    blind to autocorrelation longer than the bin length."""
    values = np.asarray(values, dtype=float)
    if len(values) < 2:
        return (float(values.mean()) if len(values) else 0.0), 0.0
    n_bins = min(n_bins, max(2, len(values) // 2))
    bins = np.array_split(values, n_bins)
    means = np.array([b.mean() for b in bins])
    return float(values.mean()), float(means.std(ddof=1) / math.sqrt(len(means)))


def chain_tau_int(values: np.ndarray, n_chains: int) -> float:
    """Mean per-chain tau_int for a chain-major series (see the module note)."""
    values = np.asarray(values, dtype=float)
    n_draws = len(values) // max(n_chains, 1)
    if n_draws < 8:
        return 0.5
    per_chain = values[: n_draws * n_chains].reshape(n_draws, n_chains)
    taus = [integrated_autocorrelation_time(per_chain[:, c])[0]
            for c in range(n_chains)]
    return float(max(float(np.mean(taus)), 0.5))


def autocorr_aware_mean_err(
    values: np.ndarray, n_chains: int | None = None, n_bins: int = 20
) -> tuple[float, float, float]:
    """Mean, error and tau_int. Binned error is the floor; where chain structure
    is known and per-chain tau_int is measurable, the naive SEM inflated by
    `sqrt(2 tau_int)` replaces it wherever larger (n_eff = N / 2 tau; chains are
    independent, so the inflation applies to the pooled SEM)."""
    values = np.asarray(values, dtype=float)
    mean, err = binned_mean_err(values, n_bins)
    naive = values.std(ddof=1) / math.sqrt(max(len(values), 2))
    tau = 0.5
    if n_chains and len(values) >= 8 * n_chains:
        tau = chain_tau_int(values, n_chains)
        err = max(err, naive * math.sqrt(2.0 * tau))
    elif n_chains:
        # FEWER THAN 8 DRAWS PER CHAIN: tau_int is not measurable, and more to
        # the point there is usually nothing to measure. A u2 ladder ensemble is
        # 1024 configurations from 1024 chains -- ONE draw each, so the
        # configurations are independent by construction and `sigma / sqrt(N)`
        # is exactly right.
        #
        # Falling through to the binned error here is a real cost, not a
        # conservative default (measured 2026-08-22): on the deployed ladder it
        # returned generated-side errors 6-10% LARGER than the naive SEM, purely
        # because a 20-bin estimator has ~16% relative noise of its own. That
        # shrinks every z for a statistical rather than a physical reason, and it
        # pushes `mean |z|` further below the half-normal null of sqrt(2/pi) --
        # i.e. it makes the scorecard look better by making the error bars worse.
        # The binned value is kept as a floor in case the ordering does carry
        # structure, but the naive SEM is no longer discarded.
        err = max(err, naive) if len(values) < 4 * n_bins else naive
    return mean, float(err), tau


def null_mean_abs_z() -> float:
    """The value `mean |z|` takes when the model is EXACTLY right and the error
    bars are correct: |z| is then half-normal with mean sqrt(2/pi) = 0.798.

    Provided as a function because it is the number every `mean |z|` in this
    project should be read against, and it was not being read against anything.
    A scorecard well BELOW it indicates overestimated errors or correlated
    observables, not a good model.
    """
    return math.sqrt(2.0 / math.pi)


def effective_observable_count(per_config: dict) -> float:
    """How many INDEPENDENT observables a scorecard really contains.

    WHY THIS IS NEEDED. `mean |z|` over a set of observables is routinely read
    against the half-normal null of `sqrt(2/pi) = 0.798`, and the standard error
    of that mean is `sqrt(1 - 2/pi) / sqrt(N)`. Using the RAW count for N assumes
    the observables are independent draws. In this project they are emphatically
    not: at L = 32 the 41 scored observables have a correlation matrix whose top
    eigenvalue is 18.6 -- one mode carries 45% of the variance -- and a mean
    within-family |correlation| of 0.62, because 2D Wilson loops of different
    sizes are near-deterministic functions of one another.

    The measured effective count there is **3.77**, so the SE of `mean |z|` is
    0.31 rather than 0.09. Three claims made in this project were wrong by that
    factor of 3.3 before it was measured: a validation `mean |z|` of 0.484 read
    as 3.3 sigma below null is really 1.0; a capacity-comparison 0.187 read as
    6.5 sigma is really 2.0; and a sector-ablation null quoted as excluding
    effects above 0.27 really excludes only those above 0.88.

    The estimator is the participation ratio of the correlation matrix's
    eigenvalues, `(sum lambda)^2 / sum lambda^2`, which is 1 for perfectly
    correlated observables and N for independent ones.

    `per_config` maps observable name -> per-configuration values, i.e. exactly
    what `measure_ensemble` returns; non-scalar entries are ignored.
    """
    import numpy as np

    rows, n = [], None
    for k, v in per_config.items():
        a = np.asarray(v)
        # Ragged and non-scalar entries (angle fields, correlators) are not
        # per-configuration scalars and must be dropped BEFORE stacking, or the
        # stack raises on the inhomogeneous shape.
        if a.ndim != 1 or a.dtype == object or a.size <= 2:
            continue
        a = a.astype(float)
        if n is None:
            n = a.size
        if a.size == n:
            rows.append(a)
    if len(rows) < 2:
        return float(len(rows))
    m = np.asarray(rows)
    m = m[m.std(axis=1) > 0]
    if len(m) < 2:
        return float(len(m))
    ev = np.linalg.eigvalsh(np.corrcoef(m))
    ev = np.clip(ev, 0.0, None)
    denom = float((ev ** 2).sum())
    return float(ev.sum() ** 2 / denom) if denom > 0 else float(len(m))


def mean_abs_z_sigma(mean_abs_z: float, n_effective: float) -> float:
    """How many sigma a `mean |z|` sits from the null, at the EFFECTIVE count.

    Positive means below the null (scorecard "better than perfect", i.e. errors
    likely overestimated); negative means above it.
    """
    se = math.sqrt(1.0 - 2.0 / math.pi) / math.sqrt(max(n_effective, 1e-9))
    return (null_mean_abs_z() - mean_abs_z) / max(se, 1e-30)
