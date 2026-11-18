# BUG_REGISTER

Every defect found in the audit of `v2.3.0`, with severity, evidence, reproduction and
status. IDs are stable and referenced from the test suite (`tests/regression/`,
`tests/scientific/`).

Severity: **S1** = wrong science emitted silently · **S2** = wrong hard error on correct
input · **S3** = crash/data loss · **S4** = documentation untruth · **S5** = cosmetic.

| ID | Sev | Area | Defect | Evidence | Status |
|---|---|---|---|---|---|
| PF-001 | S2 | chem | DBE ignores P/B/Si valence → hard error on PPh₃, TMSCl, boronic acids | `chem.py:211-242`; `check_formula("C18H15P")` → `CHEM-DBE-FRACTION` | **Fixed** |
| PF-002 | S1 | chem | Charge regex eats a trailing subscript: `C7H7+` → `{C:7,H:1}` | `chem.py:122`; `parse_formula("C7H7+")` | **Fixed** |
| PF-003 | S1 | chem | Successive hydrates multiply: `CuSO4·5H2O·2H2O` → 429.83 g/mol (true 285.71) | `chem.py:139-152` | **Fixed** |
| PF-004 | S1 | chem | `[M]⁺·` / `[M]⁻` adducts ignore the electron mass (2.14 ppm at m/z 256) | `chem.py:88-90` | **Fixed** |
| PF-005 | S1 | chem | `1H NMR` label counted as a 1 H integral | `chem.py:444` | **Fixed** |
| PF-006 | S3 | chem | 16 valid elements raise "unknown element" (`Nb2O3`, `PmCl3`, …) | `MONO`/`AVG` tables | **Fixed** |
| PF-007 | S1 | research* | Dedup merged two distinct Zenodo records on title+author alone | found by `research sync` during v2.4 development | **Fixed** (new rule: different DOIs ⇒ not SAME) |
| PF-008 | S1 | research* | `WorkRecord.ensure_id()` produced `doi:` for a whitespace DOI (all such records collide) | `tests/adversarial` | **Fixed** |
| PF-009 | S3 | research* | `ResearchStore.search()` passed a JSON string where a dict was expected → AttributeError | `tests/adversarial` | **Fixed** |
| PF-010 | S4 | docs | README states three different rule counts (87, 87, 113) | `README.md:83,121` vs `rules` | **Fixed** |
| PF-011 | S4 | docs | "261 profiles with verified limits, OA status, APC" — APC present in 0/261, verified in 5/261 | `paperforge/data/journals.csv` | **Fixed** (claim corrected; data unchanged) |
| PF-012 | S4 | docs | "Faculty analysed 30" — snapshot contains 26 | `publications-openalex.json` | **Fixed** |
| PF-013 | S4 | docs | "252 journals" — 254 venue strings, 251 after documented exclusions | snapshot | **Fixed** |
| PF-014 | S4 | docs | "136 tests" vs 173 passing | `pytest` | **Fixed** |
| PF-015 | S4 | docs | Badges are static shields.io images presented as test/rule status | `README.md:3-5` | **Fixed** (replaced with a CI workflow badge + explicit note) |
| PF-016 | S4 | legal | README claims "code MIT"; no MIT licence exists | `LICENSE`, `README.md:253` | **Fixed** — owner chose the two-part split; `LICENSE-CODE` (MIT) added, `LICENSE` (CC BY 4.0) annotated, copyright line added |
| PF-017 | S5 | cli | `paperforge rules` prints codes discovered by regex over source, so a rule mentioned only in a comment would be listed | `cli.py:_all_rule_codes` | **Accepted** (documented; no false positives observed) |
| PF-018 | S5 | chem | `check_hrms` tolerance uses `max(1.0, tol_ppm)`, so a caller asking for 0.5 ppm silently gets 1.0 | `chem.py:check_hrms` | **Accepted** (deliberate floor; documented) |
| PF-019 | S4 | docs | `CITATION.cff` declared version 2.1.0 while the package was 2.3.0 | `CITATION.cff` | **Fixed** |
| PF-020 | S5 | packaging | `pyproject.toml` declared a free-text `license = {text = ...}` and omitted the new subpackages from `packages` | `pyproject.toml` | **Fixed** (PEP 639 + explicit package list) |
| PF-021 | S1 | checks | Declared CSV tables were used only as *grounding* numbers, never validated: a yield of **194 %** in `data/scope.csv` still scored 100.0/100 with zero findings | `check_project` → `check_table_values` (absent before 2.4.0); reproduction below | **Fixed** (new `TAB-IMPOSSIBLE-VALUE`, 14 tests in `tests/scientific/test_table_plausibility.py`) |
| PF-022 | S4 | figures | A missing optional dependency (Pillow) was reported as four `FIG-READ` **errors** — "cannot read image: No module named 'PIL'" with the hint "re-export the figure" — and cost a perfect demo project 4.8 points | installed wheel in a clean venv without extras: `check examples/demo-paper` → 95.2/100, 4 ✗ | **Fixed** — `FIG-NO-PIL` (info) with an actionable hint; grouped note now says "display item(s)" instead of "compounds" (5 tests, `tests/unit/test_figures_optional.py`) |
| PF-023 | S4 | ci | The CI demo gate parsed `check --json` as `["score"]` (a float), but `score` is a **nested object** — the step failed on all four matrix jobs, turning the PR red while every local run was green | first real workflow run: 4 failing checks, `ValueError: could not convert string to float: "{'score': 100.0, …}"` | **Fixed** — reads `data["score"]["score"]` (tolerating both shapes), and additionally asserts zero errors, not just a score |

