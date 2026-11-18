# Reference: the record schema

`paperforge.research.schema.WorkRecord` (schema version **1.0**, `paperforge.work/1`).
This is the single normalised shape every provider adapter must produce.

## Unknown-value semantics — read this first

| Value | Meaning |
|---|---|
| `None` | **unknown / the provider did not supply it** |
| `[]` (empty list) | the provider supplied the field and it is genuinely empty |
| `OaStatus.UNKNOWN`, `RetractionStatus.UNKNOWN`, `PeerReview.UNKNOWN`, `VersionType.UNKNOWN` | the source does not publish this signal |

There is no fourth case. A value is never inferred from a sibling record, a default, or a
guess (`DECISIONS.md` D-05).

## Fields

### Identity

| Field | Type | Notes |
|---|---|---|
| `work_id` | `str` | `doi:<normalised doi>` when a valid DOI exists, else `hash:<sha256[:16]>` of title+year+first author. Stable across providers, which is what makes ingestion idempotent. |
| `doi` | `str \| None` | normalised: no resolver prefix, lower case, no trailing punctuation |
| `provider_ids` | `dict[str, str]` | e.g. `{"openalex": "W123", "pmid": "39876543", "arxiv": "2401.00001v1"}` |

### Descriptive

| Field | Type | Notes |
|---|---|---|
| `title` | `str \| None` | HTML markup stripped, entities unescaped |
| `abstract` | `str \| None` | OpenAlex's inverted index is reconstructed in position order; a missing word appears as `[?]` rather than vanishing |
| `authors` | `list[Author]` | `name`, `orcid` (check-digit validated), `given`, `family`, `affiliations`, `institutions[{name, ror, openalex, country}]` |
| `publication_year` | `int \| None` | |
| `publication_date` | `str \| None` | ISO when the provider supplies one |
| `venue` | `str \| None` | journal / repository name |
| `publisher` | `str \| None` | |
| `issn` | `list[str]` | |
| `keywords` | `list[str]` | |

### Classification

| Field | Type | Values |
|---|---|---|
| `article_type` | `str \| None` | provider vocabulary, lower-cased |
| `subdiscipline` | `str \| None` | one of 28 chemistry labels, or `None` — a keyword model, **not benchmarked** |
| `peer_review` | `PeerReview` | `preprint` · `peer_reviewed` · `unknown` |
| `version_type` | `VersionType` | `version_of_record` · `accepted_manuscript` · `preprint` · `conference` · `correction` · `retraction` · `unknown` |
| `version_of` | `str \| None` | DOI of the version of record, when known |

### Access

| Field | Type | Values |
|---|---|---|
| `oa_status` | `OaStatus` | `gold` · `hybrid` · `green` · `bronze` · `closed` · `unknown` |
| `license` | `str \| None` | as reported by the source |
| `fulltext_url` | `str \| None` | legal landing/PDF link only |
| `data_availability` | `str \| None` | |
| `funding` | `list[dict]` | |

### Bibliometrics

| Field | Type | Notes |
|---|---|---|
| `citation_count` | `int \| None` | |
| `citation_count_source` | `str \| None` | **mandatory** when a count exists |
| `citation_count_date` | `str \| None` | the date the count was observed |

Counts are point-in-time and provider-specific; they are never averaged or normalised.

### Integrity

| Field | Type | Values |
|---|---|---|
| `retraction_status` | `RetractionStatus` | `none_known` · `retracted` · `correction` · `expression_of_concern` · `unknown` |
| `retraction_notice_doi` | `str \| None` | |
| `references` | `list[str]` | DOIs of cited works, when the provider publishes them |

`none_known` means **no notice was found in the sources queried**. It is not a clean bill of
health, and the coverage report says so on every run.

### Provenance

| Field | Type | Notes |
|---|---|---|
| `sources` | `list[Provenance]` | `provider`, `url`, `retrieved_at`, `payload_sha256`, `license` |
| `verification` | `VerificationStatus` | `unverified` · `identifier_checked` · `cross_checked` · `conflicting` |
| `confidence` | `Confidence` | per-field `"conflict"` markers after a merge |
| `retrieved_at`, `source_url` | `str \| None` | |

## Methods

| Method | Purpose |
|---|---|
| `ensure_id()` | assign and return the stable `work_id` |
| `fingerprint()` | hash of identifying content; the store uses it to decide insert vs update |
| `missing_fields()` | list of tracked fields that are unknown |
| `completeness()` | `1 − unknowns/16`, rounded to 4 dp |
| `as_dict()` / `from_dict()` | JSON round-trip including `schema_version` |

## Identifiers

| Helper | Rule |
|---|---|
| `normalise_doi("https://doi.org/10.1021/ABC")` | → `10.1021/abc` |
| `valid_doi(x)` | `^10\.\d{4,9}/\S+$` after normalisation |
| `normalise_orcid(x)` | canonical `0000-0000-0000-000X`, **ISO 7064 MOD 11-2 check digit verified**; invalid → `None` |
| `normalise_title(x)` | strips markup/entities, folds accents, lower-cases, collapses punctuation |
| `title_key(x)` | first four significant words — the dedup blocking key |
| `classify_subdiscipline(...)` | keyword hint, `None` when unsure |

## Storage layout

| Table | Contents |
|---|---|
| `works` | `work_id`, `fingerprint`, `doi`, `title`, `year`, `venue`, `verification`, `retraction`, JSON `payload`, `first_seen`, `updated_at` |
| `work_ids` | `(work_id, scheme, value)` for DOI / openalex / pmid / pmcid / arxiv |
| `provenance` | one row per (record, provider, payload hash) with the **raw** payload |
| `merges` | kept/absorbed ids, verdict, score, reasons, timestamp |
| `sync_runs` | per-provider run: started/finished, status, counts, errors, stats |
| `provider_state` | last attempt/success, consecutive failures, last error, retry-after |
| `schema_meta` | migration version (currently `1`) |

## Example

```json
{
  "schema": "paperforge.work/1",
  "schema_version": "1.0",
  "work_id": "doi:10.1021/jacs.5c13581",
  "doi": "10.1021/jacs.5c13581",
  "title": "Rapid and High-Yielding Disulfide Bioconjugation at Any Desired Site in Proteins",
  "publication_year": 2026,
  "venue": "Journal of the American Chemical Society",
  "citation_count": 6,
  "citation_count_source": "crossref",
  "citation_count_date": "2026-11-18",
  "retraction_status": "none_known",
  "verification": "cross_checked",
  "sources": [
    {"provider": "crossref", "url": "https://doi.org/10.1021/jacs.5c13581",
     "retrieved_at": "2026-11-18T08:21:59Z", "payload_sha256": "…"},
    {"provider": "openalex", "url": "https://api.openalex.org/works/W…",
     "retrieved_at": "2026-11-18T08:22:00Z", "payload_sha256": "…"}
  ],
  "missing_fields": ["funding"],
  "completeness": 0.9375
}
```
