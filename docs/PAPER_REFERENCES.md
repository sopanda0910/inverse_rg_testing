# Reading list for the paper (compiled 2026-08-24)

Scope: the U(1) paper with the U(2) extension. This EXTENDS the verified
bibliography in `docs/u1_2d/NARRATIVE.md` §26/§26.1 — it does not replace it.
Everything already verified there is marked **[in §26.1]** and not re-argued.

Verification key:
* **[V-today]** — abstract page fetched 2026-08-24; title/authors/journal/abstract confirmed.
* **[V-26.1]** — verified 2026-08-15 in NARRATIVE §26.1.
* **[S]** — seen in search results only; metadata plausible but NOT confirmed against the record.
* **[M]** — from memory; must be checked before submission.

---

## TIER 0 — Read these first. They decide your framing.

These are the papers a referee will ask "how is this different?" about. Four of
the six are NEW since the 2026-08-15 sweep.

### 0.1 Alharazin, Panteleeva, Sun, "Diffusion Models for SU(2) Lattice Gauge Theory in Two Dimensions", PRD **114**, 014522 (2026), arXiv:2602.09045 **[V-today]**

**The single most important new reference, and it lands directly on `u2_2d`.**
Score-based diffusion for 2D SU(2) Wilson action, **quaternion parameterization**
(your `su2_2d` convention), trained at fixed beta_0 = 2.0 on 8x8, gauge-augmented,
then transferred in coupling by **rescaling the score with beta** and in volume by a
**fully convolutional U-Net** — i.e. the Zhu et al. recipe carried to non-abelian.
Validation is the **average plaquette against exact analytics, and nothing else**.

Why it matters, in both directions:
* It kills any claim that "diffusion for non-abelian gauge fields" is itself new.
* It is a near-perfect foil. 2D SU(2) has **no topological sectors** (pi_1 trivial —
  which is exactly why `su2_2d` was chosen as a warm-up and then set aside), so
  their setting cannot test the thing your paper is about. **U(2) is the smallest
  group where the field is genuinely non-abelian AND topology survives**, and your
  determinant-sector construction is the reason you can test it. Say this.
* Their |Delta| <= 0.001 on the plaquette at the training coupling, degrading to
  |Delta| < 0.06 over beta in [1,4], is exactly the *observable-level* agreement
  your §20 dissociation result says is uninformative about the density. Cite them
  at that point.

### 0.2 Komijani, Marinkovic, Turgut, "Diffusion model for SU(N) gauge theories", arXiv:2605.06134 (May 2026) **[V-today]**

SU(3) Wilson action in **2D and 4D**, implicit score matching. The load-bearing
sentence for you, verbatim from the abstract: *"For large values of inverse
coupling, accurate reverse-time integration requires predictor-corrector schemes,
for which we introduce a corrector based on Hamiltonian molecular dynamics. While
the corrector significantly improves sampling quality, it also increases the
computational cost."*

That is an **independent, non-abelian confirmation of your central negative
result** — the raw diffusion proposal is not correct at large beta and needs MCMC
machinery bolted onto it, at a cost. Your §20 design directive and your
retherm-tail measurements are the same finding reached from the other side. This
is the strongest external support your falsification framing has.

### 0.3 Vega, El-Khadra, "Sampling the Schwinger Model with Gauge-Equivariant Diffusion", arXiv:2606.27481, PAI26 (Stanford) **[V-today]**

N_f = 2 Schwinger model, U(1)-equivariant score-based model, **model likelihoods
used to obtain unbiased estimates of observables**, and a claimed reduction in
topological freezing. This is the exactness-via-likelihood route your §20/§21
measured as out of reach at O(100)-nat weight spread. You need to explain why
their route works at their scale and what your density-gap measurement predicts
about its scaling.

### 0.4 Zhu, Aarts, Wang, Zhou, Wang — the two papers **[V-26.1]**