\* PF-007/008/009 are defects in the **new** research layer, found by the adversarial
suite while it was being written. PF-021 and PF-022 are inherited gaps in the *manuscript*
engine, found by black-box testing while writing the tutorials and while installing the built
wheel without extras. All are recorded
here because the register is the project's defect history, not just the inherited one.

---

## Reproduction commands

```bash
# PF-001 (on tag v2.3.0)
python3 -c "from paperforge import chem; print(chem.check_formula('C18H15P'))"

# PF-002
python3 -c "from paperforge import chem; print(chem.parse_formula('C7H7+'))"

# PF-003
python3 -c "from paperforge import chem; print(chem.average_mass('CuSO4·5H2O·2H2O'))"

# PF-004
python3 -c "from paperforge import chem; m=chem.monoisotopic_mass('C14H10NO2S'); \
print(chem.ppm_error(m-chem.ELECTRON, chem.adduct_mass('C14H10NO2S','[M]+.')))"

# PF-005
python3 -c "from paperforge import chem; print(chem.parse_integrals('1H NMR delta 7.5 (s, 1H)')[0])"

# PF-006
python3 -c "from paperforge import chem; chem.parse_formula('Nb2O3')"

# PF-021 (before the fix: 0 errors, 100.0/100)
cp -a examples/demo-paper /tmp/pf021
python3 -c "import csv,pathlib;p=pathlib.Path('/tmp/pf021/data/scope.csv');r=list(csv.reader(p.open(newline='')));
[r[i].__setitem__(4,'194') for i,row in enumerate(r) if row[0]=='3a'];csv.writer(p.open('w',newline='')).writerows(r)"
python3 -m paperforge check /tmp/pf021        # now: TAB-IMPOSSIBLE-VALUE, evidence 88.0, total 97.6
```

Each now has a permanent guard in the suite:

```bash
python3 -m pytest tests/scientific/ -v        # independent reference values
python3 -m pytest tests/regression -v         # the pre-2.4.0 contract, incl. data integrity
```

---

## Open items requiring the owner

| ID | Needs | Default if no decision |
|---|---|---|
| — | none outstanding: D-1 (licence split) and D-2 (name) were decided by the owner on 2026-11-18 | — |
