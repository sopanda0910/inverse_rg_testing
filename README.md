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
| `su2_2d/` | 2D SU(2) | **set aside, not in the tree** — restore with `git checkout 87fd6fa -- su2_2d` |

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
pip install -e .               # required: scripts import `u1_2d` as a package
pytest u1_2d/tests -q
```

Checks that should pass before anything is published:

```bash
python u1_2d/scripts/29_verify_identities.py              # exact physics identities
python u1_2d/scripts/30_assemble_appendix_figures.py --check   # figures match sources
```

The first re-derives every claim tagged exact in
[`docs/PHYSICS_WALKTHROUGH.md`](docs/PHYSICS_WALKTHROUGH.md) — topological
charge integrality, gauge invariance, the blocking telescope, curl-head
completeness against the Wilson score, the ⟨Q²⟩ ladder fixed point, the area
law, and the instanton hop cost. The second verifies the 27 appendix figures
still match the outputs they were made from.
