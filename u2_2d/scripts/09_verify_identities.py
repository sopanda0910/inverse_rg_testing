"""Exact identities of the 2D U(2) study. Seconds to run; must pass.

The U(2) analogue of `u1_2d/scripts/29_verify_identities.py`. Every check here is
an exact statement -- machine precision, no statistics -- and each one is
load-bearing for a claim the project makes:

  group        the split (phi, quaternion) representation really is U(2)
  gauge        traces, determinant phases and Q are gauge invariant
  determinant  det is a homomorphism, so Q is a functional of psi alone
  blocking     the determinant telescope is exact even though U(2) does not commute
  force        the analytic u(2) force equals autograd
  updates      overrelaxation is microcanonical; the conditional SU(2) sampler
               leaves psi and Q untouched bit-for-bit
  winding      even winding is purely central; odd winding is not, and cannot be
  exact        the character expansion reproduces Weyl integration and the area law

Run:  python u2_2d/scripts/09_verify_identities.py
"""

import math
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import u1_2d.lgt.blocking as u1_blocking
import u1_2d.lgt.lattice as u1_lattice
from scipy.special import ive
from u2_2d.lgt import exact
from u2_2d.lgt.actions import WilsonU2Action, DetSectorAction, log_g0
from u2_2d.lgt.blocking import (
    block_links,
    blocked_det_plaquette_from_fine,
    half_link,
    matching_residuals,
)
from u2_2d.lgt.hmc import u2_force
from u2_2d.lgt.lattice import (
    det_links,
    det_phase,
    half_retr,
    identity_links,
    link_environment,
    plaquette,
    random_gauge_transform,
    random_links,
    to_matrix,
    from_matrix,
    topological_charge,
    topological_charge_float,
    u2_conj,
    u2_exp,
    u2_log,
    u2_mul,
    wilson_loop,
)
from u2_2d.lgt.local_updates import (
    apply_winding,
    central_winding_field,
    conditional_su2_sweeps,
    overrelaxation_sweep,
    retherm_sweeps,
    set_topological_charge,
)

TOL = 1e-10
FAILURES: list[str] = []


def check(name: str, value: float, tol: float = TOL) -> None:
    ok = bool(value <= tol) and not math.isnan(value)
    print(f"  [{'ok ' if ok else 'FAIL'}] {name:<58s} {value:.3e}  (tol {tol:.0e})")
    if not ok:
        FAILURES.append(name)


def section(title: str) -> None:
    print(f"\n{title}\n" + "-" * len(title))


