"""arXiv adapter (Atom/XML).

Access (verified 2026-11-18): ``https://export.arxiv.org/api/query`` returns
Atom XML; anonymous use is permitted. arXiv asks for a 3-second delay between
requests, which this adapter enforces as ``default_interval``.

arXiv is a preprint server: every record is reported as
``peer_review=PREPRINT`` and ``version_type=PREPRINT``. Where the entry carries
an ``arxiv:doi`` (a journal DOI), the record is linked to the version of record
via ``version_of``.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

from ..research.schema import (Author, OaStatus, PeerReview, VersionType, WorkRecord,
                               normalise_doi)
from .api import Capabilities, Provider, ProviderResult
from .base import MalformedResponse

BASE = "https://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


class ArxivProvider(Provider):
    name = "arxiv"
    base_url = BASE
    license = "arXiv terms (per-article licences reported)"
    docs_url = "https://info.arxiv.org/help/api/index.html"
    default_interval = 3.0
    capabilities = Capabilities(
        search=True, fetch_by_doi=False, fulltext_links=True, citation_counts=False,
        references=False, retraction_signal=False, oa_status=True, institutional_ids=False,
        rate_limit_note="arXiv requests a 3 s delay between calls",
    )

    def search(self, query: str, limit: int = 25, **filters: Any) -> ProviderResult:
        # arXiv does not understand free-text chemistry notation well; the caller
        # decides the field query (all:, ti:, abs:).
        params = {"search_query": query, "start": 0,
                  "max_results": max(1, min(int(limit), 100)),
                  "sortBy": "submittedDate", "sortOrder": "descending"}
        text = self.http.get_text(BASE, params)
        items = self._parse(text)
        from .base import RawResponse
        resp = RawResponse(url=BASE, status=200, payload=None, retrieved_at=self._now())
        records = [self.normalise(i, retrieved_at=resp.retrieved_at, url=BASE) for i in items]
        return self._finish(records, items, resp, total=len(items))

    def fetch(self, identifier: str) -> ProviderResult:
        aid = identifier.strip()
        aid = re.sub(r"^https?://arxiv\.org/abs/", "", aid)
        if normalise_doi(aid):
            params = {"search_query": f'doi:"{normalise_doi(aid)}"', "max_results": 1}
        else:
            params = {"id_list": aid, "max_results": 1}
        text = self.http.get_text(BASE, params)
        items = self._parse(text)
        from .base import RawResponse
        resp = RawResponse(url=BASE, status=200, payload=None, retrieved_at=self._now())
        return self._finish([self.normalise(i, retrieved_at=resp.retrieved_at, url=BASE)
                             for i in items], items, resp, total=len(items))

    @staticmethod
    def _now() -> str:
        from .base import utcnow
        return utcnow()

    def _parse(self, text: str) -> list[dict[str, Any]]:
        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            raise MalformedResponse(self.name, f"not Atom: {exc}") from exc
        out: list[dict[str, Any]] = []
        for entry in root.findall("a:entry", NS):
            def txt(path: str) -> str | None:
                node = entry.find(path, NS)
                return node.text if node is not None and node.text else None

            out.append({
                "id": txt("a:id") or "",
                "title": txt("a:title"),
                "summary": txt("a:summary"),
                "published": txt("a:published"),
                "updated": txt("a:updated"),
                "authors": [n.text for n in entry.findall("a:author/a:name", NS) if n.text],
                "doi": txt("arxiv:doi"),
                "journal_ref": txt("arxiv:journal_ref"),
                "primary_category": (entry.find("arxiv:primary_category", NS).get("term")
                                     if entry.find("arxiv:primary_category", NS) is not None else None),
                "categories": [c.get("term") for c in entry.findall("a:category", NS) if c.get("term")],
                "license": txt("arxiv:license"),
            })
        return out

    def normalise(self, raw: dict[str, Any], *, retrieved_at: str = "",
                  url: str = "") -> WorkRecord:
        arxiv_id = (raw.get("id") or "").rsplit("/abs/", 1)[-1] or ""
        journal_doi = normalise_doi(raw.get("doi")) or None
        rec = WorkRecord(
            # A preprint's own identity is the arXiv id; the journal DOI (when
            # present) describes its version of record and must not become the
            # record's DOI, or deduplication would merge the two versions.
            doi=None,
            provider_ids={k: v for k, v in {"arxiv": arxiv_id,
                                            "doi_of_record": journal_doi}.items() if v},
            title=self._clean(raw.get("title")),
            abstract=self._clean(raw.get("summary")),
            authors=[Author(name=n) for n in raw.get("authors") or []],
            publication_year=self._year(raw.get("published")),
            publication_date=(raw.get("published") or "")[:10] or None,
            venue="arXiv",
            publisher="arXiv",
            keywords=[c for c in (raw.get("categories") or []) if c],
            article_type="preprint",
            peer_review=PeerReview.PREPRINT,
            version_type=VersionType.PREPRINT,
            version_of=journal_doi,
            oa_status=OaStatus.GREEN,
            license=raw.get("license"),
            fulltext_url=(raw.get("id") or None),
            retrieved_at=retrieved_at or None,
            source_url=url or None,
        )
        rec.sources.append(self._provenance(raw.get("id") or url, retrieved_at, raw))
        rec.ensure_id()
        return rec
