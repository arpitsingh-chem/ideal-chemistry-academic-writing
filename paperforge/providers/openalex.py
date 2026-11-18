"""OpenAlex adapter.

OpenAlex is the primary discovery index: broad chemistry coverage, institutional
and author identifiers, retraction flags and open-access status.

Access conditions (verified 2026-11-18 against the live API):

* No key needed, **but** keyless requests share one daily budget per IP address.
  When it is spent the API answers ``403``/``429`` with a JSON body containing
  ``reason: "daily_budget"`` and ``retryAfter`` seconds. PaperForge surfaces
  that as :class:`~paperforge.providers.base.RateLimited` (never a crash) and
  stops retrying when the reset is further away than two minutes.
* A free key (``OPENALEX_API_KEY``) has its own budget and is strongly
  recommended for synchronisation jobs.
* ``mailto`` is used for polite identification; it does **not** raise the quota.
"""
from __future__ import annotations

import os
from typing import Any

from ..research.schema import (Author, OaStatus, PeerReview, RetractionStatus,
                               VersionType, WorkRecord, normalise_doi, normalise_orcid)
from .api import Capabilities, Provider, ProviderResult
from .base import RateLimited

BASE = "https://api.openalex.org"


def rebuild_abstract(inverted_index: dict[str, list[int]] | None) -> str | None:
    """Reconstruct plain text from OpenAlex's ``abstract_inverted_index``.

    OpenAlex stores abstracts as ``{word: [positions]}`` for legal reasons.
    A naive ``" ".join(index)`` returns word-salad, so positions are rebuilt
    and a gap is rendered as ``[?]`` rather than silently closed up — a missing
    word must be visible, not papered over.
    """
    if not inverted_index:
        return None
    slots: dict[int, str] = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            if isinstance(pos, int) and 0 <= pos < 100_000:
                slots.setdefault(pos, word)
    if not slots:
        return None
    out: list[str] = []
    for i in range(max(slots) + 1):
        out.append(slots.get(i, "[?]"))
    return " ".join(out)


