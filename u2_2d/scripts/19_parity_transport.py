"""Stage 19: is the base's parity weight right because it was sampled, or by luck?

The gap this closes. Section 12.2 is honest that the ladder base does NOT sample
the odd/even weight: at L = 16, beta = 28 there are **zero** parity flips ever, so
the weight is frozen in during the hot-start ordering, one independent draw per
chain. The defence is an argument, not a measurement -- exact P(odd) is within
1% of 1/2 whenever <Q^2> >~ 1, and the base has <Q^2> = 1.0012, so a frozen-in
weight is right to ~0.007 absolute. A referee is entitled to ask for the
measurement, and there are two halves to it.

  POSITIVE CONTROL. L = 16, beta = 14 has 2453 parity flips (stage 15), so its
  parity weight is genuinely SAMPLED. Climb the ladder from there --
  beta = 14 -> 49.05 -> 190.02, both model betas inside the training range, so no
  retraining is involved -- and check that every rung reproduces exact P(odd).
  If transport is the identity the design claims, it must.

  FAILURE BOUNDARY. The argument has a stated validity condition, <Q^2> >~ 1,
  and it is worth showing where it breaks rather than only where it holds. This
  script evaluates the exact odd weight across couplings and marks where a
  frozen-in ~1/2 would be wrong by more than the ensemble can resolve. At
  L = 8, beta = 20 the exact odd weight is 0.3335, and a hot quench returns
  0.5156 -- wrong by +55%. Quoting the safe case without the boundary is what
  makes the defence look like special pleading.

Both halves go in the paper. The first says the mechanism works; the second says
we know when it would not, which is the part that makes the first believable.

    python u2_2d/scripts/19_parity_transport.py \
        --ladders out/u2_2d/ladder out/u2_2d/ladder_mobile
"""

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u2_2d.lgt.exact import (
    det_topological_charge_distribution,
    det_topological_susceptibility,
)
from u2_2d.lgt.lattice import topological_charge
from u2_2d.utils import load_config, load_ensemble, save_json

# couplings the failure-boundary scan walks; L = 8 and 16 are where the study
# has parity-flip counts from stage 15, so the two tables can be read together.
BOUNDARY = [(8, b) for b in (6, 10, 14, 20, 28)] + [(16, b) for b in (14, 21, 28, 56)]


def exact_odd_weight(beta: float, size: int) -> tuple[float, float]:
    q, p = det_topological_charge_distribution(beta, size)
    odd = float(sum(pi for qi, pi in zip(q, p) if int(qi) % 2))
    q2 = float(det_topological_susceptibility(beta, size) * size * size)
    return odd, q2


def chi2_against_exact(charge: np.ndarray, beta: float, size: int,
                       min_expected: float = 5.0) -> dict:
    """Pooled chi^2 of the sector histogram against exact P(Q).

    Bins whose EXPECTED count falls below `min_expected` are pooled into the
    tails rather than dropped: dropping them is what silently shrinks a
    denominator, and section 22 lists that as one of the three habits not to
    repeat from the U(1) write-up.
    """
    q_values, probs = det_topological_charge_distribution(beta, size)
    n = charge.size
    counts = np.array([(charge == q).sum() for q in q_values], dtype=float)
    expected = probs * n

    keep = expected >= min_expected
    if keep.sum() < 2:
        return {"chi2": None, "dof": 0, "p_value": None, "testable_bins": int(keep.sum())}
    obs = list(counts[keep])
    exp = list(expected[keep])
    # pool everything below threshold into one tail bin so the total is conserved
    pooled_obs, pooled_exp = counts[~keep].sum(), expected[~keep].sum()
    if pooled_exp >= min_expected:
        obs.append(pooled_obs)
        exp.append(pooled_exp)
    obs, exp = np.array(obs), np.array(exp)
    chi2 = float(((obs - exp) ** 2 / exp).sum())
    dof = len(obs) - 1
    from scipy.stats import chi2 as chi2_dist

    return {"chi2": chi2, "dof": dof,
            "p_value": float(chi2_dist.sf(chi2, dof)),
            "testable_bins": int(len(obs))}


