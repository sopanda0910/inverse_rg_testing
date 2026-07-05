"""Statistics helpers: jackknife errors, integrated autocorrelation times, z-scores."""

import math

import numpy as np


def jackknife(values: np.ndarray, estimator=np.mean) -> tuple[float, float]:
    """Leave-one-out jackknife mean and error of `estimator` over axis 0."""
    values = np.asarray(values, dtype=float)
    n = len(values)
    if n < 2:
        return float(estimator(values)), float("inf")
    full = estimator(values)
    loo = np.array([estimator(np.delete(values, i, axis=0)) for i in range(n)])
    err = math.sqrt((n - 1) / n * np.sum((loo - loo.mean()) ** 2))
    return float(full), float(err)


def binned_mean_err(values: np.ndarray, n_bins: int = 20) -> tuple[float, float]:
    """Mean and error from binning (robust to mild autocorrelation)."""
    values = np.asarray(values, dtype=float)
    n_bins = min(n_bins, max(2, len(values) // 2))
    bins = np.array_split(values, n_bins)
    means = np.array([b.mean() for b in bins])
    return float(values.mean()), float(means.std(ddof=1) / math.sqrt(len(means)))


def integrated_autocorrelation_time(
    series: np.ndarray, c_window: float = 6.0
) -> tuple[float, float]:
    """Madras-Sokal windowed tau_int with automatic window W: smallest W >= c * tau(W).

    Returns (tau_int, error). tau_int = 0.5 for an uncorrelated series.
    """
    series = np.asarray(series, dtype=float)
    n = len(series)
    centered = series - series.mean()
    var = np.dot(centered, centered) / n
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


def z_score(value: float, error: float, reference: float, reference_error: float = 0.0) -> float:
    total_err = math.sqrt(error**2 + reference_error**2)
    if total_err == 0:
        return float("inf") if value != reference else 0.0
    return (value - reference) / total_err
