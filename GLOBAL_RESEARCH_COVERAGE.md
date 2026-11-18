# GLOBAL_RESEARCH_COVERAGE

A measured statement of what the research layer actually covers. Every number below was
produced by the commands shown, on 2026-11-18, from this branch. Nothing is estimated.

> **PaperForge does not index "every scientific paper ever published", and it never
> claims to.** It queries a set of open indexes, stores what they return, records what
> failed, and tells you both.

---

## 1. Sources integrated

| # | Source | Adapter | Discovery | DOI lookup | OA status | Citations | Retraction signal |
|---|---|---|---|---|---|---|---|
| 1 | OpenAlex | `providers/openalex.py` | ✅ | ✅ | ✅ | ✅ | ✅ |
| 2 | Crossref | `providers/crossref.py` | ✅ | ✅ | – | ✅ | ✅ |
| 3 | Europe PMC | `providers/europepmc.py` | ✅ | ✅ | ✅ | ✅ | ✅ |
| 4 | arXiv | `providers/arxiv.py` | ✅ | – (id lookup) | ✅ | – | – |
| 5 | DataCite | `providers/datacite.py` | ✅ | ✅ | ✅ | ✅ | – |
| 6 | DOAJ | `providers/doaj.py` | ✅ | ✅ | ✅ | – | – |
| 7 | Unpaywall | `providers/unpaywall.py` | enricher | ✅ | ✅ | – | – |
| 8 | Semantic Scholar | `providers/semantic_scholar.py` | ✅ | ✅ | ✅ | ✅ | – |
| 9 | ORCID | `providers/identity.py` | identity lookup | – | – | – | – |
| 10 | ROR | `providers/identity.py` | identity lookup | – | – | – | – |
| 11 | PubChem | `providers/pubchem.py` | compound lookup | – | – | – | – |

Blocked and documented (7): ChemRxiv, Google Scholar, Scopus, Web of Science, Dimensions,
CORE, NIST WebBook — evidence in `DATA_SOURCES.md`.

## 2. A real synchronisation, measured

```
$ export PF_MAILTO=you@example.org
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

$ paperforge research sync "lanthanide single molecule magnet" \
      --db final.sqlite3 --source crossref --source datacite --limit 6
  OK   crossref            6 record(s)   OK   datacite            6 record(s)
found 12, unique 12, merged 0, inserted 12
```

Resulting coverage report (`paperforge research coverage --db final.sqlite3 --json`):

| Metric | Measured value | Note |
|---|---|---|
| Records in store | **62** | |
| Records with a DOI | **52** | the 10 without are arXiv preprints, which have arXiv ids, not DOIs — by design |
| Records with an abstract | **47** | |
| Records with an ORCID-bearing author | **13** | only Crossref/Europe PMC publish ORCIDs |
| Distinct venues | **25** | |
| Distinct publishers | **23** | |
| Countries represented | **0** | ⚠ OpenAlex (the only institution-bearing source) was rate-limited in this run |
| Institutions represented | **0** | ⚠ same cause |
| Year range | **1977–2026** | Crossref keyword search reaches into the back catalogue |
| Records merged as duplicates | **0** | the two queries returned disjoint result sets |
| Cross-checked by ≥2 providers | **0** | same cause; verified separately by `research fetch` |
| Conflicting metadata | **0** | |
| Retracted | **0** | none of the retrieved records carry a retraction relation |
| Last successful sync | 2026-11-18T08:29:25Z | |

**Read this table as a demonstration of the machinery, not as a corpus.** 62 records is
what two queries with `--limit 10` returned in one minute; it says nothing about the size
of the indexes (Crossref alone reported 336,485 matches for the query).

## 3. Deduplication, measured on a controlled case

Duplicate detection is exercised by fixture, not by hoping it happens live:

```
$ python3 -m pytest tests/integration/test_research_pipeline.py -k Deduplication -v
```