def main() -> int:
    torch.manual_seed(20260819)
    dtype = torch.float64
    size, batch, beta = 8, 4, 6.0
    action = WilsonU2Action(beta)
    hot = random_links(size, batch=batch, dtype=dtype)
    warm = retherm_sweeps(identity_links(size, batch=batch, dtype=dtype), action, 40)
    # Blocking and the winding map preserve Q only up to WRAP EVENTS: the coarse
    # plaquette angle is the wrapped sum of four fine ones, and a shift of 2 pi / V
    # moves a plaquette already sitting at the branch cut across it. Both are
    # exp-small exactly where topology matters, so the exactness checks below run on
    # a cold ensemble and the wrap rate at moderate coupling is reported as info.
    cold_beta = 60.0
    cold = retherm_sweeps(identity_links(size, batch=16, dtype=dtype),
                          WilsonU2Action(cold_beta), 80)

    section("group representation")
    a, b = random_links(size, batch, dtype=dtype), random_links(size, batch, dtype=dtype)
    check("to_matrix o from_matrix o to_matrix = to_matrix",
          float((to_matrix(from_matrix(to_matrix(a))) - to_matrix(a)).abs().max()))
    check("u2_mul is matrix multiplication",
          float((to_matrix(u2_mul(a, b)) - to_matrix(a) @ to_matrix(b)).abs().max()))
    check("u2_conj is hermitian conjugation",
          float((to_matrix(u2_conj(a)) - to_matrix(a).mH).abs().max()))
    check("u2_conj is the group inverse",
          float((to_matrix(u2_mul(a, u2_conj(a)))
                 - torch.eye(2, dtype=torch.cdouble)).abs().max()))
    alg = 0.4 * torch.randn(64, 4, dtype=dtype)
    check("u2_log o u2_exp = id on the principal branch",
          float((u2_log(u2_exp(alg)) - alg).abs().max()))
    check("half_link squared is the link",
          float((to_matrix(u2_mul(half_link(a), half_link(a))) - to_matrix(a)).abs().max()))

    section("gauge invariance and topology")
    gauged = random_gauge_transform(warm)
    check("(1/2)ReTr P is gauge invariant",
          float((half_retr(plaquette(gauged)) - half_retr(plaquette(warm))).abs().max()))
    check("determinant plaquette phase is gauge invariant",
          float(torch.sin(det_phase(plaquette(gauged)) - det_phase(plaquette(warm))).abs().max()))
    check("Q is gauge invariant",
          float((topological_charge(gauged) - topological_charge(warm)).abs().max()))
    check("Q is an integer",
          float((topological_charge_float(warm) - topological_charge(warm)).abs().max()), 1e-9)
    check("Q is an integer (hot configurations too)",
          float((topological_charge_float(hot) - topological_charge(hot)).abs().max()), 1e-9)

    section("determinant sector is a U(1) gauge field")
    psi = det_links(warm)
    check("arg det P = U(1) plaquette angle of psi",
          float(torch.sin(u1_lattice.plaquette_angles(psi) - det_phase(plaquette(warm))).abs().max()))
    check("Q = U(1) topological charge of psi",
          float((u1_lattice.topological_charge(psi) - topological_charge(warm)).abs().max()))
    w32 = wilson_loop(warm, 3, 2)
    check("det of a 3x2 Wilson loop = U(1) 3x2 loop of psi",
          float(torch.sin(det_phase(w32) - u1_lattice.wilson_loop_angles(psi, 3, 2)).abs().max()))
    su2_gauge = random_links(size, batch, dtype=dtype)
    su2_gauge = torch.cat([torch.zeros_like(su2_gauge[..., :1]), su2_gauge[..., 1:]], dim=-1)
    from u2_2d.lgt.lattice import gauge_transform
    check("psi is untouched by an SU(2) gauge transformation",
          float(torch.sin(det_links(gauge_transform(warm, su2_gauge[:, 0])) - psi).abs().max()))

    section("blocking")
    coarse = block_links(warm)
    check("determinant telescope: coarse det plaquette = sum of four fine ones",
          float(torch.sin(det_phase(plaquette(coarse))
                          - blocked_det_plaquette_from_fine(warm)).abs().max()))
    check("blocking commutes with det: det(block(U)) = block(det(U))",
          float(torch.sin(det_links(coarse) - u1_blocking.block_links(psi)).abs().max()))
    check("Q is preserved by blocking (cold, wrap-free)",
          float((topological_charge(block_links(cold)) - topological_charge(cold)).abs().max()))
    wrap_rate = float((topological_charge(coarse) != topological_charge(warm)).double().mean())
    print(f"  [info] blocking wrap rate at beta={beta:g}, L={size}: {wrap_rate:.3f} of configurations")

    section("force and local updates")
    algebra = torch.zeros(warm.shape[:-1] + (4,), dtype=dtype, requires_grad=True)
    total = action.per_config(u2_mul(u2_exp(algebra), warm)).sum()
    (autograd,) = torch.autograd.grad(total, algebra)
    check("analytic u(2) force = autograd",
          float((u2_force(warm, beta) - autograd).abs().max()))
    env = link_environment(warm)
    check("staple sum rule: sum_links ReTr(U Sigma) = 4 sum_p ReTr P",
          float((env[..., 0].real.sum(dim=(1, 2, 3))
                 - 4.0 * half_retr(plaquette(warm)).sum(dim=(-2, -1))).abs().max()), 1e-9)
    check("overrelaxation is microcanonical",
          float((action.per_config(overrelaxation_sweep(warm))
                 - action.per_config(warm)).abs().max()), 1e-9)
    relaxed = conditional_su2_sweeps(warm, action, 4)
    check("conditional SU(2) sampler leaves psi untouched",
          float((det_links(relaxed) - psi).abs().max()))
    check("conditional SU(2) sampler leaves Q untouched",
          float((topological_charge(relaxed) - topological_charge(warm)).abs().max()))

    section("winding moves")
    even = apply_winding(cold, torch.full((cold.shape[0],), 2.0, dtype=dtype))
    check("central winding gives delta Q = +2 (cold, wrap-free)",
          float((topological_charge(even) - topological_charge(cold) - 2.0).abs().max()))
    check("central winding leaves the SU(2) sector untouched",
          float((even[..., 1:] - cold[..., 1:]).abs().max()))
    check("central winding field is the U(1) instanton",
          float(torch.sin(u1_lattice.plaquette_angles(central_winding_field(size, dtype=dtype))
                          - 2.0 * math.pi / size**2).abs().max()))
    targets = topological_charge(cold) + torch.tensor([1.0, -1.0, 2.0, -3.0] * 4, dtype=dtype)
    moved = set_topological_charge(cold, targets)
    check("set_topological_charge hits any sector, odd included",
          float((topological_charge(moved) - targets).abs().max()))
    # The Z_2 of U(2) = (U(1) x SU(2)) / Z_2: odd Q forces the SU(2) sector to move.
    odd_su2_change = float((moved[..., 1:] - cold[..., 1:]).abs().max())
    print(f"  [info] odd winding necessarily moves SU(2): max |dq| = {odd_su2_change:.3f}")
    if odd_su2_change < 1e-6:
        FAILURES.append("odd winding left SU(2) untouched (would contradict pi_1)")

    section("exact solution")
    for b in (1.0, 4.0, 12.0, 40.0):
        x = 0.5 * b
        weyl = 0.5 * ive(1, x) * (ive(0, x) - ive(2, x)) / (ive(0, x) ** 2 - ive(1, x) ** 2)
        check(f"character expansion = Weyl integration, beta={b:g}",
              abs(exact.plaquette_exact(b) - weyl), 1e-9)
        check(f"r_fund = <(1/2)ReTr P>, beta={b:g}",
              abs(exact.wilson_loop_exact(b, 1) - exact.plaquette_exact(b)), 1e-9)
        check(f"area law <W(A)> = r^A, beta={b:g}",
              abs(exact.wilson_loop_exact(b, 5) - exact.plaquette_exact(b) ** 5), 1e-9)
        check(f"finite-volume logZ derivative -> infinite volume, beta={b:g}",
              abs(exact.plaquette_exact(b, 24) - exact.plaquette_exact(b)), 1e-5)
    for b in (4.0, 20.0):
        q_values, probs = exact.det_topological_charge_distribution(b, 12)
        chi_from_pq = float((q_values**2 * probs).sum()) / 144.0
        check(f"chi_t from P(Q) = chi_t from the density, beta={b:g}",
              abs(chi_from_pq / exact.det_topological_susceptibility(b) - 1.0), 2e-2)
        check(f"P(Q) is normalized and symmetric, beta={b:g}",
              float(np.abs(probs - probs[::-1]).max()), 1e-12)
    check("matched U(1) coupling -> beta/4 at strong coupling in beta",
          abs(exact.matched_u1_beta(400.0) / 100.0 - 1.0), 1e-3)
    grid = torch.linspace(-math.pi + 1e-6, math.pi - 1e-6, 401, dtype=dtype)
    det_action = DetSectorAction(9.0)
    numeric = torch.autograd.functional.jacobian(
        lambda t: det_action.plaquette_log_weight(t).sum(), grid
    )
    from u2_2d.lgt.actions import det_sector_plaquette_score
    check("det-sector analytic score = autograd of its log weight",
          float((numeric - det_sector_plaquette_score(grid, 9.0)).abs().max()), 1e-9)
    check("log_g0(0) = 0",
          float(log_g0(torch.zeros(1, dtype=dtype)).abs().max()))

    section("matching")
    residual = matching_residuals(220.0)
    check("blocked coupling -> tree level beta/4 at strong coupling in beta",
          abs(residual["tree_level_ratio"] - 1.0), 5e-2)

    print()
    if FAILURES:
        print(f"FAILED ({len(FAILURES)}):")
        for name in FAILURES:
            print(f"  - {name}")
        return 1
    print("all identities hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