class OpenAlexProvider(Provider):
    name = "openalex"
    base_url = BASE
    license = "CC0-1.0 (OpenAlex metadata)"
    docs_url = "https://docs.openalex.org/"
    default_interval = 0.12
    capabilities = Capabilities(
        search=True, fetch_by_doi=True, fulltext_links=True, citation_counts=True,
        references=True, retraction_signal=True, oa_status=True, institutional_ids=True,
        requires_key=False,
        rate_limit_note="keyless requests share a per-IP daily budget; a free key has its own",
    )

    def __init__(self, **kw: Any) -> None:
        super().__init__(**kw)
        self.api_key = self.api_key or os.environ.get("OPENALEX_API_KEY") or None

    def _params(self, **extra: Any) -> dict[str, Any]:
        params: dict[str, Any] = {"mailto": self.mailto}
        if self.api_key:
            params["api_key"] = self.api_key
        params.update(extra)
        return params

    # -- search ------------------------------------------------------------
    def search(self, query: str, limit: int = 25, **filters: Any) -> ProviderResult:
        filt = []
        if filters.get("from_year"):
            filt.append(f"from_publication_date:{filters['from_year']}-01-01")
        if filters.get("to_year"):
            filt.append(f"to_publication_date:{filters['to_year']}-12-31")
        if filters.get("institution"):
            filt.append(f"institutions.id:{filters['institution']}")
        if filters.get("type"):
            filt.append(f"type:{filters['type']}")
        if filters.get("is_oa"):
            filt.append("is_oa:true")
        params = self._params(search=query or None, filter=",".join(filt) or None,
                              per_page=max(1, min(int(limit), 200)))
        resp = self.http.get_json(f"{BASE}/works", params)
        payload = resp.payload or {}
        items = payload.get("results") or []
        records = [self.normalise(item, retrieved_at=resp.retrieved_at, url=resp.url)
                   for item in items if isinstance(item, dict)]
        total = (payload.get("meta") or {}).get("count")
        return self._finish(records, items, resp, total=total)

    # -- fetch -------------------------------------------------------------
    def fetch(self, identifier: str) -> ProviderResult:
        doi = normalise_doi(identifier)
        if not doi:
            raise RateLimited(self.name, "fetch expects a DOI for OpenAlex")
        resp = self.http.get_json(f"{BASE}/works/doi:{doi}", self._params())
        item = resp.payload or {}
        rec = self.normalise(item, retrieved_at=resp.retrieved_at, url=resp.url)
        return self._finish([rec], [item], resp, total=1)

    def institution(self, name: str, limit: int = 5) -> list[dict[str, Any]]:
        """Institution lookup (used by the IISER Bhopal institutional adapter)."""
        resp = self.http.get_json(f"{BASE}/institutions",
                                  self._params(search=name, per_page=limit))
        return (resp.payload or {}).get("results") or []

    # -- normalise ---------------------------------------------------------
    def normalise(self, raw: dict[str, Any], *, retrieved_at: str = "",
                  url: str = "") -> WorkRecord:
        authors: list[Author] = []
        for authorship in raw.get("authorships") or []:
            person = authorship.get("author") or {}
            if not person.get("display_name"):
                continue
            insts = []
            for inst in authorship.get("institutions") or []:
                if inst.get("display_name"):
                    insts.append({
                        "name": inst["display_name"],
                        "ror": (inst.get("ror") or "").rsplit("/", 1)[-1] or "",
                        "openalex": (inst.get("id") or "").rsplit("/", 1)[-1] or "",
                        "country": inst.get("country_code") or "",
                    })
            authors.append(Author(
                name=person["display_name"],
                orcid=normalise_orcid(person.get("orcid")),
                given=person.get("given_name") or None,
                family=person.get("family_name") or None,
                affiliations=[i["name"] for i in insts],
                institutions=insts,
            ))

        location = raw.get("primary_location") or {}
        source = location.get("source") or {}
        oa = raw.get("open_access") or {}
        biblio = raw.get("biblio") or {}
        ids = raw.get("ids") or {}

        oa_map = {"gold": OaStatus.GOLD, "hybrid": OaStatus.HYBRID, "green": OaStatus.GREEN,
                  "bronze": OaStatus.BRONZE, "closed": OaStatus.CLOSED}
        oa_status = oa_map.get((oa.get("oa_status") or "").lower(), OaStatus.UNKNOWN)
        # OpenAlex leaves oa_status blank for many legitimate records; fall back
        # to its boolean, and only then to unknown.
        if oa_status is OaStatus.UNKNOWN and oa.get("is_oa") is True:
            oa_status = OaStatus.GREEN

        work_type = (raw.get("type") or "").lower()
        version = VersionType.UNKNOWN
        peer = PeerReview.UNKNOWN
        if work_type == "preprint":
            version, peer = VersionType.PREPRINT, PeerReview.PREPRINT
        elif work_type in {"article", "review", "book-chapter", "proceedings-article"}:
            version, peer = VersionType.VERSION_OF_RECORD, PeerReview.PEER_REVIEWED
        elif work_type == "erratum":
            version = VersionType.CORRECTION
        elif work_type == "retraction":
            version = VersionType.RETRACTION

        retraction = RetractionStatus.NONE_KNOWN
        if raw.get("is_retracted") is True:
            retraction = RetractionStatus.RETRACTED
        elif work_type == "retraction":
            retraction = RetractionStatus.RETRACTED

        venue = source.get("display_name") or None
        issn = [v for v in (source.get("issn_l"),) if v]
        issn += [v for v in (source.get("issn") or []) if v not in issn]

        cited = raw.get("cited_by_count")
        rec = WorkRecord(
            doi=normalise_doi(raw.get("doi")) or None,
            provider_ids={"openalex": (raw.get("id") or "").rsplit("/", 1)[-1] or ""},
            title=self._clean(raw.get("display_name") or raw.get("title")),
            abstract=rebuild_abstract(raw.get("abstract_inverted_index")),
            authors=authors,
            publication_year=self._year(raw.get("publication_year") or raw.get("publication_date")),
            publication_date=raw.get("publication_date") or None,
            venue=self._clean(venue),
            publisher=self._clean(source.get("host_organization_name")),
            issn=issn,
            keywords=[k.get("display_name") for k in (raw.get("keywords") or [])
                      if isinstance(k, dict) and k.get("display_name")],
            article_type=work_type or None,
            peer_review=peer,
            version_type=version,
            oa_status=oa_status,
            license=((location.get("license") or "") or None),
            fulltext_url=(location.get("landing_page_url") or oa.get("oa_url") or None),
            citation_count=cited if isinstance(cited, int) else None,
            citation_count_source=self.name if isinstance(cited, int) else None,
            citation_count_date=retrieved_at[:10] or None,
            retraction_status=retraction,
            # OpenAlex exposes referenced works as OpenAlex IDs, not DOIs, so the
            # reference list stays empty (an explicit "not supplied" state).
            references=[],
            retrieved_at=retrieved_at or None,
            source_url=url or None,
        )
        rec.provider_ids.update({
            "pmid": ids.get("pmid", "").rsplit("/", 1)[-1] if ids.get("pmid") else "",
        })
        rec.provider_ids = {k: v for k, v in rec.provider_ids.items() if v}
        rec.sources.append(self._provenance(url or f"{BASE}/works/{rec.provider_ids.get('openalex', '')}",
                                            retrieved_at, raw))
        rec.ensure_id()
        return rec
