"""Iterated inverse-RG generation for 2D U(2): coarse ensemble -> fine, rung by rung.

Each rung doubles the linear size and quadruples the coupling, and factorizes the
step as p(psi, q) = p(psi) p(q | psi):

    1. lift the DETERMINANT field psi = wrap(2 phi) with the conditional diffusion
       model, including structural transport of the topological sector;
    2. seed the SU(2) sector by naive inverse blocking of the coarse SU(2) part;
    3. equilibrate the SU(2) sector at frozen psi -- EXACT for p(q | psi), and it
       cannot disturb psi or Q;
    4. a short joint rethermalization at the target coupling, which is where any
       determinant-sector model error gets locally repaired.

Step 3 is the load-bearing simplification and it is exact, so the only modelling
error in the whole step is in p(psi). Step 1 is where every hard thing lives.

WHY TOPOLOGY TRANSPORTS FOR FREE HERE. Q depends only on psi (det is a
homomorphism, so the plaquette determinant phase is the plain sum of link phases
and the abelian telescope of `u1_2d` survives), and the blocked determinant
plaquette is the wrapped sum of the four fine ones exactly. So the coarse
configuration ALREADY carries the fine theory's sector, and setting psi sets Q.
Note the contrast with the classical baseline: a global Metropolis winding move at
odd charge is expensive in U(2) because it must drag the SU(2) sector across a -1
monodromy (see `lgt.local_updates`), while here step 3 relaxes exactly that
monodromy for free -- measured, the odd-charge instanton leaves dS = 26-149 and
the conditional SU(2) sweep brings it back to ~5, the physical cost of the sector.
"""

import math
import time
from dataclasses import dataclass, field

import torch

from ..lgt.actions import DetSectorAction, WilsonU2Action, det_sector_plaquette_score
from ..lgt.blocking import block_links
from ..lgt.lattice import (
    det_links,
    half_retr,
    mean_plaquette,
    plaquette,
    topological_charge,
)
from ..lgt.local_updates import conditional_su2_sweeps, retherm_sweeps


from ..model.det_lift import model_beta
from ..model.su2_lift import assemble_links, naive_su2_inverse_block


MAX_OOM_RETRIES = 6
OOM_BACKOFF_SECONDS = 15.0


def _is_oom(exc: BaseException) -> bool:
    """True for both flavours of CUDA exhaustion.

    `torch.OutOfMemoryError` comes from the caching allocator refusing a request.
    A raw `cudaErrorMemoryAllocation` surfaces instead as `AcceleratorError` --
    a different class that does NOT subclass OutOfMemoryError, so catching only
    the latter silently misses it. That is not hypothetical: it is what killed
    stage 03 on 2026-08-19, inside `torch.roll`, with the retry standing right
    there. The driver reports asynchronously, so the frame it lands on is
    unrelated to the allocation that actually failed; the message is the only
    reliable discriminator.
    """
    if isinstance(exc, torch.OutOfMemoryError):
        return True
    return isinstance(exc, torch.AcceleratorError) and "out of memory" in str(exc).lower()


