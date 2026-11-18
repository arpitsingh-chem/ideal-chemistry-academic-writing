# AUDIT_REPORT — PaperForge v2.3.0 → v2.4.0

**Audited commit:** `7161721fce9ba9215adcdab7eff0442280bd3521` (`main`, tag `v2.3.0`)
**Repository:** `arpitsingh-chem/ideal-chemistry-academic-writing`
**Audit date:** 2026-11-18
**Method:** full source read of all 25 Python modules (8,428 lines), 129 tracked files,
11 commits of history, execution of every documented command, and adversarial probing of
the chemistry engine against independently sourced reference values.

No claim in this report is based on a filename, a README statement, or a docstring.
Every finding cites the file and line, or a reproducible command.

---

## 1. Executive summary

The v2.3.0 codebase is **substantially better than its v1 ancestor** and genuinely does
most of what it claims. The manuscript engine, the journal matcher, Crossref reference
verification and the submission bundler all work: the full suite passed
(**173 passed, 3 skipped**) before any change, both demo projects score ≥ 99/100, and
`refs verify` resolved 8/8 real DOIs against Crossref during this audit.

Three classes of problem were found and are addressed on this branch:

| Class | Count | Character |
|---|---|---|
| **Silent scientific defects** in the chemistry engine | 5 | Wrong numbers produced without any warning |
| **False-positive hard errors** on correct chemistry | 2 | Correct PPh₃/TMSCl/boronic-acid formulae reported as impossible |
| **Documentation/reality divergence** | 9 | README claims contradicted by the shipped data or code |
| **Missing strategic capability** | 1 area | No global research layer: the entire evidence base was a static IISER Bhopal snapshot |

The most serious single finding is that **the DBE check emits a hard error for ordinary
organophosphorus, organosilicon and organoboron compounds** (`C18H15P`, `C3H9SiCl`,
`C6H5B(OH)2`). A tool that reports "this molecule cannot exist" for triphenylphosphine
teaches its users to ignore its errors — the worst failure mode a verification tool has.

The second most serious is that **the charge-stripping regex silently rewrites
formulae**: `C7H7+` (tropylium) parses as `CH`, a 7-fold hydrogen error, with no diagnostic.

---

## 2. Baseline measurements (before any change)

```
$ python3 -m pytest
173 passed, 3 skipped in 7.11s

$ python3 -m paperforge check examples/demo-paper
0 errors · 0 warnings · 0 notes   READINESS 100.0/100  grade A+

$ python3 -m paperforge check examples/second-paper
... references 68.0/100 ... overall 99.7/100

$ python3 -m paperforge refs verify examples/demo-paper
8 references: 8 verified, 0 unverified, 0 not found, 0 retracted, 0 duplicate DOI(s)

$ python3 -m paperforge rules | head -1
115 rule codes    (113 at audit time; two TAB- codes were added by PF-021)
```

Every one of these is reproducible on the original commit. The engine is real.

---

## 3. Silent scientific defects (chemistry engine)

### S1 — DBE crash-lands on organophosphorus, organosilicon and organoboron compounds
**File:** `paperforge/chem.py:211-242` (v2.3.0)
**Severity:** High (false hard errors on extremely common chemistry)

`ORGANIC_ELEMENTS` includes `P`, `B` and `Si`, so `dbe_applicable()` returns `True` for
them, but `dbe()` computes the halogen/nitrogen-only expression
`C − H/2 + N/2 + 1 − X/2`, which silently ignores those atoms:

```python
return c_val - h / 2 + n / 2 + 1 - x / 2      # chem.py:242
```

Measured behaviour on the audit commit:

| formula | compound | DBE computed | true DBE | emitted |
|---|---|---|---|---|
| `C18H15P` | triphenylphosphine | 11.5 | 12 | **error** `CHEM-DBE-FRACTION` |
| `C3H9SiCl` | chlorotrimethylsilane | −1.0 | 0 | **error** `CHEM-DBE-NEG` |
| `C8H20Si` | tetraethylsilane | −1.0 | 0 | **error** `CHEM-DBE-NEG` |
| `C6H5B(OH)2` | phenylboronic acid | 3.5 | 4 | **error** `CHEM-DBE-FRACTION` |

These are not exotic: TMS groups appear in a large fraction of synthetic papers.
**Fixed** (v2.4.0) with the generalised expression
`DBE = 1 + ½Σnᵢ(vᵢ−2) − ½q` over a real valence table.

### S2 — Charge stripping corrupts the formula
**File:** `paperforge/chem.py:122`
```python
s = re.sub(r"(\^?\d*[+-]+)$", "", s)          # strip charge
```
The `\d*` is greedy, so for `C7H7+` it removes `7+` and leaves `C7H`:

```
$ python3 -c "from paperforge.chem import parse_formula; print(parse_formula('C7H7+'))"
{'C': 7, 'H': 1}          # tropylium, H count wrong by 7
```

