# Paper Outline — 2D U(2), methods notes (partial)

Started 2026-09-03, scoped to the methods that were just built rather than a
full restatement of the paper's structure (see `docs/u2_2d/DESIGN.md` for the
full derivation/results narrative and `docs/u2_2d/NARRATIVE.md`/`FOLLOWUPS.md`
for the broader project history). This file exists so the thermalization
definition and its literature grounding are stated once, clearly, in a place
a paper draft can lift directly — not spread across CLAUDE.md's much longer
running log.

## Methods: thermalization / relaxation-time definition

**Definition used in the paper.** For a chain's observable series `O(t)`
(mean over `n_chains` chains at trajectory `t`), thermalization time `tau` is
the fitted time constant of

    mean_O(t) ~= target_O + A_O * exp(-t / tau)

fit **jointly across the plaquette and the 2x2/4x4 Wilson loops, sharing one
tau**, via weighted nonlinear least squares (`fit_joint_relaxation_time` in
`u2_2d/scripts/28_crossover_scan.py`). `tau` is reported with a
chain-resampling bootstrap confidence interval, and every accepted fit
carries a chi2/dof diagnostic.

This supersedes an earlier discrete threshold-crossing definition (ported
from u1: first trajectory where `|z| <= 2` against the exact target for 5
consecutive records), which was found to produce visibly rugged
cost-efficiency curves as a function of coupling — not smooth noise around a
trend, but genuinely non-interpolatable point-to-point jumps, because the
statistic is a hard threshold on a noisy quantity. It also cannot represent
"thermalizes in ~0 trajectories" (the diffusion seed's typical case)
honestly, since it forces a discrete 0/1/2-trajectory answer whose relative
size swings the derived cost-efficiency ratio arbitrarily.

**Precedent.** This is not a novel statistical construction — it follows:

- W. Detmold, M. G. Endres, *"Multiscale Monte Carlo equilibration: Pure
  Yang-Mills theory"*, Phys. Rev. D 92, 114516 (2015), arXiv:1510.04675.
- W. Detmold, M. G. Endres, *"Multiscale Monte Carlo equilibration:
  Two-color QCD with two fermion flavors"*, Phys. Rev. D 94, 114502 (2016),
  arXiv:1605.09650.

Their experimental design is this paper's, one generation earlier: a
renormalization-group-matched classical map lifts a coarse ensemble to a
fine one close to the target's thermalized distribution, which is then
rethermalized with conventional HMC and compared against cold/hot starts.
They determine rethermalization timescales via single-exponential fits of
observables approaching equilibrium, run coupled multi-exponential fits
across observables and starting distributions sharing a common exponent, and
report chi2/dof (0.6-2.1 in their study) as the fit-quality diagnostic — the
same three choices this paper's estimator makes. Citing this pins the
method to a refereed precedent rather than presenting it as ad hoc, and lets
the paper frame the diffusion-seeded approach honestly as a generative
successor to an established classical multiscale-equilibration idea.

**Numerical caveats worth a methods-section footnote, found while
implementing the estimator (full detail and regression tests in
`u2_2d/tests/test_relaxation_time.py` and CLAUDE.md's "Thermalization /
relaxation-time definition" entry):**
- A naive goodness-of-fit (delta-chi2) test alone is insufficient — verified
  on real HMC output, not merely a synthetic worry — because successive HMC
  records are autocorrelated in Monte Carlo time, which a per-record chi2
  test does not model. A second, decisive significance gate on the fitted
  tau's own chain-resampling bootstrap uncertainty is required.
- Raw per-trajectory series are now saved per coupling
  (`out-dir/series/*.npz`) specifically so a future refinement of this
  estimator can be validated by reanalysis rather than requiring the full
  HMC campaign to be rerun.

## Where this feeds the cost-efficiency result

`cost_efficiency = interval / tau_seed`, where `interval = 2 * tau_int` of an
equilibrated classical chain (`u1_2d.validate.stats.integrated_autocorrelation_time`,
the ALPHA-collaboration-style estimator already standard in this project) —
so both the numerator and the denominator of the headline ratio are now
built from the same class of estimator (a continuous fit with a bootstrap
error bar), rather than mixing a continuous autocorrelation-time estimate
against a discrete threshold-crossing count. This consistency is itself
worth stating in the methods section: the two halves of the ratio are no
longer methodologically mismatched.

## Standing rule (see CLAUDE.md)

Prefer a citable, refereed-paper methodology over an ad hoc invention
whenever one exists for the statistic being computed — stated as a general
project rule in CLAUDE.md after this thermalization-definition episode, and
worth restating here since it directly shaped this section: search the
literature before inventing a new fitting/statistics procedure, and if
deviating from a cited precedent (as this paper does, generalizing Detmold &
Endres' fixed delta-chi2 threshold to a variable-observable-count critical
value via `scipy.stats.chi2.ppf(0.95, n_params)`), state the deviation and
the reason explicitly.
