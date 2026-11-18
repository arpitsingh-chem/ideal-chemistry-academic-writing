"""PubChem adapter — authoritative molecular properties for chemistry checks.

PaperForge's own formula engine is dependency-free, but a second, independent
opinion on a molecular formula or monoisotopic mass is exactly the kind of
cross-check that catches a typo in a name/formula pairing. PubChem is used only
for that: **verification of a value the manuscript already asserts**, never as a
source of new claims about a compound.

Access (verified 2026-11-18): PUG-REST ``/compound/name/{name}/property/...``
is open; request rate is capped, so calls are spaced.
"""
from __future__ import annotations

import urllib.parse
from typing import Any

from .api import Capabilities, Provider, ProviderResult
from .base import ProviderError

BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
PROPS = "MolecularFormula,MolecularWeight,MonoisotopicMass,InChIKey,CanonicalSMILES,IUPACName"


class PubChemProvider(Provider):
    name = "pubchem"
    base_url = BASE
    license = "PubChem data is public domain (US NIH); terms of use apply"
    docs_url = "https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest"
    default_interval = 0.25
    capabilities = Capabilities(
        search=True, fetch_by_doi=False, fulltext_links=False, citation_counts=False,
        references=False, retraction_signal=False, oa_status=False, institutional_ids=False,
        rate_limit_note="<= 5 requests/second; dynamic throttling applies",
    )

    def search(self, query: str, limit: int = 10, **filters: Any) -> ProviderResult:
        """Name/CID search returning compound property records."""
        term = urllib.parse.quote(query.strip(), safe="")
        if not term:
            raise ProviderError(self.name, "empty query")
        url = f"{BASE}/compound/name/{term}/property/{PROPS}/JSON"
        resp = self.http.get_json(url, None, allow_404=True)
        if resp.status == 404:
            return ProviderResult(provider=self.name, retrieved_at=resp.retrieved_at, url=url)
        props = ((resp.payload or {}).get("PropertyTable") or {}).get("Properties") or []
        return ProviderResult(provider=self.name, raw=props[:limit],
                              retrieved_at=resp.retrieved_at, url=url, total_available=len(props))

    def fetch(self, identifier: str) -> ProviderResult:
        """Look up by CID."""
        url = f"{BASE}/compound/cid/{urllib.parse.quote(str(identifier), safe='')}/property/{PROPS}/JSON"
        resp = self.http.get_json(url, None, allow_404=True)
        props = ((resp.payload or {}).get("PropertyTable") or {}).get("Properties") or []
        return ProviderResult(provider=self.name, raw=props, retrieved_at=resp.retrieved_at, url=url)

    def properties(self, name: str) -> dict[str, Any] | None:
        res = self.search(name, limit=1)
        return res.raw[0] if res.raw else None

    def normalise(self, raw: dict[str, Any], *, retrieved_at: str = "",
                  url: str = "") -> Any:
        raise NotImplementedError("PubChem records describe compounds, not publications")
