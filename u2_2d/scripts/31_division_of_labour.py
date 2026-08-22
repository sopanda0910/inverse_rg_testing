"""Figure 22 -- what the model gets right, at which distance scale.

THE PRESENTATION OF RECORD IS z, AND THIS FIGURE DOES NOT CHANGE THAT. Panel (a)
is |z| = |mean - exact| / SEM, the same statistic fig18, fig20 and the validation
tables report. A systematic buried under a genuinely larger intrinsic fluctuation
IS genuinely less consequential, and z is the statistic that says so; large
Wilson loops fluctuate far more per configuration than the plaquette, so the same
absolute error legitimately shows as more significant on the plaquette. Nothing
below revises a published number.

Panel (b) carries the same content with the sample size divided out, because
there is one thing z cannot do on its own.

    z = sqrt(N) * bias / sigma

sqrt(N) is common to every observable in a given ensemble, so the SHAPE of the z
curve across observables already IS the shape of the N-independent ratio
bias/sigma -- panel (a) was never merely an error-bar artifact, and reading it as
one is a mistake this file made once. What panel (b) adds is that the shape
survives the choice of N: the same ensemble at 10x the configurations moves every
point in (a) up by sqrt(10) and none of them in (b).

WHAT THE TWO PANELS TOGETHER SAY, at L = 64, beta = 416.524, 256 configurations,
against cold-start UNSEEDED classical arms:

  * The fall of z with loop size is NOT special to the seed. The completely
    frozen classical chain falls 2.9x across this axis and contains no model at
    all. The seed falls 55x. The EXCESS over that baseline is the signal.

  * The reason is not that the model learns the infrared better. Its absolute
    relative bias is FLAT in scale -- 62 / 67 / 69 parts per million at W(1x1) /
    W(2x2) / W(4x4) -- while the theory's own per-configuration fluctuation grows
    374x across the same range. The bar rises and the model's error does not, so
    the model becomes progressively more adequate at larger distances for free.
    At the plaquette it is actually WORSE than a cold start (62 vs 42 ppm).

  * N* = (sigma/bias)^2 is the practitioner's form: how many configurations may
    be used before the model's systematic exceeds the user's own statistical
    error. PRE-rethermalization the seed gives N* = 1221 at W(4x4) and 2501 at
    W(8x8), against 6 and 11 for a frozen classical chain -- a ~200x advantage
    in usable statistics, and an N-independent statement about the method.

    BUT ONLY THE FIRST TWO COLUMNS OF THAT ROW ARE MEASUREMENTS (2026-08-22).
    N* SQUARES the bias, so wherever the bias is consistent with zero the N* is
    unbounded and carries no information. At 256 configurations the seed's raw
    |z| is 18.6 / 3.2 / 0.6 / 0.8 at W(1x1) / W(2x2) / W(4x4) / W(8x8) -- so
    W(4x4) and W(8x8) are already statistically indistinguishable from exact
    BEFORE anything is done to them, and 1221 and 2501 are lower bounds at best.
    The ~200x advantage is quoted from W(1x1) and W(2x2), where both arms are
    resolved. Panel (b) now draws unresolved points as HOLLOW markers and
    suppresses their N* label rather than printing a number for them.

  * NO ACTIONABLE DEFECT AT W(8x8) -- a claim that stood here until 2026-08-22
    is RETRACTED. It read: ten sweeps make W(8x8) four times worse (378 -> 1581
    ppm), so post-retherm N* = 137 against a delivered 256 configurations, and
    `n_retherm` should be tuned against that. Neither number was ever resolved.
    sigma at W(8x8) is 19500 ppm, so 256 configurations give a standard error of
    1219 ppm and the two disputed values are z = 0.31 and z = 1.30; measured on
    the SAME configurations in one pass the sign flips with sweep count (-949,
    -2498, +424, +1.6, +723, -1614 ppm at 0/2/5/10/20/40 sweeps). See
    `out/u2_2d/retherm_reconcile/RECONCILIATION.md`. What survives is the part
    that IS resolved: ten sweeps take W(1x1) from 62 to 1.3 ppm (z 18.6 ->
    -0.16) and W(2x2) from 67 to 1.9 (z 3.2 -> 0.67). Rethermalization repairs
    the ultraviolet, and what it does further out is not measurable here.
    The claim that this was also the mechanism behind u1's Fig. 38 goes with it;
    u1's own `59_pre_post_retherm.py` is a separate measurement, and there the
    repair factor merely reaches 1.0 at the largest loop rather than going below
    it -- on a raw z of 1.17, which is itself unresolved.

  * TOPOLOGY IS THE ONE PLACE THE STRONG CLAIM HOLDS UNCONDITIONALLY. Q is
    transported exactly rather than modelled, so the seed carries <Q^2> at
    z = 0.52 while the frozen arm sits at z = infinity (every Q identically
    zero, no spread at all). That is a genuine "the classical chain cannot get
    here" and it rests on no error bar.

    python u2_2d/scripts/31_division_of_labour.py
"""
from __future__ import annotations

