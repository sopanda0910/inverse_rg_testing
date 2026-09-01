"""Does the unseeded-fold bug invalidate the recorded AIS runs, or just annoy?

`fit_surrogate_cv` drew its CV fold permutation from ambient torch RNG, so the
ridge it selected was not a function of its inputs -- repeated calls on
identical data chose ridges spanning 0.003-0.03. That is fixed (`fold_seed`),
but every AIS run already on disk was collected under the bug, including the
ten seeds behind Table S7b.

Re-running those is ~14 GPU-hours, so the question is whether it would change
anything. It would only matter if a different ridge means a materially
different surrogate, and that is decided by the CV curve's SHAPE, which each
run already stores in `surrogate_fit.cv_table`:

  * flat across the plausible ridge window -> selection noise is real but
    inconsequential; the recorded runs stand, with the caveat stated.
  * sharply peaked -> the selected ridge was load-bearing and the runs were
    partly a coin flip; re-run.

Also checks the one thing that would be fatal: whether ridge selection
correlates with which seeds diverged. If the divergences sit at a particular
ridge, the Table S7b failure-mode attribution (bridge integrator, not
surrogate) is confounded and must be withdrawn.

    .venv/Scripts/python.exe u1_2d/scripts/40_fold_noise_audit.py
"""

import json
import math
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CASE = (32, 218.58)
PROTOCOL = {"n": 96, "n_bridge": 48, "basis_width": 7}
BLOWUP = 10.0
# The window a fold reshuffle could plausibly move the choice across, taken
# from the observed spread of selected ridges on identical inputs.
PLAUSIBLE = (0.001, 0.03)


