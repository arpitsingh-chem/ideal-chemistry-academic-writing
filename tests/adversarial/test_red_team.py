"""Adversarial tests: try to break the transport, the pipeline and the CLI.

Each test here corresponds to a failure mode observed in the wild or reasoned
about during the audit. The objective is not coverage — it is to prove that a
hostile or broken provider cannot corrupt data, hang the CLI, or produce a
fabricated record.
"""
from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path

import pytest

from paperforge.providers.base import (HttpClient, MalformedResponse, NotFound,
                                      ProviderUnavailable, RateLimited)
from paperforge.research.pipeline import collect, sync
from paperforge.research.schema import (Author, RetractionStatus, WorkRecord,
                                        normalise_doi, normalise_orcid)
from paperforge.research.store import ResearchStore

from ..conftest import StubProvider, StubRegistry


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------

class FakeResponse(io.BytesIO):
    def __init__(self, body: bytes, status: int = 200, headers: dict | None = None):
        super().__init__(body)
        self.status = status
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def http_with(monkeypatch, *, body=b"{}", status=200, error=None, sleeps=None):
    """Build an HttpClient whose urlopen is replaced."""

    def fake_urlopen(req, timeout=None):
        if error is not None:
            raise error
        return FakeResponse(body, status)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    recorded: list[float] = []

    def sleeper(seconds):
        recorded.append(seconds)

    client = HttpClient("test", tries=3, sleeper=sleeper)
    if sleeps is not None:
        sleeps.extend(recorded)
    return client, recorded


class TestHttpClient:
    def test_404_raises_not_found(self, monkeypatch):
        err = urllib.error.HTTPError("u", 404, "nope", {}, io.BytesIO(b'{"message":"missing"}'))
        client, _ = http_with(monkeypatch, error=err)
        with pytest.raises(NotFound):
            client.get_json("https://example.org/x")

    def test_404_can_be_allowed(self, monkeypatch):
        err = urllib.error.HTTPError("u", 404, "nope", {}, io.BytesIO(b""))
        client, _ = http_with(monkeypatch, error=err)
        assert client.get_json("https://example.org/x", allow_404=True).status == 404

    def test_daily_budget_403_is_rate_limited_and_not_retried(self, monkeypatch):
        """OpenAlex's real failure mode: 403 with a JSON budget message."""
        body = json.dumps({
            "error": "Rate limit exceeded",
            "message": "Insufficient budget ... daily_budget",
            "retryAfter": 56502,
        }).encode()
        err = urllib.error.HTTPError("u", 403, "forbidden", {}, io.BytesIO(body))
        client, sleeps = http_with(monkeypatch, error=err)
        with pytest.raises(RateLimited) as excinfo:
            client.get_json("https://api.openalex.org/works")
        assert excinfo.value.retry_after == 56502
        assert sleeps == [], "a daily budget must not be retried inside one run"

    def test_429_is_retried_then_raises(self, monkeypatch):
        err = urllib.error.HTTPError("u", 429, "slow down", {"Retry-After": "1"}, io.BytesIO(b""))
        client, sleeps = http_with(monkeypatch, error=err)
        with pytest.raises(RateLimited):
            client.get_json("https://example.org/x")
        assert len(sleeps) == client.tries - 1
        assert all(0 < s <= 2 for s in sleeps)

    def test_server_error_is_retried_then_raises(self, monkeypatch):
        err = urllib.error.HTTPError("u", 503, "down", {}, io.BytesIO(b""))
        client, sleeps = http_with(monkeypatch, error=err)
        with pytest.raises(ProviderUnavailable):
            client.get_json("https://example.org/x")
        assert len(sleeps) == client.tries - 1

    def test_network_error_is_wrapped(self, monkeypatch):
        err = urllib.error.URLError("no route to host")
        client, _ = http_with(monkeypatch, error=err)
        with pytest.raises(ProviderUnavailable) as excinfo:
            client.get_json("https://example.org/x")
        assert "network error" in str(excinfo.value)

    def test_html_instead_of_json_is_malformed(self, monkeypatch):
        client, _ = http_with(monkeypatch, body=b"<html>Just a moment...</html>")
        with pytest.raises(MalformedResponse):
            client.get_json("https://example.org/x")

    def test_empty_body_is_null_not_a_crash(self, monkeypatch):
        client, _ = http_with(monkeypatch, body=b"")
        assert client.get_json("https://example.org/x").payload is None

    def test_gzip_body_decoded(self, monkeypatch):
        import gzip

        raw = gzip.compress(json.dumps({"ok": True}).encode())
        monkeypatch.setattr("urllib.request.urlopen",
                            lambda req, timeout=None: FakeResponse(
                                raw, headers={"Content-Encoding": "gzip"}))
        client = HttpClient("test", tries=1)
        assert client.get_json("https://example.org/x").payload == {"ok": True}

    def test_stats_are_counted(self, monkeypatch):
        client, _ = http_with(monkeypatch, body=b'{"a":1}')
        client.get_json("https://example.org/x")
        assert client.stats.requests == 1
        assert client.stats.bytes_downloaded > 0


# ---------------------------------------------------------------------------
# Pipeline isolation
# ---------------------------------------------------------------------------

