"""Figures 37-39 -- how close the seed is, and how far it still is.

The prolongator framing needs both numbers, and they disagree by four orders of
magnitude. That disagreement is the paper's §5, and these three panels carry it:

  37_z_distribution   every (case, observable) z-score against the EXACT value,
                      matched cases against the deliberately-mismatched control,
                      with the unit normal overlaid. This replaces a pass count,
                      which is the reporting item the protocol insists on.
  38_z_vs_loop_area   where the agreement frays: std(z) and max|z| grow with
                      Wilson-loop extent. The residual lives in long-wavelength
                      modes, which is exactly what local rethermalization
                      relaxes slowest -- a measured statement about what the
                      HMC tail still has to do.
  39_kl_per_site      the density gap in nats per site, from the free-energy
                      identity E_q[log w] - dF = -KL(q||p). ~1 nat/site while
                      the plaquette agrees to 2 parts in 10^4.

The z-records are the tau_int-aware re-scoring (script 48), not the original
campaign summary: the original error bars were fixed 20-bin estimates rather
than per-chain tau_int estimates, so its z-scores were built on the wrong
denominators (NARRATIVE 25.7).

    python u1_2d/scripts/54_seed_accuracy_figures.py
"""

import json
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _figstyle import ARM, INK, MUTED, dress, panel_tag, title  # noqa: E402

OUT = REPO / "out" / "u1_2d"
FIG = OUT / "paper_appendix" / "figures"

# |1 - matched_target/target| below this is a matched rung; above it the case is
# a deliberate mismatch, run as a control that is SUPPOSED to fail.
MATCH_TOL = 1e-3


def load_cases():
    g = json.loads((OUT / "generalization_tau_aware" / "summary.json").read_text())
    matched, mismatched = {}, {}
    for k, v in g.items():
        (matched if abs(v.get("mismatch_ratio", 1.0) - 1.0) < MATCH_TOL
         else mismatched)[k] = v
    return matched, mismatched


def z_values(cases, predicate=None):
    out = []
    for v in cases.values():
        for r in v.get("rows", []):
            if predicate is not None and not predicate(r["observable"]):
                continue
            z = r.get("z_exact")
            if isinstance(z, (int, float)) and np.isfinite(z):
                out.append(float(z))
    return np.array(out)


def fig_z_distribution() -> None:
    matched, mismatched = load_cases()
    zm, zx = z_values(matched), z_values(mismatched)

    fig, ax = plt.subplots(figsize=(6.9, 4.25))
    bins = np.linspace(-6, 6, 49)
    ax.hist(np.clip(zm, -6, 6), bins=bins, density=True, color=ARM["seed"][0],
            alpha=0.82, zorder=3, label=f"matched rungs  ({len(matched)} cases, "
                                        f"{len(zm)} observables)")
    ax.hist(np.clip(zx, -6, 6), bins=bins, density=True, histtype="step",
            color=ARM["cold"][0], lw=1.8, zorder=4,
            label=f"deliberate mismatch  ({len(mismatched)} cases, {len(zx)})")

    grid = np.linspace(-6, 6, 400)
    ax.plot(grid, np.exp(-grid ** 2 / 2) / np.sqrt(2 * np.pi), color=INK, lw=1.6,
            ls=(0, (4, 3)), zorder=5, label="unit normal")

    ax.set_xlabel(r"$z$ against the exact character-expansion value",
                  fontsize=10, color=INK)
    ax.set_ylabel("density", fontsize=10, color=INK)
    title(ax, "The seed graded on observables, as a distribution rather than a pass count")
    dress(ax)
    ax.set_xlim(-6, 6)
    ax.legend(fontsize=8.5, frameon=False, labelcolor=INK, loc="upper left")

    stats = (rf"matched: mean$|z|$ = {np.abs(zm).mean():.3f},  "
             rf"$|z|>3$: {(np.abs(zm) > 3).sum()}/{len(zm)}" "\n"
             rf"mismatch: mean$|z|$ = {np.abs(zx).mean():.3f},  "
             rf"$|z|>3$: {(np.abs(zx) > 3).sum()}/{len(zx)}" "\n"
             r"ideal mean$|z|$ = 0.798")
    ax.text(0.985, 0.97, stats, transform=ax.transAxes, fontsize=8.5, color=INK,
            ha="right", va="top", linespacing=1.5)

    fig.text(0.5, 0.012,
             r"Every (case, observable) pair over $\beta_f = 1.49$-$872.8$ and $L$ up to 128, "
             r"on the $\tau_{\mathrm{int}}$-aware re-scoring. Outliers are clipped to $\pm 6$ "
             "for drawing.\nThe mismatch arm is a control run at a knowingly wrong coupling; "
             "it carries every $|z| > 3$ in the study.",
             fontsize=7, color=MUTED, ha="center")
    fig.tight_layout(rect=(0, 0.085, 1, 1))
    fig.savefig(FIG / "37_z_distribution.png", dpi=226)
    plt.close(fig)
    print(f"wrote 37_z_distribution.png  matched mean|z|={np.abs(zm).mean():.3f} "
          f"mismatch mean|z|={np.abs(zx).mean():.3f}")


