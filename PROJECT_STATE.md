# PROJECT_STATE

**Last updated:** 2026-11-18
**Branch:** `feat/global-research-intelligence` (based on `7161721`, tag `v2.3.0`)
**Version in tree:** 2.4.0
**Status:** implementation complete and locally verified; **not pushed** (see §5).

This file exists so that a long project survives a session boundary. Update it whenever
work stops.

---

## 1. Where things stand

| Workstream | State | Evidence |
|---|---|---|
| Repository autopsy | ✅ complete | `AUDIT_REPORT.md`, `REPOSITORY_INVENTORY.md`, `CAPABILITY_MATRIX.md`, `BUG_REGISTER.md` |
| Chemistry fixes | ✅ complete (6 defects) | `tests/scientific/` (52 reference tests) |
| Figure checks without Pillow (PF-022) | ✅ fixed | `tests/unit/test_figures_optional.py` (5 tests) |
| Research provider layer | ✅ complete (11 adapters, 7 documented as blocked) | `paperforge/providers/`, `tests/unit/` |
| Normalised schema + provenance | ✅ complete | `paperforge/research/schema.py`, `tests/integration/` |
| Deduplication + merge audit | ✅ complete | `research/dedup.py`, `merges` table |
| Persistent store + migrations | ✅ complete | `research/store.py` |
| Sync pipeline + coverage | ✅ complete | `research/pipeline.py`, `research/coverage.py` |
| CLI (`research`, `institution`) | ✅ complete | `paperforge/cli_research.py` |
| IISER Bhopal collection preserved | ✅ complete | `paperforge/institutions/iiserb.py` |
| Table-value validation | ✅ complete (1 defect found in this release) | `tests/scientific/test_table_plausibility.py` (24 tests) |
| Test suite | ✅ 365 passed, 3 skipped | `pytest` |
| Regression guards on pre-v2.4 behaviour | ✅ complete | `tests/regression/` (11 tests) |
| Packaging (wheel + sdist) | ✅ built and installed in clean venvs | `dist/`, `FINAL_QA_REPORT.md` |
| Documentation | ✅ rewritten/added | `README.md`, `docs/`, audit set |
| Security audit | ✅ complete, no unresolved critical/high | `SECURITY_AUDIT.md` |
| Licensing audit | ✅ complete; **D-1/D-2 decided by the owner** (MIT code + CC BY 4.0 content) | `LICENSE`, `LICENSE-CODE`, `LICENSING_AND_PROVENANCE_AUDIT.md` |
| CI workflows | ✅ written (not yet executed on GitHub) | `.github/workflows/` |
| **Push to GitHub** | ⛔ **blocked — no GitHub connector in this environment** | §5 |
| **Release / tag** | ⛔ not created | awaits approval + push |
| PyPI publication | ⛔ not attempted (requires owner approval) | `ROADMAP.md` |

---

## 2. Numbers (measured, not estimated)

```
tests                365 passed, 3 skipped (network-marked)
rule codes           115
journal profiles     261  (5 per-journal verified, 256 family defaults)
provider adapters    11   (7 further sources documented as blocked)
IISER Bhopal works   1,616  · 26 faculty  · 254 venues  · 2009–2026
demo manuscripts     100.0/100 (Organic Letters) · 99.7/100 (Dalton, --verify-refs) · 94.9 offline
package artefacts    paperforge-2.4.0-py3-none-any.whl  (888,022 B)
                     paperforge-2.4.0.tar.gz            (879,583 B)
                     sha256 735468c3…96e571 (wheel) · 2b8df551…82484ed (sdist)
licence              MIT for software (LICENSE-CODE) · CC BY 4.0 for docs+data (LICENSE)
                     copyright (c) 2026 Arpit Singh · owner decision D-1/D-2, 2026-11-18
manifest             215 files · 4,235,829 B · SHA-256 per file, verifies clean
commits on branch    12 (see `git log --oneline main..HEAD`)
python               3.13.18 in this environment; CI matrix 3.10–3.13
```

---

## 3. Decisions taken (summary; full log in `DECISIONS.md`)

| # | Decision |
|---|---|
| D-01 | Do **not** rewrite the working v2 engine into the proposed directory tree; add subpackages beside it |
| D-02 | Zero new runtime dependencies (urllib, sqlite3, dataclasses) |
| D-03 | SQLite, not PostgreSQL |
| D-04 | Different DOIs ⇒ never merged, regardless of title similarity |
| D-05 | Unknown metadata is `None`; never inferred |
| D-06 | Sources without a usable public API are documented as `BLOCKED`, not faked |
| D-07 | No *unilateral* licensing change (superseded) → D-12: MIT software + CC BY 4.0 content, decided by the owner |

---

## 4. Open items

| ID | Item | Owner | Blocking? |
|---|---|---|---|
| O-1 | GitHub push / PR / release | user (access) + agent (execution) | **blocks release** |
| O-2 | ~~Licence decision~~ — **resolved 2026-11-18**: MIT software + CC BY 4.0 content/data | owner | closed |
| O-3 | ~~Legal name~~ — **resolved 2026-11-18**: "Arpit Singh", 2026 | owner | closed |
| O-4 | Verify remaining 256 journal profiles | future work | no (documented) |
| O-5 | Execute CI on GitHub to confirm the workflows | after push | no |
| O-6 | Free OpenAlex API key (restores affiliation/country coverage) | user (needs their e-mail) | no |
| O-7 | A real `PF_MAILTO` contact address for the deployed pipeline | user | no |
| O-8 | Verify the remaining 256 journal profiles | maintainer work | no (documented) |

---

## 5. Known environment limitation

This session has **no GitHub write access**: no GitHub connector is available
(`list_connector_tools("github")` → `unsupported`), and no credential was requested or
supplied. All work therefore exists as a local branch with a complete commit history, plus
ready-to-push artefacts.

The user can apply it in one of three ways (details and trade-offs in `FINAL_QA_REPORT.md`
§7):

1. `git bundle` → `git fetch` from the bundle, then push;
2. `git format-patch` series → `git am`;
3. review the diff and cherry-pick.

---

## 6. How to resume

```bash
cd paperforge_work
git log --oneline main..HEAD          # what this branch contains
python -m pytest -q                   # is it still green?
git status                            # anything uncommitted?
python -m paperforge doctor
```

Then read, in order: `FINAL_QA_REPORT.md` (what was measured, what was not) → the open
items above → `DECISIONS.md` → `FINAL_QA_REPORT.md` §8 (how to apply the branch without
GitHub access).
