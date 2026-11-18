"""Coverage reporting — the antidote to "we index every paper ever published".

Every number here is measured from the store or from the provider registry. If
a metric cannot be measured, it is reported as ``None`` with a reason, never
estimated. The report always carries the list of sources that failed, because
a partial synchronisation is the normal case, not an error case.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..institutions import iiserb
from ..providers.registry import BLOCKED, Registry
from .schema import WorkRecord
from .store import ResearchStore


@dataclass
class CoverageReport:
    store_path: str
    works: int
    with_doi: int
    with_abstract: int
    with_orcid: int
    cross_checked: int
    conflicting: int
    retracted: int
    venues: int
    publishers: int
    countries: int
    institutions: int
    year_min: int | None
    year_max: int | None
    by_provider: list[dict[str, Any]]
    provider_state: list[dict[str, Any]]
    blocked_sources: dict[str, dict[str, str]]
    merged_away: int
    last_sync: str | None
    institutional: dict[str, Any]
    gaps: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "store": self.store_path,
            "records": {
                "works": self.works, "with_doi": self.with_doi,
                "with_abstract": self.with_abstract, "with_orcid": self.with_orcid,
                "venue_count": self.venues, "publisher_count": self.publishers,
                "country_count": self.countries, "institution_count": self.institutions,
                "year_range": [self.year_min, self.year_max],
            },
            "verification": {"cross_checked": self.cross_checked, "conflicting": self.conflicting},
            "integrity": {"retracted": self.retracted},
            "deduplication": {"records_merged": self.merged_away},
            "sources": self.by_provider,
            "provider_state": self.provider_state,
            "known_unavailable": self.blocked_sources,
            "last_successful_sync": self.last_sync,
            "institutional": self.institutional,
            "known_gaps": self.gaps,
        }

    def text(self) -> str:
        lines = [
            "Research coverage",
            "=================",
            f"store                 : {self.store_path}",
            f"records               : {self.works}",
            f"  with DOI            : {self.with_doi}",
            f"  with abstract       : {self.with_abstract}",
            f"  authors with ORCID  : {self.with_orcid}",
            f"  cross-checked       : {self.cross_checked}",
            f"  conflicting         : {self.conflicting}",
            f"  retracted           : {self.retracted}",
            f"venues / publishers   : {self.venues} / {self.publishers}",
            f"countries/institutions: {self.countries} / {self.institutions}",
            f"year range            : {self.year_min}–{self.year_max}",
            f"records merged away   : {self.merged_away}",
            f"last successful sync  : {self.last_sync or 'never'}",
            "",
            "sources queried (provenance rows):",
        ]
        if not self.by_provider:
            lines.append("  (none yet — run `paperforge research sync <query>`)")
        for row in self.by_provider:
            lines.append(f"  {row['provider']:16s} {row['records']:6d}  last {row['last'] or 'n/a'}")
        if self.provider_state:
            lines.append("")
            lines.append("provider health:")
            for row in self.provider_state:
                state = "OK" if not row.get("last_error") else f"FAIL ({row['last_error'][:60]})"
                lines.append(f"  {row['provider']:16s} failures={row['consecutive_failures']} {state}")
        lines.append("")
        lines.append("known unavailable sources (not integrated):")
        for name, info in self.blocked_sources.items():
            lines.append(f"  {name:18s} {info['reason'][:88]}")
        lines.append("")
        lines.append("institutional collection:")
        for key, value in self.institutional.items():
            lines.append(f"  {key:22s} {value}")
        if self.gaps:
            lines.append("")
            lines.append("known gaps:")
            for gap in self.gaps:
                lines.append(f"  - {gap}")
        return "\n".join(lines)


def build_coverage(store: ResearchStore, registry: Registry | None = None) -> CoverageReport:
    stats = store.stats()
    works = store.all_works()
    with_orcid = sum(1 for w in works if any(a.orcid for a in w.authors))
    with_abstract = sum(1 for w in works if w.abstract)
    countries = {inst.get("country") for w in works for a in w.authors
                 for inst in a.institutions if inst.get("country")}
    institutions = {inst.get("ror") or inst.get("name") for w in works for a in w.authors
                    for inst in a.institutions if inst.get("ror") or inst.get("name")}
    publishers = {w.publisher for w in works if w.publisher}

    inst_stats = iiserb.stats()
    gaps = [
        "Citation counts are point-in-time values from the provider that reported them; "
        "they are not normalised across sources.",
        "Retraction status reflects the sources queried. 'none_known' is absence of a "
        "notice in those sources, not evidence of integrity.",
        "Full text is never downloaded for closed-access works; only metadata is stored.",
    ]
    if stats["works"] == 0:
        gaps.append("The research store is empty; only the bundled institutional snapshot is available.")
    failing = [s for s in stats.get("provider_state", []) if s.get("last_error")]
    if failing:
        gaps.append("Providers with a recorded failure: "
                    + ", ".join(s["provider"] for s in failing)
                    + " — results gathered during those failures are incomplete.")

    return CoverageReport(
        store_path=stats["path"],
        works=stats["works"],
        with_doi=stats["with_doi"],
        with_abstract=with_abstract,
        with_orcid=with_orcid,
        cross_checked=stats["cross_checked"],
        conflicting=stats["conflicting"],
        retracted=stats["retracted"],
        venues=stats["venues"],
        publishers=len(publishers),
        countries=len(countries),
        institutions=len(institutions),
        year_min=stats["year_min"],
        year_max=stats["year_max"],
        by_provider=[{"provider": p["provider"], "records": p["n"], "last": p["last"]}
                     for p in stats["providers"]],
        provider_state=stats["provider_state"],
        blocked_sources=BLOCKED if registry is None else registry.blocked(),
        merged_away=stats["merged_away"],
        last_sync=stats["last_sync"],
        institutional={
            "name": iiserb.INSTITUTION["short"],
            "works": inst_stats.works,
            "faculty": inst_stats.faculty,
            "venues": inst_stats.venues,
            "years": f"{inst_stats.first_year}–{inst_stats.last_year}",
            "source": iiserb.INSTITUTION["snapshot_source"],
            "note": iiserb.coverage_note(),
        },
        gaps=gaps,
    )


def export_records(store: ResearchStore, path: str, *, fmt: str = "json") -> int:
    """Write a clean, self-describing dataset export. Returns the record count."""
    import csv
    import json
    from pathlib import Path

    works = store.all_works()
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = [w.as_dict() for w in works]
    if fmt == "json":
        payload = {
            "schema": "paperforge.dataset/1",
            "generated_at": __import__("paperforge.providers.base", fromlist=["utcnow"]).utcnow(),
            "count": len(rows),
            "records": rows,
        }
        out.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    elif fmt == "csv":
        cols = ["work_id", "doi", "title", "publication_year", "venue", "publisher",
                "article_type", "oa_status", "license", "citation_count",
                "retraction_status", "verification", "completeness"]
        with out.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
    else:
        raise ValueError(f"unknown export format {fmt!r} (use json or csv)")
    return len(rows)
