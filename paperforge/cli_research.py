"""`paperforge research ...` and `paperforge institution ...` commands.

Exit-code contract (consistent with the rest of the CLI):

* ``0`` — the requested operation completed and every provider answered;
* ``1`` — the operation completed but at least one source was unavailable
  (results are *incomplete*, not empty — the message says which);
* ``2`` — bad input (unknown provider, missing store, malformed query).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .institutions import iiserb
from .providers.base import ProviderError
from .providers.registry import BLOCKED, DISCOVERY, IMPLEMENTED, Registry
from .research.coverage import build_coverage, export_records
from .research.pipeline import sync
from .research.store import ResearchStore

DEFAULT_DB = "research.sqlite3"


def _registry() -> Registry:
    return Registry(app_version=__version__)


def _store(path: str) -> ResearchStore:
    return ResearchStore(Path(path))


def _emit(data: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# research providers
# ---------------------------------------------------------------------------

def cmd_research_providers(args) -> int:
    registry = _registry()
    rows = registry.status()
    payload = {
        "providers": [r.as_dict() for r in rows],
        "known_unavailable": registry.blocked(),
        "discovery_order": list(DISCOVERY),
    }
    if args.json:
        _emit(payload, True)
        return 0
    print(f"{len(rows)} provider adapter(s) implemented\n")
    print(f"{'source':18s} {'ready':6s} {'search':7s} {'doi':5s} {'OA':3s} {'cited':6s} note")
    for r in rows:
        caps = r.capabilities
        print(f"{r.name:18s} {'yes' if r.available else 'NO':6s} "
              f"{'yes' if caps['search'] else '-':7s} {'yes' if caps['fetch_by_doi'] else '-':5s} "
              f"{'yes' if caps['oa_status'] else '-':3s} {'yes' if caps['citation_counts'] else '-':6s} "
              f"{r.reason[:44]}")
    print("\nknown unavailable (documented, not faked):")
    for name, info in BLOCKED.items():
        print(f"  {name:18s} {info['reason'][:96]}")
        print(f"  {'':18s} alternative: {info['alternative']}")
    if not args.all_ok:
        # Not every provider needs to be ready; this is informational.
        missing = [r.name for r in rows if not r.available]
        if missing:
            print(f"\nnote: not configured: {', '.join(missing)} "
                  f"(set PF_MAILTO or the provider's API key)")
    return 0


# ---------------------------------------------------------------------------
# research search
# ---------------------------------------------------------------------------

def cmd_research_search(args) -> int:
    registry = _registry()
    sources = args.source or [s for s in DISCOVERY if _has_search(registry, s)]
    unknown = [s for s in sources if s.lower() not in IMPLEMENTED]
    if unknown:
        print(f"error: unknown provider(s): {', '.join(unknown)}", file=sys.stderr)
        return 2

    from .research.pipeline import collect
    records, outcomes = collect(registry, args.query, providers=sources,
                                limit=args.limit, from_year=args.from_year)
    if args.json:
        _emit({"query": args.query,
               "providers": [o.as_dict() for o in outcomes],
               "records": [r.as_dict() for r in records]}, True)
        return 0 if all(o.ok for o in outcomes) else 1

    if not records and all(not o.ok for o in outcomes):
        print("no results: every provider failed\n", file=sys.stderr)
        for o in outcomes:
            print(f"  {o.provider:16s} {o.error_type}: {o.error}", file=sys.stderr)
        return 1

    for rec in records:
        year = rec.publication_year or "----"
        venue = (rec.venue or "")[:44]
        print(f"{year}  {rec.title or '(untitled)'}"[:140])
        print(f"      {venue:46s} {rec.doi or '(no DOI)':32s} [{_sources(rec)}]")
    print(f"\n{len(records)} record(s) from {sum(1 for o in outcomes if o.ok)}/{len(outcomes)} providers")
    failed = [o for o in outcomes if not o.ok]
    for o in failed:
        print(f"  unavailable: {o.provider} ({o.error_type}: {str(o.error)[:70]})")
    return 0 if not failed else 1


def _has_search(registry: Registry, name: str) -> bool:
    try:
        return registry.build(name).capabilities.search
    except ProviderError:
        return False


def _sources(rec) -> str:
    names = []
    for prov in rec.sources:
        if prov.provider not in names:
            names.append(prov.provider)
    return "+".join(names) or "?"


# ---------------------------------------------------------------------------
# research fetch
# ---------------------------------------------------------------------------

def cmd_research_fetch(args) -> int:
    registry = _registry()
    hits, errors = [], []
    for name in (args.source or ["crossref", "openalex", "europepmc", "datacite"]):
        try:
            res = registry.build(name).fetch(args.identifier)
            hits.extend(res.records)
        except ProviderError as exc:
            errors.append(f"{name}: {exc}")
    if not hits:
        print(f"error: no provider could resolve {args.identifier!r}", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 1
    from .research.dedup import merge
    merged, audit = merge(hits)
    if args.json:
        _emit({"record": merged.as_dict(), "audit": audit,
               "errors": errors}, True)
        return 0
    d = merged.as_dict()
    for key in ("work_id", "doi", "title", "publication_year", "venue", "publisher",
                "article_type", "oa_status", "license", "citation_count",
                "retraction_status", "verification", "completeness"):
        print(f"{key:20s} {d.get(key)}")
    print(f"{'authors':20s} {', '.join(a['name'] for a in d['authors'][:6])}"
          + (" …" if len(d["authors"]) > 6 else ""))
    print(f"{'sources':20s} {audit['sources']}")
    if audit["conflicts"]:
        print(f"{'conflicts':20s} {audit['conflicts']}")
    if errors:
        print(f"\nnote: {len(errors)} provider(s) failed: " + "; ".join(errors), file=sys.stderr)
    return 0


# ---------------------------------------------------------------------------
# research sync / coverage / export / dedup
# ---------------------------------------------------------------------------

def cmd_research_sync(args) -> int:
    registry = _registry()
    store = _store(args.db)
    try:
        report = sync(registry, args.query, store, providers=args.source,
                      limit=args.limit, from_year=args.from_year,
                      dry_run=args.dry_run)
    finally:
        store.close()
    if args.json:
        _emit(report.as_dict(), True)
    else:
        for line in report.summary_lines():
            print(line)
    if not report.ok:
        return 1
    return 0 if not report.failed_providers else 1


def cmd_research_coverage(args) -> int:
    if not Path(args.db).exists():
        print(f"error: no research store at {args.db} "
              f"(run `paperforge research sync \"<query>\"`)", file=sys.stderr)
        return 2
    store = _store(args.db)
    try:
        report = build_coverage(store, _registry())
    finally:
        store.close()
    if args.json:
        _emit(report.as_dict(), True)
    else:
        print(report.text())
    return 0


def cmd_research_export(args) -> int:
    if not Path(args.db).exists():
        print(f"error: no research store at {args.db}", file=sys.stderr)
        return 2
    store = _store(args.db)
    try:
        n = export_records(store, args.out, fmt=args.format)
        cov = build_coverage(store)
    finally:
        store.close()
    sidecar = Path(args.out).with_suffix(Path(args.out).suffix + ".meta.json")
    sidecar.write_text(json.dumps({
        "generated_from": str(Path(args.db).resolve()),
        "records": n,
        "coverage": cov.as_dict(),
    }, indent=2), encoding="utf-8")
    print(f"wrote {n} record(s) to {args.out} (+ coverage sidecar {sidecar.name})")
    return 0


def cmd_research_dedup(args) -> int:
    if not Path(args.db).exists():
        print(f"error: no research store at {args.db}", file=sys.stderr)
        return 2
    from .research.dedup import compare
    store = _store(args.db)
    try:
        works = store.all_works()
        proposals = []
        for i in range(len(works)):
            for j in range(i + 1, len(works)):
                decision = compare(works[i], works[j])
                if decision.verdict.value != "distinct" and decision.score >= args.threshold:
                    proposals.append({"a": works[i].work_id, "b": works[j].work_id,
                                      "a_title": works[i].title, "b_title": works[j].title,
                                      **decision.as_dict()})
    finally:
        store.close()
    if args.json:
        _emit({"proposals": proposals}, True)
        return 0
    if not proposals:
        print(f"no duplicate proposals above {args.threshold} in {len(works)} record(s)")
        return 0
    for p in proposals:
        print(f"[{p['verdict']}] {p['score']:.2f}  {p['a_title'][:60]!r}")
        print(f"{'':10s}{p['b_title'][:60]!r}")
        print(f"{'':10s}{p['explanation']}")
    print(f"\n{len(proposals)} proposal(s) — a merge is applied only by `research sync`")
    return 0


# ---------------------------------------------------------------------------
# institution (preserved IISER Bhopal collection)
# ---------------------------------------------------------------------------

def cmd_institution(args) -> int:
    if args.action == "stats":
        s = iiserb.stats()
        data = {**s.as_dict(), "institution": iiserb.INSTITUTION,
                "coverage_note": iiserb.coverage_note()}
        if args.json:
            _emit(data, True)
            return 0
        print(f"{iiserb.INSTITUTION['name']} — {iiserb.INSTITUTION['department']}")
        print(f"  ROR                 {iiserb.INSTITUTION['ror']}")
        print(f"  works               {s.works}")
        print(f"  faculty identified  {s.faculty}")
        print(f"  distinct venues     {s.venues}")
        print(f"  year range          {s.first_year}–{s.last_year}")
        print(f"  preprints           {s.preprints}")
        oa = "not captured in snapshot" if s.open_access is None else s.open_access
        print(f"  open access         {oa}")
        print(f"  records without DOI {s.missing_doi}")
        print(f"  snapshot            {iiserb.INSTITUTION['snapshot']} "
              f"({iiserb.INSTITUTION['snapshot_source']})")
        print(f"\n  note: {iiserb.coverage_note()}")
        return 0

    if args.action == "search":
        hits = iiserb.search(args.query, limit=args.limit)
        if args.json:
            _emit({"query": args.query, "records": hits}, True)
            return 0
        for w in hits:
            print(f"{w.get('year', '----')}  {(w.get('title') or '')[:100]}")
            print(f"      {(w.get('journal') or '')[:50]:52s} {w.get('doi') or ''}")
        print(f"\n{len(hits)} record(s) from the bundled institutional snapshot")
        return 0

    if args.action == "faculty":
        hits = iiserb.by_faculty(args.query, limit=args.limit)
        if args.json:
            _emit({"faculty": args.query, "records": hits}, True)
            return 0
        for w in hits:
            print(f"{w.get('year', '----')}  {(w.get('title') or '')[:100]}")
        print(f"\n{len(hits)} record(s) for {args.query}")
        return 0

    if args.action == "journals":
        if args.json:
            _emit({"journals": iiserb.journal_counts()[:args.limit]}, True)
            return 0
        for name, n in iiserb.journal_counts()[:args.limit]:
            print(f"{n:4d}  {name}")
        return 0
    return 2


# ---------------------------------------------------------------------------
# argument wiring
# ---------------------------------------------------------------------------

def add_parsers(sub) -> None:
    research = sub.add_parser("research", help="global research intelligence (providers, sync, coverage)")
    rsub = research.add_subparsers(dest="research_cmd", required=True)

    p = rsub.add_parser("providers", help="list adapters, capabilities and known-unavailable sources")
    p.add_argument("--json", action="store_true")
    p.add_argument("--all-ok", action="store_true", help=argparse_suppress())
    p.set_defaults(func=cmd_research_providers)

    p = rsub.add_parser("search", help="search every configured source at once")
    p.add_argument("query")
    p.add_argument("--source", action="append", help="restrict to a provider (repeatable)")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--from-year", type=int, default=None)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_research_search)

    p = rsub.add_parser("fetch", help="resolve one DOI across providers and reconcile")
    p.add_argument("identifier", help="DOI, arXiv id or PMID")
    p.add_argument("--source", action="append")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_research_fetch)

    p = rsub.add_parser("sync", help="synchronise a query into the local research store")
    p.add_argument("query")
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--source", action="append")
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--from-year", type=int, default=None)
    p.add_argument("--dry-run", action="store_true", help="do everything except write")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_research_sync)

    p = rsub.add_parser("coverage", help="transparent coverage report")
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_research_coverage)

    p = rsub.add_parser("export", help="export a clean dataset + coverage sidecar")
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--out", required=True)
    p.add_argument("--format", choices=["json", "csv"], default="json")
    p.set_defaults(func=cmd_research_export)

    p = rsub.add_parser("dedup", help="show duplicate proposals without merging")
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--threshold", type=float, default=0.8)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_research_dedup)

    inst = sub.add_parser("institution", help="the preserved IISER Bhopal institutional collection")
    isub = inst.add_subparsers(dest="action", required=True)
    p = isub.add_parser("stats", help="collection statistics (offline snapshot)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_institution, query=None, limit=25)
    p = isub.add_parser("search", help="search the institutional snapshot")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_institution)
    p = isub.add_parser("faculty", help="works by one faculty member")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_institution)
    p = isub.add_parser("journals", help="venues ranked by captured output")
    p.add_argument("--limit", type=int, default=15)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_institution, query=None)


def argparse_suppress() -> str:
    """Placeholder help string (kept separate so the import stays dependency-free)."""
    return "accepted for symmetry; readiness is always reported"
