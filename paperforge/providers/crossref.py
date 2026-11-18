"""Crossref adapter.

Crossref is the DOI registration agency: authoritative for the version of
record, publisher, page/volume data and — crucially — for **retraction
relations**, which is why PaperForge treats it as the integrity source.

Access (verified 2026-11-18): anonymous use is permitted; the ``mailto``
parameter puts the client in the "polite pool" with better reliability. No key
is required for metadata (a paid Plus token only adds extra services).
"""
from __future__ import annotations

from typing import Any

from ..research.schema import (Author, OaStatus, PeerReview, RetractionStatus,
                               VersionType, WorkRecord, normalise_doi, normalise_orcid)
from .api import Capabilities, Provider, ProviderResult

BASE = "https://api.crossref.org"


class CrossrefProvider(Provider):
    name = "crossref"
    base_url = BASE
    license = "Crossref metadata terms (open metadata)"
    docs_url = "https://api.crossref.org/swagger-ui/index.html"
    default_interval = 0.1
    capabilities = Capabilities(
        search=True, fetch_by_doi=True, fulltext_links=True, citation_counts=True,
        references=True, retraction_signal=True, oa_status=False, institutional_ids=True,
        requires_email=False,
        rate_limit_note="polite pool via mailto; anonymous use permitted",
    )

    def _params(self, **extra: Any) -> dict[str, Any]:
        params: dict[str, Any] = {"mailto": self.mailto}
        params.update(extra)
        return params

    def search(self, query: str, limit: int = 25, **filters: Any) -> ProviderResult:
        params = self._params(query=query, rows=max(1, min(int(limit), 200)),
                              select="DOI,title,author,container-title,published,issued,"
                                     "abstract,type,subject,license,is-referenced-by-count,"
                                     "relation,update-to,publisher,ISSN,URL")
        if filters.get("from_year"):
            params["filter"] = f"from-pub-date:{filters['from_year']}-01-01"
        resp = self.http.get_json(f"{BASE}/works", params)
        message = (resp.payload or {}).get("message") or {}
        items = message.get("items") or []
        records = [self.normalise(i, retrieved_at=resp.retrieved_at, url=resp.url) for i in items]
        return self._finish(records, items, resp, total=message.get("total-results"))

    def fetch(self, identifier: str) -> ProviderResult:
        doi = normalise_doi(identifier)
        resp = self.http.get_json(f"{BASE}/works/{doi}", self._params())
        item = (resp.payload or {}).get("message") or {}
        return self._finish([self.normalise(item, retrieved_at=resp.retrieved_at, url=resp.url)],
                            [item], resp, total=1)

    def retraction_notice(self, doi: str) -> dict[str, Any] | None:
        """Forward lookup: does a retraction notice *update* this DOI?

        Crossref records the link on the notice (``updates``), not always on the
        original, so asking the reverse direction is the reliable query.
        """
        params = self._params(filter=f"updates:{normalise_doi(doi)},update-type:retraction",
                              rows=1, select="DOI,title,type,update-to")
        resp = self.http.get_json(f"{BASE}/works", params)
        items = ((resp.payload or {}).get("message") or {}).get("items") or []
        return items[0] if items else None

    # -- normalise ---------------------------------------------------------
    def normalise(self, raw: dict[str, Any], *, retrieved_at: str = "",
                  url: str = "") -> WorkRecord:
        authors: list[Author] = []
        for a in raw.get("author") or []:
            name = " ".join(filter(None, [a.get("given"), a.get("family")])).strip() \
                or a.get("name") or ""
            if not name:
                continue
            affs = [self._clean(x.get("name")) for x in (a.get("affiliation") or [])]
            authors.append(Author(
                name=name,
                orcid=normalise_orcid(a.get("ORCID")),
                given=a.get("given") or None,
                family=a.get("family") or None,
                affiliations=[x for x in affs if x],
            ))

        title = (raw.get("title") or [None])[0]
        container = (raw.get("container-title") or [None])[0]

        doi = normalise_doi(raw.get("DOI"))
        relation = raw.get("relation") or {}
        update_to = raw.get("update-to") or []
        retraction = RetractionStatus.NONE_KNOWN
        notice_doi = None
        if str(raw.get("type", "")).lower() == "retraction":
            retraction = RetractionStatus.RETRACTED
        for rel_key, status in (("is-retracted-by", RetractionStatus.RETRACTED),
                                ("is-corrected-by", RetractionStatus.CORRECTION),
                                ("is-expression-of-concern-for", RetractionStatus.EXPRESSION_OF_CONCERN)):
            entries = relation.get(rel_key) or []
            if entries:
                retraction = status
                notice_doi = entries[0].get("id") if isinstance(entries[0], dict) else None
                break
        for upd in update_to:
            if (upd.get("type") or "").lower() == "retraction":
                retraction = RetractionStatus.RETRACTED
                notice_doi = normalise_doi(upd.get("DOI")) or notice_doi

        kind = (raw.get("type") or "").lower()
        version = VersionType.UNKNOWN
        peer = PeerReview.UNKNOWN
        if kind in {"posted-content", "preprint"}:
            version, peer = VersionType.PREPRINT, PeerReview.PREPRINT
        elif kind in {"journal-article", "book-chapter", "proceedings-article", "review-article"}:
            version, peer = VersionType.VERSION_OF_RECORD, PeerReview.PEER_REVIEWED
        elif kind == "erratum":
            version = VersionType.CORRECTION
        elif kind == "retraction":
            version = VersionType.RETRACTION

        published = (raw.get("published") or raw.get("issued") or {}).get("date-parts") or [[None]]
        year = published[0][0] if published and published[0] else None

        licenses = [l.get("URL") for l in (raw.get("license") or []) if l.get("URL")]
        cited = raw.get("is-referenced-by-count")
        refs = [normalise_doi(r.get("DOI")) for r in (raw.get("reference") or [])
                if isinstance(r, dict) and r.get("DOI")]

        rec = WorkRecord(
            doi=doi or None,
            provider_ids={"crossref": doi} if doi else {},
            title=self._clean(title),
            abstract=self._clean(raw.get("abstract")),
            authors=authors,
            publication_year=year if isinstance(year, int) else None,
            publication_date="-".join(str(p) for p in published[0] if p) if published and published[0] else None,
            venue=self._clean(container),
            publisher=self._clean(raw.get("publisher")),
            issn=[i for i in (raw.get("ISSN") or []) if i],
            keywords=[k for k in (raw.get("subject") or []) if k],
            article_type=kind or None,
            peer_review=peer,
            version_type=version,
            oa_status=OaStatus.UNKNOWN,
            license=licenses[0] if licenses else None,
            fulltext_url=raw.get("URL") or None,
            citation_count=cited if isinstance(cited, int) else None,
            citation_count_source=self.name if isinstance(cited, int) else None,
            citation_count_date=retrieved_at[:10] or None,
            retraction_status=retraction,
            retraction_notice_doi=notice_doi,
            references=refs,
            retrieved_at=retrieved_at or None,
            source_url=raw.get("URL") or url or None,
        )
        rec.sources.append(self._provenance(raw.get("URL") or f"{BASE}/works/{doi}", retrieved_at, raw))
        rec.ensure_id()
        return rec
