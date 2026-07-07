"""Iterated inverse-RG generation: coarse ensemble -> fine ensemble, rung by rung.

Each rung doubles the linear lattice size:
    1. conditional diffusion sample  p_theta(fine | coarse invariants, beta_target)
    2. short local rethermalization (heatbath/Metropolis + overrelaxation) at
       beta_target -- mandatory at every rung to stop bias compounding; cheap
       because only UV modes need fixing
    3. the result becomes the coarse ensemble for the next rung.
"""

import time
from dataclasses import dataclass, field

import torch

from ..lgt.actions import make_action
from ..lgt.local_updates import retherm_sweeps, instanton_field
from ..lgt.lattice import mean_plaquette, topological_charge, plaquette_angles, wrap
from ..model.sampler import sample_ancestral
from ..model.score_net import coarse_conditioning_channels, plaquette_curl


def blocking_consistency_score(
    theta: torch.Tensor, coarse_plaq: torch.Tensor, sigma: torch.Tensor
) -> torch.Tensor:
    """Reconstruction-guidance score pulling each 2x2 cell of fine plaquettes toward
    its coarse plaquette angle (the constraint that transports topological charge).

    Gradient of -(sum_cell theta_p - Theta_P)^2 / (2 lambda(sigma)) w.r.t. the
    links, assembled through the same plaquette-curl head as the model score, so it
    is exactly gauge covariant. lambda(sigma) ~ 8 sigma^2 accounts for the noise the
    8 boundary links of a cell inject into the blocked plaquette at level sigma.

    The residual is deliberately NOT wrapped: a wrapped residual is blind to a cell
    sum landing 2 pi away from its coarse target, which lets spurious winding
    defects freeze in during sampling and inflate <Q^2> at large beta. Pulling the
    raw sum to the principal-branch target expels those defects; the probability of
    suppressing a *legitimate* |cell sum| > pi event is exp-small for beta >~ 4
    (e.g. ~0.2% per cell at beta = 4, ~4e-9 at beta = 14).
    """
    fine_plaq = plaquette_angles(theta)
    cell_sum = (
        fine_plaq[:, 0::2, 0::2]
        + fine_plaq[:, 1::2, 0::2]
        + fine_plaq[:, 0::2, 1::2]
        + fine_plaq[:, 1::2, 1::2]
    )
    residual = cell_sum - coarse_plaq
    lam = 8.0 * sigma**2 + 1e-3
    h_cells = -residual / lam
    h = h_cells.repeat_interleave(2, dim=-2).repeat_interleave(2, dim=-1)
    return plaquette_curl(h.unsqueeze(1))


@dataclass
class LadderRungResult:
    beta: float
    lattice_size: int
    configs: torch.Tensor
    observables: dict = field(default_factory=dict)


def generate_fine_from_coarse(
    model,
    schedule,
    coarse: torch.Tensor,
    beta_target: float,
    n_sampler_steps: int = 200,
    n_corrector_steps: int = 1,
    batch_size: int = 64,
    device: str = "cpu",
    consistency_weight: float = 1.0,
    enforce_coarse_charge: bool = True,
) -> torch.Tensor:
    """Conditional diffusion sample of fine configs, one per coarse config.

    enforce_coarse_charge: after sampling, set each fine configuration's
    topological sector to its coarse partner's by adding the smooth instanton
    difference (a deterministic, gauge-covariant map using only the conditioning
    input). Justification: the blocking preserves Q up to wrap events whose
    probability is exp-small at the couplings where topology matters, while the
    Wilson action's own preference between neighboring Q sectors is O(beta/V) --
    far too weak for the learned score to pin the sector reliably. Any curl-type
    guidance provably cannot fix a wrong sector either (the total wrapped
    plaquette sum is invariant under link deformations until a plaquette crosses
    +-pi), so the sector is enforced structurally and rethermalization then
    relaxes the tiny uniform strain (2 pi dQ / V per plaquette)."""
    model.eval()
    fine_size = coarse.shape[-1] * 2
    sigmas = schedule.discrete_sigmas(n_sampler_steps, device=device)
    outputs = []
    for start in range(0, coarse.shape[0], batch_size):
        chunk = coarse[start : start + batch_size].to(device).float()
        cond = coarse_conditioning_channels(chunk, fine_size)
        coarse_plaq = plaquette_angles(chunk)
        beta = torch.full((chunk.shape[0],), float(beta_target), device=device)

        def score_fn(theta, sigma):
            sig = sigma.expand(theta.shape[0])
            score = model.score(theta, sig, beta[: theta.shape[0]], cond[: theta.shape[0]])
            if consistency_weight > 0:
                score = score + consistency_weight * blocking_consistency_score(
                    theta, coarse_plaq[: theta.shape[0]], sigma
                )
            return score

        sample = sample_ancestral(
            score_fn,
            (chunk.shape[0], 2, fine_size, fine_size),
            sigmas,
            device=device,
            n_corrector_steps=n_corrector_steps,
        )
        if enforce_coarse_charge:
            inst = instanton_field(fine_size, device=sample.device, dtype=sample.dtype)
            coarse_q = topological_charge(chunk)
            for _ in range(3):
                delta_q = coarse_q - topological_charge(sample)
                if not delta_q.any():
                    break
                sample = wrap(sample + delta_q.view(-1, 1, 1, 1) * inst)
        outputs.append(sample.cpu())
    return torch.cat(outputs, dim=0)


