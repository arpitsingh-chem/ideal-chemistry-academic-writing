# PaperForge

**A chemistry manuscript engine with a global research-intelligence layer.**

Point it at your data, figures and DOIs and it composes, verifies, scores and packages a
submission-ready chemistry manuscript. Point it at a research question and it searches the
open scholarly indexes, normalises what they return, and tells you honestly what it found
— and what it could not reach.

```
pip install -e ".[figures,docx,dev]"     # Python ≥ 3.10; one required dependency (PyYAML)

paperforge doctor                                    # environment + chemistry self-test
paperforge check examples/demo-paper                 # → 100.0/100, grade A+
paperforge research search "photoredox C–H arylation" --limit 5
paperforge institution stats                         # the bundled IISER Bhopal collection
```

**State of this release:** version 2.4.0 · **360 tests passing, 3 network-marked skips** ·
wheel and sdist built and installed in clean virtual environments · 11 scholarly-provider
adapters · 115 manuscript rules · 261 journal profiles (5 verified per-journal, 256
inherited family defaults — see [Honest limitations](#10-honest-limitations)).

---

## 1. What PaperForge is for

Two problems, one engine.

**Writing a chemistry paper is a verification problem.** Chemists produce structured facts
— formulae, yields, HRMS values, NMR integrals, spectra, crystallographic deposits — and
manuscripts are checked against them by tired humans at 2 a.m. PaperForge makes those
cross-checks machine-readable: a formula that cannot exist, a mass that does not match its
formula, a yield that contradicts its own mass, an integral that does not sum to the
molecular formula, a reference that has been retracted.

**Finding the literature is a coverage problem.** A search that silently returns nothing
from a source that timed out is worse than no search. PaperForge queries eleven open
indexes through independent adapters, records which ones answered, deduplicates what comes
back with an auditable rule set, and reports its own gaps.

It never invents data. Unknown metadata is `None`, not a guess; a failed provider is
reported as failed, not silently dropped.

---

## 2. Install

```bash
git clone https://github.com/arpitsingh-chem/ideal-chemistry-academic-writing
cd ideal-chemistry-academic-writing
python3 -m pip install -e ".[figures,docx,dev]"      # add ,structures for RDKit drawing

paperforge doctor
```

| Extra | Adds | Needed for |
|---|---|---|
| *(base)* | PyYAML | checking, drafting, references, journals, research |
| `figures` | Pillow, matplotlib | figure dpi/size checks, TOC graphics, demo rebuilds |
| `docx` | python-docx | DOCX output |
| `structures` | RDKit | `paperforge scheme` (SMILES → scheme/TOC images) |
| `dev` | pytest, pypdf, ruff, build | running the test suite |

`tectonic` (or any LaTeX engine) is only needed to turn the generated `.tex` into a PDF.

---

## 3. Quick start: a manuscript

```bash
paperforge new my-paper --journal "Organic Letters"
cd my-paper                       # edit paper.yaml, data/*.csv, figures/, refs/
paperforge refs verify .          # Crossref-check every DOI, flag retractions
paperforge check .                # 115 rules, 0–100 score, exits non-zero on a gate
paperforge draft . --format all --cover-letter --highlights
paperforge si .                   # Supporting Information .tex
paperforge bundle . --strict      # submission zip + checklist + manifest
```

A project is a folder: `paper.yaml` (authors, journal, compounds, sections), `data/*.csv`
(tables), `figures/`, `refs/refs.bib`. `paperforge ingest <folder>` builds one from an
existing research directory.

### The two demo projects

| Project | Field | Journal | Result |
|---|---|---|---|
| `examples/demo-paper` | organic photoredox, 8 compounds | Organic Letters | 100.0/100, 8/8 DOIs verified |
| `examples/second-paper` | organometallic photophysics, 6 Ir(III) complexes | Dalton Transactions | 99.7/100 with `--verify-refs`; 94.9 offline (8 unverified DOIs) |

Both are synthetic but *physically consistent*: every mass, yield and integral in them is
a real calculation, and the hallucinations that v1 shipped (an impossible HRMS, a 109.9 %
yield) are now regression tests.

---

## 4. Quick start: research intelligence

```bash
export PF_MAILTO=you@example.org        # required by Unpaywall, polite for the others
export OPENALEX_API_KEY=...             # optional but strongly recommended (see below)

paperforge research providers           # what is available, and what is blocked, with reasons
paperforge research search "lanthanide single molecule magnet" --limit 5
paperforge research fetch 10.1021/jacs.5c13581      # reconcile one DOI across providers
paperforge research sync "photoredox catalysis" --db research.sqlite3 --limit 50
paperforge research coverage --db research.sqlite3  # measured coverage, including gaps
paperforge research dedup --db research.sqlite3     # duplicate *proposals*, never silent merges
paperforge research export --db research.sqlite3 --out topic.json
```

A real run, verbatim:

```
$ paperforge research sync "photoredox catalysis" --db final.sqlite3 --limit 10
  FAIL openalex         rate_limited: Insufficient budget … ($0.0008 remaining; resets at midnight UTC)
  OK   crossref           10 record(s)  (index reports   336 485)
  OK   europepmc          10 record(s)  (index reports     7 090)
  OK   arxiv              10 record(s)  (index reports        10)
  OK   datacite           10 record(s)  (index reports       729)
  OK   doaj               10 record(s)  (index reports       317)
  FAIL semantic_scholar rate_limited: Too Many Requests
found 50, unique 50, merged 0, inserted 50, updated 0, unchanged 0
note: 2 provider(s) unavailable — results are incomplete, not empty
```

Two providers failed. The run still finished, the failure is recorded in the store's
`provider_state` table, and the message says the results are incomplete. That behaviour is
the feature.

### Why an OpenAlex key

Keyless OpenAlex requests share **one daily budget per IP address**, and this audit
exhausted it. A free key (from `https://openalex.org/settings/api`) has its own budget.
PaperForge reads `OPENALEX_API_KEY` and will not retry a spent daily quota inside a run —
it records `retryAfter` and moves on.

---

## 5. Scholarly sources

Eleven adapters, each verified against the live API on **2026-11-18**:

| Source | Discovery | DOI | OA | Citations | Retraction | Notes |
|---|---|---|---|---|---|---|
| OpenAlex | ✅ | ✅ | ✅ | ✅ | ✅ | keyless quota is shared per IP; free key advised |
| Crossref | ✅ | ✅ | – | ✅ | ✅ | authoritative for the version of record and retractions |
| Europe PMC | ✅ | ✅ | ✅ | ✅ | ✅ | PubMed + preprint index in one query |
| arXiv | ✅ | – | ✅ | – | – | preprints; 3 s request interval respected |
| DataCite | ✅ | ✅ | ✅ | ✅ | – | datasets, software, Zenodo/crystallography DOIs |
| DOAJ | ✅ | ✅ | ✅ | – | – | vetted fully-open-access journals |
| Unpaywall | enricher | ✅ | ✅ | – | – | requires a contact e-mail |
| Semantic Scholar | ✅ | ✅ | ✅ | ✅ | – | anonymous tier throttles aggressively |
| ORCID | identity | – | – | – | – | author iDs, check-digit validated |
| ROR | identity | – | – | – | – | institution identity |
| PubChem | compound | – | – | – | – | independent formula/mass cross-check |

**Documented as unavailable, not faked** (evidence in [`DATA_SOURCES.md`](DATA_SOURCES.md)):
ChemRxiv (HTTP 403 Cloudflare challenge), Google Scholar (no API; scraping violates ToS),
Scopus and Web of Science (subscription), Dimensions (registered research access only),
CORE (API key), NIST Chemistry WebBook (no API).

---

## 6. What the chemistry engine actually checks

| Check | Example it catches |
|---|---|
| Formula parse (Hill, brackets, hydrates, charges) | `CuSO4·5H2O·2H2O` scaled wrongly; `C7H7+` read as `CH` |
| Mono/average mass, adducts, ppm | `[M+H]⁺ for C₁₄H₁₀NO₂S` reported as 256.0427 (true 257.0505) |
| Radical-ion adducts | `[M]⁺·` computed without the electron mass (2.14 ppm at m/z 256) |
| Degree of unsaturation | a negative DBE, or a half-integer DBE for fixed-valence elements |
| Yield ↔ mass ↔ mmol | `0.242 g` claimed for 0.86 mmol at 82 % is 109.9 % — the true value is 0.181 g |
| ¹H integral sum vs formula | 7 H reported for a 10-H molecule |
| ¹³C signal count | 20 signals for a 14-carbon formula |
| Evidence completeness | a crystal structure without a CCDC number; ">99 % pure" with no HPLC/GC |
| References | unresolvable DOI, unknown citation key, **retracted reference (Crossref forward lookup)** |

DBE uses the generalised expression `1 + ½Σnᵢ(vᵢ−2) − ½q`, so triphenylphosphine,
TMSCl and boronic acids are no longer reported as impossible molecules. Where an element
has variable valence, the finding is downgraded to a note instead of a hard error — the
tool does not cry wolf.

**What it does not do:** it verifies arithmetic and internal consistency. A formula can be
perfectly self-consistent and the compound still non-existent, and a correct HRMS
calculation says nothing about whether a measurement was honest.

---

## 7. Journal intelligence

261 profiles (`paperforge/data/journals.csv` + `journal_limits.json`), with:

* publisher family, scope terms, aliases, article types;
* abstract/body/figure/reference limits, TOC graphic dimensions;
* `source` URL and a `verified` flag **per profile**.

| Status | Count | Meaning |
|---|---|---|
| per-journal verified limits | **5** | limits read from that journal's current author guidelines |
| publisher-family defaults, `verified: false` | **256** | a conservative family-level summary, explicitly not journal-verified |

The matcher is a per-paper TF-IDF model over the captured corpus; `paperforge journals
match "topic"` ranks journals and `paperforge retarget --journal X` diffs what must change.

APC and impact-factor columns exist and are **empty**: impact factors are proprietary and
APC values change, so neither is fabricated. This README no longer claims otherwise (the
v2.3 README did — see [`AUDIT_REPORT.md`](AUDIT_REPORT.md) §4).

---

## 8. Command reference

| Command | What it does |
|---|---|
| `new PATH` | scaffold `paper.yaml`, `data/`, `figures/`, `refs/` |
| `ingest FOLDER --out P` | turn a research folder (CSV/figures/.bib) into a project |
| `context PATH` | print the grounded evidence pack for an LLM |
| `check PATH` / `check --file X.tex\|.md\|.docx` | 115 rules, 0–100 score, grade |
| `score PATH --min 90` | CI gate (non-zero exit under the bar) |
| `draft PATH --format all` | Markdown, LaTeX, DOCX, TXT (`--cover-letter`, `--highlights`) |
| `si PATH` | Supporting Information `.tex` |
| `figures PATH` | dpi/size audit + TOC dimension check |
| `scheme reaction "A>>B"` | RDKit reaction scheme with conditions and yields |
| `journals list/search/match/show` | the journal database |
| `refs verify PATH` / `refs add PATH DOI…` | Crossref verification, retraction flags, `refs.bib` |
| `retarget PATH --journal X` | field-by-field diff for another journal |
| `bundle PATH --strict` | submission zip + checklist + manifest |
| `rules` | list every rule code |
| `doctor` | environment + chemistry self-test |
| **`research providers`** | adapters, capabilities, known-unavailable sources |
| **`research search QUERY`** | query every configured source at once |
| **`research fetch DOI`** | resolve one identifier across providers and reconcile |
| **`research sync QUERY --db F`** | idempotent synchronisation into a SQLite store |
| **`research coverage --db F`** | measured coverage, provider health, known gaps |
| **`research dedup --db F`** | duplicate proposals with their reasoning |
| **`research export --db F --out F`** | clean dataset + coverage sidecar |
| **`institution stats\|search\|faculty\|journals`** | the preserved IISER Bhopal collection |

Exit codes: `0` OK · `1` gate failed **or** at least one provider unavailable · `2` bad input.
Every command that produces a report accepts `--json`.

---

## 9. Architecture

```
                    ┌──────────────────────────────────────────┐
                    │              paperforge CLI              │
                    │  check draft refs journals bundle …      │
                    │  research …   institution …              │
                    └───────┬───────────────────────┬──────────┘
                            │                       │
        ┌───────────────────▼──────┐   ┌────────────▼─────────────────────┐
        │  Manuscript engine       │   │  Research layer                  │
        │  project  draft  checks  │   │  schema  dedup  store  pipeline  │
        │  chem  figures  schemes  │   │  coverage                        │
        │  refs  journals  render  │   └────────────┬─────────────────────┘
        │  bundle                  │                │
        └──────────────────────────┘   ┌────────────▼─────────────────────┐
                                       │  providers/ (11 adapters)        │
                                       │  base.py  HttpClient: retry,     │
                                       │  backoff, Retry-After, quota     │
                                       │  registry.py: status + BLOCKED   │
                                       └────────────┬─────────────────────┘
                                                    │ HTTPS, open APIs only
                     OpenAlex · Crossref · Europe PMC · arXiv · DataCite ·
                     DOAJ · Unpaywall · Semantic Scholar · ORCID · ROR · PubChem
```

Details, decisions and rejected alternatives: [`ARCHITECTURE.md`](ARCHITECTURE.md).
Data model and schema: `paperforge/research/schema.py`. Storage: SQLite, schema version 1,
ordered migrations.

---

## 10. Honest limitations

1. **Journal limits are verified for 5 of 261 journals.** The rest inherit a family
   default marked `verified: false`. Always confirm on the journal's current author
   guidelines page before submitting.
2. **No impact factors, no acceptance rates, no APC values** — deliberately absent rather
   than invented.
3. **Subdiscipline classification is a keyword model, not benchmarked.** It returns `None`
   when unsure.
4. **Retraction status is source-scoped.** `none_known` means "no notice found in the
   sources queried", never "this paper is sound".
5. **Metadata ≠ truth.** Citation counts are point-in-time and provider-specific.
6. **No full-text, citation-graph or research-gap analysis yet** — see [`ROADMAP.md`](ROADMAP.md).
7. **Coverage is what you sync.** The bundled institutional collection is a 1,616-work
   snapshot, not a live mirror; `institution stats` says so on every run. (The v2.3 README
   quoted **1,707** works; the shipped file contains **1,616**, verified 2026-11-18. The
   earlier figure was wrong and is corrected here rather than quietly repeated.)
8. **Chemistry checks verify arithmetic, not science.**
9. **The manuscript engine is tuned to synthetic/characterisation chemistry.** Other
   subdisciplines are supported by the research layer, not yet by dedicated manuscript
   validators (`ROADMAP.md`).

---

## 11. Testing

```bash
python3 -m pytest                       # 360 passed, 3 skipped (network-marked)
python3 -m pytest -m network            # the live-API tests, skipped by default
python3 -m pytest tests/scientific -v   # independent chemistry reference values
python3 -m pytest tests/adversarial -v  # transport faults, hostile payloads, exit codes
```

| Suite | What it proves |
|---|---|
| `tests/unit` | provider parsing against recorded live payloads; schema semantics |
| `tests/integration` | dedup, merge precedence, store idempotency, coverage, exports |
| `tests/scientific` | masses/adducts/DBE against values derived outside this codebase (PubChem, CODATA, IUPAC) |
| `tests/adversarial` | 429/timeout/HTML-instead-of-JSON, 10 k records, corrupt SQLite, CLI exit codes |
| inherited v2 tests | the 173 behaviours that already worked remain working |

The suite needs **no network**. Live checks are opt-in (`-m network`).

---

## 12. Data sources, licensing, citation

* **Sources and their terms:** [`DATA_SOURCES.md`](DATA_SOURCES.md),
  [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
* **Coverage, measured:** [`GLOBAL_RESEARCH_COVERAGE.md`](GLOBAL_RESEARCH_COVERAGE.md).
* **Licence:** this repository is distributed under **CC BY 4.0** (`LICENSE`). The v2.3
  README claimed "code MIT" without an MIT licence existing; that claim has been removed
  and the question of a code-specific licence is recorded as an open owner decision in
  [`LICENSING_AND_PROVENANCE_AUDIT.md`](LICENSING_AND_PROVENANCE_AUDIT.md).
* **Institutional mark:** the IISER Bhopal logo in the thesis template belongs to the
  institution; forks should replace it (see `THIRD_PARTY_NOTICES.md` §3).

```bibtex
@software{paperforge2026,
  title  = {PaperForge: a chemistry manuscript engine with global research intelligence},
  author = {PaperForge contributors},
  year   = {2026},
  version = {2.4.0},
  url    = {https://github.com/arpitsingh-chem/ideal-chemistry-academic-writing},
  note   = {Includes a preserved 1,616-work institutional dataset for the IISER Bhopal
            Department of Chemistry (OpenAlex, CC0)}
}
```

---

## 13. Contributing, security, roadmap

* [`CONTRIBUTING.md`](CONTRIBUTING.md) — setup, test expectations, how to add a provider.
* [`SECURITY.md`](SECURITY.md) — private vulnerability reporting.
* [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) — Contributor Covenant 2.1.
* [`ROADMAP.md`](ROADMAP.md) — what is planned, what is explicitly not.
* [`CHANGELOG.md`](CHANGELOG.md) — 2.4.0 and the history before it.
* [`docs/`](docs/) — tutorials, how-to guides, reference and explanations (Diátaxis).
* [`AUDIT_REPORT.md`](AUDIT_REPORT.md) — the full pre-change audit, findings and evidence.

The governing principle: **do not claim a capability that has not been executed and
verified**, and prefer a documented "we cannot reach this source" over an integration that
pretends.
