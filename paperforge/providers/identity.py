"""Research-identity adapters: ORCID and ROR.

Both are identity *registries*, not publication indexes, and are modelled as
lookups the rest of the pipeline calls when it needs to resolve a person or an
institution rather than as discovery sources.

Access (verified 2026-11-18):
* ORCID public API v3.0 — ``pub.orcid.org/v3.0/...`` answers JSON with
  ``Accept: application/json`` and needs no token for public records.
* ROR v2 — ``api.ror.org/v2/organizations`` answers JSON, no key.
"""
from __future__ import annotations

from typing import Any

from ..research.schema import normalise_orcid
from .api import Capabilities, Provider, ProviderResult
from .base import ProviderError

ORCID_BASE = "https://pub.orcid.org/v3.0"
ROR_BASE = "https://api.ror.org/v2"


class OrcidProvider(Provider):
    name = "orcid"
    base_url = ORCID_BASE
    license = "ORCID public data (CC0 for the iD; profile terms apply)"
    docs_url = "https://info.orcid.org/documentation/api-reference/"
    default_interval = 0.2
    capabilities = Capabilities(
        search=True, fetch_by_doi=False, fulltext_links=False, citation_counts=False,
        references=False, retraction_signal=False, oa_status=False, institutional_ids=True,
        rate_limit_note="public API, no token for public records",
    )

    def extra_headers(self) -> dict[str, str]:
        return {"Accept": "application/json"}

    def search(self, query: str, limit: int = 25, **filters: Any) -> ProviderResult:
        resp = self.http.get_json(f"{ORCID_BASE}/expanded-search/",
                                  {"q": query, "rows": max(1, min(int(limit), 100))})
        payload = resp.payload or {}
        return ProviderResult(provider=self.name, records=[], raw=[payload],
                              retrieved_at=resp.retrieved_at, url=resp.url,
                              total_available=(payload.get("num-found")))

    def person(self, orcid: str) -> dict[str, Any] | None:
        """Fetch a public person record; returns the raw JSON payload."""
        oid = normalise_orcid(orcid)
        if not oid:
            raise ProviderError(self.name, f"invalid ORCID iD: {orcid!r}")
        resp = self.http.get_json(f"{ORCID_BASE}/{oid}/person", None)
        return resp.payload

    def works(self, orcid: str) -> list[dict[str, Any]]:
        oid = normalise_orcid(orcid)
        if not oid:
            raise ProviderError(self.name, f"invalid ORCID iD: {orcid!r}")
        resp = self.http.get_json(f"{ORCID_BASE}/{oid}/works", None)
        groups = ((resp.payload or {}).get("group")) or []
        out = []
        for g in groups:
            summary = ((g.get("work-summary") or [{}])[0]) or {}
            ids = {e.get("external-id-type"): e.get("external-id-value")
                   for e in ((summary.get("external-ids") or {}).get("external-id") or [])}
            out.append({
                "title": ((summary.get("title") or {}).get("title") or {}).get("value"),
                "doi": ids.get("doi"),
                "year": (((summary.get("publication-date") or {}).get("year") or {}).get("value")),
                "type": summary.get("type"),
                "put_code": summary.get("put-code"),
            })
        return out

    def normalise(self, raw: dict[str, Any], *, retrieved_at: str = "",
                  url: str = "") -> Any:   # identity records are not works
        raise NotImplementedError("ORCID records describe people, not publications")

    def fetch(self, identifier: str) -> ProviderResult:
        payload = self.person(identifier) or {}
        return ProviderResult(provider=self.name, records=[], raw=[payload],
                              retrieved_at="", url=f"{ORCID_BASE}/{identifier}/person")


class RorProvider(Provider):
    name = "ror"
    base_url = ROR_BASE
    license = "ROR data is CC0"
    docs_url = "https://ror.readme.io/docs/rest-api"
    default_interval = 0.2
    capabilities = Capabilities(
        search=True, fetch_by_doi=False, fulltext_links=False, citation_counts=False,
        references=False, retraction_signal=False, oa_status=False, institutional_ids=True,
        rate_limit_note="open API, no key",
    )

    def search(self, query: str, limit: int = 10, **filters: Any) -> ProviderResult:
        resp = self.http.get_json(f"{ROR_BASE}/organizations",
                                  {"query": query, "page": 1})
        payload = resp.payload or {}
        items = payload.get("items") or []
        return ProviderResult(provider=self.name, records=[], raw=items[:limit],
                              retrieved_at=resp.retrieved_at, url=resp.url,
                              total_available=payload.get("number_of_results"))

    def organisation(self, query: str) -> dict[str, Any] | None:
        """Best-match institution record (v2 schema: ``names``, ``locations``, ``ids``)."""
        res = self.search(query, limit=1)
        return res.raw[0] if res.raw else None

    @staticmethod
    def summarise(raw: dict[str, Any]) -> dict[str, Any]:
        """Flatten a ROR v2 record to the fields PaperForge stores."""
        names = raw.get("names") or []
        display = next((n.get("value") for n in names if n.get("types", [""])[0] in ("ror_display", "label")), None) \
            or (names[0].get("value") if names else None)
        locations = raw.get("locations") or []
        country = None
        city = None
        if locations:
            geo = (locations[0].get("geonames_details") or {})
            country = geo.get("country_name")
            city = geo.get("name")
        return {
            "ror": (raw.get("id") or "").rsplit("/", 1)[-1],
            "name": display,
            "country": country,
            "city": city,
            "types": raw.get("types") or [],
            "aliases": [n.get("value") for n in names if n.get("value")],
            "status": raw.get("status"),
        }

    def normalise(self, raw: dict[str, Any], *, retrieved_at: str = "",
                  url: str = "") -> Any:
        raise NotImplementedError("ROR records describe organisations, not publications")

    def fetch(self, identifier: str) -> ProviderResult:
        resp = self.http.get_json(f"{ROR_BASE}/organizations/{identifier}")
        return ProviderResult(provider=self.name, records=[], raw=[resp.payload or {}],
                              retrieved_at=resp.retrieved_at, url=resp.url)