def fig_z_vs_loop_area() -> None:
    matched, _ = load_cases()
    per_obs: dict[str, list[float]] = {}
    for v in matched.values():
        for r in v.get("rows", []):
            m = re.fullmatch(r"wilson_(\d+)x(\d+)", r["observable"])
            if not m:
                continue
            z = r.get("z_exact")
            if isinstance(z, (int, float)) and np.isfinite(z):
                per_obs.setdefault(r["observable"], []).append(float(z))

    def area(name):
        a, b = re.fullmatch(r"wilson_(\d+)x(\d+)", name).groups()
        return int(a) * int(b)

    names = sorted(per_obs, key=area)
    areas = [area(n) for n in names]
    std = [float(np.std(per_obs[n])) for n in names]
    mx = [float(np.max(np.abs(per_obs[n]))) for n in names]
    n_obs = [len(per_obs[n]) for n in names]

    fig, ax = plt.subplots(figsize=(6.9, 4.25))
    ax.plot(areas, std, color=ARM["seed"][0], marker="o", ms=7, lw=2.0,
            markeredgecolor="white", markeredgewidth=0.7, zorder=4,
            label=r"std($z$) across matched cases")
    ax.plot(areas, mx, color=ARM["cold"][0], marker="s", ms=6, lw=1.6,
            markeredgecolor="white", markeredgewidth=0.7, zorder=4,
            label=r"max $|z|$")
    ax.axhline(1.0, color=INK, lw=1.2, ls=(0, (4, 3)), zorder=3)
    ax.text(1.05, 1.06, r"std($z$) = 1: errors correctly sized", fontsize=8, color=INK)

    for n, a, s in zip(names, areas, std):
        if n in ("wilson_1x1", "wilson_4x4", "wilson_12x12"):
            ax.annotate(n.replace("wilson_", "W(").replace("x", r"$\times$") + ")",
                        (a, s), textcoords="offset points", xytext=(0, -19),
                        ha="center", fontsize=8, color=ARM["seed"][0])

    ax.set_xscale("log")
    ax.set_xlabel(r"Wilson loop area  $R \times T$  (lattice units)", fontsize=10, color=INK)
    ax.set_ylabel(r"$z$ against exact", fontsize=10, color=INK)
    title(ax, "Where the agreement frays: the residual lives in long-wavelength modes")
    dress(ax)
    ax.set_ylim(0, max(mx) * 1.15)
    ax.legend(fontsize=9, frameon=False, labelcolor=INK, loc="upper left")
    fig.text(0.5, 0.012,
             f"{min(n_obs)}-{max(n_obs)} matched cases per loop size. Small loops are "
             "reproduced to within the error bars; extended loops are not.\n"
             "Local rethermalization relaxes exactly these modes slowest, so this is a "
             "measurement of what the HMC tail is left to do.",
             fontsize=7, color=MUTED, ha="center")
    fig.tight_layout(rect=(0, 0.085, 1, 1))
    fig.savefig(FIG / "38_z_vs_loop_area.png", dpi=226)
    plt.close(fig)
    print("wrote 38_z_vs_loop_area.png  std(z) " +
          " -> ".join(f"{s:.2f}" for s in (std[0], std[len(std) // 2], std[-1])))


def fig_kl_per_site() -> None:
    """Deployed-checkpoint KL, plus the instrument's validation on a solvable case."""
    rows = json.loads((OUT / "ode_reweighting" / "reweighting_results.json").read_text())
    rows = sorted(rows, key=lambda r: (r["fine_L"], r["fine_beta"]))
    cert = json.loads((OUT / "exactness2" / "cert_easy"
                       / "reweighting_results.json").read_text())[0]

    labels, kl, sem, vol = [], [], [], []
    for r in rows:
        fe = r["free_energy_certificate"]
        V = 2 * r["fine_L"] ** 2
        labels.append(rf"$L={r['fine_L']}$" + "\n" + rf"$\beta={r['fine_beta']:g}$")
        kl.append(fe["kl_per_site"])
        sem.append(fe["kl_sem"] / V)
        vol.append(V)

    x = np.arange(len(rows))
    fig, ax = plt.subplots(figsize=(6.9, 4.23))
    ax.bar(x, kl, width=0.56, color=ARM["seed"][0], zorder=3, alpha=0.9)
    ax.errorbar(x, kl, yerr=sem, fmt="none", ecolor=INK, elinewidth=1.1,
                capsize=4, zorder=5)

    for xi, k, V in zip(x, kl, vol):
        ax.annotate(f"{k:.2f}", (xi, k), textcoords="offset points", xytext=(0, 7),
                    ha="center", fontsize=9.5, color=INK, fontweight="bold")
        ax.annotate(f"{k * V:.0f} nats\nper config", (xi, 0.06), ha="center",
                    va="bottom", fontsize=7.5, color="white")

    fe = cert["free_energy_certificate"]
    ax.axhline(fe["kl_per_site"], color=ARM["hmc+inst"][0], lw=1.4, ls=(0, (4, 3)),
               zorder=4)
    ax.text(len(rows) - 0.45, fe["kl_per_site"] + 0.03,
            rf"instrument validated on a solvable case: $L=8$, $\beta=2$, "
            rf"{fe['kl_per_site']:.2f} nats/site",
            fontsize=7.5, color=ARM["hmc+inst"][0], ha="right")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9, color=INK)
    ax.set_xlim(-0.6, len(rows) - 0.4)
    ax.set_ylim(0, max(kl) * 1.32)
    ax.set_ylabel("KL(model $\\|$ Boltzmann), nats per site", fontsize=10, color=INK)
    title(ax, "The seed is not the Boltzmann distribution, and that is the tail's job")
    dress(ax)
    fig.text(0.5, 0.012,
             r"From the free-energy identity $E_q[\log w] - \Delta F = -\mathrm{KL}(q\|p)$ "
             "with the exact character-expansion free energy, on the deployed checkpoint.\n"
             "The same ensembles reproduce the plaquette to ~2 parts in "
             r"$10^4$ (figures 37, 28). Error bars are the certificate SEM divided by $V$.",
             fontsize=7, color=MUTED, ha="center")
    fig.tight_layout(rect=(0, 0.085, 1, 1))
    fig.savefig(FIG / "39_kl_per_site.png", dpi=232)
    plt.close(fig)
    print("wrote 39_kl_per_site.png  kl/site=" + ", ".join(f"{k:.2f}" for k in kl))


def main() -> int:
    FIG.mkdir(parents=True, exist_ok=True)
    fig_z_distribution()
    fig_z_vs_loop_area()
    fig_kl_per_site()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
