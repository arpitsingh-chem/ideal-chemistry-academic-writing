"""Integration tests: schema -> dedup -> store -> coverage.

No network. Providers are stubbed with pre-built records so the behaviour under
test is the pipeline itself, not a remote API.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from paperforge.institutions import iiserb
from paperforge.providers.base import ProviderUnavailable, RateLimited
from paperforge.research.coverage import build_coverage, export_records
from paperforge.research.dedup import Verdict, compare, find_duplicates, merge
from paperforge.research.pipeline import reconcile, sync
from paperforge.research.schema import (Author, PeerReview, Provenance, RetractionStatus,
                                        VerificationStatus, VersionType, WorkRecord,
                                        normalise_doi, normalise_orcid, title_key)
from paperforge.research.store import ResearchStore

from ..conftest import StubProvider, StubRegistry


def make(doi=None, title="Photoredox arylation of quinoxalinones", family="Kalia",
         year=2026, venue="Organic Letters", provider="crossref", **kw) -> WorkRecord:
    rec = WorkRecord(doi=doi, title=title, authors=[Author(name=f"Dimpy {family}", family=family)],
                     publication_year=year, venue=venue, **kw)
    rec.sources.append(Provenance(provider=provider, url="https://example.org",
                                  retrieved_at="2026-11-18T00:00:00Z",
                                  payload_sha256="0" * 64))
    rec.ensure_id()
    return rec


class TestSchema:
    def test_unknown_is_none_not_a_guess(self):
        rec = WorkRecord(title="X")
        assert rec.doi is None and rec.citation_count is None
        assert "doi" in rec.missing_fields()

    def test_doi_normalisation(self):
        assert normalise_doi("https://doi.org/10.1021/JACS.5C13581") == "10.1021/jacs.5c13581"
        assert normalise_doi("doi:10.1021/ABC") == "10.1021/abc"
        assert normalise_doi("  10.1021/x.  ") == "10.1021/x"

    def test_work_id_is_doi_based_for_stability(self):
        a = make(doi="10.1021/abc")
        b = make(doi="https://doi.org/10.1021/ABC")
        assert a.work_id == b.work_id == "doi:10.1021/abc"

    def test_work_id_falls_back_to_content_hash(self):
        rec = WorkRecord(title="No DOI here", publication_year=2020,
                         authors=[Author(name="A Author", family="Author")])
        assert rec.ensure_id().startswith("hash:")

    @pytest.mark.parametrize("orcid,valid", [
        ("0000-0002-1825-0097", True),        # official example iD (valid check digit)
        ("https://orcid.org/0000-0002-1825-0097", True),
        ("0000-0002-1825-0098", False),       # wrong check digit
        ("0000-0002-1825", False),
        ("not-an-orcid", False),
    ])
    def test_orcid_check_digit(self, orcid, valid):
        got = normalise_orcid(orcid)
        assert (got is not None) is valid

    def test_roundtrip_preserves_everything(self):
        rec = make(doi="10.1021/abc", abstract="A", keywords=["k"], issn=["1234-5678"],
                   retraction_status=RetractionStatus.NONE_KNOWN)
        back = WorkRecord.from_dict(rec.as_dict())
        for field in ("doi", "title", "publication_year", "venue", "abstract",
                      "retraction_status", "keywords", "issn"):
            assert getattr(back, field) == getattr(rec, field), field

    def test_completeness_is_measured_not_asserted(self):
        sparse = WorkRecord(title="t")
        rich = make(doi="10.1021/x", abstract="a", keywords=["k"], publisher="ACS")
        assert sparse.completeness() < rich.completeness() <= 1.0


class TestDeduplication:
    def test_identical_doi_is_same(self):
        d = compare(make(doi="10.1021/abc"), make(doi="https://doi.org/10.1021/ABC"))
        assert d.verdict is Verdict.SAME and d.score == 1.0

    def test_different_dois_are_never_merged_on_titles(self):
        d = compare(make(doi="10.5281/zenodo.1"), make(doi="10.5281/zenodo.2"))
        assert d.verdict is Verdict.DISTINCT
        assert "different DOIs" in " ".join(d.conflicts)

    def test_version_suffix_is_linked_not_merged(self):
        d = compare(make(doi="10.25405/ncl.34472799"),
                    make(doi="10.25405/ncl.34472799.v1"))
        assert d.verdict is Verdict.RELATED_VERSION

    def test_preprint_and_version_of_record_are_linked(self):
        preprint = make(doi=None, provider="arxiv")
        preprint.version_type = VersionType.PREPRINT
        preprint.peer_review = PeerReview.PREPRINT
        preprint.version_of = "10.1021/abc"
        publisher = make(doi="10.1021/abc")
        d = compare(preprint, publisher)
        assert d.verdict is Verdict.RELATED_VERSION

    def test_missing_doi_uses_corroborating_signals(self):
        a = make(doi=None, provider="europepmc")
        b = make(doi=None, provider="openalex")
        d = compare(a, b)
        assert d.verdict is Verdict.SAME
        assert d.score >= 0.8
        assert d.explain()

    def test_same_title_different_authors_is_distinct(self):
        a = make(doi=None, title="Magnetic properties of lanthanide complexes", family="Patra")
        b = make(doi=None, title="Magnetic properties of lanthanide complexes", family="Koner")
        d = compare(a, b)
        assert d.verdict is Verdict.DISTINCT
        assert "no shared author surnames" in " ".join(d.conflicts)

    def test_blocking_groups_by_title_key(self):
        assert title_key("A Photoredox <i>Arylation</i>") == "photoredox arylation"

    def test_find_duplicates_reports_proposals_only(self):
        records = [make(doi=None, family="Kalia"), make(doi=None, family="Kalia")]
        proposals = find_duplicates(records)
        assert proposals and proposals[0]["verdict"] == "same"
        assert "explanation" in proposals[0]

    def test_merge_records_conflicts_and_precedence(self):
        a = make(doi="10.1021/abc", venue="Org. Lett.")
        a.sources[0].provider = "crossref"
        b = make(doi="10.1021/abc", venue="Organic Letters")
        b.sources[0].provider = "unpaywall"
        b.citation_count, b.citation_count_source = 12, "unpaywall"
        merged, audit = merge([a, b])
        assert merged.citation_count == 12
        assert merged.citation_count_source == "unpaywall"
        assert merged.verification in {VerificationStatus.CROSS_CHECKED,
                                       VerificationStatus.CONFLICTING}
        assert audit["kept_id"] == merged.work_id
        assert any(c["field"] == "venue" for c in audit["conflicts"])

    def test_merge_prefers_a_definite_enum_over_unknown(self):
        a = make(doi="10.1021/abc")
        a.retraction_status = RetractionStatus.UNKNOWN
        b = make(doi="10.1021/abc")
        b.retraction_status = RetractionStatus.RETRACTED
        merged, _ = merge([a, b])
        assert merged.retraction_status is RetractionStatus.RETRACTED


class TestStore:
    def test_migration_and_version(self, tmp_path):
        store = ResearchStore(tmp_path / "r.sqlite3")
        assert store.version() == 1
        store.close()

    def test_upsert_is_idempotent(self, tmp_path):
        store = ResearchStore(tmp_path / "r.sqlite3")
        rec = make(doi="10.1021/abc")
        first = store.upsert([rec])
        second = store.upsert([WorkRecord.from_dict(rec.as_dict())])
        assert (first.inserted, first.unchanged) == (1, 0)
        assert (second.inserted, second.unchanged) == (0, 1)
        assert store.count() == 1
        store.close()

    def test_update_when_content_changes(self, tmp_path):
        store = ResearchStore(tmp_path / "r.sqlite3")
        store.upsert([make(doi="10.1021/abc")])
        changed = make(doi="10.1021/abc", title="A completely different title")
        result = store.upsert([changed])
        assert result.updated == 1
        store.close()

    def test_lookup_by_identifier(self, tmp_path):
        store = ResearchStore(tmp_path / "r.sqlite3")
        store.upsert([make(doi="10.1021/abc")])
        assert store.find_by_identifier("doi", "10.1021/ABC") is not None
        assert store.find_by_identifier("doi", "10.1021/nope") is None
        store.close()

    def test_raw_payloads_are_stored_separately(self, tmp_path):
        store = ResearchStore(tmp_path / "r.sqlite3")
        rec = make(doi="10.1021/abc")
        store.upsert([rec], raw_by_work={rec.work_id: [{"provider": "crossref", "x": 1}]})
        rows = store.conn.execute("SELECT raw FROM provenance").fetchall()
        assert rows and json.loads(rows[0]["raw"])["provider"] == "crossref"
        store.close()

    def test_merge_removes_the_absorbed_row_and_is_logged(self, tmp_path):
        store = ResearchStore(tmp_path / "r.sqlite3")
        a, b = make(doi=None, family="Kalia"), make(doi=None, family="Kalia")
        store.upsert([a, b])
        before = store.count()
        store.record_merge(a.work_id, b.work_id, compare(a, b))
        assert store.count() == before - 1
        assert store.stats()["merged_away"] == 1
        store.close()

    def test_sync_history(self, tmp_path):
        store = ResearchStore(tmp_path / "r.sqlite3")
        run = store.start_sync("crossref", "query")
        store.finish_sync(run, status="ok")
        assert store.stats()["last_sync"]
        store.close()


class TestPipeline:
    def test_sync_inserts_and_merges(self, tmp_path):
        a = make(doi=None, family="Kalia")
        b = make(doi=None, family="Kalia")
        registry = StubRegistry({"one": StubProvider([a], name="one"),
                                 "two": StubProvider([b], name="two")})
        store = ResearchStore(tmp_path / "r.sqlite3")
        report = sync(registry, "q", store, providers=["one", "two"])
        assert report.records_found == 2
        assert report.unique_records == 1
        assert report.merged_duplicates == 1
        assert store.count() == 1
        store.close()

    def test_provider_failure_does_not_stop_the_sync(self, tmp_path):
        good = StubProvider([make(doi="10.1021/abc")], name="good")
        bad = StubProvider([], name="bad", fail=ProviderUnavailable("bad", "boom"))
        store = ResearchStore(tmp_path / "r.sqlite3")
        report = sync(StubRegistry({"good": good, "bad": bad}), "q", store,
                      providers=["good", "bad"])
        assert report.ok
        assert report.failed_providers == ["bad"]
        assert store.count() == 1
        assert any("incomplete" in line for line in report.summary_lines())
        store.close()

    def test_rate_limit_is_recorded_with_its_retry_after(self, tmp_path):
        limited = StubProvider([], name="limited",
                               fail=RateLimited("limited", "budget spent", status=429,
                                                retry_after=3600))
        store = ResearchStore(tmp_path / "r.sqlite3")
        report = sync(StubRegistry({"limited": limited}), "q", store, providers=["limited"])
        outcome = report.providers[0]
        assert outcome.error_type == "rate_limited"
        assert outcome.retry_after == 3600
        state = store.stats()["provider_state"]
        assert state and state[0]["consecutive_failures"] == 1
        store.close()

    def test_dry_run_writes_nothing(self, tmp_path):
        store = ResearchStore(tmp_path / "r.sqlite3")
        registry = StubRegistry({"one": StubProvider([make(doi="10.1021/abc")], name="one")})
        report = sync(registry, "q", store, providers=["one"], dry_run=True)
        assert report.upsert.inserted == 0
        assert store.count() == 0
        assert store.stats()["sync_runs"] == 0
        store.close()

    def test_reconcile_keeps_version_pairs(self, tmp_path):
        preprint = make(doi=None, provider="arxiv")
        preprint.version_type = VersionType.PREPRINT
        publisher = make(doi="10.1021/abc", provider="crossref")
        unique, merges = reconcile([preprint, publisher])
        assert len(unique) == 2      # linked, not destroyed
        assert merges == 0


class TestCoverageReport:
    def test_report_is_measured_and_states_gaps(self, tmp_path):
        store = ResearchStore(tmp_path / "r.sqlite3")
        store.upsert([make(doi="10.1021/abc")])
        cov = build_coverage(store)
        assert cov.works == 1
        assert cov.with_doi == 1
        assert cov.gaps, "a coverage report must always state its known gaps"
        assert "none_known" in " ".join(cov.gaps) or "Retraction" in " ".join(cov.gaps)
        text = cov.text()
        assert "known unavailable sources" in text
        assert "institutional collection" in text
        store.close()

    def test_empty_store_does_not_pretend_to_have_data(self, tmp_path):
        store = ResearchStore(tmp_path / "r.sqlite3")
        cov = build_coverage(store)
        assert cov.works == 0
        assert any("empty" in g for g in cov.gaps)
        store.close()

    def test_export_json_and_csv(self, tmp_path):
        store = ResearchStore(tmp_path / "r.sqlite3")
        store.upsert([make(doi="10.1021/abc")])
        n_json = export_records(store, str(tmp_path / "out.json"), fmt="json")
        n_csv = export_records(store, str(tmp_path / "out.csv"), fmt="csv")
        assert n_json == n_csv == 1
        payload = json.loads((tmp_path / "out.json").read_text())
        assert payload["count"] == 1 and payload["records"][0]["doi"] == "10.1021/abc"
        with pytest.raises(ValueError):
            export_records(store, str(tmp_path / "out.x"), fmt="xml")
        store.close()


class TestInstitutionalCollection:
    def test_snapshot_is_preserved(self):
        s = iiserb.stats()
        assert s.works > 1000
        assert s.venues > 100
        assert s.first_year and s.last_year

    def test_stats_do_not_claim_absent_fields(self):
        """The snapshot has no is_oa field; that must read as unknown, not zero."""
        s = iiserb.stats()
        assert s.open_access is None
        assert s.retracted is None

    def test_search_finds_a_known_record(self):
        hits = iiserb.search("photoredox", limit=5)
        assert hits
        assert all("photoredox" in (h.get("title", "") + " " + (h.get("abstract") or "")).lower()
                   for h in hits)

    def test_coverage_note_is_honest(self):
        note = iiserb.coverage_note()
        assert "not a live query" in note and "not complete" in note
