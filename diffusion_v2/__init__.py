"""Inverse-RG conditional diffusion for 2D compact U(1) lattice gauge theory.

Subpackages:
    lgt       -- lattice core: actions, HMC, local updates, blocking, exact results
    model     -- wrapped-Gaussian diffusion on the torus, gauge-covariant score net
    pipeline  -- iterated coarse-to-fine generation ladder with rethermalization
    validate  -- observables, statistics, report generation

DIFFUSION_V2_TORCH_THREADS caps torch's thread pools for this process. This is
the only thread-count lever that works on this machine's PyTorch build (OMP/MKL
env vars are ignored), and per-process capping is the validated-safe way to run
parallel campaign stages on the Snapdragon laptop -- do NOT combine parallelism
with EcoQoS unthrottling or priority elevation (documented hardware crashes).
"""

import os as _os

if _os.environ.get("DIFFUSION_V2_TORCH_THREADS"):
    import torch as _torch

    _n = int(_os.environ["DIFFUSION_V2_TORCH_THREADS"])
    _torch.set_num_threads(_n)
    try:
        _torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
