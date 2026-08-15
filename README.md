# InverseRG

Diffusion-based inverse renormalization group for lattice field theories.

Coarse configurations are lifted to fine configurations with a score-based
(diffusion) model, trained so that gauge-invariant observable distributions
(Wilson loops, and where applicable topological charge) match direct HMC
ensembles. Iterating the lift up a matched beta ladder produces large, fine
lattices at costs where direct HMC suffers from critical slowing down and
topological freezing.

## Layout

| package | theory | status |
|---|---|---|
| [`u1_2d/`](u1_2d/) | 2D compact U(1) | **closed** — complete study, results of record in [`out/u1_2d/paper_appendix/appendix.md`](out/u1_2d/paper_appendix/appendix.md) |
| `su2_2d/` | 2D SU(2) | **set aside, not in the tree** — restore with `git checkout 87fd6fa -- su2_2d` |

The full mathematical narrative of the U(1) study (physics background,
diffusion machinery, the exactness program, AIS, and closure) is in
[`docs/NARRATIVE.md`](docs/NARRATIVE.md); the final audit is
[`docs/V2_AUDIT.md`](docs/V2_AUDIT.md).

Headline U(1) result: at large beta, plain HMC is topologically frozen and
instanton-HMC pays an entry cost that leaves it ~6 sigma biased on Wilson
observables at L = 64 even after 16x the standard burn-in, while the
diffusion pipeline is flat-cost and passes all observables — with its
correctness carried by exact Markov-chain machinery wrapped around the
generative proposal.

## Quick start

A virtual environment is pre-configured at `.venv/`:

```bash
.venv/Scripts/activate         # Windows
pip install -e .               # required: scripts import `u1_2d` as a package
pytest u1_2d/tests -q
```

Checks that should pass before anything is published:

```bash
python u1_2d/scripts/29_verify_identities.py              # exact physics identities
python u1_2d/scripts/30_assemble_appendix_figures.py --check   # figures match sources
```

The first re-derives every claim tagged exact in
[`docs/PHYSICS_WALKTHROUGH.md`](docs/PHYSICS_WALKTHROUGH.md) — topological
charge integrality, gauge invariance, the blocking telescope, curl-head
completeness against the Wilson score, the ⟨Q²⟩ ladder fixed point, the area
law, and the instanton hop cost. The second verifies the 28 appendix figures
still match the outputs they were made from.

## Reproducing the study

One driver runs the whole campaign, resumably — every stage writes a sentinel
to `out/u1_2d/campaign_state/` and is skipped on relaunch, and the underlying
scripts skip their own finished work:

```bash
python u1_2d/scripts/run_campaign.py            # full campaign
python u1_2d/scripts/run_campaign.py --smoke    # minutes, not hours
```

Its stage order is the pipeline order, and the stages map to the numbered
scripts:

| stage | script | device |
|---|---|---|
| DATA | `01_generate_data.py` | cpu, 8 shards |
| TRAIN | `02_train.py` | cuda |
| LADDER | `03_run_ladder.py` | cuda |
| VALIDATE | `04_validate.py` | cpu |
| thermalization | `05_hmc_thermalization.py` | cuda |
| study | `06_generalization_study.py` | cuda |
| HEADTOHEAD | `14_diffusion_vs_instanton_hmc.py` | cuda |
| ESS | `15_model_ess.py` | cuda |
| AUTOCORR | `11_autocorrelation.py` | cpu |
| VERDICT | `12_campaign_verdict.py` | — |

See [`CLAUDE.md`](CLAUDE.md) for why each stage gets that device (batched HMC
is kernel-launch-bound and is often *faster on CPU* below L ≈ 64) and for the
sharding recipe.

### Analysis scripts added after the campaign

These read the campaign's outputs and are run individually, not by the driver:

| script | question it answers |
|---|---|
| `33_charge_freezing_sigma.py` | at what σ does the model stop changing topological sector, and how often does it land in the coarse sector unaided? |
| `34_surrogate_floor_vs_n.py` | is the AIS surrogate floor real or an artifact of fit-set size? |
| `35_crossover_window.py` | in which β regimes is a speedup over HMC even defined? |
| `36_dissociation_figure.py` | Figure 28: observables agree while the density does not |
| `37_tiling_baseline.py` | do non-learned prolongators explain the speedup? |
| `parse_ais_seed_rate.py` | how often does the AIS bridge diverge? (Table S7b) |
| `parse_proj_seed_sweep.py` | is the charge-projection threshold effect inside seed noise? |
| `run_hparam_sweep.py` | does any never-tuned hyperparameter clear the baseline seed spread? |
| `32_gpu_smoke.py` | runs every compute-bearing script once on the GPU, flagging device bugs |