JHEP **03** (2026) 111 / arXiv:2502.05504 (journal; the MALA-exactness claim), and
arXiv:2410.19602 (NeurIPS 2024 ML4PS workshop; the figures §25.6b digitizes).
Already handled correctly in §26.1. **Do not conflate them.** Your digitized
2.36x <Q^2> overshoot against their workshop figures is, as §24.3 says, the
sharpest single result you have — but it is a workshop version they flagged as
in-progress, so that caveat belongs in the paper body, not only in a footnote.

### 0.5 Endres, Brower, Detmold, Orginos, Pochinsky, PRD **92**, 114516 (2015), arXiv:1510.04675 **[V-26.1]**

Marked "mandatory" in §26. Still the structural ancestor: RG-matched coarse action
→ cheap coarse equilibration → **Q-preserving prolongation** → parallel
rethermalization. Your paper is this with a learned prolongator and an *exact*
transport identity in place of their measured Q correlation > 0.8. The comparison
§23.2 says has never been run — **learned prolongator vs classical smearing-based
one** — is the most obvious referee request. Decide now whether you run it or
explicitly scope it out.
Companion: Detmold, Endres, PRD **97**, 074507 (2018) **[S]**.

### 0.6 Albandea, Hernandez, Ramos, Romero-Lopez, EPJC **81**, 873 (2021), arXiv:2106.14234 **[V-26.1]** + erratum EPJC **83**, 508 (2023)

Marked "mandatory" — the winding-HMC baseline of record. Cite the erratum
alongside. Also the prior art for `docs/INSTANTON.md`'s marginal odd move.

---

## TIER 1 — New since your 2026-08-15 sweep. Read before framing the intro.

### Flow-based topology in 4D SU(3) — the state of the art you are measured against

* Bonanno, Bulgarelli, Cellini, Nada, Panfalone, Vadacchino, Verzichelli,
  "A scalable flow-based approach to mitigate topological freezing",
  arXiv:2601.20708, Lattice 2025 proceedings, PoS **518**, 034 **[S]**.
  Stochastic normalizing flow transporting an OBC-defect prior to a fully
  periodic ensemble, gauge-equivariant defect layers via masked parametric stout
  smearing, **4D SU(3)**, exact.
* "Scaling flow-based approaches for topology sampling in SU(3) gauge theory",
  JHEP **04** (2026) 051 / arXiv:2510.25704 **[S]** (same group).

These two are why a bare "we avoid topological freezing" claim will not land in
2026. Your differentiator is the *transport identity* and the *distributional
validation*, not freezing-avoidance as such.

### Wenger, "Machine learning for four-dimensional SU(3) lattice gauge theories", arXiv:2604.12416 (Apr 2026) **[V-today]**

Review. Covers flows, SNFs, diffusion, **and** the other ML-meets-RG thread:
machine-learned **RG-improved gauge actions** via gauge-equivariant CNNs, with
continuum-limit scaling for a machine-learned fixed-point action.

Useful contrast for your intro: that line learns the **action** (RG arrow
forward, into an improved coarse description); you learn the **configuration map**
(RG arrow reversed). Naming both makes your positioning look deliberate rather
than unaware.
Companion: "Machine-Learned Renormalization-Group-Improved Gauge Actions and
Classically Perfect Gradient Flows", PRL (2026) **[S]**.

### Bachtis, arXiv:2405.16288 **[V-today, ID confirmed]**

Now confirmed as *"Generating configurations of increasing lattice size with
machine learning and the inverse renormalization group"*, PoS **451**, 001 —
a review of the inverse-RG line from Ron–Swendsen–Brandt onward. §26 listed it
only as "review"; it is the closest thing to a survey of your own frame, so cite
it as such.

---

## TIER 2 — Foundations §26 flagged as absent. You need all of these.

### Diffusion / score-based generative modelling

