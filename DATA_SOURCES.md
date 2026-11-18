# DATA_SOURCES

Every external source PaperForge touches, what it is used for, its **verified** access
conditions on 2026-11-18, and its licence. Sources that were investigated and **rejected**
are listed too, with the evidence — a documented "no" is worth more than an optimistic
integration that breaks.

Verification method: an anonymous `curl` (and, for adapters, the real code path) against
the public endpoint from a clean network. HTTP status and response shape recorded.

## 1. Integrated sources

| Source | Used for | Access (verified 2026-11-18) | Licence / terms | Adapter |
|---|---|---|---|---|
| **OpenAlex** | discovery, institutions, authors, OA status, citations, retraction flag | `api.openalex.org` HTTP 200. **Keyless requests share a per-IP daily budget**; when spent the API returns 403/429 with `reason: "daily_budget"` and `retryAfter`. A free key (`OPENALEX_API_KEY`) has its own budget. `mailto` identifies the client but does **not** raise the quota. | CC0 for metadata | `providers/openalex.py` |
| **Crossref** | authoritative DOI metadata, publisher/pages, references, **retraction relations** | HTTP 200 anonymously; `mailto` places the client in the polite pool. One request in this audit received **429** without a `mailto`, which is why the adapter always sends one. | Crossref open metadata terms | `providers/crossref.py` |
| **Europe PMC** | PubMed/MEDLINE + preprint index (arXiv, bioRxiv, ChemRxiv, medRxiv), citation counts, OA links | HTTP 200, no key, `format=json&resultType=core`. Single-element lists arrive as bare strings (handled). | Europe PMC terms; per-record licence reported | `providers/europepmc.py` |
| **arXiv** | preprints (physics/chemistry-adjacent) | `export.arxiv.org/api/query` HTTP 200 over **https** (http returns 301). Requests a 3 s delay between calls — enforced. | arXiv API terms; per-article licence | `providers/arxiv.py` |
| **DataCite** | datasets, software, repository DOIs (Zenodo 10.5281, crystallography, etc.) | `api.datacite.org/dois` HTTP 200; `page[size]` must be URL-encoded as `page%5Bsize%5D`. | CC0 metadata | `providers/datacite.py` |
| **DOAJ** | vetted fully-OA journals and articles | `doaj.org/api/search/...` HTTP 200; the query sits **in the path** and must be URL-encoded. | CC0 metadata | `providers/doaj.py` |
| **Unpaywall** | legal OA location for a DOI | HTTP 200 **only with `?email=`** (no key). Modelled as an enricher: no `search()`. | CC0 data; API terms | `providers/unpaywall.py` |
| **Semantic Scholar** | citation counts, citation contexts (future) | `graph/v1` HTTP 200 anonymously, but **429 "Too Many Requests"** was observed repeatedly under normal use. Optional key (`SEMANTIC_SCHOLAR_API_KEY`). | S2 API terms (check per use) | `providers/semantic_scholar.py` |
| **ORCID** | author identity, works list | `pub.orcid.org/v3.0` HTTP 200 with `Accept: application/json`; no token for public records. | ORCID public data terms | `providers/identity.py` |
| **ROR** | institution identity, country, aliases | `api.ror.org/v2/organizations` HTTP 200, no key. **v2 schema** (`names`, `locations`) differs from v1. | CC0 | `providers/identity.py` |
| **PubChem** | independent cross-check of a formula / monoisotopic mass | PUG-REST HTTP 200; dynamic throttling ≤ 5 req/s. | Public domain (US NIH) | `providers/pubchem.py` |

### National / institutional

| Source | Status |
|---|---|
| **IISER Bhopal Department of Chemistry** | Preserved as a **bundled snapshot** `paperforge/data/publications-openalex.json` (1,616 works, 2009–2026), originally built from the OpenAlex works API filtered by author IDs. Offline, typed, tested (`paperforge/institutions/iiserb.py`). Not refreshed automatically; refresh is an explicit, reviewable operation. |

## 2. Investigated and **not** integrated

