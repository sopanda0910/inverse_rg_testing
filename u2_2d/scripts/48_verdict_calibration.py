"""Is `07_pq_sampling.py`'s verdict CALIBRATED? Synthetic null, known answer.

WHY THIS EXISTS. Fixing the `odd_z` error bar on 2026-08-22 (it summed
per-sector bootstrap errors in quadrature over cells that are multinomial and
therefore negatively correlated) changed two verdicts at L = 16, and neither new
verdict looks like physics:

  | beta  | <Q^2> z | changes | frozen | odd/exact | z_odd  | chi2/dof | verdict      |
  |-------|---------|---------|--------|-----------|--------|----------|--------------|
  | 28    | +0.45   | 45909   | 0%     | **1.008** | +2.61  | 0.87     | PARITY-STUCK |
  | 51.75 | +0.29   | 34152   | 0%     | 0.995     | -1.11  | **6.90** | DISAGREES    |
  | 56    | +0.55   | 32556   | 0%     | 1.002     | +0.40  | 1.09     | SAMPLED      |

Two separate smells:

  * **`PARITY-STUCK` fires on a 0.8% deviation** while the chain changes sector
    45909 times and no chain is frozen. That verdict exists to catch a parity
    balance PINNED to its initial condition -- a gross effect, measured at
    odd/exact = 1.69 from a hot start and 0.000 from a cold one. A pure
    significance gate (`|z| > 2`) gets arbitrarily strict as statistics grow, so
    at 256 chains x 300 draws it has stopped testing mobility and started
    testing the move's accuracy to three decimal places. Significance is not
    effect size.
  * **chi2/dof runs 0.87 -> 6.90 -> 1.09 across beta.** A real sampling
    pathology should get worse as beta rises, not spike in the middle. And the
    statistic is built the way `odd_z` used to be: `sum_q z_q^2` over sector
    cells that are negatively correlated, compared against `n_sectors` as though
    it were a chi-squared with that many degrees of freedom. It is not -- the
    cells are multinomial (so at most k-1 free), the per-cell error is
    `sqrt(p(1-p)/n)` rather than Pearson's `sqrt(p/n)`, and neither the
    correlation nor the small expected counts in the tails are accounted for.

Both are hypotheses about the TEST, not about the sampler, and they are settled
by feeding the test data whose answer is known.

WHAT THIS SCRIPT DOES. It never runs HMC. It draws synthetic charge histories of
exactly the shape `07` produces -- `[n_draws, n_chains]` -- from the closed-form
P(Q) itself, so the null hypothesis is TRUE BY CONSTRUCTION, then runs `07`'s own
`analyse()` and `verdict()` over many replicas and reports how often each verdict
fires. Anything above the nominal rate is the test failing, not the sampler.

Four arms, chosen so the script measures both error kinds:

  * `iid`      -- every draw independent from the exact P(Q). The cleanest null.
  * `sticky`   -- with probability `s` a draw repeats the previous one, else
                  redraws from P(Q). The marginal is UNCHANGED and exact, but the
                  series is autocorrelated, which is what a real chain looks
                  like. `--match-changes` tunes `s` to reproduce a measured
                  sector-change count so the mimicry is quantitative.
  * `odd_bias` -- the exact P(Q) with the odd sectors reweighted by
                  `--odd-bias`. This measures POWER: how big a parity error the
                  test can actually see, which is what decides whether +2.61 at
                  a 0.8% deviation means anything.
  * `parity_frozen` -- each chain draws its parity ONCE from the exact odd
                  weight and then only ever visits sectors of that parity. This
                  is the pathology `PARITY-STUCK` was built for, so a test with
                  no power here is broken in the opposite direction.

READ THE `iid` AND `sticky` ROWS FIRST. If `chi2/dof` is centred well above 1 or
the `|z_odd| > 2` rate is well above 5% there, the L = 16 verdicts above are
artefacts and `07`'s statistics need fixing before its output means anything.

    python u2_2d/scripts/48_verdict_calibration.py --lattice-size 16 \
        --betas 28,51.75,56 --n-chains 256 --n-draws 300 --replicas 200
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u2_2d.lgt.exact import det_topological_charge_distribution
from u2_2d.utils import save_json


def load_stage07():
    """Import `07_pq_sampling.py` by path -- the module name is not an identifier.

    The point of the exercise is to test the DEPLOYED functions, so they are
    imported rather than reimplemented; a reimplementation would calibrate a
    copy of the test and prove nothing about the one that produced the verdicts.
    """
    path = Path(__file__).resolve().parent / "07_pq_sampling.py"
    spec = importlib.util.spec_from_file_location("stage07", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def draw_history(rng, q_values, probs, n_draws, n_chains, arm, stickiness,
                 odd_bias):
    """A `[n_draws, n_chains]` charge history with a KNOWN sector distribution."""
    p = np.asarray(probs, dtype=float)
    q = np.asarray(q_values)

    if arm == "odd_bias":
        w = p * np.where(np.abs(q.astype(int)) % 2 == 1, odd_bias, 1.0)
        p = w / w.sum()

    if arm == "parity_frozen":
        odd_mask = (np.abs(q.astype(int)) % 2 == 1)
        p_odd = float(p[odd_mask].sum())
        # Each chain's parity is drawn ONCE, from the correct weight, and then
        # never changes -- the marginal over chains is right on average while no
        # chain ever crosses. That is precisely the failure the verdict targets.
        parity = rng.random(n_chains) < p_odd
        out = np.empty((n_draws, n_chains))
        for c in range(n_chains):
            mask = odd_mask if parity[c] else ~odd_mask
            sub = p[mask] / p[mask].sum()
            out[:, c] = rng.choice(q[mask], size=n_draws, p=sub)
        return out

    out = rng.choice(q, size=(n_draws, n_chains), p=p).astype(float)
    if arm == "sticky" and stickiness > 0:
        # Repeat-the-previous-draw leaves the marginal exactly invariant while
        # introducing autocorrelation, so any change in the verdict rate is
        # attributable to the correlation alone.
        for d in range(1, n_draws):
            hold = rng.random(n_chains) < stickiness
            out[d] = np.where(hold, out[d - 1], out[d])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lattice-size", type=int, default=16)
    ap.add_argument("--betas", default="28,51.75,56")
    ap.add_argument("--n-chains", type=int, default=256)
    ap.add_argument("--n-draws", type=int, default=300)
    ap.add_argument("--replicas", type=int, default=200)
    ap.add_argument("--stickiness", type=float, default=0.4,
                    help="P(a draw repeats the previous one) in the sticky arm")
    ap.add_argument("--odd-bias", type=float, default=1.008,
                    help="odd-sector reweighting in the power arm; the default "
                         "is the deviation actually seen at L=16 beta=28")
    ap.add_argument("--arms",
                    default="iid,sticky,odd_bias,parity_frozen")
    ap.add_argument("--n-boot", type=int, default=400,
                    help="bootstrap draws inside analyse(); 4000 is the "
                         "deployed value and is far too slow for a scan")
    ap.add_argument("--gof-boot", type=int, default=400,
                    help="bootstrap draws inside sector_goodness_of_fit")
    ap.add_argument("--seed", type=int, default=20260822)
    ap.add_argument("--out-dir", default="out/u2_2d/verdict_calibration")
    args = ap.parse_args()

    stage07 = load_stage07()
    # The deployed bootstrap count is fixed inside analyse(); shrink it for the
    # scan and say so, since the error bar's own noise is a confounder here.
    original = stage07.chain_bootstrap

    def cheap_bootstrap(per_chain, statistic, n_boot=args.n_boot, seed=0):
        return original(per_chain, statistic, n_boot=args.n_boot, seed=seed)

    stage07.chain_bootstrap = cheap_bootstrap

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)
    size = args.lattice_size
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]

    records = []
    print(f"L = {size}, {args.n_chains} chains x {args.n_draws} draws, "
          f"{args.replicas} replicas per cell, n_boot = {args.n_boot}")
    print(f"\n{'beta':>7} {'arm':<14} {'median':>8} {'|z_odd|>2':>10} "
          f"{'median':>8} {'gof rej':>9} {'verdict rates':<40}")
    print(f"{'':>7} {'':<14} {'z_odd':>8} {'rate':>10} {'gof p':>8} "
          f"{'rate':>9}")
    for beta in [float(b) for b in args.betas.split(",")]:
        q_values, probs = det_topological_charge_distribution(beta, size)
        for arm in arms:
            z_odds, chi2s, verdicts = [], [], []
            for _ in range(args.replicas):
                hist = draw_history(rng, q_values, probs, args.n_draws,
                                    args.n_chains, arm, args.stickiness,
                                    args.odd_bias)
                rec = stage07.analyse(hist, beta, size,
                                      seed=int(rng.integers(1 << 30)),
                                      gof_boot=args.gof_boot)
                rec["verdict"] = stage07.verdict(rec)
                z_odds.append(rec["odd_z"])
                chi2s.append(rec.get("gof_p", 1.0))
                verdicts.append(rec["verdict"])
            z_odds = np.asarray(z_odds)
            chi2s = np.asarray(chi2s)
            counts = {v: verdicts.count(v) / len(verdicts)
                      for v in sorted(set(verdicts))}
            records.append({
                "beta": beta, "lattice_size": size, "arm": arm,
                "n_chains": args.n_chains, "n_draws": args.n_draws,
                "replicas": args.replicas, "stickiness": args.stickiness,
                "odd_bias": args.odd_bias,
                "median_z_odd": float(np.median(z_odds)),
                "mean_abs_z_odd": float(np.mean(np.abs(z_odds))),
                "rate_absz_odd_gt2": float(np.mean(np.abs(z_odds) > 2)),
                "median_gof_p": float(np.median(chi2s)),
                "rate_gof_reject": float(np.mean(chi2s < 0.01)),
                "verdict_rates": counts,
            })
            summary = " ".join(f"{k}={v:.0%}" for k, v in counts.items())
            print(f"{beta:7.2f} {arm:<14} {np.median(z_odds):8.2f} "
                  f"{np.mean(np.abs(z_odds) > 2):10.0%} "
                  f"{np.median(chi2s):8.3f} {np.mean(chi2s < 0.01):9.0%} "
                  f"{summary:<40}")
            save_json(out_dir / "verdict_calibration.json", records)

    print(f"\n{'=' * 78}")
    print("HOW TO READ THIS")
    print("  iid / sticky are TRUE NULLS -- the sector distribution is exact by")
    print("  construction. There, |z_odd| > 2 should fire ~5% of the time and")
    print("  median chi2/dof should sit near 1. A higher rate is the TEST")
    print("  failing, and the L=16 verdicts that motivated this run are then")
    print("  artefacts rather than findings.")
    print("  odd_bias measures POWER at the deviation actually observed; if the")
    print("  iid arm already fires as often, the observed z carries no")
    print("  information about a real bias.")
    print("  parity_frozen must fire at a high rate or the verdict has lost the")
    print("  pathology it exists to catch.")
    print(f"\nwrote {out_dir / 'verdict_calibration.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
