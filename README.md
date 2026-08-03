# InverseRG

Diffusion-based inverse renormalization group for lattice field theories.

Coarse configurations are lifted to fine configurations with a score-based
(diffusion) model, trained so that gauge-invariant observable distributions
(Wilson loops, and where applicable topological charge) match direct HMC
ensembles. Iterating the lift up a matched beta ladder produces large, fine
lattices at costs where direct HMC suffers from critical slowing down and
topological freezing.

## Layout

| package | theory | status |
|---|---|---|
| [`u1_2d/`](u1_2d/) | 2D compact U(1) | **closed** — complete study, results of record in [`out/u1_2d/paper_appendix/appendix.md`](out/u1_2d/paper_appendix/appendix.md) |
| [`su2_2d/`](su2_2d/) | 2D SU(2) | active — scripted, heavy stages not yet run |

The full mathematical narrative of the U(1) study (physics background,
diffusion machinery, the exactness program, AIS, and closure) is in
[`docs/NARRATIVE.md`](docs/NARRATIVE.md); the final audit is
[`docs/V2_AUDIT.md`](docs/V2_AUDIT.md).

Headline U(1) result: at large beta, plain HMC is topologically frozen and
instanton-HMC pays an entry cost that leaves it ~6 sigma biased on Wilson
observables at L = 64 even after 16x the standard burn-in, while the
diffusion pipeline is flat-cost and passes all observables — with its
correctness carried by exact Markov-chain machinery wrapped around the
generative proposal.

## Quick start

A virtual environment is pre-configured at `.venv/`:

```bash
.venv/Scripts/activate         # Windows
pip install -e .
pytest u1_2d/tests su2_2d/tests -q
```

SU(2) pipeline (scripted; see `su2_2d/README.md`):

```bash
python su2_2d/scripts/00_smoke.py
python su2_2d/scripts/01_generate_data.py --config su2_2d/configs/su2.yaml
python su2_2d/scripts/02_train.py         --config su2_2d/configs/su2.yaml
python su2_2d/scripts/03_sample_validate.py --config su2_2d/configs/su2.yaml
```