| Scenario | Verdict | Score | Behaviour |
|---|---|---|---|
| Same DOI, different spelling (`https://doi.org/10.1021/ABC` vs `10.1021/abc`) | `same` | 1.00 | merged |
| Same `pmid`/`arxiv` id from two providers | `same` | 0.98 | merged |
| Two **different** DOIs, identical title and author | `distinct` | 0.00 | **not** merged (PF-007) |
| `…/ncl.34472799` vs `…/ncl.34472799.v1` | `related_version` | 0.90 | linked, both kept |
| Preprint with `version_of` → published DOI | `related_version` | 0.95 | linked, both kept |
| No DOIs, same title + author + year + venue | `same` | 0.92 | merged |
| Same title, different first authors, no DOIs | `distinct` | – | not merged; conflict recorded |

Live, the second sync merged 3 records across Crossref/Europe PMC/DataCite and later
revealed the Zenodo over-merge that produced rule PF-007 — which is exactly why the audit
trail exists: `SELECT * FROM merges` shows the decision, the score and the reasons.

## 4. Chemistry subdiscipline coverage

Classification is a keyword model over title/abstract/keywords
(`research/schema.py:classify_subdiscipline`) covering 28 subdisciplines. It returns
`None` when nothing matches — an explicit unknown, not a guess.

| Status | Detail |
|---|---|
| Coverage breadth | 28 labels implemented |
| Validation | Present in `WorkRecord.subdiscipline`; `None` allowed |
| Accuracy | **Not benchmarked.** No labelled chemistry corpus with a defensible licence was available, so no precision/recall figure is claimed. |
| How to improve | Hand-label 300 abstracts across subdisciplines, publish the label set as test data, then measure. Listed in `ROADMAP.md`. |

## 5. Known coverage gaps (emitted by the tool itself)

`paperforge research coverage` always lists its gaps; the current list is:

1. Citation counts are point-in-time values from the provider that reported them and are
   not normalised across sources.
2. Retraction status reflects the sources queried — `none_known` is the absence of a
   notice *in those sources*, not evidence of integrity.
3. Full text is never downloaded for closed-access works; only metadata is stored.
4. Providers with a recorded failure mean the results of that run are incomplete
   (in the run above: OpenAlex and Semantic Scholar).
5. Institution and country fields are empty when OpenAlex is unavailable.
6. No full-text, citation-graph, or research-gap analysis yet (`ROADMAP.md`).

## 6. Institutional collection (preserved)

```
$ paperforge institution stats
Indian Institute of Science Education and Research Bhopal — Department of Chemistry
  ROR                 https://ror.org/04m7r8v69
  works               1616
  faculty identified  26
  distinct venues     254
  year range          2009–2026
  preprints           88
  records without DOI 2
  open access         not captured in snapshot
  snapshot            publications-openalex.json (OpenAlex works API, author-ID-verified)
```

Two deliberate honesty properties:

* **26 faculty**, not the 30 the old README claimed — measured from the snapshot's
  `faculty` field union.
* **Open access and retraction counts read as "not captured"**, not as `0`. The snapshot
  predates those OpenAlex fields; reporting `0` would be a false negative dressed as data.

Top venues by captured output: Chemical Communications 97 · Chem. Eur. J. 83 ·
Organic Letters 78 · ChemRxiv 61 · ChemInform 53 (a digest — excluded from journal
matching, as documented in `journals.py`).

## 7. How to grow coverage responsibly

```bash
export OPENALEX_API_KEY=...        # free key, own daily budget
paperforge research sync "your topic" --db research.sqlite3 --limit 200 --from-year 2015
paperforge research coverage --db research.sqlite3
paperforge research dedup    --db research.sqlite3 --threshold 0.85
paperforge research export   --db research.sqlite3 --out data/topic-2026.json
```

Rules the pipeline enforces: no scraping, no paywall circumvention, no fabricated records,
per-provider rate limits, and a committed record of every merge.
