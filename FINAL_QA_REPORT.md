# FINAL_QA_REPORT

Independent verification of the v2.4.0 work, as measured on **2026-11-18** in this
environment (Python 3.13.18, Linux). Every number here was produced by a command; nothing
is estimated. Where a check could not run, it says so and says why.

**Verdict:** the implementation is verified to the extent this environment allows.
**Two things are not verified and cannot be verified here**: the GitHub Actions workflows
have never executed (no push access), and no external provider is guaranteed stable
(the live results below are a snapshot, not a contract).

---

## 1. Test results

```
$ python3 -m pytest
360 passed, 3 skipped in 13.25s
```

Baseline before this work (tag `v2.3.0`, measured in `/home/user/origin_repo`):
**173 passed, 3 skipped in 7.11s**. No baseline test was deleted, weakened or skipped; the
inherited suite runs unchanged and still passes (173 of the 360).

| Suite | Tests | What it actually proves |
|---|---:|---|
| inherited (`tests/test_*.py`) | 173 | the v2.3 engine still behaves as documented |
| `tests/unit/test_providers_offline.py` | 26 | each adapter parses a captured real payload; no network |
| `tests/integration/test_research_pipeline.py` | 40 | schema round-trip, store migrations, dedup decisions, pipeline stages, CLI wiring, institutional dataset |
| `tests/adversarial/test_red_team.py` | 34 | hostile input: malformed JSON, HTML-behind-JSON, huge/negative counts, unicode, duplicate DOIs, timeouts, mid-run outage, corrupt fixtures, empty query, SQL-ish strings |
| `tests/scientific/test_chemistry_reference.py` | 52 | chemistry values against **outside** references (below) |
| `tests/scientific/test_table_plausibility.py` | 24 | physically impossible table values are caught (new rule) |
| `tests/regression/test_v23_contract.py` | 11 | pre-v2.4 behaviour and shipped-data integrity are pinned |

Skips (3): the `-m network` tests, which require the internet by design.

Guarantee enforced by `tests/regression`: `apc_usd` and `if_2024` must remain empty in
`journals.csv`, the journal table must stay at 261 rows and the snapshot at 1,616 works.
If any of those change, either the data was edited deliberately (update the golden) or
something corrupted it — both worth failing a build over.

---

## 2. Independent scientific verification

The values below come from **outside this codebase**: PubChem PUG-REST (a capture is
committed as `tests/fixtures/providers/pubchem_aspirin.json`), CODATA 2018 atomic masses
restated inside the test, or the published generalised DBE formula. The test recomputes
each value with its own expression — it never compares `chem.mass(x)` with `chem.mass(x)`.

| Quantity | Expected | Source | Result |
|---|---|---|---|
| aspirin monoisotopic mass | 180.0422587 | PubChem CID 2244 | pass |
| caffeine | 194.0804 | PubChem | pass |
| benzene | 78.046950 | PubChem | pass |
| C₆₀ | 720.0 | exact integer | pass |
| CuSO₄·5H₂O average mass | 249.68 | IUPAC/CODATA | pass |
| demo compound `[M+H]⁺` | 223.0866 | value in the published example | pass |
| `[M]⁺·` electron correction | 256.042676 | electron mass 0.00054857990946 | pass |
| DBE `C18H15P` / `C3H9SiCl` / `C6H5B(OH)2` | 12 / 0 / 4 | generalised formula, by hand | pass |

**What this does not prove:** that any experiment was performed. See
`docs/explanations/verification-model.md`.

---

## 3. Adversarial findings — defects found in this release

Red-teaming the *new* code found four real defects. All four are fixed, pinned by tests,
and recorded in `BUG_REGISTER.md`.

| ID | Severity | Defect | How it was found | Fix |
|---|---|---|---|---|
| PF-007 | S1 | Two distinct Zenodo DOIs merged into one record on title + first author | inspecting the SQLite store after the first live sync | two different DOIs are never `SAME`; version-suffixed DOI → `related_version` |
| PF-008 | S1 | A whitespace-only DOI produced `work_id "doi:"`, so all such records collided | `tests/adversarial` | `valid_doi()` gate before id assignment |
| PF-009 | S3 | `ResearchStore.search()` passed a JSON string to `from_dict`, raising `AttributeError` | `tests/adversarial` | decode at the boundary |
| PF-021 | S1 | A **194 % yield** in a declared CSV table scored 100.0/100 with zero findings | black-box testing while writing the tutorials | `check_table_values()` + `TAB-IMPOSSIBLE-VALUE` |

