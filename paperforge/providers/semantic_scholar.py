"""Semantic Scholar adapter (S2 Graph API).

Useful for citation contexts and influential-citation counts. Anonymous access
exists but is aggressively rate limited, so the adapter is deliberately
last-in-the-queue for enrichment and degrades quietly.

Access (verified 2026-11-18): ``/graph/v1/paper/DOI:{doi}`` answered 200
anonymously. An optional ``SEMANTIC_SCHOLAR_API_KEY`` raises the quota.
"""
from __future__ import annotations

import os
from typing import Any

from ..research.schema import Author, OaStatus, PeerReview, VersionType, WorkRecord, normalise_doi
from .api import Capabilities, Provider, ProviderResult

BASE = "https://api.semanticscholar.org/graph/v1"
FIELDS = ("title,abstract,year,venue,publicationVenue,authors,externalIds,citationCount,"
          "influentialCitationCount,isOpenAccess,openAccessPdf,publicationTypes,"
          "publicationDate,journal,fieldsOfStudy,referenceCount")


class SemanticScholarProvider(Provider):
    name = "semantic_scholar"
    base_url = BASE
    license = "S2 API terms (ODC-BY for derived data; check per use)"
    docs_url = "https://api.semanticscholar.org/api-docs/"
    default_interval = 1.1
    capabilities = Capabilities(
        search=True, fetch_by_doi=True, fulltext_links=True, citation_counts=True,
        references=False, retraction_signal=False, oa_status=True, institutional_ids=False,
        requires_key=False,
        rate_limit_note="anonymous tier is heavily throttled; key strongly advised",
    )

    def __init__(self, **kw: Any) -> None:
        super().__init__(**kw)
        self.api_key = self.api_key or os.environ.get("SEMANTIC_SCHOLAR_API_KEY") or None

    def extra_headers(self) -> dict[str, str]:
        key = self.api_key or os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
        return {"x-api-key": key} if key else {}

    def search(self, query: str, limit: int = 25, **filters: Any) -> ProviderResult:
        params = {"query": query, "limit": max(1, min(int(limit), 100)), "fields": FIELDS}
        if filters.get("from_year"):
            params["year"] = f"{filters['from_year']}-"
        resp = self.http.get_json(f"{BASE}/paper/search", params)
        items = (resp.payload or {}).get("data") or []
        records = [self.normalise(i, retrieved_at=resp.retrieved_at, url=resp.url) for i in items]
        return self._finish(records, items, resp, total=(resp.payload or {}).get("total"))

    def fetch(self, identifier: str) -> ProviderResult:
        doi = normalise_doi(identifier)
        resp = self.http.get_json(f"{BASE}/paper/DOI:{doi}", {"fields": FIELDS})
        item = resp.payload or {}
        return self._finish([self.normalise(item, retrieved_at=resp.retrieved_at, url=resp.url)],
                            [item], resp, total=1)

    def normalise(self, raw: dict[str, Any], *, retrieved_at: str = "",
                  url: str = "") -> WorkRecord:
        ext = raw.get("externalIds") or {}
        venue = raw.get("venue") or ((raw.get("publicationVenue") or {}).get("name"))
        pdf = (raw.get("openAccessPdf") or {}).get("url")
        types = raw.get("publicationTypes") or []
        peer = PeerReview.PEER_REVIEWED if types else PeerReview.UNKNOWN
        rec = WorkRecord(
            doi=normalise_doi(ext.get("DOI")) or None,
            provider_ids={k: v for k, v in {"semantic_scholar": raw.get("paperId"),
                                            "pmid": ext.get("PubMed"),
                                            "arxiv": ext.get("ArXiv")}.items() if v},
            title=self._clean(raw.get("title")),
            abstract=self._clean(raw.get("abstract")),
            authors=[Author(name=a.get("name") or "")
                     for a in raw.get("authors") or [] if a.get("name")],
            publication_year=self._year(raw.get("year")),
            publication_date=raw.get("publicationDate") or None,
            venue=self._clean(venue),
            publisher=None,
            keywords=[f for f in (raw.get("fieldsOfStudy") or []) if f],
            article_type=(types[0].lower() if types else None),
            peer_review=peer,
            version_type=VersionType.VERSION_OF_RECORD if peer is PeerReview.PEER_REVIEWED
            else VersionType.UNKNOWN,
            oa_status=OaStatus.GREEN if raw.get("isOpenAccess") else OaStatus.UNKNOWN,
            fulltext_url=pdf,
            citation_count=raw.get("citationCount") if isinstance(raw.get("citationCount"), int) else None,
            citation_count_source=self.name if isinstance(raw.get("citationCount"), int) else None,
            citation_count_date=retrieved_at[:10] or None,
            retrieved_at=retrieved_at or None,
            source_url=url or None,
        )
        rec.provider_ids = {k: v for k, v in rec.provider_ids.items() if v}
        rec.sources.append(self._provenance(url, retrieved_at, raw))
        rec.ensure_id()
        return rec
