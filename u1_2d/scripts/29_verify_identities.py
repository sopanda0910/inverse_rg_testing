"""Re-verify the exact identities the physics argument rests on.

Every check here is an *algebraic* or *closed-form* statement — none of them
involve the trained model, and none of them are statistical. They either hold
to floating-point precision or the physics argument in docs/PHYSICS_WALKTHROUGH.md
has a hole. Run time: a few seconds.

    .venv/Scripts/python.exe u1_2d/scripts/29_verify_identities.py
"""

import math

import torch

from u1_2d.lgt.actions import WilsonAction
from u1_2d.lgt.blocking import (
    approx_matched_coarse_beta,
    block_links,
    blocked_plaquette_from_fine,
    villain_blocked_beta,
)
from u1_2d.lgt.exact import (
    plaquette_exact,
    topological_susceptibility_exact,
    wilson_loop_exact,
)
from u1_2d.lgt.lattice import (
    plaquette_angles,
    random_gauge_transform,
    topological_charge_float,
    wrap,
)
from u1_2d.lgt.local_updates import instanton_field
from u1_2d.model.score_net import plaquette_curl

TOL = 1e-12


def main() -> int:
    torch.manual_seed(0)
    lattice, batch = 16, 4
    field = (torch.rand(batch, 2, lattice, lattice) * 2 * math.pi - math.pi).double()
    failures = []

    def check(name: str, value: float, tol: float = TOL) -> None:
        ok = value <= tol
        print(f"   [{'ok' if ok else 'FAIL'}] {name}: {value:.3e}  (tol {tol:.0e})")
        if not ok:
            failures.append(name)

    print("1. Q is an exact integer on every configuration (sec A4)")
    charge = topological_charge_float(field)
    print(f"   Q = {[f'{v:+.12f}' for v in charge.tolist()]}")
    check("max |Q - round(Q)|", float((charge - charge.round()).abs().max()))

    print("\n2. Gauge invariance of the plaquette and of Q (sec A3)")
    gauged = random_gauge_transform(field)
    check(
        "max |cos p(gauged) - cos p|",
        float((torch.cos(plaquette_angles(gauged)) - torch.cos(plaquette_angles(field))).abs().max()),
    )
    check(
        "max |Q(gauged) - Q|",
        float((topological_charge_float(gauged) - charge).abs().max()),
    )

    print("\n3. Coarse plaquette = wrapped sum of its four fine plaquettes (sec B1)")
    check(
        "max |P_coarse - wrap(sum of 4 fine)|",
        float(wrap(plaquette_angles(block_links(field)) - blocked_plaquette_from_fine(field)).abs().max()),
    )

    print("\n4. Curl head spans exactly the Wilson score, h_p = -beta sin(theta_p) (sec C4)")
    beta = 3.7
    leaf = field.clone().requires_grad_(True)
    action_sum = -beta * torch.cos(plaquette_angles(leaf)).sum()
    (grad,) = torch.autograd.grad(action_sum, leaf)
    curl = plaquette_curl((-beta * torch.sin(plaquette_angles(field))).unsqueeze(1))
    check("max |curl(h) + dS/dtheta|", float((curl + grad).abs().max()))

    print("\n5. <Q^2> is a fixed point of the ladder, (V, beta) -> (4V, 4beta) (sec B3)")
    size, coupling, rungs = 8, 1.3472, []
    for _ in range(4):
        rungs.append(topological_susceptibility_exact(coupling, "villain", size) * size * size)
        size, coupling = 2 * size, 4 * coupling
    print("   <Q^2>: " + " -> ".join(f"{v:.5f}" for v in rungs))
    check("relative drift rung 1 -> rung 4", abs(rungs[-1] / rungs[0] - 1.0), tol=1e-3)

    print("\n6. Villain blocking is exactly beta_f/4; Wilson is not (sec B2)")
    for fine in (14.1464, 55.0237):
        villain = approx_matched_coarse_beta(fine, "villain")
        wilson = approx_matched_coarse_beta(fine, "wilson")
        print(f"   beta_f = {fine:8.4f}   Wilson-matched beta_c = {wilson:9.6f}"
              f"   (tree level {fine / 4:.4f}, off by {abs(wilson / (fine / 4) - 1) * 100:.1f}%)")
        check(f"Villain match == beta_f/4 at beta_f={fine}",
              abs(villain / villain_blocked_beta(fine) - 1.0), tol=1e-9)

    print("\n7. Finite-volume Wilson loop on the torus (sec A5)")
    for coupling in (4.0, 55.0237):
        for size in (16, 32):
            check(
                f"beta={coupling:.4f} L={size}: W(A=0) = 1",
                abs(wilson_loop_exact(coupling, 0, "wilson", size) - 1.0),
                tol=1e-9,
            )
            check(
                f"beta={coupling:.4f} L={size}: W(A=1) = <cos theta_p>",
                abs(wilson_loop_exact(coupling, 1, "wilson", size)
                    - plaquette_exact(coupling, "wilson", size)),
                tol=1e-12,
            )
        # r_1^A is the V -> inf LIMIT of the torus sum, not a reference for a
        # finite lattice: the wrapping terms fall like exp(-sigma (V - A)), so
        # the finite-volume result must converge to it as the volume grows.
        r1 = plaquette_exact(coupling, "wilson")
        for area in (4, 16):
            near = abs(wilson_loop_exact(coupling, area, "wilson", 16) / r1**area - 1.0)
            far = abs(wilson_loop_exact(coupling, area, "wilson", 64) / r1**area - 1.0)
            check(
                f"beta={coupling:.4f} A={area:2d}: finite-V -> r_1^A as V grows",
                far,
                tol=max(1e-12, near / 100.0),
            )

    print("\n8. Instanton hop carries Q = 1 at cost dS ~ 2 pi^2 beta / V (sec C5)")
    for size, coupling in ((32, 55.0237), (64, 55.0237)):
        cold = torch.zeros(1, 2, size, size)
        hopped = wrap(cold + instanton_field(size))
        delta_s = float(WilsonAction(coupling).per_config(hopped) - WilsonAction(coupling).per_config(cold))
        predicted = 2 * math.pi**2 * coupling / (size * size)
        print(f"   L={size:3d} beta={coupling:.4f}: dS = {delta_s:7.4f}   2 pi^2 beta/V = {predicted:7.4f}")
        check(f"L={size}: |Q(instanton) - 1|", abs(float(topological_charge_float(hopped)) - 1.0), tol=1e-6)

    print()
    if failures:
        print(f"FAILED: {len(failures)} check(s): {failures}")
        return 1
    print("All exact identities hold.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
