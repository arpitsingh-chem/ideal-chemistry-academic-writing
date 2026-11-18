"""Unpaywall adapter — open-access location enrichment.

Unpaywall answers one question extremely well: *where can this DOI be read for
free, legally?* It is therefore modelled as an **enricher**, not a discovery
source: it does not implement ``search``.

Access (verified 2026-11-18): ``https://api.unpaywall.org/v2/{doi}`` requires a
contact ``email`` parameter (no key). Requests without it are rejected, so the
adapter reports itself unavailable until ``PF_MAILTO`` is set.
"""
from __future__ import annotations

from typing import Any

from ..research.schema import OaStatus, WorkRecord, normalise_doi
from .api import Capabilities, Provider, ProviderResult

BASE = "https://api.unpaywall.org/v2"


class UnpaywallProvider(Provider):
    name = "unpaywall"
    base_url = BASE
    license = "Unpaywall data is CC0; API terms apply"
    docs_url = "https://unpaywall.org/products/api"
    default_interval = 0.1
    capabilities = Capabilities(
        search=False, fetch_by_doi=True, fulltext_links=True, citation_counts=False,
        references=False, retraction_signal=False, oa_status=True, institutional_ids=False,
        requires_email=True, rate_limit_note="email parameter mandatory",
    )

    def search(self, query: str, limit: int = 25, **filters: Any) -> ProviderResult:
        raise NotImplementedError("Unpaywall is a DOI enricher; it has no search endpoint")

    def fetch(self, identifier: str) -> ProviderResult:
        doi = normalise_doi(identifier)
        resp = self.http.get_json(f"{BASE}/{doi}", {"email": self.mailto})
        payload = resp.payload or {}
        return self._finish([self.normalise(payload, retrieved_at=resp.retrieved_at,
                                           url=resp.url)], [payload], resp, total=1)

    def normalise(self, raw: dict[str, Any], *, retrieved_at: str = "",
                  url: str = "") -> WorkRecord:
        status_map = {"gold": OaStatus.GOLD, "hybrid": OaStatus.HYBRID,
                      "green": OaStatus.GREEN, "bronze": OaStatus.BRONZE,
                      "closed": OaStatus.CLOSED}
        best = raw.get("best_oa_location") or {}
        oa = status_map.get((raw.get("oa_status") or "").lower(), OaStatus.UNKNOWN)
        if oa is OaStatus.UNKNOWN and raw.get("is_oa") is False:
            oa = OaStatus.CLOSED
        rec = WorkRecord(
            doi=normalise_doi(raw.get("doi")) or None,
            title=self._clean(raw.get("title")),
            publication_year=self._year(raw.get("year")),
            venue=self._clean(raw.get("journal_name")),
            publisher=self._clean(raw.get("publisher")),
            issn=[i for i in raw.get("journal_issns", "").split(",") if i],
            oa_status=oa,
            license=best.get("license") or None,
            fulltext_url=best.get("url_for_pdf") or best.get("url") or None,
            retrieved_at=retrieved_at or None,
            source_url=url or None,
        )
        # Only identifier + access facts: everything else is left unknown here so
        # that merge logic cannot mistake Unpaywall's sparse view for authority.
        rec.sources.append(self._provenance(f"{BASE}/{rec.doi}", retrieved_at, raw))
        rec.ensure_id()
        return rec
