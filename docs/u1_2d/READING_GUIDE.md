# Reading Guide — which sections matter, and for what

An importance labeling of `NARRATIVE.md` and `PHYSICS_WALKTHROUGH.md`, scored
on two separate axes because they do not agree:

- **Paper** — does a claim, number, figure, or citation the paper needs live
  here? Anchored to `docs/PAPER_OUTLINE.md`.
- **Explain** — do you need it to talk someone through the project out loud,
  from zero, in half an hour?

| tier | meaning |
|---|---|
| **★★★** | Load-bearing. A headline claim lives here, or you cannot tell the story without it. |
| **★★** | Mechanism or defense. Needed to answer questions and to write methods, not to state the claims. |
| **★** | Reference. Open it when writing that one subsection. |
| **○** | Archive. Process history or superseded text — read only to avoid quoting a stale number. |

**Division of labour between the two documents.** `PHYSICS_WALKTHROUGH.md`
answers *what may be claimed and what warrants it* — it is already
paper-facing prose, and its **[ALGEBRA] / [SOLVABLE] / [LEARNED] / [IMPOSED] /
[MEASURED]** tag scheme is the single most useful writing device in the repo.
`NARRATIVE.md` answers *why it is true* (every derivation) and *how we got
here* (the experimental record, the corrections, the literature). Where a topic
appears in both, draft from the walkthrough and pull the derivation from the
narrative.

---

## PHYSICS_WALKTHROUGH.md — the paper-facing document

Highest signal per page in the repo. If you read one thing before writing,
read this.

| § | Section | Paper | Explain | Why |
|---|---|---|---|---|
| — | How to read / **status-tag scheme** | ★★★ | ★★★ | The exact/learned/imposed sorting *is* the paper's honesty argument. Adopt the tags as a drafting discipline even if they never appear in the text. |
| 0 | The claim, in one paragraph | ★★★ | ★★★ | Closest thing to a finished abstract that exists. Start here. |
| A1 | Sampling, not integration | ★ | ★★★ | Standard for the paper; essential for a non-specialist. |
| A2 | Links vs plaquettes | ★★ | ★★★ | Feeds paper §2.1 conventions. |
| A3 | Gauge invariance — half the coordinates are fictitious | ★★ | ★★★ | The *architectural* framing (§3.3 motivation), not decoration. |
| A4 | Q is an exact integer | ★★★ | ★★★ | The villain. Feeds §2.3 and every topology claim. |
| A5 | 2D U(1) is exactly solvable | ★★★ | ★★★ | "The whole reason the paper can say anything the rest of the literature cannot" — paper §2.2. |
| B1 | The blocking telescope | ★★ | ★★★ | One geometric fact everything downstream rests on. |
| B2 | Coupling matching: tree level is not good enough | ★★★ | ★★ | The 13.1% / 2.8% table. Novelty claim #2 (§24.2) and paper §3.1. |
| B3 | The ladder; sector transport is an identity | ★★★ | ★★★ | **The design's justification.** ⟨Q²⟩ fixed point, 1.20271 → 1.20334. Paper §3.1 + Fig 3. |
| B4 | What that identity does **not** license | ★★★ | ★★★ | "True of the target, false of the transport." The scoping statement a referee pushes hardest on. |
| C1 | Forward process = exact heat kernel | ★★ | ★★ | Paper §3.2. The *abelian luxury* flag here is what makes §7.1 land. |
| C2 | The score is all you need | ★ | ★★ | Standard ML; one paragraph in the paper. |
| C3 | Denoising score matching | ★ | ★★ | Standard, cite Vincent. The three physics refinements (β-aware noise floor) are worth a sentence. |
| C4 | The curl head — exactly the right function class | ★★★ | ★★ | Paper §3.3. The **completeness** argument (holonomies) is the genuinely novel bit, and is the thing SU(2) broke. |
| C5 | Topology transport machinery **[IMPOSED]** | ★★★ | ★★★ | Paper §3.4 + §5.4. Carries the raw-vs-transported ⟨Q²⟩ table and the λ(σ) = 8σ² derivation. |
| D | Preamble: the two claims kept apart | ★★★ | ★★★ | The paper's structural thesis in five lines. |
| D1 | Graded on observables — **stands** | ★★★ | ★★★ | Paper §4. Contains the "upper bound on bias, and it's tight" framing and the std(z)-vs-loop-area growth. |
| D2 | Graded as a measure — **fails** | ★★★ | ★★★ | Paper §6.1–6.2. The ESS → KL replacement is called out here as the most transferable contribution — agreed. |
| D3 | Why the dissociation had to happen | ★★★ | ★★★ | Paper §6.3, the lead-figure section. Reconciles D1 and D2 before a referee has to. |
| D4 | The falsification chain + the closing control | ★★★ | ★★ | Paper §6.4. The R²_c within-arm argument is the closure; the Villain honesty note is an editorial asset. |
| E | Objections, answers, residual risk (7 rows) | ★★★ | ★★ | Referee pre-emption, with what you would concede. **Row 7 (priority vs Zhu et al.) is the single most important editorial decision in the project.** |
| F1 | The crutch ledger | ★★★ | ★★ | What does not survive to 4D SU(3). The P(Q) row was demoted 2026-08-14 — read that version, not the older framing. |
| F2 | What actually transfers | ★★ | ★★★ | Paper §9 outlook in list form. |
| F3 | The design directive, read literally (+ MALA test) | ★★★ | ★★★ | Paper §7.1–7.2. "**Must**, not *does*" — the distinction that has to survive editing. |
| F4 | The first thing SU(2) broke | ★★ | ★★ | Paper §9 outlook, concrete. |
| — | Appendix: verified identities | ★★ | ★ | Paper appendix F / reproducibility. Paste-ready. |
| — | One-page summary | ★★★ | ★★★ | Best elevator pitch in the repo. Memorize the "what to claim / what not to claim" pair. |

