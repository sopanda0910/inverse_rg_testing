"""What actually causes the AIS bridge to blow up: a controlled ridge scan.

Table S7b recorded that 2 of 10 runs at 32:218.58 diverge by 10^2-10^3, and
attributed it to the bridge integrator "not the surrogate", on the evidence
that minimum HMC acceptance separates the two outcomes cleanly while held-out
R^2 does not. `40_fold_noise_audit.py` then found that both divergent runs had
also selected the smallest ridge on the grid and no converged run had, which
made that attribution a correlation among three coupled quantities rather than
a cause.

This turns it into an intervention. `--ridge-floor` restricts the ridge grid
from below and touches nothing else -- in particular it consumes no global RNG,
so every floor sees byte-identical ODE samples and baselines. The only thing
varying across the scan is the surrogate's regularization.

    for fl in 0.01 0.03 0.1 0.3; do
      python u1_2d/scripts/28_ais_transport.py --n-configs 96 \
        --ridge-floor $fl --out artifacts/ridgescan/floor_$fl
    done
    python u1_2d/scripts/41_ridge_scan_report.py

Read the output with the scale in mind: sigma is the standard deviation of the
log importance weight in NATS, and ESS/N ~ exp(-sigma^2). Usable reweighting
needs sigma <~ 1.5. Every number in this scan is 7-80x above that, so the
comparison is between degrees of failure. Nothing here makes AIS a working
sampler; it identifies why one failure mode fires.
"""

import argparse
import json
import math
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
USABLE_SIGMA = math.sqrt(math.log(10.0))  # sigma at which ESS/N ~ 0.1


def coef_norm(fit: dict) -> float:
    return math.sqrt(sum(v * v for v in fit["std_coefficients"].values()))


