"""Provider registry: construction, availability probing and honest status.

The registry is the single place that knows which sources exist, which are
usable in the current configuration, and which are known to be unreachable —
with the evidence for that claim. ``paperforge research providers`` prints it.

A source is only listed in :data:`IMPLEMENTED` when an adapter exists **and**
has been exercised against the live API during development. Sources that
looked promising but block automated clients are recorded in
:data:`BLOCKED` instead of being faked.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Iterable

from .api import Provider
from .arxiv import ArxivProvider
from .base import ProviderError
from .crossref import CrossrefProvider
from .datacite import DataCiteProvider
from .doaj import DoajProvider
from .europepmc import EuropePmcProvider
from .identity import OrcidProvider, RorProvider
from .openalex import OpenAlexProvider
from .pubchem import PubChemProvider
from .semantic_scholar import SemanticScholarProvider
from .unpaywall import UnpaywallProvider

#: Adapters with a working, verified public API.
IMPLEMENTED: dict[str, type[Provider]] = {
    "openalex": OpenAlexProvider,
    "crossref": CrossrefProvider,
    "europepmc": EuropePmcProvider,
    "arxiv": ArxivProvider,
    "datacite": DataCiteProvider,
    "doaj": DoajProvider,
    "unpaywall": UnpaywallProvider,
    "semantic_scholar": SemanticScholarProvider,
    "orcid": OrcidProvider,
    "ror": RorProvider,
    "pubchem": PubChemProvider,
}

#: Discovery-first providers used by ``research search`` unless narrowed.
DISCOVERY = ("openalex", "crossref", "europepmc", "arxiv", "datacite", "doaj",
             "semantic_scholar")

#: Sources deliberately NOT integrated, with the observed evidence.
BLOCKED: dict[str, dict[str, str]] = {
    "chemrxiv": {
        "reason": "Cloudflare challenge (HTTP 403 'Just a moment...') on the public API; "
                  "no documented key-less JSON endpoint is reachable from a script",
        "verified_on": "2026-11-18",
        "alternative": "ChemRxiv records are reachable via Europe PMC (preprint index) "
                       "and via Crossref (posted-content DOIs)",
    },
    "google_scholar": {
        "reason": "No public API; scraping violates the Terms of Service",
        "verified_on": "2026-11-18",
        "alternative": "OpenAlex / Semantic Scholar citation counts",
    },
    "scopus": {
        "reason": "Requires an institutional Elsevier API key",
        "verified_on": "2026-11-18",
        "alternative": "OpenAlex (broader, open)",
    },
    "web_of_science": {
        "reason": "Requires institutional Clarivate access",
        "verified_on": "2026-11-18",
        "alternative": "OpenAlex / Crossref",
    },
    "dimensions": {
        "reason": "Free for research use only via a registered account and DSL; not a "
                  "public keyless API",
        "verified_on": "2026-11-18",
        "alternative": "OpenAlex",
    },
    "nist_webbook": {
        "reason": "No public API; HTML only, and bulk reuse needs permission",
        "verified_on": "2026-11-18",
        "alternative": "PubChem for structure/property cross-checks",
    },
    "core": {
        "reason": "API key required (free tier registration)",
        "verified_on": "2026-11-18",
        "alternative": "Unpaywall + Europe PMC full-text links",
    },
}


@dataclass
class ProviderStatus:
    name: str
    available: bool
    reason: str
    capabilities: dict[str, Any] = field(default_factory=dict)
    license: str | None = None
    docs_url: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "available": self.available, "reason": self.reason,
                "capabilities": self.capabilities, "license": self.license,
                "docs_url": self.docs_url}


class Registry:
    """Builds providers on demand and remembers their configured state."""

    def __init__(self, *, mailto: str | None = None, app_version: str = "0",
                 api_keys: dict[str, str] | None = None) -> None:
        self.mailto = mailto or os.environ.get("PF_MAILTO") or None
        self.app_version = app_version
        self.api_keys = {k.lower(): v for k, v in (api_keys or {}).items() if v}
        self._cache: dict[str, Provider] = {}
        self.failures: dict[str, str] = {}

    def build(self, name: str) -> Provider:
        key = name.lower().replace("-", "_")
        if key in self._cache:
            return self._cache[key]
        if key not in IMPLEMENTED:
            if key in BLOCKED:
                raise ProviderError(key, f"not integrated: {BLOCKED[key]['reason']}")
            raise ProviderError(key, f"unknown provider {name!r}; known: {', '.join(sorted(IMPLEMENTED))}")
        provider = IMPLEMENTED[key](
            app_version=self.app_version,
            api_key=self.api_keys.get(key),
            mailto=self.mailto,
        )
        self._cache[key] = provider
        return provider

    def names(self) -> list[str]:
        return sorted(IMPLEMENTED)

    def build_many(self, names: Iterable[str] | None = None) -> list[Provider]:
        out = []
        for name in (names or DISCOVERY):
            try:
                out.append(self.build(name))
            except ProviderError as exc:
                self.failures[name] = str(exc)
        return out

    def status(self) -> list[ProviderStatus]:
        rows = []
        for name in sorted(IMPLEMENTED):
            try:
                provider = self.build(name)
            except ProviderError as exc:       # pragma: no cover - defensive
                rows.append(ProviderStatus(name, False, str(exc)))
                continue
            ok, reason = provider.available()
            rows.append(ProviderStatus(
                name=name, available=ok, reason=reason,
                capabilities=provider.capabilities.as_dict(),
                license=provider.license, docs_url=provider.docs_url,
            ))
        return rows

    def blocked(self) -> dict[str, dict[str, str]]:
        return dict(BLOCKED)


def default_registry(app_version: str = "0") -> Registry:
    return Registry(mailto=os.environ.get("PF_MAILTO") or None, app_version=app_version)