---

## NARRATIVE.md — derivations and the historical record

Longer, and the tiering is far less uniform: Part I is textbook, Part IV is the
experimental log, Part V is where the paper's framing was actually decided.

### Part I — the physics problem

| § | Section | Paper | Explain | Why |
|---|---|---|---|---|
| 1 | What we are trying to compute | ★ | ★★★ | The lottery framing and 1/√n. Textbook for the paper; excellent for an outsider. |
| 2 | The lattice and the U(1) testbed | ★★ | ★★★ | Conventions of record for paper §2.1. |
| 3 | Gauge invariance | ★★ | ★★★ | Same content as A3, more slowly. |
| 4 | Topology — the quantized winding number | ★★★ | ★★★ | Has the full integrality derivation (telescope + wrapping) that A4 compresses. |
| 5 | Why 2D U(1) is the right mock | ★★★ | ★★★ | Has the *derivation* of the character expansion — paper appendix A. |
| 6 | HMC — the workhorse, and how it fails | ★★★ | ★★★ | Two things the paper needs: the precise statement of HMC exactness (volume-preserving + reversible ⇒ detailed balance), and the **ΔS ≈ 2π²β/V instanton-hop derivation** that paper §5.1 is built on. |

### Part II — the inverse RG idea

| § | Section | Paper | Explain | Why |
|---|---|---|---|---|
| 7 | Blocking | ★★ | ★★★ | Carries the exact character-convolution MLE matching derivation (paper §3.1). |
| 8 | **The ladder + the ⟨Q²⟩ fixed point** | ★★★ | ★★★ | **The most valuable single section in the document.** The identity, the continuum-trajectory reading, and the "what this does and does not license" split. |

### Part III — diffusion on a torus of angles

| § | Section | Paper | Explain | Why |
|---|---|---|---|---|
| 9 | Forward process: exact heat kernel | ★★ | ★★ | Poisson-summation derivation; the SU(3) warning that §7.1 cashes in. |
| 10 | The score, and Anderson's theorem | ★ | ★★ | Standard. The SMLD update derivation is nice but appendix-grade. |
| 11 | Denoising score matching + proof sketch | ★ | ★★ | Standard, cite Vincent. The three refinements are physics and deserve a paragraph. |
| 12 | The gauge-covariant score network | ★★★ | ★★★ | Paper §3.3. The completeness argument, the FiLM topology channel (2πQ_c/V), and continuous-β conditioning. |
| 13 | **Topology transport machinery** | ★★★ | ★★★ | Paper §3.4 + Figs 5–6. σ_freeze measurements, the match-rate-vs-volume table, and the honest record that the deployed threshold is mis-set and measurably does not matter. |
| 14 | What the validated pipeline achieves | ★★★ | ★★★ | Headline numbers for paper §4.2 and §5.5. **Read §20 and §25.7 before quoting any of it** — the scoping and the τ_int-aware re-scoring both land on this section. |

