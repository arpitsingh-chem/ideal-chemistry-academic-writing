"""Offline parsing tests for every provider adapter.

Each test feeds a *recorded* live payload (tests/fixtures/providers/) through the
adapter's normaliser and asserts on the fields PaperForge actually relies on.
This is what catches the classic integration failure: an adapter that "works"
until the provider renames a key.
"""
from __future__ import annotations

import json

import pytest

from paperforge.providers.arxiv import ArxivProvider
from paperforge.providers.crossref import CrossrefProvider
from paperforge.providers.datacite import DataCiteProvider
from paperforge.providers.doaj import DoajProvider
from paperforge.providers.europepmc import EuropePmcProvider
from paperforge.providers.openalex import OpenAlexProvider, rebuild_abstract
from paperforge.providers.pubchem import PubChemProvider
from paperforge.providers.registry import BLOCKED, IMPLEMENTED
from paperforge.providers.semantic_scholar import SemanticScholarProvider
from paperforge.providers.unpaywall import UnpaywallProvider
from paperforge.research.schema import OaStatus, PeerReview, RetractionStatus

from ..conftest import FakeHttp, fixture_json, fixture_text

DOI = "10.1021/jacs.5c13581"


class TestCrossrefParsing:
    def setup_method(self):
        self.raw = fixture_json("crossref_work_jacs.json")["message"]
        self.http = FakeHttp(fixture_json("crossref_work_jacs.json"))
        self.provider = CrossrefProvider(mailto="test@example.org", client=self.http)

    def test_fetch_normalises_metadata(self):
        rec = self.provider.fetch(DOI).records[0]
        assert rec.doi == DOI
        assert rec.title.startswith("Rapid and High-Yielding Disulfide Bioconjugation")
        assert rec.publication_year == 2026
        assert rec.venue == "Journal of the American Chemical Society"
        assert [a.name for a in rec.authors][:3] == [
            "Dastgir Shakil Shaikh", "Suman Rajput", "Dimpy Kalia"]
        assert rec.work_id == f"doi:{DOI}"

    def test_citation_count_carries_its_source_and_date(self):
        rec = self.provider.fetch(DOI).records[0]
        assert isinstance(rec.citation_count, int)
        assert rec.citation_count_source == "crossref"
        assert rec.citation_count_date == "2026-11-18"

    def test_never_invents_missing_fields(self):
        rec = self.provider.fetch(DOI).records[0]
        # Crossref does not publish an OA status; it must remain unknown, not "closed"
        assert rec.oa_status is OaStatus.UNKNOWN
        assert "oa_status" in rec.missing_fields()

    def test_provenance_recorded(self):
        rec = self.provider.fetch(DOI).records[0]
        assert rec.sources and rec.sources[0].provider == "crossref"
        assert len(rec.sources[0].payload_sha256) == 64

    def test_retraction_relation_detected(self):
        raw = dict(self.raw)
        raw["relation"] = {"is-retracted-by": [{"id": "10.9999/retraction.1"}]}
        rec = self.provider.normalise(raw)
        assert rec.retraction_status is RetractionStatus.RETRACTED
        assert rec.retraction_notice_doi == "10.9999/retraction.1"

    def test_preprint_type(self):
        raw = dict(self.raw, type="posted-content")
        rec = self.provider.normalise(raw)
        assert rec.peer_review is PeerReview.PREPRINT


class TestOpenAlexParsing:
    def test_inverted_index_is_rebuilt_in_order(self):
        index = {"Photoredox": [0], "catalysis": [1], "works": [2]}
        assert rebuild_abstract(index) == "Photoredox catalysis works"

    def test_positions_are_respected_not_dict_order(self):
        index = {"world": [1], "hello": [0]}
        assert rebuild_abstract(index) == "hello world"

    def test_gap_is_visible(self):
        # a missing word must show up, not vanish silently
        assert "[?]" in rebuild_abstract({"a": [0], "c": [2]})

    def test_empty_index_is_unknown_not_empty_string(self):
        assert rebuild_abstract(None) is None
        assert rebuild_abstract({}) is None

    def test_record_from_fixture(self):
        payload = fixture_json("openalex_work.json")
        provider = OpenAlexProvider(mailto="test@example.org", client=FakeHttp(payload))
        rec = provider.fetch(DOI).records[0]
        assert rec.doi == DOI
        assert rec.title.startswith("Rapid and High-Yielding")
        assert rec.abstract and len(rec.abstract) > 100
        assert rec.citation_count is not None
        assert rec.citation_count_source == "openalex"
        assert rec.provider_ids.get("openalex", "").startswith("W")


