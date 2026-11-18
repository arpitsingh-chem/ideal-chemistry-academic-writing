# REPOSITORY_INVENTORY

Inventory of `arpitsingh-chem/ideal-chemistry-academic-writing` at
`7161721fce9ba9215adcdab7eff0442280bd3521` (tag `v2.3.0`), with the state after this
branch noted where relevant.

**Baseline facts:** 129 tracked files · 34 Python modules (9,370 lines) · 11 commits ·
1 branch (`main`) · 1 tag (`v2.3.0`) · 1 GitHub Actions workflow · no issues or releases
recorded at audit time.

---

## 1. Top-level

| Path | Files | Role | Assessment |
|---|---|---|---|
| `README.md` | 1 | 261 lines | Substantially accurate, nine overstatements (see `AUDIT_REPORT.md` §4) |
| `LICENSE` | 1 | CC BY 4.0 text | No copyright line; README claims MIT for code (`LICENSING_AND_PROVENANCE_AUDIT.md`) |
| `pyproject.toml` | 1 | build config, v2.3.0 | Free-text licence field; subpackage list would have missed the new packages |
| `Makefile` | 1 | dev tasks | Sound; targets verified (`help`, `test`, `check`, `pdf`, …) |
| `CITATION.cff` | 1 | citation metadata | Declared version 2.1.0 (package was 2.3.0) |
| `CONTRIBUTING.md` | 1 | contribution guide | Reasonable, pre-dates the research layer |
| `.env.example` | 1 | placeholders | No secrets |
| `CAPABILITY-REPORT.md` | 1 | v2 capability prose | Superseded by `CAPABILITY_MATRIX.md` (measured) |
| `FIELD-TEST.md`, `HARD-CASE-REPORT.md` | 2 | prior adversarial reports | **Genuine and useful**; eight and fourteen defects respectively, all fixed with regression tests |
| `.github/workflows/manuscript-lint.yml` | 1 | CI: tests + demo + guard-rails | Works; no `permissions:` block |

## 2. Engine — `paperforge/` (8,428 lines at audit time)

| Module | Lines | Responsibility | Class |
|---|---|---|---|
| `chem.py` | 537 | formula parsing, masses, adducts, DBE, yields, NMR integrals | **E** at audit (6 defects) → **A** now |
| `checks.py` | 1,071 | the 116-rule engine, scoring, report model | A |
| `project.py` | 494 | `paper.yaml` model and validation | A |
| `draft.py` | 519 | composition: abstract, sections, tables, experimental, SI | A |
| `render.py` | 508 | Markdown / LaTeX / DOCX / TXT rendering | A |
| `cli.py` | 586 | argument parsing and 20 commands | A |
| `refs.py` | 454 | Crossref verification, retraction lookup, BibTeX | A |
| `journals.py` | 444 | profiles, alias resolution, TF-IDF matcher, retargeting | A (data honesty: C) |
| `ingest.py` | 414 | folder → project | B |
| `figures.py` | 235 | dpi/size checks, TOC rendering | A |
| `schemes.py` | 188 | RDKit reaction schemes/TOC | B (RDKit absent in CI) |
| `bundle.py` | 132 | submission zip + checklist + manifest | A |
| `llm.py` | 123 | optional grounded LLM drafting | C (needs a live model) |
| `util.py` | 275 | IO, encoding, hashing | A |
| `__init__.py`, `__main__.py` | 12 | version, `python -m` | A |

**Added on this branch (28 files):** `providers/` (13 modules), `research/` (5),
`institutions/` (2), `cli_research.py`, plus 4 test suites and 11 provider fixtures.

## 3. Data — `paperforge/data/` (≈2.6 MB)

| File | Size/rows | Source | Licence | Assessment |
|---|---|---|---|---|
| `publications-openalex.json` | 1,616 works | OpenAlex works API, author-ID-verified | CC0 | Sound; **field set predates `is_oa`/`is_retracted`** (reported as "not captured", not 0) |
| `journals.csv` | 261 rows | curated | factual | `apc_usd` 0/261, `if_2024` 0/261, `url` 8/261, `limits_verified` 0/261 populated |
| `journal_limits.json` | 3 top-level keys | publisher guidance summaries | factual | 5 per-journal verified overrides + 7 family defaults + 1 generic |
| `journal-activity.csv` | 254 rows | derived from the snapshot | derived | consistent with the snapshot |
| `iiserb-bhopal-chemistry-journals.csv` | 257 rows | curated | factual | fine |
| `iiserb-bhopal-scholars.csv` | 200 rows | co-author statistics | names from the public record | column is `scholar`,`coauthored_papers` — **not** a faculty list, despite the name |
| `iiserb-bhopal-faculty.md` | 32 entries | curated | – | 32 entries vs 26 faculty in the snapshot vs "30" in the README |
| `publications-sample.json` | small | sample | – | used by tests |
| `README.md` | – | provenance note | – | accurate |

