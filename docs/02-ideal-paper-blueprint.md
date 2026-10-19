# 02 · The Ideal Chemistry Research Paper — Section-by-Section Specification

This blueprint synthesises the requirements of the 252 journals in the IISER Bhopal chemistry portfolio (261 journal profiles are maintained by the engine) (see [01-journal-requirements.md](01-journal-requirements.md)) into one actionable specification. **Follow this and you satisfy >95% of a journal's formal requirements before you even look at its guidelines page.**

---

## 0. Pre-writing (2–4 weeks before drafting)

| Task | Tool (all free) | Done |
|------|-----------------|------|
| Systematic literature review | OpenAlex API, Google Scholar, PubMed, CORE | ☐ |
| Reference manager + BibTeX/CSL | Zotero (free, Better BibTeX plugin) | ☐ |
| Journal shortlist (top 3) | `paperforge journals match "your topic"` | ☐ |
| Read 5 recent papers *from your target journal* | publisher site | ☐ |
| Copy the journal's template | ACS/RSC/Wiley template downloads | ☐ |
| Raw data + spectra + CIFs organised | lab notebook, electronic archive | ☐ |

**Rule:** decide the *story* before writing: one sentence — "We discovered/disproved/synthesised X, which matters because Y, as shown by Z."

---

## 1. Title

- **≤18 words / ~135 characters** (hard at RSC Industrial Chem. Mater.; good practice everywhere).
- State the **molecular/system-level result**, not the technique: ✗ *"Studies on the use of NMR"* → ✓ *"Chalcogen-Bonded Organic Frameworks from 1,2,5-Chalcogenadiazoles"*.
- No "Novel", "First", "Green" hype unless rigorously supported.
- Chemistry convention: systematic names or class names + key property (e.g., "Aggregation-Induced Emission", "Singlet Fission").

## 2. Authors & affiliations

- Full names, ORCID iDs (corresponding author mandatory at ACS/Wiley; recommended for all).
- Complete institutional addresses; footnote current addresses if different.
- Corresponding author with e-mail; mark with asterisk + "To whom correspondence should be addressed".
- **Authorship ethics:** every named author made a significant intellectual contribution (CRediT will ask which). No gift/honorary authors (IISER Bhopal and all analysed journals follow ICMJE/COPE norms).

## 3. Abstract (150–300 words)

Four-move structure (works for every publisher):

1. **Context** (1 sentence) — the problem and why it matters.
2. **Gap/approach** (1–2 sentences) — what was missing; what you did.
3. **Key results** (2–4 sentences) — quantitative: yields, rate constants, binding affinities, *k* values, detection limits, with units.
4. **Conclusion/impact** (1 sentence) — what the result means.

**Rules:**
- No references, no graphics, no compound numbers (Wiley forbids them in abstracts).
- No hype adjectives; no "first time" claims.
- Standalone — a reader must understand it without the paper.
- Words like "superb/excellent" banned at several ACS journals.

## 4. Keywords

4–7, lowercase, searchable, from the journal's keyword list where provided. Order: broad → specific. Example (JOC-style): *carbene transfer; gold catalysis; C–H functionalization; heterocycles; DFT calculations; mechanism*.

## 5. Graphical abstract / TOC

| Publisher | Size | Text |
|-----------|------|------|
| ACS | 3.25 × 1.75 in (8.25 × 4.45 cm) | not needed (abstract suffices) |
| RSC | 8 cm × 4 cm max, >600 dpi | 1–2 sentences, ~20 words |
| Wiley | 5 × 5 cm (Angew); 5.5 × 5.0 or 11.5 × 2.5 cm (Eur. JOC) | ≤450 characters |

Design: one panel, a **reaction scheme or structural motif + one key graph/spectrum**, minimal text; readable at thumbnail size; no re-used manuscript figures (RSC says graphic "should not be re-used").

## 6. Introduction

1. **Macro context** (2–3 sentences) — field importance, not textbook.
2. **State of the art** (1–2 paragraphs) — what is known, with key references; end each topic sentence with the citation.
3. **The gap** (explicit) — "However, … remains unexplored" — the gap must be real and recent.
4. **Your approach + what you found** (1 paragraph) — hypothesis, design logic, headline result.
5. **Significance** (1 sentence) — why it matters beyond the immediate result.

