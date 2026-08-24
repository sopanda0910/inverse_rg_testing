"""Export a copy-paste-ready Overleaf bundle: paper/main.tex + paper/figures/.

WHY THIS EXISTS. The two studies keep their figures in
`out/{u1_2d,u2_2d}/paper_appendix/figures/`, each gated by its own assembler
(`u1_2d/scripts/30_...`, `u2_2d/scripts/49_...`). A paper needs them in one
tree, under names LaTeX can actually include, arranged in the order
`docs/u1_2d/PAPER_OUTLINE.md` prescribes. Doing that by hand is how a figure
list drifts from the figures on disk, which is the failure both assemblers
exist to prevent -- so it is generated here instead.

    python u1_2d/scripts/64_export_paper_bundle.py [--out paper]

Produces

    paper/main.tex
    paper/figures/u1_2d/*.png
    paper/figures/u2_2d/*.png

which is exactly the layout to upload to Overleaf.

THREE THINGS IT HANDLES THAT A MANUAL COPY WOULD GET WRONG.

  * **Dots in filenames.** `fig1_det_density_L32_beta105.651.png` breaks
    graphicx's extension detection. Names are rewritten on copy
    (`beta105p651`), so no `\\includegraphics` brace-grouping trick is needed
    and the bundle stays readable.
  * **Every tracked figure is placed exactly once.** The section plan below is
    checked against both assemblers' figure tables: a figure in no section, in
    two sections, or named but not tracked is an error, not a silent omission.
  * **The pipeline schematic is u2's, deliberately.** `41_pipeline_schematic.py`
    draws one schematic for BOTH studies (the SU(2) box is dashed and labelled
    `u2 only`), so `u2/fig28_pipeline.png` is the paper's figure 1 and u1's own
    `44_pipeline.png` is demoted to the reproducibility appendix. Same for
    `fig30_multi_lift.png`, which shows both studies side by side and therefore
    belongs with the METHOD, not with the transfer section.

THIS IS AN OUTLINE, NOT A DRAFT. Section bodies are one-line notes saying what
belongs there, taken from `PAPER_OUTLINE.md`. The figures, captions, ordering
and cross-references are real; the prose is not written.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import shutil
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

U1_FIGS = ROOT / "out/u1_2d/paper_appendix/figures"
U2_FIGS = ROOT / "out/u2_2d/paper_appendix/figures"


def load_u2_captions() -> dict[str, str]:
    """u2's captions are single-sourced in its assembler; import them by path."""
    path = ROOT / "u2_2d/scripts/49_assemble_appendix_figures.py"
    spec = importlib.util.spec_from_file_location("u2_assembler", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {name: caption for name, (_s, _i, caption) in module.FIGURES.items()}


# u1 captions. Written here rather than parsed out of appendix.md: that file's
# per-figure sections are multi-paragraph discussion, and a first-paragraph
# heuristic would silently produce a wrong caption the day someone reorders a
# sentence. appendix.md remains the long-form record.
U1_CAPTIONS: dict[str, str] = {
    "01_ladder_drift.png":
        "Per-rung observable drift along the deployed ladder, generated "
        "against the exact character expansion.",
    "02_ladder_topology.png":
        "Topological charge along the ladder. Exact finite-volume "
        "$\\langle Q^2\\rangle \\approx V/(4\\pi^2\\beta)$ is a fixed point of "
        "$\\beta_f = 4\\beta_c$, $L_f = 2L_c$, so the coarse ensemble's $P(Q)$ "
        "\\emph{is} the fine theory's.",
    "03_ladder_rung_L64.png":
        "Full observable comparison at the top rung, $L = 64$, "
        "$\\beta = 55.02$.",
    "04_matched_scan.png":
        "Matched-coupling generalization scan: agreement against the exact "
        "reference as the coarse coupling is varied at fixed ladder relation.",
    "05_mismatch_scan.png":
        "Mismatch scan -- the coarse and fine couplings deliberately taken off "
        "the ladder relation.",
    "06_size_scan.png":
        "Size scan: the same lift applied at $L = 32$, $64$ and $128$.",
    "07_raw_topology.png":
        "Topological charge of the RAW lift, before charge enforcement, across "
        "the campaign.",
    "08_case_low.png":
        "Representative campaign case, weak coupling.",
    "09_case_high.png":
        "Representative campaign case, strong coupling -- the regime the "
        "method targets.",
    "10_case_extrapolation.png":
        "Representative case OUTSIDE the training range "
        "($\\beta_c = 218.58$, $3.6\\times$ past $\\beta_{\\max} = 60$). The "
        "raw lift is far off and the rethermalization tail repairs it, so this "
        "case validates the pipeline rather than the model.",
    "11_case_L64.png":
        "Representative case at $L = 64$.",
    "12_timescales.png":
        "Thermalization and decorrelation timescales against coupling, which "
        "set the yardstick every $t_{\\mathrm{therm}}$ in this paper is "
        "measured against.",
    "13_beta_scan.png":
        "Observable agreement across 14 couplings, $\\beta = 6$ to $518$, in "
        "relative deviation AND in $z$, with the training ceiling at "
        "$\\beta = 60$ hatched. u1's coverage is dense to the ceiling rather "
        "than a set of isolated rungs, so the ceiling shows as a step and the "
        "bias SIGN flips across it.",
    "14_relaxation_mid.png":
        "Relaxation from each starting configuration at intermediate coupling.",
    "15_relaxation_high.png":
        "Relaxation from a diffusion seed at strong coupling, against cold and "
        "hot starts. The seed begins at equilibrium; the classical starts do "
        "not arrive within the budget.",
    "16_autocorrelation_modes.png":
        "Autocorrelation by observable and by starting condition.",
    "17_headtohead_cost.png":
        "Head-to-head cost against the classical baseline of record, HMC + "
        "winding update.",
    "18_entry_cost.png":
        "Entry cost: what has to be paid before the first usable "
        "configuration.",
    "19_ess_weights.png":
        "Importance weights from the probability-flow ODE. Retained as the "
        "record that ESS was measured, not as a headline: ESS diagnoses "
        "importance sampling, which this paper does not do.",
    "20_mismatch_exact_sectors.png":
        "The mismatch scan repeated with exactly-seeded sectors, isolating "
        "sector weights from local structure.",
    "21_pq_tail_mismatch.png":
        "$P(Q)$ before and after the HMC tail under coupling mismatch -- "
        "sector-tail recovery.",
    "22_pq_tail_L64.png":
        "The same at $L = 64$.",
    "23_ess_progress.png":
        "ESS across the fine-tuning program.",
    "24_proposal_sweep.png":
        "Proposal sweep in the ESS program.",
    "25_finetune_dynamics.png":
        "Fine-tuning dynamics. The question it answers is whether the density "
        "gap can be trained away; it cannot.",
    "26_three_way.png":
        "Three-way comparison across the exactness program.",
    "27_program_optimum.png":
        "The program optimum over the exactness sweep.",
    "28_dissociation.png":
        "The dissociation: observable-level agreement is sharp (plaquette to "
        "$\\sim 2$ parts in $10^4$) while the density is not (KL of "
        "$450$--$2100$ nats per configuration). Observable agreement does not "
        "certify the measure, which is why $t_{\\mathrm{therm}}$ rather than "
        "an observable table is the metric of record.",
    "29_seed_quality.png":
        "LEAD FIGURE. $t_{\\mathrm{therm}}$ against $\\beta$ over a "
        "$586\\times$ coupling range, five arms. The yardstick is the "
        "decorrelation interval $2\\tau_{\\mathrm{int}}$, not the cold arm: a "
        "ratio against a cold start flatters the seed everywhere and means "
        "nothing.",
    "30_volume_scan.png":
        "Does the advantage survive volume. A two-sided answer, reported as "
        "such.",
    "31_frozen_traces.png":
        "$Q$ traces showing plain periodic HMC frozen -- zero sector changes "
        "in 3000 trajectories at $\\beta = 14.15$, $55.02$ and $218.58$. This "
        "is the failure the method exists to address.",
    "32_burnin_wall.png":
        "The burn-in wall: cost of reaching equilibrium classically as the "
        "coupling stiffens.",
    "33_ladder_fixed_point.png":
        "Exact $\\langle Q^2\\rangle$ as a fixed point of the ladder "
        "($1.20271 \\to 1.20334$ over four rungs, Villain). Sector transport "
        "is an identity, not an approximation, and climbing the ladder is a "
        "continuum-limit trajectory at fixed physical volume.",
    "34_match_rate_volume.png":
        "Raw topological-charge match rate against volume, before enforcement.",
    "35_sector_freeze_sigma.png":
        "Sector freezing against $\\sigma$ -- where in the noise schedule "
        "topology stops being carried.",
    "36_sector_tail.png":
        "Sector-tail recovery: $P(Q)$ before and after the HMC tail.",
    "37_z_distribution.png":
        "$z$ against the exact reference over all observables.",
    "38_z_vs_loop_area.png":
        "$\\mathrm{std}(z)$ against loop area. Residual model error "
        "concentrates in EXTENDED observables, growing $1.09 \\to 1.44$ from "
        "$W(4\\times4)$ to $W(12\\times12)$ -- so large-loop dispersion must be "
        "reported, not just the plaquette. Read with the resolution note: at "
        "256 configurations the raw $z$ at $W(8\\times8)$ is $1.17$ and is not "
        "resolved.",
    "39_kl_per_site.png":
        "KL per site across cases -- the density gap stated per degree of "
        "freedom rather than per configuration.",
    "40_cost_per_config.png":
        "Seconds per independent configuration by arm, against the classical "
        "baseline of record (HMC + winding, $0.198$ s at $\\beta = 218.58$).",
    "41_breakeven.png":
        "Break-even: ensemble size at which the pipeline's fixed cost is "
        "repaid.",
    "42_mala_locality.png":
        "The MALA-locality test: a local corrector is not a substitute for a "
        "real tail.",
    "43_zhu_pq.png":
        "$P(Q)$ in the head-to-head against Zhu et al.",
    "44_pipeline.png":
        "u1-only pipeline schematic. SUPERSEDED for the main text by "
        "Figure~\\ref{fig:u2_2d:fig28_pipeline}, which is drawn for both "
        "studies; retained "
        "as the record of the U(1) pipeline alone.",
    "45_architecture.png":
        "Score-network architecture: the gauge-covariant curl head.",
    "46_observable_scan.png":
        "Observable agreement across 14 couplings in relative deviation and in "
        "$z$. Panel (d) shows ten rethermalization sweeps returning almost "
        "every coupling to $|z| < 2$, including far past the training ceiling.",
}

# (label, section title, note, [(study, filename)]) -- the paper's figure plan.
# Every tracked figure appears exactly once across MAIN and APPENDIX; the
# checker below enforces it.
MAIN: list[tuple[str, str, str, list[tuple[str, str]]]] = [
    ("intro", "Introduction",
     "The claim: topology must be TRANSPORTED across an inverse-RG step, not "
     "produced by the generative map. Classical prolongation plus cheap local "
     "repair already matches the learned lift on local observables and is "
     "cheaper -- and is 0x to 217x wrong on the topological susceptibility, "
     "topologically trivial at large beta. Local thermalization speed is NOT "
     "claimed as a differentiator.",
     [("u2", "fig28_pipeline.png")]),
    ("setup", "Setup: the theory and why it is the right testbed",
     "2D compact U(1) on the lattice; exact solvability via the character "
     "expansion; the failure mode being targeted.",
     [("u1", "31_frozen_traces.png")]),
    ("method", "Method",
     "Blocking and the ladder fixed-point invariant; diffusion on the torus of "
     "angles; the gauge-covariant score network; topology transport; climbing "
     "more than one rung; what repairs the raw lift; the reverse-diffusion "
     "step count.",
     [("u1", "33_ladder_fixed_point.png"), ("u1", "34_match_rate_volume.png"),
      ("u2", "fig30_multi_lift.png")]),
    ("seedquality", "The result: seed quality",
     "The measurement and its TWO yardsticks -- local observables AND topology. "
     "Seven arms. On trajectories-to-equilibrium the classical arms match or "
     "beat the seed and are 10x cheaper; on mean squared topological charge "
     "every one of them fails (Table S6c). Scoring thermalization alone is what "
     "made classical prolongation look sufficient. The tail never has to "
     "tunnel; whether the advantage survives volume.",
     [("u1", "29_seed_quality.png"), ("u1", "15_relaxation_high.png"),
      ("u1", "36_sector_tail.png"), ("u1", "30_volume_scan.png")]),
    ("distance", "How far from equilibrium is the seed?",
     "Observable-level agreement; where the agreement frays and why that is "
     "the interesting part; the density gap, measured; why the dissociation "
     "had to happen; and why the gap will not be trained away.",
     [("u1", "13_beta_scan.png"), ("u1", "38_z_vs_loop_area.png"),
      ("u1", "28_dissociation.png"), ("u1", "39_kl_per_site.png")]),
    ("cost", "Cost accounting",
     "The classical baseline of record is HMC + winding, not PTBC and not "
     "plain HMC; the winding update itself; break-even.",
     [("u1", "40_cost_per_config.png")]),
    ("implications", "What this implies for the class of method",
     "The design directive, now demonstrated rather than owed; a local "
     "corrector is not a substitute for a real tail; a reporting protocol.",
     []),
    ("u2", "Carrying the method to a non-abelian group: 2D U(2)",
     "What carries over unchanged and why; two freezing mechanisms rather than "
     "one; two standard diagnostics that report HEALTHY on a parity-frozen "
     "chain; the seed result; cost stated as a cost claim; what does not "
     "carry.",
     [("u2", "fig07_topological_reach.png"), ("u2", "fig06_seed_quality.png"),
      ("u2", "fig09_parity_mobility.png"), ("u2", "fig13_cost.png"),
      ("u2", "fig26_transport_exactness.png")]),
    ("related", "Related work", "Classical multiscale thermalization as the "
     "direct ancestor; the learned coarse-to-fine line; width is not "
     "correctness; positioning.", []),
    ("conclusions", "Conclusions and outlook", "", []),
]

APPENDIX: list[tuple[str, str, str, list[tuple[str, str]]]] = [
    ("app:exact", "Exact character-expansion references",
     "The closed forms both studies are scored against, and the checks that "
     "the implementations reproduce them.",
     [("u2", "fig4_beta_matching.png"), ("u2", "fig5_ladder.png"),
      ("u2", "fig1_det_density_L32_beta105.651.png"),
      ("u2", "fig1_det_density_L64_beta416.524.png"),
      ("u2", "fig2_sectors_L32_beta105.651.png"),
      ("u2", "fig2_sectors_L64_beta416.524.png"),
      ("u2", "fig3_area_law_L32_beta105.651.png"),
      ("u2", "fig3_area_law_L64_beta416.524.png"),
      ("u2", "fig11_ladder_accuracy.png"), ("u2", "fig12_area_law.png")]),
    ("app:campaign", "Full campaign tables and scans",
     "The 38-case study on $\\tau_{\\mathrm{int}}$-aware records, per-observable "
     "$z$, and the sector-mode comparison.",
     [("u1", "04_matched_scan.png"), ("u1", "05_mismatch_scan.png"),
      ("u1", "06_size_scan.png"), ("u1", "07_raw_topology.png"),
      ("u1", "08_case_low.png"), ("u1", "09_case_high.png"),
      ("u1", "10_case_extrapolation.png"), ("u1", "11_case_L64.png"),
      ("u1", "20_mismatch_exact_sectors.png"),
      ("u1", "21_pq_tail_mismatch.png"), ("u1", "22_pq_tail_L64.png"),
      ("u1", "35_sector_freeze_sigma.png"),
      ("u1", "46_observable_scan.png")]),
    ("app:classical", "Burn-in, classical remedies, and cost",
     "The instanton-HMC burn-in scan, the classical-remedy benchmark "
     "(PTBC tuning, open boundaries, the swap-acceptance bug), and the "
     "positioning experiments.",
     [("u1", "12_timescales.png"), ("u1", "14_relaxation_mid.png"),
      ("u1", "16_autocorrelation_modes.png"), ("u1", "32_burnin_wall.png"),
      ("u1", "17_headtohead_cost.png"), ("u1", "18_entry_cost.png"),
      ("u1", "41_breakeven.png"), ("u1", "42_mala_locality.png"),
      ("u1", "43_zhu_pq.png")]),
    ("app:density", "The density-gap program",
     "ODE likelihood, fiber weights, the six-item falsification chain, the "
     "within-model $R^2_c$ decomposition, and the Villain control together "
     "with why it cannot be read as a subtraction.",
     [("u1", "37_z_distribution.png"), ("u1", "19_ess_weights.png"),
      ("u1", "23_ess_progress.png"), ("u1", "24_proposal_sweep.png"),
      ("u1", "25_finetune_dynamics.png"), ("u1", "26_three_way.png"),
      ("u1", "27_program_optimum.png")]),
    ("app:u2freeze", "U(2): topological freezing and the two winding moves",
     "The failure being targeted in the non-abelian case, and the "
     "U(2)-specific fact that there are two freezing mechanisms with "
     "different controlling parameters -- only one of which the ladder "
     "protects.",
     [("u2", "fig19_freezing.png"), ("u2", "fig10_winding_economics.png"),
      ("u2", "fig20_honest_distributions_L64_beta416.524.png")]),
    ("app:u2cov", "U(2): coverage, volume, and where the seed stops working",
     "Seed quality tracks distance to the nearest training rung, not "
     "$\\beta$. These are the limits, stated rather than papered over.",
     [("u2", "fig21_seed_quality.png"), ("u2", "fig29_observable_scan.png"),
      ("u2", "fig27_volume_scan.png")]),
    ("app:u2dist", "U(2): how far from equilibrium the seed is",
     "Observable-level agreement is sharp while the density is not, "
     "reproducing the U(1) dissociation. Read the resolution notes: large "
     "Wilson loops are frequently not resolved at 64--256 configurations.",
     [("u2", "fig08_wilson_spread.png"),
      ("u2", "fig16_distributions_L32_beta105.651.png"),
      ("u2", "fig16_distributions_L64_beta416.524.png"),
      ("u2", "fig17_z_distribution_L32_beta105.651.png"),
      ("u2", "fig17_z_distribution_L64_beta416.524.png"),
      ("u2", "fig18_z_vs_loop_area_L32_beta105.651.png"),
      ("u2", "fig18_z_vs_loop_area_L64_beta416.524.png"),
      ("u2", "fig22_division_of_labour.png"),
      ("u2", "fig23_dissociation.png"), ("u2", "fig24_kl_per_site.png")]),
    ("app:u2cost", "U(2): cost and tuning",
     "The two knobs that were measured rather than assumed.",
     [("u2", "fig14_sampler_steps.png"), ("u2", "fig25_retherm_scan.png"),
      ("u2", "fig15_prolongator.png")]),
    ("app:repro", "Reproducibility",
     "\\texttt{29\\_verify\\_identities.py} and \\texttt{09\\_verify\\_identities.py}; "
     "the two figure gates \\texttt{30\\_assemble\\_appendix\\_figures.py --check} "
     "and \\texttt{49\\_assemble\\_appendix\\_figures.py --check}; device "
     "conventions; checkpoints.",
     [("u1", "01_ladder_drift.png"), ("u1", "02_ladder_topology.png"),
      ("u1", "03_ladder_rung_L64.png"), ("u1", "45_architecture.png"),
      ("u1", "44_pipeline.png")]),
]

PREAMBLE = r"""% Generated by u1_2d/scripts/64_export_paper_bundle.py -- do not hand-edit
% the figure blocks; regenerate instead, so the figure list cannot drift from
% the figures on disk.
%
% Layout expected by Overleaf:
%   main.tex
%   figures/u1_2d/*.png
%   figures/u2_2d/*.png
% TWO-COLUMN. `article` + `twocolumn` is used rather than revtex4-2 so the file
% compiles with no class beyond a base TeX install; to move to APS styling,
% swap this one line for
%   \documentclass[aps,prd,twocolumn,superscriptaddress]{revtex4-2}
% and delete the geometry line and the \twocolumn[...] title block below
% (revtex spans the title and abstract itself).
\documentclass[twocolumn,10pt]{article}

\usepackage[margin=1in]{geometry}
\usepackage{graphicx}
\usepackage{amsmath, amssymb}
\usepackage{booktabs}
\usepackage[hidelinks]{hyperref}
\usepackage[font=small]{caption}

\graphicspath{{figures/}}

% TITLE REFRAMED 2026-08-24. The previous title -- "Learned Prolongation ... a
% diffusion-model configuration as an HMC starting seed" -- named the claim
% that does NOT survive a properly built classical baseline: `flux`
% prolongation plus 200 local sweeps BEATS the seed on
% trajectories-to-equilibrium (0 against 6 at beta_f = 218.58), sits 0.07 sigma
% from the exact plaquette with correct dispersion, and is 10x cheaper to
% build. What no classical arm can do is topology: all of them are 0x-217x
% wrong on <Q^2> (67_prolongator_topology.py). Lead with transport.
\title{Transported, not Generated: exact topology in a learned\\
       inverse-renormalization-group sampler for lattice gauge theory}
\author{}
\date{}

\begin{document}

% Standard idiom for a full-width title and abstract in a twocolumn article:
% `@twocolumnfalse` makes \maketitle take its one-column branch, so it does not
% nest a \twocolumn inside this one.
\makeatletter
\twocolumn[
  \begin{@twocolumnfalse}
  \maketitle
  \begin{abstract}
  \noindent OUTLINE ONLY --- abstract not written. The claim the paper carries
  is that topological charge must be TRANSPORTED across an
  inverse-renormalization-group step rather than produced by the generative
  map, and that this is what separates the method both from classical
  prolongation and from other generative samplers. Every classical prolongator
  tested reproduces the exact plaquette to $10^{-4}$--$10^{-7}$ while getting
  $\langle Q^2\rangle$ wrong by a factor between $0$ and $217$; the best of them
  on local observables is topologically TRIVIAL at large $\beta$, reintroducing
  the freezing the method exists to remove. Removing transport from our own
  pipeline inflates $\langle Q^2\rangle$ by $17\times$ and violates charge
  conjugation at $5.4\sigma$ --- a test needing no closed form, so it ports to
  theories where none exists. Local thermalization speed is explicitly NOT
  claimed as a differentiator. 2D compact U(1) is the primary study; 2D U(2) is
  the transfer demonstration, and its topology is carried by an abelian
  determinant sector, which is what makes exact transport possible in a
  non-abelian group.
  \end{abstract}
  \vspace{1.5em}
  \end{@twocolumnfalse}
]
\makeatother

\tableofcontents
\clearpage
"""


def latex_safe(name: str) -> str:
    """Rewrite a figure filename so graphicx can find it.

    Dots inside the stem (`...beta105.651.png`) defeat extension detection.
    Rewriting on copy keeps the .tex free of brace-grouping workarounds.
    """
    stem, _, ext = name.rpartition(".")
    return stem.replace(".", "p") + "." + ext


def escape(text: str) -> str:
    """Escape specials in text that is ALREADY authored as LaTeX.

    Used for the u1 captions and the section notes, which contain deliberate
    math (`$\\beta$`) and commands. Only `%`, `&` and `#` are escaped, since
    those are never intentional here.
    """
    return text.replace("%", r"\%").replace("&", r"\&").replace("#", r"\#")


# The u2 captions are single-sourced from the u2 assembler, where they serve a
# MARKDOWN appendix, so they are plain prose: `<Q^2>`, `w_det(alpha)`, `Z_2`.
# Blanket-escaping those produces `\$<\$Q\^{}2\$>\$`, which is unreadable, and
# leaving them alone is a LaTeX error. So the recurring physics notation is
# translated first, protected behind placeholders, and only the residue is
# escaped. Ordered longest-first: `<Q^2>` must not be eaten by the `<` rule.
MATH: list[tuple[str, str]] = [
    ("<(1/2)ReTr W(A)> = r_fund^A",
     r"$\langle \tfrac{1}{2}\mathrm{Re\,Tr}\,W(A)\rangle = r_{\mathrm{fund}}^A$"),
    ("w_det(alpha) = 2 I_1(z)/z",
     r"$w_{\det}(\alpha) = 2 I_1(z)/z$"),
    ("<Q^2>", r"$\langle Q^2\rangle$"),
    ("|z| < 2", r"$|z| < 2$"),
    ("O(beta/V)", r"$O(\beta/V)$"),
    ("sqrt(2/pi)", r"$\sqrt{2/\pi}$"),
    ("Z_2", r"$Z_2$"),
    ("t_therm", r"$t_{\mathrm{therm}}$"),
    ("n_effective", r"$n_{\mathrm{effective}}$"),
    ("std(z)", r"$\mathrm{std}(z)$"),
    ("beta_f", r"$\beta_f$"),
    ("beta/4", r"$\beta/4$"),
    ("Z_2 monodromy", r"$Z_2$ monodromy"),
]

RESIDUE = [("%", r"\%"), ("&", r"\&"), ("#", r"\#"), ("_", r"\_"),
           ("^", r"\^{}"), ("~", r"\textasciitilde{}"),
           ("<", r"$<$"), (">", r"$>$")]


def plain_to_latex(text: str) -> str:
    """Convert a plain-prose caption to LaTeX without mangling its notation."""
    protected: list[str] = []

    def protect(replacement: str) -> str:
        protected.append(replacement)
        return f"\x00{len(protected) - 1}\x00"

    for plain, math in MATH:
        text = text.replace(plain, protect(math))
    # Backticked spans are code/paths; they carry underscores of their own.
    text = re.sub(r"`([^`]+)`",
                  lambda m: protect(r"\texttt{" + m.group(1).replace("_", r"\_")
                                    + "}"), text)
    for char, rep in RESIDUE:
        text = text.replace(char, rep)
    return re.sub(r"\x00(\d+)\x00", lambda m: protected[int(m.group(1))], text)


def lint_tex(text: str) -> list[str]:
    """Find unescaped LaTeX specials in typeset argument bodies.

    There is no TeX toolchain in this repo's environment, so the generated file
    cannot be compile-checked here. This is the substitute: it catches the one
    failure mode this generator can actually introduce -- a plain-prose caption
    reaching the page with a bare `_`, `^`, `<` or `%` in it, which is a hard
    LaTeX error rather than a cosmetic one. Math spans, `\\texttt` bodies and
    `\\ref`/`\\label` arguments are stripped first: specials are legal in all
    three.
    """
    backslash = chr(92)
    esc = re.escape(backslash)
    problems = []
    for kind in ("caption", "section", "emph"):
        for match in re.finditer(esc + kind + r"\{", text):
            index, depth = match.end(), 1
            while index < len(text) and depth:
                depth += {"{": 1, "}": -1}.get(text[index], 0)
                index += 1
            body = text[match.end():index - 1]
            stripped = re.sub(r"\$[^$]*\$", "", body)
            stripped = re.sub(esc + r"(texttt|ref|label)\{[^}]*\}", "", stripped)
            stripped = re.sub(esc + r"[a-zA-Z]+", "", stripped)
            for special in ("%", "&", "#", "_", "^"):
                stripped = stripped.replace(backslash + special, "")
            for char in "_^<>%&#":
                if char in stripped:
                    problems.append(f"{kind}: unescaped {char!r} in "
                                    f"{body[:70]!r}")
                    break
    return problems


def render(study: str, caption: str) -> str:
    """u1 captions are authored as LaTeX; u2 captions are plain markdown prose."""
    return escape(caption) if study == "u1" else plain_to_latex(caption)


def split_editorial(caption: str) -> tuple[str, str]:
    """Peel a leading editorial marker off a caption.

    Several captions open with a note to the author rather than to the reader
    -- "SECTION LEAD.", "STRONGEST PANEL IN THE SECTION.", "MAIN TEXT, method
    section, not the transfer section." Those earn their place in the internal
    appendix and in this outline, but a printed caption that announces its own
    placement reads as an editing mistake. They are emitted as a LaTeX comment
    above the figure instead, where they stay useful while drafting and vanish
    from the page.

    The marker is a leading sentence that STARTS in capitals and is short. The
    capitals test is on the first four characters, so "ESS across the ..." and
    "KL per site ..." (two-letter initialisms followed by a space) are not
    mistaken for markers.
    """
    match = re.match(r"^([A-Z]{4}[^.]*\.)\s+(.+)$", caption, re.DOTALL)
    if match and len(match.group(1)) <= 60:
        return match.group(1), match.group(2)
    return "", caption


# A single column at 10pt with 1in margins is about 3.2in wide. A figure with
# aspect 1.5 rendered there is 2.1in tall, which is already marginal for a
# multi-panel plot; anything wider is unreadable. So the span is decided from
# the image's MEASURED aspect ratio rather than by eye: at or above this, the
# figure gets `figure*` and spans both columns.
# Set from --draft; read inside figure_block.
DRAFT = [False]

SPAN_ASPECT = 1.5

# ...but aspect alone is not enough, and assuming it was got this wrong once.
# `46_observable_scan.png` is a four-panel figure 2459 px wide at aspect 1.48 --
# just under the threshold, so it would have been squeezed into 3.2 in with its
# panels at 1.6 in each. Native pixel width is the second signal: matplotlib
# saves at 150-200 dpi here, so 2000 px means the figure was DRAWN about ten
# inches wide and will not survive a third of that.
SPAN_PIXEL_WIDTH = 2000

# Editorial overrides, kept as an explicit list rather than by tuning a
# threshold until it produced the desired answer. A lead figure spans because
# it is the lead figure, which is not a property any measurement can see.
FORCE_SPAN = {("u1_2d", "29_seed_quality.png")}

# Above this, the figure is so wide that even full width leaves it a strip --
# `16_autocorrelation_modes.png` is 16588x1326, which is 0.5in tall across the
# text block. Emitted anyway, with a warning, because silently shipping an
# illegible figure is worse than shipping a flagged one.
STRIP_ASPECT = 6.0


def prepare_image(src: Path, dest: Path, palette: bool) -> tuple[int, int]:
    """Copy a figure into the bundle in a form pdfTeX does not have to decode.

    THIS IS THE COMPILE-TIME FIX, and it is not about how many figures there
    are. Matplotlib writes RGBA (colour type 6) and every one of these 82
    figures is RGBA. pdfTeX can copy a PNG's compressed image data straight
    into the PDF only for colour types 0, 2 and 3 (grey, RGB, palette) at 8 or
    16 bits, non-interlaced, with no transparency. RGBA misses that path, so
    pdfTeX decodes the image with libpng, splits the alpha into a SEPARATE
    soft-mask image, and re-encodes both -- across 145 megapixels here. That is
    what exhausts a free-plan compile budget; the figure count barely matters.

    Flattening onto white is EXACTLY lossless in this bundle: every alpha
    channel was measured and is fully opaque (extrema (255, 255)), so no pixel
    changes value. The saved file is RGB, non-interlaced, 8-bit, which is
    precisely the pass-through case.

    Deliberately NOT downsampled. Resampling anti-aliased line art creates more
    distinct colours than the crisp original, so capping at 300 dpi measured
    112% of the original bytes -- it costs quality and saves nothing. Pixel
    count is also no longer the cost once decoding is skipped.

    `palette` additionally quantizes to 256 colours: 40% of the original bytes,
    still pass-through, but LOSSY -- measured worst case across these figures is
    0.33% of pixels off by more than 8/255 (max 79), all of it on anti-aliased
    edges rather than in flat regions. Off by default; use it only if the
    lossless bundle is still too heavy.
    """
    try:
        from PIL import Image
    except ImportError:
        # Pillow is a matplotlib dependency, so this should not happen here.
        # Copy verbatim rather than fail, but say so loudly: the bundle will
        # still be RGBA and will still be slow to compile.
        print(f"  WARNING: no Pillow -- {src.name} copied as RGBA, which is "
              "the thing that makes compiles time out")
        shutil.copy2(src, dest)
        return png_size(src)

    with Image.open(src) as im:
        size = im.size
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            flat = Image.new("RGB", im.size, (255, 255, 255))
            flat.paste(im, mask=im.getchannel("A"))
        else:
            flat = im.convert("RGB")
        if palette:
            flat = flat.quantize(colors=256, method=Image.MEDIANCUT,
                                 dither=Image.NONE)
        flat.save(dest, "PNG", optimize=True)
    return size


def png_size(path: Path) -> tuple[int, int]:
    """Pixel width and height from the PNG IHDR chunk. No PIL for 8 bytes."""
    return struct.unpack(">II", path.read_bytes()[16:24])


def spans_columns(study: str, name: str, width: int, aspect: float) -> bool:
    """Does this figure need both columns to stay legible?"""
    return ((study, name) in FORCE_SPAN
            or aspect >= SPAN_ASPECT
            or width >= SPAN_PIXEL_WIDTH)


def figure_block(study: str, name: str, caption: str, wide: bool,
                 aspect: float) -> str:
    label = f"fig:{study}:{Path(latex_safe(name)).stem}"
    marker, caption = split_editorial(caption)
    prefix = [f"% OUTLINE NOTE: {marker}"] if marker else []
    width = "0.98" if wide else "1.0"
    if aspect >= STRIP_ASPECT:
        prefix.append(f"% WARNING: aspect {aspect:.1f} -- unreadably short even "
                      "at full text width; split it or rotate it.")
    # `\linewidth` adapts on its own: it is \textwidth inside figure* and
    # \columnwidth inside figure, so one width spec serves both.
    env = "figure*" if wide else "figure"
    # `h` and `b` are silently ignored for starred floats, so do not ask.
    where = "[tbp]" if wide else "[htbp]"
    return "\n".join(prefix + [
        f"\\begin{{{env}}}{where}",
        r"  \centering",
        f"  \\includegraphics[{'draft,' if DRAFT[0] else ''}"
        f"width={width}\\linewidth]{{{study}/{latex_safe(name)}}}",
        f"  \\caption{{{caption}}}",
        f"  \\label{{{label}}}",
        f"\\end{{{env}}}",
        "",
    ])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="paper",
                    help="bundle directory (created; figures overwritten)")
    ap.add_argument("--palette", action="store_true",
                    help="quantize figures to 256 colours: 40%% of the bytes, "
                         "still pass-through, but LOSSY (worst case measured "
                         "here: 0.33%% of pixels off by >8/255, all on "
                         "anti-aliased edges). Use only if the lossless bundle "
                         "is still too heavy.")
    ap.add_argument("--draft", action="store_true",
                    help="emit includegraphics[draft] -- figures become "
                         "labelled boxes and no image file is read at all. "
                         "For checking structure and float placement fast.")
    ap.add_argument("--check", action="store_true",
                    help="validate the plan against the assemblers without "
                         "writing anything")
    args = ap.parse_args()

    DRAFT[0] = args.draft
    u2_captions = load_u2_captions()
    captions = {"u1": U1_CAPTIONS, "u2": u2_captions}
    available = {"u1": {p.name for p in U1_FIGS.glob("*.png")},
                 "u2": {p.name for p in U2_FIGS.glob("*.png")}}
    source_dir = {"u1": U1_FIGS, "u2": U2_FIGS}

    placed: list[tuple[str, str]] = []
    for section_list in (MAIN, APPENDIX):
        for _label, _title, _note, figs in section_list:
            placed.extend(figs)

    problems = []
    duplicated = sorted({f for f in placed if placed.count(f) > 1})
    if duplicated:
        problems.append(f"placed more than once: {duplicated}")
    for study in ("u1", "u2"):
        want = {n for s, n in placed if s == study}
        missing_file = sorted(want - available[study])
        if missing_file:
            problems.append(f"{study}: placed but not on disk: {missing_file}")
        unplaced = sorted(available[study] - want)
        if unplaced:
            problems.append(f"{study}: on disk but in no section: {unplaced}")
        no_caption = sorted(want - set(captions[study]))
        if no_caption:
            problems.append(f"{study}: no caption: {no_caption}")

    for problem in problems:
        print(f"[plan] {problem}")
    if problems:
        print("\nFAIL: the figure plan does not match the assembled figures")
        return 1
    print(f"plan is consistent: {len(placed)} figures placed, "
          f"{len([f for f in placed if f[0] == 'u1'])} u1 / "
          f"{len([f for f in placed if f[0] == 'u2'])} u2")
    if args.check:
        return 0

    out = Path(args.out)
    total_bytes = [0, 0]
    for study in ("u1", "u2"):
        dest = out / "figures" / f"{study}_2d"
        dest.mkdir(parents=True, exist_ok=True)
        for name in sorted(available[study]):
            prepare_image(source_dir[study] / name, dest / latex_safe(name),
                          args.palette)
        written = sum(f.stat().st_size for f in dest.glob("*.png"))
        source_bytes = sum((source_dir[study] / n).stat().st_size
                           for n in available[study])
        total_bytes[0] += source_bytes
        total_bytes[1] += written
        print(f"copied {len(available[study])} figures -> {dest} "
              f"({source_bytes / 1e6:.1f} -> {written / 1e6:.1f} MB)")

    spans = {True: 0, False: 0}
    lines = [PREAMBLE]
    for label, title, note, figs in MAIN:
        lines.append(f"\\section{{{escape(title)}}}\n\\label{{sec:{label}}}\n")
        if note:
            lines.append(f"\\emph{{Outline: {escape(note)}}}\n")
        for study, name in figs:
            px_w, px_h = png_size(source_dir[study] / name)
            aspect = px_w / px_h if px_h else 1.0
            wide = spans_columns(f"{study}_2d", name, px_w, aspect)
            lines.append(figure_block(f"{study}_2d", name,
                                      render(study, captions[study][name]),
                                      wide, aspect))
            spans[wide] += 1
        lines.append("\\clearpage\n")

    lines.append("\\appendix\n")
    for label, title, note, figs in APPENDIX:
        lines.append(f"\\section{{{escape(title)}}}\n\\label{{{label}}}\n")
        if note:
            lines.append(f"\\emph{{Outline: {escape(note)}}}\n")
        for study, name in figs:
            px_w, px_h = png_size(source_dir[study] / name)
            aspect = px_w / px_h if px_h else 1.0
            wide = spans_columns(f"{study}_2d", name, px_w, aspect)
            lines.append(figure_block(f"{study}_2d", name,
                                      render(study, captions[study][name]),
                                      wide, aspect))
            spans[wide] += 1
        lines.append("\\clearpage\n")
    lines.append("\\end{document}\n")

    kind = "256-colour palette" if args.palette else "RGB (lossless here)"
    print(f"figures: RGBA -> {kind}, "
          f"{total_bytes[0] / 1e6:.1f} -> {total_bytes[1] / 1e6:.1f} MB. "
          "pdfTeX copies these streams into the PDF instead of decoding each "
          "and building a soft mask -- that is the compile-time fix.")
    print(f"two-column: {spans[True]} figures span both columns (figure*), "
          f"{spans[False]} sit in one column (aspect < {SPAN_ASPECT} and "
          f"native width < {SPAN_PIXEL_WIDTH} px)")
    tex = out / "main.tex"
    tex.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {tex}")

    # A figure whose \label is never \ref'd is fine in an outline, but a \ref to
    # a label that does not exist is a dangling cross-reference and is not.
    text = tex.read_text(encoding="utf-8")
    labels = set(re.findall(r"\\label\{([^}]+)\}", text))
    refs = set(re.findall(r"\\ref\{([^}]+)\}", text))
    dangling = sorted(refs - labels)
    if dangling:
        print(f"WARNING: dangling \\ref targets: {dangling}")
        return 1
    print(f"{len(labels)} labels, {len(refs)} references, none dangling")

    lint = lint_tex(text)
    for problem in lint:
        print(f"[latex] {problem}")
    if lint:
        print("\nFAIL: unescaped LaTeX specials reached a typeset argument")
        return 1
    print("no unescaped LaTeX specials in captions or headings")
    print("NOTE: no TeX toolchain in this environment -- this is a lint, not a "
          "compile. Build once in Overleaf before trusting it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
