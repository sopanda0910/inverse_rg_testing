"""Compare a verification run's validation report against the frozen v2 results.

    python u1_2d/scripts/31_compare_verification.py

The comparison is against *exact* character-expansion results (the z_exact column),
not against the frozen run's central values: two checkpoints trained from different
RNG streams are not expected to agree config-for-config, but both must agree with
the exact theory to within their own error bars. A GPU port that changed the physics
would show up as z_exact drifting away from zero, not as a shifted plaquette.
"""

import argparse
import re
from pathlib import Path

FROZEN = "out/u1_2d/validation/report.md"
CANDIDATE = "out/u1_2d/gpu_verification/validation/report.md"
# The observables the appendix actually quotes, plus the extended loops where
# CLAUDE.md says residual model error concentrates.
KEY = ["plaquette", "wilson_2x2", "wilson_4x4", "wilson_8x8", "Q^2",
       "chi_top ((<Q^2>-<Q>^2)/V)"]


def parse_report(path: Path) -> dict[str, dict[str, dict[str, float]]]:
    """{rung: {observable: {column: value}}} from the markdown tables."""
    rungs: dict[str, dict[str, dict[str, float]]] = {}
    rung = None
    header: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            rung = line[3:].strip()
            rungs[rung] = {}
            header = []
        elif line.startswith("|") and rung is not None:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if not header:
                header = cells
                continue
            if set("".join(cells)) <= set("-: "):
                continue
            row = {}
            for col, cell in zip(header[1:], cells[1:]):
                try:
                    row[col] = float(cell)
                except ValueError:
                    pass
            rungs[rung][cells[0]] = row
    return rungs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen", default=FROZEN)
    parser.add_argument("--candidate", default=CANDIDATE)
    args = parser.parse_args()

    frozen, cand = parse_report(Path(args.frozen)), parse_report(Path(args.candidate))
    worst = 0.0
    verdict_lines = []
    for rung in frozen:
        if rung not in cand:
            verdict_lines.append(f"MISSING in candidate: {rung}")
            continue
        print(f"\n## {rung}")
        print(f"{'observable':28s} {'frozen':>11s} {'z_ex':>7s}   "
              f"{'candidate':>11s} {'z_ex':>7s}   {'d(z_ex)':>8s}")
        for obs in KEY:
            f_row, c_row = frozen[rung].get(obs), cand[rung].get(obs)
            if not f_row or not c_row:
                continue
            fz, cz = f_row.get("z_exact"), c_row.get("z_exact")
            if fz is None or cz is None:
                continue
            dz = cz - fz
            worst = max(worst, abs(cz))
            print(f"{obs:28s} {f_row['value']:11.5g} {fz:7.2f}   "
                  f"{c_row['value']:11.5g} {cz:7.2f}   {dz:+8.2f}")

    print(f"\nlargest |z_exact| in the candidate run: {worst:.2f}")
    print("interpretation: |z_exact| <~ 3 across the key observables means the "
          "candidate agrees with exact theory as well as the frozen run does.")
    for line in verdict_lines:
        print(line)


if __name__ == "__main__":
    main()
