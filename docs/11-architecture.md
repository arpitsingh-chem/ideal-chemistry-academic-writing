# 11 · Architecture of PaperForge

This document explains how the engine is put together, why each module exists, and where
to add a rule or a journal without breaking the invariants. It assumes you have read the
README.

---

## 1. Design constraints

Five constraints shaped every module.

1. **Deterministic first.** Given the same `paper.yaml`, `data/` and `figures/`, the
   output must be byte-identical. That rules out free-form generation in the core: the
   engine *assembles* prose from structured facts and refuses to invent any. An optional
   LLM pass (`llm.py`) can rewrite sentences, but it is off by default, grounded in the
   facts, and re-checked afterwards.
2. **Chemistry is a first-class type.** A formula is not a string; it is a parsed object
   with a mass, a DBE and a Hill-order canonical form. Every place that compares numbers
   goes through it.
3. **The journal is a parameter, not an assumption.** Hard-coded "300 words" would be
   wrong for most of the 261 journals in the database. Limits live in data, resolved
   through an article-type alias table.
4. **Fail loudly, score honestly.** A missing DOI, an unresolvable reference, or a mass
   that disagrees with the formula are errors with codes, not log lines. The score is a
   pure function of the findings.
5. **No network in the default path.** `check`, `draft`, `score` and `bundle` are offline.
   Crossref is a separate, cached step (`refs verify`).

---

## 2. Module map

```
paperforge/
  util.py      IO, text normalisation, sentence/word statistics, visible_text()
  chem.py      formula parsing, masses, adducts, DBE, HRMS ppm, yields, NMR integrals
  journals.py  JournalProfile, 261-row database, article-type resolution, Matcher
  project.py   the schema: Paper/Author/Compound/Figure/Table/Reference + validation
  refs.py      Crossref client, cache, retraction graph, BibTeX read/write, verify
  figures.py   dpi / physical-size / TOC audits, inventory
  schemes.py   RDKit → PIL drawing: molecule, reaction scheme, TOC graphic
  draft.py     compose(): structured facts → a Document model; prose + experimental
  render.py    Document → Markdown / LaTeX / DOCX / SI, with escaping that survives TeX
  checks.py    the 87-rule engine, Report, scoring, file-level checks (.tex/.md/.docx)
  bundle.py    submission package: PDF-ready tree, checklist, manifest, zip
  cli.py       argparse surface; every command is a thin wrapper
  llm.py       optional, grounded rewriting (never required)
```

Data flows in one direction:

```
paper.yaml ──► Project.load ──► compose ──► Document ──► render ──► build/*
      │                             │
      └── data/*.csv ───────────────┘
                                    └──► check_project ──► Report ──► score
```

`check` **re-composes** the document before checking, so what is scored is exactly what is
rendered. There is no second, drifting notion of "the manuscript".

---

## 3. `chem.py` — the part that makes the rest possible

### Formula parsing

Accepted: `C14H10N2O`, `CuSO4·5H2O`, `C6H5NO2·HCl`, coordination compounds such as
`[Cu(NH3)4]SO4` and `K4[Fe(CN)6]` (parentheses and square brackets are both group
multipliers), and `C14H10N2O+`. Organic shorthand (`Ph`, `Me`) is *not* accepted in
formulae — it belongs in names; the parser raises rather than guessing.

Outputs a `Formula(elements: dict[str, float], charge: int)` with:

* `monoisotopic_mass()` — most abundant isotope, 5-decimal constants
  (H 1.00782503207, C 12.0, N 14.0030740048, O 15.99491461956, S 31.97207100,
  Cl 34.96885268, Br 78.9183371, I 126.904473);
* `average_mass()` — IUPAC atomic weights, used for yields and mmol;
* `dbe()` — `C − H/2 + N/2 + 1 − X/2`; non-integer or negative values are errors
  (`CHEM-DBE-FRACTION`, `CHEM-DBE-NEG`), because they mean the formula is impossible.

### Adducts

