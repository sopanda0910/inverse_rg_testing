# SUPERSEDED -- the sampler-step scan of an UNBLENDED sampler

The record is `../sampler_steps_deployed/`.

This scan called `generate_fine_from_coarse` with the FUNCTION defaults, which
have `physics_blend_coef = 0.0`, while the deployed ladder runs
`physics_blend_coef: 1.0`, `physics_blend_beta_min: 5.0` and rebuilds the noise
schedule with `sigma_min_beta_coef: 0.1` before sampling. The blend and the step
count interact, so these numbers describe a sampler nobody runs.

Its conclusion -- that 18 steps is a free 10-14x saving -- is WITHDRAWN. On the
deployed sampler the post-rethermalization column is flat from 12 steps but the
RAW column is still falling at 100 (worst |z| 16.0 at 18 steps against 1.0 at
200, beta_f = 55.02), and every seed-quality claim in the paper is measured on
the raw lift. `v3_scale.yaml` stays at 200. See
`u1_2d/configs/v3_scale_s18.yaml` for the end-to-end verification.
