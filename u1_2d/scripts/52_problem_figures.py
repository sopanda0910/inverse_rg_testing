"""Figures 31-32 -- the failure mode the prolongator exists to address.

Two walls, and the paper needs both drawn before it claims to climb either:

  31_frozen_traces  Q(t) for periodic HMC at three couplings. Zero sector
                    changes in 3000 trajectories at all three, against the
                    winding update on the same chain settings, which moves
                    thousands of times for a 1-18% overhead. This is what
                    "topological freezing" means as a picture, and it is also
                    the reason a sector-change count is the wrong health check:
                    the frozen arm reports a SMALL tau_int, not a large one.

  32_burnin_wall    the plaquette relaxing from a cold start, a hot start and a
                    diffusion seed at the same three couplings. The binding
                    constraint in the headline regime is UV thermalization, not
                    topology: at beta = 218.58 the hot start never arrives and
                    the cold start needs hundreds of trajectories, while the
                    seed starts inside the band.

The Q traces come from `43_ptbc_benchmark.py --save-series`; the relaxation
series are the cached ones from `05_hmc_thermalization.py`.

    python u1_2d/scripts/52_problem_figures.py
"""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO))

from _figstyle import ARM, INK, MUTED, dress, panel_tag, title  # noqa: E402

from u1_2d.lgt import exact  # noqa: E402

OUT = REPO / "out" / "u1_2d"
FIG = OUT / "paper_appendix" / "figures"

BETAS = [14.1464, 55.0237, 218.58]
THERM = {
    14.1464: "L32_beta14.1464/A_bc4_L32_beta14.1464",
    55.0237: "L32_beta55.0237/D_bc14.1464_L32_beta55.0237",
    218.58: "L32_beta218.58/D_bc55.0237_L32_beta218.58",
}
STARTS = [("cold start", ARM["cold"]), ("hot start", ARM["hot"]),
          ("diffusion seed", ARM["seed"])]


def fig_frozen_traces() -> None:
    src = OUT / "classical_arms"
    rows = json.loads((src / "ptbc_benchmark.json").read_text())
    changes = {(r["arm"], round(r["beta"], 4)): r["n_sector_changes"] for r in rows}

    window = 600          # 3000 trajectories overplot into a solid block
    fig, axes = plt.subplots(1, 3, figsize=(6.9, 2.5), sharey=False)
    for ax, beta in zip(axes, BETAS):
        for arm, key, lw, alpha in (("hmc+inst", "hmc_inst", 0.7, 0.85),
                                    ("hmc", "hmc", 1.8, 1.0)):
            f = src / f"q_series_{key}_L32_beta{beta:g}.npz"
            q = np.load(f)["q"][:window, 0]
            ax.plot(q, color=ARM[arm][0], lw=lw, alpha=alpha,
                    zorder=(3 if arm == "hmc+inst" else 6), label=ARM[arm][2])
        q2_exact = (exact.topological_susceptibility_exact(beta, "wilson", 32) * 32 * 32)
        n_frozen = changes.get(("hmc", round(beta, 4)))
        n_inst = changes.get(("hmc+inst", round(beta, 4)))
        ax.set_title(rf"$\beta_f = {beta:g}$" + "\n" +
                     f"sector changes: {n_frozen}  vs  {n_inst:,}\n" +
                     rf"exact $\langle Q^2\rangle = {q2_exact:.3f}$",
                     fontsize=8.5, color=MUTED, pad=8, loc="center")
        ax.set_xlabel("trajectory", fontsize=9.5, color=INK)
        ax.set_xlim(0, window)
        dress(ax)
    axes[0].set_ylabel(r"topological charge $Q$", fontsize=10, color=INK)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, fontsize=9, frameon=False, labelcolor=INK,
               loc="upper right", ncol=2, bbox_to_anchor=(0.995, 1.0),
               handletextpad=0.5, columnspacing=1.8)
    fig.suptitle("Periodic HMC does not change topological sector, at any coupling tested",
                 fontsize=12, color=INK, x=0.008, ha="left", y=0.995)
    fig.text(0.5, 0.012,
             rf"$L = 32$, one representative chain of four per arm; the first {window} of 3000 "
             "trajectories are drawn, because at this density the full run overplots into a "
             "solid block.\nThe frozen arm's flat line is why a sector-change count, not "
             r"$\tau_{\mathrm{int}}$, is the diagnostic: a constant series has no "
             r"autocorrelation to integrate, so freezing reports a *small* "
             r"$\tau_{\mathrm{int}}$.",
             fontsize=7, color=MUTED, ha="center")
    fig.tight_layout(rect=(0, 0.085, 1, 0.90))
    fig.savefig(FIG / "31_frozen_traces.png", dpi=336)
    plt.close(fig)
    print("wrote 31_frozen_traces.png  " +
          ", ".join(f"beta={b:g}: {changes[('hmc', round(b, 4))]}" for b in BETAS))


