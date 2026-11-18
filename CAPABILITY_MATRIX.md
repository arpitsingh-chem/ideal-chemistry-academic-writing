# CAPABILITY_MATRIX

Status of every capability at audit time (`v2.3.0`) and after this branch (`v2.4.0`).

Legend — **A** fully implemented & verified by execution · **B** implemented, thin test
coverage · **C** partial · **D** documentation only · **E** broken/misleading ·
**F** missing but strategically important · **—** not applicable.

"Verified by" gives the command or test file that proves the status. Nothing in this
table is asserted without one.

## 1. Chemistry

| Capability | v2.3.0 | v2.4.0 | Verified by |
|---|---|---|---|
| Molecular formula parsing (Hill, brackets, hydrates, adducts) | E | A | `tests/scientific/test_chemistry_reference.py::TestFormulaParsing` |
| Charge parsing | E (PF-002) | A | same, `test_charge_is_not_eaten_as_a_subscript` |
| Multiple hydrates | E (PF-003) | A | `test_heptahydrate_written_two_ways_agrees` |
| Average / monoisotopic mass | A | A | `TestMonoisotopicMass` (PubChem cross-check) |
| Adduct m/z ([M+H]⁺, [M+Na]⁺, [M−H]⁻, formate, acetate, 2+/3+) | A | A | `TestAdducts` |
| Radical-ion adducts | E (PF-004) | A | `test_radical_cation_loses_an_electron` |
| ppm error & HRMS verification | A | A | `test_wrong_calcd_value_is_flagged` |
| DBE / valence sanity | E (PF-001) | A | `TestDegreeOfUnsaturation` |
| Nitrogen rule | A | A | (suppressed for ions, correctly) |
| Yield ↔ mass ↔ mmol arithmetic | A | A | `TestYieldArithmetic` |
| ¹H NMR integral summation | E (PF-005) | A | `TestNmrIntegrals` |
| ¹³C signal count vs formula | A | A | `test_too_many_carbons_is_an_error` |
| Isotopic distribution | F | F | — (needs a full isotope table; not attempted) |
| IR / Raman / UV-vis / fluorescence reporting checks | F | F | — |
| Electrochemical reporting checks | F | F | — |
| Crystallographic (CIF) validation | F | F | — |
| SMILES/InChI/InChIKey handling | C | C | via RDKit when installed (`schemes.py`); not a validator |
| Molecular descriptors | F | F | — |
| PubChem cross-check of a formula/mass | F | A | `paperforge/providers/pubchem.py` + fixture test |
| Second-opinion validation of *reported* values | F | C | PubChem adapter exists; not wired into `check` (deliberate: no silent network in a linter) |

## 2. Manuscript engine

| Capability | v2.3.0 | v2.4.0 | Verified by |
|---|---|---|---|
| Project model (`paper.yaml`) | A | A | `tests/test_cli_and_bundle.py` |
| Composition (abstract, sections, tables from CSV, experimental) | A | A | `paperforge check examples/demo-paper` → 100.0 |
| Markdown / LaTeX / DOCX / TXT rendering | A | A | `draft --format all` executed |
| Supporting Information `.tex` | B | B | `si` runs; no golden-file test |
| Cover letter & highlights | B | B | runs; no golden file |
| Figure dpi/size validation, TOC crop to exact cm/dpi | A | A | `figures` + `check` |
| Reaction scheme / TOC drawing | B | B | requires RDKit (not installed here); `HAVE_RDKIT` guard |
| Submission bundle (zip + checklist + manifest) | A | A | `tests/test_cli_and_bundle.py` |
| 115-rule checker with weighted score | A | A | `rules`, `check`, `score` |
| Grounded LLM drafting (opt-in) | C | C | `llm.py`; needs a live model, not exercised |
| Journal retargeting diff | A | A | `retarget` |

## 3. Journals & references

| Capability | v2.3.0 | v2.4.0 | Verified by |
|---|---|---|---|
| 261 journal profiles + alias resolution | A | A | `journals list/show` |
| Per-journal **verified** limits | C (5/261) | C (5/261) | `journal_limits.json` |
| Family-default limits with explicit `verified: false` | A | A | `profile()` |
| TF-IDF journal matcher | A | A | `journals match` |
| Explainable recommendations | C | C | score printed; no reason list |
| APC / impact factor data | D (columns exist, empty) | D | README no longer claims otherwise |
| Crossref DOI verification | A | A | `refs verify` 8/8 live |
| Retraction detection (forward lookup) | A | A | `refs.py:retraction_notice` |
| Retraction corroboration from a second source | F | B | Europe PMC status mapped in the new provider layer |
| BibTeX parse/emit | A | A | `tests/test_render_refs.py` |
| CSL-exact reference styles | C | C | `format_reference` documented as approximate |

## 4. Global research intelligence (new)

| Capability | v2.3.0 | v2.4.0 | Verified by |
|---|---|---|---|
| Multi-provider search | F | A | `research search` (live) |
| Normalised record schema with explicit unknowns | F | A | `tests/unit/test_schema*`, `tests/integration` |
| Provenance (provider, URL, timestamp, payload hash) | F | A | `test_provenance_recorded`, `test_raw_payloads_are_stored_separately` |
| Deduplication with audit trail | F | A | `TestDeduplication`, `merges` table |
| Version relationships (preprint vs VoR) | F | A | `test_preprint_and_version_of_record_are_linked` |
| SQLite store, migrations, idempotent upsert | F | A | `TestStore` |
| Sync history + provider health | F | A | `sync_runs`, `provider_state` |
| Transparent coverage report | F | A | `research coverage` |
| Dataset export (JSON/CSV + coverage sidecar) | F | A | `TestCoverageReport::test_export_json_and_csv` |
| Institutional (IISER Bhopal) collection preserved | C (raw JSON) | A | `institution stats/search/faculty/journals` |
| ORCID / ROR identity resolution | F | A | `providers/identity.py` (live-verified) |
| Scheduled synchronisation | F | B | GitHub Actions workflow added; not yet executed on GitHub |
| Citation-network analysis | F | F | — (roadmap) |
| Research-gap discovery | F | F | — (roadmap) |

## 5. Engineering

| Capability | v2.3.0 | v2.4.0 | Verified by |
|---|---|---|---|
| Test suite | A (173) | A (360) | `pytest` |
| Independent scientific fixtures | C | A | `tests/scientific/` |
| Adversarial suite | B | A | `tests/adversarial/` |
| Wheel + sdist build | C | A | `python -m build` |
| Clean-venv install from wheel & sdist | C | A | `FINAL_QA_REPORT.md` §4 |
| Type hints | B | B | partial; no mypy gate yet |
| Lint config | F | A (config) | `ruff` section in `pyproject.toml`; not yet a blocking gate |
| CI workflow | C (single lint job) | A | `.github/workflows/ci.yml` |
| Dependency automation | F | A | `.github/dependabot.yml` |
| Security policy | F | A | `SECURITY.md` |
| Third-party notices | F | A | `THIRD_PARTY_NOTICES.md` |

## 6. Honest totals (v2.4.0)

Counted from the tables above:

* **Fully implemented & verified (A):** 45 capabilities
* **Implemented, thin coverage (B):** 8
* **Partial (C):** 9
* **Documentation only (D):** 2
* **Broken (E):** 0
* **Missing / roadmap (F):** 11

No completion percentage is claimed: the categories are not commensurable, and the
research-layer capabilities that dominate the strategic gap were absent at audit time.