* Anderson, "Reverse-time diffusion equation models", Stoch. Proc. Appl. **12**, 313 (1982) — already in §10 **[M]**. The time-reversal result the whole method rests on.
* Vincent, "A connection between score matching and denoising autoencoders", Neural Computation **23**, 1661 (2011) **[M]**. Denoising score matching — your training objective.
* Hyvarinen, JMLR **6**, 695 (2005) **[M]** — implicit score matching; cite if you contrast with Komijani et al. (0.2), who use it.
* Song, Ermon, "Generative modeling by estimating gradients of the data distribution", NeurIPS 2019 **[M]**.
* Ho, Jain, Abbeel, "Denoising diffusion probabilistic models", NeurIPS 2020 **[M]**.
* Song, Sohl-Dickstein, Kingma, Kumar, Ermon, Poole, "Score-based generative modeling through stochastic differential equations", ICLR 2021 **[M]**. The SDE / probability-flow ODE formulation — cite for your ODE-likelihood work (§21).
* **Karras, Aittala, Aila, Laine, "Elucidating the design space of diffusion-based generative models", NeurIPS 2022** **[M]**. *Add this one.* It is the standard reference for noise schedules and sampler step counts, and you have a measured 200-vs-18-vs-25-step result in both studies. That result currently has no methodological anchor.
* Grathwohl et al., FFJORD, ICLR 2019 **[M]** — continuous-flow likelihood, for §21.
* Neal, "Annealed importance sampling", Stat. Comput. **11**, 125 (2001) — already cited §21 **[M]**.
* **De Bortoli, Mathieu, Hutchinson, Thornton, Teh, Doucet, "Riemannian score-based generative modelling", NeurIPS 2022, arXiv:2202.02763** **[V-today, ID]**. *Add.* The general framework for diffusion on manifolds, and the heat-kernel-intractability problem it has to work around. Your U(1)/U(2) case is the tractable corner of it (wrapped Gaussian; character expansion) — a point in your favour, worth making explicitly against this reference.

### Exact 2D solutions — needed for the U(2) extension

Your `lgt.exact` character expansion on the torus needs its lineage cited:

* Migdal, Sov. Phys. JETP **42**, 413 (1975) — heat-kernel lattice action, RG-invariant **[M]**.
* Rusakov, Mod. Phys. Lett. A **5**, 693 (1990) — character expansion for 2D YM on a Riemann surface **[M]**.
* Witten, "On quantum gauge theories in two dimensions", CMP **141**, 153 (1991) **[M]**.
* Menotti, Onofri, NPB **190**, 288 (1981) — 2D lattice gauge theory exact results **[M]**.
* Gross, Witten, PRD **21**, 446 (1980); Wadia, PLB **93**, 403 (1980) **[M]** — only if you discuss the large-N transition.
* **'t Hooft, NPB 153, 141 (1979)** **[M]** — *strongly suggested*. Your U(2) = (U(1) x SU(2))/Z_2 even/odd-Q structure, and the Z_2 monodromy that makes odd dQ expensive, is a **twisted-sector / 't Hooft-flux** statement. `DESIGN.md` currently derives it from scratch. Citing 't Hooft turns a bespoke observation into a recognised structure — a large framing win for the U(2) half.

### Topological charge definition and freezing

* Del Debbio, Manca, Vicari, PLB **594**, 315 (2004) **[in §26, unverified]**.
* Schaefer, Sommer, Virotta, NPB **845**, 93 (2011) **[V-26.1]** — the Wilson-loops-decouple-from-Q result. §23.5 is right that this is the published statement of your §20 dissociation. It should be cited near the abstract, not buried.
* Luscher, Schaefer, JHEP **07** (2011) 036 **[V-26.1]** — open BCs.
* Laio, Martinelli, Sanfilippo, JHEP **07** (2016) 089 **[V-26.1]** — metadynamics.
* Hasenbusch, PRD **96**, 054504 (2017) **[V-26.1]**; Bonanno, Bonati, D'Elia, JHEP **03** (2021) 111 **[V-26.1]** — parallel tempering in boundary conditions.
* Bonanno, Nada, Vadacchino, JHEP **04** (2024) 126 **[V-26.1]** — out-of-equilibrium.
* Berg, Luscher, NPB **190**, 412 (1981) **[M]** — geometric topological charge, if you justify your Q definition.

### Critical slowing down, autocorrelation, error analysis

