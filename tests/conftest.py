"""Shared test helpers.

Everything here is offline. Network access is never required to run the suite —
`-m network` marks the few tests that additionally exercise a live API, and they
skip by default.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "providers"


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def fixture_json(name: str) -> Any:
    return json.loads(fixture_text(name))


class FakeHttp:
    """Stand-in for :class:`paperforge.providers.base.HttpClient`.

    Records the URLs it was asked for so tests can assert on request shape, and
    can be told to raise a specific provider error to simulate outages.
    """

    def __init__(self, payload: Any = None, *, text: str | None = None,
                 status: int = 200, raise_exc: Exception | None = None,
                 provider: str = "fake") -> None:
        from paperforge.providers.base import CallStats

        self.payload = payload
        self.text = text
        self.status = status
        self.raise_exc = raise_exc
        self.provider = provider
        self.calls: list[tuple[str, dict[str, Any] | None]] = []
        self.stats = CallStats()

    def _maybe_raise(self) -> None:
        if self.raise_exc is not None:
            raise self.raise_exc

    def get_json(self, url: str, params: dict[str, Any] | None = None, *, allow_404: bool = False):
        from paperforge.providers.base import RawResponse

        self.calls.append((url, params))
        self._maybe_raise()
        return RawResponse(url=url, status=self.status, payload=self.payload,
                           retrieved_at="2026-11-18T00:00:00Z")

    def get_text(self, url: str, params: dict[str, Any] | None = None) -> str:
        self.calls.append((url, params))
        self._maybe_raise()
        return self.text or ""


@pytest.fixture
def fake_http():
    return FakeHttp


class StubProvider:
    """A minimal Provider used to test the pipeline without any HTTP at all."""

    name = "stub"
    capabilities = None

    def __init__(self, records, *, name="stub", fail: Exception | None = None):
        from paperforge.providers.api import Capabilities

        self.name = name
        self.records = records
        self.fail = fail
        self.capabilities = Capabilities()
        self.license = "test"
        self.docs_url = ""

    def available(self):
        return True, "ready"

    def search(self, query, limit=25, **filters):
        from paperforge.providers.api import ProviderResult

        if self.fail:
            raise self.fail
        return ProviderResult(provider=self.name, records=list(self.records)[:limit],
                              raw=[{}], retrieved_at="2026-11-18T00:00:00Z", url="stub://")

    def fetch(self, identifier):
        return self.search("")


class StubRegistry:
    """Registry replacement that returns pre-built stub providers."""

    def __init__(self, providers: dict[str, Any]):
        self.providers = providers

    def build(self, name: str):
        if name not in self.providers:
            from paperforge.providers.base import ProviderError

            raise ProviderError(name, f"unknown provider {name!r}")
        return self.providers[name]

    def status(self):
        return []

    def blocked(self):
        return {}

    def names(self):
        return sorted(self.providers)
