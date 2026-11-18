# Provider fixtures

`live/` payloads were captured from the real public APIs (see `PROVENANCE` below).
They are committed so the provider test-suite runs offline and deterministically —
no test in this repository requires network access to pass.

| file | endpoint | captured |
|---|---|---|
| `crossref_work_jacs.json` | `api.crossref.org/works/10.1021/jacs.5c13581` | 2026-11-18 |
| `europepmc_search.json` | `ebi.ac.uk/europepmc/webservices/rest/search?query=photoredox+catalysis` | 2026-11-18 |
| `arxiv_search.atom` | `export.arxiv.org/api/query?search_query=all:photoredox` | 2026-11-18 |
| `datacite_search.json` | `api.datacite.org/dois?query=perovskite` (trimmed to 1 record) | 2026-11-18 |
| `doaj_search.json` | `doaj.org/api/search/articles/photoredox` | 2026-11-18 |
| `unpaywall_oa.json` | `api.unpaywall.org/v2/10.1021/jacs.5c13581` | 2026-11-18 |
| `openalex_work.json` | `api.openalex.org/works/doi:10.1021/jacs.5c13581` | 2026-11-18 |
| `semanticscholar_paper.json` | `api.semanticscholar.org/graph/v1/paper/DOI:10.1021/jacs.5c13581` | 2026-11-18 |
| `pubchem_aspirin.json` | `pubchem.ncbi.nlm.nih.gov/.../name/aspirin/property/...` | 2026-11-18 |
| `ror_iiserb.json` | `api.ror.org/v2/organizations?query=...Bhopal` (2 records) | 2026-11-18 |

Trimming is limited to removing long descriptive fields and extra array items;
every identifying field the adapters read is preserved verbatim.

Fixtures are test data, not a redistribution of the providers' content:
Crossref/DataCite/DOAJ/Unpaywall/OpenAlex metadata is open; the Europe PMC and
Semantic Scholar samples are two-record excerpts used solely to test parsing.
