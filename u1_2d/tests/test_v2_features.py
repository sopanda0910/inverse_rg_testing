"""Tests for the v2 additions: symmetry augmentation, biased sigma sampling,
channel norm / coarse FiLM, ODE likelihood, ESS, and checkpoint roundtrip."""

import math

import pytest
import torch

from u1_2d.lgt.blocking import block_links
from u1_2d.lgt.lattice import gauge_transform, plaquette_angles, topological_charge
from u1_2d.model.likelihood import importance_ess, ode_log_likelihood
from u1_2d.model.schedule import GeometricNoiseSchedule
from u1_2d.model.score_net import ChannelNorm, GaugeCovariantScoreNet, coarse_conditioning_channels
from u1_2d.model.symmetry import charge_conjugate, random_symmetry, reflect_x, rotate90
from u1_2d.model.train import RungData, TrainConfig, save_checkpoint, load_checkpoint, train_score_model
from u1_2d.model.wrapped import wrap, wrapped_normal_score


def random_field(batch=4, size=8, scale=0.7, seed=0):
    torch.manual_seed(seed)
    return wrap(scale * (torch.rand(batch, 2, size, size) * 2 * math.pi - math.pi))


class TestSymmetry:
    def test_action_invariance(self):
        f = random_field()
        s0 = torch.cos(plaquette_angles(f)).sum(dim=(-2, -1))
        for transform in (rotate90, reflect_x, charge_conjugate):
            s1 = torch.cos(plaquette_angles(transform(f))).sum(dim=(-2, -1))
            assert torch.allclose(s0, s1, atol=1e-5), transform.__name__

    def test_charge_mapping(self):
        f = random_field(seed=3)
        q = topological_charge(f)
        assert torch.equal(topological_charge(rotate90(f)), q)
        assert torch.equal(topological_charge(reflect_x(f)), -q)
        assert torch.equal(topological_charge(charge_conjugate(f)), -q)

    def test_group_relations(self):
        f = random_field(seed=1)
        g = f
        for _ in range(4):
            g = rotate90(g)
        assert torch.allclose(g, f, atol=1e-6)
        assert torch.allclose(reflect_x(reflect_x(f)), f, atol=1e-6)

    def test_random_symmetry_preserves_action(self):
        f = random_field(seed=2)
        s0 = torch.cos(plaquette_angles(f)).sum(dim=(-2, -1))
        gen = torch.Generator().manual_seed(11)
        for _ in range(5):
            g = random_symmetry(f, generator=gen)
            s1 = torch.cos(plaquette_angles(g)).sum(dim=(-2, -1))
            assert torch.allclose(s0, s1, atol=1e-5)

    def test_blocking_after_transform_valid_pair(self):
        # Blocking preserves Q only up to plaquette wrap events, so use a smooth
        # field (physical-coupling regime) where wraps cannot occur.
        f = random_field(batch=2, size=8, scale=0.2, seed=4)
        g = rotate90(f)
        coarse = block_links(g)
        assert coarse.shape == (2, 2, 4, 4)
        assert torch.equal(topological_charge(coarse), topological_charge(g))


class TestSigmaBias:
    def test_high_beta_bias_shrinks_sigma(self):
        schedule = GeometricNoiseSchedule(0.03, 6.0)
        torch.manual_seed(0)
        plain = schedule.sample_sigma(4000, "cpu", beta=100.0)
        torch.manual_seed(0)
        biased = schedule.sample_sigma(4000, "cpu", beta=100.0, high_beta_bias=0.5)
        assert biased.median() < plain.median()

    def test_bias_negligible_at_small_beta(self):
        schedule = GeometricNoiseSchedule(0.03, 6.0)
        torch.manual_seed(0)
        plain = schedule.sample_sigma(4000, "cpu", beta=1.0)
        torch.manual_seed(0)
        biased = schedule.sample_sigma(4000, "cpu", beta=1.0, high_beta_bias=0.5)
        ratio = math.log(float(biased.log().mean().exp())) / math.log(float(plain.log().mean().exp()))
        assert 0.5 < ratio < 2.0


class TestModelVariants:
    def test_channel_norm_is_per_site(self):
        norm = ChannelNorm(16)
        x = torch.randn(2, 16, 8, 8)
        y_full = norm(x)
        y_patch = norm(x[:, :, :4, :4])
        assert torch.allclose(y_full[:, :, :4, :4], y_patch, atol=1e-6)

    def test_channel_norm_model_gauge_invariant(self):
        model = GaugeCovariantScoreNet(hidden=16, depth=2, cond_channels=4,
                                       norm_type="channel", cond_film=True)
        for p in model.parameters():
            torch.nn.init.normal_(p, std=0.05)
        theta = random_field(batch=2, size=8, seed=5)
        cond = coarse_conditioning_channels(block_links(theta), 8)
        sigma = torch.full((2,), 0.5)
        beta = torch.full((2,), 4.0)
        out = model(theta, sigma, beta, cond)
        phases = torch.randn(2, 8, 8)
        theta_g = gauge_transform(theta, phases)
        out_g = model(theta_g, sigma, beta, cond)
        assert torch.allclose(out, out_g, atol=1e-4)

    def test_model_runs_at_different_sizes(self):
        model = GaugeCovariantScoreNet(hidden=16, depth=2, cond_channels=4,
                                       norm_type="channel")
        for size in (8, 16):
            theta = random_field(batch=2, size=size, seed=6)
            cond = coarse_conditioning_channels(block_links(theta), size)
            out = model(theta, torch.full((2,), 1.0), torch.full((2,), 4.0), cond)
            assert out.shape == theta.shape
            assert torch.isfinite(out).all()

    def test_checkpoint_roundtrip_new_kwargs(self, tmp_path):
        cfg = TrainConfig(hidden=16, depth=2, cond_channels=5,
                          norm_type="channel", cond_film=True)
        model = GaugeCovariantScoreNet(hidden=16, depth=2, cond_channels=5,
                                       norm_type="channel", cond_film=True)
        path = str(tmp_path / "ckpt.pt")
        save_checkpoint(model.state_dict(), cfg, path)
        loaded, schedule = load_checkpoint(path)
        assert loaded.norm_type == "channel"
        assert loaded.cond_film is True
        theta = random_field(batch=2, size=8, seed=7)
        cond = coarse_conditioning_channels(block_links(theta), 8, n_channels=5)
        out = loaded(theta, torch.full((2,), 1.0), torch.full((2,), 4.0), cond)
        assert torch.isfinite(out).all()


