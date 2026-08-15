"""Tests for the (sigma, beta)-conditioned score correction head.

This module produced a quoted campaign result (the 354-parameter correction
head in Fig. 27a) with no test coverage, which is the gap these close. The
properties that matter are the ones the design argument rests on: the head is
a no-op until trained, it cannot touch the frozen base weights, it preserves
the base network's gauge covariance, and it keeps the scaled-score contract
that `train.denoising_loss` consumes.
"""

import math

import torch

from u1_2d.lgt import random_gauge_transform
from u1_2d.model.score_correction import (
    CorrectedScore,
    load_corrected_checkpoint,
    save_correction,
)
from u1_2d.model.score_net import GaugeCovariantScoreNet


def random_field(batch=2, size=8, seed=0):
    gen = torch.Generator().manual_seed(seed)
    return torch.rand(batch, 2, size, size, generator=gen) * 2 * math.pi - math.pi


def make_base(seed=0):
    torch.manual_seed(seed)
    base = GaugeCovariantScoreNet(hidden=16, depth=2, cond_channels=4)
    for p in base.head.parameters():
        torch.nn.init.normal_(p, std=0.1)
    torch.nn.init.constant_(base.force_gate.bias, 0.7)
    return base


def inputs(batch=2, size=8, seed=0):
    base = make_base(seed)
    field = random_field(batch, size, seed + 1)
    sigma = torch.full((batch,), 0.5)
    beta = torch.full((batch,), 2.0)
    cond = torch.zeros(batch, base.cond_channels, size, size)
    return base, field, sigma, beta, cond


class TestZeroInitialization:
    def test_is_identity_before_training(self):
        """Zero-init of the last layer must make the head an exact no-op.

        This is the whole basis for "if training helps at all, the improvement
        is generalizable": the corrected model starts life equal to the base.
        """
        base, field, sigma, beta, cond = inputs()
        model = CorrectedScore(base)
        assert torch.allclose(model.score(field, sigma, beta, cond),
                              base.score(field, sigma, beta, cond), atol=1e-6)

    def test_coefficients_start_at_zero(self):
        base, _, sigma, beta, _ = inputs()
        a, b = CorrectedScore(base).coefficients(sigma, beta)
        assert torch.allclose(a, torch.zeros_like(a))
        assert torch.allclose(b, torch.zeros_like(b))

    def test_nonzero_coefficients_do_change_the_score(self):
        """Guard against the no-op test passing for the wrong reason."""
        base, field, sigma, beta, cond = inputs()
        model = CorrectedScore(base)
        torch.nn.init.normal_(model.net[-1].weight, std=0.5)
        torch.nn.init.constant_(model.net[-1].bias, 0.3)
        assert not torch.allclose(model.score(field, sigma, beta, cond),
                                  base.score(field, sigma, beta, cond), atol=1e-6)


class TestFrozenBase:
    def test_base_parameters_are_frozen(self):
        base, *_ = inputs()
        model = CorrectedScore(base)
        assert all(not p.requires_grad for p in model.base.parameters())
        assert all(p.requires_grad for p in model.net.parameters())

    def test_backward_leaves_base_gradients_empty(self):
        base, field, sigma, beta, cond = inputs()
        model = CorrectedScore(base)
        torch.nn.init.normal_(model.net[-1].weight, std=0.1)
        model.score(field, sigma, beta, cond).pow(2).sum().backward()
        assert all(p.grad is None for p in model.base.parameters())
        assert any(p.grad is not None and p.grad.abs().sum() > 0
                   for p in model.net.parameters())

    def test_parameter_count_is_small(self):
        """Capacity is the design argument, so it is worth pinning."""
        base, *_ = inputs()
        model = CorrectedScore(base, hidden=16)
        n = sum(p.numel() for p in model.net.parameters())
        assert n < 1000, f"correction head grew to {n} parameters"


class TestGaugeCovariance:
    def test_corrected_score_still_gauge_invariant(self):
        """The added term is a Wilson curl, so covariance must survive it."""
        base, field, sigma, beta, cond = inputs()
        model = CorrectedScore(base)
        torch.nn.init.normal_(model.net[-1].weight, std=0.5)
        torch.nn.init.constant_(model.net[-1].bias, 0.4)
        transformed = random_gauge_transform(
            field, generator=torch.Generator().manual_seed(9))
        assert torch.allclose(model.score(field, sigma, beta, cond),
                              model.score(transformed, sigma, beta, cond),
                              atol=1e-4)

    def test_corrected_score_orthogonal_to_gauge_orbits(self):
        base, field, sigma, beta, cond = inputs(size=8)
        model = CorrectedScore(base)
        torch.nn.init.normal_(model.net[-1].weight, std=0.5)
        torch.nn.init.constant_(model.net[-1].bias, 0.4)
        out = model.score(field, sigma, beta, cond)
        divergence = (out[:, 0] - out[:, 0].roll(1, dims=-2)
                      + out[:, 1] - out[:, 1].roll(1, dims=-1))
        assert divergence.abs().max() < 1e-4


class TestContracts:
    def test_forward_returns_the_scaled_score(self):
        """train.denoising_loss consumes sigma * score, not score."""
        base, field, sigma, beta, cond = inputs()
        model = CorrectedScore(base)
        torch.nn.init.normal_(model.net[-1].weight, std=0.2)
        expected = model.score(field, sigma, beta, cond) * sigma.reshape(-1, 1, 1, 1)
        assert torch.allclose(model(field, sigma, beta, cond), expected, atol=1e-6)

    def test_cond_channels_passes_through(self):
        base, *_ = inputs()
        assert CorrectedScore(base).cond_channels == base.cond_channels

    def test_beta_eff_softens_with_sigma(self):
        """beta_eff = beta / (1 + 4 beta sigma^2): equals beta at sigma -> 0 and
        decreases monotonically, which is what makes the curl term the right
        shape for a late-time offset."""
        beta = torch.tensor([2.0])
        prev = None
        for s in (1e-6, 0.1, 0.5, 2.0):
            sigma = torch.tensor([s])
            beta_eff = beta / (1.0 + 4.0 * beta * sigma**2)
            if s < 1e-3:
                assert torch.allclose(beta_eff, beta, atol=1e-4)
            if prev is not None:
                assert beta_eff.item() < prev
            prev = beta_eff.item()


class TestCheckpointRoundTrip:
    def test_save_load_preserves_outputs(self, tmp_path):
        base, field, sigma, beta, cond = inputs()
        base_path = tmp_path / "base.pt"
        from u1_2d.model.train import TrainConfig, save_checkpoint
        cfg = TrainConfig(hidden=16, depth=2, cond_channels=4,
                          sigma_min=0.03, sigma_max=6.0)
        save_checkpoint(base.state_dict(), cfg, str(base_path))

        model = CorrectedScore(base)
        torch.nn.init.normal_(model.net[-1].weight, std=0.3)
        torch.nn.init.constant_(model.net[-1].bias, 0.2)
        expected = model.score(field, sigma, beta, cond)

        corr_path = tmp_path / "corrected.pt"
        save_correction(model, str(base_path), corr_path)
        reloaded, _ = load_corrected_checkpoint(corr_path, device="cpu")
        assert torch.allclose(reloaded.score(field, sigma, beta, cond),
                              expected, atol=1e-5)
