"""Europe PMC adapter.

Europe PMC indexes PubMed/MEDLINE plus preprint servers (arXiv, bioRxiv,
ChemRxiv, medRxiv) in one query interface, with open citation counts and
open-access full-text links. For chemistry-adjacent life science it is the
best free complement to Crossref.

Access (verified 2026-11-18): no key, no e-mail required; JSON via
``format=json``; ``resultType=core`` returns the abstract and author list.
"""
from __future__ import annotations

from typing import Any

from ..research.schema import (Author, OaStatus, PeerReview, RetractionStatus,
                               VersionType, WorkRecord, normalise_doi, normalise_orcid)
from .api import Capabilities, Provider, ProviderResult

BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"


class EuropePmcProvider(Provider):
    name = "europepmc"
    base_url = BASE
    license = "Europe PMC terms (mixed; per-record licence reported)"
    docs_url = "https://europepmc.org/RestfulWebService"
    default_interval = 0.05
    capabilities = Capabilities(
        search=True, fetch_by_doi=True, fulltext_links=True, citation_counts=True,
        references=False, retraction_signal=True, oa_status=True, institutional_ids=False,
        rate_limit_note="no key required; be polite (<= 10 req/s)",
    )

    def search(self, query: str, limit: int = 25, **filters: Any) -> ProviderResult:
        q = query
        if filters.get("from_year"):
            q += f" AND (FIRST_PDATE:[{filters['from_year']}-01-01 TO 2100-12-31])"
        params = {"query": q, "format": "json", "resultType": "core",
                  "pageSize": max(1, min(int(limit), 100)), "email": self.mailto}
        resp = self.http.get_json(f"{BASE}/search", params)
        payload = resp.payload or {}
        items = ((payload.get("resultList") or {}).get("result")) or []
        records = [self.normalise(i, retrieved_at=resp.retrieved_at, url=resp.url) for i in items]
        return self._finish(records, items, resp, total=payload.get("hitCount"))

    def fetch(self, identifier: str) -> ProviderResult:
        doi = normalise_doi(identifier)
        ident = f'DOI:"{doi}"' if doi else f'EXT_ID:"{identifier}"'
        params = {"query": ident, "format": "json", "resultType": "core", "pageSize": 1}
        resp = self.http.get_json(f"{BASE}/search", params)
        items = (((resp.payload or {}).get("resultList") or {}).get("result")) or []
        records = [self.normalise(i, retrieved_at=resp.retrieved_at, url=resp.url) for i in items]
        return self._finish(records, items, resp, total=len(items))

    def normalise(self, raw: dict[str, Any], *, retrieved_at: str = "",
                  url: str = "") -> WorkRecord:
        authors: list[Author] = []
        for a in ((raw.get("authorList") or {}).get("author")) or []:
            name = a.get("fullName") or " ".join(filter(None, [a.get("firstName"), a.get("lastName")]))
            if not name:
                continue
            affs = [a.get("affiliation")] if a.get("affiliation") else []
            authors.append(Author(name=name,
                                  orcid=normalise_orcid(a.get("authorId", {}).get("value")
                                                        if isinstance(a.get("authorId"), dict) else None),
                                  given=a.get("firstName") or None,
                                  family=a.get("lastName") or None,
                                  affiliations=[x for x in affs if x]))

        doi = normalise_doi(raw.get("doi"))
        is_oa = raw.get("isOpenAccess")
        oa = OaStatus.UNKNOWN
        if str(is_oa).upper() == "Y":
            oa = OaStatus.GREEN if not raw.get("isGoldOA") else OaStatus.GOLD

        # Europe PMC's XML->JSON conversion collapses single-element lists to a
        # bare value, so pubType is sometimes a dict and sometimes a string.
        raw_types = (raw.get("pubTypeList") or {}).get("pubType") or []
        if isinstance(raw_types, (str, dict)):
            raw_types = [raw_types]
        types = [(t.get("name", "") if isinstance(t, dict) else str(t)) for t in raw_types]
        types = [t for t in types if t]
        lowered = " ".join(types).lower()
        peer, version = PeerReview.UNKNOWN, VersionType.UNKNOWN
        if "preprint" in lowered:
            peer, version = PeerReview.PREPRINT, VersionType.PREPRINT
        elif types:
            peer, version = PeerReview.PEER_REVIEWED, VersionType.VERSION_OF_RECORD

        # Europe PMC marks retractions in ``commentCorrectionList``.
        retraction = RetractionStatus.NONE_KNOWN
        for cc in ((raw.get("commentCorrectionList") or {}).get("commentCorrection")) or []:
            kind = (cc.get("type") or "").lower()
            if "retract" in kind:
                retraction = RetractionStatus.RETRACTED
                break
            if "erratum" in kind or "correction" in kind:
                retraction = RetractionStatus.CORRECTION

        journal = ((raw.get("journalInfo") or {}).get("journal") or {})
        cited = raw.get("citedByCount")
        rec = WorkRecord(
            doi=doi or None,
            provider_ids={k: v for k, v in {
                "europepmc": raw.get("id"),
                "pmid": raw.get("pmid"),
                "pmcid": raw.get("pmcid"),
            }.items() if v},
            title=self._clean(raw.get("title")),
            abstract=self._clean(raw.get("abstractText")),
            authors=authors,
            publication_year=self._year(raw.get("pubYear")),
            publication_date=raw.get("firstPublicationDate") or None,
            venue=self._clean(journal.get("title") or raw.get("journalTitle")),
            publisher=None,
            issn=[i for i in [journal.get("issn"), journal.get("essn")] if i],
            keywords=[],
            article_type=(types[0].lower() if types else None),
            peer_review=peer,
            version_type=version,
            oa_status=oa,
            license=raw.get("license") or None,
            fulltext_url=(f"https://europepmc.org/article/{raw.get('source', 'MED')}/{raw.get('id')}"
                          if raw.get("inEPMC") == "Y" or raw.get("isOpenAccess") == "Y" else None),
            citation_count=cited if isinstance(cited, int) else None,
            citation_count_source=self.name if isinstance(cited, int) else None,
            citation_count_date=retrieved_at[:10] or None,
            retraction_status=retraction,
            retrieved_at=retrieved_at or None,
            source_url=url or None,
        )
        rec.sources.append(self._provenance(url or f"{BASE}/search?query=DOI:{doi}", retrieved_at, raw))
        rec.ensure_id()
        return rec
