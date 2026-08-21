"""Stage 15: does the odd/even balance ever MOVE, and if not, what sets it?

THE PROBLEM THIS ANSWERS. The stored base ensemble (L = 16, beta = 28, 256 chains,
1024 configurations = 4 draws per chain) measures an odd-sector excess of 13% at
z_odd = +2.42, chi2/dof = 2.41 -- the PARITY-STUCK signature -- while a scan at the
identical coupling with 200 draws per chain measured 1.030 and z_odd = +0.69, a
clean SAMPLED verdict. Same dynamics, same coupling, opposite verdicts. Since the
base is the single point where topology enters the whole study, that gap has to be
resolved rather than averaged over.

THE OBVIOUS HYPOTHESIS IS WRONG, AND THAT IS THE RESULT. It is natural to read the
gap as a slowly-relaxing parity balance -- the hot start strands excess odd weight,
it drains over some long timescale, and 4 draws per chain simply does not average
it. That predicts a visible transient and a large tau_int on the parity indicator,
and prescribes a longer run. Measuring it says otherwise: at L = 16, beta = 28, NO
CHAIN EVER CHANGES PARITY. Not once in 256 chains over 2000 trajectories, while the
same run logs tens of thousands of Q changes -- all of them even.

So the odd fraction is not a relaxing observable at all. It is a label assigned to
each chain once, during the hot-start ordering, and carried unchanged forever. The
number of independent parity draws is exactly n_chains no matter how long anything
runs, the correct error model is a binomial over chains, and the two conflicting
measurements are simply two draws of a 256-chain binomial that landed 2 sigma
apart. THE ONLY LEVER IS MORE CHAINS.

WHY tau_int(Q^2) CANNOT SEE THIS, AND IT IS THE TRAP THE THEORY SETS. The base
measures tau_int(Q^2) = 0.55 draws -- essentially decorrelated -- which reads as a
well-equilibrated topology. Q^2 fluctuates on the EVEN channel, which the central
instanton keeps wide open at cost 2 pi^2 beta / V, a ladder invariant. It is nearly
blind to the odd/even channel, which is shut. A fast tau_int on a quantity blind to
the frozen mode certifies an equilibrium that does not exist.

WHAT THIS SCRIPT REPORTS. The parity flip count (the decisive number), the odd
fraction against the closed form with a binomial-over-chains error, tau_int of the
parity indicator against tau_int(Q^2), and -- for couplings where parity DOES move
-- the block-by-block relaxation of the odd fraction from a hot start with no
burn-in, since there the transient is a real thing that has to be discarded.
Scanning beta locates where parity mobility actually dies, which is a sharper
boundary than the PARITY-STUCK verdict of stage 07: that verdict is a hypothesis
test on one binomial draw and can pass on luck, while a flip count cannot.
"""

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u2_2d.lgt.actions import WilsonU2Action
from u2_2d.lgt.exact import det_topological_charge_distribution
from u2_2d.lgt.hmc import BatchedHMCU2, adapted_hmc_params
from u2_2d.lgt.local_updates import retherm_sweeps
from u2_2d.utils import configure_device, resolve_device, save_json, set_seed


def tau_int(series: np.ndarray, c: float = 5.0) -> float:
    """tau_int of a [n_draws, n_chains] series, averaged over non-constant chains."""
    n = series.shape[0]
    taus = []
    for chain in series.T:
        if chain.var() <= 0:
            continue
        x = chain - chain.mean()
        acf = np.correlate(x, x, mode="full")[n - 1:] / (chain.var() * n)
        t = 0.5
        for w in range(1, n):
            t += acf[w]
            if w >= c * t:
                break
        taus.append(max(t, 0.5))
    return float(np.mean(taus)) if taus else float("inf")


