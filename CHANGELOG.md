# Changelog

All notable changes to this project. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
the project follows [Semantic Versioning](https://semver.org/).

Numbers in entries are measured, not aspirational. Where a claim is a *count*, the command
that produces it is given.

---

## [2.4.0] — 2026-11-18

Global research intelligence, six chemistry-engine defect fixes, honest documentation,
packaging and CI. Backward compatible: every v2.3 command, API and file format still works.

### Added

**Research intelligence layer** (`paperforge/research/`, `paperforge/providers/`)

* `WorkRecord` — a normalised schema with explicit unknown states (`None`), provenance per
  value, and a `missing_fields()`/`completeness()` pair so unknowns are visible rather than
  filled in.
* Eleven provider adapters, each verified against the live API on 2026-11-18: OpenAlex,
  Crossref, Europe PMC, arXiv, DataCite, DOAJ, Unpaywall, Semantic Scholar, ORCID, ROR,
  PubChem. `HttpClient` provides retries with exponential backoff, `Retry-After` handling,
  per-provider politeness intervals and a typed error taxonomy.
* Deduplication with an audit trail: identifier-first matching, version relationships
  (preprint / accepted manuscript / version of record / correction) kept *linked* rather
  than merged, and a documented field-precedence rule for reconciliation.
* SQLite store (schema v1, ordered migrations): idempotent upserts keyed on `work_id` +
  fingerprint, raw provider payloads stored separately from the normalised row, merge log,
  sync history and per-provider health.
* Synchronisation pipeline with per-provider failure isolation, dry-run, incremental
  `--from-year`, checkpoint rows and a coverage exporter (JSON/CSV + sidecar).
* `paperforge research {providers,search,fetch,sync,coverage,dedup,export}` and
  `paperforge institution {stats,search,faculty,journals}` command groups, all `--json`
  capable, with a documented exit-code contract (`0` ok, `1` partial, `2` bad input).
* `paperforge/institutions/iiserb.py` — the preserved IISER Bhopal collection given a
  typed, tested, offline interface (1,616 works; "not a live query and not complete" is
  printed on every run).

**Engineering**

* 47 independent scientific tests (`tests/scientific/`) whose expected values come from
  PubChem/CODATA/IUPAC rather than from this codebase.
* 34 adversarial tests (`tests/adversarial/`): daily-quota 403, 429 with `Retry-After`,
  503, DNS failure, HTML served instead of JSON, gzip bodies, 10,000-record ingestion,
  corrupt SQLite files, injection-shaped ORCIDs, CLI exit codes.
* `tests/conftest.py` fixtures and recorded live API payloads so the suite runs offline.
* PEP 639 packaging metadata, optional-dependency extras (`figures`, `docx`, `structures`,
  `dev`, `all`), explicit package list including the new subpackages.
* GitHub Actions: CI (lint, tests, packaging, install-from-wheel), dependency review,
  scheduled research synchronisation, Dependabot.
* `SECURITY.md`, `CODE_OF_CONDUCT.md`, `THIRD_PARTY_NOTICES.md`, `MANIFEST.md`, and the
  audit/QA documents listed in §"Documentation" below.

### Fixed — chemistry engine (see `BUG_REGISTER.md`, PF-001…PF-006)

* **DBE no longer reports correct organophosphorus, organosilicon and organoboron
  compounds as impossible.** Replaced the C/H/N/O/halogen expression with
  `1 + ½Σnᵢ(vᵢ−2) − ½q` over a real valence table. `C18H15P` 11.5→12, `C3H9SiCl` −1→0,
  `C6H5B(OH)2` 3.5→4; all three previously raised hard errors.
* **Charge parsing no longer eats a trailing subscript.** `C7H7+` parsed as `CH` (H count
  wrong by 7); it now parses as `C7H7` with charge +1. `[Fe(CN)6]3-` and `SO4 2-` handled.
  An ambiguous attached magnitude (`SO42-`) is *reported*, not guessed.
* **Successive hydrates no longer multiply.** `CuSO4·5H2O·2H2O` returned 429.83 g/mol
  (true heptahydrate: 285.71). Segment-wise parsing makes the two spellings agree to 1e-9.
* **Radical-ion adducts account for the electron.** `[M]⁺·`/`[M]⁻` were off by one electron
  mass (2.14 ppm at m/z 256).
* **`1H NMR` is no longer counted as a 1 H integral**, and formulae embedded in an NMR
  field are ignored by the integral parser.
* **16 elements added** to the mass tables (`Nb`, `Tc`, `Pm`, `Be`, `Ne`, `Po`, `At`, `Rn`,
  `Ra`, `Ac`, `Pa`, `Np`, `Pu`, `Am`, `Cm`, `Bk`).

### Fixed — a new defect found in this release (`BUG_REGISTER.md` PF-021)

* **Declared CSV tables are now validated for physical plausibility.** Until this release
  table cells were used only as *grounding* numbers for prose, never checked: changing a
  yield in `examples/demo-paper/data/scope.csv` from 94 % to **194 %** still produced
  0 findings and 100.0/100. A 194 % yield is not a style problem — no experiment can produce
  it. `check_table_values()` now flags, per column name, percentages outside 0–100
  (`TAB-IMPOSSIBLE-VALUE`, error), negative masses/amounts (error), temperatures below
  absolute zero (error) and negative durations (warning). Cells such as `n.d.`,
  `>99% (HPLC)` and `94 ± 2` are tolerated; columns with no known physical range are never
  guessed at. 14 regression tests in `tests/scientific/test_table_plausibility.py`, and the
  rule count rises 113 → 115.

### Fixed — documentation (see `AUDIT_REPORT.md` §4)

* Rule count stated three different ways (87 / 87 / 113). It was 113; **115** after the
  two `TAB-` codes added in the *Fixed — new defects found in this release* section.
* "261 profiles with verified limits, OA status, APC" — APC is populated in 0/261 and only
  5/261 have per-journal verification. Claim corrected; data unchanged.
* "Faculty analysed 30" — the snapshot contains 26.
* "252 journals" — 254 venue strings (251 after the documented exclusions).
* "136 tests" — 173 at audit time, 360 now.
* "code MIT" — no MIT licence exists; claim removed (open owner decision, D-1).
* `CITATION.cff` version 2.1.0 while the package was 2.3.0.
* Static shields.io badges presented as CI/test status; replaced with a real workflow badge.

### Changed

* `pyproject.toml` modernised (PEP 639 licence expression and `license-files`, explicit
  packages, extras, classifiers, URLs, ruff and pytest configuration).
* `paperforge.__version__` → `2.4.0`.

### Notes

* **No licensing change was made.** The repository remains CC BY 4.0. Re licensing code
  under MIT (the old README's claim) is the owner's decision — see
  `LICENSING_AND_PROVENANCE_AUDIT.md` D-1.
* No git history was rewritten; institutional authorship is preserved.

---

## [2.3.0] — 2026-10 (inherited)

* Shipped the journal database inside the package.
* Hard-case audit: 14 defects fixed, 8 of them silent (including two swapped yields that
  previously scored 95.2 A+).

## [2.2] — 2026-10 (inherited)

* Fixed a letter-spaced abstract produced from a string-valued field, and a missed
  retraction.

## [2.1] — 2026-10 (inherited)

* PaperForge v2.1: chemistry-aware manuscript engine — formula/HRMS/yield/NMR checks,
  113-rule scorer, journal matcher, Crossref verification, LaTeX/DOCX rendering,
  submission bundling. Replaced the v1 documentation-only toolkit.

## [1.0] — 2026 (inherited)

* Initial release: evidence-based chemistry academic-writing toolkit (documentation and
  templates).

---

## Verifying a release

```bash
python3 -m pytest                       # expect: 360 passed, 3 skipped
python3 -m paperforge check examples/demo-paper          # expect: 100.0/100
python3 -m paperforge research providers                 # expect: 11 adapters, 7 blocked
python3 -m build && pip install dist/paperforge-2.4.0-py3-none-any.whl
```
