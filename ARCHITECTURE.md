# ARCHITECTURE

PaperForge v2.4.0 has two halves that share one rule: **nothing is invented.**

* a **manuscript engine** (v2 lineage, preserved) that turns structured data into a
  submission-ready paper and checks it against 115 rules and 261 journal profiles;
* a **research intelligence layer** (new in v2.4) that queries the world's open scholarly
  indexes, normalises what they return, reconciles duplicates, and reports its own coverage.

```
                        ┌──────────────────────────────────────────────┐
                        │                  CLI (cli.py)                │
                        │  check · draft · refs · journals · bundle …  │
                        │  research …  ·  institution …                │
                        └───────────────┬──────────────────────────────┘
        ┌───────────────────────────────┼────────────────────────────────┐
        │                               │                                │
┌───────▼────────┐   ┌──────────────────▼───────────┐   ┌────────────────▼─────────┐
│  Manuscript    │   │      Research layer          │   │   Institution layer      │
│  engine        │   │  research/                   │   │  institutions/iiserb.py  │
├────────────────┤   ├──────────────────────────────┤   ├──────────────────────────┤
│ project.py     │   │ schema.py    (WorkRecord)    │   │ bundled snapshot         │
│ draft.py       │   │ dedup.py     (compare/merge) │   │ (offline, typed API)     │
│ checks.py(115) │   │ store.py     (SQLite + migs) │   └──────────────────────────┘
│ chem.py        │   │ pipeline.py  (sync/reconcile)│
│ figures.py     │   │ coverage.py  (honest metrics)│
│ refs.py        │   └───────────┬──────────────────┘
│ journals.py    │               │
│ render.py      │   ┌───────────▼──────────────────────────────────────┐
│ bundle.py      │   │            providers/ (11 adapters)              │
└────────────────┘   │  base.py   HttpClient: retry/backoff/429/Retry-  │
                     │            After/UA/quota-honest error taxonomy  │
                     │  api.py    Provider ABC + Capabilities           │
                     │  openalex crossref europepmc arxiv datacite doaj │
                     │  unpaywall semantic_scholar orcid ror pubchem    │
                     │  registry.py  status · BLOCKED(with evidence)    │
                     └──────────────────────────────────────────────────┘
                                     │  HTTPS (open APIs only)
                              ┌──────▼──────────────────────────────┐
                              │ OpenAlex · Crossref · Europe PMC ·  │
                              │ arXiv · DataCite · DOAJ · Unpaywall │
                              │ Semantic Scholar · ORCID · ROR ·    │
                              │ PubChem                             │
                              └─────────────────────────────────────┘
```

## 1. Design decisions and why

| Decision | Alternative rejected | Reason |
|---|---|---|
| Keep the v2 manuscript modules in place; add subpackages beside them | Rewrite into the `core/chemistry/publications/…` tree from the brief | The v2 modules pass 173 tests and produce a 100/100 demo. A rewrite would risk working behaviour for cosmetic structure. The brief says so explicitly; the evidence agreed. |
| `urllib` in `HttpClient` | `httpx` / `requests` | Base install stays at one dependency (PyYAML). Nothing in the transport needs HTTP/2, connection pooling across threads, or async: a sync job is sequential by design (rate limits are per-provider). |
| SQLite | PostgreSQL | Single-user corpus of 10³–10⁵ records; no server to operate; the 10k-record adversarial test runs in ~1 s. PostgreSQL is available to anyone who needs it by exporting JSON. |
| Plain dataclasses | Pydantic | The schema needs enumerations, explicit unknowns and provenance — expressible in ~200 lines with zero runtime dependency. Pydantic would be a large dependency for validation PaperForge already tests. |
| `Provision` of `None` for unknown values | Filling gaps from a sibling record | Filling gaps is fabrication. `missing_fields()` and `completeness()` make unknowns visible instead. |
| Provider errors are typed and isolated | One generic exception | A 429 with a `retryAfter` of 15 hours must not be retried three times, and must not abort a five-provider sync. `RateLimited.retry_after` drives both decisions. |
| Dedup: different DOIs ⇒ never `SAME` | Title-similarity merge | Two registered DOIs are two registered objects (Zenodo mints one per version). PF-007 in `BUG_REGISTER.md` is this bug, caught live. |
| Journal profiles keep `verified: false` | Sprinkling plausible limits | 256/261 profiles inherit publisher-family defaults. Marking them verified would be a lie with a compliance consequence. |