import argparse
import glob
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

INK, MUTED, GRID = "#1a1a1a", "#5c5c5c", "#d8d8d8"

# Ordered by DISTANCE SCALE, ultraviolet on the left. The topological charge is
# the far right of the same axis: it is the most global observable there is.
SCALES = [("wilson_1x1", "W(1x1)\nplaquette"), ("wilson_2x2", "W(2x2)"),
          ("wilson_4x4", "W(4x4)"), ("wilson_8x8", "W(8x8)")]

ARM_STYLE = {
    "hmc_frozen": ("plain HMC (frozen)", "#D55E00", (0, (5, 2)), "s", 1.5),
    "hmc_winding": (r"+ winding $\Delta Q=2$", "#E69F00", (0, (1, 1.5)), "v", 1.5),
    "hmc_winding_odd": (r"+ winding $\Delta Q=1$", "#009E73", (0, (4, 1, 1, 1)),
                        "D", 1.5),
    "pre": ("diffusion seed, PRE-retherm", "#CC79A7", "-", "o", 2.4),
    "post": ("diffusion seed, POST-retherm", "#0072B2", "-", "o", 2.6),
}
ORDER = ["hmc_frozen", "hmc_winding", "hmc_winding_odd", "pre", "post"]


def panel_fixed_time(ax, report):
    """|z| by scale -- the presentation of record, unchanged."""
    arms = report["arms"]
    x = np.arange(len(SCALES) + 1)
    for name in ORDER:
        arm = arms.get(name)
        if not arm:
            continue
        label, colour, ls, marker, lw = ARM_STYLE[name]
        z = [abs(arm["z"].get(k, float("nan"))) for k, _ in SCALES]
        zq = arm.get("z_q_squared")
        z.append(abs(zq) if zq is not None and math.isfinite(zq) else float("nan"))
        ax.plot(x, z, ls=ls, color=colour, lw=lw, marker=marker, ms=6,
                markeredgecolor="white", markeredgewidth=0.6, label=label,
                zorder=4 if name in ("pre", "post") else 3)
        # A frozen arm has ZERO spread in Q, so its z is infinite rather than
        # large. Draw it at the top with an arrow instead of dropping the point,
        # which would read as agreement.
        if zq is not None and not math.isfinite(zq):
            ax.annotate("", xy=(x[-1], 60), xytext=(x[-1], 26),
                        arrowprops=dict(arrowstyle="-|>", color=colour, lw=1.2))
            ax.plot([x[-1]], [26], marker=marker, ms=7, color=colour,
                    markerfacecolor="none", markeredgewidth=1.4)
            ax.annotate(r"$z=\infty$" + chr(10) + "(every $Q=0$," + chr(10)
                        + "no spread)",
                        xy=(x[-1] - 0.06, 30), fontsize=6.8, color=colour,
                        ha="right", va="bottom")

    ax.axhspan(0, 2, color="#2e7d32", alpha=0.10, lw=0, zorder=0)
    ax.text(x[0] - 0.35, 1.35, r"agreement ($|z| \leq 2$)", fontsize=7.5,
            color="#2e7d32", va="center")
    ax.set_yscale("symlog", linthresh=1.0, linscale=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels([lab for _, lab in SCALES] + [r"$\langle Q^2\rangle$"],
                       fontsize=8)
    ax.set_ylabel(r"$|z|$ against the closed form", fontsize=9.5, color=INK)
    ax.set_title("(a) significance against exact, at fixed time",
                 fontsize=10.5, loc="left", color=INK)
    ax.annotate("ultraviolet", xy=(0.02, 0.02), xycoords="axes fraction",
                fontsize=7.5, color=MUTED, ha="left", style="italic")
    ax.annotate("global / topological", xy=(0.98, 0.02), xycoords="axes fraction",
                fontsize=7.5, color=MUTED, ha="right", style="italic")
    ax.legend(frameon=False, fontsize=7.5, loc="upper center",
              bbox_to_anchor=(0.5, -0.10), ncol=2, handletextpad=0.5,
              columnspacing=1.4)


def panel_significance(ax, report):
    """bias / sigma of ONE configuration: panel (a) with the sample size out.

    RESOLUTION IS DRAWN, NOT ASSUMED. `N* = (sigma/bias)^2` squares the bias, so
    on a scale where the bias is consistent with zero the N* is unbounded and
    means nothing -- it is a squared noise fluctuation, and reading one as a
    measurement is what produced the retracted W(8x8) finding in the docstring.
    A point whose own |z| is below 2 is therefore drawn HOLLOW and its N* label
    suppressed, so the figure cannot be read as four measurements when it carries
    two.
    """
    arms = report["arms"]
    n = float(report.get("n_configs") or 1)
    x = np.arange(len(SCALES))
    unresolved_from = None
    for name in ORDER:
        arm = arms.get(name)
        if not arm or "relative_deviation" not in arm:
            continue
        label, colour, ls, marker, lw = ARM_STYLE[name]
        ratio = [abs(arm["relative_deviation"][k])
                 / max(arm["relative_sem"][k] * math.sqrt(n), 1e-18)
                 for k, _ in SCALES]
        resolved = [abs(arm["z"].get(k, 0.0)) >= 2.0 for k, _ in SCALES]
        ax.plot(x, ratio, ls=ls, color=colour, lw=lw, zorder=4
                if name in ("pre", "post") else 3, label=label)
        for i, (v, ok) in enumerate(zip(ratio, resolved)):
            ax.plot([x[i]], [v], marker=marker, ms=6, color=colour,
                    markerfacecolor=colour if ok else "white",
                    markeredgecolor=colour if not ok else "white",
                    markeredgewidth=1.3 if not ok else 0.6,
                    zorder=5 if name in ("pre", "post") else 3)
        if name == "pre":
            below = [i for i, ok in enumerate(resolved) if not ok]
            unresolved_from = min(below) if below else None
        if name in ("pre", "post"):
            for i, (v, ok) in enumerate(zip(ratio, resolved)):
                if not ok:
                    continue
                ax.annotate("$N^*$=%.0f" % (1.0 / v ** 2), (i, v), fontsize=6.8,
                            color=colour, ha="center", va="bottom",
                            textcoords="offset points", xytext=(0, 7))

    # Shade the region where the RAW lift's own deviation is already unresolved:
    # nothing measured to the right of this line constrains the model.
    if unresolved_from is not None:
        ax.axvspan(unresolved_from - 0.5, len(SCALES) - 0.5, color="#5c5c5c",
                   alpha=0.08, lw=0, zorder=0)
        ax.annotate("raw lift already consistent with exact here" + chr(10)
                    + r"($|z| < 2$): $N^*$ unbounded, not measured",
                    xy=((unresolved_from + len(SCALES) - 1) / 2.0, 0.93),
                    xycoords=("data", "axes fraction"), fontsize=6.8,
                    color=MUTED, ha="center", va="top", style="italic")

    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels([lab for _, lab in SCALES], fontsize=8)
    ax.set_ylabel(r"bias / $\sigma$ of one configuration", fontsize=9.5,
                  color=INK)
    ax.set_title("(b) the same content, sample size divided out",
                 fontsize=10.5, loc="left", color=INK)
    lo, hi = ax.get_ylim()
    ax.set_ylim(lo, hi * 2.2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", default=None,
                        help="honest_distributions_*.json (default: newest)")
    parser.add_argument("--out",
                        default="out/u2_2d/figures/fig22_division_of_labour.png")
    args = parser.parse_args()

    path = args.report
    if path is None:
        found = sorted(glob.glob("out/u2_2d/figures/honest_distributions_*.json"))
        if not found:
            print("no honest_distributions_*.json; run 29_honest_distributions.py")
            return 1
        path = found[-1]
    report = json.loads(Path(path).read_text(encoding="utf-8"))

    fig, axes = plt.subplots(1, 2, figsize=(12.6, 5.2))
    panel_fixed_time(axes[0], report)
    panel_significance(axes[1], report)
    for ax in axes:
        ax.grid(alpha=0.25, which="major", color=GRID)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(MUTED)
        ax.tick_params(colors=MUTED, labelsize=8.5)

    fig.suptitle("Which scales the model has right, and what the "
                 "rethermalization tail costs",
                 fontsize=12.5, color=INK, x=0.02, ha="left")
    fig.text(0.5, -0.02,
             f"L = {report.get('lattice_size')}, beta = {report.get('beta')}, "
             f"{report.get('n_configs', '?')} configurations per arm, cold-start "
             "and UNSEEDED classical arms.  (a) is the statistic of record; "
             "(b) divides out N and is reported as discussion, not as a "
             "revision." + chr(10)
             + "In (b) the classical arm falls 2.9x across this axis with no "
               "model in it and the seed falls 55x -- the EXCESS is the signal. "
               "$N^*$ = configurations usable before the model's bias exceeds "
               "the user's statistical error." + chr(10)
             + "HOLLOW markers and the shaded band mark scales where that arm's "
               "own deviation is below $|z| = 2$: the bias is consistent with "
               "zero there, so $N^*$ is unbounded and no number is printed.",
             fontsize=6.8, color=MUTED, ha="center", linespacing=1.6)

    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(0, 0.02, 1, 0.95))
    fig.savefig(dest, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {dest}")

    n = float(report.get("n_configs") or 1)
    keys = [k for k, _ in SCALES]
    hdr = "".join(("W" + k.split("_")[1]).rjust(11) for k in keys)
    for title, fn in (
            ("|z|  (statistic of record)",
             lambda a, k: abs(a["z"][k])),
            ("relative deviation, ppm",
             lambda a, k: abs(a["relative_deviation"][k]) * 1e6),
            ("bias / sigma_1config  (N-independent)",
             lambda a, k: abs(a["relative_deviation"][k])
             / (a["relative_sem"][k] * math.sqrt(n))),
            ("N* = configs before bias > stat error  (-- where |z| < 2: the "
             "bias is consistent with zero and N* is unbounded)",
             lambda a, k: (a["relative_sem"][k] * math.sqrt(n)
                           / abs(a["relative_deviation"][k])) ** 2)):
        print(f"\n{title}")
        print(f"  {'arm':22s}{hdr}")
        for name in ORDER:
            arm = report["arms"].get(name)
            if not arm or "relative_deviation" not in arm:
                continue
            cells = []
            for k in keys:
                if title.startswith("N*") and abs(arm["z"].get(k, 0.0)) < 2.0:
                    cells.append("%11s" % "--")
                else:
                    cells.append("%11.4g" % fn(arm, k))
            print(f"  {name:22s}" + "".join(cells))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