def fig_burnin_wall() -> None:
    fig, axes = plt.subplots(1, 3, figsize=(6.9, 2.57))

    for ax, beta in zip(axes, BETAS):
        stem = THERM[beta]
        series = np.load(OUT / "thermalization" / f"{stem}_series.npz")
        summary = json.loads((OUT / "thermalization" / f"{stem}_summary.json").read_text())
        target = exact.plaquette_exact(beta, "wilson", 32)

        for name, (color, marker, _) in STARTS:
            key = f"{name}|plaquette"
            if key not in series:
                continue
            s = series[key]
            mean = s.mean(axis=1)
            sem = s.std(axis=1) / np.sqrt(s.shape[1])
            t = np.arange(len(mean))
            ax.plot(t, mean, color=color, lw=1.6, zorder=4, label=name)
            ax.fill_between(t, mean - sem, mean + sem, color=color, alpha=0.22,
                            linewidth=0, zorder=3)

        ax.axhline(target, color=INK, lw=1.2, ls=(0, (4, 3)), zorder=5)
        tt = summary["t_therm"]
        note = [r"$t_{\mathrm{therm}}$ (plaquette)"]
        for name, (color, _, _) in STARTS:
            v = tt.get(name, {}).get("plaquette")
            budget = (summary["n_traj_gen"] if name == "diffusion seed"
                      else summary["n_traj_baseline"])
            note.append(f"  {name}: " + ("%d" % v if np.isfinite(v) else f"> {budget}"))
        ax.text(0.975, 0.05, "\n".join(note), transform=ax.transAxes, fontsize=7.5,
                color=MUTED, ha="right", va="bottom", linespacing=1.45)

        ax.set_xscale("symlog", linthresh=1.0, linscale=0.5)
        ax.set_xlim(0, max(len(series[f"{n}|plaquette"]) for n, _ in STARTS
                           if f"{n}|plaquette" in series))
        ax.set_title(rf"$\beta_f = {beta:g}$", fontsize=10, color=INK, pad=8)
        ax.set_xlabel("trajectory", fontsize=9.5, color=INK)
        lo = min(target * 0.985, target - 0.02)
        ax.set_ylim(lo, target + (target - lo) * 0.45)
        dress(ax)

    axes[0].set_ylabel("mean plaquette", fontsize=10, color=INK)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, fontsize=9, frameon=False, labelcolor=INK,
               loc="upper right", ncol=3, bbox_to_anchor=(0.995, 1.0),
               handletextpad=0.5, columnspacing=1.8)
    for ax, beta in zip(axes, BETAS):
        target = exact.plaquette_exact(beta, "wilson", 32)
        ax.annotate("exact", xy=(0.99, target), xycoords=("axes fraction", "data"),
                    textcoords="offset points", xytext=(0, 4), fontsize=7.5,
                    color=INK, ha="right", va="bottom")

    fig.suptitle("The burn-in wall: what a starting configuration has to climb",
                 fontsize=12, color=INK, x=0.008, ha="left", y=0.995)
    fig.text(0.5, 0.012,
             r"$L = 32$. Bands are the across-chain SEM (128 chains for the seed, 32 for the "
             "baselines). Hot starts run far below the frame at every coupling; the axis is "
             "cropped to the\nseed's scale deliberately, because that is the scale at which "
             r"$t_{\mathrm{therm}}$ is decided. A non-converging entry is reported against its "
             "own budget, never as \"never\".",
             fontsize=7, color=MUTED, ha="center")
    fig.tight_layout(rect=(0, 0.075, 1, 0.90))
    fig.savefig(FIG / "32_burnin_wall.png", dpi=342)
    plt.close(fig)
    print("wrote 32_burnin_wall.png")


def main() -> int:
    FIG.mkdir(parents=True, exist_ok=True)
    fig_frozen_traces()
    fig_burnin_wall()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
