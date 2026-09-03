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

## Discussion: does the method need the exact P(Q), or just sector coverage?

Started 2026-09-03, prompted by a question about whether the widening-coverage
training rungs (`configs/widening_test.yaml`, raw beta 600-2000) should carry
`sector_augment`. Relevant to `\S\ref{sec:conclusions}` (Discussion) in
`paper/current.tex`, which already states a version of this claim and should be
read alongside this section rather than duplicated.

**What `sector_augment` actually does, mechanically (`01_generate_data.py`).**
It is not part of the diffusion model's denoising process — it edits the raw
HMC-generated training *data* before the score net ever trains on it,
because that is the only point where it can matter: the net only ever learns
from what sits in the training `.pt` files, and if every configuration at a
high-beta rung is frozen at Q=0 (true HMC behavior far into the frozen
regime), the net never sees what a nonzero-Q configuration's local structure
looks like at that coupling, and has no training signal for the sectors a
coarse-input lift may later force it into via `enforce_coarse_charge`.
The mechanism: a fixed fraction (0.5, on every deployed rung with beta >=
51.75) of a rung's configurations get a deterministic instanton shift to a
charge drawn **uniformly** over {-2,-1,+1,+2} — not weighted by the true
`P(Q)` at that beta at all — followed by the exact conditional SU(2) sampler
(which absorbs the strain an odd shift leaves without touching Q) and a few
retherm sweeps within the now-fixed sector.

**So the deployed data already answers "replicate P(Q), or just widen
coverage?" — it does the latter, but only as a blend, not a clean test.**
Each high-beta rung is `seed_exact_sectors` (draws Q from the true, closed-
form P(Q) — collapsing to near-all-Q=0 this far out) plus `sector_augment`
layered on top (uniform-flat, ignoring P(Q) entirely). This is suggestive
evidence for the coverage-over-frequency hypothesis — the deployed checkpoint
already trains on data that does not match the true P(Q), and lift quality is
fine — but it is not the controlled ablation that would actually establish
it, since no checkpoint has ever been trained on pure uniform coverage with
`seed_exact_sectors` off. CLAUDE.md flags the clean ablation as queued, not
run.

**The generalization argument to full QCD, and the assumption it rests on.**
If coverage-without-frequency holds up under that ablation, the natural
extension for a theory where P(Q) is not solvable (full QCD) is: manufacture
sector coverage in the training data by *some* topology-changing mechanism
applied to existing configurations — a forced/approximate instanton, or a
PTBC ladder used purely to manufacture the global topological moves the
theory does not offer cheaply on its own — without needing that mechanism's
acceptance rate or resulting frequencies to be correct at all, only its
*reach* across sectors.

This is not a free-standing trick, though, and stating it without its
precondition would overclaim. It works here specifically because **Q is
never sampled from the trained model** — it is imposed afterward by exact
transport (`enforce_coarse_charge`), so the model's only job is to learn
correct local structure conditioned on a given sector, never the sector's own
probability. The full-QCD form of the claim is therefore a two-part package:
(i) *some* mechanism, however biased, that can visit multiple sectors while
building training data, plus (ii) an analogous *transport* step at
deployment that imposes charge on the fine lattice rather than asking the
trained model to sample it correctly. Part (ii) is exact in this paper
because U(2)'s topological charge lives entirely in an abelian determinant
sector, which blocks/transports as a plain sum (`\S\ref{app:blocking_proof}`
in `current.tex`). Whether an analogous transport — exact, or even just
unbiased — exists for 4D SU(3) is a separate, harder open question that this
argument does not answer on its own, and is the assumption the whole
generalization claim leans on.

**Framing for the paper (Discussion section):** state the coverage-over-
frequency claim as *supported but not yet isolated by a controlled ablation*,
and state the full-QCD extension as conditional on an analogous transport
mechanism existing there — not as an established generalization path.
