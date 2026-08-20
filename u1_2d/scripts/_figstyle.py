"""Shared drawing conventions for the paper figures.

Scripts 50 and 51 each carried their own copy of this palette; the panels added
for `PAPER_OUTLINE.md` are numerous enough that a third copy would guarantee
drift. The values are unchanged from script 50, which validated them:
Okabe-Ito, fixed order, never cycled -- lightness band PASS, chroma floor PASS,
normal-vision contrast floor 18.7. Adjacent-pair CVD separation sits at 7.6,
inside the floor band, so every series that uses hue must also carry a distinct
marker or a direct label.
"""

INK, MUTED, GRID = "#1a1a1a", "#5c5c5c", "#d8d8d8"

OKABE_ITO = {
    "orange": "#D55E00",
    "blue": "#0072B2",
    "sky": "#56B4E9",
    "green": "#009E73",
    "purple": "#CC79A7",
    "yellow": "#E69F00",
    "vermilion": "#D55E00",
}

ARM = {
    "seed": ("#D55E00", "o", "diffusion seed"),
    "cold": ("#0072B2", "s", "fresh cold start"),
    "hot": ("#56B4E9", "^", "fresh hot start"),
    "ape": ("#009E73", "D", "APE-smeared prolongator"),
    "geom": ("#CC79A7", "x", "geometric prolongators"),
    "hmc": ("#0072B2", "s", "periodic HMC"),
    "hmc+inst": ("#009E73", "D", "HMC + winding update"),
    "ptbc": ("#CC79A7", "v", "PTBC (tuned)"),
    "open": ("#E69F00", "P", "open boundaries"),
}


def dress(ax, *, grid="major"):
    """Spines, ticks and grid, applied identically everywhere."""
    if grid:
        ax.grid(True, which=grid, color=GRID, lw=0.6, zorder=0)
        ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
        ax.spines[side].set_linewidth(0.8)
    ax.tick_params(colors=MUTED, labelsize=8.5)


def title(ax, text, **kw):
    ax.set_title(text, fontsize=11.5, color=INK, pad=12, loc="left", **kw)


def panel_tag(ax, tag, x=-0.085, y=1.06):
    ax.text(x, y, tag, transform=ax.transAxes, fontsize=10.5,
            fontweight="bold", color=INK, ha="left", va="bottom")
