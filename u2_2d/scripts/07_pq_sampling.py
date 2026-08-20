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

The verdict per coupling combines two things, because either alone is
misleading: the sectors must agree with the closed form (chi-squared over the
sector histogram) AND the chains must actually tunnel (a frozen ensemble that
was started in the right sectors agrees perfectly while sampling nothing).
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
    draws = np.empty(n_boot)
    for i in range(n_boot):
        pick = rng.integers(0, n_chains, n_chains)
        draws[i] = statistic(per_chain[:, pick].reshape(-1))
    return float(value), float(draws.std())


def analyse(q_history: np.ndarray, beta: float, size: int, seed: int = 0) -> dict:
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
    odd = [s for s in sectors if int(s["q"]) % 2]
    odd_measured = float(sum(s["measured"] for s in odd))
    odd_exact = float(sum(s["exact"] for s in odd))
    odd_err = float(np.sqrt(sum(s["err"] ** 2 for s in odd)))
    odd_z = (odd_measured - odd_exact) / odd_err if odd_err > 0 else 0.0

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
        "odd_ratio": odd_measured / odd_exact if odd_exact > 0 else float("nan"),
        "odd_z": float(odd_z),
        "beta_over_volume": beta / (size * size),
        "sectors": sectors,
        "mean_abs_z": float(np.mean([abs(s["z"]) for s in sectors])),
    }


def verdict(record: dict) -> str:
    """Two independent ways to fail, and both must be checked.

    A frozen ensemble seeded into the right sectors passes the chi-squared test
    while sampling nothing, so agreement alone is not evidence. Equally, a warm
    ensemble that tunnels freely but disagrees with the closed form is a bug.
    """
    tunnels = record["frozen_fraction"] < 0.5 and record["sector_changes"] > 0
    agrees = record["chi2"] < 2.0 * record["n_sectors"]
    parity_ok = abs(record["odd_z"]) < 2.0
    if not tunnels:
        return "FROZEN"
    if not parity_ok:
        # Sector changes are happening, so this is not freezing in the ordinary
        # sense: the even-charge move is alive and the odd/even balance is not.
        # "STUCK" rather than "FROZEN" because the balance is pinned to its
        # initial condition in whichever direction that condition pointed.
        return "PARITY-STUCK"
    if not agrees:
        return "DISAGREES"
    return "SAMPLED"


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
    args = parser.parse_args()

    device = resolve_device({"device": args.device or "auto"})
    print(configure_device(device))
    set_seed(args.seed)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    size = args.lattice_size
    betas = [float(b) for b in args.betas.split(",")]

    records = []
    for beta in betas:
        action = WilsonU2Action(beta)
        step_size, n_steps = adapted_hmc_params(beta)
        sampler = BatchedHMCU2(size, action, n_chains=args.n_chains,
                               n_steps=n_steps, step_size=step_size, device=device,
                               hot_start=True, topological_updates=True)
        # Deliberately NOT seeded: the whole point is to find out whether the
        # dynamics reaches the right sector weights on its own. A hot start puts
        # the chains in a spread of sectors without using the closed form.
        start = retherm_sweeps(sampler.initialize(), action, args.thermalize_sweeps)
        _, stats = sampler.sample(args.n_draws, burn_in=args.burn_in,
                                  thin=args.thin, initial_state=start,
                                  record_history=True)
        q_history = np.stack(stats.topological_charge_history)
        record = analyse(q_history, beta, size, seed=args.seed)
        record["hmc_acceptance"] = stats.acceptance_rate
        record["winding_acceptance"] = stats.winding_acceptance_rate
        record["verdict"] = verdict(record)
        records.append(record)
        print(f"L={size:3d} beta={beta:6.2f}  <Q^2> {record['q_squared']:.4f} "
              f"+- {record['q_squared_err']:.4f} (exact {record['q_squared_exact']:.4f}, "
              f"z {record['q_squared_z']:+.2f})  changes {record['sector_changes']:5d}  "
              f"frozen {record['frozen_fraction']:.0%}  chi2/dof "
              f"{record['chi2']/record['n_sectors']:.2f}  -> {record['verdict']}",
              flush=True)

    save_json(out_dir / "pq_sampling.json", records)

    lines = [f"# Sampling P(Q): L = {size}", "",
             "Unseeded HMC + winding update. Errors bootstrap over CHAINS, so a",
             "frozen chain counts as one independent charge however long it ran.", "",
             "| beta | beta/V | <Q^2> | exact | z | changes | frozen | chi2/dof | odd/exact | z_odd | verdict |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in records:
        lines.append(
            f"| {r['beta']:g} | {r['beta_over_volume']:.4f} | "
            f"{r['q_squared']:.4f} +- {r['q_squared_err']:.4f} | "
            f"{r['q_squared_exact']:.4f} | {r['q_squared_z']:+.2f} | {r['sector_changes']} | "
            f"{r['frozen_fraction']:.0%} | {r['chi2']/r['n_sectors']:.2f} | "
            f"{r['odd_ratio']:.3f} | {r['odd_z']:+.2f} | {r['verdict']} |"
        )
    sampled = [r for r in records if r["verdict"] == "SAMPLED"]
    if sampled:
        best = max(sampled, key=lambda r: r["beta"])
        lines += ["", f"Coldest coupling with honestly sampled topology: "
                      f"**beta = {best['beta']:g}** at L = {size}."]
    else:
        lines += ["", "No coupling in this scan sampled topology honestly."]
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nwrote {out_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
