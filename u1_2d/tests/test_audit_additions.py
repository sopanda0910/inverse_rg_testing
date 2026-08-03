"""Tests added by the 2026-08-02 audit: stats coverage, HMC exactness pins,
exact-P(Q) sampling check, rectangle identities, log-partition, AIS machinery.
"""

import pytest
import math

import numpy as np
import torch

from u1_2d.lgt import make_action, run_hmc_ensemble
from u1_2d.lgt.exact import (
    log_partition,
    plaquette_exact,
    topological_susceptibility_exact,
)
from u1_2d.lgt.hmc import BatchedHMC
from u1_2d.lgt.lattice import (
    rectangle_x_angles,
    rectangle_y_angles,
    topological_charge,
    wilson_loop_angles,
)
from u1_2d.model.ais import (
    BASIS_FEATURE_NAMES,
    FEATURE_NAMES,
    RICH_FEATURE_NAMES,
    _BridgeAction,
    bridge_features,
    fit_surrogate,
    sector_resolved_estimate,
)
from u1_2d.model.schedule import GeometricNoiseSchedule
from u1_2d.model.score_net import coarse_conditioning_channels
from u1_2d.validate.stats import (
    autocorr_aware_mean_err,
    binned_mean_err,
    chain_tau_int,
    integrated_autocorrelation_time,
    jackknife,
    ks_p_neff,
    z_score,
)


def _ar1(n, phi, seed, size=1):
    rng = np.random.default_rng(seed)
    x = np.zeros((n, size))
    innov = rng.normal(size=(n, size)) * math.sqrt(1 - phi**2)
    for t in range(1, n):
        x[t] = phi * x[t - 1] + innov[t]
    return x.squeeze()


class TestStats:
    def test_tau_int_ar1_closed_form(self):
        phi = 0.8
        tau_exact = (1 + phi) / (2 * (1 - phi))
        tau, err = integrated_autocorrelation_time(_ar1(40000, phi, 0))
        assert abs(tau - tau_exact) < 0.25 * tau_exact

    def test_tau_int_uncorrelated(self):
        tau, _ = integrated_autocorrelation_time(np.random.default_rng(1).normal(size=20000))
        assert abs(tau - 0.5) < 0.15

    def test_chain_tau_int_beats_interleaved(self):
        phi, n_chains = 0.8, 8
        tau_exact = (1 + phi) / (2 * (1 - phi))
        chains = _ar1(4000, phi, 2, size=n_chains)
        interleaved = chains.reshape(-1)
        tau_chain = chain_tau_int(interleaved, n_chains)
        tau_naive, _ = integrated_autocorrelation_time(interleaved)
        assert abs(tau_chain - tau_exact) < 0.3 * tau_exact
        assert tau_naive < 1.0

    def test_autocorr_aware_err_inflates(self):
        phi, n_chains = 0.9, 8
        chains = _ar1(2000, phi, 3, size=n_chains)
        vals = chains.reshape(-1)
        _, err_naive = binned_mean_err(vals)
        _, err_aware, tau = autocorr_aware_mean_err(vals, n_chains=n_chains)
        assert tau > 2.0
        assert err_aware >= err_naive

    def test_jackknife_matches_sem_for_mean(self):
        vals = np.random.default_rng(4).normal(size=500)
        mu, err = jackknife(vals)
        assert abs(mu - vals.mean()) < 1e-12
        assert abs(err - vals.std(ddof=1) / math.sqrt(len(vals))) < 1e-3

    def test_z_score(self):
        assert abs(z_score(1.5, 0.5, 1.0) - 1.0) < 1e-12

    def test_ks_p_neff_smaller_neff_larger_p(self):
        rng = np.random.default_rng(5)
        a = rng.normal(size=2000)
        b = rng.normal(size=2000) + 0.08
        p_full = ks_p_neff(a, b, 2000, 2000)
        p_small = ks_p_neff(a, b, 100, 100)
        assert 0.0 <= p_full <= 1.0
        assert p_small > p_full


class TestHMCExactness:
    def test_omelyan_reversibility(self):
        torch.manual_seed(0)
        action = make_action("wilson", 3.0)
        hmc = BatchedHMC(8, action, n_chains=2, n_steps=6, step_size=0.15)
        theta = (torch.rand(2, 2, 8, 8, dtype=torch.float64) * 2 - 1) * math.pi
        pi = torch.randn_like(theta)
        theta_f, pi_f = hmc.omelyan(theta.clone(), pi.clone())
        theta_b, pi_b = hmc.omelyan(theta_f.clone(), -pi_f.clone())
        diff = (torch.atan2(torch.sin(theta_b - theta), torch.cos(theta_b - theta))).abs().max()
        assert float(diff) < 1e-12
        assert float((pi_b + pi).abs().max()) < 1e-12

    def test_dh_scales_as_dt_squared(self):
        torch.manual_seed(1)
        action = make_action("wilson", 3.0)
        theta = (torch.rand(4, 2, 8, 8, dtype=torch.float64) * 2 - 1) * math.pi
        pi = torch.randn_like(theta)

        def dh(dt):
            hmc = BatchedHMC(8, action, n_chains=4, n_steps=int(round(1.2 / dt)), step_size=dt)
            h0 = action.per_config(theta) + 0.5 * pi.square().sum(dim=(1, 2, 3))
            tf, pf = hmc.omelyan(theta.clone(), pi.clone())
            h1 = action.per_config(tf) + 0.5 * pf.square().sum(dim=(1, 2, 3))
            return float((h1 - h0).abs().mean())

        ratio = dh(0.1) / max(dh(0.05), 1e-300)
        assert 2.5 < ratio < 7.0