def measure_ensemble(path: Path) -> dict | None:
    configs, meta = load_ensemble(path)
    with torch.no_grad():
        charge = topological_charge(configs).cpu().numpy()
    size = int(configs.shape[-2])
    beta = float(meta.get("beta", 0.0)) if meta else 0.0
    if not beta:
        # fall back to the filename, which encodes it
        stem = path.stem
        beta = float(stem.split("beta")[-1])
    n = charge.size
    odd = float((np.abs(charge) % 2 == 1).mean())
    odd_exact, q2_exact = exact_odd_weight(beta, size)
    sem = math.sqrt(max(odd_exact * (1 - odd_exact), 1e-12) / n)
    return {
        "path": str(path),
        "lattice_size": size,
        "beta": beta,
        "n": int(n),
        "odd_fraction": odd,
        "odd_fraction_exact": odd_exact,
        "odd_sem": sem,
        "odd_z": (odd - odd_exact) / sem,
        "q_squared": float((charge ** 2).mean()),
        "q_squared_exact": q2_exact,
        "chi2": chi2_against_exact(charge, beta, size),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="u2_2d/configs/default.yaml")
    parser.add_argument("--ladders", nargs="+",
                        default=["out/u2_2d/ladder", "out/u2_2d/ladder_mobile"])
    parser.add_argument("--bases", nargs="+", default=["16:14", "16:28"],
                        help="L:beta stage-01 ensembles to score as well")
    parser.add_argument("--out-dir", default="out/u2_2d/parity_transport")
    args = parser.parse_args()

    config = load_config(args.config)
    data_dir = Path(config["data"].get("out_dir", "out/u2_2d/data"))

    rows = []
    for spec in args.bases:
        L, b = spec.split(":")
        path = data_dir / f"u2_L{int(L)}_beta{float(b):g}.pt"
        if not path.exists():
            print(f"[skip] base {spec}: missing {path}")
            continue
        row = measure_ensemble(path)
        row["kind"] = "base"
        row["ladder"] = "-"
        rows.append(row)

    for d in args.ladders:
        d = Path(d)
        if not d.exists():
            print(f"[skip] ladder {d}: not present")
            continue
        for path in sorted(d.glob("ladder_L*_beta*.pt")):
            row = measure_ensemble(path)
            row["kind"] = "rung"
            row["ladder"] = d.name
            rows.append(row)

    for r in rows:
        c = r["chi2"]
        print(f"{r['ladder']:>18s} {r['kind']:>4s} L={r['lattice_size']:3d} "
              f"beta={r['beta']:9.3f}  P(odd)={r['odd_fraction']:.4f} "
              f"(exact {r['odd_fraction_exact']:.4f}, z={r['odd_z']:+5.2f})  "
              f"<Q^2>={r['q_squared']:.4f} (exact {r['q_squared_exact']:.4f})  "
              f"chi2 p="
              + ("--" if c["p_value"] is None else f"{c['p_value']:.3f}"))

    boundary = []
    for L, b in BOUNDARY:
        odd, q2 = exact_odd_weight(float(b), L)
        boundary.append({"lattice_size": L, "beta": float(b),
                         "odd_exact": odd, "q_squared_exact": q2,
                         "half_error": 0.5 - odd})

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    save_json(out_dir / "parity_transport.json",
              {"ensembles": rows, "boundary": boundary})
    _write_report(out_dir / "report.md", rows, boundary)
    print(f"\nwrote {out_dir / 'parity_transport.json'} and report.md")
    return 0


def _write_report(path: Path, rows: list, boundary: list) -> None:
    lines = [
        "# Parity transport: sampled at the base, or frozen in and lucky?",
        "",
        "## Measured",
        "",
        "| ladder | | $L$ | $\\beta$ | $n$ | $P({\\rm odd})$ | exact | $z$ | "
        "$\\langle Q^2\\rangle$ | exact | $\\chi^2$ $p$ |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        c = r["chi2"]
        lines.append(
            f"| {r['ladder']} | {r['kind']} | {r['lattice_size']} | {r['beta']:g} | "
            f"{r['n']} | {r['odd_fraction']:.4f} | {r['odd_fraction_exact']:.4f} | "
            f"${r['odd_z']:+.2f}$ | {r['q_squared']:.4f} | "
            f"{r['q_squared_exact']:.4f} | "
            + ("--" if c["p_value"] is None else f"{c['p_value']:.3f}") + " |")

    lines += [
        "",
        "The `ladder_mobile` rows are the positive control: their base "
        "($L = 16$, $\\beta = 14$) records 2453 parity flips in stage 15, so its "
        "odd/even weight is genuinely **sampled** rather than frozen in at "
        "ordering. If sector transport is the identity the design claims, every "
        "rung above it must reproduce exact $P({\\rm odd})$ -- and the ladder of "
        "record, whose base has zero flips, must agree with it.",
        "",
        "## Where the frozen-in argument would fail",
        "",
        "The defence in section 12.2 is conditional: a frozen-in weight lands near "
        "$1/2$, and exact $P({\\rm odd})$ is near $1/2$ only while "
        "$\\langle Q^2\\rangle \\gtrsim 1$. Below that the two part company, and "
        "the quench is simply wrong.",
        "",
        "| $L$ | $\\beta$ | exact $\\langle Q^2\\rangle$ | exact $P({\\rm odd})$ | "
        "error of assuming $1/2$ |",
        "|---|---|---|---|---|",
    ]
    for b in boundary:
        lines.append(
            f"| {b['lattice_size']} | {b['beta']:g} | {b['q_squared_exact']:.4f} | "
            f"{b['odd_exact']:.4f} | ${b['half_error']:+.4f}$ |")

    lines += [
        "",
        "Read the two columns together. Wherever $\\langle Q^2\\rangle \\gtrsim 1$ "
        "the error of assuming $1/2$ is under a percent and a hot quench is safe; "
        "where $\\langle Q^2\\rangle$ falls well below 1 it is not. The measured "
        "case is $L = 8$, $\\beta = 20$: exact $P({\\rm odd}) = 0.3335$, hot quench "
        "$0.5156$, wrong by $+55\\%$. **State the condition, not just the "
        "conclusion** -- a base with a narrow $P(Q)$ would fail this badly, and "
        "the ladder base is safe because it satisfies the condition, not because "
        "quenching samples parity.",
        "",
        "Source: `u2_2d/scripts/19_parity_transport.py`.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
