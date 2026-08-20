"""Seed an ensemble across topological sectors from the exact determinant P(Q).

WHY THIS EXISTS. In 2D U(2) the classical global winding move works only at even
charge (see `local_updates`), so above the freezing threshold a plain HMC chain
cannot equilibrate P(Q) at all: measured at L = 8, plain HMC makes 0 sector
changes at beta >= 20, and adding the winding move buys only even-charge hops.
The stage-01 ensembles at the ladder's base coupling come out with
<Q^2> = 0.083 against an exact 0.504 -- they are not reference ensembles, they are
one sector.

WHAT THIS DOES, AND WHY IT IS LEGITIMATE. The determinant-sector P(Q) is known in
closed form and has been checked against local sampling to 1-2% in every sector
(`scripts/05_topology_study.py`). Sampling a target sector from it and moving each
configuration there is exact by construction, and the two steps that follow are
each exact as well:

    Q ~ P(Q) exact        ->  set_topological_charge (deterministic, hits any sector)
                          ->  conditional_su2_sweeps (EXACT sampler for p(q | psi))

The conditional sampler is what makes this honest rather than a fudge: the
winding map leaves a large SU(2) action defect at odd charge (measured 38-191),
and the conditional heatbath removes it exactly, without touching psi or Q. What
remains is an ensemble with the correct sector weights whose within-sector
distribution the subsequent HMC burn-in equilibrates. Since local dynamics does
not tunnel at these couplings, the seeded sector weights survive burn-in, which is
precisely the property that makes this work and also the property that makes it a
seeding step and not a sampler.

This is the U(2) analogue of `u1_2d.pipeline.ladder.resample_exact_sectors`, and
ensembles built with it must be labelled as such -- their P(Q) is exact by
construction, so they cannot also be used as evidence that P(Q) is right.
"""

import torch

from .actions import WilsonU2Action
from .exact import det_topological_charge_distribution
from .lattice import topological_charge
from .local_updates import conditional_su2_sweeps, set_topological_charge


def sample_exact_sectors(n_configs: int, beta: float, lattice_size: int,
                         generator: torch.Generator | None = None) -> torch.Tensor:
    """Draw `n_configs` topological charges from the exact finite-volume P(Q)."""
    q_values, probs = det_topological_charge_distribution(beta, lattice_size)
    index = torch.multinomial(torch.from_numpy(probs).to(dtype=torch.float64),
                              n_configs, replacement=True, generator=generator)
    return torch.from_numpy(q_values).to(dtype=torch.float64)[index]


def seed_exact_sectors(links: torch.Tensor, beta: float, n_su2_sweeps: int = 25,
                       generator: torch.Generator | None = None) -> torch.Tensor:
    """Move each configuration into a sector drawn from the exact P(Q), then
    re-equilibrate the SU(2) sector at frozen determinant."""
    targets = sample_exact_sectors(links.shape[0], beta, links.shape[-2],
                                   generator=generator).to(links.dtype)
    moved = set_topological_charge(links, targets)
    relaxed = conditional_su2_sweeps(moved, WilsonU2Action(beta), n_su2_sweeps)
    return relaxed


def seeded_sector_fraction(links: torch.Tensor, targets: torch.Tensor) -> float:
    """Fraction of configurations that actually landed in their target sector.

    The winding map can miss when a plaquette sits at the branch cut, which is
    common on hot or strongly coupled starts and exp-small exactly where seeding
    matters. Reported rather than asserted, because at those couplings the burn-in
    equilibrates topology on its own and a miss costs nothing.
    """
    return float((topological_charge(links) == targets.to(links.device)).double().mean())