PF-021 is the most uncomfortable finding in this report and the reason it is here: the
manuscript engine used data tables only to *ground* prose numbers, never to validate them.
The failure mode — a number no experiment can produce passing silently — is precisely what
the tool is sold to prevent. Reproduction:

```bash
cp -a examples/demo-paper /tmp/pf021
python3 -c "import csv,pathlib;p=pathlib.Path('/tmp/pf021/data/scope.csv');\
r=list(csv.reader(p.open(newline='')));[x.__setitem__(4,'194') for x in r[1:] if x[0]=='3a'];\
csv.writer(p.open('w',newline='')).writerows(r)"
python3 -m paperforge check /tmp/pf021     # before: 100.0/100 · after: 97.6, TAB-IMPOSSIBLE-VALUE
```

### Red-team cases that passed without a fix

Empty query · 5,000-record payload · HTML served as JSON · `null`/negative/huge citation
counts · unicode titles, diacritics and CJK · 10,000-record ingest (idempotent, no
duplicates) · provider timeouts mid-run · every provider failing (the run reports
"incomplete, not empty" and exits 1) · corrupt fixture file · DOI with URL prefix /
uppercase / trailing punctuation · SQL-metacharacter search strings.

---

## 4. Live external verification (2026-11-18)

Network behaviour was exercised for real; this is a snapshot and providers change.

```
$ python3 -m paperforge research providers
11 provider adapter(s) implemented        (7 further sources documented as BLOCKED)

$ python3 -m paperforge research sync "photoredox catalysis" --limit 10
  OK   crossref 10 · europepmc 10 · arxiv 10 · datacite 10 · doaj 10
  FAIL openalex         rate_limited: Insufficient budget (shared per-IP daily budget)
  FAIL semantic_scholar rate_limited: Too Many Requests
found 50, unique 50, merged 0, inserted 50, updated 0, unchanged 0
note: 2 provider(s) unavailable — results are incomplete, not empty   (exit code 1)
```

Second sync, different query (`--source crossref --source datacite --limit 6`):
`12/12 inserted`. Re-running the first query: `unchanged 50`, `inserted 0` — idempotent.

Coverage after those runs: **62 works, 52 with DOI, 47 with abstract, 13 authors with
ORCID, 25 venues, 23 publishers, 0 countries / 0 institutions** (OpenAlex is the only
integrated source for affiliations and it was down — reported as 0, not guessed),
years 1977–2026, 0 merged, last sync `2026-11-18T08:29:25Z`, 4 known gaps listed.
`provider_state`: openalex 1 failure, semantic_scholar 1 failure.

Institutional dataset (offline snapshot): **1,616 works · 26 faculty · 254 venues ·
2009–2026 · 88 preprints · 2 without DOI**, and it says on every run that it is a snapshot.

Single-DOI reconciliation (`research fetch 10.1021/jacs.5c13581`): resolved by
crossref + europepmc + openalex, `verification: cross_checked`, `oa_status: closed`,
`citation_count: 6` (source crossref, dated), `retraction_status: none_known`,
`completeness: 0.9375`. DataCite returned 404 for a publisher DOI, which is reported as a
per-provider note, not an error.

**Not verified live:** ChemRxiv (403 Cloudflare challenge — documented, never worked
around), Google Scholar/Scopus/Web of Science/Dimensions/NIST WebBook/CORE (no usable
public API — documented as BLOCKED with alternatives). Unpaywall's OA lookup needs a real
contact e-mail, so its live path was only exercised at the HTTP level (`best_oa_location:
null` for a closed JACS DOI).

---

## 5. Packaging and installation

```
$ python3 -m build
paperforge-2.4.0-py3-none-any.whl   885,840 bytes
paperforge-2.4.0.tar.gz             877,381 bytes
sha256 c81e845d4bfda8d718724791cd115ad35e5bb47705e6384ced260f06f4282cce  (wheel)
sha256 eb4a6f46098f7b30448ad665899f8157433185b8db51bf82f48cdacae4f1f608  (sdist)
```