Every downstream value — molar mass, exact mass, DBE, NMR integral check — is then
wrong, silently. **Fixed**: `split_charge()` reads a magnitude only when it follows `)`,
`]` or whitespace; `C7H7+` → `C7H7` with q = +1; `[Fe(CN)6]3-` → `[Fe(CN)6]` with q = −3.

### S3 — Successive hydrates are multiplied together
**File:** `paperforge/chem.py:139-152` (the `if mult > 1:` branch)
The hydrate multiplier is applied to *the whole remaining string*, so
`CuSO4·5H2O·2H2O` is read as 5 × (H2O·2H2O) = H30O19:

```
$ python3 -c "from paperforge.chem import average_mass as m; print(m('CuSO4·5H2O·2H2O'))"
429.827        # correct value for a heptahydrate is 285.71
```
A 50 % mass error, with no warning. **Fixed** by segment-wise parsing; the two spellings
of copper(II) sulfate heptahydrate now agree to 1e-9.

### S4 — Radical-ion adducts ignore the electron mass
**File:** `paperforge/chem.py:88-90`
```python
"[M]+": (0.0, 1), "[M]+.": (0.0, 1), "[M]-": (0.0, 1),
```
`[M]⁺·` is the molecule minus one electron. The shift is small (0.00055 Da) but not
negligible: **2.14 ppm at m/z 256**, i.e. outside the 1–2 ppm window many journals now
expect, and inside a 5 ppm window only by luck.

```
code: 256.043225    true [M]+·: 256.042676    Δ = +2.14 ppm
```
**Fixed**: `[M]+`/`[M]+.` = −1 e⁻, `[M]-` = +1 e⁻.

### S5 — `1H NMR` counted as a proton integral
**File:** `paperforge/chem.py:444` (`parse_integrals`)
The regex `(?<![\d.])(\d{1,2})\s*H\b` matches the experiment label itself, so a field
beginning `1H NMR (400 MHz …)` gains a phantom proton:

```
"HRMS for C14H10NO2S, 1H NMR δ 7.5 (s, 1H)"   ->  2   (should be 1)
```
Because `check_nmr` compares this total with the formula's hydrogen count, the phantom
proton can mask (or create) a real integral error. **Fixed**: experiment labels and
embedded formulae are stripped before summation.

### S6 — Elements missing from the mass tables
`Nb`, `Tc`, `Pm`, `Be`, `Ne`, `Po`, `At`, `Rn`, `Ra`, `Ac`, `Pa`, `Np`, `Pu`, `Am`, `Cm`,
`Bk` raise `unknown element` for valid formulae (`Nb2O3` failed). **Fixed** — 16 elements
added with CODATA/IUPAC values.

---

## 4. Documentation versus reality

Each row was verified by executing the documented behaviour.

| # | README claim (v2.3.0) | Measured reality | Verdict |
|---|---|---|---|
| D1 | "the 87-rule engine" (line 83) and "87 codes across eight dimensions" (line 121) | `paperforge rules` prints **113** | Contradiction inside one README (the badge on line 3 says 113) |
| D2 | "261 profiles … with **verified** word/page limits … **OA status, APC** and scope terms" (line 143) | `apc_usd` populated in **0/261** rows; `if_2024` **0/261**; `url` **8/261**; `limits_verified` **0/261**; only **5 of 261** journals have a per-journal verified override (all others inherit a family default) | Overstated |
| D3 | "jurnals … scope terms, **IF**, **APC**, OA, limits" (command table) | IF and APC columns are empty for every journal | Misleading |
| D4 | "Faculty analysed **30**" (line 164) | the snapshot names **26** distinct faculty; `faculty.md` lists 32 entries; no file contains 30 | Unsupported |
| D5 | "**252** journals … 253 venue names" (line 166) | 254 distinct non-empty venue strings (251 after excluding `Unknown`, `ChemInform` and merging the two Angewandte spellings) | Off by one |
| D6 | "Content CC BY 4.0; **code MIT**" (line 253) | `LICENSE` is CC BY 4.0 only; there is no MIT text and no MIT grant | **Licensing defect** |
| D7 | `tests/` "**136 tests**" (line 239) | 173 passed + 3 skipped at audit time | Stale |
| D8 | badges "tests-173 passing", "rules-115" | static shields.io images, not CI status | Not evidence of CI state |
| D9 | "every limit in `paperforge/data/` traces to a publisher guideline" (Philosophy §1) | true for 5 journals; 256 inherit family defaults marked `verified: false` | Overstated |

None of these break the software. All of them break trust in the documentation, which for
a scientific tool is the same thing.

---

## 5. Strategic gap — the research layer

The repository's "research intelligence" was, at audit time, entirely a **static snapshot**:
`paperforge/data/publications-openalex.json` (1,616 works, 30 faculty query, 2009–2026),
read by the journal matcher. That is a legitimate and well-executed institutional dataset,
but it is:

* not updatable without re-running an out-of-repo script;
* not queryable outside the journal matcher;
* single-institution, single-source, single-discipline-weighted;
* presented in the README as though it were general journal intelligence.

There was **no** provider abstraction, no normalised record schema, no provenance model,
no deduplication, no coverage reporting, and no mechanism for a second data source.
This is the gap v2.4.0 closes (see `ARCHITECTURE.md`, `DATA_SOURCES.md`,
`GLOBAL_RESEARCH_COVERAGE.md`).

---

## 6. Capability classification (audit-time)

Full matrix in `CAPABILITY_MATRIX.md`. Summary:

* **A — fully implemented and verified by execution (14):** formula parse/Hill order,
  mono/average mass, adduct m/z, ppm comparison, yield↔mass, journal DB + alias
  resolution, TF-IDF journal matcher, Crossref DOI verification, retraction forward
  lookup, BibTeX round-trip, figure dpi check, TOC dimension rendering, Markdown/LaTeX/
  DOCX rendering, submission bundling.
* **B — implemented, inadequately tested at audit time (5):** ingest, DOCX generation,
  scheme drawing (needs RDKit, absent from CI), Si generation, cover letter.
* **C — partially implemented (3):** "verified journal limits" (5/261), retraction
  *forward* lookup (works, but only Crossref; no Europe PMC corroboration at audit time),
  NLM/ACS reference formatting (approximate, not CSL).
* **D — documentation only (2):** docs 01–10 are guidance from v1, not executable;
  `docs/10-free-tools-and-apis.md` lists sources no code touches.
* **E — broken or misleading (2):** the three chemistry DBE/charge defects above, and
  the README numbers D1–D9.
* **F — missing but strategically important (4):** global research providers, normalised
  record schema, provenance/dedup, coverage reporting.

---

## 7. What this branch changes

| Area | Change | Evidence |
|---|---|---|
| Chemistry | 6 defects fixed (S1–S6), 47 new independent reference tests | `tests/scientific/` |
| Research | 11 provider adapters, normalised schema, dedup, SQLite store, coverage | `paperforge/providers/`, `paperforge/research/` |
| CLI | `research` and `institution` command groups | `paperforge/cli_research.py` |
| Packaging | PEP 639 metadata, wheel + sdist, clean-venv install verified | `dist/`, `FINAL_QA_REPORT.md` |
| Docs | README rewritten against measured behaviour; 9 inconsistencies corrected | `README.md`, `CHANGELOG.md` |
| Tests | 173 → 360 passing (+3 network-marked skips) | `FINAL_QA_REPORT.md` |

The **IISER Bhopal collection is preserved** and given a typed, tested interface
(`paperforge/institutions/iiserb.py`); nothing in the snapshot was deleted or rewritten.

---

## 8. Findings deliberately **not** fixed

| Finding | Why not | What is documented instead |
|---|---|---|
| 256/261 journals lack per-journal verified limits | Verifying them requires reading each publisher's author guidelines; inventing values is explicitly forbidden | The profile reports `verified: false`; `DATA_SOURCES.md` lists the verification procedure |
| APC / impact-factor columns are empty | Impact factors are proprietary (Clarivate) and APC values change; neither can be fabricated | Columns retained but empty; README no longer claims they are populated |
| Scopus, Web of Science, Dimensions, Google Scholar, CORE, NIST WebBook | No free, key-less API (see `DATA_SOURCES.md` for the evidence per source) | Recorded in `BLOCKED` with reason, date and alternative |
| ChemRxiv API | HTTP 403 Cloudflare challenge on 2026-11-18 from a script client | Reachable indirectly via Europe PMC preprints and Crossref `posted-content` |
| `[α]D`/purity/CCDC semantic checks | Requires judgement beyond pattern matching | Existing `EVI-*` warnings retained, not upgraded to "verified" |
| BibTeX → CSL-exact reference styles | Needs a CSL engine (external data, licence review) | `format_reference` is documented as an approximation |

---

## 9. Residual risk

1. **Provider drift.** Any adapter can break when an upstream schema changes. Mitigation:
   fixture-based tests, capability declarations, per-provider isolation, and a
   `research providers` readiness command.
2. **Quota reality.** OpenAlex keyless quota was exhausted during this audit and Semantic
   Scholar rate-limited at 429 (see `FINAL_QA_REPORT.md` §5). The pipeline continues and
   reports this honestly; a free OpenAlex key is strongly recommended for scheduled sync.
3. **Metadata ≠ truth.** Every record carries provenance, verification status and the
   date its citation count was observed. The coverage report states its own gaps.
4. **The chemistry engine verifies arithmetic and internal consistency — not chemistry.**
   A formula can be internally consistent and the compound still not exist, and a correct
   HRMS calculation says nothing about whether the measurement was real. This limitation is
   now stated in the README and in `chem.py`'s module docstring.
