# How to add a scholarly provider

**Use when:** you want PaperForge to query a source it does not yet support.

Read this whole page before writing code. The hard part is not the HTTP call; it is the
decision about what the source can *honestly* support.

---

## 0. First: can you access it at all?

```bash
curl -s -o /dev/null -w '%{http_code}\n' 'https://api.example.org/search?q=chemistry'
```

| Result | Meaning |
|---|---|
| `200` with JSON | continue |
| `401` / `403` | needs a key, or blocks scripts. Try with a key; if it needs an institutional subscription, stop |
| `403` with an HTML body | a bot challenge (CDN). **Do not** work around it — record it as blocked |
| `429` | usable, but document the quota and set a politeness interval |

Read the provider's terms of service. If they forbid automated access, or require you to
bypass a CAPTCHA, the correct contribution is a `BLOCKED` entry (step 6), not an adapter.

## 1. Write the adapter

`paperforge/providers/example.py`:

```python
from __future__ import annotations
from typing import Any

from ..research.schema import Author, OaStatus, WorkRecord, normalise_doi
from .api import Capabilities, Provider, ProviderResult

BASE = "https://api.example.org"


class ExampleProvider(Provider):
    name = "example"
    base_url = BASE
    license = "CC0 metadata"                    # be exact
    docs_url = "https://api.example.org/docs"
    default_interval = 0.2                      # seconds between requests
    capabilities = Capabilities(
        search=True, fetch_by_doi=True,
        fulltext_links=False, citation_counts=True,
        references=False, retraction_signal=False,
        oa_status=True, institutional_ids=False,
        rate_limit_note="100 requests/hour without a key",
    )

    def search(self, query: str, limit: int = 25, **filters: Any) -> ProviderResult:
        resp = self.http.get_json(f"{BASE}/search", {"q": query, "n": min(limit, 100)})
        items = (resp.payload or {}).get("results") or []
        records = [self.normalise(i, retrieved_at=resp.retrieved_at, url=resp.url) for i in items]
        return self._finish(records, items, resp, total=(resp.payload or {}).get("total"))

    def fetch(self, identifier: str) -> ProviderResult:
        doi = normalise_doi(identifier)
        resp = self.http.get_json(f"{BASE}/work/{doi}")
        item = resp.payload or {}
        return self._finish([self.normalise(item, retrieved_at=resp.retrieved_at, url=resp.url)],
                            [item], resp, total=1)

    def normalise(self, raw: dict[str, Any], *, retrieved_at: str = "", url: str = "") -> WorkRecord:
        rec = WorkRecord(
            doi=normalise_doi(raw.get("doi")) or None,
            title=self._clean(raw.get("title")),
            authors=[Author(name=a["name"]) for a in raw.get("authors") or [] if a.get("name")],
            publication_year=self._year(raw.get("year")),
            venue=self._clean(raw.get("journal")),
            citation_count=raw.get("cited_by"),
            citation_count_source=self.name,
            citation_count_date=retrieved_at[:10] or None,
            # Anything the provider does not publish stays None. Do not guess.
            retrieved_at=retrieved_at or None,
            source_url=url or None,
        )
        rec.sources.append(self._provenance(url, retrieved_at, raw))
        rec.ensure_id()
        return rec
```

### The three rules that matter

1. **`None` for unknown.** Never default a missing field to `0`, `""`, `"closed"` or a
   sibling value.
2. **`Capabilities` must be true.** If there is no search endpoint, set `search=False` and
   raise `NotImplementedError` — callers rely on this to build the readiness table.
3. **Provenance on every record.** `self._provenance(...)` stores provider, URL, timestamp
   and a payload hash.

## 2. Register it

```python
# paperforge/providers/registry.py
from .example import ExampleProvider

IMPLEMENTED = {
    ...
    "example": ExampleProvider,
}
DISCOVERY = (..., "example")      # only if it has a real search endpoint
```

## 3. Capture a fixture

```bash
python3 - <<'PY'
import json, pathlib, urllib.request
url = "https://api.example.org/search?q=photoredox&n=2"
body = urllib.request.urlopen(url, timeout=25).read().decode()
pathlib.Path("tests/fixtures/providers/example_search.json").write_text(body)
PY
```

Add a row to `tests/fixtures/providers/README.md` with the endpoint and the capture date.

## 4. Test offline

```python
# tests/unit/test_providers_offline.py
class TestExampleParsing:
    def test_search(self):
        from paperforge.providers.example import ExampleProvider
        from ..conftest import FakeHttp, fixture_json

        provider = ExampleProvider(client=FakeHttp(fixture_json("example_search.json")))
        result = provider.search("photoredox", limit=2)
        assert result.records
        rec = result.records[0]
        assert rec.title
        assert rec.citation_count_source == "example"
        # the field this provider does not publish must stay unknown
        assert rec.license is None
```

## 5. Document it

* Add a row to the table in `DATA_SOURCES.md` with the verified status code, the date, the
  licence **and the exact quota behaviour**.
* Add the licence to `THIRD_PARTY_NOTICES.md`.
* Add it to the table in `README.md` §5.

## 6. If it turns out to be unusable

Record it instead of shipping it:

```python
BLOCKED["example"] = {
    "reason": "HTTP 403 Cloudflare challenge on the public API (verified 2026-11-18)",
    "verified_on": "2026-11-18",
    "alternative": "reachable via Crossref (posted-content DOIs)",
}
```

This is a **complete, valuable contribution**: it stops the next person from wasting an
afternoon, and it keeps `research providers` truthful.

## 7. Checklist

- [ ] `curl` status recorded, with date
- [ ] terms of service read; no access-control bypass
- [ ] `Capabilities` accurate (including `requires_key` / `requires_email`)
- [ ] `default_interval` respects the provider's stated rate
- [ ] unknown fields left `None`
- [ ] provenance attached
- [ ] fixture + offline test
- [ ] `DATA_SOURCES.md`, `THIRD_PARTY_NOTICES.md`, `README.md` updated
- [ ] `python -m pytest tests/unit -q` passes
- [ ] `python -m paperforge research providers` shows it truthfully
