"""Tiny (sigma, beta)-conditioned physics-form score correction.

The measured density gap is a nearly uniform per-site log-weight spread
(0.02-0.07 nats/site across the (L, beta) plane) -- the signature of a small
COHERENT drift offset, and a uniform per-plaquette offset is exactly a
Wilson-curl direction. This module corrects the frozen base score with two
scalar functions of (sigma, beta):

    s_eff = (1 + a(sigma, beta)) * s_base
            + b(sigma, beta) * wilson_exact_score(theta, beta_eff),
    beta_eff = beta / (1 + 4 beta sigma^2),

a, b from a ~600-parameter zero-initialized MLP. Capacity is matched to the
error structure on purpose: two smooth scalar fields over (sigma, beta) can
neither memorize configurations nor fit case idiosyncrasies -- if training
helps at all, the improvement is generalizable by construction (the
anti-overfitting counterpart of the failed 724k-parameter scale-up). The
wrapper exposes the base network's `score` signature and `cond_channels`, so
every downstream consumer (likelihood, samplers, scripts 19/22/24) works
unchanged.
"""

import math

import torch
from torch import nn


class CorrectedScore(nn.Module):
    def __init__(self, base: nn.Module, hidden: int = 16) -> None:
        super().__init__()
        self.base = base
        for p in self.base.parameters():
            p.requires_grad_(False)
        self.net = nn.Sequential(
            nn.Linear(2, hidden), nn.SiLU(),
            nn.Linear(hidden, hidden), nn.SiLU(),
            nn.Linear(hidden, 2),
        )
        nn.init.zeros_(self.net[-1].weight)
        nn.init.zeros_(self.net[-1].bias)

    @property
    def cond_channels(self) -> int:
        return getattr(self.base, "cond_channels", 4)

    def coefficients(self, sigma: torch.Tensor, beta: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        feats = torch.stack([torch.log(sigma.clamp_min(1e-6)),
                             torch.log(beta.clamp_min(1e-6)) / 4.0], dim=-1)
        out = self.net(feats)
        return out[..., 0], out[..., 1]

    def score(self, theta: torch.Tensor, sigma: torch.Tensor, beta: torch.Tensor,
              cond: torch.Tensor) -> torch.Tensor:
        from ..pipeline.ladder import wilson_exact_score

        s = self.base.score(theta, sigma, beta, cond)
        a, b = self.coefficients(sigma, beta)
        beta_eff = beta / (1.0 + 4.0 * beta * sigma**2)
        curl = wilson_exact_score(theta, beta_eff.view(-1, 1, 1))
        return (1.0 + a.view(-1, 1, 1, 1)) * s + b.view(-1, 1, 1, 1) * curl

    def forward(self, theta: torch.Tensor, sigma: torch.Tensor, beta: torch.Tensor,
                cond: torch.Tensor) -> torch.Tensor:
        # Drop-in for GaugeCovariantScoreNet.forward, whose contract is the
        # SCALED score (~ sigma * score) -- what train.denoising_loss consumes.
        sigma_b = sigma.reshape(-1, 1, 1, 1) if sigma.dim() > 0 else sigma
        return self.score(theta, sigma, beta, cond) * sigma_b


def save_correction(model: CorrectedScore, base_checkpoint: str, path) -> None:
    torch.save({
        "correction_state": model.net.state_dict(),
        "base_checkpoint": str(base_checkpoint),
        "hidden": model.net[0].out_features,
    }, path)


def load_corrected_checkpoint(path, device: str = "cpu"):
    """Returns (CorrectedScore, schedule) -- drop-in for train.load_checkpoint."""
    from .train import load_checkpoint

    payload = torch.load(path, map_location=device, weights_only=True)
    base, schedule = load_checkpoint(payload["base_checkpoint"], device)
    model = CorrectedScore(base, hidden=payload["hidden"])
    model.net.load_state_dict(payload["correction_state"])
    model.to(device).eval()
    return model, schedule