def measure(size: int, beta: float, args, device: str, hot: bool = True) -> dict:
    action = WilsonU2Action(beta)
    step_size, n_steps = adapted_hmc_params(beta)
    sampler = BatchedHMCU2(size, action, n_chains=args.n_chains, n_steps=n_steps,
                           step_size=step_size, device=device, hot_start=hot,
                           topological_updates=True,
                           winding_charge_step=args.charge_step,
                           winding_interval=args.winding_interval)
    # NO burn-in: the transient is part of the measurement. Recording from
    # trajectory zero is the only way to tell a slow relaxation from a frozen
    # label, and those two prescribe opposite fixes.
    start = retherm_sweeps(sampler.initialize(), action, args.thermalize_sweeps)
    _, stats = sampler.sample(args.n_draws, burn_in=0, thin=args.thin,
                              initial_state=start, record_history=True)
    q = np.stack(stats.topological_charge_history)

    q_values, probs = det_topological_charge_distribution(beta, size)
    odd_exact = float(sum(p for v, p in zip(q_values, probs) if int(v) % 2))

    parity = (np.abs(q).astype(int) % 2).astype(float)
    block = max(1, args.n_draws // args.n_blocks)
    blocks = []
    for i in range(0, args.n_draws - block + 1, block):
        chunk = parity[i:i + block]
        # Error over CHAINS: within a block the chains are the independent axis.
        per_chain = chunk.mean(axis=0)
        err = float(per_chain.std() / np.sqrt(per_chain.size))
        blocks.append({
            "first_trajectory": int(i * args.thin),
            "last_trajectory": int((i + block) * args.thin),
            # <Q^2> per block too: parity is one frozen mode, but the shape WITHIN
            # a parity class relaxes through the even winding move and has its own
            # transient. Watching only parity would miss an under-relaxed base.
            "q_squared": float((q[i:i + block] ** 2).mean()),
            "odd_fraction": float(chunk.mean()),
            "err": err,
            "ratio_to_exact": float(chunk.mean() / odd_exact),
            "z": float((chunk.mean() - odd_exact) / err) if err > 0 else 0.0,
        })

    # THE DECISIVE COUNT. If no chain ever flips parity, the odd fraction is a
    # fixed label rather than an observable with a relaxation time, the number of
    # independent draws is n_chains, and the error model is binomial.
    flips = int((np.diff(parity, axis=0) != 0).sum())
    chains_flipped = int((np.diff(parity, axis=0) != 0).any(axis=0).sum())
    binom_err = float(np.sqrt(odd_exact * (1.0 - odd_exact) / args.n_chains))
    binom_z = float((float(parity[0].mean()) - odd_exact) / binom_err)

    tau_parity = tau_int(parity)
    tau_q2 = tau_int(q.astype(float) ** 2)

    relaxed_at = None
    for i, b in enumerate(blocks):
        if all(abs(x["z"]) < 2.0 for x in blocks[i:]):
            relaxed_at = b["first_trajectory"]
            break

    return {
        "start": "hot" if hot else "cold",
        # WHICH WINDING MOVE produced these flips is the whole story -- the same
        # coupling reads PARITY-STUCK under charge_step 2 and fully mobile under
        # charge_step 1 -- so it is recorded, never inferred from the directory
        # name a run happened to be written to.
        "winding_charge_step": int(args.charge_step),
        "winding_interval": int(args.winding_interval),
        "lattice_size": size, "beta": beta, "n_chains": args.n_chains,
        "n_draws": args.n_draws, "thin": args.thin,
        "beta_L": beta * size,
        "n_trajectories": args.n_draws * args.thin,
        "odd_exact": odd_exact,
        "odd_fraction": float(parity.mean()),
        "odd_fraction_first_draw": float(parity[0].mean()),
        "parity_flips": flips,
        "chains_that_flipped": chains_flipped,
        "parity_frozen": flips == 0,
        "binomial_err_over_chains": binom_err,
        "binomial_z": binom_z,
        "q_sector_changes": int((np.diff(q, axis=0) != 0).sum()),
        "tau_int_parity_draws": tau_parity,
        "tau_int_parity_trajectories": tau_parity * args.thin,
        "tau_int_q_squared_draws": tau_q2,
        "blocks": blocks,
        "relaxed_after_trajectories": relaxed_at,
        "hmc_acceptance": stats.acceptance_rate,
        "winding_acceptance": stats.winding_acceptance_rate,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default=None)
    parser.add_argument("--out-dir", default="out/u2_2d/base_parity")
    parser.add_argument("--lattice-size", type=int, default=16)
    parser.add_argument("--betas", default="28")
    parser.add_argument("--n-chains", type=int, default=256)
    parser.add_argument("--n-draws", type=int, default=400)
    parser.add_argument("--thin", type=int, default=5)
    parser.add_argument("--thermalize-sweeps", type=int, default=40)
    parser.add_argument("--n-blocks", type=int, default=20)
    parser.add_argument("--seed", type=int, default=11)
    # charge_step 2 is the CENTRAL move and cannot change parity by construction --
    # it is the correct baseline, not a bug, and it is what every pre-2026-08-20
    # number in this script was measured with. charge_step 1 routes to the
    # marginal odd move (docs/INSTANTON.md), which is the one that flips parity.
    # Run BOTH: the contrast is the result, and quoting either alone misleads.
    parser.add_argument("--charge-step", type=int, default=2,
                        choices=(1, 2),
                        help="2 = central (cannot flip parity); 1 = marginal odd")
    parser.add_argument("--winding-interval", type=int, default=1,
                        help="attempt the winding move every N trajectories; the "
                             "marginal move costs 25 SU(2) sweeps per attempt")
    parser.add_argument("--cold", action="store_true",
                        help="cold start as well as hot: where parity is frozen "
                             "the two disagree, which is the proof that the "
                             "split is inherited rather than sampled")
    args = parser.parse_args()

    device = resolve_device({"device": args.device or "auto"})
    print(configure_device(device))
    set_seed(args.seed)

    size = args.lattice_size
    records = []
    for b in args.betas.split(","):
        records.append(measure(size, float(b), args, device, hot=True))
        if args.cold:
            records.append(measure(size, float(b), args, device, hot=False))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    save_json(out_dir / "base_parity.json", records)

    print(f"\nL = {size}, {args.n_chains} chains, hot start, no burn-in, "
          f"{args.n_draws * args.thin} trajectories each\n")
    print(f"{'beta':>8s} {'start':>6s} {'beta L':>7s} {'Q chg':>7s} {'parity flips':>13s} "
          f"{'odd frac':>9s} {'exact':>7s} {'binom z':>8s} {'tau(Q^2)':>9s}")
    for r in records:
        print(f"{r['beta']:8.2f} {r['start']:>6s} {r['beta_L']:7.0f} {r['q_sector_changes']:7d} "
              f"{r['parity_flips']:13d} {r['odd_fraction']:9.4f} "
              f"{r['odd_exact']:7.4f} {r['binomial_z']:+8.2f} "
              f"{r['tau_int_q_squared_draws']:9.2f}")

    for r in records:
        if not r["parity_frozen"]:
            continue
        need = int(np.ceil(r["odd_exact"] * (1 - r["odd_exact"])
                           / (0.5 * r["binomial_err_over_chains"]) ** 2))
        print(f"\nbeta = {r['beta']:g}: PARITY FROZEN at beta L = {r['beta_L']:.0f}. "
              f"Every one of {r['q_sector_changes']} Q changes is even.")
        print("  The odd fraction is fixed during hot-start ordering and never moves "
              "again, so the")
        print(f"  independent parity draws are n_chains = {r['n_chains']} however "
              "long anything runs.")
        print(f"  binomial error {r['binomial_err_over_chains']:.4f} -> "
              f"z = {r['binomial_z']:+.2f}; to halve it takes {need} chains, and "
              "nothing else will.")

    lines = [f"# Parity mobility at L = {size}", "",
             "Hot start, no burn-in, unseeded. The decisive column is PARITY FLIPS:",
             "where it is zero the odd fraction is a fixed label, the independent",
             "draws are the chains, and only more chains improve it.", "",
             "| beta | start | beta L | Q changes | parity flips | chains flipped |"
             " odd frac | exact | binomial z | tau_int(Q^2) |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in records:
        lines.append(
            f"| {r['beta']:g} | {r['start']} | {r['beta_L']:.0f} | {r['q_sector_changes']} | "
            f"{r['parity_flips']} | {r['chains_that_flipped']}/{r['n_chains']} | "
            f"{r['odd_fraction']:.4f} | {r['odd_exact']:.4f} | "
            f"{r['binomial_z']:+.2f} | {r['tau_int_q_squared_draws']:.2f} |")
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nwrote {out_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