## 2. Data flow — one synchronisation

```
CLI: paperforge research sync "photoredox catalysis" --limit 10
  │
  ├─ registry.build_many(["openalex","crossref","europepmc","arxiv","datacite","doaj",
  │                      "semantic_scholar"])
  ├─ for each provider:  Provider.search(query, limit)  ── ProviderError ──▶ ProviderOutcome(ok=False)
  │     └─ raw JSON ──▶ Provider.normalise() ──▶ WorkRecord (+ Provenance, payload sha256)
  ├─ reconcile(): pairwise compare() on a title-key block
  │     ├─ SAME            → merge() → one record + audit dict (fields, conflicts)
  │     ├─ RELATED_VERSION → keep both, set version_of
  │     └─ DISTINCT        → keep both
  ├─ store.upsert(unique)  (idempotent on work_id + fingerprint)
  │     ├─ works (normalised payload)   ├─ work_ids (doi/openalex/pmid/arxiv)
  │     ├─ provenance (raw payloads)    ├─ merges  (decision + reasons)
  │     └─ sync_runs / provider_state (checkpoint + health)
  └─ SyncReport → summary lines, exit code 0 (all ok) / 1 (partial)
```

## 3. Error taxonomy

| Error | Raised when | Retried? | Effect on a run |
|---|---|---|---|
| `NotFound` | provider says the record does not exist (404) | no | that provider yields no record |
| `RateLimited` | 429, or 403 + budget text; carries `retry_after` | yes, unless `retry_after > 120 s` | provider marked failed, run continues |
| `ProviderUnavailable` | 5xx, DNS/TLS/timeout | yes, exponential backoff + jitter | provider marked failed, run continues |
| `MalformedResponse` | body is not the documented JSON/XML | no | provider marked failed, **no record synthesised** |
| `ProviderError` | adapter misuse (unknown source, bad identifier) | no | CLI exit code 2 |

## 4. Storage schema (SQLite, `schema_meta.version = 1`)

| Table | Purpose |
|---|---|
| `works` | one row per normalised record: `work_id`, `fingerprint`, `doi`, `title`, `year`, `venue`, `verification`, `retraction`, JSON `payload`, `first_seen`, `updated_at` |
| `work_ids` | `(work_id, scheme, value)` — DOI, OpenAlex id, PMID, arXiv id, PMCID |
| `provenance` | one row per (record, provider, payload hash) with the **raw** payload |
| `merges` | kept/absorbed ids, verdict, score, human-readable reasons, timestamp |
| `sync_runs` | per-provider run rows: started/finished, status, counts, errors, stats |
| `provider_state` | last attempt/success, consecutive failures, last error, retry-after |
| `schema_meta` | migration version |

Migrations are an ordered list of SQL scripts (`store.py:_MIGRATIONS`); each is applied
once and the version is bumped in the same transaction.

## 5. Module boundaries (dependency direction)

```
cli.py ─▶ cli_research.py ─▶ research/{pipeline,coverage,dedup,store} ─▶ providers/*
   │                                    │                                   │
   └─▶ checks/draft/render/…            └─▶ research/schema.py ◀─────────────┘
                                             (no imports from providers)
```

`schema.py` knows nothing about HTTP and nothing about SQLite; `providers/*` knows nothing
about storage; `store.py` knows nothing about HTTP. That is what makes the provider layer
testable offline and the store testable without a provider.

## 6. Where the two halves meet

* `refs.py` (manuscript) and `providers/crossref.py` (research) both read Crossref, but
  deliberately through separate code paths: the manuscript path is a **blocking,
  authoritative** verification step during `check`, while the research path is a
  **discovery** path with caching and retry policy. Merging them would make `check`
  network-dependent, which the existing behaviour forbids.
* `journals.py` uses the institutional snapshot for its TF-IDF matcher; the research layer
  can grow that corpus from live providers without touching the matcher.

## 7. Known architectural debt

1. `checks.py` is 1,071 lines and mixes eight rule families. It works and is tested; it
   should be split into `checks/{structure,evidence,references,figures,journal,ethics,
   style}.py` when a second contributor joins.
2. `draft.py`/`render.py` have overlapping responsibilities for citation renumbering.
3. No type-checker gate (`mypy`/`pyright`) in CI yet; annotations are partial.
4. Journal verification is a manual, per-journal procedure with no drift detection.
5. The research layer has no full-text or citation-graph analysis yet (see `ROADMAP.md`).