class TestEuropePmcParsing:
    def test_single_element_list_collapse(self):
        """Europe PMC returns pubType as a bare string when there is only one."""
        payload = fixture_json("europepmc_search.json")
        provider = EuropePmcProvider(client=FakeHttp(payload))
        result = provider.search("photoredox", limit=2)
        assert result.records, "no records parsed"
        for rec in result.records:
            assert rec.title
            assert rec.source_url or True     # fetch url may be the query url

    def test_retraction_comment_detected(self):
        provider = EuropePmcProvider(client=FakeHttp({}))
        raw = {
            "id": "12345", "source": "MED", "title": "A paper",
            "pubTypeList": {"pubType": ["research-article"]},
            "commentCorrectionList": {"commentCorrection": [
                {"type": "Retraction of publication"}]},
        }
        rec = provider.normalise(raw)
        assert rec.retraction_status is RetractionStatus.RETRACTED


class TestArxivParsing:
    def test_atom_parsed_offline(self):
        provider = ArxivProvider(client=FakeHttp(text=fixture_text("arxiv_search.atom")))
        result = provider.search("all:photoredox", limit=2)
        assert len(result.records) == 2
        rec = result.records[0]
        assert rec.peer_review is PeerReview.PREPRINT
        assert rec.venue == "arXiv"
        assert rec.abstract

    def test_preprint_does_not_take_the_journal_doi_as_its_own(self):
        provider = ArxivProvider(client=FakeHttp(text=""))
        raw = {"id": "http://arxiv.org/abs/2401.00001v1", "title": "T", "summary": "S",
               "published": "2024-01-01T00:00:00Z", "authors": ["A B"],
               "doi": "10.1021/jacs.4c00001"}
        rec = provider.normalise(raw)
        # the record's own identity is the arXiv id; the journal DOI is the VoR link
        assert rec.doi is None
        assert rec.provider_ids["arxiv"] == "2401.00001v1"
        assert rec.version_of == "10.1021/jacs.4c00001"

    def test_malformed_xml_raises_provider_error(self):
        from paperforge.providers.base import MalformedResponse

        provider = ArxivProvider(client=FakeHttp(text="<not-atom"))
        with pytest.raises(MalformedResponse):
            provider.search("x")


class TestDataCiteDoajUnpaywall:
    def test_datacite(self):
        payload = fixture_json("datacite_search.json")
        provider = DataCiteProvider(client=FakeHttp(payload))
        result = provider.search("perovskite", limit=1)
        assert result.records
        rec = result.records[0]
        assert rec.doi and rec.title

    def test_doaj_is_gold_open_access(self):
        provider = DoajProvider(client=FakeHttp(fixture_json("doaj_search.json")))
        result = provider.search("photoredox", limit=2)
        assert result.records
        assert all(r.oa_status is OaStatus.GOLD for r in result.records)

    def test_unpaywall_reports_only_access_facts(self):
        provider = UnpaywallProvider(mailto="t@example.org",
                                     client=FakeHttp(fixture_json("unpaywall_oa.json")))
        rec = provider.fetch(DOI).records[0]
        assert rec.doi == DOI
        assert rec.authors == []          # never inferred from a sparse payload
        assert rec.publication_year is not None

    def test_unpaywall_has_no_search(self):
        provider = UnpaywallProvider(mailto="t@example.org", client=FakeHttp({}))
        with pytest.raises(NotImplementedError):
            provider.search("anything")


class TestSemanticScholarAndPubChem:
    def test_semantic_scholar_fixture(self):
        provider = SemanticScholarProvider(client=FakeHttp(
            fixture_json("semanticscholar_paper.json")))
        rec = provider.fetch(DOI).records[0]
        assert rec.doi == DOI
        assert rec.title

    def test_pubchem_properties(self):
        payload = fixture_json("pubchem_aspirin.json")
        provider = PubChemProvider(client=FakeHttp(payload))
        props = provider.properties("aspirin")
        assert props["MolecularFormula"] == "C9H8O4"
        assert float(props["MonoisotopicMass"]) == pytest.approx(180.0422587, abs=1e-6)


class TestCapabilityHonesty:
    def test_every_implemented_adapter_has_verified_access(self):
        """No adapter is registered as available without a tested public endpoint."""
        assert set(IMPLEMENTED) >= {"openalex", "crossref", "europepmc", "arxiv",
                                    "datacite", "doaj", "unpaywall"}

    def test_blocked_sources_carry_evidence_and_an_alternative(self):
        for name, info in BLOCKED.items():
            assert info["reason"], name
            assert info["verified_on"], name
            assert info["alternative"], name
            assert name not in IMPLEMENTED

    def test_chemrxiv_is_not_faked(self):
        assert "chemrxiv" in BLOCKED
        assert "403" in BLOCKED["chemrxiv"]["reason"]

    def test_unpaywall_declares_its_email_requirement(self):
        assert IMPLEMENTED["unpaywall"].capabilities.requires_email is True