`adduct_mass(formula, "[M+H]+")` subtracts the electron and adds the proton
(1.007276466621), so `C14H10NO2S` → 257.0505, not 257.0510. Adducts supported:
`[M+H]+`, `[M+Na]+`, `[M+K]+`, `[M+NH4]+`, `[M+Li]+`, `[M+Ag]+`, `[M−H]−`, `[M+Cl]−`,
`[M+Br]−`, `[M+HCOO]−`, `[M+CH3COO]−`, `[M+2H]2+`, `[M+3H]3+`, and the radical cations
`[M]+•` / `[M]−`. Author shorthand (`M+Na`, `[M+FA−H]−`, `M+•`) is canonicalised through
`ADDUCT_ALIASES`, so real-world HRMS lines are parsed without editing.

### Yield arithmetic

```
mass_g = mmol * average_mass * yield/100          (mmol in mmol → g = mmol·MW/1000)
```

`check_yield_consistency()` reports the implied yield when the three numbers disagree by
more than 2 % relative, and prints the corrected value. The v1 template's
`0.242 g / 0.86 mmol / 82 %` resolves to 109.9 %.

### NMR integrals

Parses `δ 7.90–7.82 (m, 2H, ArH)`, `(d, J = 8.8 Hz, 2H)`, `(s, 3H)`; sums `nH` and
compares with the formula's hydrogen count. Exchangeable protons are counted when the
assignment string mentions NH/OH/SH, because journals accept their absence.

---

## 4. `journals.py` — a database with a type system

`JournalProfile` carries: canonical name, aliases, publisher, family, ISSN, impact factor,
APC, OA status, scope terms, `limits` (abstract/body words, pages, figures, references,
title words) and `graphics` (TOC width/height cm, dpi, required/optional).

Article-type resolution order:

1. explicit override (`paper.article_type`);
2. alias match, longest first (`"JACS letter"` → communication);
3. family default (`exclusive_types: true` for Organic Letters pins the single type);
4. first declared type.

This is why `profile("ChemComm")` no longer resolves to *ChemInform* (v1 bug), and why
`retarget` can print a truthful diff.

### The matcher

Each captured paper becomes a TF-IDF document (chemical tokens, stop-words removed,
sublinear term frequencies). A query is scored against **each paper**, the top three similarities are
averaged, and a weak log-frequency prior is applied. Averaging top-3 rather than
concatenating a journal corpus is what stopped large journals from floating to the top
with zero matched terms (v1 behaviour: identical top-60 for unrelated topics).

---

## 5. `project.py` — the schema is the contract

`Project.load()` accepts YAML, JSON or TOML, validates types strictly (a yield of
`"ninety-four"` is rejected with a path into the document), and normalises:

* authors: names, ORCID, affiliation, CRediT roles (validated against the 14 official
  roles);
* compounds: `id`, `name`, `formula`, `mw`, `mmol`, `mass_g`, `yield_percent`,
  `hrms_calcd/found/adduct`, `nmr_1h`, `nmr_13c`, `n_13c_signals`, `ir`, `mp`, `purity`,
  `procedure`, `known` (skips characterisation in the Experimental);
* figures/tables/schemes with captions, files, dpi;
* references: DOI, key, or free-text metadata.

`citation_keys()` collects keys from three sources — the structured reference list, inline
`[key]` markers inside paragraph text, and `cites:` lists — so `REF-MISSING-KEY` catches
the paragraph someone pasted from a co-author.

`scaffold()` writes a project that scores below 60 with a readable list of what is
missing, rather than an empty folder.

---

## 6. `refs.py` — trustworthy bibliography

* Crossref lookups with `mailto` politeness, on-disk cache keyed by DOI;
* **rejects** supplement DOIs (`…​.s001`), prefers `query.title` + `query.author` with
  `filter=type:journal-article`;
* retraction detection via the `relation` graph (`is-retracted-by`), surfaced as
  `REF-RETRACTED` (critical);