## 4. Tests — `tests/` (1,504 lines at audit time, 10 files)

| File | Lines | Covers | Assessment |
|---|---|---|---|
| `test_checks.py` | 550 | rule engine, scoring, regressions | strong |
| `test_render_refs.py` | 235 | LaTeX/Markdown rendering, references | strong |
| `test_schemes_and_stress.py` | 196 | schemes + stress inputs | good (scheme tests skip without RDKit) |
| `test_chem.py` | 180 | chemistry | **good but enshrined the defects**: it asserted `6C` must fail but never asserted `C7H7+`, hydrates or P/N/Si valences |
| `test_cli_and_bundle.py` | 172 | CLI, bundling, exit codes | good |
| `test_journals.py` | 124 | journal DB and matcher | good |
| `test_ingest.py` | 123 | ingestion | moderate |
| `test_refresh_corpus.py` | 82 | snapshot refresh | moderate |
| `test_templates_and_docs.py` | 73 | template consistency, docs | moderate |
| — | — | **no independent scientific reference values** | gap → filled by `tests/scientific/` |

Suite result at audit: **173 passed, 3 skipped** (network-marked).

## 5. Content and templates

| Path | Contents | Note |
|---|---|---|
| `docs/01–10` | v1 evidence-based guides (journals, blueprint, thesis, review, cover letter, SI, citations, data deposition, originality, free tools) | **D** — valuable prose, not executable; `docs/10` lists sources no code used until now |
| `docs/11-architecture.md` | v2 architecture | accurate for v2.3; superseded by `ARCHITECTURE.md` |
| `templates/latex/manuscript` | main.tex, SI, refs.bib, 2 figure PDFs | internally consistent after the v2 fix |
| `templates/latex/thesis` | 11 chapters, bibliography, spectra PDFs, **IISER logo** | logo is a third-party mark (see notices) |
| `templates/markdown`, `templates/word`, `templates/review` | manuscript/review templates | `manuscript-template.docx` generated by python-docx (verified) |
| `examples/demo-paper`, `examples/second-paper` | full projects + data + figures + `build_demo.py` | the strongest artifacts in the repo; 100.0 and 99.7 (`--verify-refs`) |
| `checklists/` (3), `agents/` (5), `scripts/` (7) | process aids and thin wrappers | agents/ and checklists/ are prompt/documentation material, not code |
| `scripts/refresh_corpus.py` | snapshot refresh | operates outside the package; not wired into any workflow (fixed on this branch via the research layer) |

## 6. Git history (11 commits)

`855541f` initial release → `cde2312` CITATION → `0176991` v2.1 engine → `fdfe942` remove
fabricated template data → `df1e0db` README v2 → `392cf22`/`203cf7c` CI → `5b03015` three
black-box defects (v2.2) → `b59c771` FIELD-TEST → `e20f339` hard-case audit, 14 defects
(v2.3) → `7161721` ship the journal database.

Authorship: 8 commits `Arpit Singh`, 2 `PaperForge`, 1 `IISER-Bhopal-Chemistry
<chemwriting@iiserb.ac.in>` (see `LICENSING_AND_PROVENANCE_AUDIT.md` §3).

**Trajectory:** each release fixed real, self-reported defects. That pattern is the
strongest evidence in the repository that the project is serious — and it is preserved
here: v2.4.0's own additions were adversarially tested and produced four of their own
defects (PF-007…PF-009), all fixed before release.

## 7. Automation gaps found

| Gap | Consequence | Addressed |
|---|---|---|
| No `permissions:` in the workflow | over-privileged `GITHUB_TOKEN` | ✅ `ci.yml` |
| No dependency updates | silent staleness | ✅ `dependabot.yml` |
| No packaging job | a broken wheel would ship unnoticed | ✅ `ci.yml` `package` job |
| No link checking | dead documentation links | ✅ `ci.yml` `docs` job |
| No scheduled data refresh | the snapshot ages silently | ✅ `research-sync.yml` |
| No security policy | no private disclosure route | ✅ `SECURITY.md` |
