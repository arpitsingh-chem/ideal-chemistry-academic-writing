# THIRD_PARTY_NOTICES

PaperForge contains original code and documentation, plus data and dependencies from
third parties. This file records them. PaperForge's own licence is in `LICENSE`
(CC BY 4.0); the notices below apply to the components they name.

---

## 1. Data and metadata sources

### OpenAlex
- **Used for:** `paperforge/data/publications-openalex.json` (1,616 works of the IISER
  Bhopal Department of Chemistry), and live queries through `paperforge/providers/openalex.py`.
- **Licence:** CC0 1.0 Universal (public domain dedication) for the metadata.
- **Attribution:** not legally required under CC0; cited here as a courtesy and because
  the project's scientific claims depend on it.
- **Source:** <https://openalex.org>, <https://docs.openalex.org>

### Crossref
- **Used for:** DOI metadata verification and retraction relations
  (`paperforge/refs.py`, `paperforge/providers/crossref.py`).
- **Licence/terms:** Crossref's open metadata terms; bibliographic metadata may be reused
  with attribution.
- **Source:** <https://www.crossref.org>, <https://api.crossref.org>

### Europe PMC
- **Used for:** biomedical/preprint literature search (`paperforge/providers/europepmc.py`).
- **Terms:** Europe PMC terms of use; **per-record licences vary** and are recorded in each
  record's `license` field when the API supplies one.
- **Source:** <https://europepmc.org>

### arXiv
- **Used for:** preprint discovery (`paperforge/providers/arxiv.py`).
- **Terms:** arXiv API terms; each article carries its own licence, which the adapter
  reports rather than overrides.
- **Source:** <https://info.arxiv.org/help/api/index.html>

### DataCite
- **Used for:** dataset/software DOIs (`paperforge/providers/datacite.py`).
- **Licence:** CC0 for the metadata; **the dataset's own licence** is authoritative for the
  content and is reported in `WorkRecord.license`.
- **Source:** <https://datacite.org>

### DOAJ (Directory of Open Access Journals)
- **Used for:** vetted open-access journals/articles (`paperforge/providers/doaj.py`).
- **Licence:** CC0 for metadata.
- **Source:** <https://doaj.org>

### Unpaywall
- **Used for:** legal open-access locations for a DOI (`paperforge/providers/unpaywall.py`).
- **Terms:** Unpaywall API terms; data is CC0. Cite Unpaywall when using its OA data.
- **Source:** <https://unpaywall.org/products/api>

### Semantic Scholar (Allen Institute for AI)
- **Used for:** citation counts / enrichment (`paperforge/providers/semantic_scholar.py`).
- **Terms:** S2 API terms of service. Do not redistribute S2 data at scale.
- **Source:** <https://www.semanticscholar.org/product/api>

### ORCID
- **Used for:** author identity resolution (`paperforge/providers/identity.py`).
- **Terms:** ORCID public API terms; per-record lookup only, no bulk harvesting.
- **Source:** <https://info.orcid.org/documentation/api-reference/>

### Research Organization Registry (ROR)
- **Used for:** institution identity (`paperforge/providers/identity.py`).
- **Licence:** CC0.
- **Source:** <https://ror.org>

### PubChem (NCBI/NLM)
- **Used for:** independent cross-checks of molecular formula and monoisotopic mass
  (`paperforge/providers/pubchem.py`).
- **Terms:** PubChem data is in the public domain (US Government work); cite PubChem.
- **Source:** <https://pubchem.ncbi.nlm.nih.gov>

## 2. Publisher submission guidelines

`paperforge/data/journal_limits.json` records **numeric submission parameters** (abstract
word limits, figure counts, TOC dimensions) summarised from publishers' public author
guidelines, together with the URL of each source page.

* Only factual parameters are stored; **no guideline prose is copied**.
* Every profile carries `source` and `verified` flags; 256 of 261 inherit a
  publisher-family default and are marked `verified: false`.
* Publisher names and journal titles are the trademarks of their owners and are used
  descriptively (nominative use) to identify the guidelines referenced.

Publishers referenced: American Chemical Society; Royal Society of Chemistry; Wiley-VCH;
Elsevier; Springer Nature; Taylor & Francis; Oxford University Press; Cambridge University
Press; IUCr; Thieme; Bentham; MDPI/Frontiers; the Nature/AAAI family.

## 3. Institutional mark

**IISER Bhopal logo** — `templates/latex/thesis/figures/iiserb_logo.pdf`

* The logo is the institutional mark of the **Indian Institute of Science Education and
  Research Bhopal** and is **not** licensed to this project.
* It is included solely because it belongs to the institution-specific **thesis template**,
  where using it is appropriate.
* **If you fork this repository, or use the thesis template at another institution,
  remove or replace this file.** Its presence does not imply any endorsement of, or
  affiliation with, this project.

## 4. Software dependencies

PaperForge does not vendor third-party code. The following packages are installed by the
user and remain under their own licences.

| Package | Extra | Licence | Role |
|---|---|---|---|
| PyYAML | required | MIT | parsing `paper.yaml` |
| Pillow | `[figures]` | HPND (Python Imaging Library licence) | figure checks, TOC rendering |
| matplotlib | `[figures]` | PSF-based (Matplotlib licence) | demo figures |
| python-docx | `[docx]` | MIT | DOCX output |
| RDKit | `[structures]` | BSD-3-Clause | structure/reaction drawing |
| pytest, pytest-cov | `[dev]` | MIT | testing |
| pypdf | `[dev]` | BSD-3-Clause | PDF inspection in tests |
| ruff | `[dev]` | MIT | linting |
| build | `[dev]` | MIT | packaging |
| setuptools | build | MIT | build backend |

A `pip install paperforge` installs **only PyYAML**; everything else is opt-in.

## 5. Test fixtures

`tests/fixtures/providers/` contains small excerpts of live API responses captured on
2026-11-18, used to test parsing without network access. Provenance (endpoint, date,
trimming) is recorded in `tests/fixtures/providers/README.md`. They are test data, not a
redistribution of the providers' corpora.

## 6. Reporting an attribution problem

If you believe material in this repository is used without proper attribution or
permission, please open an issue or contact the maintainers — see `SECURITY.md` for the
private channel. Such reports are treated as priority defects.