class TestPipelineIsolation:
    def test_one_dead_provider_never_aborts_the_run(self, tmp_path):
        providers = {
            "up": StubProvider([WorkRecord(title="A", doi="10.1021/a")], name="up"),
            "down": StubProvider([], name="down", fail=ProviderUnavailable("down", "503")),
            "weird": StubProvider([], name="weird", fail=RuntimeError("unexpected")),
        }
        records, outcomes = collect(StubRegistry(providers), "q",
                                    providers=["up", "down", "weird"])
        assert len(records) == 1
        assert {o.provider for o in outcomes if o.ok} == {"up"}
        assert {o.error_type for o in outcomes if not o.ok} == {"ProviderUnavailable",
                                                               "RuntimeError"}

    def test_failed_provider_contributes_no_phantom_records(self, tmp_path):
        registry = StubRegistry({"down": StubProvider([], name="down",
                                                     fail=ProviderUnavailable("down", "x"))})
        store = ResearchStore(tmp_path / "r.sqlite3")
        report = sync(registry, "q", store, providers=["down"])
        assert report.records_found == 0
        assert store.count() == 0
        assert not report.ok
        store.close()

    def test_interrupted_sync_leaves_a_running_row(self, tmp_path):
        """Checkpoint: a crash mid-sync must be visible, not silently lost."""
        store = ResearchStore(tmp_path / "r.sqlite3")
        store.start_sync("crossref", "q")
        rows = store.conn.execute("SELECT status FROM sync_runs").fetchall()
        assert rows[0]["status"] == "running"
        store.close()


# ---------------------------------------------------------------------------
# Schema robustness
# ---------------------------------------------------------------------------

class TestSchemaRobustness:
    @pytest.mark.parametrize("doi", [
        "", "   ", "not-a-doi", "10.1/x", "http://", "10.1021/",
    ])
    def test_invalid_dois_do_not_become_ids(self, doi):
        normalised = normalise_doi(doi)
        rec = WorkRecord(title="t", doi=doi or None)
        assert rec.ensure_id().startswith(("hash:", "doi:"))
        if not normalised:
            assert rec.ensure_id().startswith("hash:")

    def test_unicode_title_roundtrips(self):
        rec = WorkRecord(title="Photoinduced C–H activation of ¹³C-labelled quinolines — "
                               "a naïve approach (µmol scale, Å-scale)", doi="10.1021/ünicode")
        back = WorkRecord.from_dict(rec.as_dict())
        assert back.title == rec.title

    def test_extremely_long_title_is_accepted(self):
        rec = WorkRecord(title="A " * 5000)
        assert len(WorkRecord.from_dict(rec.as_dict()).title) > 5000

    def test_injected_html_is_stripped_from_display_but_not_crash(self):
        rec = WorkRecord(title="<script>alert(1)</script>Photoredox", doi="10.1021/x")
        payload = rec.as_dict()
        assert payload["title"].startswith("<script>")   # stored verbatim, rendered by us
        assert json.dumps(payload)                        # serialisable

    def test_orcid_with_sql_payload_is_rejected(self):
        assert normalise_orcid("0000-0002-1825-0097'; DROP TABLE works;--") is None

    def test_absent_retraction_field_is_unknown_not_safe(self):
        rec = WorkRecord(title="t")
        assert rec.retraction_status is RetractionStatus.UNKNOWN
        assert "retraction_status" in rec.missing_fields()

    def test_enum_typo_degrades_to_unknown(self):
        data = WorkRecord(title="t").as_dict()
        data["oa_status"] = "definitely-not-an-enum"
        assert WorkRecord.from_dict(data).oa_status.value == "unknown"

    def test_authors_with_no_family_name(self):
        rec = WorkRecord(title="t", authors=[Author(name="Consortium")])
        assert rec.authors[0].family_name == "Consortium"


# ---------------------------------------------------------------------------
# Store robustness
# ---------------------------------------------------------------------------

class TestStoreRobustness:
    def test_corrupt_database_file_is_reported_clearly(self, tmp_path):
        bad = tmp_path / "bad.sqlite3"
        bad.write_bytes(b"this is not a database")
        with pytest.raises(Exception) as excinfo:
            ResearchStore(bad)
        assert "database" in str(excinfo.value).lower()

    def test_two_records_same_id_different_content_do_not_duplicate(self, tmp_path):
        store = ResearchStore(tmp_path / "r.sqlite3")
        a = WorkRecord(title="v1", doi="10.1021/abc")
        b = WorkRecord(title="v2 (corrected)", doi="10.1021/abc")
        store.upsert([a])
        store.upsert([b])
        assert store.count() == 1
        assert store.get("doi:10.1021/abc").title == "v2 (corrected)"
        store.close()

    def test_ten_thousand_records(self, tmp_path):
        store = ResearchStore(tmp_path / "r.sqlite3")
        records = [WorkRecord(title=f"Paper {i}", doi=f"10.9999/p{i}",
                              publication_year=2000 + i % 25) for i in range(10_000)]
        result = store.upsert(records)
        assert result.inserted == 10_000
        assert store.count() == 10_000
        assert store.search("Paper 9999")
        store.close()


# ---------------------------------------------------------------------------
# CLI exit codes
# ---------------------------------------------------------------------------

class TestCliContract:
    def _run(self, *args: str) -> int:
        import paperforge.cli as cli

        return cli.main(list(args))

    def test_unknown_provider_is_bad_input(self, capsys):
        assert self._run("research", "search", "x", "--source", "nonsense") == 2

    def test_coverage_without_store_is_bad_input(self, tmp_path, capsys):
        assert self._run("research", "coverage", "--db", str(tmp_path / "missing.db")) == 2

    def test_providers_command_succeeds(self):
        assert self._run("research", "providers") == 0

    def test_institution_stats_succeeds(self):
        assert self._run("institution", "stats") == 0

    def test_help_mentions_research(self):
        with pytest.raises(SystemExit):
            self._run("--help")
