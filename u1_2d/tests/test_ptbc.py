"""Correctness of the PTBC / open-boundary machinery.

The swap acceptance is the part that can be wrong silently: a mis-derived dS
still produces a running chain and plausible-looking topology, while biasing
the physical replica. It is therefore checked against the actions themselves
rather than against its own algebra.
"""

import math

import pytest
import torch

from u1_2d.lgt.actions import WilsonAction
from u1_2d.lgt.lattice import plaquette_angles, topological_charge
from u1_2d.lgt.ptbc import (
    DefectWilsonAction,
    OpenBoundaryWilsonAction,
    geometric_c_ladder,
    swap_replicas,
)

L = 8
BETA = 2.0


def _cfg(seed, b=1):
    g = torch.Generator().manual_seed(seed)
    return (torch.rand(b, 2, L, L, generator=g) * 2 - 1) * math.pi


class TestDefectAction:
    def test_c_one_reproduces_wilson(self):
        """c = 1 must be the periodic action to machine precision."""
        theta = _cfg(0, 4)
        ref = WilsonAction(BETA).per_config(theta)
        got = DefectWilsonAction(BETA, L, c=1.0).per_config(theta)
        assert torch.allclose(ref, got, atol=1e-6)

    def test_c_zero_drops_exactly_the_defect(self):
        theta = _cfg(1, 3)
        full = WilsonAction(BETA).per_config(theta)
        cut = DefectWilsonAction(BETA, L, c=0.0, defect_width=1, defect_x0=0)
        plaq = plaquette_angles(theta)
        dropped = BETA * torch.cos(plaq[..., 0:1, :]).sum(dim=(-2, -1))
        assert torch.allclose(cut.per_config(theta), full + dropped, atol=1e-6)

    def test_defect_cos_sum_matches_direct(self):
        theta = _cfg(2, 2)
        a = DefectWilsonAction(BETA, L, c=0.5, defect_width=2, defect_x0=3)
        plaq = plaquette_angles(theta)
        idx = torch.tensor([3, 4])
        assert torch.allclose(a.defect_cos_sum(theta),
                              torch.cos(plaq[..., idx, :]).sum(dim=(-2, -1)),
                              atol=1e-6)

    def test_defect_wraps_around_lattice(self):
        a = DefectWilsonAction(BETA, L, c=0.0, defect_width=2, defect_x0=L - 1)
        m = a._mask(torch.device("cpu"), torch.float32)
        assert m[L - 1, 0] == 0.0 and m[0, 0] == 0.0
        assert m[1, 0] == 1.0


class TestSwapAcceptance:
    @pytest.mark.parametrize("c_lo,c_hi", [(1.0, 0.5), (0.5, 0.0), (0.8, 0.2)])
    def test_delta_s_matches_action_difference(self, c_lo, c_hi):
        """dS from defect plaquettes == the full swapped-action difference.

        This is the identity the sampler's correctness rests on:
          dS = [S_lo(x_hi) + S_hi(x_lo)] - [S_lo(x_lo) + S_hi(x_hi)]
        """
        x_lo, x_hi = _cfg(10, 5), _cfg(11, 5)
        a_lo = DefectWilsonAction(BETA, L, c=c_lo, defect_width=2, defect_x0=1)
        a_hi = DefectWilsonAction(BETA, L, c=c_hi, defect_width=2, defect_x0=1)
        direct = ((a_lo.per_config(x_hi) + a_hi.per_config(x_lo))
                  - (a_lo.per_config(x_lo) + a_hi.per_config(x_hi)))
        formula = a_lo.beta * (a_lo.c - a_hi.c) * (
            a_lo.defect_cos_sum(x_lo) - a_lo.defect_cos_sum(x_hi))
        assert torch.allclose(direct, formula, atol=1e-4)

    def test_swap_is_a_permutation_of_configs(self):
        """Swaps move configurations between replicas; none are created."""
        stack = torch.stack([_cfg(20 + r) for r in range(4)])
        before = sorted(float(x.sum()) for x in stack)
        actions = [DefectWilsonAction(BETA, L, c=c) for c in geometric_c_ladder(4)]
        out, _ = swap_replicas(stack.clone(), actions, parity=0)
        after = sorted(float(x.sum()) for x in out)
        assert all(abs(a - b) < 1e-4 for a, b in zip(before, after))

    def test_always_accepts_when_ladder_is_degenerate(self):
        """Equal c means dS = 0, so every proposed swap is accepted."""
        stack = torch.stack([_cfg(30 + r) for r in range(4)])
        actions = [DefectWilsonAction(BETA, L, c=0.7) for _ in range(4)]
        _, acc = swap_replicas(stack.clone(), actions, parity=0)
        assert float(acc[0].mean()) == 1.0 and float(acc[2].mean()) == 1.0

    def test_parity_leaves_untouched_pairs_alone(self):
        stack = torch.stack([_cfg(40 + r) for r in range(4)])
        actions = [DefectWilsonAction(BETA, L, c=c) for c in geometric_c_ladder(4)]
        out, acc = swap_replicas(stack.clone(), actions, parity=1)
        # pair (0,1) is not proposed at odd parity -- NaN, not 0, so that
        # averaging over trajectories does not halve the reported acceptance
        assert torch.isnan(acc[0]).all()
        assert torch.allclose(out[0], stack[0], atol=1e-6)


