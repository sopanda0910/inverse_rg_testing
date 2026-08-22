"""Stage 07: where can P(Q) be SAMPLED rather than seeded?

WHY THIS EXISTS. The ladder transports topological charge as an identity -- the
determinant lift sets psi and psi sets Q -- so P(Q) at every rung IS the base
ensemble's P(Q). Nothing above the base can create, destroy or reweight a sector.
That makes the base ensemble the single point where topology enters, and it means
the study's topological claim is only ever as good as the base's P(Q).

Stage 01 gets that distribution by SEEDING from the closed form
(`lgt.sector_seed`), which is exact by construction and therefore cannot be cited
as evidence that anything reproduces P(Q). The alternative is to put the base at a
coupling where HMC plus the winding move genuinely equilibrates topology, measure
that its P(Q) matches the closed form, and let transport carry an honestly sampled
distribution up into the frozen regime where direct sampling is impossible. That
is a far stronger claim, and this stage finds the coupling where it is available.

WHAT IS MEASURED, AND THE STATISTICS THAT MATTER. Above the freezing threshold a
chain never leaves its starting sector, so the number of INDEPENDENT topological
charges is the number of chains, not the number of configurations -- quoting a
naive standard error over configurations understates the uncertainty by
sqrt(n_draws) and turns noise into a fake discrepancy. Every error bar here comes
from a bootstrap over CHAINS, which degrades gracefully to exactly that limit:
a frozen chain contributes one independent charge no matter how long it ran.

That includes P(odd), which is the number the U(2)-specific verdict turns on.
Until 2026-08-22 its error was the QUADRATURE SUM of the per-sector bootstrap
errors, and that is wrong in a direction that matters: the sector cells are
multinomial and hence negatively correlated, so the quadrature sum overstates the
error on their sum and understates every |odd_z| the script prints. Any
`PARITY-STUCK` verdict quoted from a run before that date was measured with the
too-forgiving bar and should be re-measured before it is cited.

The verdict per coupling combines THREE things, because no one of them is
sufficient (rebuilt 2026-08-22 -- see `verdict` and `sector_goodness_of_fit`):

  * the chains must TUNNEL at all (a frozen ensemble started in the right
    sectors agrees perfectly while sampling nothing);
  * PARITY must actually flip -- a count, not a hypothesis test, because a
    significance gate gets arbitrarily strict as statistics grow and the
    pathology being tested for is structural; and
  * the sector histogram must agree with the closed form, judged by a
    BOOTSTRAP-CALIBRATED p-value rather than a chi-squared-shaped quantity that
    was never chi-squared distributed.

`48_verdict_calibration.py` feeds this script synthetic histories drawn from the
closed form itself, where the null is true by construction, and checks that each
verdict fires at its nominal rate. Run it after touching anything here.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u2_2d.lgt.actions import WilsonU2Action
from u2_2d.lgt.exact import (
    det_topological_charge_distribution,
    det_topological_susceptibility,
)
from u2_2d.lgt.hmc import BatchedHMCU2, adapted_hmc_params
from u2_2d.lgt.local_updates import retherm_sweeps
from u2_2d.utils import configure_device, resolve_device, save_json, set_seed


def integrated_autocorrelation(series: np.ndarray, c: float = 5.0) -> float:
    """tau_int of a [n_draws, n_chains] series, averaged over chains.

    Automatic windowing (Sokal): sum rho until the window reaches c * tau. A
    frozen chain has zero variance and no defined autocorrelation; those are
    dropped rather than counted as tau = 1, which would claim independence for
    exactly the chains that have none.
    """
    n_draws = series.shape[0]
    taus = []
    for chain in series.T:
        var = chain.var()
        if var <= 0:
            continue
        x = chain - chain.mean()
        acf = np.correlate(x, x, mode="full")[n_draws - 1:] / (var * n_draws)
        tau = 0.5
        for window in range(1, n_draws):
            tau += acf[window]
            if window >= c * tau:
                break
        taus.append(max(tau, 0.5))
    return float(np.mean(taus)) if taus else float("inf")


def chain_bootstrap(per_chain: np.ndarray, statistic, n_boot: int = 4000,
                    seed: int = 0) -> tuple[float, float]:
    """(value, standard error) resampling whole CHAINS with replacement.

    `per_chain` is [n_draws, n_chains]. Resampling chains rather than
    configurations is what makes the error bar honest under freezing: a chain
    stuck in one sector resamples as a single charge however long it is.
    """
    rng = np.random.default_rng(seed)
    n_chains = per_chain.shape[1]
    value = statistic(per_chain.reshape(-1))

    # EXACT FAST PATH FOR THE MEAN, which is the only statistic this script
    # uses. Every chain has the same length, so the mean over a resampled set of
    # chains is the mean of those chains' own means -- an algebraic identity,
    # not an approximation, and it turns an O(n_boot * n_draws * n_chains) loop
    # into O(n_boot * n_chains). At the deployed 4000 bootstraps over
    # 300 x 256 that is ~300x, which is the difference between this script being
    # scannable and not (see `48_verdict_calibration.py`, which needs hundreds of
    # replicas of it). Verified against the general path in the u2 test suite.
    if statistic is np.mean:
        chain_means = per_chain.mean(axis=0)
        picks = rng.integers(0, n_chains, size=(n_boot, n_chains))
        draws = chain_means[picks].mean(axis=1)
        return float(value), float(draws.std())

    draws = np.empty(n_boot)
    for i in range(n_boot):
        pick = rng.integers(0, n_chains, n_chains)
        draws[i] = statistic(per_chain[:, pick].reshape(-1))
    return float(value), float(draws.std())


def sector_goodness_of_fit(q_history: np.ndarray, q_values, probs,
                           n_boot: int = 2000, seed: int = 0) -> dict:
    """Does the sector HISTOGRAM match the closed form? Calibrated, not assumed.

    WHAT WAS WRONG WITH THE OLD TEST (replaced 2026-08-22). It formed
    `chi2 = sum_q z_q^2` from per-sector chain-bootstrap errors and compared it
    against `n_sectors`. Three things break that, all in the same direction:

      * the sector cells are MULTINOMIAL, so they are negatively correlated and
        the terms are not independent -- the same defect that made `odd_z` too
        forgiving, here making the sum too large;
      * the per-cell error is `sqrt(p(1-p)/n)` while Pearson's chi-squared wants
        `sqrt(p/n)`, which inflates every term by `1/(1-p)`; and
      * the reference is `n_sectors`, but the frequencies sum to one, so at most
        `k-1` are free -- and the deep tail sectors have expected counts far
        below the handful that makes any chi-squared approximation usable.

    Measured consequence: on data drawn FROM the exact P(Q), the old statistic
    exceeded its own `2 * n_sectors` threshold on a large fraction of replicas.
    See `48_verdict_calibration.py`.

    WHAT THIS DOES INSTEAD. Chains are independent replicas, and everything
    awkward -- the multinomial correlation between sectors, the autocorrelation
    along a chain, the freezing -- lives INSIDE a chain. So the test is a
    one-sample test on the per-chain sector-frequency VECTORS, whose covariance
    is estimated from the chains themselves and needs no model:

        X^2 = (mean_c f_c - p)^T  pinv(Cov(f_c) / n_chains)  (mean_c f_c - p)

    with the pseudo-inverse absorbing the rank deficiency from `sum_q f = 1`.
    The p-value is then BOOTSTRAPPED rather than read off a chi-squared table:
    chains are resampled, the statistic recomputed about the observed mean, and
    the observed value placed in that null distribution. That is calibrated
    whatever the tails do.

    THE POOLING RULE IS PER CHAIN, NOT PER ENSEMBLE, and it matters. Cochran's
    usual "expected count >= 5" applied to the whole ensemble keeps bins expected
    to hold seven configurations out of 76800 -- which means essentially every
    CHAIN sees that sector zero times, the bin has near-zero variance, and it
    destabilizes the pseudo-inverse the whole statistic runs through. Since the
    covariance is estimated ACROSS CHAINS, the requirement has to be that a chain
    can resolve the bin at all: `p * n_draws >= 1`. Measured rejection rate at a
    nominal 1%, over 120 replicas per cell, uncorrelated / sticky draws:

        rule                beta 28        beta 51.75     beta 56
        p * n_total >= 5    0.8% / 2.5%    3.3% / 5.0%    0.8% / 3.3%
        p * n_draws >= 1    0.8% / 0.0%    1.7% / 2.5%    0.8% / 3.3%
        p * n_draws >= 5    1.7% / 0.0%    2.5% / 0.0%    0.0% / 3.3%

    `p * n_draws >= 1` is at least as well calibrated everywhere and keeps more
    bins than the stricter rule, which collapses to three bins by beta = 51.75
    and stops being able to see sector shape at all.
    """
    q = np.asarray(q_values)
    p = np.asarray(probs, dtype=float)
    n_chains = q_history.shape[1]
    n_draws = q_history.shape[0]

    keep = p * n_draws >= 1.0
    if keep.sum() < 2:
        return {"gof_chi2": 0.0, "gof_dof": 0, "gof_p": 1.0,
                "gof_bins": int(keep.sum()), "gof_note": "too few usable bins"}

    # [n_chains, n_bins] -- each chain's own sector frequencies, plus one pooled
    # bin for everything the closed form says is rare.
    cols = [(q_history == qq).mean(axis=0) for qq in q[keep]]
    target = list(p[keep])
    tail = float(p[~keep].sum())
    # The pooled tail must clear the SAME per-chain bar as any other bin. Pooling
    # a set of sectors that are individually unresolvable into one bin that is
    # still unresolvable just relocates the instability.
    if tail * n_draws >= 1.0:
        cols.append(np.isin(q_history, q[~keep]).mean(axis=0))
        target.append(tail)
    f = np.stack(cols, axis=1)
    target = np.asarray(target, dtype=float)

    # DROP THE LARGEST BIN. The frequencies are multinomial and sum to a
    # constant, so the all-ones direction carries essentially ZERO variance --
    # and a pseudo-inverse with a small `rcond` happily inverts it, dividing a
    # tiny mean offset by a tinier variance and manufacturing an enormous
    # statistic out of nothing. Measured at L = 16, beta = 56: keeping every bin
    # gave X^2 = 12.4 (p = 0.022) on one seed and X^2 = 51.6 (p = 0.0002) on an
    # independent one, while NO individual sector deviated by more than 1.2
    # sigma -- a `DISAGREES` verdict with no disagreement anywhere in it.
    # Dropping one bin removes the redundancy exactly and leaves a full-rank
    # covariance: the same two datasets then give 3.46 (p = 0.489) and 1.97
    # (p = 0.755). Equivalent to raising `rcond` to 1e-4, but with no tuning
    # parameter to choose, which is why it is done this way.
    if f.shape[1] > 1:
        drop = int(np.argmax(target))
        columns = [i for i in range(f.shape[1]) if i != drop]
        f, target = f[:, columns], target[columns]

    def statistic(sample, centre):
        d = sample.mean(axis=0) - centre
        cov = np.cov(sample, rowvar=False, ddof=1) / sample.shape[0]
        inv = np.linalg.pinv(cov, rcond=1e-10, hermitian=True)
        return float(d @ inv @ d), int(np.linalg.matrix_rank(cov, tol=1e-10))

    observed, dof = statistic(f, target)

    rng = np.random.default_rng(seed)
    centre = f.mean(axis=0)
    picks = rng.integers(0, n_chains, size=(n_boot, n_chains))
    null = np.empty(n_boot)
    for b in range(n_boot):
        null[b] = statistic(f[picks[b]], centre)[0]
    # +1 in both places: the observed value is one draw from the null too, so a
    # p-value can never be exactly zero at finite n_boot.
    p_value = float((np.sum(null >= observed) + 1) / (n_boot + 1))
    return {"gof_chi2": observed, "gof_dof": dof, "gof_p": p_value,
            "gof_bins": int(f.shape[1]) + 1, "gof_pooled_tail": tail,
            "gof_note": "one bin dropped to remove the sum-to-one redundancy"}


def analyse(q_history: np.ndarray, beta: float, size: int, seed: int = 0,
            gof_boot: int = 2000) -> dict:
    """Compare a [n_draws, n_chains] charge history against the closed form."""
    q_values, probs = det_topological_charge_distribution(beta, size)
    exact_q2 = det_topological_susceptibility(beta, size) * size * size

    q2_value, q2_err = chain_bootstrap(q_history ** 2, np.mean, seed=seed)
    changes = int((np.diff(q_history, axis=0) != 0).sum())
    frozen = int((q_history == q_history[0]).all(axis=0).sum())
    n_chains = q_history.shape[1]

    sectors = []
    chi2 = 0.0
    n_free = 0
    for q, p in zip(q_values, probs):
        measured, err = chain_bootstrap(
            (q_history == q).astype(float), np.mean, seed=seed
        )
        # The chain bootstrap is the whole error model. An earlier version also
        # floored this at the binomial error for n_chains, to stop a frozen
        # ensemble looking precise -- but the bootstrap already does that (a
        # frozen chain resamples as one charge), and in the TUNNELLING regime the
        # floor dominates the real error and inflates every bar until chi-squared
        # cannot fail. It scored 0.00 on data carrying a 22% sector deficit.
        z = (measured - p) / err if err > 0 else 0.0
        chi2 += z * z
        n_free += 1 if err > 0 else 0
        sectors.append({"q": float(q), "measured": measured, "err": err,
                        "exact": float(p), "z": float(z)})

    # PARITY IS THE DIAGNOSTIC THAT MATTERS HERE, and a sector-by-sector
    # chi-squared cannot see it. U(2) = (U(1) x SU(2)) / Z_2, so an even change of
    # Q is the free central instanton while an odd one must drag SU(2) across a -1
    # monodromy at cost O(beta L). The signature is a COHERENT imbalance spread
    # over every odd sector -- each individually within 1 sigma, jointly far
    # outside it.
    #
    # NOTE THE SIGN IS NOT FIXED. The barrier blocks the odd<->even channel in BOTH
    # directions, so the parity balance keeps whatever the initial condition gave
    # it: a hot start strands EXCESS odd weight (measured 1.69 at L=8/beta=20 and
    # 1.15 at L=16/beta=51.75), a cold start reaches NO odd sectors at all, and a
    # deficit (0.78 at L=32/beta=203) is only the case where relaxation stalled on
    # the other side. So the test is on |odd_z|, not on a deficit.
    #
    # P(odd) IS BOOTSTRAPPED DIRECTLY, NOT SUMMED IN QUADRATURE (fixed
    # 2026-08-22). The previous version built the error on the odd weight as
    # `sqrt(sum(err_q^2))` over the odd sectors. Those cells are MULTINOMIAL and
    # therefore NEGATIVELY correlated -- if one sector is over-occupied another
    # must be under-occupied -- so the quadrature sum overestimates the error on
    # their sum and shrinks every |odd_z| this script reports. It is the same
    # error `34_marginal_move_bias.py` already avoids, and it made the
    # `PARITY-STUCK` verdict too forgiving in exactly the regime the verdict
    # exists to catch.
    #
    # Bootstrapping the parity indicator over CHAINS gets the correlation for
    # free: each resample recomputes the whole odd fraction on the resampled
    # chains, so the covariance between sectors is carried rather than assumed
    # away. The per-sector `err` entries stay as they are -- they are correct for
    # the chi-squared, which uses them one at a time.
    odd = [s for s in sectors if int(s["q"]) % 2]
    odd_exact = float(sum(s["exact"] for s in odd))
    parity = np.mod(np.rint(q_history).astype(np.int64), 2).astype(float)
    odd_measured, odd_err = chain_bootstrap(parity, np.mean, seed=seed)
    odd_z = (odd_measured - odd_exact) / odd_err if odd_err > 0 else 0.0
    # The tabulated sum is kept for the record: it differs from the direct parity
    # only if a chain reaches an odd sector outside the closed form's q range,
    # which would itself be worth seeing.
    odd_tabulated = float(sum(s["measured"] for s in odd))

    # PARITY MOBILITY IS A COUNT, NOT A HYPOTHESIS TEST (added 2026-08-22).
    # `PARITY-STUCK` used to be declared from `|odd_z| > 2`, and a pure
    # significance gate gets arbitrarily strict as statistics grow: at 256 chains
    # x 300 draws it fired on a 0.8% deviation in P(odd) at L = 16, beta = 28 --
    # on a chain with 45909 sector changes and no frozen chains, which is the
    # opposite of stuck. The pathology the verdict exists for is STRUCTURAL: the
    # parity balance is pinned to its initial condition because nothing crosses
    # the Z_2 monodromy. So count the crossings, exactly as `15_base_parity.py`
    # does -- that is the project's own standing rule, "count flips to establish
    # mobility; use stage 07 to test the resulting distribution", and this script
    # was violating it.
    parity_series = np.mod(np.rint(q_history).astype(np.int64), 2)
    parity_flips = int((np.diff(parity_series, axis=0) != 0).sum())
    parity_frozen = int((parity_series == parity_series[0]).all(axis=0).sum())

    # CHARGE CONJUGATION IS AN EXACT SYMMETRY, so testing it needs no closed form
    # at all -- which makes it the sharpest diagnostic here (added 2026-08-22).
    # The action is invariant under U -> U*, which sends Q -> -Q, so P(Q) must be
    # exactly even. Any asymmetry is a defect in the SAMPLER, and it cannot be
    # blamed on the reference: the closed form does not enter.
    #
    # It is also the test that found itself. The general goodness-of-fit flagged
    # L = 16, beta = 56 at p = 0.022 with no single sector past 1.6 sigma, and the
    # residual turned out to be coherently signed in Q: -1 low while +1 high, -2
    # low while +2 high. One number captures that; a sector-by-sector scan
    # dilutes it across bins.
    signed = np.sign(np.rint(q_history))
    asym_value, asym_err = chain_bootstrap(signed, np.mean, seed=seed)
    charge_asymmetry_z = asym_value / asym_err if asym_err > 0 else 0.0

    gof = sector_goodness_of_fit(q_history, q_values, probs,
                                 n_boot=gof_boot, seed=seed)

    return {
        "beta": beta, "lattice_size": size, "n_chains": n_chains,
        "n_draws": int(q_history.shape[0]),
        "q_squared": q2_value, "q_squared_err": q2_err, "q_squared_exact": float(exact_q2),
        "q_squared_z": float((q2_value - exact_q2) / q2_err) if q2_err > 0 else float("inf"),
        "sector_changes": changes,
        "frozen_chains": frozen,
        "frozen_fraction": frozen / n_chains,
        "tau_int_q_squared": integrated_autocorrelation(q_history ** 2),
        "chi2": float(chi2), "n_sectors": max(n_free, 1),
        "odd_measured": odd_measured, "odd_exact": odd_exact,
        "odd_err": float(odd_err),
        "odd_tabulated": odd_tabulated,
        "odd_ratio": odd_measured / odd_exact if odd_exact > 0 else float("nan"),
        "odd_z": float(odd_z),
        "odd_error_model": "chain bootstrap of the parity indicator",
        "charge_asymmetry": float(asym_value),
        "charge_asymmetry_err": float(asym_err),
        "charge_asymmetry_z": float(charge_asymmetry_z),
        "parity_flips": parity_flips,
        "parity_frozen_chains": parity_frozen,
        "parity_frozen_fraction": parity_frozen / n_chains,
        "beta_over_volume": beta / (size * size),
        "sectors": sectors,
        "mean_abs_z": float(np.mean([abs(s["z"]) for s in sectors])),
        **gof,
    }


def verdict(record: dict, alpha: float = 0.01) -> str:
    """Three independent ways to fail, and all must be checked.

    A frozen ensemble seeded into the right sectors passes any goodness-of-fit
    test while sampling nothing, so agreement alone is not evidence. Equally, a
    warm ensemble that tunnels freely but disagrees with the closed form is a
    bug.

    REBUILT 2026-08-22, after fixing the `odd_z` error bar changed two verdicts
    at L = 16 and neither new verdict survived calibration. Two changes:

    * **MOBILITY IS STRUCTURAL, NOT STATISTICAL.** `PARITY-STUCK` is now
      declared from the parity FLIP COUNT, not from `|odd_z| > 2`. A pure
      significance gate gets stricter without limit as statistics grow, so the
      old rule called a chain with 45909 sector changes and zero frozen chains
      "stuck" on the strength of a 0.8% deviation in P(odd). Mobility and
      accuracy are different questions and this script was conflating them.
    * **AGREEMENT USES A CALIBRATED p-VALUE.** `chi2 < 2 * n_sectors` was not a
      chi-squared test of anything (see `sector_goodness_of_fit`); it fired far
      above its nominal rate on data drawn from the exact distribution.

    `odd_z` is still reported, and it is still the right statistic for asking
    whether the odd weight is BIASED -- it is just not the right statistic for
    asking whether parity moves. Read it beside `odd_ratio`: at large statistics
    a significant `odd_z` on a sub-percent `odd_ratio` is a precision
    measurement of the move, not a pathology.
    """
    tunnels = record["frozen_fraction"] < 0.5 and record["sector_changes"] > 0
    # A chain that never crosses the Z_2 monodromy keeps whatever parity weight
    # its initial condition handed it -- right or wrong, it did not sample it.
    parity_mobile = (record.get("parity_flips", 0) > 0
                     and record.get("parity_frozen_fraction", 0.0) < 0.5)
    agrees = record.get("gof_p", 1.0) >= alpha
    if not tunnels:
        return "FROZEN"
    if not parity_mobile:
        # Sector changes are happening, so this is not freezing in the ordinary
        # sense: the even-charge move is alive and the odd/even balance is not.
        # "STUCK" rather than "FROZEN" because the balance is pinned to its
        # initial condition in whichever direction that condition pointed.
        return "PARITY-STUCK"
    if not agrees:
        return "DISAGREES"
    return "SAMPLED"


def write_report(out_dir: Path, size: int, records: list, args) -> None:
    """Render the markdown table. Shared by the sampling and --reanalyse
    paths so a re-analysis produces a report identical in form to a run.

    THE MOVE IS READ FROM THE RECORDS, NOT FROM `args`. Under `--reanalyse` the
    command line carries argparse DEFAULTS -- charge_step 2, the retired joint
    proposal -- while the data on disk was generated with whatever was passed at
    run time. Printing the defaults would relabel a marginal-move measurement as
    a joint-move one, which is precisely the confusion that forced every verdict
    in this study to be re-measured once already.
    """
    steps = {r.get("winding_charge_step") for r in records
             if r.get("winding_charge_step") is not None}
    intervals = {r.get("winding_interval") for r in records
                 if r.get("winding_interval") is not None}
    move = {
        "charge_step": steps.pop() if len(steps) == 1 else "MIXED/UNRECORDED",
        "interval": intervals.pop() if len(intervals) == 1 else "MIXED/UNRECORDED",
    }
    lines = [f"# Sampling P(Q): L = {size}", "",
             "Unseeded HMC + winding update. Errors bootstrap over CHAINS, so a",
             "frozen chain counts as one independent charge however long it ran.",
             "P(odd) is bootstrapped DIRECTLY from the parity indicator rather",
             "than summed in quadrature over sectors, which would understate it.",
             f"Winding move: charge_step {move['charge_step']}, interval "
             f"{move['interval']}.", "",
             "Parity mobility is a FLIP COUNT, not a hypothesis test, and",
             "agreement is a bootstrap-calibrated p-value; see `verdict`.", "",
             "| beta | beta/V | <Q^2> | exact | z | changes | parity flips | "
             "frozen | gof p | C-asym z | odd/exact | z_odd | verdict |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in records:
        lines.append(
            f"| {r['beta']:g} | {r['beta_over_volume']:.4f} | "
            f"{r['q_squared']:.4f} +- {r['q_squared_err']:.4f} | "
            f"{r['q_squared_exact']:.4f} | {r['q_squared_z']:+.2f} | {r['sector_changes']} | "
            f"{r['parity_flips']} | "
            f"{r['frozen_fraction']:.0%} | {r['gof_p']:.3f} | "
            f"{r.get('charge_asymmetry_z', float('nan')):+.2f} | "
            f"{r['odd_ratio']:.4f} | {r['odd_z']:+.2f} | {r['verdict']} |"
        )
    sampled = [r for r in records if r["verdict"] == "SAMPLED"]
    if sampled:
        best = max(sampled, key=lambda r: r["beta"])
        lines += ["", f"Coldest coupling with honestly sampled topology: "
                      f"**beta = {best['beta']:g}** at L = {size}."]
    else:
        lines += ["", "No coupling in this scan sampled topology honestly."]
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def history_name(size: int, beta: float) -> str:
    """Stable filename for a saved charge history."""
    return f"q_history_L{size}_beta{beta:g}.npy"


def history_meta_name(size: int, beta: float) -> str:
    """Sidecar recording HOW a history was generated.

    A charge history is meaningless without the move that produced it -- the
    joint proposal scores zero parity flips where the marginal move scores tens
    of thousands, and this study has already had to re-measure every verdict once
    because that attribution was lost. `--reanalyse` cannot recover it from the
    command line, since argparse would hand it the DEFAULTS. So it travels with
    the data.
    """
    return f"q_history_L{size}_beta{beta:g}.meta.json"


def reanalyse(out_dir: Path, size: int, args) -> int:
    """Recompute every verdict from saved histories. No HMC, seconds not hours.

    This is the escape hatch that did not exist when the statistics in this file
    were rebuilt on 2026-08-22: the charge histories are the expensive artefact
    and the verdict is a pure function of them, so a change to `analyse` or
    `verdict` should cost a re-analysis rather than a re-simulation.
    """
    found = list(out_dir.glob(f"q_history_L{size}_beta*.npy"))
    if not found:
        print(f"no saved histories under {out_dir}; re-run without --reanalyse")
        return 1
    # Sort by BETA, not by filename: lexicographic order puts beta = 6 after
    # beta = 20, and the report table is read as a ladder in coupling.
    found.sort(key=lambda path: float(path.stem.split("beta")[-1]))
    # The winding settings live in the previous summary, keyed by beta; a
    # re-analysis must not silently relabel which move produced the data.
    previous = {}
    summary_path = out_dir / "pq_sampling.json"
    if summary_path.exists():
        try:
            for entry in json.loads(summary_path.read_text(encoding="utf-8")):
                previous[round(float(entry["beta"]), 6)] = entry
        except Exception:
            previous = {}

    records = []
    for path in found:
        beta = float(path.stem.split("beta")[-1])
        q_history = np.load(path)
        record = analyse(q_history, beta, size, seed=args.seed,
                         gof_boot=args.gof_boot)
        record["verdict"] = verdict(record)
        record["reanalysed_from"] = path.name
        prior = dict(previous.get(round(beta, 6), {}))
        sidecar = path.with_suffix("").with_suffix(".meta.json")
        if sidecar.exists():
            # The sidecar is authoritative: it was written by the run itself,
            # while the summary may have been rewritten by an earlier
            # re-analysis that predates these fields.
            prior.update(json.loads(sidecar.read_text(encoding="utf-8")))
        for key in ("winding_charge_step", "winding_interval",
                    "hmc_acceptance", "winding_acceptance", "n_chains",
                    "thin", "burn_in", "seed"):
            if key in prior:
                record[key] = prior[key]
        records.append(record)
        print(f"L={size:3d} beta={beta:6.2f}  <Q^2> {record['q_squared']:.4f} "
              f"+- {record['q_squared_err']:.4f} "
              f"(exact {record['q_squared_exact']:.4f}, "
              f"z {record['q_squared_z']:+.2f})  "
              f"changes {record['sector_changes']:6d}  "
              f"parity flips {record['parity_flips']:6d}  "
              f"gof p {record['gof_p']:.3f}  "
              f"C-asym z {record['charge_asymmetry_z']:+.2f}  "
              f"odd/exact {record['odd_ratio']:.4f} "
              f"(z {record['odd_z']:+.2f})  -> {record['verdict']}", flush=True)
    save_json(out_dir / "pq_sampling.json", records)
    write_report(out_dir, size, records, args)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default=None)
    parser.add_argument("--out-dir", default="out/u2_2d/pq_sampling")
    parser.add_argument("--lattice-size", type=int, default=8)
    parser.add_argument("--betas", default="6,8,10,12,14")
    parser.add_argument("--n-chains", type=int, default=128)
    parser.add_argument("--n-draws", type=int, default=150)
    parser.add_argument("--thin", type=int, default=5)
    parser.add_argument("--burn-in", type=int, default=300)
    parser.add_argument("--thermalize-sweeps", type=int, default=40)
    parser.add_argument("--seed", type=int, default=0)
    # EVERY `PARITY-STUCK` verdict this script produced before 2026-08-21 was
    # measured with charge_step 2, the JOINT proposal, which is now known to
    # score zero parity flips at couplings where the marginal move scores 61403.
    # Those verdicts gate `seed_exact_sectors` and the choice of ladder base, so
    # they have to be re-measured under the move actually in use.
    parser.add_argument("--charge-step", type=int, default=2, choices=(1, 2),
                        help="2 = central/joint (historical); 1 = marginal odd")
    parser.add_argument("--winding-interval", type=int, default=1)
    # THE CHARGE HISTORY IS THE EXPENSIVE PART AND THE ANALYSIS IS THE CHEAP
    # PART, so keep the former (added 2026-08-22). The statistics in this file
    # were rebuilt twice in one day -- the odd-weight error bar and then the
    # whole goodness-of-fit -- and each time every verdict had to be regenerated
    # by re-running hours of HMC, because only the summary was ever written out.
    # A [n_draws, n_chains] integer array is a few hundred kilobytes.
    parser.add_argument("--no-save-history", action="store_true",
                        help="do not write the raw charge histories")
    parser.add_argument("--reanalyse", action="store_true",
                        help="recompute verdicts from the saved histories in "
                             "--out-dir and exit, running no HMC at all")
    parser.add_argument("--gof-boot", type=int, default=2000)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    size = args.lattice_size
    betas = [float(b) for b in args.betas.split(",")]

    if args.reanalyse:
        return reanalyse(out_dir, size, args)

    device = resolve_device({"device": args.device or "auto"})
    print(configure_device(device))
    set_seed(args.seed)

    records = []
    for beta in betas:
        action = WilsonU2Action(beta)
        step_size, n_steps = adapted_hmc_params(beta)
        sampler = BatchedHMCU2(size, action, n_chains=args.n_chains,
                               n_steps=n_steps, step_size=step_size, device=device,
                               hot_start=True, topological_updates=True,
                               winding_charge_step=args.charge_step,
                               winding_interval=args.winding_interval)
        # Deliberately NOT seeded: the whole point is to find out whether the
        # dynamics reaches the right sector weights on its own. A hot start puts
        # the chains in a spread of sectors without using the closed form.
        start = retherm_sweeps(sampler.initialize(), action, args.thermalize_sweeps)
        _, stats = sampler.sample(args.n_draws, burn_in=args.burn_in,
                                  thin=args.thin, initial_state=start,
                                  record_history=True)
        q_history = np.stack(stats.topological_charge_history)
        if not args.no_save_history:
            np.save(out_dir / history_name(size, beta), q_history)
            save_json(out_dir / history_meta_name(size, beta), {
                "lattice_size": size, "beta": beta,
                "winding_charge_step": int(args.charge_step),
                "winding_interval": int(args.winding_interval),
                "n_chains": args.n_chains, "n_draws": args.n_draws,
                "thin": args.thin, "burn_in": args.burn_in,
                "thermalize_sweeps": args.thermalize_sweeps,
                "seed": args.seed, "hot_start": True, "seeded_sectors": False,
            })
        record = analyse(q_history, beta, size, seed=args.seed,
                         gof_boot=args.gof_boot)
        record["hmc_acceptance"] = stats.acceptance_rate
        record["winding_acceptance"] = stats.winding_acceptance_rate
        # Which winding move produced this verdict is part of the verdict.
        record["winding_charge_step"] = int(args.charge_step)
        record["winding_interval"] = int(args.winding_interval)
        record["verdict"] = verdict(record)
        records.append(record)
        print(f"L={size:3d} beta={beta:6.2f}  <Q^2> {record['q_squared']:.4f} "
              f"+- {record['q_squared_err']:.4f} (exact {record['q_squared_exact']:.4f}, "
              f"z {record['q_squared_z']:+.2f})  changes {record['sector_changes']:5d}  "
              f"parity flips {record['parity_flips']:6d}  "
              f"frozen {record['frozen_fraction']:.0%}  gof p "
              f"{record['gof_p']:.3f}  C-asym z "
              f"{record['charge_asymmetry_z']:+.2f}  "
              f"odd/exact {record['odd_ratio']:.4f} "
              f"(z {record['odd_z']:+.2f})  -> {record['verdict']}",
              flush=True)

    save_json(out_dir / "pq_sampling.json", records)

    write_report(out_dir, size, records, args)
    print(f"\nwrote {out_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
