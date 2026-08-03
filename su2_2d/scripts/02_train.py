"""Train the SU(2) curl-head score network by exact heat-kernel DSM.

    .venv/Scripts/python.exe su2_2d/scripts/02_train.py --config su2_2d/configs/su2.yaml
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import os

import torch

torch.set_num_threads(int(os.environ.get("SU2_2D_TORCH_THREADS", "8")))
import yaml

from su2_2d.model.train import train


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="su2_2d/configs/su2.yaml")
    args = parser.parse_args()
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))

    data_dir = Path(config["data"]["out_dir"])

    def load(pattern):
        out = []
        for f in sorted(data_dir.glob(pattern)):
            blob = torch.load(f, map_location="cpu", weights_only=False)
            out.append((blob["lattice_size"], blob["configs"], blob["beta"]))
        return out

    def group_by_size(datasets):
        groups = []
        for l in sorted({size for size, _, _ in datasets}):
            parts = [(c, b) for (size, c, b) in datasets if size == l]
            data = torch.cat([c for c, _ in parts], dim=0)
            beta_vec = torch.cat([torch.full((c.shape[0],), float(b)) for c, b in parts])
            groups.append((data, beta_vec))
            betas = sorted({round(float(b), 3) for _, b in parts})
            print(f"  L={l}: {data.shape[0]} configs over {len(betas)} couplings "
                  f"[{min(betas):g} .. {max(betas):g}]")
        return groups

    datasets = load("wilson_*.pt")
    if not datasets:
        raise SystemExit("no training data — run 01_generate_data.py first")
    print("training groups:")
    groups = group_by_size(datasets)

    heldout_sets = load("heldout_*.pt")
    heldout = None
    if heldout_sets:
        print("held-out (never trained, generalization guard):")
        heldout = group_by_size(heldout_sets)

    ckpt = config["train"]["checkpoint"]
    train(groups, config["train"], checkpoint_path=ckpt, seed=config["seed"],
          heldout_groups=heldout)
    print(f"checkpoint: {ckpt}")


if __name__ == "__main__":
    main()
