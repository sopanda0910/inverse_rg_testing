"""The determinant half of the lift: reuse the closed U(1) study on psi = wrap(2 phi).

`u2_2d.lgt.lattice.det_links` hands back a [B, 2, L, L] compact U(1) gauge field
in exactly the layout `u1_2d` consumes, and blocking commutes with it (det is a
homomorphism), so the ENTIRE U(1) generative stack applies unchanged:

    u1_2d.model.score_net.GaugeCovariantScoreNet   gauge-invariant inputs, curl head
    u1_2d.model.train.train_score_model            denoising score matching
    u1_2d.model.schedule.GeometricNoiseSchedule    wrapped-Gaussian noise ladder
    u1_2d.pipeline.ladder.blocking_consistency_score / apply_coarse_charge

That reuse is the point of the split representation, and it is why the U(2) study
starts from a finished machine rather than a blank one.

TWO THINGS ARE NOT INHERITED, AND BOTH MATTER.

1. The determinant sector is NOT U(1) Wilson at beta / 4. Integrating SU(2) out
   of one plaquette gives the exact marginal weight
   w_det(alpha) = 2 I_1(z) / z with z = beta cos(alpha / 2)
   (`u2_2d.lgt.actions.DetSectorAction`), whose large-beta expansion is Wilson at
   beta_1 = beta / 4 plus a (3/2) log cos(alpha / 2) measure term from the three
   integrated-out SU(2) directions. Training data are real U(2) determinant
   fields, so the score-matching target is exact regardless; but anything that
   quotes an analytic U(1) coupling -- the beta the network is conditioned on, the
   analytic force hint inside its head -- must use `matched_u1_beta`, the
   minimum-KL projection onto the U(1) family, and not beta / 4. The two agree to
   0.003% at beta = 220 and disagree by 23% at beta = 4 (see
   `lgt.exact.det_matching_residuals`).

2. The physics blend must use the determinant-sector score, not the Wilson one.
   `u2_2d.pipeline.ladder` supplies `det_sector_exact_score` for that; the Bessel
   ratio I_2 / I_1 it carries tends to 1 only at large coupling.

The network is conditioned on `matched_u1_beta(beta_u2)` so its learned
sigma/beta embedding and its gated analytic hint sit at a coupling where the
Wilson form is the best available one-parameter description of the data. The
residual is exactly what the score net is there to learn.
"""

import torch

from ..lgt.blocking import block_links
from ..lgt.exact import matched_u1_beta
from ..lgt.lattice import det_links


def model_beta(beta_u2: float) -> float:
    """The U(1) coupling to condition the determinant score net on."""
    return matched_u1_beta(float(beta_u2))


def det_pair(fine_links: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """U(2) ensemble -> (fine determinant field, blocked determinant field).

    Uses `det_links(block_links(.))`, which equals `u1_2d`-blocking of
    `det_links(.)` identically -- the exact determinant telescope. Computing it on
    the U(2) side keeps a single blocking definition in the codebase and lets
    `scripts/09_verify_identities.py` check the equality rather than assume it.
    """
    return det_links(fine_links), det_links(block_links(fine_links))


def det_rung_data(name: str, fine_links: torch.Tensor, beta_u2: float):
    """Package a U(2) ensemble as `u1_2d.model.train.RungData` on its determinant sector."""
    from u1_2d.model.train import RungData

    fine, coarse = det_pair(fine_links)
    return RungData(name=name, fine=fine.float(), coarse=coarse.float(),
                    beta=model_beta(beta_u2))


def train_det_model(train_rungs, val_rungs, config):
    """Thin pass-through to `u1_2d.model.train.train_score_model`."""
    from u1_2d.model.train import train_score_model

    return train_score_model(train_rungs, val_rungs, config)


def load_det_model(path: str, device: str = "cpu"):
    """Thin pass-through to `u1_2d.model.train.load_checkpoint`."""
    from u1_2d.model.train import load_checkpoint

    return load_checkpoint(path, device=device)