Both artefacts were installed into **separate clean venvs** and exercised from the
installed package (not the source tree):

| Check | wheel venv | sdist venv |
|---|---|---|
| `paperforge --version` → `paperforge 2.4.0` | pass | pass |
| `paperforge doctor` → chemistry engine computes 257.0505 | pass | pass |
| `paperforge research providers` → 11 adapters | pass | pass |
| `paperforge check examples/demo-paper` → 100.0 | pass | not run there |
| `paperforge institution stats` → 1,616 works | not run there | pass |
| `from paperforge.providers.registry import IMPLEMENTED, BLOCKED` → 11 / 7 | — | pass |

This matters because the previous `packages = ["paperforge"]` would have produced a wheel
that imported fine and then failed on `paperforge.providers`. The explicit package list is
what makes the test above meaningful.

Install cost: one required runtime dependency (PyYAML). `pip install paperforge` pulls
nothing else; RDKit/Pillow/python-docx/matplotlib stay optional extras.

---

## 6. Static checks

| Check | Command | Result |
|---|---|---|
| YAML parses (all workflows + dependabot + issue forms) | `yaml.safe_load` over `.github/**/*.yml` | 6/6 OK |
| Relative documentation links resolve | link scan over every `*.md` | 56 links, **0 broken** |
| Tree matches manifest | `python3 scripts/verify_manifest.py` | 217 files, **OK** |
| Secret scan | `grep -rInE 'api[_-]?key\|secret\|token\|password'` over source | no credential; only variable names and docs |
| Version consistency | `pyproject.toml` vs `paperforge.__version__` vs `CITATION.cff` | 2.4.0 / 2.4.0 / 2.4.0 |
| Data honesty guard | `tests/regression` | APC/IF columns empty, 261 rows, 1,616 works |
| **ruff** | `python3 -m ruff check` | **not run — ruff is not installed here** (CI runs it advisory) |
| mypy | — | not configured (deliberate: it is a P1 item, see `ROADMAP.md`) |

One real defect was found by the link check itself: `templates/markdown/manuscript.md`
referenced a figure that did not exist. The template now ships the figure.

---

## 7. Environment limitations and what was done instead

| Limitation | Impact | Mitigation taken |
|---|---|---|
| **No GitHub write access** — no GitHub connector is available, and no credential was requested | phases 12.1–12.3 (push, PR, release) cannot be performed here | work exists as 7 commits on a local branch, plus `dist/` artefacts; three application paths documented in §8 |
| GitHub Actions never executed | the workflow YAML is unproven on real runners | YAML validated locally, commands copied from locally-executed equivalents, link-check logic run locally |
| OpenAlex keyless budget exhausted mid-session (shared per-IP `daily+budget`) | affiliation/country coverage 0 | adapter degrades gracefully, records `retry_after`, run reports "incomplete"; a free key is the fix (owner action) |
| Semantic Scholar anonymous tier returns 429 | no S2 data in the live runs | adapter kept, tested offline, marked as rate-limited rather than broken |
| `ruff`, `PIL`, `python-docx`, `rdkit`, `matplotlib` not installed / not persistent | lint, some rendering and scheme paths not exercised here | `doctor` reports each as ✓/✗; the wheel venv install covers the runtime path; scheme tests skip cleanly |
| No LaTeX engine | PDF compilation not verified | `.tex` generation is verified; compiling is documented as a user step |

---

## 8. How to apply this work without GitHub access

The branch `feat/global-research-intelligence` (7 commits on top of `7161721`) can be moved
by any of:

```bash
# 1. bundle (preserves commits, messages and authorship)
git bundle create paperforge-2.4.0.bundle main..feat/global-research-intelligence
#    then, in a clone of the real repository:
git fetch /path/to/paperforge-2.4.0.bundle feat/global-research-intelligence
git push origin FETCH_HEAD:refs/heads/feat/global-research-intelligence

# 2. patch series (reviewable, one mail per commit)
git format-patch main..feat/global-research-intelligence -o /tmp/patches
git am /tmp/patches/*.patch

# 3. plain diff for review before any of the above
git diff main..feat/global-research-intelligence > /tmp/paperforge-2.4.0.diff
```