* Wolff, PRL **62**, 361 (1989); Swendsen, Wang, PRL **58**, 86 (1987) **[M]** — cluster algorithms: the canonical CSD remedies that do not exist for gauge fields. One sentence, but it frames why the problem is hard.
* Madras, Sokal, J. Stat. Phys. **50**, 109 (1988) **[M]**.
* **Wolff (ALPHA Collaboration), "Monte Carlo errors with less errors", Comput. Phys. Commun. 156, 143 (2004)** **[M]**. *Add.* This is the standard citation for the tau_int-aware error estimator you ported into both `u1_2d/validate/stats.py` and `u2_2d/validate/stats.py` and promoted to the validation of record. It currently has none.

### Trivializing maps and flows (the other route to the same goal)

* **Luscher, "Trivializing maps, the Wilson flow and the HMC algorithm", CMP 293, 899 (2010), arXiv:0907.5491** **[M]**. *Add* — the origin of the trivializing-map idea.
* Bacchio, Kessel, Schaefer, Vaitl, "Learning trivializing gradient flows for lattice gauge theories", PRD **107**, L051504 (2023), arXiv:2212.08469 **[V-today, ID]**. Competitive performance with ~14 parameters against ~1M for deep models on SU(3) 16^2 — a direct challenge to any "you need a big network" premise, and a natural companion to Rancon et al.'s three-parameter Ising result already in §23.1.
* Albergo, Kanwar, Racaniere, Rezende, Urban et al., "Learning trivializing flows", EPJC (2023), arXiv:2302.08408 **[S]**.
* "Non-perturbative trivializing flows for lattice gauge theories", arXiv:2410.13161 **[S]**.

### Stochastic normalizing flows / non-equilibrium

* Caselle, Cellini, Nada, Panero, "Stochastic normalizing flows as non-equilibrium transformations", JHEP **07** (2022) 015, arXiv:2201.08862 **[S]**.
* Jarzynski, PRL **78**, 2690 (1997); Crooks, PRE **60**, 2721 (1999) **[M]**.
* "Scaling of stochastic normalizing flows in SU(3) lattice gauge theory", PRD **111**, 074517 (2025) **[S]**.

### Multilevel / multigrid (your ladder's classical relatives)

* Luscher, Weisz, JHEP **09** (2001) 010 **[M]** — multilevel algorithms.
* Ce, Giusti, Schaefer, PRD **93**, 094507 (2016) **[M]**.
* Brower, Clark, Strelchenko, Weinberg — adaptive multigrid **[M]**, if you lean on the multigrid analogy.

### Neural field transformations — NTHMC, and you owe this one

`CLAUDE.md` records that `u2_2d` deliberately matches NTHMC's split
representation, plaquette orientation and determinant-phase Q so configurations
are interchangeable. That must be cited.

* Jin, "Neural network field transformation and its application in HMC", arXiv:2201.01862, Lattice 2021 **[V-today, ID]**.
* Jin et al., "Neural network gauge field transformation for 4D SU(3) gauge fields", arXiv:2405.19692 **[V-today, ID]**.
* "Neural field transformations for hybrid Monte Carlo: architectural design and scaling", arXiv:2511.02018, NeurIPS 2025 ML4PS **[V-today, ID]**.

### Gauge-equivariant architectures

* Favoni, Ipp, Muller, Schuh, "Lattice gauge equivariant convolutional neural networks", PRL **128**, 032003 (2022) **[S]**.
* Lehner, Wettig, "Gauge-equivariant neural networks as preconditioners in lattice QCD", PRD **108**, 034503 (2023), arXiv:2302.05419 **[S]**.
* "Gauge-equivariant multigrid neural networks" **[S]**; "Gauge-equivariant graph neural networks for lattice gauge theories", arXiv:2604.20797 **[S]**.

Relevant because **your score net is not gauge-equivariant** — it models `psi`,
a gauge-variant field, and you rely on gauge augmentation plus the fact that Q
and the scored observables are invariant. That is a defensible design choice but
a referee will ask, so cite the alternative and answer it in one paragraph.

### Reviews to cite once in the intro

