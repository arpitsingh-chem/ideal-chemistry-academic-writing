"""DOAJ adapter — Directory of Open Access Journals.

DOAJ is the vetted allow-list of fully open-access, peer-reviewed journals
(independent vetting criteria, not self-declared). PaperForge uses it for two
purposes:

1. discovery of articles in vetted OA journals;
2. a *positive* open-access signal when recommending a submission venue.

Access (verified 2026-11-18): ``https://doaj.org/api/search/articles/{query}``
returns ``bibjson`` records, no key required.
"""
from __future__ import annotations

import urllib.parse
from typing import Any

from ..research.schema import Author, OaStatus, PeerReview, VersionType, WorkRecord, normalise_doi
from .api import Capabilities, Provider, ProviderResult

BASE = "https://doaj.org/api"


class DoajProvider(Provider):
    name = "doaj"
    base_url = BASE
    license = "DOAJ metadata is CC0"
    docs_url = "https://doaj.org/api/v2/docs"
    default_interval = 0.2
    capabilities = Capabilities(
        search=True, fetch_by_doi=False, fulltext_links=True, citation_counts=False,
        references=False, retraction_signal=False, oa_status=True, institutional_ids=False,
        rate_limit_note="query term embedded in the path; URL-encode it",
    )

    def _q(self, query: str) -> str:
        # DOAJ accepts a bare term or a field query: "bibjson.title:photoredox"
        return urllib.parse.quote(query.replace("/", " "), safe=':+-_"*()[]{}')

    def search(self, query: str, limit: int = 25, **filters: Any) -> ProviderResult:
        page_size = max(1, min(int(limit), 100))
        resp = self.http.get_json(
            f"{BASE}/search/articles/{self._q(query)}", {"pageSize": page_size, "page": 1})
        items = (resp.payload or {}).get("results") or []
        records = [self.normalise(i, retrieved_at=resp.retrieved_at, url=resp.url) for i in items]
        return self._finish(records, items, resp, total=(resp.payload or {}).get("total"))

    def fetch(self, identifier: str) -> ProviderResult:
        doi = normalise_doi(identifier)
        resp = self.http.get_json(f"{BASE}/search/articles/{self._q(f'doi:{doi}')}",
                                  {"pageSize": 1})
        items = (resp.payload or {}).get("results") or []
        return self._finish([self.normalise(i, retrieved_at=resp.retrieved_at, url=resp.url)
                             for i in items], items, resp, total=len(items))

    def normalise(self, raw: dict[str, Any], *, retrieved_at: str = "",
                  url: str = "") -> WorkRecord:
        bib = raw.get("bibjson") or {}
        authors = []
        for a in bib.get("author") or []:
            name = a.get("name") or ""
            if not name:
                continue
            authors.append(Author(name=name,
                                  orcid=None,
                                  affiliations=[a.get("affiliation")] if a.get("affiliation") else []))
        journal = bib.get("journal") or {}
        identifiers = {i.get("type"): i.get("id") for i in (bib.get("identifier") or [])}
        links = [l.get("url") for l in (bib.get("link") or []) if l.get("url")]
        rec = WorkRecord(
            doi=normalise_doi(identifiers.get("doi")) or None,
            provider_ids={"doaj": raw.get("id") or ""},
            title=self._clean(bib.get("title")),
            abstract=self._clean(bib.get("abstract")),
            authors=authors,
            publication_year=self._year(bib.get("year")),
            publication_date=bib.get("year") and f"{bib['year']}-01-01" or None,
            venue=self._clean(journal.get("title")),
            publisher=self._clean(journal.get("publisher")),
            issn=[i for i in [journal.get("issn"), journal.get("eissn")] if i],
            keywords=[k for k in (bib.get("keywords") or []) if k],
            article_type=(journal.get("license") and "journal-article") or "journal-article",
            peer_review=PeerReview.PEER_REVIEWED,
            version_type=VersionType.VERSION_OF_RECORD,
            oa_status=OaStatus.GOLD,       # DOAJ membership implies full OA
            license=(journal.get("license") or [{}])[0].get("type") if journal.get("license") else None,
            fulltext_url=links[0] if links else None,
            retrieved_at=retrieved_at or None,
            source_url=url or None,
        )
        rec.provider_ids = {k: v for k, v in rec.provider_ids.items() if v}
        rec.sources.append(self._provenance(links[0] if links else url, retrieved_at, raw))
        rec.ensure_id()
        return rec
