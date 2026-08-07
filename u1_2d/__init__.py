"""Inverse-RG conditional diffusion for 2D compact U(1) lattice gauge theory.

Subpackages:
    lgt       -- lattice core: actions, HMC, local updates, blocking, exact results
    model     -- wrapped-Gaussian diffusion on the torus, gauge-covariant score net
    pipeline  -- iterated coarse-to-fine generation ladder with rethermalization
    validate  -- observables, statistics, report generation

U1_2D_TORCH_THREADS caps torch's thread pools for this process; U1_2D_DEVICE
overrides the config's device for every script (see utils.resolve_device).

The thread cap only bites on CPU runs -- it is the sole thread-count lever that
works on the Snapdragon build (OMP/MKL env vars are ignored there), and
per-process capping is the validated-safe way to run parallel campaign stages on
that laptop: do NOT combine parallelism with EcoQoS unthrottling or priority
elevation (documented hardware crashes). On the CUDA box it is inert for the
training loop and matters only to the HMC/measurement stages that stay on CPU.
"""

import os as _os

if _os.environ.get("U1_2D_TORCH_THREADS"):
    import torch as _torch

    _n = int(_os.environ["U1_2D_TORCH_THREADS"])
    _torch.set_num_threads(_n)
    try:
        _torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