* BibTeX writer that is **pure ASCII**: HTML stripped from titles, typographic dashes and
  hyphens folded, titles wrapped in `{{…}}` to survive case-changing styles, because
  T1-encoded fonts cannot render U+2010/U+2013 (the v1 template's failure mode);
* a brace-depth BibTeX reader that handles single-line entries and nested braces
  (`tests/test_render_refs.py::test_bib_file_checks` guards this).

---

## 7. `draft.py` + `render.py` — from facts to prose

`compose()` builds a `Document` with typed blocks (heading, paragraph, table, figure,
scheme, experimental, equation). Prose is assembled from the structured facts:

* abstract: five moves (context, gap, approach, result, impact), each a paragraph in
  `paper.yaml`;
* results summary: generated from `datasets:` (rows, columns, ranges) — no invented
  numbers;
* experimental: one block per compound, from `procedure`, yield in %, g and mmol;
* conclusion: explicit `narrative.conclusion` or a fallback built from the abstract's
  impact sentence;
* back matter: CRediT, COI, funding, data availability, safety, AI disclosure.

`render.tex_escape()` is the most heavily tested function in the codebase. Ordered
stashing: shorthands (`C–H`) → multi-character tokens (`¹³C`, `ν̃`) → formulae (`\ce{}`)
→ superscripts → `−1` → specials. The v1 approach lost formulae inside `\ce{@@…@@}`
placeholders; this one has a regression test for every token class.

Tables wider than five columns are wrapped in `\resizebox`; headers are humanised
(`yield_percent` → `Yield (%)`); significance markers (`a`) become `\textsuperscript{a}`.

---

## 8. `checks.py` — 87 rules, one report

`Report.add(code, severity, dimension, message, hint)` is the only way to record a
finding. `check_project()` runs eight dimension checkers, then `score()` applies weights:
structure 15, abstract 10, evidence 20, references 15, figures 10, journal 15, ethics 10,
style 5; penalties 12 / 4 / 0.5; a critical finding caps the score at 55.

Every rule has a code, a severity, a dimension, a message and an actionable hint. The
code list is stable — CI configs and editor integrations depend on it — so new behaviour
gets a new code rather than changing an old one.

`check_file()` applies the same engine to an existing `.tex`, `.md` or `.docx` that was
not produced by the engine (this is how you audit a co-author's draft). `visible_text()`
unwraps headings, captions, `\textbf{}` and `\ce{}` before analysis, so a `\paragraph{Data
availability.}` is visible to the ethics checker (v1 silently dropped it, producing
false positives).

---

## 9. `bundle.py` — the submission package

Produces `submission/` with the manuscript, SI, the figures (copied, with the dpi audit
carried into the report), references, a generated `CHECKLIST.md` (journal-specific), a
`manifest.json` (size and SHA-256 per file) and a zip. `--strict` with `--fail-on blocker|error|warn` and `--min-score` makes it usable in
CI: the bundle is refused, not silently produced, when the manuscript is not ready.

---

## 10. Invariants (do not break these)

1. `check_project` and `compose` must agree on headings and text — checks run on the
   composed document.
2. Rendered LaTeX must contain no `@@` placeholder and no raw Unicode outside `\ce{}`;
   `tests/test_render_refs.py` enforces this.
3. All numeric comparisons use `chem.py`; no ad-hoc mass arithmetic anywhere else.
4. The default path never performs network I/O.
5. Every rule has a regression test, and every bug found in the v1 corpus has a code.

---

## 11. Extending

**Add a journal** — append a row to `data/journals.csv` and, if the limits are not a
family default, an entry to `data/journal_limits.json`:

```json
"Journal of Fictional Chemistry": {
  "family": "elsevier",
  "types": {"article": {"abstract_max": 250, "body_max": 6000}},
  "graphics": {"toc_cm": [8.0, 4.0], "dpi": 300}
}
```

**Add a rule** — write a checker that appends to `Report`, give it an unused code from
`paperforge rules`, register it in the dimension function, and add a failing fixture to
`tests/test_checks.py`. A rule without a test that fails before the rule existed is not
accepted.

**Add an output format** — implement `render.to_<format>(doc, project)` and wire it into
`cli draft`. Keep escaping in `render.py`, not in the renderer.

**Add an LLM pass** — extend `llm.py` with a grounded prompt (facts in, sentences out),
then re-run `check`; a rewritten abstract that introduces a number not present in the
facts is rejected by `EVI-UNGROUNDED-ABSTRACT`.
