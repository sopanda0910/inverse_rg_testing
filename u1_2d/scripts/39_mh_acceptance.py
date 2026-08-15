"""Is exactness-by-Metropolis reachable? Answered from data already on disk.

Option 2 of the exact-P(Q) removal routes (docs/NARRATIVE.md sec 21.5): use
the model as an independence proposal inside Metropolis-Hastings targeting the
true Boltzmann distribution. That needs only ACTION RATIOS -- never P(Q), never
Z -- so it removes the analytic crutch entirely and upgrades the pipeline from
a validated heuristic to asymptotically exact.

The question is whether it is usable, and that is decided by the acceptance
rate. For an independence sampler with proposal q and target p, the acceptance
probability from state i to proposal j is

    alpha(i -> j) = min(1, w_j / w_i),        w = p/q,

so the whole thing is a function of the log-weight distribution -- which
15_model_ess already computes and stores. No new sampling is needed: this
script is arithmetic on `ess_results.json`.

Reported per case:
  * mean acceptance in stationarity, E_{i~w, j~q}[min(1, w_j/w_i)]
  * the implied integrated autocorrelation time, tau ~ 1/alpha for small alpha
  * how many proposals one independent configuration costs

    .venv/Scripts/python.exe u1_2d/scripts/39_mh_acceptance.py
"""

import argparse
import json
import math
from pathlib import Path

import torch

REPO = Path(__file__).resolve().parents[2]


def mh_diagnostics(log_w: torch.Tensor, n_pairs: int = 2_000_000,
                   seed: int = 0) -> dict:
    """Independence-MH acceptance implied by a set of log importance weights.

    In stationarity the current state is distributed as p, i.e. drawn from the
    q-sample with probability proportional to w; the proposal is drawn from q,
    i.e. uniformly from the same sample. Estimating the expectation by pairing
    those two draws avoids forming an n x n matrix, which is what makes this
    tractable at n = 512.
    """
    lw = log_w.double()
    lw = lw - lw.max()
    p = torch.softmax(lw, dim=0)                  # stationary weights
    n = lw.numel()
    gen = torch.Generator().manual_seed(seed)
    i = torch.multinomial(p, n_pairs, replacement=True, generator=gen)
    j = torch.randint(0, n, (n_pairs,), generator=gen)
    alpha = torch.minimum(torch.ones(n_pairs, dtype=torch.float64),
                          torch.exp(lw[j] - lw[i]))
    acc = float(alpha.mean())
    # For an independence sampler the chain sticks for 1/alpha steps on
    # average, so tau_int ~ (2 - alpha) / alpha; report the cost in proposals.
    tau = (2.0 - acc) / acc if acc > 0 else float("inf")
    # Resolution guard. When one sample carries essentially all the weight the
    # stationary state is that sample, and the estimator degenerates to
    #   alpha ~ mean_j(w_j) / w_max = 1 / (n * p_max) -> 1/n.
    # It is then reporting the sample size, not the acceptance -- the same
    # floor that makes ESS/N read 1/N (Table S2). Flag it rather than quote it.
    floor = 1.0 / n
    return {
        "acceptance": acc,
        "acceptance_is_at_floor": acc < 2.0 * floor,
        "resolution_floor": floor,
        "tau_int_proposals": tau,
        "proposals_per_independent_config": tau,
        "max_weight_share": float(p.max()),
        "log_w_std": float(lw.std()),
        "log_w_range": float(lw.max() - lw.min()),
        "n": int(n),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", nargs="+",
                    default=["out/u1_2d/model_ess_n512",
                             "out/u1_2d/model_ess_n512_case4",
                             "out/u1_2d/model_ess"],
                    help="directories holding ess_results.json")
    ap.add_argument("--out", default="out/u1_2d/mh_acceptance.json")
    args = ap.parse_args()

    rows = {}
    for src in args.sources:
        path = REPO / src / "ess_results.json"
        if not path.exists():
            continue
        for c in json.loads(path.read_text(encoding="utf-8")):
            if not isinstance(c, dict) or not c.get("log_weights"):
                continue
            key = (c["fine_L"], round(c["fine_beta"], 3))
            # Prefer the largest n available for each case.
            if key in rows and rows[key]["n"] >= c["n"]:
                continue
            d = mh_diagnostics(torch.tensor(c["log_weights"]))
            d.update({"L": c["fine_L"], "beta": c["fine_beta"], "src": src})
            rows[key] = d
    if not rows:
        raise SystemExit("no ess_results.json with stored log_weights found")

    print("Independence-MH with the diffusion model as proposal\n")
    print("| L | beta_f | n | acceptance | 1/n floor | proposals per indep. config | "
          "largest single weight |")
    print("|---|---|---|---|---|---|---|")
    for key in sorted(rows):
        r = rows[key]
        acc = (f"<= {r['acceptance']:.3g} (at floor)" if r["acceptance_is_at_floor"]
               else f"{r['acceptance']:.3g}")
        cost = ("inf" if math.isinf(r["proposals_per_independent_config"])
                else f">= {r['proposals_per_independent_config']:.3g}")
        print(f"| {r['L']} | {r['beta']:g} | {r['n']} | {acc} | "
              f"{r['resolution_floor']:.3g} | {cost} | "
              f"{100 * r['max_weight_share']:.1f}% |")

    worst = max(rows.values(), key=lambda r: r["proposals_per_independent_config"])
    best = min(rows.values(), key=lambda r: r["proposals_per_independent_config"])
    print(f"\nbest case  : {best['L']}:{best['beta']:g} -> "
          f"{best['acceptance']:.3g} acceptance")
    print(f"worst case : {worst['L']}:{worst['beta']:g} -> "
          f"{worst['acceptance']:.3g} acceptance")
    at_floor = [r for r in rows.values() if r["acceptance_is_at_floor"]]
    if at_floor:
        print(f"\n{len(at_floor)} of {len(rows)} cases are AT the 1/n resolution "
              "floor: the estimate is\nreporting the sample size, not the "
              "acceptance. Read those rows as upper bounds.")
    print("\nReading: an independence sampler is usable when acceptance is a few\n"
          "percent or better. What is measured here is not a small acceptance --\n"
          "it is an acceptance too small for 512 samples to resolve, with one\n"
          "configuration holding ~100% of the weight. The qualitative verdict is\n"
          "robust even though the number is not: independence-MH on THIS proposal\n"
          "is not viable at these volumes.\n"
          "That is a statement about the proposal, not about the MH route. The\n"
          "fallback is a variant that proposes smaller moves -- partial (block)\n"
          "updates, or delayed rejection -- where acceptance is tunable by move\n"
          "size instead of being fixed by the global density mismatch.")

    out = REPO / args.out
    out.write_text(json.dumps(
        {f"{r['L']}:{r['beta']:g}": r for r in rows.values()}, indent=2),
        encoding="utf-8")
    print(f"\nwrote {out.relative_to(REPO)}")


if __name__ == "__main__":
    main()
