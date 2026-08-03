"""Tests for probability-flow ODE sampling with likelihood and the
reweighting / independence-Metropolis exactness utilities."""

import math

import torch

from u1_2d.model.likelihood import (
    _ess_from_log_weights,
    conditional_ode_sample,
    independence_metropolis,
    ode_log_likelihood,
    ode_sample_with_likelihood,
    reweighted_mean,
    snis_log_weights,
)
from u1_2d.model.schedule import GeometricNoiseSchedule
from u1_2d.model.score_net import GaugeCovariantScoreNet
from u1_2d.model.wrapped import wrapped_normal_log_density, wrapped_normal_score


class TestOdeSampleWithLikelihood:
    def test_zero_score_gives_uniform_prior_density(self):
        def score_fn(theta, sigma):
            return theta * 0.0

        sigmas = GeometricNoiseSchedule(0.05, 6.0).discrete_sigmas(30)
        x, log_q = ode_sample_with_likelihood(score_fn, (8, 2, 4, 4), sigmas, n_probes=1, seed=0)
        n_dof = 2 * 4 * 4
        expected = -n_dof * math.log(2.0 * math.pi)
        assert torch.allclose(log_q, torch.full_like(log_q, expected), atol=1e-5)
        assert float(x.abs().max()) <= math.pi + 1e-6

    def test_wrapped_gaussian_target_high_ess_and_roundtrip(self):
        # Target: iid wrapped N(0, s0) per angle. The noised marginal at level
        # sigma is exactly wrapped N(0, sqrt(s0^2 + sigma^2)), so this score is
        # the TRUE marginal score and the only errors are Heun discretization
        # and the (exact, n_probes=0) divergence -- an end-to-end validity test
        # of sample density and weights.
        s0 = 0.8

        def score_fn(theta, sigma):
            width = torch.sqrt(torch.as_tensor(s0) ** 2 + sigma**2)
            return wrapped_normal_score(theta, width)

        schedule = GeometricNoiseSchedule(0.02, 6.0)
        sigmas_desc = schedule.discrete_sigmas(80)
        x, log_q = ode_sample_with_likelihood(
            score_fn, (32, 2, 4, 4), sigmas_desc, n_probes=0, seed=1
        )

        width_end = math.sqrt(s0**2 + schedule.sigma_min**2)
        log_p = wrapped_normal_log_density(x, torch.tensor(width_end)).sum(dim=(1, 2, 3))
        ess, _, _ = _ess_from_log_weights(log_p - log_q)
        assert ess > 0.5

        log_q_eval = ode_log_likelihood(
            score_fn, x, torch.flip(sigmas_desc, dims=[0]), n_probes=0
        )
        assert float((log_q - log_q_eval).abs().max()) < 1.0

    def test_conditional_ode_sample_shapes_and_finiteness(self):
        torch.manual_seed(0)
        model = GaugeCovariantScoreNet(hidden=8, depth=1, cond_channels=4)
        schedule = GeometricNoiseSchedule(0.05, 6.0)
        coarse = torch.rand(3, 2, 4, 4) * 2 * math.pi - math.pi
        fine, log_q = conditional_ode_sample(
            model, schedule, coarse, beta_target=2.0,
            n_steps=6, n_probes=1, batch_size=2, seed=3,
        )
        assert fine.shape == (3, 2, 8, 8)
        assert log_q.shape == (3,)
        assert torch.isfinite(log_q).all()
        log_w = snis_log_weights(fine, log_q, 2.0, coarse=coarse, coarse_beta_matched=0.5)
        assert log_w.shape == (3,)
        assert torch.isfinite(log_w).all()


class TestReweighting:
    def test_reweighted_mean_recovers_target(self):
        # Proposal N-ish sample with known log-weights toward a subset: the
        # weighted mean must match the direct weighted average.
        values = torch.tensor([1.0, 2.0, 3.0, 4.0])
        log_w = torch.log(torch.tensor([1.0, 1.0, 2.0, 4.0]))
        mu, err = reweighted_mean(values, log_w)
        expected = float((values * torch.tensor([1.0, 1.0, 2.0, 4.0])).sum() / 8.0)
        assert abs(mu - expected) < 1e-6
        assert err > 0

    def test_reweighted_mean_uniform_weights_is_plain_mean(self):
        values = torch.arange(10.0)
        mu, _ = reweighted_mean(values, torch.zeros(10))
        assert abs(mu - 4.5) < 1e-6


class TestIndependenceMetropolis:
    def test_uniform_weights_accept_everything(self):
        idx, acc = independence_metropolis(torch.zeros(50), seed=0)
        assert acc == 1.0
        assert torch.equal(idx, torch.arange(50))

    def test_dominant_weight_absorbs_chain(self):
        log_w = torch.full((40,), -30.0)
        log_w[7] = 0.0
        idx, _ = independence_metropolis(log_w, seed=0)
        assert (idx[8:] == 7).all()

    def test_stationary_distribution_matches_weights(self):
        # Two-state weights 3:1 -- long-chain occupancy must approach 3/4.
        torch.manual_seed(0)
        n = 20000
        heavy = torch.rand(n) < 0.5
        log_w = torch.where(heavy, torch.tensor(math.log(3.0)), torch.tensor(0.0))
        idx, _ = independence_metropolis(log_w, seed=1)
        frac_heavy = float(heavy[idx].float().mean())
        assert abs(frac_heavy - 0.75) < 0.02
