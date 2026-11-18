"""DataCite adapter — research data, software and repository outputs.

Chemistry papers increasingly cite datasets, crystal-structure deposits (CCDC),
and code. DataCite registers those DOIs (10.5281 Zenodo, 10.17172, 10.5517
crystallography, etc.), so it is the fourth pillar of reference verification
next to Crossref, Europe PMC and arXiv.

Access (verified 2026-11-18): ``https://api.datacite.org/dois`` is open, JSON:API
shaped, page-size capped at 1000.
"""
from __future__ import annotations

from typing import Any

from ..research.schema import Author, OaStatus, VersionType, WorkRecord, normalise_doi, normalise_orcid
from .api import Capabilities, Provider, ProviderResult

BASE = "https://api.datacite.org"


class DataCiteProvider(Provider):
    name = "datacite"
    base_url = BASE
    license = "DataCite metadata is CC0"
    docs_url = "https://support.datacite.org/docs/api"
    default_interval = 0.1
    capabilities = Capabilities(
        search=True, fetch_by_doi=True, fulltext_links=True, citation_counts=True,
        references=True, retraction_signal=False, oa_status=True, institutional_ids=True,
        rate_limit_note="page[size] capped at 1000",
    )

    def search(self, query: str, limit: int = 25, **filters: Any) -> ProviderResult:
        params: dict[str, Any] = {"query": query,
                                  "page[size]": max(1, min(int(limit), 100))}
        if filters.get("resource_type"):
            params["resource-type-id"] = filters["resource_type"]
        resp = self.http.get_json(f"{BASE}/dois", params)
        items = (resp.payload or {}).get("data") or []
        records = [self.normalise(i, retrieved_at=resp.retrieved_at, url=resp.url) for i in items]
        total = ((resp.payload or {}).get("meta") or {}).get("total")
        return self._finish(records, items, resp, total=total)

    def fetch(self, identifier: str) -> ProviderResult:
        doi = normalise_doi(identifier)
        resp = self.http.get_json(f"{BASE}/dois/{doi}")
        item = (resp.payload or {}).get("data") or {}
        return self._finish([self.normalise(item, retrieved_at=resp.retrieved_at, url=resp.url)],
                            [item], resp, total=1)

    def normalise(self, raw: dict[str, Any], *, retrieved_at: str = "",
                  url: str = "") -> WorkRecord:
        attrs = raw.get("attributes") or {}
        titles = attrs.get("titles") or []
        creators = []
        for c in attrs.get("creators") or []:
            name = c.get("name") or " ".join(filter(None, [c.get("givenName"), c.get("familyName")]))
            if not name:
                continue
            creators.append(Author(
                name=name,
                orcid=normalise_orcid((c.get("nameIdentifiers") or [{}])[0].get("nameIdentifier")
                                      if c.get("nameIdentifiers") else None),
                given=c.get("givenName") or None,
                family=c.get("familyName") or None,
                affiliations=[a.get("name") for a in (c.get("affiliation") or [])
                              if isinstance(a, dict) and a.get("name")],
            ))
        types = attrs.get("types") or {}
        rights = [r.get("rightsUri") or r.get("rights") for r in (attrs.get("rightsList") or [])]
        cited = attrs.get("citationCount")
        rec = WorkRecord(
            doi=normalise_doi(attrs.get("doi")) or None,
            provider_ids={"datacite": attrs.get("doi") or ""},
            title=self._clean(titles[0].get("title")) if titles else None,
            abstract=self._clean((attrs.get("descriptions") or [{}])[0].get("description")
                                 if attrs.get("descriptions") else None),
            authors=creators,
            publication_year=attrs.get("publicationYear") if isinstance(attrs.get("publicationYear"), int) else None,
            venue=self._clean(attrs.get("publisher")),
            publisher=self._clean(attrs.get("publisher")),
            keywords=[s.get("subject") for s in (attrs.get("subjects") or []) if s.get("subject")],
            article_type=(types.get("resourceTypeGeneral") or "").lower() or None,
            version_type=VersionType.VERSION_OF_RECORD,
            oa_status=OaStatus.GREEN if rights else OaStatus.UNKNOWN,
            license=rights[0] if rights else None,
            fulltext_url=attrs.get("url") or None,
            citation_count=cited if isinstance(cited, int) else None,
            citation_count_source=self.name if isinstance(cited, int) else None,
            citation_count_date=retrieved_at[:10] or None,
            references=[normalise_doi(r.get("relatedIdentifier")) for r in
                        (attrs.get("relatedIdentifiers") or [])
                        if r.get("relatedIdentifierType") == "DOI"][:50],
            retrieved_at=retrieved_at or None,
            source_url=url or None,
        )
        rec.provider_ids = {k: v for k, v in rec.provider_ids.items() if v}
        rec.sources.append(self._provenance(attrs.get("url") or url, retrieved_at, raw))
        rec.ensure_id()
        return rec