def _run_batched(fn, batch_size: int, n_items: int):
    """Apply `fn(start, size)` over batches, halving the batch on a CUDA OOM.

    This lift peaks at 168 MiB (L = 32) and 116 MiB (L = 64) against ~7.8 GiB
    free, so an exhaustion here is not this process outgrowing the card -- it is
    contention with something else on the machine. Halving still helps (it lowers
    the instantaneous request and gives the competitor time to release), and a
    stage that takes minutes per rung should degrade rather than die.
    """
    outputs = []
    start = 0
    attempts = 0
    while start < n_items:
        size = min(batch_size, n_items - start)
        try:
            outputs.append(fn(start, size))
        except Exception as exc:
            if not _is_oom(exc) or (size == 1 and attempts >= MAX_OOM_RETRIES):
                raise
            attempts += 1
            # empty_cache() ALLOCATES, and on a card that is already exhausted it
            # raises the very error being handled -- which turned this recovery
            # path into a second crash on 2026-08-19. The cleanup is best-effort:
            # if it cannot run, the smaller batch below is still worth trying.
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass
            batch_size = max(1, size // 2)
            # Exhaustion here means contention, not this process outgrowing the
            # card (the lift peaks at 168 MiB against ~7.8 GiB free), so the
            # competitor needs a moment to release more than we need a smaller
            # batch. Back off for progressively longer before retrying.
            delay = OOM_BACKOFF_SECONDS * attempts
            print(f"  CUDA out of memory at batch {size} (attempt {attempts}/"
                  f"{MAX_OOM_RETRIES}); waiting {delay:g}s, retrying at {batch_size}",
                  flush=True)
            time.sleep(delay)
            continue
        start += size
    return outputs


def _sweep_on_device(configs: torch.Tensor, sweep, device: str,
                     batch_size: int = 256) -> torch.Tensor:
    """Run a local-update sweep on `device` and hand the result back on CPU.

    Ensembles are CPU-resident by project convention, but the local updates are
    where the ladder actually spends its time at large L, and they cross over to
    the GPU at L = 16 for U(2) -- by L = 64 the GPU does 9.9 heatbath sweeps/s
    against 0.35 on one CPU thread, a factor of 28. Batching keeps the transfer
    and the working set bounded.
    """
    if not str(device).startswith("cuda"):
        return sweep(configs)
    out = _run_batched(
        lambda start, size: sweep(configs[start:start + size].to(device)).cpu(),
        batch_size, configs.shape[0],
    )
    return torch.cat(out, dim=0)


def det_sector_exact_score(psi: torch.Tensor, beta_u2: float) -> torch.Tensor:
    """Exact score of the determinant-sector target, through the plaquette-curl head.

    The U(2) replacement for `u1_2d.pipeline.ladder.wilson_exact_score`. The
    determinant marginal is not Wilson, so the per-plaquette factor is
    d/d(alpha) log w_det = -(beta/2) sin(alpha/2) I_2(z) / I_1(z) rather than
    -beta_1 sin(alpha); the Bessel ratio tends to 1 only at large coupling.
    """
    from u1_2d.lgt.lattice import plaquette_angles
    from u1_2d.model.score_net import plaquette_curl

    h = -det_sector_plaquette_score(plaquette_angles(psi), beta_u2)
    return plaquette_curl(h.unsqueeze(1))


@dataclass
class LadderRungResult:
    beta: float
    lattice_size: int
    configs: torch.Tensor
    observables: dict = field(default_factory=dict)
    raw_configs: torch.Tensor | None = None


def lift_determinant(
    model,
    schedule,
    coarse_psi: torch.Tensor,
    beta_target: float,
    n_sampler_steps: int = 200,
    n_corrector_steps: int = 1,
    batch_size: int = 64,
    device: str = "cpu",
    consistency_weight: float = 1.0,
    enforce_coarse_charge: bool = True,
    charge_projection_sigma: float = 0.5,
    charge_projection_interval: int = 10,
    physics_blend_coef: float = 0.0,
    corrector_snr: float = 0.16,
) -> torch.Tensor:
    """Conditional diffusion lift of the determinant field, one fine psi per coarse psi.

    Mirrors `u1_2d.pipeline.ladder.generate_fine_from_coarse` -- same reconstruction
    guidance, same in-trajectory charge projection, same rationale -- with two
    substitutions: the network is conditioned on `model_beta(beta_target)` (the
    minimum-KL U(1) projection of the determinant sector, not beta / 4), and the
    small-sigma physics blend uses the exact determinant-sector score.
    """
    from u1_2d.lgt.lattice import plaquette_angles, topological_charge as u1_charge
    from u1_2d.model.sampler import sample_ancestral
    from u1_2d.model.score_net import coarse_conditioning_channels
    from u1_2d.pipeline.ladder import apply_coarse_charge, blocking_consistency_score

    model.eval()
    beta_model = model_beta(beta_target)
    fine_size = coarse_psi.shape[-1] * 2
    sigmas = schedule.discrete_sigmas(n_sampler_steps, device=device, beta=beta_model)
    cond_channels = getattr(model, "cond_channels", 4)

    def lift_batch(start, size):
        chunk = coarse_psi[start : start + size].to(device).float()
        cond = coarse_conditioning_channels(chunk, fine_size, n_channels=cond_channels)
        coarse_plaq = plaquette_angles(chunk)
        beta = torch.full((chunk.shape[0],), float(beta_model), device=device)

        def score_fn(psi, sigma):
            sig = sigma.expand(psi.shape[0])
            score = model.score(psi, sig, beta[: psi.shape[0]], cond[: psi.shape[0]])
            if physics_blend_coef > 0:
                sigma_c = physics_blend_coef / math.sqrt(beta_model)
                w = 1.0 / (1.0 + (sigma / sigma_c) ** 2)
                # A determinant plaquette angle carries four links worth of noise;
                # in the near-Gaussian regime that smears precision beta_1 to
                # beta_1 / (1 + 4 beta_1 sigma^2). Converted back to a U(2)
                # coupling through the same tree-level factor of 4.
                beta_eff = beta_model / (1.0 + 4.0 * beta_model * float(sigma) ** 2)
                score = (1.0 - w) * score + w * det_sector_exact_score(psi, 4.0 * beta_eff)
            if consistency_weight > 0:
                score = score + consistency_weight * blocking_consistency_score(
                    psi, coarse_plaq[: psi.shape[0]], sigma
                )
            return score

        step_callback = None
        if enforce_coarse_charge and charge_projection_interval > 0:
            coarse_q = u1_charge(chunk)
            counter = {"n": 0}

            def step_callback(psi, sigma_next, coarse_q=coarse_q, counter=counter):
                if sigma_next >= charge_projection_sigma:
                    return psi
                counter["n"] += 1
                if counter["n"] % charge_projection_interval:
                    return psi
                return apply_coarse_charge(psi, coarse_q)

        sample = sample_ancestral(
            score_fn,
            (chunk.shape[0], 2, fine_size, fine_size),
            sigmas,
            device=device,
            n_corrector_steps=n_corrector_steps,
            corrector_snr=corrector_snr,
            step_callback=step_callback,
        )
        if enforce_coarse_charge:
            sample = apply_coarse_charge(sample, u1_charge(chunk))
        return sample.cpu()

    outputs = _run_batched(lift_batch, batch_size, coarse_psi.shape[0])
    if str(device).startswith("cuda"):
        # The next rung quadruples the working set, so anything this one left
        # cached is exactly what makes that rung fail to allocate.
        try:
            torch.cuda.empty_cache()
        except Exception:
            pass
    return torch.cat(outputs, dim=0)


def generate_fine_from_coarse(
    model,
    schedule,
    coarse: torch.Tensor,
    beta_target: float,
    n_su2_sweeps: int = 20,
    device: str = "cpu",
    **lift_kwargs,
) -> torch.Tensor:
    """One full inverse-RG step on U(2) configurations [N, 2, Lc, Lc, 5].

    Returns CPU-resident fine configurations at 2 Lc. `n_su2_sweeps` is the only
    knob with no analogue in `u1_2d`: it is how long the EXACT conditional SU(2)
    sampler runs, so larger is strictly better and 2D SU(2) equilibrates fast.
    """
    coarse = coarse.cpu()
    psi_fine = lift_determinant(model, schedule, det_links(coarse), beta_target,
                                device=device, **lift_kwargs)
    su2_seed = naive_su2_inverse_block(coarse[..., 1:])
    fine = assemble_links(psi_fine, su2_seed)
    action = WilsonU2Action(beta_target)
    return _sweep_on_device(
        fine, lambda x: conditional_su2_sweeps(x, action, n_su2_sweeps), device
    )


def _rung_observables(configs: torch.Tensor) -> dict:
    with torch.no_grad():
        charge = topological_charge(configs)
        psi = det_links(configs)
        from u1_2d.lgt.lattice import plaquette_angles

        return {
            "plaquette": float(mean_plaquette(configs)),
            "det_plaquette": float(torch.cos(plaquette_angles(psi)).mean()),
            "q_mean": float(charge.mean()),
            "q_squared": float(charge.square().mean()),
        }


def generate_ladder(
    coarse_ensemble: torch.Tensor,
    beta_schedule: list[float],
    model,
    noise_schedule,
    n_su2_sweeps: int = 20,
    n_retherm_sweeps: int = 10,
    batch_size: int = 64,
    device: str = "cpu",
    verbose: bool = True,
    retherm_topological_updates: bool = False,
    on_rung=None,
    **lift_kwargs,
) -> list[LadderRungResult]:
    """Iterate the inverse-RG step up the ladder.

    `coarse_ensemble`: [N, 2, L0, L0, 5] equilibrated at the coarsest rung.
    `beta_schedule`: target U(2) couplings for successive fine rungs.
    Observables are logged at every rung so bias accumulation stays visible, and
    both the pre- and post-rethermalization values are recorded so it is clear how
    much of the agreement the model earned and how much the sweeps repaired.

    `on_rung(result)` fires as each rung completes. A rung costs minutes and the
    top one is the most likely to fail -- it has the largest working set and the
    least margin -- so the caller gets the chance to persist each rung instead of
    losing the finished ones to a failure in the next.
    """
    current = coarse_ensemble
    results = []
    for rung_index, beta_target in enumerate(beta_schedule):
        t0 = time.time()
        fine = generate_fine_from_coarse(
            model, noise_schedule, current, beta_target,
            n_su2_sweeps=n_su2_sweeps, batch_size=batch_size, device=device,
            **lift_kwargs,
        )
        obs_raw = _rung_observables(fine)
        raw = fine.clone()
        action = WilsonU2Action(beta_target)
        fine = _sweep_on_device(
            fine,
            lambda x: retherm_sweeps(x, action, n_retherm_sweeps,
                                     topological_updates=retherm_topological_updates),
            device,
        )
        obs = _rung_observables(fine)
        obs["plaquette_pre_retherm"] = obs_raw["plaquette"]
        obs["q_squared_pre_retherm"] = obs_raw["q_squared"]
        result = LadderRungResult(beta=beta_target, lattice_size=fine.shape[-2],
                                  configs=fine, observables=obs, raw_configs=raw)
        results.append(result)
        if on_rung is not None:
            on_rung(result)
        if verbose:
            print(f"rung {rung_index}: L={fine.shape[-2]} beta={beta_target:g} "
                  f"plaq={obs['plaquette']:.4f} (pre-retherm {obs_raw['plaquette']:.4f}) "
                  f"<Q^2>={obs['q_squared']:.3f}  [{time.time()-t0:.0f}s]")
        current = fine
    return results
