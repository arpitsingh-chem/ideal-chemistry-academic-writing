# 04 · The Ideal Peer Review — Blueprint for Chemists

Peer review is the quality gate of the 252 journals in the portfolio. This guide turns you into the reviewer editors trust and authors thank — and mirrors what reviewers will do to *your* manuscripts (write papers accordingly).

---

## 1. Before you accept (the ethics gate)

- **Decline if:** conflict of interest (co-author, collaborator, competitor, same institute, financial), insufficient expertise for the core claim, or you cannot meet the deadline.
- **Confidentiality:** the manuscript is privileged; never share, cite, or mine it.
- **Double-anonymised (RSC)/single-anonymised (ACS, Wiley):** respect the model; never identify yourself in the review.

## 2. How to read a chemistry manuscript (45–90 min)

**Pass 1 — scope & integrity (10 min):**
- Does it fit the journal? (Desk-rejection criteria from `docs/01` §4.)
- Title/abstract match the claims? Hype words?
- Similarity check flags? Data availability statement present?
- Ethics statements present (human/animal/dual-use)?

**Pass 2 — chemistry check (30–60 min):**
- **Claims vs. evidence:** every headline claim must map to a figure/table. Trace the logic chain.
- **Characterisation completeness** (the #1 chemistry-review criterion): every new compound needs ¹H/¹³C NMR + HRMS + (melting point/purity); crystals need CCDC + checkCIF; yields must reconcile with quantities (g ↔ mmol ↔ %).
- **Purity proof** where properties are measured (impurities change photophysics/magnetism/catalysis!).
- **Quantitative sanity:** rate constants, binding constants, quantum yields, detection limits — recompute at least one by hand from raw numbers.
- **Mechanism logic:** do the control experiments exclude alternatives? Missing controls are Major.
- **Reference check:** are the critical prior claims cited? (Missing key references = Major; nitpicks = Minor.)
- **Reproducibility:** could a skilled researcher repeat the experiments from the Experimental section alone?

**Pass 3 — writing quality (10 min):**
- Structure, figure quality (labels legible? axes units?), SI organisation, English clarity (note: never penalise non-native phrasing harshly — comment on clarity, not accent).

## 3. Writing the review report (template: `templates/review/`)

```
Reviewer Report — Manuscript ID XXXXX
Journal: [name] | Manuscript type: [Article/Communication/…]

SUMMARY (3–5 sentences)
What the paper reports, its method, and its central claim. Show you read it.

MAJOR COMMENTS (numbered, specific)
Each one: the problem → why it matters → what to do (experiment/analysis/reanalysis/clarify).
Focus on claims-vs-evidence gaps, missing controls, characterisation gaps,
interpretation errors, reproducibility blocks.

MINOR COMMENTS (numbered, specific)
Figure legibility, numbering, SI organisation, reference additions, typos in
structures/equations (point to exact structures by number).

RECOMMENDATION
Accept / Minor revision / Major revision / Reject — with 1–2 sentence justification.
```

**Tone rules (COPE-aligned):**
- Critique the work, never the authors. No "the authors are sloppy" — say "Scheme 2 lacks yields for entries 4–6".
- Requests must be proportionate: a "Major" must be *necessary* for the claim, not nice-to-have.
- Don't request experiments for experiments' sake; don't cite your own unpublished work ("reviewer 2" clichés).

## 4. What journals expect of reviewers (from the portfolio guidelines)

- ACS/RSC/Wiley: comments on **novelty, significance, correctness, reproducibility, clarity**.
- RSC: reviewers explicitly check **data availability** and **reproducibility** of experimental/computational work.
- Wiley (Angew. Chem.): reviewers assess "whether the chemistry changes how adjacent chemists think".
- Typical workload: **2–3 reviews for a first decision; 30–40 days total** (Angew.); be prompt.

## 5. Reviewing computational/theory papers (Srinivasan/Nandi/Sharma-style work)

- Is the level of theory appropriate for the question (DFT vs post-HF vs MD; functional choice justified)?
- Basis-set convergence / k-point sampling / ensemble size stated?
- Are coordinates, input files, or a data repository link provided (RSC requires reproducibility)?
- Do conclusions overreach the model's accuracy? (e.g., energetics ±4 kcal/mol ≠ mechanistic proof at 1 kcal/mol differences.)

## 6. Reviewing crystallography (Chopra-group-style work)

- checkCIF alerts explained, not ignored (A/B-level alerts need discussion).
- H-atom treatment stated; disorder modelled and justified; R-values vs. data resolution sensible; CCDC deposition number present.
- Intermolecular-interaction claims (H-bonds, halogen/chalcogen bonds) supported by geometry + Hirshfeld surface or similar analyses where claimed.

---

*Next: [05-cover-letter-and-response.md](05-cover-letter-and-response.md)*
