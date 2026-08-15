"""How often does the AIS bridge actually work at the headline case?

Table S7 quotes one seed at 32:218.58 and reads it as the mechanism working as
derived. It does -- when it works. Across every run of that case at the shipped
protocol (n=96, 48 bridge steps, final7 basis) the held-out spread either
reduces by roughly the predicted factor or diverges by three orders of
magnitude, with nothing in between. This collects them and reports the rate.

Runs are pooled by (case, n, n_bridge, basis), not by directory name, so
seeds from separate campaigns count once each and nothing is quietly dropped.

    .venv/Scripts/python.exe u1_2d/scripts/parse_ais_seed_rate.py
"""

import json
import math
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CASE = (32, 218.58)
PROTOCOL = {"n": 96, "n_bridge": 48, "basis_width": 7}
BLOWUP = 10.0  # held-out std this many times the baseline is a divergence, not a fit


def collect() -> list[dict]:
    runs = {}
    for path in sorted(REPO.glob("artifacts/**/ais_results.json")) + \
            sorted(REPO.glob("out/u1_2d/**/ais_results.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        # A run file is either one case or a list of them.
        cases = doc if isinstance(doc, list) else [doc]
        for j in cases:
            if not isinstance(j, dict):
                continue
            if (j.get("fine_L"), round(j.get("fine_beta", 0), 2)) != CASE:
                continue
            if j.get("n") != PROTOCOL["n"]:
                continue
            ais = j.get("ais", {})
            if ais.get("n_bridge") != PROTOCOL["n_bridge"]:
                continue
            # No basis field is written; the coefficient count is the basis.
            if len(j["surrogate_fit"]["std_coefficients"]) != PROTOCOL["basis_width"]:
                continue
            before = j["baseline"]["log_weight_std_fiber"]
            after = ais["log_weight_std_heldout"]
            runs[path.parent.name] = {
                "run": path.parent.name,
                "before": before,
                "after": after,
                "ratio": before / after if after else float("inf"),
                "surrogate_r2_heldout": 1 - (j["surrogate_fit"]["resid_std_heldout"] /
                                             j["surrogate_fit"]["target_std"]) ** 2,
                "hmc_acc_min": ais.get("hmc_acceptance_min"),
                "final_step": ais.get("final_step_size"),
                "step": ais.get("step_size"),
                "kl_per_site": j.get("free_energy_certificate", {}).get("kl_per_site"),
                "diverged": after > BLOWUP * before,
            }
    return sorted(runs.values(), key=lambda r: r["run"])


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def main() -> None:
    runs = collect()
    if not runs:
        print("no matching runs")
        return
    print(f"case {CASE[0]}:{CASE[1]}, n={PROTOCOL['n']}, "
          f"n_bridge={PROTOCOL['n_bridge']} -- {len(runs)} seeds\n")
    print("| run | std before | std after (held-out) | reduction | held-out R^2 | "
          "min HMC acc | step collapsed | KL/site |")
    print("|---|---|---|---|---|---|---|---|")
    for r in runs:
        collapsed = "yes" if r["final_step"] and r["step"] and \
            r["final_step"] < 0.5 * r["step"] else "no"
        red = "DIVERGED" if r["diverged"] else f"{r['ratio']:.2f}x"
        kl = f"{r['kl_per_site']:.2f}" if r["kl_per_site"] is not None else "--"
        print(f"| {r['run']} | {r['before']:.1f} | {r['after']:.1f} | {red} | "
              f"{r['surrogate_r2_heldout']:.3f} | {r['hmc_acc_min']:.3f} | "
              f"{collapsed} | {kl} |")

    bad = [r for r in runs if r["diverged"]]
    good = [r for r in runs if not r["diverged"]]
    lo, hi = wilson_ci(len(bad), len(runs))
    print(f"\ndiverged {len(bad)}/{len(runs)} = {100 * len(bad) / len(runs):.0f}% "
          f"(95% CI {100 * lo:.0f}-{100 * hi:.0f}%, score interval)")
    if good:
        ratios = [r["ratio"] for r in good]
        print(f"when it works: {min(ratios):.2f}-{max(ratios):.2f}x reduction, "
              f"mean {statistics.fmean(ratios):.2f}x")
        kls = [r["kl_per_site"] for r in good if r["kl_per_site"] is not None]
        if kls:
            print(f"KL/site over non-diverged seeds: {min(kls):.2f}-{max(kls):.2f} "
                  f"nats (mean {statistics.fmean(kls):.2f})")
    if bad and good:
        r2s = [r["surrogate_r2_heldout"] for r in bad]
        g2s = [r["surrogate_r2_heldout"] for r in good]
        print(f"held-out R^2 does NOT separate them: diverged "
              f"{min(r2s):.3f}-{max(r2s):.3f} vs healthy {min(g2s):.3f}-{max(g2s):.3f}")
        accs, gaccs = [r["hmc_acc_min"] for r in bad], [r["hmc_acc_min"] for r in good]
        print(f"min bridge-HMC acceptance DOES: diverged "
              f"{min(accs):.3f}-{max(accs):.3f} vs healthy "
              f"{min(gaccs):.3f}-{max(gaccs):.3f} -- "
              f"{'separable' if max(accs) < min(gaccs) else 'overlapping'}")

    out = REPO / "out" / "u1_2d" / "ais_transport" / "seed_rate.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "case": f"{CASE[0]}:{CASE[1]}",
        "protocol": PROTOCOL,
        "runs": runs,
        "n_seeds": len(runs),
        "n_diverged": len(bad),
        "divergence_rate": len(bad) / len(runs),
        "wilson_ci_95": [lo, hi],
        "reduction_when_working": [min(r["ratio"] for r in good),
                                   max(r["ratio"] for r in good)] if good else None,
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {out.relative_to(REPO)}")


if __name__ == "__main__":
    main()
