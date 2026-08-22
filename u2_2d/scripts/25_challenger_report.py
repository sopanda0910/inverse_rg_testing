"""A/B the retrained challenger against the deployed incumbent.

WHY THIS EXISTS AS A SCRIPT RATHER THAN A JUDGEMENT CALL AFTERWARDS. The
2026-08-20 coverage retrain looked like a clear win on the number it was aimed at
-- L = 64 extended-loop mean |z| went 1.14 -> 0.34 -- and was a net LOSS once the
rest was checked: L = 32 regressed 0.52 -> 0.92, the density gap regressed at all
four cases, and seed quality collapsed (t_therm 24 -> 46, tuned sweeps 5 -> 30).
A retrain aimed at one quantity will generally trade against the others, so the
criteria have to be fixed before the numbers are known. These four were declared
in `run_overnight.ps1` before the run started:

  (a) <Q^2> at the top rung moves TOWARD exact          -- the reason for this retrain
  (b) seed quality does not regress                     -- what the last one broke
  (c) L = 32 extended-loop mean |z| does not regress    -- ditto
  (d) density gap does not regress                      -- ditto

(a) is the target; (b)-(d) are guards. A challenger that wins (a) and loses two
guards is a trade, not an improvement, and the incumbent stays deployed.

Nothing here promotes anything. It prints a verdict and writes a report; moving
det_score_net_v2.pt into place is a separate, deliberate act.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out" / "u2_2d"


def load(path: Path):
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def fmt(value, spec=".4f"):
    if value is None:
        return "  --  "
    try:
        return format(float(value), spec)
    except (TypeError, ValueError):
        return str(value)


def arm_of(bench, name):
    if not bench:
        return None
    for arm in bench.get("arms", []):
        if arm.get("arm") == name:
            return arm
    return None


def criterion_a(rows):
    """<Q^2>, reported at the BASE, not at the top rung.

    CORRECTED 2026-08-21, before any verdict was read. This criterion originally
    compared <Q^2> at the top rung and that is not a test of the score net.
    Topology is TRANSPORTED, not generated: `enforce_coarse_charge` sets the fine
    charge from the coarse one, so an inverse-RG step moves <Q^2> by an identity
    and the network cannot influence it even in principle. The top-rung number is
    a property of (i) the base ensemble's P(Q) and (ii) which 1024 of the base's
    4096 configurations the ladder happened to subsample.

    Measured, which is what forced the correction: the incumbent's base carries
    <Q^2> = 0.9668 and its ladder reports 1.0156; the challenger's base carries
    0.9822 -- closer to exact -- and its ladder reports 0.9121. Both ladders sit
    within ~1.6 SEM of their own base (SEM ~ 0.044 at 1024 independent charges),
    so the apparent 1.0156-vs-0.9121 gap is a subsample draw and nothing else.
    Scoring the challenger on it would have failed it for the training structure
    on a quantity training cannot reach.

    So the base is what gets the verdict, and the top rung is reported for
    information with the draw noise attached.
    """
    import math

    inc_base = load(OUT / "data" / "summary.json")
    cha_base = load(OUT / f"data_{DATA_SUFFIX}" / "summary.json")

    def base_q2(summary):
        if not summary:
            return None
        for r in summary:
            if (isinstance(r, dict) and r.get("lattice_size") == 16
                    and abs(float(r.get("beta", 0)) - 28.0) < 1e-6):
                return r.get("q_squared"), r.get("n_chains") or 1024
        return None

    bi, bc = base_q2(inc_base), base_q2(cha_base)
    if bi and bc:
        exact = 1.0011887008808318
        sem = math.sqrt(2.0 / bc[1])
        zi, zc = (bi[0] - exact) / sem, (bc[0] - exact) / sem
        verdict = "PASS" if abs(zc) <= abs(zi) else "FAIL"
        rows.append(("(a) <Q^2> ladder base", bi[0], bc[0], verdict,
                     f"exact {exact:.4f}, SEM {sem:.3f}; z {zi:+.2f} -> {zc:+.2f}"))
    else:
        rows.append(("(a) <Q^2> ladder base", None, None, "MISSING", ""))

    inc = arm_of(load(OUT / "seed_benchmark" / "seed_benchmark.json"), "A_diffusion_seed")
    cha = arm_of(load(OUT / f"seed_benchmark_{SUFFIX}" / "seed_benchmark.json"), "A_diffusion_seed")
    if inc and cha:
        rows.append(("    <Q^2> top rung", inc["topology"]["q_squared"],
                     cha["topology"]["q_squared"], "info",
                     "transported identity: subsample draw, NOT a model test"))
        return
    if not (inc and cha):
        return
    # Coverage is reported alongside, not as a gate: with the marginal odd move
    # every ergodic arm now reaches 1.000, so it no longer discriminates.
    rows.append(("    P(Q) covered", inc["topology"]["exact_probability_covered"],
                 cha["topology"]["exact_probability_covered"], "info", ""))


def criterion_b(rows):
    """Seed quality: t_therm and the tuned sweeps the lift needs."""
    # BOTH sides must come from a `_matched` directory. The overnight queue ran
    # stage 17 with default arms and --n-retherm 10, and at 10 retherm sweeps the
    # ablation is destroyed: `halve` sits 19% from exact pre-retherm and still
    # scores t_therm = 0, because the rethermalization, not the lift, is what the
    # measurement then sees. The incumbent's record is --n-retherm 0, and the
    # challenger is re-run on that protocol into `_v2_matched`.
    for size, tag in ((32, "L32"), (64, "L64")):
        inc = load(OUT / f"prolongator_{tag}_matched" / "prolongator.json")
        cha = load(OUT / f"prolongator_{tag}_{SUFFIX}_matched" / "prolongator.json")
        if not (inc and cha):
            rows.append((f"(b) seed quality {tag}", None, None, "MISSING", ""))
            continue

        def pick(data, arm):
            for entry in data:
                if entry.get("arm") == arm:
                    return entry
            return {}

        i, c = pick(inc, "diffusion_tuned"), pick(cha, "diffusion_tuned")
        it, ct = i.get("t_therm_slowest"), c.get("t_therm_slowest")
        isw, csw = i.get("tuned_sweeps"), c.get("tuned_sweeps")
        ok = (ct is not None and it is not None and ct <= it) and \
             (csw is not None and isw is not None and csw <= isw)
        rows.append((f"(b) t_therm {tag}", it, ct, "PASS" if ok else "FAIL",
                     f"tuned sweeps {isw} -> {csw}"))


def criterion_c(rows):
    """Extended-loop mean |z| vs the CLOSED FORM, at L = 32 and L = 64.

    Against exact, not against the HMC reference. The reference ensemble is
    regenerated alongside the challenger, so a z-vs-reference column compares two
    things that both moved; the closed form is the only fixed rule here.

    "Extended" is area >= 16 (4x4 and up), because that is where U(1) found the
    residual model error concentrates -- std(z) grew 1.09 -> 1.44 from W(4x4) to
    W(12x12) -- and the plaquette agrees to parts in 10^4 whatever the model does.

    A `mean |z|` IS NOT READ AGAINST ZERO, AND ITS RESOLUTION IS NOT sqrt(N_rows)
    (added 2026-08-22). Two corrections, both of which changed how the numbers
    this criterion has already produced should be read:

      * The null is `sqrt(2/pi) = 0.798`, because |z| is half-normal when the
        model is exactly right and the errors are correct. So an extended-loop
        score of 0.187 is four times "better than perfect" and is evidence about
        the error bars rather than about the model, and the v2 move 0.187 ->
        0.292 goes TOWARD the null, not away from it.
      * The standard error of that mean is `sqrt(1 - 2/pi) / sqrt(N_eff)`, and
        `N_eff` is the participation ratio of the observables' correlation
        matrix, NOT the row count. It is 3.77 at L = 32 against 41 rows, because
        2D Wilson loops of different sizes are near-deterministic functions of
        one another. Reading 0.187 as 6.5 sigma from the null was wrong by 3.3x;
        it is 2.0 sigma.

    The declared 5% verdict is left exactly as it was -- moving a gate after the
    numbers are known is the failure this script exists to prevent -- but every
    row now carries the resolution beside it, so a "FAIL" that is a fifth of a
    sigma cannot be quoted as a regression.
    """
    import math

    import numpy as np

    # Measured participation ratios, used only when a summary predates
    # `validate.report.compare` recording its own (see
    # `47_effective_observables.py`, which back-fills them).
    N_EFF_FALLBACK = {32: 3.77, 64: 3.25}

    def mean_ext_z(summary):
        out = {}
        for r in summary or []:
            vals = []
            for row in r.get("rows", []):
                name = row.get("observable", "")
                if "wilson_" not in name or "det_" in name:
                    continue
                try:
                    a, b = name.split("wilson_")[1].split("x")
                    area = int(a) * int(b)
                except ValueError:
                    continue
                z = row.get("z_vs_exact")
                if area >= 16 and z is not None:
                    vals.append(abs(float(z)))
            if vals:
                size = r["lattice_size"]
                n_eff = (r.get("n_effective_extended") or r.get("n_effective")
                         or N_EFF_FALLBACK.get(size) or len(vals))
                out[size] = (float(np.mean(vals)), float(n_eff), len(vals))
        return out

    inc = mean_ext_z(load(OUT / "validation" / "summary.json"))
    cha = mean_ext_z(load(OUT / f"validation_{SUFFIX}" / "summary.json"))
    if not (inc and cha):
        rows.append(("(c) extended loops", None, None, "MISSING", ""))
        return
    null = math.sqrt(2.0 / math.pi)
    for size in sorted(set(inc) & set(cha)):
        (i, n_eff, n_rows), (c, _, _) = inc[size], cha[size]
        se = math.sqrt(1.0 - 2.0 / math.pi) / math.sqrt(max(n_eff, 1e-9))
        # The two scores share the observable set and much of the noise, so this
        # is a resolution scale rather than a paired test; it is quoted as such.
        moved = abs(c - i) / max(se, 1e-30)
        rows.append((f"(c) ext loops L={size}", i, c,
                     "PASS" if c <= i * 1.05 else "FAIL",
                     f"mean |z| vs exact, area >= 16 (5% tolerance); null "
                     f"{null:.3f}, N_eff {n_eff:.2f} of {n_rows} rows, "
                     f"SE {se:.2f} -- the move is {moved:.1f} SE"
                     + ("" if moved >= 1.0 else ", i.e. UNRESOLVED")))


def criterion_d(rows):
    """Density gap: KL per site at each case."""
    inc = load(OUT / "density_gap" / "density_gap.json")
    cha = load(OUT / f"density_gap_{SUFFIX}" / "density_gap.json")
    if not (inc and cha):
        rows.append(("(d) density gap", None, None, "MISSING", ""))
        return
    by_case = {e["case"]: e for e in cha}
    worse = 0
    for entry in inc:
        case = entry["case"]
        other = by_case.get(case)
        if not other:
            continue
        i = entry["free_energy_certificate"]["kl_per_site"]
        c = other["free_energy_certificate"]["kl_per_site"]
        if c > i:
            worse += 1
        rows.append((f"(d) KL/site {case}", i, c, "PASS" if c <= i else "FAIL", ""))
    rows.append(("(d) density gap overall", None, None,
                 "PASS" if worse == 0 else "FAIL", f"{worse} of {len(inc)} cases worse"))


SUFFIX = "v2"
DATA_SUFFIX = "v2"
LABEL = "(114 rungs, 3 volumes, random beta, sector augmentation)"


def main() -> None:
    global SUFFIX, LABEL
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    # The four criteria read challenger artefacts by a common suffix, so a new
    # challenger needs a flag rather than a forked script. Everything else --
    # what counts as a target, what counts as a guard, and the INCOMPLETE rule
    # -- is shared, which is the point.
    ap.add_argument("--suffix", default="v2",
                    help="challenger artefact suffix, e.g. v2 or cap")
    ap.add_argument("--label", default=None, help="one-line description")
    # The CAPACITY challenger reuses data_v2 unchanged -- that is the point of it,
    # since both previous attempts moved the data and regressed. So its data-side
    # criterion is v2's, and saying so explicitly beats silently reporting the
    # criterion as MISSING when the answer is "identical by construction".
    ap.add_argument("--data-suffix", default=None,
                    help="suffix for the DATA artefacts, if it differs from "
                         "--suffix (capacity experiment: v2)")
    ap.add_argument("--out", default=None, help="report path")
    args = ap.parse_args()
    SUFFIX = args.suffix
    global DATA_SUFFIX
    DATA_SUFFIX = args.data_suffix or ("v2" if SUFFIX == "cap" else SUFFIX)
    if args.label:
        LABEL = args.label
    elif SUFFIX == "cap":
        LABEL = "(hidden 96, depth 5, batch 64, 260 epochs, SAME data_v2)"

    rows: list[tuple] = []
    criterion_a(rows)
    criterion_b(rows)
    criterion_c(rows)
    criterion_d(rows)

    lines = ["# Challenger vs incumbent", "",
             "Incumbent: `out/u2_2d/checkpoints/det_score_net.pt` (12 fixed couplings)",
             f"Challenger: `out/u2_2d/checkpoints/det_score_net_{SUFFIX}.pt` "
             + LABEL, "",
             f"| {'criterion':<26} | {'incumbent':>12} | {'challenger':>12} | verdict | note |",
             f"| {'-'*26} | {'-'*12}:| {'-'*12}:| --- | --- |"]
    for name, inc, cha, verdict, note in rows:
        lines.append(f"| {name:<26} | {fmt(inc):>12} | {fmt(cha):>12} | {verdict} | {note} |")

    lines += ["",
              "**Reading criterion (c).** `mean |z|` is not read against zero. "
              "|z| is half-normal when the model is exactly right and the error "
              "bars are correct, so the null is `sqrt(2/pi) = 0.798`; a score "
              "far BELOW it is evidence of overestimated errors or of correlated "
              "observables, not of a good model. The resolution of the mean is "
              "`sqrt(1 - 2/pi) / sqrt(N_eff)` with `N_eff` the participation "
              "ratio of the observables' correlation matrix. Over the whole "
              "scorecard that is 3.73 at L = 32 against 41 rows; over the "
              "area >= 16 subset this criterion actually averages it is "
              "**1.45**, so those thirteen loops are worth about one and a "
              "half independent observables and the standard error of their "
              "mean |z| is ~0.50. A move of a tenth is a fifth of a standard "
              "error and is not a regression.", ""]

    gates = [r[3] for r in rows if r[3] in ("PASS", "FAIL")]
    failed = gates.count("FAIL")
    target_ok = any(r[0].startswith("(a)") and r[3] == "PASS" for r in rows)
    # A criterion that could not be evaluated is NOT a criterion that passed.
    # Without this the report says "DEPLOY THE CHALLENGER" as soon as (a) lands
    # and the three guards are still MISSING -- which is exactly the reading the
    # guards exist to prevent, and it is worst when the queue is still running.
    missing = [r[0] for r in rows if r[3] == "MISSING"]
    lines += ["", "## Verdict", ""]
    if missing:
        lines.append(f"**INCOMPLETE** -- {len(missing)} criterion/criteria not yet "
                     f"measured: {', '.join(missing)}. No verdict until all four "
                     "are in; a missing guard is not a passed guard.")
    elif not gates:
        lines.append("**INCONCLUSIVE** -- no criterion could be evaluated.")
    elif failed == 0 and target_ok:
        lines.append("**DEPLOY THE CHALLENGER.** It moves the target and trips no guard.")
    elif target_ok and failed:
        lines.append(f"**TRADE, NOT AN IMPROVEMENT** -- target met, {failed} guard(s) "
                     "regressed. Incumbent stays deployed unless the regressions are "
                     "argued case by case.")
    else:
        lines.append(f"**KEEP THE INCUMBENT** -- target not met, {failed} guard(s) failed.")
    lines += ["", "Promotion is a separate deliberate act: copy "
              f"`det_score_net_{SUFFIX}.pt` over `det_score_net.pt` and re-run the "
              "downstream stages against `default.yaml`.", ""]

    text = "\n".join(lines)
    print(text)
    dest = Path(args.out) if args.out else (
        OUT / ("challenger_report.md" if SUFFIX == "v2"
               else f"challenger_report_{SUFFIX}.md"))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    print(f"\nwrote {dest}")


if __name__ == "__main__":
    main()