class TestOpenBoundary:
    def test_drops_one_row_of_plaquettes(self):
        theta = _cfg(50, 2)
        full = WilsonAction(BETA).per_config(theta)
        open_a = OpenBoundaryWilsonAction(BETA, L)
        plaq = plaquette_angles(theta)
        dropped = BETA * torch.cos(plaq[..., L - 1:L, :]).sum(dim=(-2, -1))
        assert torch.allclose(open_a.per_config(theta), full + dropped, atol=1e-6)

    def test_equals_defect_action_with_full_cut(self):
        theta = _cfg(51, 2)
        a = OpenBoundaryWilsonAction(BETA, L)
        b = DefectWilsonAction(BETA, L, c=0.0, defect_width=1, defect_x0=L - 1)
        assert torch.allclose(a.per_config(theta), b.per_config(theta), atol=1e-6)


class TestPhysicalReplicaUnbiased:
    def test_periodic_replica_action_is_untouched_by_tempering(self):
        """The c = 1 replica must be scored by the plain Wilson action.

        If this drifts, every PTBC measurement is of the wrong theory.
        """
        ladder = geometric_c_ladder(5)
        assert ladder[0] == 1.0 and ladder[-1] == 0.0
        theta = _cfg(60, 3)
        a0 = DefectWilsonAction(BETA, L, c=ladder[0])
        assert torch.allclose(a0.per_config(theta),
                              WilsonAction(BETA).per_config(theta), atol=1e-6)

    def test_charge_is_integer_on_periodic_replica(self):
        theta = _cfg(61, 6)
        q = topological_charge(theta)
        assert torch.allclose(q, torch.round(q), atol=1e-5)


# --- stacked (batched-over-replicas) path -------------------------------------
# The stacked action is a pure performance rewrite, so every test here pins it
# against the per-replica path it replaces rather than against fresh algebra.

CS = [1.0, 0.6, 0.25, 0.0]


def _stack_cfg(seed, R, b):
    g = torch.Generator().manual_seed(seed)
    return (torch.rand(R * b, 2, L, L, generator=g) * 2 - 1) * math.pi


def test_stacked_per_config_matches_unstacked():
    from u1_2d.lgt.ptbc import StackedDefectWilsonAction
    B = 3
    st = StackedDefectWilsonAction(BETA, L, CS, n_chains=B, defect_length=2)
    theta = _stack_cfg(7, len(CS), B)
    got = st.per_config(theta)
    for r, c in enumerate(CS):
        a = DefectWilsonAction(BETA, L, c=c, defect_length=2)
        want = a.per_config(theta[r * B:(r + 1) * B])
        assert torch.allclose(got[r * B:(r + 1) * B], want, atol=1e-10)