Nothing has been pushed, merged, tagged or published. `main` is untouched at `7161721`.

---

## 9. Acceptance table (measured, not scored)

| Requirement | Status | Evidence |
|---|---|---|
| Repository autopsy before any change | **Fully verified** | 7 reports, `main` unmodified, 173-test baseline captured first |
| Provider layer, uniform interface, 11 adapters | **Fully verified** | 26 offline tests + live runs |
| One dead provider never crashes the platform | **Fully verified** | live OpenAlex/S2 failures; 2 providers hard-failing in one run |
| Universal record with provenance, unknown→null | **Fully verified** | schema tests, `completeness()`/`missing_fields()`, live `fetch` |
| Dedupe with auditable decisions, never on title alone | **Fully verified** | 40 integration + 34 adversarial tests; PF-007 fixed; `merges` table |
| Transparent coverage metrics; no "every paper" claim | **Fully verified** | coverage report lists its own gaps and provider health |
| IISER Bhopal dataset preserved | **Fully verified** | `institution stats` 1,616 works / 26 faculty, 2 tests |
| Chemistry rules across subdisciplines | **Partially verified** | 115 rules and 52 reference-value tests cover formula/mass/HRMS/NMR/yield/valence; **no NMR/IR/UV-vis/electrochemistry/kinetics validators exist yet** (`ROADMAP.md`) |
| "No check claims experimental truth" | **Fully verified** | `docs/explanations/verification-model.md`, README limitation 8 |
| Journal intelligence without invented IF/APC | **Fully verified** | guard test: both columns empty in 261 rows; 5 verified profiles with sources |
| Architecture overhaul only where evidence demands | **Fully verified** | `ARCHITECTURE_ASSESSMENT.md`; no module moved; 173 tests unchanged |
| Pipeline: incremental + full, retries, backoff, quota, checkpoint, idempotent, dry-run, logs | **Fully verified** | integration tests; live re-run `unchanged 50`; `exit 1` on partial |
| No paywall/CAPTCHA/auth bypass | **Fully verified** | ChemRxiv 403 documented, not bypassed; `DATA_SOURCES.md` |
| Packaging, clean-venv install, checksums | **Fully verified** | §5 |
| CI workflows | **Not verified** | written and YAML-validated, never executed on a runner |
| Documentation from the implementation, Diátaxis, executed commands | **Fully verified** | every transcript captured this session; 56 links resolve; 9 false README claims removed |
| Licence/provenance corrected without rewriting history | **Partially verified** | contradiction documented, no relicensing, no history rewrite; **the licence and copyright-holder decisions are the owner's** (D-1, D-2) |
| Maintenance, roadmap, migration, state, decisions, manifest | **Fully verified** | all present; manifest verifies 217 files |
| PyPI Trusted Publishing evaluation | **Not implemented** (deliberate) | evaluated in `ROADMAP.md`; publishing requires explicit owner approval |
| Push branch / open PR / create release | **Blocked by external access** | no GitHub connector; §8 gives three paths |
| Independent verification by a second party | **Not verified** | this report is self-verification; an external reviewer has not seen the code |

### What this table deliberately does not contain

No completion percentage. A single number would have to weight "115 verified rules" against
"no NMR validator at all" and would be meaningless; the per-row status is the honest unit of
progress.

---

## 10. Residual risk after this work

1. **A user could read `100/100` as scientific validation.** Mitigated by documentation and
   by the tool's own output, but not eliminated — a human habit is not a software defect.
2. **Provider terms can change.** Only a quarterly review (`MAINTENANCE_GUIDE.md` §1)
   keeps `DATA_SOURCES.md` truthful.
3. **256 of 261 journal profiles are family defaults.** An author who skims the output
   could submit to a wrong limit. This is the highest-impact honest gap remaining.
4. **The new table check uses column names** to infer physical meaning. A table with an
   unhelpful header (`col5`) is not validated — deliberately, since guessing would be worse.
5. **`none_known` may still be misread as "this paper is safe".** Named to minimise it.
