"""Synchronisation pipeline: discover -> normalise -> reconcile -> store.

Properties the brief demands, and where each one lives:

===================  =======================================================
incremental          ``since`` / ``from_year`` filters passed to providers
idempotent           :meth:`ResearchStore.upsert` keyed on ``work_id``
dry-run              ``dry_run=True`` performs every step except the writes
provider isolation   each provider is wrapped; one failure is recorded
rate limits          :class:`~paperforge.providers.base.HttpClient`
retries/backoff      idem
checkpoint recovery  ``sync_runs`` rows are written before and after
provenance           raw payload + provider + URL + timestamp per record
coverage honesty     :mod:`paperforge.research.coverage`
===================  =======================================================
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from ..providers.api import Provider, ProviderResult
from ..providers.base import ProviderError, RateLimited, utcnow
from ..providers.registry import DISCOVERY, Registry
from .dedup import Verdict, compare, merge
from .schema import WorkRecord
from .store import ResearchStore, UpsertResult


@dataclass
class ProviderOutcome:
    provider: str
    ok: bool
    records: int = 0
    total_available: int | None = None
    error: str | None = None
    error_type: str = ""
    retry_after: float | None = None
    duration_ms: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {"provider": self.provider, "ok": self.ok, "records": self.records,
                "total_available": self.total_available, "error": self.error,
                "error_type": self.error_type, "retry_after": self.retry_after,
                "duration_ms": self.duration_ms}


@dataclass
class SyncReport:
    query: str
    providers: list[ProviderOutcome] = field(default_factory=list)
    records_found: int = 0
    unique_records: int = 0
    merged_duplicates: int = 0
    upsert: UpsertResult = field(default_factory=UpsertResult)
    dry_run: bool = False
    started_at: str = ""
    finished_at: str = ""

    @property
    def ok(self) -> bool:
        return any(p.ok for p in self.providers)

    @property
    def failed_providers(self) -> list[str]:
        return [p.provider for p in self.providers if not p.ok]

    def as_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "dry_run": self.dry_run,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "providers": [p.as_dict() for p in self.providers],
            "records_found": self.records_found,
            "unique_records": self.unique_records,
            "merged_duplicates": self.merged_duplicates,
            "inserted": self.upsert.inserted,
            "updated": self.upsert.updated,
            "unchanged": self.upsert.unchanged,
            "failed_providers": self.failed_providers,
        }

    def summary_lines(self) -> list[str]:
        lines = [f"query: {self.query!r}   mode: {'dry-run' if self.dry_run else 'write'}"]
        for p in self.providers:
            if p.ok:
                lines.append(f"  OK   {p.provider:16s} {p.records:4d} record(s)"
                             f"  (index reports {p.total_available if p.total_available is not None else 'n/a'})"
                             f"  {p.duration_ms} ms")
            else:
                lines.append(f"  FAIL {p.provider:16s} {p.error_type}: {p.error}")
        lines.append(f"found {self.records_found}, unique {self.unique_records}, "
                     f"merged {self.merged_duplicates}, inserted {self.upsert.inserted}, "
                     f"updated {self.upsert.updated}, unchanged {self.upsert.unchanged}")
        if self.failed_providers:
            lines.append(f"note: {len(self.failed_providers)} provider(s) unavailable — "
                         "results are incomplete, not empty")
        return lines


def collect(registry: Registry, query: str, *, providers: Iterable[str] | None = None,
            limit: int = 25, from_year: int | None = None, **filters: Any) -> tuple[list[WorkRecord], list[ProviderOutcome]]:
    """Query each provider independently, never letting one failure propagate."""
    records: list[WorkRecord] = []
    outcomes: list[ProviderOutcome] = []
    for name in (providers or DISCOVERY):
        started = utcnow()
        try:
            provider: Provider = registry.build(name)
            ok, reason = provider.available()
            if not ok:
                outcomes.append(ProviderOutcome(name, False, error=reason, error_type="unavailable"))
                continue
            res: ProviderResult = provider.search(query, limit=limit,
                                                  from_year=from_year, **filters)
            for rec in res.records:
                records.append(rec)
            outcomes.append(ProviderOutcome(
                name, True, records=len(res.records), total_available=res.total_available,
                duration_ms=_ms_since(started)))
            if isinstance(res.records, list) and res.warnings:
                outcomes[-1].error = "; ".join(res.warnings)
        except RateLimited as exc:
            outcomes.append(ProviderOutcome(name, False, error=exc.message,
                                            error_type="rate_limited",
                                            retry_after=exc.retry_after,
                                            duration_ms=_ms_since(started)))
        except ProviderError as exc:
            outcomes.append(ProviderOutcome(name, False, error=exc.message,
                                            error_type=type(exc).__name__,
                                            duration_ms=_ms_since(started)))
        except Exception as exc:  # pragma: no cover - defensive, still isolated
            outcomes.append(ProviderOutcome(name, False, error=f"unexpected: {exc}",
                                            error_type=type(exc).__name__,
                                            duration_ms=_ms_since(started)))
    return records, outcomes


def _ms_since(stamp: str) -> int:
    from datetime import datetime
    try:
        started = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        return int((datetime.now(started.tzinfo) - started).total_seconds() * 1000)
    except ValueError:  # pragma: no cover
        return 0


def reconcile(records: list[WorkRecord], *, store: ResearchStore | None = None,
              dry_run: bool = False) -> tuple[list[WorkRecord], int]:
    """Collapse records that describe the same work; return (unique, merges)."""
    groups: list[list[WorkRecord]] = []
    for rec in records:
        placed = False
        for group in groups:
            decision = compare(group[0], rec)
            if decision.merge:
                group.append(rec)
                if store is not None and not dry_run:
                    store.record_merge(kept_id=group[0].ensure_id(),
                                       merged_id=rec.ensure_id(), decision=decision)
                placed = True
                break
            if decision.verdict is Verdict.RELATED_VERSION:
                # link, do not merge: keep both, record the relationship
                rec.version_of = rec.version_of or group[0].doi
                placed = False
        if not placed:
            groups.append([rec])

    unique: list[WorkRecord] = []
    merges = 0
    for group in groups:
        merged, _audit = merge(group)
        unique.append(merged)
        merges += len(group) - 1
    return unique, merges


def sync(registry: Registry, query: str, store: ResearchStore, *,
         providers: Iterable[str] | None = None, limit: int = 25,
         from_year: int | None = None, dry_run: bool = False,
         reconcile_first: bool = True, **filters: Any) -> SyncReport:
    """One full synchronisation step."""
    report = SyncReport(query=query, dry_run=dry_run, started_at=utcnow())
    provider_names = list(providers or DISCOVERY)
    run_ids: dict[str, int] = {}
    if not dry_run:
        for name in provider_names:
            run_ids[name] = store.start_sync(name, query)

    records, outcomes = collect(registry, query, providers=provider_names,
                                limit=limit, from_year=from_year, **filters)
    report.providers = outcomes
    report.records_found = len(records)

    for outcome in outcomes:
        if not dry_run:
            store.note_provider(outcome.provider, ok=outcome.ok, error=outcome.error,
                               retry_after=outcome.retry_after)

    if reconcile_first:
        unique, merges = reconcile(records, store=store, dry_run=dry_run)
    else:
        unique, merges = records, 0
    report.unique_records = len(unique)
    report.merged_duplicates = merges

    if not dry_run and unique:
        raw_by_work = {unique[i].ensure_id(): [] for i in range(len(unique))}
        report.upsert = store.upsert(unique, raw_by_work=raw_by_work)
    report.finished_at = utcnow()

    if not dry_run:
        by_provider: dict[str, ProviderOutcome] = {o.provider: o for o in outcomes}
        for name, run_id in run_ids.items():
            outcome = by_provider.get(name)
            store.finish_sync(
                run_id,
                status="ok" if outcome and outcome.ok else "failed",
                result=report.upsert if outcome and outcome.ok else UpsertResult(),
                errors=[outcome.error] if outcome and outcome.error else [],
                stats={"duration_ms": outcome.duration_ms if outcome else None,
                       "total_available": outcome.total_available if outcome else None},
                requested=outcome.records if outcome else 0,
            )
    return report