def test_stacked_defect_cos_sums_match_unstacked():
    from u1_2d.lgt.ptbc import StackedDefectWilsonAction
    B = 2
    st = StackedDefectWilsonAction(BETA, L, CS, n_chains=B, defect_length=3)
    theta = _stack_cfg(11, len(CS), B)
    got = st.defect_cos_sums(theta)
    for r, c in enumerate(CS):
        a = DefectWilsonAction(BETA, L, c=c, defect_length=3)
        want = a.defect_cos_sum(theta[r * B:(r + 1) * B])
        assert torch.allclose(got[r], want, atol=1e-10)


def test_stacked_swap_energy_matches_unstacked_rule():
    """dS from the vectorized swap equals the two-action difference."""
    from u1_2d.lgt.ptbc import StackedDefectWilsonAction
    B = 2
    st = StackedDefectWilsonAction(BETA, L, CS, n_chains=B, defect_length=2)
    theta = _stack_cfg(13, len(CS), B)
    m = st.defect_cos_sums(theta)
    for r in range(len(CS) - 1):
        a_lo = DefectWilsonAction(BETA, L, c=CS[r], defect_length=2)
        a_hi = DefectWilsonAction(BETA, L, c=CS[r + 1], defect_length=2)
        x_lo = theta[r * B:(r + 1) * B]
        x_hi = theta[(r + 1) * B:(r + 2) * B]
        want = ((a_lo.per_config(x_hi) + a_hi.per_config(x_lo))
                - (a_lo.per_config(x_lo) + a_hi.per_config(x_hi)))
        got = BETA * (CS[r] - CS[r + 1]) * (m[r] - m[r + 1])
        assert torch.allclose(got, want, atol=1e-8)


def test_stacked_swap_is_a_permutation_and_respects_parity():
    from u1_2d.lgt.ptbc import StackedDefectWilsonAction, swap_replicas_stacked
    B, R = 2, len(CS)
    st = StackedDefectWilsonAction(BETA, L, CS, n_chains=B, defect_length=2)
    theta = _stack_cfg(17, R, B)
    before = theta.clone()
    out, acc = swap_replicas_stacked(theta.clone(), st, parity=0)
    assert acc.shape == (R - 1, B)
    # odd pairs are not proposed under parity 0 and must not average in as 0
    assert torch.isnan(acc[1::2]).all()
    assert not torch.isnan(acc[0::2]).any()
    sb = before.view(R, B, 2, L, L)
    so = out.view(R, B, 2, L, L)
    for r in range(0, R - 1, 2):
        for b in range(B):
            if acc[r, b] > 0:
                assert torch.allclose(so[r, b], sb[r + 1, b])
                assert torch.allclose(so[r + 1, b], sb[r, b])
            else:
                assert torch.allclose(so[r, b], sb[r, b])


def test_stacked_c_equals_one_reproduces_wilson():
    from u1_2d.lgt.ptbc import StackedDefectWilsonAction
    st = StackedDefectWilsonAction(BETA, L, [1.0, 1.0], n_chains=2)
    theta = _stack_cfg(23, 2, 2)
    assert torch.allclose(st.per_config(theta),
                          WilsonAction(BETA).per_config(theta), atol=1e-10)


def test_stacked_mask_cache_tracks_defect_translation():
    from u1_2d.lgt.ptbc import StackedDefectWilsonAction
    st = StackedDefectWilsonAction(BETA, L, CS, n_chains=1, defect_length=2)
    theta = _stack_cfg(29, len(CS), 1)
    s0 = st.per_config(theta).clone()
    st.move_defect_to(3)
    s1 = st.per_config(theta)
    assert not torch.allclose(s0, s1)
    ref = [DefectWilsonAction(BETA, L, c=c, defect_length=2, defect_x0=3)
           .per_config(theta[r:r + 1])[0] for r, c in enumerate(CS)]
    assert torch.allclose(s1, torch.stack(ref), atol=1e-10)
