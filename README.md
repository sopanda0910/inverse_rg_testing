# InverseRG (diffusion)

Diffusion-based inverse renormalization group for 2D compact U(1) lattice gauge theory.

Coarse configurations are lifted to fine configurations with a score-based (diffusion) model over wrapped link angles, trained so that gauge-invariant observable distributions (Wilson loops, topological charge) match direct HMC ensembles. Iterating the lift up a matched beta ladder produces large, fine lattices at costs where direct HMC suffers from critical slowing down and topological freezing.

All project code lives in [`diffusion/`](diffusion/README.md) — see that README for the physics background, module layout, and pipeline instructions.

## Quick Start

A virtual environment is pre-configured at `.venv/` with all dependencies installed:

```bash
source .venv/bin/activate      # Windows: .venv/Scripts/activate
pip install -e .
```

Run the pipeline (see `diffusion/README.md` for details):

```bash
python diffusion/scripts/01_generate_data.py --config diffusion/configs/demo.yaml
python diffusion/scripts/02_train.py         --config diffusion/configs/demo.yaml
python diffusion/scripts/03_run_ladder.py    --config diffusion/configs/demo.yaml
python diffusion/scripts/04_validate.py      --config diffusion/configs/demo.yaml
```

Run tests:

```bash
pytest diffusion/tests -q
```

## References

- M. Creutz, *Quarks, Gluons and Lattices*, Cambridge University Press (1983).