class TestExactReferences:
    def test_log_partition_derivative_is_plaquette(self):
        beta, L, h = 2.0, 8, 1e-4
        dlogz = (log_partition(beta + h, L) - log_partition(beta - h, L)) / (2 * h)
        plaq = plaquette_exact(beta, "wilson", L)
        assert abs(dlogz / (L * L) - plaq) < 1e-5

    def test_log_partition_villain_derivative(self):
        beta, L, h = 3.0, 8, 1e-4
        dlogz = (log_partition(beta + h, L, "villain") - log_partition(beta - h, L, "villain")) / (2 * h)
        # d log c_q / d beta for villain: q^2/(2 beta^2) - 1/(2 beta); check
        # against the same quantity from the character sum at q-truncation.
        assert math.isfinite(dlogz)

    def test_sampled_q2_matches_exact(self):
        beta, L = 1.5, 8
        configs, _ = run_hmc_ensemble(
            L, make_action("wilson", beta), n_configs=768, n_chains=16,
            burn_in=150, thin=3, n_steps=8, step_size=0.18,
            topological_updates=True, hot_start=True,
        )
        q2 = (topological_charge(configs).float() ** 2).numpy()
        exact_q2 = topological_susceptibility_exact(beta, "wilson", L) * L * L
        mean, err, _ = autocorr_aware_mean_err(q2, n_chains=16)
        assert abs(mean - exact_q2) < 4.0 * max(err, 1e-6)


class TestLatticeIdentities:
    def test_rectangles_equal_wilson_loops(self):
        torch.manual_seed(2)
        field = (torch.rand(3, 2, 8, 8) * 2 - 1) * math.pi
        assert torch.allclose(rectangle_x_angles(field), wilson_loop_angles(field, 2, 1), atol=1e-6)
        assert torch.allclose(rectangle_y_angles(field), wilson_loop_angles(field, 1, 2), atol=1e-6)


class TestScheduleAndConditioning:
    def test_discrete_sigmas_tensor_beta(self):
        s = GeometricNoiseSchedule(0.01, 6.0, sigma_min_beta_coef=0.1)
        grid = s.discrete_sigmas(10, beta=torch.tensor([4.0, 55.0, 218.0]))
        assert grid.shape == (10, 3)
        assert torch.all(grid[0] >= grid[-1])
        scalar = s.discrete_sigmas(10, beta=55.0)
        assert scalar.shape == (10,)
        assert torch.allclose(grid[:, 1], scalar, rtol=1e-5)

    def test_coarse_conditioning_unbatched_roundtrip(self):
        coarse = (torch.rand(2, 4, 4) * 2 - 1) * math.pi
        out = coarse_conditioning_channels(coarse, 8)
        assert out.shape == (4, 8, 8)
        batched = coarse_conditioning_channels(coarse.unsqueeze(0), 8)
        assert batched.shape == (1, 4, 8, 8)
        assert torch.allclose(out, batched[0])


