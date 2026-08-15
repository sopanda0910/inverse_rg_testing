"""Recover Zhu et al.'s published histogram counts from their figure, exactly.

arXiv:2410.19602 reports its topological-charge results only as histograms --
no tables, no data-availability statement, no code release. It also flags the
one comparison that would settle whether those histograms are *correct*:

    "We are currently comparing the numerically computed distribution with the
     analytical prediction, which is possible in this simple theory."

The analytical prediction is `u1_2d.lgt.exact`. The missing half is their
numbers, and those turn out to be recoverable: the figures are vector graphics
(the PDF contains no image XObjects), so every bar is a path whose corner
coordinates are in the content stream. Calibrating against the axis ticks
returns the bar heights, and the check that this is exact rather than
approximate is that every recovered height is an integer multiple of 1/1024 --
their stated ensemble size -- with the counts summing to 1023.

This is digitization of a published figure, not their released data. It is
labelled as such wherever the numbers are used.

    .venv/Scripts/python.exe u1_2d/scripts/47_zhu_figure_extract.py \
        --pdf ~/Downloads/2410.19602v1.pdf
"""

import argparse
import importlib.util
import json
import re
import zlib
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
NUM = r"[-+]?\d*\.?\d+"


def _load_18():
    spec = importlib.util.spec_from_file_location(
        "pq18", REPO / "u1_2d" / "scripts" / "18_pq_hmc_tail.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def decompress_streams(pdf: Path) -> dict[int, bytes]:
    data = pdf.read_bytes()
    if b"/Subtype/Image" in data or b"/Subtype /Image" in data:
        print("warning: PDF contains raster images; figures may not be vector")
    out, i = {}, 0
    for m in re.finditer(rb"stream\r?\n", data):
        s = m.end()
        e = data.find(b"endstream", s)
        if e < 0:
            continue
        try:
            out[i] = zlib.decompress(data[s:e])
        except zlib.error:
            out[i] = None
        i += 1
    return out


def find_panels(streams: dict, want: str) -> list[int]:
    """Content streams whose drawn text contains `want`.

    More than one panel can match -- the trajectory figure carries the same
    axis label as the histogram -- so this returns all candidates and the
    caller keeps whichever actually yields bars.
    """
    hits = []
    for idx, dec in streams.items():
        if not dec:
            continue
        labels = "".join(re.findall(r"\((.*?)\)", dec.decode("latin1")))
        if want.replace(" ", "") in labels.replace(" ", ""):
            hits.append(idx)
    return hits


def extract_bars(dec: bytes) -> dict:
    """Bar heights per series, in data coordinates.

    Calibration uses the shared bar baseline for zero (not the tick-label
    baseline, which sits a few points lower and would bias every height by a
    constant) and the labelled tick spacing for the scales.
    """
    d = dec.decode("latin1")
    x0, y0, _, _ = map(float, re.search(
        rf"({NUM}) ({NUM}) ({NUM}) ({NUM}) re W n", d).groups())
    labs = []
    for m in re.finditer(rf"1 0 -0 1 ({NUM}) ({NUM}) cm\s*\nBT(.*?)ET", d, re.S):
        labs.append((float(m.group(1)), float(m.group(2)),
                     "".join(re.findall(r"\((.*?)\)", m.group(3)))))
    yl = sorted((ty, float(s)) for tx, ty, s in labs
                if tx < x0 and re.fullmatch(r"[\d.]+", s))
    xl = sorted((tx, s) for tx, ty, s in labs
                if ty < y0 and re.fullmatch(r"\d+", s))
    dy = (yl[-1][0] - yl[0][0]) / (yl[-1][1] - yl[0][1])
    dx = min(xl[i + 1][0] - xl[i][0] for i in range(len(xl) - 1))

    cur, shapes = [], []
    for ln in (l.strip() for l in d.split("\n")):
        mm = re.fullmatch(rf"({NUM}) ({NUM}) (m|l)", ln)
        if mm:
            cur.append((float(mm.group(1)), float(mm.group(2))))
            continue
        if ln == "h":
            continue
        if ln in ("f", "f*", "B", "b", "B*", "b*", "S"):
            if ln in ("B", "b", "B*", "b*") and len(cur) >= 4:
                shapes.append(cur[:])
            cur = []

    boxes = []
    for pts in shapes:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        if max(xs) - min(xs) < 5 or max(ys) - min(ys) < 0.5:
            continue
        boxes.append((min(xs), max(xs), min(ys), max(ys)))
    if not boxes:
        return {}
    base = Counter(round(b[2], 3) for b in boxes).most_common(1)[0][0]
    barw = Counter(round(b[1] - b[0], 2) for b in boxes).most_common(1)[0][0]
    zeros = [tx for tx, s in xl if s == "0"]
    xz = zeros[len(zeros) // 2]
    centres = sorted({round((b[0] + b[1]) / 2, 3) for b in boxes
                      if abs((b[1] - b[0]) - barw) < 0.5})
    xzero = min(centres, key=lambda c: abs(c - (xz + 4.5)))

    series = {}
    for b in boxes:
        if abs((b[1] - b[0]) - barw) > 0.5 or abs(b[2] - base) > 1.0:
            continue
        q = ((b[0] + b[1]) / 2 - xzero) / dx
        v = (b[3] - base) / dy
        if v < 1e-4:
            continue
        series.setdefault(round(q - round(q), 2), {})[round(q)] = v
    return {k: v for k, v in series.items() if len(v) >= 3}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default=str(Path.home() / "Downloads" / "2410.19602v1.pdf"))
    ap.add_argument("--n", type=int, default=1024,
                    help="their stated ensemble size; used to verify the "
                         "recovered heights are exact integer counts")
    ap.add_argument("--L", type=int, default=16)
    ap.add_argument("--beta", type=float, default=7.0)
    ap.add_argument("--out", default="out/u1_2d/zhu_comparison")
    args = ap.parse_args()

    pdf = Path(args.pdf).expanduser()
    if not pdf.exists():
        raise SystemExit(f"PDF not found: {pdf}")
    streams = decompress_streams(pdf)
    candidates = find_panels(streams, "Topological Charge Q")
    if not candidates:
        raise SystemExit("could not locate any topological-charge panel")
    idx, series = None, {}
    for c in candidates:
        try:
            s = extract_bars(streams[c])
        except (AttributeError, IndexError, ValueError, ZeroDivisionError):
            continue
        # keep the panel with the most occupied sectors; the trajectory figure
        # shares the axis label but draws no bars
        if sum(len(v) for v in s.values()) > sum(len(v) for v in series.values()):
            idx, series = c, s
    if not series:
        raise SystemExit(f"no bars recovered from panels {candidates}; "
                         "the figure may not be vector")

    from u1_2d.lgt import exact
    m18 = _load_18()
    q_values, probs = exact.topological_charge_distribution(
        args.beta, args.L, "wilson")
    exq2 = float((q_values.astype(float) ** 2 * probs).sum())
    ex = {int(q): float(p) for q, p in zip(q_values, probs)}

    # The series with the most occupied sectors is the diffusion model; the
    # narrow one is HMC (their frozen arm).
    ordered = sorted(series.values(), key=len, reverse=True)
    named = {"diffusion (Zhu et al.)": ordered[0]}
    if len(ordered) > 1:
        named["HMC (Zhu et al.)"] = ordered[1]

    rows = []
    print(f"panel stream index {idx};  exact <Q^2> = {exq2:.4f} at "
          f"L={args.L}, beta={args.beta:g}\n")
    for label, dist in named.items():
        counts = {q: v * args.n for q, v in dist.items()}
        ints = {q: int(round(c)) for q, c in counts.items()}
        max_dev = max(abs(counts[q] - ints[q]) for q in counts)
        q_series = np.array([q for q, c in ints.items() for _ in range(c)],
                            dtype=float)
        q2 = float((q_series ** 2).mean())
        p = m18.chi2_p(q_series, q_values, probs)
        rows.append({
            "arm": label, "counts": ints, "total": int(sum(ints.values())),
            "max_integer_deviation": round(max_dev, 3),
            "q2": q2, "q2_over_exact": q2 / exq2, "chi2_p": p,
        })
        print(f"{label}")
        print("  Q       " + "".join(f"{q:>8d}" for q in sorted(ints)))
        print("  counts  " + "".join(f"{ints[q]:>8d}" for q in sorted(ints)))
        print("  exact   " + "".join(f"{ex.get(q, 0.0) * args.n:>8.1f}"
                                     for q in sorted(ints)))
        print(f"  total {sum(ints.values())} of {args.n};  max deviation from "
              f"integer counts {max_dev:.3f}")
        print(f"  <Q^2> = {q2:.4f}  ({q2 / exq2:.2f}x exact)   chi2 p = "
              f"{'n/a' if p is None else f'{p:.3g}'}\n")

    worst = max(r["max_integer_deviation"] for r in rows)
    if worst < 0.05:
        print("Every recovered height is an integer count to <0.05 of a "
              "configuration:\nthe extraction is exact, not an estimate.")
    else:
        print(f"WARNING: heights deviate from integer counts by up to {worst:.2f}; "
              "treat as approximate digitization.")

    out = REPO / args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "zhu_figure_counts.json").write_text(
        json.dumps({"source": str(pdf), "panel_stream": idx,
                    "L": args.L, "beta": args.beta, "n_stated": args.n,
                    "exact_q2": exq2, "arms": rows}, indent=2, default=str),
        encoding="utf-8")
    print(f"wrote {(out / 'zhu_figure_counts.json').relative_to(REPO)}")


if __name__ == "__main__":
    main()
