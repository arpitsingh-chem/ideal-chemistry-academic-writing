"""Provider abstraction: one adapter per scholarly source.

Every adapter implements the same small interface, so the rest of PaperForge
never needs to know which source a record came from:

===============  ============================================================
``name``         stable identifier used in provenance and the CLI
``capabilities`` what the source can actually do (verified, not assumed)
``search()``     free-text discovery, returns normalised records + raw payload
``fetch()``      look up one known identifier (DOI, PMID, arXiv id...)
``normalise()``  provider payload -> :class:`~paperforge.research.schema.WorkRecord`
===============  ============================================================

Failure policy: adapters raise :class:`~paperforge.providers.base.ProviderError`
subclasses. Callers (the sync pipeline, the CLI) catch ``ProviderError`` per
provider, so one unavailable source degrades a report instead of breaking it.
Nothing in this package fabricates a record to cover for a failed fetch.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, ClassVar

from ..research.schema import Provenance, WorkRecord, classify_subdiscipline
from .base import HttpClient, ProviderError, RawResponse, utcnow


@dataclass
class Capabilities:
    """What an adapter really supports. Readers of the coverage report rely on this."""

    search: bool = True
    fetch_by_doi: bool = True
    fulltext_links: bool = False
    citation_counts: bool = False
    references: bool = False
    retraction_signal: bool = False
    oa_status: bool = False
    institutional_ids: bool = False
    requires_key: bool = False
    requires_email: bool = False
    rate_limit_note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "search": self.search, "fetch_by_doi": self.fetch_by_doi,
            "fulltext_links": self.fulltext_links, "citation_counts": self.citation_counts,
            "references": self.references, "retraction_signal": self.retraction_signal,
            "oa_status": self.oa_status, "institutional_ids": self.institutional_ids,
            "requires_key": self.requires_key, "requires_email": self.requires_email,
            "rate_limit_note": self.rate_limit_note,
        }


@dataclass
class ProviderResult:
    """Records returned by one provider for one operation."""

    provider: str
    records: list[WorkRecord] = field(default_factory=list)
    raw: list[dict[str, Any]] = field(default_factory=list)
    retrieved_at: str = ""
    url: str = ""
    total_available: int | None = None
    warnings: list[str] = field(default_factory=list)
    from_cache: bool = False

    def __len__(self) -> int:
        return len(self.records)


class Provider:
    """Base class. Subclasses declare ``name``, ``base_url`` and ``capabilities``."""

    name: ClassVar[str] = "provider"
    base_url: ClassVar[str] = ""
    license: ClassVar[str | None] = None
    docs_url: ClassVar[str] = ""
    capabilities: ClassVar[Capabilities] = Capabilities()
    default_interval: ClassVar[float] = 0.0

    def __init__(self, *, app_version: str = "0", api_key: str | None = None,
                 mailto: str | None = None, client: HttpClient | None = None) -> None:
        self.api_key = api_key
        self.mailto = mailto
        self.http = client or HttpClient(
            self.name, app_version=app_version,
            base_headers=self.extra_headers(),
            min_interval=self.default_interval,
        )

    # -- hooks -------------------------------------------------------------
    def extra_headers(self) -> dict[str, str]:
        return {}

    def available(self) -> tuple[bool, str]:
        """Whether this adapter can run as configured, with the reason if not."""
        caps = self.capabilities
        if caps.requires_key and not self.api_key:
            return False, f"requires an API key (set {self.name.upper()}_API_KEY)"
        if caps.requires_email and not self.mailto:
            return False, "requires a contact e-mail (set PF_MAILTO)"
        return True, "ready"

    # -- interface ---------------------------------------------------------
    def search(self, query: str, limit: int = 25, **filters: Any) -> ProviderResult:
        raise NotImplementedError

    def fetch(self, identifier: str) -> ProviderResult:
        raise NotImplementedError

    def normalise(self, raw: dict[str, Any], *, retrieved_at: str = "",
                  url: str = "") -> WorkRecord:
        raise NotImplementedError

    # -- helpers -----------------------------------------------------------
    def _provenance(self, url: str, retrieved_at: str, raw: dict[str, Any] | None) -> Provenance:
        import hashlib
        import json
        digest = ""
        if raw is not None:
            digest = hashlib.sha256(json.dumps(raw, sort_keys=True, default=str).encode()).hexdigest()
        return Provenance(provider=self.name, url=url, retrieved_at=retrieved_at,
                          payload_sha256=digest, license=self.license)

    def _finish(self, records: list[WorkRecord], raw: list[dict[str, Any]], resp: RawResponse,
                *, total: int | None = None) -> ProviderResult:
        for rec in records:
            if rec.subdiscipline is None:
                rec.subdiscipline = classify_subdiscipline(rec.title, rec.abstract, rec.keywords)
        return ProviderResult(provider=self.name, records=records, raw=raw,
                             retrieved_at=resp.retrieved_at, url=resp.url,
                             total_available=total)

    @staticmethod
    def _clean(text: Any) -> str | None:
        """Whitespace-collapse and unescape a provider string; ``None`` if empty."""
        import html
        import re
        if not isinstance(text, str):
            return None
        value = html.unescape(re.sub(r"<[^>]+>", " ", text))
        value = re.sub(r"\s+", " ", value).strip()
        return value or None

    @staticmethod
    def _year(value: Any) -> int | None:
        import re
        if isinstance(value, int) and 1500 < value < 2200:
            return value
        m = re.search(r"(1[89]\d\d|20\d\d|21\d\d)", str(value or ""))
        return int(m.group(1)) if m else None


def now() -> str:
    return utcnow()


__all__ = ["Capabilities", "ProviderResult", "Provider", "ProviderError", "WorkRecord", "now", "time"]