def _rung_observables(configs: torch.Tensor) -> dict:
    with torch.no_grad():
        charge = topological_charge(configs)
        return {
            "plaquette": float(mean_plaquette(configs)),
            "q_mean": float(charge.mean()),
            "q_squared": float(charge.square().mean()),
        }


def generate_ladder(
    coarse_ensemble: torch.Tensor,
    beta_schedule: list[float],
    model,
    noise_schedule,
    n_retherm_sweeps: int = 10,
    action_type: str = "wilson",
    n_sampler_steps: int = 200,
    n_corrector_steps: int = 1,
    batch_size: int = 64,
    device: str = "cpu",
    verbose: bool = True,
    consistency_weight: float = 1.0,
    enforce_coarse_charge: bool = True,
    retherm_topological_updates: bool = False,
) -> list[LadderRungResult]:
    """Iterate conditional generation up the ladder.

    coarse_ensemble: [N, 2, L0, L0] equilibrated at the coarsest rung.
    beta_schedule: target couplings for successive fine rungs (each doubles L).
    Returns one LadderRungResult per generated rung (observables logged at every
    rung so drift/bias accumulation is visible).

    retherm_topological_updates: include instanton Q-hop proposals in the
    rethermalization at every rung. The smooth-instanton dS is O(beta / V), so
    acceptance stays high even at couplings where local updates never tunnel;
    this re-equilibrates P(Q) at each rung instead of freezing in the sector
    inherited from the base ensemble. Leave off to test whether the model and
    charge transport alone reproduce topology.
    """
    current = coarse_ensemble
    results = []
    for rung_index, beta_target in enumerate(beta_schedule):
        t0 = time.time()
        fine = generate_fine_from_coarse(
            model,
            noise_schedule,
            current,
            beta_target,
            n_sampler_steps=n_sampler_steps,
            n_corrector_steps=n_corrector_steps,
            batch_size=batch_size,
            device=device,
            consistency_weight=consistency_weight,
            enforce_coarse_charge=enforce_coarse_charge,
        )
        obs_raw = _rung_observables(fine)
        action = make_action(action_type, beta_target)
        fine = retherm_sweeps(
            fine, action, n_retherm_sweeps, topological_updates=retherm_topological_updates
        )
        obs = _rung_observables(fine)
        obs["plaquette_pre_retherm"] = obs_raw["plaquette"]
        obs["q_squared_pre_retherm"] = obs_raw["q_squared"]
        result = LadderRungResult(
            beta=beta_target, lattice_size=fine.shape[-1], configs=fine, observables=obs
        )
        results.append(result)
        if verbose:
            print(
                f"rung {rung_index}: L={fine.shape[-1]} beta={beta_target} "
                f"plaq={obs['plaquette']:.4f} (pre-retherm {obs_raw['plaquette']:.4f}) "
                f"<Q^2>={obs['q_squared']:.3f}  [{time.time()-t0:.0f}s]"
            )
        current = fine
    return results