class TestLikelihood:
    def test_ode_likelihood_matches_wrapped_gaussian(self):
        torch.manual_seed(1)
        s0 = 0.4
        x0 = wrap(s0 * torch.randn(4, 2, 4, 4))

        def score_fn(theta, sigma):
            width = torch.sqrt(torch.as_tensor(s0**2) + sigma**2)
            return wrapped_normal_score(theta, width)

        sigmas = torch.exp(torch.linspace(math.log(0.01), math.log(6.0), 100))
        logq = ode_log_likelihood(score_fn, x0, sigmas, n_probes=4, seed=0)

        def wrapped_logpdf(x, s):
            ks = torch.arange(-8, 9).view(-1, 1)
            vals = torch.exp(-(x.flatten()[None, :] + 2 * math.pi * ks) ** 2 / (2 * s**2))
            return torch.log(vals.sum(0) / (s * math.sqrt(2 * math.pi)))

        width0 = math.sqrt(s0**2 + 0.01**2)
        exact = torch.stack([wrapped_logpdf(x0[i], width0).sum() for i in range(4)])
        assert torch.allclose(logq, exact, atol=0.15)

    def test_perfect_proposal_gives_unit_ess(self):
        from u1_2d.lgt.actions import make_action

        fine = random_field(batch=16, size=8, seed=9)
        action = make_action("wilson", 2.0)
        log_q = -action.per_config(fine)
        diag = importance_ess(fine, log_q, 2.0, "wilson")
        assert diag["ess_per_n"] > 0.999
        assert diag["log_weight_std"] < 1e-5


class TestTrainingLoop:
    def test_train_with_augment_and_bias_runs(self, tmp_path):
        torch.manual_seed(0)
        fine = random_field(batch=24, size=8, seed=10)
        rung = RungData("t", fine, block_links(fine), 2.0)
        val = RungData("t", fine[:4], block_links(fine[:4]), 2.0)
        cfg = TrainConfig(
            epochs=1, batch_size=8, hidden=16, depth=2, cond_channels=4,
            sym_augment=1.0, high_beta_sigma_bias=0.3, norm_type="channel",
            cond_film=True, sigma_min_beta_coef=0.3,
            checkpoint_path=str(tmp_path / "ck.pt"),
        )
        model, history = train_score_model([rung], [val], cfg)
        assert len(history) == 1
        assert math.isfinite(history[0]["train_loss"])


class TestSectorFixes:
    def test_conjugate_symmetrize_preserves_action(self):
        from u1_2d.pipeline.ladder import conjugate_symmetrize

        f = random_field(batch=32, size=8, seed=20)
        gen = torch.Generator().manual_seed(3)
        g = conjugate_symmetrize(f, generator=gen)
        s0 = torch.sort(torch.cos(plaquette_angles(f)).sum(dim=(-2, -1))).values
        s1 = torch.sort(torch.cos(plaquette_angles(g)).sum(dim=(-2, -1))).values
        assert torch.allclose(s0, s1, atol=1e-5)
        q0, q1 = topological_charge(f), topological_charge(g)
        assert torch.equal(q0.abs(), q1.abs())
        assert not torch.equal(q0, q1)

    def test_resample_exact_sectors_hits_targets(self):
        from u1_2d.pipeline.ladder import resample_exact_sectors
        from u1_2d.lgt.exact import topological_charge_distribution

        f = random_field(batch=64, size=8, scale=0.3, seed=21)
        gen = torch.Generator().manual_seed(5)
        beta = 2.0
        g = resample_exact_sectors(f, beta, "wilson", generator=gen)
        q = topological_charge(g)
        q_values, probs = topological_charge_distribution(beta, 8)
        exact_q2 = float((q_values.astype(float) ** 2 * probs).sum())
        got_q2 = float(q.square().mean())
        # 64 draws from exact P(Q): mean Q^2 within ~4 sigma of exact
        var = float(((q_values.astype(float) ** 2 - exact_q2) ** 2 * probs).sum())
        assert abs(got_q2 - exact_q2) < 4.0 * (var / 64) ** 0.5 + 1e-6