def collect() -> list[dict]:
    runs = {}
    for path in sorted(REPO.glob("artifacts/**/ais_results.json")) + \
            sorted(REPO.glob("out/u1_2d/**/ais_results.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for j in (doc if isinstance(doc, list) else [doc]):
            if not isinstance(j, dict) or "surrogate_fit" not in j:
                continue
            if (j.get("fine_L"), round(j.get("fine_beta", 0), 2)) != CASE:
                continue
            if j.get("n") != PROTOCOL["n"]:
                continue
            ais = j.get("ais", {})
            if ais.get("n_bridge") != PROTOCOL["n_bridge"]:
                continue
            fit = j["surrogate_fit"]
            if len(fit["std_coefficients"]) != PROTOCOL["basis_width"]:
                continue
            table = {float(k): v for k, v in fit["cv_table"].items()}
            before = j["baseline"]["log_weight_std_fiber"]
            after = ais["log_weight_std_heldout"]
            coef = list(fit["std_coefficients"].values())
            runs[path.parent.name] = {
                "run": path.parent.name,
                "ridge": float(fit["ridge"]),
                "cv_table": table,
                "cv_at_selected": table[float(fit["ridge"])],
                "cv_best": min(table.values()),
                # Standardized-coefficient norm: how steep the surrogate makes
                # the bridge. This is the quantity the ridge controls, and the
                # quantity a fixed-step HMC has to cope with.
                "coef_norm": math.sqrt(sum(c * c for c in coef)),
                "diverged": after > BLOWUP * before,
                "ratio": before / after if after else float("inf"),
                "hmc_acc_min": ais.get("hmc_acceptance_min"),
                "r2_heldout": 1 - (fit["resid_std_heldout"] / fit["target_std"]) ** 2,
            }
    return sorted(runs.values(), key=lambda r: r["run"])


def window_spread(table: dict[float, float]) -> float:
    """Worst-case CV penalty from landing anywhere in the plausible window.

    This is the quantity the bug actually controls: not how good the chosen
    ridge was, but how much worse a different fold split could have made it.
    """
    vals = [v for k, v in table.items() if PLAUSIBLE[0] <= k <= PLAUSIBLE[1]]
    return max(vals) / min(vals) if vals else float("nan")


def main() -> None:
    runs = collect()
    if not runs:
        raise SystemExit("no runs found at the Table S7b protocol")

    print(f"AIS runs at {CASE[0]}:{CASE[1]:g}, protocol {PROTOCOL}\n")
    print("| run | ridge | CV at selected | CV best | penalty | worst-case over "
          "ridge window | held-out R^2 | min HMC acc | outcome |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in runs:
        pen = r["cv_at_selected"] / r["cv_best"]
        acc = "--" if r["hmc_acc_min"] is None else f"{r['hmc_acc_min']:.3f}"
        outcome = "DIVERGED" if r["diverged"] else f"{r['ratio']:.2f}x"
        print(f"| {r['run']} | {r['ridge']:g} | {r['cv_at_selected']:.3f} | "
              f"{r['cv_best']:.3f} | {pen:.3f}x | {window_spread(r['cv_table']):.3f}x | "
              f"{r['r2_heldout']:.3f} | {acc} | {outcome} |")

    spreads = [window_spread(r["cv_table"]) for r in runs
               if math.isfinite(window_spread(r["cv_table"]))]
    pens = [r["cv_at_selected"] / r["cv_best"] for r in runs]
    print(f"\nCV penalty actually paid   : {min(pens):.3f}-{max(pens):.3f}x "
          f"(median {statistics.median(pens):.3f}x)")
    print(f"Worst case over ridge window: {min(spreads):.3f}-{max(spreads):.3f}x "
          f"(median {statistics.median(spreads):.3f}x)")

    # The confound test: does ridge choice track divergence?
    div = [r for r in runs if r["diverged"]]
    ok = [r for r in runs if not r["diverged"]]
    print(f"\nridges among {len(div)} diverged : "
          f"{sorted({r['ridge'] for r in div})}")
    print(f"ridges among {len(ok)} converged: "
          f"{sorted({r['ridge'] for r in ok})}")
    shared = {r["ridge"] for r in div} & {r["ridge"] for r in ok}
    if div and ok:
        if shared:
            print(f"ridge {sorted(shared)} appears in BOTH outcomes -> ridge "
                  "selection does not explain the divergences.")
        else:
            k, n = len(div), len(runs)
            # Probability that the k diverged runs are exactly the k holding the
            # extreme ridge, if outcome were independent of ridge.
            p = 1.0 / math.comb(n, k)
            print(f"ridge values are DISJOINT between outcomes (p = 1/C({n},{k}) "
                  f"= {p:.3f} under independence).")

    # The proposed mechanism, testable from stored coefficients: a small ridge
    # leaves a large-norm surrogate, which makes the bridge steep, which a
    # fixed-step HMC cannot integrate. If true, coef_norm separates the outcomes
    # in the same direction as ridge and gives the chain a physical reading.
    print(f"\nsurrogate coefficient norm (steepness of the bridge)")
    print(f"  diverged : {sorted(round(r['coef_norm'], 1) for r in div)}")
    print(f"  converged: {sorted(round(r['coef_norm'], 1) for r in ok)}")
    if div and ok:
        if min(r["coef_norm"] for r in div) > max(r["coef_norm"] for r in ok):
            print("  -> separates cleanly, same direction as ridge. Reading: the "
                  "under-regularized\n     surrogate makes the bridge too steep "
                  "for the integrator. Surrogate and\n     integrator are ONE "
                  "failure mode, not two; the claim that the cause is the\n"
                  "     integrator 'not the surrogate' is not supported.")
        else:
            print("  -> does NOT separate, so the ridge-divergence association "
                  "does not run through\n     bridge steepness; the mechanism is "
                  "unidentified on the stored data.")

    worst = max(spreads) if spreads else float("nan")
    print("\nVerdict")
    if worst < 1.15:
        print(f"  The CV curve is flat over the ridge window (worst case "
              f"{worst:.2f}x). A different fold split would have chosen a "
              "different\n  ridge and gotten essentially the same surrogate. The "
              "recorded runs stand;\n  state the bug and this measurement, do not "
              "burn the GPU hours.")
    elif worst < 1.5:
        print(f"  Mild sensitivity (worst case {worst:.2f}x). Recorded runs are "
              "usable but the\n  fold noise is a real term in their error budget "
              "and must be quoted.")
    else:
        print(f"  Ridge choice is load-bearing (worst case {worst:.2f}x). "
              "Re-run the seeds.")


if __name__ == "__main__":
    main()