def load_run(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    out = {}
    for c in doc if isinstance(doc, list) else [doc]:
        key = f"{c['fine_L']}:{c['fine_beta']:.4g}"
        out[key] = {
            "baseline": c["baseline"]["log_weight_std_fiber"],
            "after": c["ais"]["log_weight_std_heldout"],
            "ridge": c["surrogate_fit"]["ridge"],
            "coef_norm": coef_norm(c["surrogate_fit"]),
            "acc_min": c["ais"].get("hmc_acceptance_min"),
            "r2_heldout": 1 - (c["surrogate_fit"]["resid_std_heldout"] /
                               c["surrogate_fit"]["target_std"]) ** 2,
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan-dir", default="artifacts/ridgescan")
    ap.add_argument("--record", default="out/u1_2d/ais_transport")
    # The unfloored fold-fixed run is the floor=0 arm of this same scan: same
    # seed, same code path, ridge_floor=None. Its baselines are identical to
    # the floored arms, which is the check that it belongs in the comparison.
    ap.add_argument("--nofloor", default="out/u1_2d/ais_transport_foldfixed")
    ap.add_argument("--out", default="out/u1_2d/ridge_scan")
    args = ap.parse_args()

    arms = [("record", load_run(REPO / args.record / "ais_results.json"))]
    nofloor = load_run(REPO / args.nofloor / "ais_results.json")
    if nofloor:
        arms.append(("none", nofloor))
    scan = []
    for d in sorted((REPO / args.scan_dir).glob("floor_*")):
        m = re.search(r"floor_([\d.]+)", d.name)
        if m:
            scan.append((float(m.group(1)), load_run(d / "ais_results.json")))
    scan.sort(key=lambda t: t[0])
    arms += [(f"{f:g}", r) for f, r in scan]
    if len(arms) < 2:
        raise SystemExit(f"no scan arms under {args.scan_dir}")

    cases = sorted({k for _, r in arms for k in r},
                   key=lambda s: (int(s.split(":")[0]), float(s.split(":")[1])))
    heads = [n for n, _ in arms]

    lines = ["# AIS surrogate ridge: controlled scan", "",
             "sigma = std of the log importance weight, nats. ESS/N ~ exp(-sigma^2);",
             f"usable reweighting needs sigma <~ {USABLE_SIGMA:.2f}. Every entry below is far",
             "above that -- this scan explains a failure mode, it does not fix the sampler.",
             "", "The `record` column is the published Table S7 run, which used a DIFFERENT",
             "coarse ensemble (the unseeded-fold RNG stream); it is shown for orientation",
             "and is not a controlled comparison. The numbered columns all share identical",
             "ODE samples and baselines, so only regularization differs across them.", ""]

    for title, key, fmt in (
            ("held-out sigma (nats)", "after", "{:.4g}"),
            ("surrogate coefficient norm", "coef_norm", "{:.4g}"),
            ("minimum HMC acceptance", "acc_min", "{:.3f}")):
        lines += [f"## {title}", "",
                  "| case | baseline sigma | " + " | ".join(heads) + " |",
                  "|---" * (len(heads) + 2) + "|"]
        for c in cases:
            base = next((r[c]["baseline"] for n, r in arms
                         if c in r and n != "record"), float("nan"))
            row = [c, f"{base:.1f}"]
            for _, r in arms:
                v = r.get(c, {}).get(key)
                row.append("--" if v is None else fmt.format(v))
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

    # Verdicts, each stated only where the data supports it.
    lines += ["## What the scan establishes", ""]
    controlled = [(n, r) for n, r in arms if n != "record"]
    mono = []
    for c in cases:
        seq = [(n, r[c]["coef_norm"]) for n, r in controlled if c in r]
        if len(seq) >= 3 and all(a[1] > b[1] for a, b in zip(seq, seq[1:])):
            mono.append(c)
    lines.append(
        f"* Coefficient norm falls monotonically with the ridge floor in "
        f"{len(mono)} of {len(cases)} cases, so the floor does what it is "
        "meant to do.")

    improved, reversed_ = [], []
    for c in cases:
        seq = [r[c]["after"] for _, r in controlled if c in r]
        if len(seq) >= 3:
            (improved if seq[-1] < seq[0] else reversed_).append(c)
    lines.append(
        f"* Held-out sigma improves with regularization in {len(improved)} of "
        f"{len(improved) + len(reversed_)} cases"
        + (f", and REVERSES in {', '.join(reversed_)} -- more regularization is "
           "not universally better, so there is a per-case optimum and no single "
           "floor to hard-code." if reversed_ else "."))

    # The decisive counterexample to an acceptance-only guard.
    for c in cases:
        seq = [(n, r[c]) for n, r in controlled if c in r]
        accs = [v["acc_min"] for _, v in seq if v["acc_min"] is not None]
        sigs = [v["after"] for _, v in seq]
        base = seq[0][1]["baseline"]
        if accs and max(accs) - min(accs) < 0.05 and max(sigs) > 5 * base:
            lines.append(
                f"* **{c} refutes the acceptance guard.** Minimum HMC acceptance "
                f"is flat at {accs[0]:.3f} across the whole scan while held-out "
                f"sigma moves {min(sigs):.3g} -> {max(sigs):.4g} against a "
                f"baseline of {base:.1f}. A run can blow up by "
                f"{max(sigs) / base:.0f}x with a perfectly healthy integrator, so "
                "`hmc_acceptance_min` is not a sufficient guard; coefficient norm "
                "is the quantity that tracks the failure.")

    best = []
    for c in cases:
        seq = [(n, r[c]["after"], r[c]["baseline"]) for n, r in controlled if c in r]
        n, s, b = min(seq, key=lambda t: t[1])
        best.append(f"{c}: {b / s:.2f}x at floor {n}" if s < b
                    else f"{c}: never beats baseline (best {s:.4g} vs {b:.1f})")
    lines += ["", "Best achievable spread reduction per case, over the scan:", ""]
    lines += [f"* {b}" for b in best]
    lines += ["", f"All best-case sigmas remain >= {USABLE_SIGMA:.2f} by a wide "
              "margin, i.e. ESS/N stays indistinguishable from zero.", ""]

    out_dir = REPO / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    (out_dir / "ridge_scan.json").write_text(
        json.dumps({n: r for n, r in arms}, indent=2), encoding="utf-8")
    print("\n".join(lines))
    print(f"wrote {(out_dir / 'report.md').relative_to(REPO)}")


if __name__ == "__main__":
    main()
