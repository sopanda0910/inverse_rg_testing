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

    datasets = []
    for f in sorted(Path(config["data"]["out_dir"]).glob("wilson_*.pt")):
        blob = torch.load(f, map_location="cpu", weights_only=False)
        datasets.append((blob["lattice_size"], blob["configs"], blob["beta"]))
    if not datasets:
        raise SystemExit("no training data — run 01_generate_data.py first")

    # one model over all sizes and couplings: group by lattice size (batches
    # must share a size to stack), then train jointly across groups
    groups = []
    for l in sorted({size for size, _, _ in datasets}):
        parts = [(c, b) for (size, c, b) in datasets if size == l]
        data = torch.cat([c for c, _ in parts], dim=0)
        beta_vec = torch.cat([torch.full((c.shape[0],), float(b)) for c, b in parts])
        groups.append((data, beta_vec))
        print(f"group L={l}: {data.shape[0]} configs, "
              f"betas {sorted({float(b) for _, b in parts})}")

    ckpt = config["train"]["checkpoint"]
    train(groups, config["train"], checkpoint_path=ckpt, seed=config["seed"])
    print(f"checkpoint: {ckpt}")


if __name__ == "__main__":
    main()
