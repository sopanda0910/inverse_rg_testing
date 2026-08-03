"""Train the SU(2) curl-head score network by exact heat-kernel DSM.

    .venv/Scripts/python.exe su2_2d/scripts/02_train.py --config su2_2d/configs/su2.yaml
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import torch
import yaml

from su2_2d.model.train import train


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="su2_2d/configs/su2.yaml")
    args = parser.parse_args()
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))

    datasets, betas = [], []
    for f in sorted(Path(config["data"]["out_dir"]).glob("wilson_*.pt")):
        blob = torch.load(f, map_location="cpu", weights_only=False)
        # mixed lattice sizes train fine (fully convolutional): group per size
        datasets.append((blob["lattice_size"], blob["configs"], blob["beta"]))
    if not datasets:
        raise SystemExit("no training data — run 01_generate_data.py first")

    # simplest first version: train per lattice size, sharing one checkpoint
    # via sequential passes (continuous-beta multi-size training carried over
    # from U(1) comes after the first lift validates)
    sizes = sorted({l for l, _, _ in datasets})
    ckpt = config["train"]["checkpoint"]
    for l in sizes:
        parts = [(c, b) for (ll, c, b) in datasets if ll == l]
        data = torch.cat([c for c, _ in parts], dim=0)
        beta_vec = torch.cat([torch.full((c.shape[0],), float(b)) for c, b in parts])
        print(f"training on L={l}: {data.shape[0]} configs, "
              f"betas {sorted({float(b) for _, b in parts})}")
        train(data, beta_vec, config["train"], checkpoint_path=ckpt,
              seed=config["seed"])
    print(f"checkpoint: {ckpt}")


if __name__ == "__main__":
    main()
