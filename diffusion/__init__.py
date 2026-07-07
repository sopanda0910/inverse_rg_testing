"""Inverse-RG conditional diffusion for 2D compact U(1) lattice gauge theory.

Subpackages:
    lgt       -- lattice core: actions, HMC, local updates, blocking, exact results
    model     -- wrapped-Gaussian diffusion on the torus, gauge-covariant score net
    pipeline  -- iterated coarse-to-fine generation ladder with rethermalization
    validate  -- observables, statistics, report generation
"""