Rules: cite review(s) + primary literature in balance; **no self-citation excess** (ACS bans it); define abbreviations at first use; assume a non-specialist chemist.

## 7. Results and Discussion

The heart. Organise by **concept**, not chronologically:

- **Synthesis**: schemes with conditions, yields, substrate scope tables.
- **Characterisation**: what proves identity (NMR, HRMS, XRD, …), what proves purity (elemental analysis, melting range, HPLC trace).
- **Property/mechanism**: data → interpretation → (optional) computational support.
- **Comparison**: against literature benchmarks — table with literature values.

**Rules:**
- Figure at **first mention** (ACS); every figure/table referenced in text.
- Error bars + uncertainty analysis; correct significant figures (RSC explicit).
- Do not duplicate data in figure *and* table.
- Discuss anomalies honestly; reviewers reward it.
- Numbering: consecutive Arabic, no gaps; equations numbered as needed.

## 8. Experimental Section (the chemist's contract)

Structure:
1. **General methods** — solvents, reagents, instrumentation (model numbers), standard techniques once.
2. **Synthetic procedures** — for *every* compound: amounts (**g and mmol**), conditions, work-up, purification; yields (with basis of calculation); known compounds → cite literature + characterisation reference.
3. **Characterisation data** — per compound:
   - ¹H NMR: δ, multiplicity, J (Hz), integration
   - ¹³C NMR: δ
   - HRMS (ESI/APCI-MALDI) with calc. vs found
   - IR (selected bands), melting point
   - [α]D (chiral compounds), elemental analysis or HRMS proof of purity
   - UV–vis/fluorescence for optical studies (λmax, ε, Φ, τ)
   - Crystallographic data → CCDC number + checkCIF
   - Magnetic data → measurement conditions + Pascal's-constant correction statement
4. **Safety statement** — unexpected/new hazards emphasised; affirmative statement that hazards were considered (ACS requires).
5. **Computational details** — level of theory, basis set, software versions, coordinates (SI).

**Known-compound rule (RSC):** reference previously published characterisation data; don't re-report spectra.

## 9. Conclusion / Summary and Outlook

- Restate achievement in 2–4 sentences (not an abstract copy).
- Honest limitations + future directions (Wiley reviews require "Summary and Outlook").
- No new data, no new references.

## 10. References

- Follow the target journal style exactly (numbered ACS/Wiley, or RSC per-journal).
- **Complete entries**: authors, title (required at most ACS + several RSC journals), journal, year, volume, page/article no., DOI.
- 100% of references resolvable (test DOIs with `scripts/doi2bib.py`).
- Balanced: landmark papers + recent (last 3 years) + the journal's own papers where genuine.
- No unpublished results as citations ("in preparation" → data in SI).

## 11. Back matter

- **CRediT author-contribution statement** (Wiley mandatory; ACS recommended).
- **Acknowledgements**: funding agencies + grant numbers (mandatory for reporting compliance), facility staff, reviewers of an earlier draft.
- **Conflict-of-interest declaration** — "The authors declare no competing financial interest."
- **Data availability statement** — repository + accession numbers; never "available on request".
- **Supporting Information paragraph** — descriptive list of SI contents (ACS format).
- **AI-use disclosure** — per journal policy (Nature/Elsevier/Wiley/RSC now request or require it): e.g., "AI tools were used for grammar editing and reference formatting; no AI was used to generate data or scientific claims."

## 12. Supporting Information (see [06-supporting-information.md](06-supporting-information.md))

---

## Word-count cheat sheet

| Article type | Abstract | Body | References counted? |
|--------------|----------|------|---------------------|
| ACS Article | ≤300 | ~7,000 practical | no |
| ACS Letter | ≤150–250 | 2,200–3,000 | no |
| RSC Full Paper | 50–250 | <8,000 | no |
| RSC Communication | 50–250 | 1,500–3,000 | no |
| Angew. Communication | — (TOC text 450 chars) | **4 printed pages** | yes (counts toward pages) |
| Angew. Research Article | ≤200 | ~5,000 | no (10 printed pages) |
| Chem. Eur. J. Research Article | ≤200 | 2,500–5,600 | no |

---

*Next: [03-thesis-blueprint.md](03-thesis-blueprint.md) · [04-peer-review-blueprint.md](04-peer-review-blueprint.md)*