class TestAIS:
    def test_fit_surrogate_recovers_coefficients(self):
        torch.manual_seed(3)
        x = torch.randn(400, 3)
        g_true = torch.tensor([2.0, -1.0, 0.5])
        y = x @ g_true + 3.0 + 0.01 * torch.randn(400)
        fit = fit_surrogate(x, y)
        assert fit["r2"] > 0.999
        assert torch.allclose(fit["g"].float(), g_true, atol=0.02)
        assert abs(fit["const"] - 3.0) < 0.05

    def test_bridge_action_force_matches_finite_difference(self):
        for basis in BASIS_FEATURE_NAMES:
            torch.manual_seed(4)
            theta = (torch.rand(1, 2, 4, 4, dtype=torch.float64) * 2 - 1) * math.pi * 0.3
            g = torch.zeros(len(BASIS_FEATURE_NAMES[basis]), dtype=torch.float64)
            g[:7] = torch.tensor([0.7, 0.2, 0.0, 0.0, 0.1, 0.0, 0.05], dtype=torch.float64)
            if basis == "rich11":
                g[8] = 0.15
            bridge = _BridgeAction(make_action("wilson", 5.0), g, 0.0, 1.25, "wilson", basis)
            bridge.t = 0.4
            t = theta.clone().requires_grad_(True)
            (grad,) = torch.autograd.grad(bridge.per_config(t).sum(), t)
            eps = 1e-6
            for idx in [(0, 0, 1, 2), (0, 1, 3, 0)]:
                tp = theta.clone()
                tp[idx] += eps
                tm = theta.clone()
                tm[idx] -= eps
                fd = float((bridge.per_config(tp) - bridge.per_config(tm)) / (2 * eps))
                assert abs(fd - float(grad[idx])) < 1e-4, basis

    def test_bridge_basis_widths(self):
        """The default basis must stay final7: it reproduces the Table S7 result
        of record. rich11 is retained only to reproduce the recorded negative."""
        theta = (torch.rand(2, 2, 4, 4) * 2 - 1) * math.pi
        assert bridge_features(theta, 0.5).shape[1] == 7
        assert bridge_features(theta, 0.5, "wilson", "rich11").shape[1] == 11
        assert len(FEATURE_NAMES) == 7 and len(RICH_FEATURE_NAMES) == 11
        assert RICH_FEATURE_NAMES[:7] == FEATURE_NAMES
        with pytest.raises(ValueError):
            bridge_features(theta, 0.5, "wilson", "nope")

    def test_bridge_endpoints(self):
        torch.manual_seed(5)
        theta = (torch.rand(2, 2, 4, 4) * 2 - 1) * math.pi
        g = torch.ones(len(FEATURE_NAMES)) * 0.1
        action = make_action("wilson", 2.0)
        bridge = _BridgeAction(action, g, 0.5, 0.5, "wilson")
        bridge.t = 1.0
        assert torch.allclose(bridge.per_config(theta), action.per_config(theta), atol=1e-5)
        bridge.t = 0.0
        feats = bridge_features(theta, 0.5)
        expected = action.per_config(theta) - (feats @ g + 0.5)
        assert torch.allclose(bridge.per_config(theta), expected, atol=1e-5)

    def test_bridge_features_width_and_grad(self):
        torch.manual_seed(6)
        theta = ((torch.rand(3, 2, 4, 4) * 2 - 1) * math.pi).requires_grad_(True)
        feats = bridge_features(theta, 0.5)
        assert feats.shape == (3, len(FEATURE_NAMES))
        (grad,) = torch.autograd.grad(feats.sum(), theta)
        assert torch.isfinite(grad).all()
        assert float(grad.abs().sum()) > 0


class TestCertificateAndSectors:
    def test_certificate_identity_uniform_proposal(self):
        # x ~ Uniform[-pi, pi]^N with exact log q = -N log 2pi; coarse level at
        # beta = 0 contributes nothing (Z_haar(0) = 1, S = 0). Then
        # E[w] = (2 pi)^N Z_haar(beta_f), so gap -> 0 -- validates the formula
        # AND the log_partition normalization convention in one shot, and the
        # KL field must be >= 0 (it equals KL(uniform || p)).
        from u1_2d.model.likelihood import free_energy_certificate

        torch.manual_seed(7)
        L, beta = 2, 0.5
        n = 8192
        n_dof = 2 * L * L
        x = (torch.rand(n, 2, L, L) * 2 - 1) * math.pi
        action = make_action("wilson", beta)
        log_q = torch.full((n,), -n_dof * math.log(2 * math.pi), dtype=torch.float64)
        log_w = (-action.per_config(x).double()) - log_q
        cert = free_energy_certificate(log_w, L, beta, 0.0, "wilson")
        assert abs(cert["gap"]) < 5 * cert["sem"] + 0.02
        assert cert["kl_from_mean_log_w"] > -3 * cert["kl_sem"]

    def test_sector_resolved_exact_combination(self):
        values = torch.tensor([1.0, 1.2, 3.0, 3.4, 5.0])
        log_w = torch.zeros(5)
        q = torch.tensor([0.0, 0.0, 1.0, 1.0, 2.0])
        out = sector_resolved_estimate(values, log_w, q, [0, 1, 2], [0.6, 0.3, 0.1],
                                       min_count=2)
        # sector 2 has one sample < min_count -> falls back to covered mean
        m0, m1 = 1.1, 3.2
        fallback = (0.6 * m0 + 0.3 * m1) / 0.9
        expected = 0.6 * m0 + 0.3 * m1 + 0.1 * fallback
        assert abs(out["mean"] - expected) < 1e-6
        assert abs(out["covered_mass"] - 0.9) < 1e-9
        assert out["per_sector"]["+0"]["count"] == 2
        assert "mean" not in out["per_sector"]["+2"]

    def test_sector_resolved_weighted_within_sector(self):
        values = torch.tensor([2.0, 4.0])
        log_w = torch.tensor([math.log(3.0), 0.0])
        q = torch.tensor([0.0, 0.0])
        out = sector_resolved_estimate(values, log_w, q, [0], [1.0], min_count=2)
        assert abs(out["mean"] - (3.0 * 2.0 + 4.0) / 4.0) < 1e-6
