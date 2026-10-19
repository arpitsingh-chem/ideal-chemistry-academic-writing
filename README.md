# PaperForge — an ideal chemistry academic-writing engine

[![tests](https://img.shields.io/badge/tests-157%20passing-brightgreen)](#verification)
[![rules](https://img.shields.io/badge/rules-90-blue)](#the-rule-set)
[![version](https://img.shields.io/badge/version-2.0.0-informational)](#)

**Turn a folder of CSV tables, figures, spectra metadata and DOIs into a submission-ready
chemistry manuscript — checked against 87 machine-readable rules, 261 journal profiles and
the chemistry itself.**

> v1 of this repository was a *documentation and template* collection: excellent prose, but
> the "checker" gave 0 errors / 0 warnings to a template containing a wrong HRMS value,
> and the journal matcher returned the same 60 journals for every query.
> **v2 is the toolkit those documents promised.** Everything below runs.

```
             ┌──────────────┐    ┌───────────────┐    ┌──────────────┐
  paper.yaml │  compose     │ →  │  verify       │ →  │  package     │
  data/*.csv │  (draft.py)  │    │  (checks.py)  │    │  (bundle.py) │
  figures/   │  MD/TeX/DOCX │    │  87 rules     │    │  zip+checklist│
  refs.bib   └──────────────┘    └───────────────┘    └──────────────┘
                     ↑                   ↑
              chem.py (masses, DBE,   journals.py (261 profiles,
              yields, NMR integrals)  per-paper TF-IDF matcher)
```

---

## 1. Install and run in 30 seconds

```bash
python3 -m pip install -e ".[figures,docx,structures]"   # RDKit optional but recommended

python3 -m paperforge doctor                             # environment + chemistry self-test
python3 -m paperforge new my-paper --journal "Organic Letters"
python3 -m paperforge check examples/demo-paper           # → 100.0/100 (A+)
python3 -m paperforge draft examples/demo-paper --format all --cover-letter --highlights
```

Requires Python ≥ 3.10. `tectonic` (or any LaTeX engine) is only needed to turn the
generated `.tex` into a PDF; `rdkit` only to draw structures from SMILES.

### The demo project is the proof

Two independent example projects prove the engine is not tuned to one subfield:

* `examples/demo-paper/` — organic photoredox (Organic Letters), 8 compounds, 100.0/100.
* `examples/second-paper/` — organometallic photophysics/bioinorganic (Dalton Transactions),
  6 Ir(III) complexes, 4 display items, 8 DOI-verified references, 99.7/100, 8-page PDF.

The first is a synthetic but *physically consistent* study — a photoredox C–H arylation of
quinoxalin-2(1H)-ones with eight products `3a`–`3h`:

| compound | R | yield / % | formula | [M+H]⁺ calcd |
|---|---|---|---|---|
| 3a | Ph | 94 | C14H10N2O | 223.0866 |
| 3b | 4-MeC6H4 | 88 | C15H12N2O | 237.1022 |
| 3c | 4-MeOC6H4 | 81 | C15H12N2O2 | 253.0972 |
| 3d | 4-ClC6H4 | 76 | C14H9ClN2O | 257.0476 |
| 3e | 4-CF3C6H4 | 72 | C15H9F3N2O | 291.0740 |
| 3f | 4-NO2C6H4 | 68 | C14H9N3O3 | 268.0717 |
| 3g | 2-naphthyl | 64 | C18H12N2O | 273.1022 |
| 3h | 3-thienyl | 61 | C12H8N2OS | 229.0430 |

From it, with **no manual editing**, `paperforge` produces: abstract → 3 sections → 2 tables
from CSV → Figures 1–2 + Scheme 1 + journal-exact TOC graphic → Experimental for all 8
compounds → SI → CRediT/COI/funding/data/safety/AI statements → cover letter → highlights →
DOCX and an 8-page PDF, at 100.0/100 with 8/8 DOIs verified.

---

## 2. Command reference

| command | what it does |
|---|---|
| `new PATH` | scaffold `paper.yaml`, `data/`, `figures/`, `refs/` |
| `ingest FOLDER --out P` | turn a research folder (CSV/figures/.bib) into a project |
| `context PATH` | print the grounded evidence pack for an LLM |
| `journals list/search/show` | 261-journal database: scope terms, IF, APC, OA, limits |
| `journals match "topic"` | per-paper TF-IDF ranking over 1,616 captured works |
| `refs verify PATH` | Crossref check every DOI; writes `refs.bib` + `references.md`; flags retractions |
| `refs add PATH DOI…` | resolve + append verified entries |
| `check PATH` / `check --file X.tex\|.md\|.docx` | the 87-rule engine, 0–100 score, grade |
| `score PATH --min 90` | CI gate (non-zero exit under the bar) |
| `draft PATH --format all` | Markdown, LaTeX, DOCX, TXT + `--cover-letter`, `--highlights` |
| `si PATH` | Supporting Information `.tex` |
| `figures PATH` | dpi/size audit + TOC dimension check |
| `scheme reaction "A>>B"` | RDKit reaction scheme with conditions, labels, yields |
| `scheme toc "A>>B" --journal "Chem. Commun."` | TOC graphic at exact cm/dpi for that journal |
| `retarget PATH --journal X` | field-by-field diff: what must change to submit elsewhere |
| `bundle PATH --strict` | submission zip + checklist + manifest; `--fail-on`, `--min-score` |
| `doctor` | environment + chemistry self-test |
| `rules` | list every rule code |

Exit codes: `0` OK · `1` score/gate failure · `2` bad input. Every command takes
`--json` where a machine-readable report makes sense.

---

## 3. What makes it chemistry-aware, not just text-aware

Text linters cannot tell you that your mass is wrong. PaperForge parses the chemistry:

* **Formula engine** — Hill order, hydrates (`CuSO₄·5H₂O` = 249.677), adducts, charged
  species; monoisotopic and average masses; DBE (detects non-integer and negative DBE).
* **HRMS arithmetic** — calcd `[M+H]⁺`, `[M+Na]⁺`, `[M−H]⁻` from the neutral formula,
  compared with the reported value at a configurable ppm window. *The v1 template's
  HRMS 256.0427 for C₁₄H₁₀NO₂S was off by 0.99 ppm and is flagged `CHEM-HRMS-CALCD`;
  the correct value is 257.0505.*
* **Yield ↔ mass ↔ mmol** — `0.242 g` claimed for 0.86 mmol at 82 % is a 109.9 % yield;
  reported as `CHEM-YIELD-MASS` with the number that *should* be there (0.181 g).
* **NMR integrals vs formula** — sums the ¹H integrals and compares with the formula's H
  count (7 H reported for a 10-H molecule is an error, not a style nit).
* **Purity/evidence grounding** — ">99 % pure" without HPLC/GC evidence, or a crystal
  structure without a CCDC number, is a blocker (`EVI-*`), not a note.
* **Reference hygiene** — unknown citation keys (`REF-MISSING-KEY`), DOIs that do not
  resolve, retracted references, duplicate entries, non-ASCII that breaks T1 fonts.

## 4. The rule set

87 codes across eight weighted dimensions:

| dimension | weight | examples |
|---|---|---|
| structure | 15 % | title length, abstract presence/split, section grammar, heading order |
| abstract | 10 % | word limit for the *resolved* article type, the five moves (context/gap/approach/result/impact) |
| evidence | 20 % | formula↔HRMS, yield↔mass, NMR H-count, CCDC, purity claims |
| references | 15 % | missing keys, unresolvable DOIs, retractions, duplicates, style |
| figures | 10 % | dpi < 300, physical width vs journal column width, TOC aspect |
| journal | 15 % | abstract/body word caps, page caps, required statements per publisher |
| ethics | 10 % | CRediT, COI, funding, data availability, AI disclosure, safety |
| style | 5 % | hype words, hedging density, sentence-length CV, unit styling |

Scoring: 100 − 12·errors − 4·warnings − 0.5·notes, any **critical** finding caps at 55.
≥ 90 submission-ready · ≥ 75 minor revision · ≥ 60 major revision. Grades A+ ≥ 95 … F.

`paperforge rules` prints the live list; `tests/` encodes the historical bugs each rule
exists to catch.

## 5. Journal knowledge

261 profiles (`data/journals.csv`, `data/journal_limits.json`) with publisher family,
verified word/page limits, TOC graphic size, OA status, APC and scope terms.
Article-type resolution is alias-first, so `"JACS letter"` → communication (2,200 words),
`"Org. Lett. paper"` → the single Organic Letters type (200-word abstract),
`"Angew. letter"` → communication (200-word abstract, 5.5 × 5.0 cm TOC graphic).

The matcher is a per-paper TF-IDF model: each captured paper is a document, the query is
scored against the best three papers of a journal, with a mild log-frequency prior
(× 0.75 below three papers). Five probe topics:

| probe | top-3 |
|---|---|
| gold catalysis | Angew. Chem. Int. Ed. 83.2 · Chem. Eur. J. 79.3 · Chem. Commun. 79.0 |
| SMM lanthanides | Dalton 95.9 · Chem. Commun. 86.4 · Inorg. Chem. 73.4 |
| POPs/CO₂ capture | Chem. Commun. 100 · Chem. Asian J. 78.7 · ACS Omega 65.4 |
| photoredox C–H arylation | Chem. Commun. 100 · Org. Lett. 71.8 |
| halogen bonds | J. Mol. Struct. 91.4 · Acta Cryst. A 89.5 · Cryst. Growth Des. 86.8 |

## 6. Evidence base

| Item | Value |
|---|---|
| Faculty analysed | 30 (all IISER Bhopal Department of Chemistry faculty) |
| Publications | **1,616** works, 2009–2026 (OpenAlex, author-ID verified) |
| Journals in which they published | **252** (253 venue names, 252 after merging the Angewandte split; ChemInform digest excluded) |
| Journal profiles maintained | **261** |
| Publisher families | ACS, RSC, Wiley-VCH, Elsevier, Springer, IUCr, preprint servers |

Top journals by captured output (Angew. Int. Ed. merges the German/International records):

| # | Journal | Papers |
|---|---|---|
| 1 | Chemical Communications | 97 |
| 2 | Chemistry – A European Journal | 83 |
| 3 | Organic Letters | 78 |
| 4 | Angewandte Chemie International Edition | 66 |
| 5 | ChemRxiv (preprints) | 61 |
| 6 | Crystal Growth & Design | 53 |
| 7 | Chemistry – An Asian Journal | 52 |
| 8 | Dalton Transactions | 41 |
| 9 | Inorganic Chemistry | 38 |
| 10 | The Journal of Organic Chemistry | 36 |

The v1 README quoted 1,707 publications / 257 journals and a top-10 that did not match
the committed data. Those numbers are corrected here; `data/publications-openalex.json`
is the single source of truth and `paperforge journals list` reads from it.

## 7. Verification

```bash
python3 -m pytest tests/ -q            # 157 passed
python3 -m paperforge check examples/demo-paper          # 100.0 / 100
python3 -m paperforge refs verify examples/demo-paper    # 8/8 verified
cd examples/demo-paper/build && tectonic -X compile manuscript.tex   # 8 pages
```

The suite includes adversarial tests (50 kB random Unicode, 2,000-row tables, 160
references, impossible formulae, negative yields, missing fields) and performance budgets
(full check + compose + render < 3 s).

## 8. Templates (now internally consistent)

The v1 LaTeX templates shipped a fabricated characterisation block: HRMS `256.0427` for
C₁₄H₁₀NO₂S (true `[M+H]⁺` = 257.0505), `0.242 g` for 0.86 mmol at 82 % (true 0.181 g), and
¹H integrals summing to 7 for a 10-H formula — while the bundled checker reported
0 errors. They have been replaced with verified values (C₁₄H₁₁NO₂S, MW 257.31, [M+H]⁺
258.0583, 0.211 g, integrals = 11 H) and the fabricated bibliography has been replaced with
eight Crossref-verified DOIs. `templates/` should contain no unverified number.

---

## Repository map

```
paperforge/          the engine (chem, journals, project, refs, figures, schemes,
                     checks, draft, render, bundle, cli, llm)
data/                journal DB, limits, 1,616-work publication corpus
templates/           LaTeX manuscript + thesis, Word, Markdown, review
docs/                evidence-based guides 01–10 and the v2 architecture (11)
examples/            demo project + journal-calibrated prose examples
checklists/          pre-submission, thesis, peer-review
scripts/             thin wrappers over paperforge (v1 scripts kept for reference)
agents/              prompt packs: draft-from-data, reviewer-2, literature triage, rebuttal
tests/               136 tests, including adversarial and regression guards
```

## Philosophy (unchanged, now enforced by code)

1. **Journals are the spec** — every limit in `data/` traces to a publisher guideline.
2. **Originality is built, not patched** — the engine assembles *your* data and prose; it
   never invents results. `llm-draft` is opt-in and grounded.
3. **Reproducibility is a chemistry requirement** — formula, mass, yield and evidence
   cross-checks are hard rules, not suggestions.
4. **AI tools are assistants, not authors** — authorship, claims and data stay human-owned.

## License & citation

Content CC BY 4.0; code MIT. If this saves you a desk rejection, cite:

```bibtex
@software{paperforge2026,
  title  = {PaperForge: an ideal chemistry academic-writing engine},
  year   = {2026},
  note   = {Evidence base: 1,616 publications, IISER Bhopal Department of Chemistry}
}
```
