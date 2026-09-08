"""Swap the sector-augmented supplement rungs into u1's training directory,
keeping the single-sector originals, and REFUSE to proceed unless the swap
actually produced topological coverage.

The verification is the point. The first attempt at this fix regenerated all
30 rungs, exited 0 at every level, logged DONE -- and produced ensembles
byte-equivalent in coverage to the ones they replaced, because
`01_generate_data.py` read `sector_augment` only from the per-rung dict and
the config set it at the `data:` level. Nothing in any log said so. So this
script checks the PROPERTY (does each swapped rung occupy more than one
topological sector) rather than the exit code, and fails loudly if not.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from u1_2d.lgt.lattice import topological_charge

SRC = Path("out/u1_2d/data_random_2000_sectorfix")
DST = Path("out/u1_2d/data_wide")
BAK = Path("out/u1_2d/data_wide_presectorfix")
EXPECTED = 30


def sectors(path: Path) -> tuple[int, float]:
    p = torch.load(path, map_location="cpu", weights_only=True)
    q = topological_charge(p["configs"]).numpy().round().astype(int)
    return int(len(np.unique(q))), float((q ** 2).mean())


def main() -> int:
    files = sorted(SRC.glob("*.pt"))
    # REQUIRE THE FULL SET. A partial swap is worse than none: it produces a
    # training set that is neither the control nor the corrected arm, and
    # nothing downstream would say so. This fired for real on 2026-09-07,
    # when a stale log marker let the retrain start after only 4 of 30 rungs
    # had been regenerated.
    if len(files) < EXPECTED:
        print(f"REFUSING: {len(files)} regenerated rungs under {SRC}, "
              f"expected {EXPECTED}. A partial swap would silently mix the "
              f"corrected and control arms.")
        return 1
    if not files:
        print(f"no regenerated rungs under {SRC}")
        return 1
    BAK.mkdir(parents=True, exist_ok=True)
    swapped, bad = 0, []
    for f in files:
        n_sec, q2 = sectors(f)
        if n_sec < 2:
            bad.append((f.name, n_sec, q2))
            continue
        target = DST / f.name
        if target.exists():
            shutil.copy2(target, BAK / f.name)
        shutil.copy2(f, target)
        swapped += 1
        print(f"  swapped {f.name}: {n_sec} sectors, <Q^2>={q2:.4f}")
    if bad:
        print(f"\nREFUSING: {len(bad)} regenerated rung(s) still occupy one sector:")
        for name, n, q2 in bad:
            print(f"  {name}: sectors={n} <Q^2>={q2:.4f}")
        print("The augmentation did not take effect. Do not train on this.")
        return 1
    print(f"\n{swapped} rungs swapped; originals kept in {BAK}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