| Source | Verified obstacle | Documented alternative |
|---|---|---|
| **ChemRxiv** | `chemrxiv.org/engage/chemrxiv/public-api/v1/items` → **HTTP 403**, Cloudflare interstitial ("Just a moment..."). No key-less JSON endpoint reachable from a script. | ChemRxiv DOIs are reachable via Europe PMC (preprint index) and Crossref (`posted-content`). |
| **Google Scholar** | No public API. Scraping violates the Terms of Service. | OpenAlex / Semantic Scholar citation counts. |
| **Scopus** | Requires an institutional Elsevier API key and subscription. | OpenAlex (broader coverage, open). |
| **Web of Science** | Requires institutional Clarivate access. | OpenAlex / Crossref. |
| **Dimensions** | Free for research via a registered account and DSL; not a public keyless API. | OpenAlex. |
| **Microsoft Academic** | Retired (31 Dec 2021); no maintained successor under that identity. | OpenAlex (its successor in practice). |
| **CORE** | API key required (free tier registration). | Unpaywall + Europe PMC full-text links. |
| **NIST Chemistry WebBook** | No public API; HTML only; bulk reuse needs permission. | PubChem for structure/property cross-checks. |
| **RCSB PDB / COD** | Public APIs exist, but PaperForge has no crystallographic validator yet; integrating storage without a validator would add data without capability. | `ROADMAP.md` (crystallography track). |

## 3. Rate-limit and quota policy

| Provider | Policy implemented |
|---|---|
| OpenAlex | 0.12 s minimum interval; a daily-budget 403 is **not** retried inside a run; honours `retryAfter`; `OPENALEX_API_KEY` supported |
| Crossref | 0.10 s; always sends `mailto` (polite pool) |
| Europe PMC | 0.05 s |
| arXiv | 3.0 s (arXiv's stated request) |
| DataCite / DOAJ / Unpaywall | 0.1 / 0.2 / 0.1 s |
| Semantic Scholar | 1.1 s; treated as a best-effort enricher |
| PubChem | 0.25 s |
| ORCID / ROR | 0.2 s |

All intervals are overridable via `PF_HTTP_INTERVAL`, timeouts via `PF_HTTP_TIMEOUT`,
retries via `PF_HTTP_TRIES`, and the contact address via `PF_MAILTO`.

## 4. What is stored, and what is not

**Stored:** bibliographic metadata returned by the APIs (titles, authors, venue, dates,
identifiers, abstracts where the provider publishes them, citation counts with the date
observed, OA status, licence strings, retraction relations), plus the raw provider payload
for provenance.

**Not stored:** full text of closed-access works, PDFs, subscriber content, author
e-mail addresses harvested from papers, or anything obtained by circumventing
authentication, paywalls, CAPTCHAs or robots directives. No provider is scraped.

## 5. Attribution requirements

| Source | Obligation | Where honoured |
|---|---|---|
| OpenAlex | CC0 — no attribution required, but cite it as the data source | `THIRD_PARTY_NOTICES.md`, `CITATION.cff` |
| Crossref | open metadata; cite Crossref as the DOI registration agency | notices + per-record provenance |
| Europe PMC | cite; respect per-record licence | provenance `license` field |
| arXiv | per-article licence (often CC BY / arXiv default) | provenance `license` field |
| DataCite | CC0 metadata; the *dataset* licence is in the record | `WorkRecord.license` |
| DOAJ | CC0 | notices |
| Unpaywall | cite Unpaywall; CC0 data | notices |
| Semantic Scholar | S2 API terms; do not redistribute at scale | notices |
| ORCID | ORCID public API terms; no bulk harvesting | adapter is per-record lookup |
| ROR | CC0 | notices |
| PubChem | public domain; cite PubChem | notices |

## 6. Reproducing the access checks

```bash
curl -s -o /dev/null -w '%{http_code}\n' 'https://api.openalex.org/works/doi:10.1021/jacs.5c13581?mailto=you@example.org'
curl -s -o /dev/null -w '%{http_code}\n' 'https://api.crossref.org/works/10.1021/jacs.5c13581?mailto=you@example.org'
curl -s -o /dev/null -w '%{http_code}\n' 'https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:10.1021/jacs.5c13581&format=json'
curl -s -o /dev/null -w '%{http_code}\n' 'https://export.arxiv.org/api/query?search_query=all:photoredox&max_results=1'
curl -s -o /dev/null -w '%{http_code}\n' 'https://chemrxiv.org/engage/chemrxiv/public-api/v1/items?term=photoredox&limit=2'   # 403: blocked
python3 -m paperforge research providers      # readiness table, from the running code
```