### Part IV — the exactness program

| § | Section | Paper | Explain | Why |
|---|---|---|---|---|
| 15 | Importance sampling in one page | ★★ | ★★ | ESS/N ≈ e^−Var[log w] — the one formula that explains everything after it. Paper §6.1. |
| 16 | The probability-flow ODE and its likelihood | ★★ | ★★ | Paper §6.2 method. Two things matter: **the one-pass correction** (sample the ODE, don't evaluate a separately-drawn ensemble), and **the instrument validation on a solvable target**, which is what licenses every negative result. |
| 17 | Which weights: the fiber correction | ★★ | ★ | Without it a referee says the weights were broken by construction. One paragraph in the paper, but a necessary one. |
| 18 | The iterations, in order | ★★★ | ★★ | Paper §6.4, the falsification chain. Long. The durable content is the **forward/reverse-KL asymmetry** — it explains three separate failures and yields the project rule *validation likelihood is the wrong selection metric for ESS*. |
| 18.5 | The Villain control | ★★ | ★ | Paper §6.4 closure. The lesson (**prefer a within-model decomposition to a cross-arm subtraction**) is more transferable than the arm itself. Note it walks back its own earlier claim — quote only the current numbers. |
| 19 | The generalization discipline | ★★ | ★★ | Paper methods + §7.3 protocol. Six rules; the guarded checkpoint blocked 4 of 6 saves. |
| 20 | **Where this leaves the physics claims** | ★★★ | ★★★ | **Second-most valuable section.** The two-claims separation, the three scoping qualifications on "validated", the cost honesty, and the design directive. Feeds the paper's intro paragraph and all of §7. |
| 21 | Annealed importance sampling | ★★ | ★ | Paper §6.4 (one bullet) + appendix D. Heavy. What survives into the text: the floor theorem, 8-of-10 seeds, and that the divergence cause is the **surrogate's ridge**, settled by intervention. |
| 21.5 | The open problem (superseded) | ○ | ○ | Struck through by its own successor. Kept because the *reasoning* is right and the *premise* was stale. Do not quote. |
| 21.6 | **Topology without an exact P(Q): measured** | ★★★ | ★★ | This is what rewrote the crutch ledger. Transport passes at every volume; the tail cost is ≤150 trajectories and *falls* with V. Feeds paper §5.4 and §7. |
| 22 | Closure: what "finished" means | ★★ | ★★★ | Adopted / closed-with-mechanism / measured-residual, in one screen. The best status summary for a verbal explanation, and a skeleton for paper §9. |

### Part V — literature and positioning

Compiled *after* the study closed. This is where the paper's framing was decided.

| § | Section | Paper | Explain | Why |
|---|---|---|---|---|
| 23 | Background: what was already known | ★★★ | ★ | Paper §8.1 wholesale. Within it: **23.2 (Endres et al., multiscale thermalization)** is the classical ancestor and the most important omitted citation; **23.5 (Schaefer–Sommer–Virotta)** is the published physics result explaining why the dissociation had to happen — cite it in §6.3; **23.6 (Albandea et al.)** is the winding-HMC baseline and must be cited as prior art, not presented as in-house; **23.7 (Singha et al., Lattice 2026)** is the sharpest competitor and is a conference talk an arXiv sweep will miss. |
| 24 | **Honest positioning** | ★★★ | ★★★ | Paper §8.2–8.3 *and* the whole framing decision. §24.1a is the Zhu head-to-head data. §24.2 lists what remains novel, in decreasing confidence. §24.3 is the instruction for how to write the paper — follow it. |
| 25 | Objections a referee will raise | ★★★ | ★★ | Six objections with status. Feeds paper §5, §6.5, and the appendix. Note which have moved since the list was written. |
| 25.5 | Post-closure corrections | ★★★ | ★ | **Read as a trap list before quoting any table.** Five published items corrected; four appendix tables carried superseded numbers. Also the five methodological lessons ("compute the resolution floor before reading the number"). |
| 25.6 | The three owed experiments | ★★★ | ★★ | Tables S8–S10, and the entirety of paper §5.2 (the winding update is exact and nearly free), §8.2 (Zhu head-to-head), §6.5 (MALA is a local diagnostic). Also establishes that **PTBC is the wrong baseline** and that `hmc+inst` at 0.198 s per independent configuration is the number to beat. |
| 25.7 | Closing the review backlog | ★★ | ○ | Changes numbers you will otherwise quote wrong: Table S3 denominator is **38, not 35**; the τ_int-aware re-scoring moves mean \|z_exact\| 0.957 → 0.888; and the `topo_weight = 0.3` recommendation is **withdrawn**. |
| 26 | Minimum citation set | ★★★ | ○ | Bibliography skeleton, with the mandatory-citation flags. |
| 26.1 | Bibliography with verification status | ★★★ | ○ | 14 verified, 15 explicitly unverified. **Check the unverified list before submission.** Note that "Zhu et al." is two different papers. |

---

## Suggested read order

**To explain the project to someone (30 min):** WALKTHROUGH §0 → A4 → A5 →
B3 → C5 → D1 → D2 → D3 → one-page summary. That is the whole story with every
claim correctly scoped.

**To write the paper:** WALKTHROUGH end to end once, for the tags and the
defense table. Then, per paper section — §1 from NARRATIVE §20 and §24.3;
§2 from NARRATIVE §2–6; §3 from NARRATIVE §7, 8, 12, 13; §4 from NARRATIVE §14
plus §20's three qualifications plus §25.7's re-scoring; §5 from §25.6a and
§6's hop derivation; §6 from WALKTHROUGH D1–D4 and NARRATIVE §15–18, 21;
§7 from NARRATIVE §20 and WALKTHROUGH F3; §8 from NARRATIVE §23–24; §9 from
NARRATIVE §22 and WALKTHROUGH F1–F4.

**To not get burned:** NARRATIVE §25.5, §25.7, and WALKTHROUGH F1, before
quoting anything numeric.

---

## Live inconsistencies between the documents

Found while labeling. Each needs one number chosen before drafting.

1. **KL per site.** WALKTHROUGH D2 says 0.88 (16:55) and 1.02 (32:218.6);
   NARRATIVE §21 says "about 0.9–1.0"; `PAPER_OUTLINE.md` §6.2 says **1.10 and
   1.70**. NARRATIVE §21's AIS cross-check gives 1.01–1.68 (mean 1.16) at the
   extrapolation case. Three different pairs are in circulation.
2. **R²_c, the matching-residual bound.** NARRATIVE §18.5 (current) gives
   0.045 / 0.105 / 0.085 — "at most about ten percent" — and explicitly says
   this is *twice* the original campaign's 0.062 / 0.005 / 0.023. WALKTHROUGH
   D4, NARRATIVE §22, `CLAUDE.md`, and `PAPER_OUTLINE.md` §6.4 all still say
   **≤6%**. The conclusion survives either way; the quoted margin does not.
3. **Sector-mode denominator.** §25.7 regenerates Table S3 on 38 τ_int-aware
   cases; §21.5, §21.6, §25 and WALKTHROUGH F1 all still say "3 of 35" and
   "2 of 35".
4. **std(z) vs loop area.** WALKTHROUGH D1 and NARRATIVE §20: 1.093 → 1.438,
   max \|z\| 3.12 → 5.91. `PAPER_OUTLINE.md` §4.3: 1.3 → 1.4, max \|z\|
   3.3 → 4.5. Different runs.
5. **Raw charge-match rate.** Quoted as a flat **0.21** in NARRATIVE §8, §25
   and WALKTHROUGH B4/E1, but the measurement is volume-dependent —
   0.484 / 0.234 / 0.094 at L = 16 / 32 / 64 (§13). The scalar is the least
   informative form of the project's most persuasive number; prefer the
   scaling law.
6. **L = 128 training-area multiple.** "64× the training area" (NARRATIVE §14)
   vs "16× the largest" (WALKTHROUGH D1, which flags the discrepancy and
   explains it). Use 16×.

---

## Amendment — the prolongator reframing (2026-08-19)

The **Paper** column above was scored against the previous framing (a standalone
sampler, plus a negative result about density). The paper is now framed as a
**learned prolongator**: the model produces HMC starting configurations, and
correctness comes from the chain. `PAPER_OUTLINE.md` and the appendix header
were rewritten accordingly; `NARRATIVE.md` and `PHYSICS_WALKTHROUGH.md` are
unchanged and remain the record.

Re-score these rows. Everything not listed keeps its tier.

| section | was | now | why |
|---|---|---|---|
| NARRATIVE §14 (validated pipeline) | ★★★ | ★★★ | Unchanged tier, changed *use*: the seeding bullet is now the headline, the observable campaign is supporting evidence for *how close* the seed is. |
| NARRATIVE §15–18 (density program) | ★★★ | ★★★ | **Kept deliberately.** Reframed from "the exactness claim fails" to "this is exactly how wrong the seed is, and therefore how much work the tail does." The ODE likelihood is a measuring instrument, not a failed certificate. |
| NARRATIVE §18.5 (Villain control) | ★★ | ★ | Closes a competing explanation for a gap that is no longer a problem. Appendix at most. |
| NARRATIVE §19 (generalization discipline) | ★★ | ★★★ | Rises: `t_therm` claims live or die on fresh-seed, disjoint-case honesty. |
| NARRATIVE §21 (AIS) | ★★ | ○ | Orphaned. It delivers exactness via importance weights; the HMC tail delivers exactness directly. |
| NARRATIVE §21.6 (topology without exact P(Q)) | ★★★ | ★★★ | Rises in *importance*: the ≤150-trajectory sector tail that does not grow with volume is now part of the headline cost claim. |
| NARRATIVE §23.2 (Endres et al.) | (inside ★★★ §23) | **★★★, on its own** | Becomes the paper's primary related work. This is the algorithm being improved. |
| NARRATIVE §25.6a (classical baseline) | ★★★ | ★★★ | Unchanged, but `hmc+inst` at 0.198 s/independent config is now the cost denominator. |
| WALKTHROUGH D2 (graded as a measure) | ★★★ | ★★★ | Same tier, inverted reading: "this claim fails" → "this is the tail's job specification." |
| WALKTHROUGH E, row 7 (priority vs Zhu) | ★★★ | ★★ | Largely defused. Nobody in that line measures trajectories to equilibrium against a tuned classical prolongator. |
| WALKTHROUGH F3 (design directive) | ★★★ | ★★★ | Strengthened: "**must**, not *does*" becomes "does" — the paper is the demonstration. |

**New material, both of record:**

- `out/u1_2d/paper_appendix/figures/29_seed_quality.png` — trajectories to
  thermalization vs β, five arms, 35 couplings. The lead figure. Built by
  `u1_2d/scripts/50_seed_quality_figure.py`; registered in
  `30_assemble_appendix_figures.py` (29 figures tracked, `--check` passes).
- Appendix protocol **item 11** — report `t_therm` against a tuned classical
  prolongator, include a geometric control, state the budget in the cell.

**Two things now owed:**

1. ~~**The volume scan.**~~ **Run 2026-08-19** — `30_volume_scan.png`,
   `out/u1_2d/thermalization_volume/`, script `51_volume_scan_figure.py`. The
   answer is two-sided: the seed's absolute bias is flat in volume (9.7, 8.5,
   9.7 × 10⁻⁴) so it does not degrade, but `t_therm` grows 1 → 3 → 30 because
   the z-criterion's acceptance width shrinks as the spatial mean
   self-averages. **The flat-cost claim holds in β and not in V** — the
   advantage narrows 168× → 133× → 17.6×. Confound to fix if rerun: the chain
   count falls 32/16/8 across the three volumes.
2. **`appendix.tex` lags `appendix.md`.** The reframed header, the Figure 29
   caption and protocol item 11 exist only in the markdown.
