"""Statistics helpers: jackknife errors, integrated autocorrelation times,
z-scores, exponential relaxation fits."""

import math

import numpy as np
from scipy.optimize import curve_fit


def fit_exponential_relaxation(mean: np.ndarray, target: float) -> dict:
    """Fit C + A exp(-t/tau) to an ensemble-mean relaxation curve.

    Always attempts the fit (a curve that starts at its plateau -- e.g. a
    diffusion seed -- still gets a tau, flagged in `status` as amplitude within
    noise). tau is None only when the fit fails outright, the window is too
    short, or the fitted tau exceeds the window and is meaningless. C is the
    fitted plateau; `plateau_minus_target` says whether the curve relaxes
    toward the exact value or gets stuck away from it."""
    mean = np.asarray(mean, dtype=float)
    t = np.arange(len(mean), dtype=float)
    tail = mean[max(len(mean) // 2, 1):]
    c0, noise = float(tail.mean()), float(tail.std())
    a0 = float(mean[0] - c0)
    out = {"tau": None, "A": a0, "C": c0, "target": target,
           "plateau_minus_target": c0 - target, "status": "fit failed"}
    if len(mean) < 8:
        out["status"] = "window too short to fit"
        return out
    if float(np.std(mean)) < 1e-12 * max(1.0, abs(c0)):
        out["status"] = "constant series (no decay; frozen)"
        return out

    def model(t, A, tau, C):
        return C + A * np.exp(-t / tau)

    a_init = a0 if abs(a0) > 1e-12 else max(noise, 1e-6)
    try:
        popt, pcov = curve_fit(
            model, t, mean, p0=(a_init, max(len(mean) / 10.0, 2.0), c0),
            bounds=([-np.inf, 1e-2, -np.inf], [np.inf, 50.0 * len(mean), np.inf]),
            maxfev=20000,
        )
    except Exception as exc:
        out["status"] = f"fit failed ({type(exc).__name__})"
        return out
    A, tau, C = (float(v) for v in popt)
    tau_err = float(np.sqrt(pcov[1, 1])) if np.all(np.isfinite(pcov)) else float("inf")
    out.update(A=A, C=C, plateau_minus_target=C - target)
    if tau > 3.0 * len(mean):
        out["status"] = "unreliable (tau exceeds window)"
        return out
    if not math.isfinite(tau_err) or tau_err <= 0.0 or tau_err >= tau:
        out["status"] = ("no measurable decay (starts at plateau; tau unconstrained)"
                         if abs(A) <= 2.0 * max(noise, 1e-12)
                         else "unconstrained fit (tau error exceeds tau)")
        return out
    out.update(tau=tau, tau_error=tau_err)
    out["status"] = ("ok" if abs(A) > 2.0 * max(noise, 1e-12)
                     else "ok (amplitude within noise of plateau)")
    return out


# ---------------------------------------------------------------------------
# t_therm ESTIMATOR, ported verbatim (same gates, same thresholds, same fixed
# bugs) from u2_2d/scripts/28_crossover_scan.py on 2026-09-03, replacing the
# discrete threshold-crossing `thermalization_time` in
# u1_2d/scripts/05_hmc_thermalization.py. u1 and u2 must be evaluated with
# the SAME estimator unless a difference is explicitly justified (none is,
# here) -- see CLAUDE.md's "Thermalization / relaxation-time definition"
# entry for the full derivation, literature grounding (Detmold & Endres,
# PRD 92, 114516 (2015); PRD 94, 114502 (2016)), and the four real numerical
# bugs found and fixed while building/running it in u2. This is NOT
# `fit_exponential_relaxation` above: that fits a FREE plateau C (not fixed
# at the exact target) and reports curve_fit's own covariance-based error,
# neither of which is right for a "how long until the target is reached"
# estimator, and it has none of the four bug fixes below. It stays in this
# file only for the dashed-curve plot overlay, not for any t_therm number
# that feeds a claim.
#
# u1 records EVERY trajectory (`series[k].append(v)` each step, no
# subsampling), unlike u2's `record_every=2` -- so t = arange(len(mean))
# directly, no record_every parameter needed.
def _tail_is_biased(tails: list, rng: "np.random.Generator", n_chains: int,
                    n_boot: int = 200) -> bool:
    """True if ANY (tail_series, target) pair's settled tail (second half of
    the observation window) is significantly biased from its target, under a
    CHAIN-resampling bootstrap. See the matching function in
    u2_2d/scripts/28_crossover_scan.py for the full derivation: "no resolved
    decay" is ambiguous between "already at target" and "flat but stuck away
    from target the whole window", and a plain chi2 test on the full-window
    disagreement is fooled by within-chain autocorrelation the same way the
    delta-chi2 gate below would be; chain resampling is not.
    """
    for tail, target in tails:
        tail_mean = float(tail.mean())
        boots = np.empty(n_boot)
        for i in range(n_boot):
            pick = rng.integers(0, n_chains, n_chains)
            boots[i] = tail[:, pick].mean()
        tail_err = float(boots.std())
        if tail_err > 0 and abs(tail_mean - target) / tail_err >= 2.0:
            return True
    return False


def _fit_exp_once(t: np.ndarray, mean: np.ndarray, sem: np.ndarray,
                  target: float) -> tuple[float, float]:
    """One exponential relaxation-time fit: mean(t) ~= target + A*exp(-t/tau).
    Returns (tau, chi2_per_dof) -- tau is 0.0 if already at target, inf if no
    resolved decay within the window. See u2_2d/scripts/28_crossover_scan.py's
    `_fit_exp_once` for the full derivation of every gate below -- ported
    verbatim.

    chi2_per_dof ADDED 2026-09-06, porting u2's fix of the same date (found
    reanalysing u2's saved crossover series: a fit can clear the delta-chi2
    test below AND the bootstrap significance gate in the caller while still
    being an objectively bad description of the data -- chi2/dof ~40-9000 in
    the real case that motivated this, against Detmold & Endres' quoted
    0.6-2.1 healthy range -- because both existing gates test whether the
    exponential is SIGNIFICANTLY BETTER than flat/noise, not whether it is
    GOOD IN AN ABSOLUTE SENSE. u1 and u2 share this estimator, so u1 shares
    the gap and the fix, per this project's standing rule that the two
    studies not drift apart in methodology."""
    chi2_flat = float(np.sum(((mean - target) / sem) ** 2))
    n_dof_flat = max(len(t), 1)

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
        return 0.0, chi2_flat / n_dof_flat

    pred = target + popt[0] * np.exp(-t / max(popt[1], 1e-6))
    chi2_exp = float(np.sum(((mean - pred) / sem) ** 2))
    if chi2_flat - chi2_exp < 6.0:
        return 0.0, chi2_flat / n_dof_flat

    n_dof_fit = max(len(t) - 2, 1)
    chi2_per_dof = chi2_exp / n_dof_fit
    tau = float(popt[1])
    upper = float(t[-1]) * 10.0
    if tau >= upper * (1.0 - 1e-3):
        return float("inf"), chi2_flat / n_dof_flat
    # ABSOLUTE goodness-of-fit veto -- gate on chi2/dof itself, not a formal
    # p-value (a p-value gets arbitrarily strict as dof grows and flags
    # perfectly healthy fits; see u2's 28_crossover_scan.py for the measured
    # example of that exact mistake). NaN signals "resolved a decay the
    # bootstrap called significant, but the exponential model does not
    # actually describe this series" -- distinct from both 0.0 (already at
    # target) and inf (never converges).
    if chi2_per_dof > 5.0:
        return float("nan"), chi2_per_dof
    return max(tau, 0.0), chi2_per_dof


def fit_relaxation_time(series: np.ndarray, target: float, n_boot: int = 100,
                        seed: int = 0) -> tuple[float, float]:
    """Exponential relaxation-time replacement for `thermalization_time`,
    ported verbatim from u2_2d/scripts/28_crossover_scan.py's function of the
    same name. `series` is [n_records, n_chains]. Returns (tau_hat, tau_err),
    tau_err from a chain-resampling bootstrap.
    """
    t = np.arange(series.shape[0], dtype=float)
    mean = series.mean(axis=1)
    sem = np.maximum(series.std(axis=1, ddof=1) / math.sqrt(series.shape[1]), 1e-12)
    tau_hat, _ = _fit_exp_once(t, mean, sem, target)

    n_chains = series.shape[1]
    rng = np.random.default_rng(seed)
    boots = np.empty(n_boot)
    for i in range(n_boot):
        pick = rng.integers(0, n_chains, n_chains)
        sub = series[:, pick]
        m = sub.mean(axis=1)
        s = np.maximum(sub.std(axis=1, ddof=1) / math.sqrt(n_chains), 1e-12)
        boots[i] = _fit_exp_once(t, m, s, target)[0]
    finite = boots[np.isfinite(boots)]
    if len(finite) > 3:
        q16, q84 = np.percentile(finite, [16, 84])
        tau_err = float((q84 - q16) / 2.0)
    elif len(finite) > 1:
        tau_err = float(finite.std())
    else:
        tau_err = float("nan")

    if math.isfinite(tau_hat) and tau_hat > 0 and math.isfinite(tau_err):
        if tau_err <= 0 or tau_hat / tau_err < 2.0:
            tau_hat = 0.0

    if tau_hat == 0.0:
        tail = series[series.shape[0] // 2:]
        if _tail_is_biased([(tail, target)], rng, n_chains):
            tau_hat = float("inf")
    return tau_hat, tau_err


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
    """Mean and error from binning (robust to mild autocorrelation).

    Fixed n_bins is blind to autocorrelation longer than the bin length; where
    chain structure is known, prefer `autocorr_aware_mean_err`."""
    values = np.asarray(values, dtype=float)
    n_bins = min(n_bins, max(2, len(values) // 2))
    bins = np.array_split(values, n_bins)
    means = np.array([b.mean() for b in bins])
    return float(values.mean()), float(means.std(ddof=1) / math.sqrt(len(means)))


def chain_tau_int(values: np.ndarray, n_chains: int) -> float:
    """Mean per-chain tau_int for a series ordered chain-major per draw
    (run_hmc_ensemble contract: index = draw * n_chains + chain). Computing
    tau_int on the interleaved ordering instead reads ~0.5 regardless of the
    true autocorrelation, because correlated samples sit n_chains apart."""
    values = np.asarray(values, dtype=float)
    n_draws = len(values) // max(n_chains, 1)
    if n_draws < 8:
        return 0.5
    per_chain = values[: n_draws * n_chains].reshape(n_draws, n_chains)
    taus = [integrated_autocorrelation_time(per_chain[:, c])[0] for c in range(n_chains)]
    return float(max(float(np.mean(taus)), 0.5))


def autocorr_aware_mean_err(
    values: np.ndarray, n_chains: int | None = None, n_bins: int = 20
) -> tuple[float, float, float]:
    """Mean, error, and tau_int. The binned error is the floor; when chain
    structure is known and per-chain tau_int is measurable, the naive sem
    inflated by sqrt(2 tau_int) replaces it wherever larger (n_eff = N / 2 tau;
    chains are independent, so the inflation applies to the pooled sem)."""
    values = np.asarray(values, dtype=float)
    mean, err = binned_mean_err(values, n_bins)
    tau = 0.5
    if n_chains and len(values) >= 8 * n_chains:
        tau = chain_tau_int(values, n_chains)
        naive = values.std(ddof=1) / math.sqrt(max(len(values), 2))
        err = max(err, naive * math.sqrt(2.0 * tau))
    return mean, float(err), tau


def ks_p_neff(a: np.ndarray, b: np.ndarray, n_eff_a: float, n_eff_b: float) -> float:
    """Two-sample KS p-value with autocorrelation-corrected effective sample
    sizes. scipy's ks_2samp assumes i.i.d. samples; with autocorrelated inputs
    its p-values overstate significance. Statistic from the full samples,
    p from the asymptotic Kolmogorov distribution at the effective size."""
    from scipy.stats import ks_2samp, kstwobign

    d = float(ks_2samp(np.asarray(a, dtype=float), np.asarray(b, dtype=float)).statistic)
    ne = n_eff_a * n_eff_b / max(n_eff_a + n_eff_b, 1e-9)
    if ne < 4:
        return float("nan")
    root = math.sqrt(ne)
    return float(kstwobign.sf((root + 0.12 + 0.11 / root) * d))


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


def normalized_autocorrelation(series: np.ndarray, max_lag: int) -> np.ndarray:
    """Normalized autocorrelation Gamma(delta) for delta = 0 .. max_lag.

    Gamma(delta) = <(x_t - mu)(x_{t+delta} - mu)> / var(x), so Gamma(0) = 1.
    Accepts a single trace [T] or batched chains [T, B]; each chain is centered
    and normalized by its own mean/variance. Returns [max_lag + 1] or
    [max_lag + 1, B]. max_lag is clipped to T - 2.
    """
    series = np.asarray(series, dtype=float)
    single = series.ndim == 1
    if single:
        series = series[:, None]
    n = series.shape[0]
    max_lag = max(0, min(max_lag, n - 2))
    centered = series - series.mean(axis=0)
    var = np.maximum((centered**2).mean(axis=0), 1e-300)
    gamma = np.empty((max_lag + 1, series.shape[1]))
    gamma[0] = 1.0
    for lag in range(1, max_lag + 1):
        gamma[lag] = (centered[:-lag] * centered[lag:]).mean(axis=0) / var
    return gamma[:, 0] if single else gamma


def z_score(value: float, error: float, reference: float, reference_error: float = 0.0) -> float:
    total_err = math.sqrt(error**2 + reference_error**2)
    if total_err == 0:
        return float("inf") if value != reference else 0.0
    return (value - reference) / total_err