* Cranmer, Kanwar, Racaniere, Rezende, Shanahan, "Advances in machine-learning-based sampling motivated by lattice quantum chromodynamics", Nature Reviews Physics **5**, 526 (2023) **[S]**.
* Boyda et al., Snowmass, "Applications of machine learning to lattice quantum field theory", arXiv:2202.05838 **[M]**.
* Albergo, Kanwar, Shanahan et al., "Introduction to normalizing flows for lattice field theory", arXiv:2101.08176 **[S]**.
* "Lecture notes on normalizing flows for lattice quantum field theories", arXiv:2504.18126 **[S]**.

### Diffusion-as-RG theory (your conceptual frame)

* Cotler, Rezchikov, "Renormalizing diffusion models", arXiv:2308.12355 **[in §26, unverified]**.
* Masuki, Ashida, "Generative diffusion model with inverse renormalization group flows", arXiv:2501.09064 **[V-today, ID]**.
* "Renormalization group flow, optimal transport and diffusion-based generative model", PRE **111**, 015304 (2025), arXiv:2402.17090 **[S — author list NOT checked]**.
* Wang, Aarts, Zhou, JHEP **05** (2024) 060 **[V-26.1]** — diffusion as stochastic quantization.

---

## TIER 3 — Already in §26. Verify before submission, do not re-research.

Ron/Swendsen/Brandt PRL **89**, 275701 (2002); Efthymiou/Beach/Melko PRB **99**,
075113 (2019); Bachtis/Aarts/DiRenzo/Lucini PRL **128**, 081603 (2022)
**[V-26.1]**; Bachtis PRB **110**, L140202 (2024); Rancon/Rancon/Ivek/Balog PRE
**113**, 055302 (2026) **[V-26.1]**; Albergo/Kanwar/Shanahan PRD **100**, 034515
(2019); Kanwar et al. PRL **125**, 121601 (2020); Del Debbio/Marsh Rossney/Wilson
PRD **104**, 094507 (2021); Abbott et al. arXiv:2211.07541; Nicoli et al. PRD
**108** (2023) *(article number still missing)*; Bauer/Kapust/Pawlowski/Temmen
arXiv:2412.12842; Singha/Chakrabarti/Arora PRD **108**, 074518 (2023)
**[V-26.1]**; Singha et al. arXiv:2604.10209; Bachtis arXiv:2310.12631.

Plus the un-indexed but decisive one: **Singha, Kauffmann, Jansen, Finkenrath,
Arora, Nakajima, Lattice 2026 talk** (§23.7) — ESS/N 0.5–0.7 *flat in volume*
via a Q-shift bijection, and a multilevel doubling on the same beta_c = beta_f/4
line. Chase down whether a proceedings version exists now; if it does, it is
Tier 0.

---

## What this changes about the framing

1. **"Diffusion for gauge theory" and "diffusion for non-abelian gauge theory"
   are both taken** (Zhu et al.; Alharazin et al.; Komijani et al.; Vega &
   El-Khadra). §24.3's conclusion holds and is now stronger: lead with
   **distributional falsification**, not with the sampler.
2. **You now have external corroboration for the negative result.** Komijani et
   al. need an HMD corrector at large beta; Zhu et al.'s Q histogram overshoots
   2.36x against your exact reference. Two independent groups, same failure
   direction. That converts "we measured our own model's density gap" into "this
   is a property of beta-extrapolated diffusion samplers, and here is the
   reference that reveals it."
3. **U(2) has a cleaner justification than the docs currently give.** Alharazin
   et al. did 2D SU(2) — which has no topology at all. The sentence to write is:
   *the smallest gauge group in 2D that is simultaneously non-abelian and
   topologically non-trivial is U(2), and its topology is carried entirely by an
   abelian determinant sector, which is what makes exact transport possible.*
4. **Two citations would upgrade derivations you currently present as bespoke:**
   't Hooft flux for the Z_2 parity structure, and Wolff's UWerr for the
   tau_int-aware errors that are now your validation of record.
5. **The Endres et al. comparison is the likeliest referee demand.** Learned
   prolongator vs classical. Scope it in or scope it out explicitly.
