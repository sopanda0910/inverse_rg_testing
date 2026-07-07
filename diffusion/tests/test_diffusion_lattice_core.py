import math

import numpy as np
import pytest
import torch

from diffusion.lgt import (
    WilsonAction,
    VillainAction,
    run_hmc_ensemble,
    block_links,
    random_gauge_transform,
    topological_charge_float,
    wrap,
)
from diffusion.lgt.lattice import plaquette_angles, mean_plaquette, wilson_loop_angles
from diffusion.lgt.blocking import blocked_plaquette_from_fine, match_coarse_beta
from diffusion.lgt.local_updates import (
    heatbath_sweep,
    overrelaxation_sweep,
    metropolis_sweep,
    topological_update,
    instanton_field,
)
from diffusion.lgt import exact


def random_field(batch=4, size=8, seed=0):
    gen = torch.Generator().manual_seed(seed)
    return torch.rand(batch, 2, size, size, generator=gen) * 2 * math.pi - math.pi


class TestExactFormulas:
    def test_infinite_volume_matches_bessel_ratio(self):
        from scipy.special import iv

        for beta in (0.5, 2.0, 8.0):
            assert exact.plaquette_exact(beta) == pytest.approx(iv(1, beta) / iv(0, beta), rel=1e-10)

    def test_villain_plaquette_closed_form(self):
        for beta in (0.5, 1.0, 4.0):
            assert exact.plaquette_exact(beta, "villain") == pytest.approx(
                math.exp(-1.0 / (2.0 * beta)), rel=1e-6
            )

    def test_finite_volume_converges_to_infinite(self):
        assert exact.plaquette_exact(2.0, "wilson", 64) == pytest.approx(
            exact.plaquette_exact(2.0), abs=1e-9
        )

    def test_wilson_loop_area_law(self):
        beta = 2.0
        r1 = exact.plaquette_exact(beta)
        assert exact.wilson_loop_exact(beta, 6) == pytest.approx(r1**6, rel=1e-10)

    def test_topological_distribution_normalized_and_consistent(self):
        q_values, probs = exact.topological_charge_distribution(2.0, 16)
        assert probs.sum() == pytest.approx(1.0, abs=1e-8)
        chi_finite = exact.topological_susceptibility_exact(2.0, "wilson", 64)
        chi_infinite = exact.topological_susceptibility_exact(2.0)
        assert chi_finite == pytest.approx(chi_infinite, rel=2e-3)

    def test_infinite_volume_susceptibility_matches_parent_module(self):
        from inverserg.measurements import topological_susceptibility_theory

        assert exact.topological_susceptibility_exact(3.0) == pytest.approx(
            topological_susceptibility_theory(3.0), rel=1e-8
        )


class TestHMC:
    @pytest.mark.parametrize("beta", [0.5, 1.0, 2.0])
    def test_reproduces_exact_plaquette(self, beta):
        torch.manual_seed(11)
        configs, stats = run_hmc_ensemble(
            8, WilsonAction(beta), n_configs=240, n_chains=12, burn_in=120, thin=3,
            topological_updates=True, hot_start=True,
        )
        plaq = torch.cos(plaquette_angles(configs)).mean(dim=(-2, -1)).numpy()
        err = plaq.std() / math.sqrt(len(plaq) / 4)
        reference = exact.plaquette_exact(beta, "wilson", 8)
        assert abs(plaq.mean() - reference) < max(4 * err, 0.01)
        assert stats.acceptance_rate > 0.6

    def test_topological_charge_is_integer(self):
        torch.manual_seed(3)
        configs, _ = run_hmc_ensemble(8, WilsonAction(1.0), n_configs=40, n_chains=8, burn_in=40, thin=2)
        q_float = topological_charge_float(configs)
        assert torch.allclose(q_float, q_float.round(), atol=1e-4)


class TestGaugeInvariance:
    def test_observables_invariant(self):
        field = random_field()
        transformed = random_gauge_transform(field, generator=torch.Generator().manual_seed(5))
        assert torch.allclose(
            plaquette_angles(field), plaquette_angles(transformed), atol=1e-5
        )
        assert torch.allclose(
            wilson_loop_angles(field, 2, 2), wilson_loop_angles(transformed, 2, 2), atol=1e-4
        )
        assert torch.allclose(
            topological_charge_float(field), topological_charge_float(transformed), atol=1e-3
        )


class TestBlocking:
    def test_coarse_plaquette_is_sum_of_fine_cell(self):
        field = random_field(batch=3, size=12)
        direct = plaquette_angles(block_links(field))
        telescoped = blocked_plaquette_from_fine(field)
        assert torch.allclose(wrap(direct - telescoped), torch.zeros_like(direct), atol=1e-4)

    def test_blocked_villain_matches_direct_quarter_beta(self):
        torch.manual_seed(21)
        beta = 4.0
        action = VillainAction(beta)
        field = torch.rand(48, 2, 16, 16) * 2 * math.pi - math.pi
        with torch.no_grad():
            for _ in range(250):
                field = metropolis_sweep(field, action)
                field = overrelaxation_sweep(field)
                field, _ = topological_update(field, action)
            values = []
            for _ in range(150):
                field = metropolis_sweep(field, action)
                field = overrelaxation_sweep(field)
                field, _ = topological_update(field, action)
                values.append(float(mean_plaquette(block_links(field))))
        values = np.array(values)
        err = values.std() / math.sqrt(len(values) / 6)
        reference = exact.plaquette_exact(beta / 4.0, "villain", 8)
        assert abs(values.mean() - reference) < max(4 * err, 0.01)

    def test_beta_matching_recovers_direct_wilson(self):
        torch.manual_seed(31)
        beta = 4.0
        configs, _ = run_hmc_ensemble(
            16, WilsonAction(beta), n_configs=200, n_chains=10, burn_in=150, thin=4,
            topological_updates=True, hot_start=True,
        )
        matched = match_coarse_beta(block_links(configs))
        expected = 1.3555
        assert matched == pytest.approx(expected, abs=0.12)


class TestLocalUpdates:
    def test_overrelaxation_preserves_action(self):
        field = random_field(batch=2, size=10, seed=7).double()
        for action in (WilsonAction(2.0), VillainAction(3.0)):
            before = action.per_config(field)
            after = action.per_config(overrelaxation_sweep(field))
            assert torch.allclose(before, after, rtol=1e-10, atol=1e-8)

    def test_heatbath_reaches_exact_plaquette(self):
        torch.manual_seed(13)
        beta = 2.0
        field = torch.zeros(64, 2, 12, 12)
        with torch.no_grad():
            for _ in range(80):
                field = heatbath_sweep(field, beta)
                field = overrelaxation_sweep(field)
            values = []
            for _ in range(60):
                field = heatbath_sweep(field, beta)
                field = overrelaxation_sweep(field)
                values.append(float(mean_plaquette(field)))
        values = np.array(values)
        err = values.std() / math.sqrt(len(values) / 5)
        assert abs(values.mean() - exact.plaquette_exact(beta, "wilson", 12)) < max(4 * err, 0.008)

    def test_instanton_field_has_unit_charge(self):
        inst = instanton_field(8)
        plaq = plaquette_angles(inst)
        assert torch.allclose(plaq, torch.full_like(plaq, 2 * math.pi / 64), atol=1e-4)
        assert float(topological_charge_float(inst)) == pytest.approx(1.0, abs=1e-4)
