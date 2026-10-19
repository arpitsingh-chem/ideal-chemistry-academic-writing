"""Command-line interface: `paperforge <command>`."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .checks import CATEGORIES, WEIGHTS, check_file, check_project, score
from .draft import compose, cover_letter, highlights
from .figures import inventory, make_toc, toc_dimensions
from .journals import Matcher, journal_names, profile, resolve, retarget, search
from .project import Project, ProjectError, scaffold
from .refs import add_dois, check_bib_file, verify_project
from .render import to_docx, to_latex, to_markdown, to_plain, to_docx as _to_docx
from .util import write_text

ICON = {"error": "✗", "warn": "!", "info": "·"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class CliError(RuntimeError):
    """Raised for user-facing command errors (no traceback)."""


def _load(path: str, journal: str | None = None, article_type: str | None = None) -> Project:
    try:
        p = Project.load(path)
    except ProjectError as exc:
        raise CliError(str(exc)) from exc
    if journal:
        p.paper["journal"] = journal
    if article_type:
        p.paper["article_type"] = article_type
    return p


def _print_report(rep, verbose: bool = False) -> None:
    counts = rep.counts()
    print(f"=== {rep.source or 'manuscript'} — {rep.profile.journal} ({rep.profile.article_type}) ===")
    print(f"{counts['error']} errors · {counts['warn']} warnings · {counts['info']} notes\n")
    for cat in CATEGORIES:
        issues = rep.by(category=cat)
        if not issues and not verbose:
            continue
        print(f"[{cat.upper()}]")
        for i in issues:
            print(f"  {ICON[i.severity]} {i.code:<28} {i.message}")
            if i.hint and (verbose or i.severity == "error"):
                print(f"      → {i.hint}")
        print()


def _print_score(sc: dict) -> None:
    print(f"\nREADINESS  {sc['score']}/100   grade {sc['grade']}   ({sc['status']})")
    if sc.get("capped_by_blockers"):
        print("  score capped at 55 because of blocking issues")
    print()
    for cat, val in sc["categories"].items():
        bar = "█" * int(val / 5) + "░" * (20 - int(val / 5))
        print(f"  {cat:<11} {bar} {val:5.1f}  (weight {WEIGHTS[cat]}%)")
    if sc["blockers"]:
        print("\n  BLOCKERS")
        for b in sc["blockers"]:
            print(f"    ✗ {b['message']}")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_new(args) -> int:
    path = scaffold(args.path, title=args.title or "", journal=args.journal or "Organic Letters")
    print(f"created {path}")
    print("next: edit paper.yaml, then `paperforge draft .`")
    return 0


def cmd_journals(args) -> int:
    if args.action == "list":
        rows = journal_names()
        print(f"{len(rows)} journals in the database")
        for n in rows[: args.top]:
            p = profile(n)
            print(f"  {n:<55} {p.family:<12} abs≤{p.limits.abstract_max:<4}")
        return 0
    if args.action == "search":
        rows = search(args.query, top=args.top)
        for r in rows:
            print(f"  {r['journal']:<55} {r['family']:<12} {r['papers']:>4} papers")
        if not rows:
            print("no match")
        return 0
    if args.action == "match":
        m = Matcher()
        text = " ".join(args.query) if isinstance(args.query, list) else args.query
        rows = m.recommend(text, top=args.top, family=args.family)
        print(f"Query: {text}\n")
        print(f"{'score':>6}  {'journal':<48}{'papers':>7}  scope match")
        print("-" * 100)
        for r in rows:
            print(f"{r['score']:>6.1f}  {r['journal'][:46]:<48}{r['papers']:>7}  {', '.join(r['matched_terms'][:4])}")
        print("\nScores blend topical similarity (TF-IDF over the department's 1,616 papers) with venue frequency.")
        print("Always confirm scope + current limits on the journal page.")
        return 0
    if args.action == "show":
        p = profile(args.query if isinstance(args.query, str) else args.query[0], args.article_type)
        print(json.dumps(p.as_dict(), indent=2, ensure_ascii=False))
        return 0
    return 1


def cmd_refs(args) -> int:
    if args.action == "add":
        project = _load(args.path)
        added = add_dois(project.root, args.dois, mailto=args.mailto)
        for a in added:
            print(f"  {a.get('status','?'):<10} {a.get('doi')}  {a.get('title','')[:60]}")
        print("\nAdd the verified entries to the `references:` block in paper.yaml.")
        return 0
    if args.action == "verify":
        project = _load(args.path)
        rep = verify_project(project, offline=args.offline, mailto=args.mailto)
        print(rep.summary())
        for e in rep.entries:
            mark = {"verified": "✓", "not_found": "✗", "network_error": "?", "unverified": "?"}[e["status"]]
            print(f"  {mark} {e['key']:<28} {e['doi']:<35} {e['title'][:50]}")
        if rep.errors:
            print("\nissues:")
            for err in rep.errors[:30]:
                print(f"  - {err}")
        return 0 if rep.ok else 1
    if args.action == "check":
        res = check_bib_file(args.path)
        print(json.dumps(res, indent=2))
        return 0
    return 1


def cmd_figures(args) -> int:
    if args.action == "inventory":
        project = _load(args.path)
        prof = profile(project.journal, project.article_type)
        for row in inventory(project, prof):
            print(f"  {row['id']:<10} {row['file']:<35} {row['px']:<12} {row['dpi'] or '-':<6} "
                  f"{'vector' if row['vector'] else row['format']}")
        return 0
    if args.action == "toc":
        prof = profile(args.journal, args.article_type) if args.journal else None
        if prof and prof.toc_width_cm:
            w, h = prof.toc_width_cm, prof.toc_height_cm
            dpi = prof.toc_dpi
        else:
            w, h, dpi = 8.25, 4.45, 300
        out = make_toc(args.source, args.out, w, h, dpi)
        px = toc_dimensions(prof) if prof else (0, 0)
        print(f"wrote {out} at {w}×{h} cm, {dpi} dpi" + (f" ({px[0]}×{px[1]} px)" if px[0] else ""))
        return 0
    return 1


def cmd_draft(args) -> int:
    project = _load(args.path, args.journal, args.article_type)
    doc = compose(project)
    out = Path(args.out or project.root / "build")
    out.mkdir(parents=True, exist_ok=True)
    formats = args.format if isinstance(args.format, list) else [args.format]
    written = []
    if "all" in formats or "md" in formats:
        written.append(write_text(out / "manuscript.md", to_markdown(doc)))
    if "all" in formats or "tex" in formats:
        written.append(write_text(out / "manuscript.tex", to_latex(doc, project)))
        written.append(write_text(out / "si.tex", to_latex(doc, project, si=True)))
    if "all" in formats or "docx" in formats:
        try:
            written.append(to_docx(doc, out / "manuscript.docx", project))
        except Exception as exc:
            print(f"warning: could not write .docx ({exc})")
    if "txt" in formats:
        written.append(write_text(out / "manuscript.txt", to_plain(doc)))
    if args.cover_letter:
        written.append(write_text(out / "cover_letter.md", cover_letter(project, doc)))
    if args.highlights:
        items = highlights(project, doc)
        if items:
            written.append(write_text(out / "highlights.md", "# Highlights\n\n" +
                                      "\n".join(f"- {h}" for h in items) + "\n"))
        else:
            print("note: paper.yaml has no `highlights:` entries — skipping highlights.md")
    # Copy build inputs so the generated .tex compiles in place (figures + bib).
    import shutil
    fig_dir = project.root / "figures"
    if fig_dir.exists() and out.resolve() != fig_dir.resolve():
        (out / "figures").mkdir(parents=True, exist_ok=True)
        for src in fig_dir.iterdir():
            if src.is_file() and src.suffix.lower() in {".png", ".jpg", ".jpeg", ".pdf", ".eps", ".tif", ".tiff"}:
                dest = out / "figures" / src.name
                if not dest.exists() or src.stat().st_mtime > dest.stat().st_mtime:
                    shutil.copy2(src, dest)
    for bib in (project.root / "refs").glob("*.bib") if (project.root / "refs").exists() else []:
        dest = out / "refs" / bib.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists() or bib.stat().st_mtime > dest.stat().st_mtime:
            shutil.copy2(bib, dest)
    for w in written:
        print(f"wrote {w}")
    if doc.meta.get("generated_sections"):
        print(f"\ngenerated sections (verify before submitting): {doc.meta['generated_sections']}")
    return 0


def cmd_ingest(args) -> int:
    from .ingest import ingest

    try:
        report = ingest(args.source, args.out or args.source,
                        title=args.title, journal=args.journal,
                        article_type=args.article_type)
    except FileNotFoundError as exc:
        raise CliError(str(exc)) from exc
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    print(f"ingested {report['files_scanned']} files → {report['project']}")
    print(f"  compounds {report['compounds']} · datasets {report['datasets']} · "
          f"tables {report['tables']} · figures {report['figures']} · "
          f"references {report['references']}")
    for w in report["warnings"]:
        print(f"  note: {w}")
    print(f"\nnext: edit {Path(report['project']) / 'paper.yaml'} "
          f"(see INGEST.md), then `paperforge check .`")
    return 0


def cmd_context(args) -> int:
    """Print the grounded evidence pack (safe to paste into any LLM)."""
    from .llm import evidence_pack

    project = _load(args.path)
    pack = evidence_pack(project)
    if args.compact:
        print(json.dumps({k: pack[k] for k in ("title", "journal", "article_type",
                                               "citation_keys", "numbers_present_in_data")},
                         indent=2, ensure_ascii=False))
    else:
        print(json.dumps(pack, indent=2, ensure_ascii=False))
    return 0


def cmd_check(args) -> int:
    if args.file:
        rep = check_file(args.file, journal=args.journal or "Organic Letters",
                         article_type=args.article_type or "article", offline=True)
    else:
        project = _load(args.path)
        ref_report = None
        if args.verify_refs:
            ref_report = verify_project(project, offline=args.offline)
        rep = check_project(project, args.journal, args.article_type,
                            ref_report=ref_report, offline=not args.verify_refs)
    if args.json:
        print(json.dumps({"issues": [i.as_dict() for i in rep.issues],
                          "metrics": rep.metrics, "score": score(rep)}, indent=2, ensure_ascii=False))
    else:
        _print_report(rep, verbose=args.verbose)
        _print_score(score(rep))
    return 1 if rep.errors else 0


def cmd_score(args) -> int:
    project = _load(args.path, args.journal, args.article_type)
    ref_report = verify_project(project, offline=args.offline) if args.verify_refs else None
    rep = check_project(project, args.journal, args.article_type, ref_report=ref_report,
                        offline=not args.verify_refs)
    sc = score(rep)
    if args.json:
        print(json.dumps(sc, indent=2, ensure_ascii=False))
    else:
        _print_score(sc)
    return 0 if sc["score"] >= args.min else 1


def cmd_si(args) -> int:
    project = _load(args.path)
    doc = compose(project)
    out = write_text(Path(args.out or project.root / "si" / "si.tex"), to_latex(doc, project, si=True))
    print(f"wrote {out}")
    return 0


def cmd_cover(args) -> int:
    project = _load(args.path)
    doc = compose(project)
    out = write_text(Path(args.out or project.root / "cover_letter.md"), cover_letter(project, doc))
    print(f"wrote {out}")
    return 0


def cmd_bundle(args) -> int:
    from .bundle import build

    project = _load(args.path, args.journal, args.article_type)
    ref_report = verify_project(project, offline=args.offline) if not args.no_verify else None
    rep = check_project(project, args.journal, args.article_type, ref_report=ref_report,
                        offline=args.no_verify)
    result = build(project, args.out or project.root / "submission", strict=args.strict,
                   min_score=args.min_score, report=rep, fail_on=args.fail_on)
    print(f"submission package: {result['out_dir']}")
    print(f"zip: {result['zip']}")
    if result["score"]:
        print(f"score: {result['score']['score']}/100 ({result['score']['grade']})")
    return 0


def cmd_retarget(args) -> int:
    project = _load(args.path)
    src = profile(project.journal, project.article_type)
    dst = profile(args.to, args.article_type or project.article_type)
    from .checks import Report
    from .draft import compose_prose
    from .util import word_count

    prose = compose_prose(project)
    metrics = {"abstract_words": word_count(project.abstract_text()), "body_words": word_count(prose),
               "references": len(project.references),
               "figures": len([f for f in project.figures if f.kind not in {"toc", "graphical"}]) + len(project.tables)}
    print(f"{src.journal} → {dst.journal}")
    for row in retarget(src, dst, metrics):
        mark = {"pass": "✓", "fail": "✗", "warn": "!"}[row["status"]]
        print(f"  {mark} {row['item']:<22} {str(row['current']):>12} / {row['target_limit']}  {row['action']}")
    return 0


def cmd_rules(args) -> int:
    from .checks import __dict__ as _d  # noqa: F401
    codes = sorted({m for m in _all_rule_codes()})
    print(f"{len(codes)} rule codes")
    for c in codes:
        print(f"  {c}")
    return 0


def _all_rule_codes():
    import inspect
    import re as _re
    from . import checks as module
    from . import figures as figmod

    # check() re-emits the TOC-* codes from figures.py, so both modules count.
    src = inspect.getsource(module) + inspect.getsource(figmod)
    return set(_re.findall(r'"((?:STR|EVI|CHEM|REF|FIG|TAB|TOC|JNL|ETH|STY|GRD|FILE)-[A-Z0-9-]+)"', src))


def cmd_scheme(args) -> int:
    from .schemes import HAVE_RDKIT, reaction_scheme, toc_graphic

    if not HAVE_RDKIT:
        print("error: RDKit is required (`pip install rdkit`)", file=sys.stderr)
        return 2
    if args.action == "reaction":
        parts = args.reaction.split(">>")
        if len(parts) != 2:
            print("error: use 'reactant>>product' (dot-separate multiple structures)", file=sys.stderr)
            return 2
        reactants = [x for x in parts[0].split(".") if x]
        products = [x for x in parts[1].split(".") if x]
        out = reaction_scheme(reactants, products, conditions=args.conditions or [],
                              yield_text=args.yield_text or "",
                              labels=(args.labels.split(",") if args.labels else None),
                              out=args.out)
        print(f"wrote {out}")
        return 0
    if args.action == "toc":
        prof = profile(args.journal) if args.journal else None
        w = prof.toc_width_cm if prof and prof.toc_width_cm else 8.25
        h = prof.toc_height_cm if prof and prof.toc_height_cm else 4.45
        dpi = prof.toc_dpi if prof else 300
        parts = args.reaction.split(">>")
        out = toc_graphic(parts[0], parts[1], caption=args.caption or "",
                          width_cm=w, height_cm=h, dpi=dpi,
                          arrow_label=args.arrow or "", yield_text=args.yield_text or "",
                          out=args.out)
        print(f"wrote {out} at {w}×{h} cm, {dpi} dpi")
        return 0
    return 1


def cmd_doctor(args) -> int:
    import importlib
    from .chem import adduct_mass

    print(f"paperforge {__version__}")
    print(f"python {sys.version.split()[0]}")
    for mod, purpose in (("yaml", "YAML projects"), ("PIL", "figure resolution checks"),
                         ("docx", "DOCX output"), ("matplotlib", "demo figures")):
        try:
            m = importlib.import_module(mod)
            print(f"  ✓ {mod:<12} {purpose}")
        except ImportError:
            print(f"  ✗ {mod:<12} {purpose} (optional)")
    try:
        print(f"  ✓ chem engine: C14H10NO2S [M+H]+ = {adduct_mass('C14H10NO2S','[M+H]+'):.4f}")
    except Exception as exc:
        print(f"  ✗ chem engine: {exc}")
    root = Path(__file__).resolve().parent.parent
    print(f"  data: {len(journal_names())} journals, "
          f"{(root / 'data' / 'publications-openalex.json').exists() and 'corpus loaded' or 'corpus missing'}")
    return 0


def cmd_llm_draft(args) -> int:  # pragma: no cover - needs a live model
    from .llm import draft_with_llm

    project = _load(args.path)
    try:
        text = draft_with_llm(project, provider=args.provider, model=args.model)
    except (OSError, KeyError, ValueError) as exc:
        raise CliError(f"LLM request failed ({exc}); is {args.provider} reachable and configured?") from exc
    if not text.strip():
        raise CliError(f"{args.provider} returned an empty draft")
    out = write_text(Path(args.out or project.root / "build" / "llm_draft.md"), text)
    print(f"wrote {out}")
    return 0


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="paperforge",
        description="PaperForge — a chemistry-aware manuscript engine: compose, verify, score and package a paper.",
    )
    ap.add_argument("--version", action="version", version=f"paperforge {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("context", help="print the grounded evidence pack for an LLM")
    p.add_argument("path")
    p.add_argument("--compact", action="store_true")
    p.set_defaults(func=cmd_context)

    p = sub.add_parser("ingest", help="turn a folder of data/figures/refs into a project")
    p.add_argument("source")
    p.add_argument("--out", default=None, help="project directory (default: in place)")
    p.add_argument("--title")
    p.add_argument("--journal", default="Organic Letters")
    p.add_argument("--article-type", default="article")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("new", help="scaffold a new paper project")
    p.add_argument("path")
    p.add_argument("--title", default="")
    p.add_argument("--journal", default="Organic Letters")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("journals", help="journal database: list/search/match/show")
    p.add_argument("action", choices=["list", "search", "match", "show"])
    p.add_argument("query", nargs="*", default="")
    p.add_argument("--top", type=int, default=20)
    p.add_argument("--family", default=None)
    p.add_argument("--article-type", default=None)
    p.set_defaults(func=cmd_journals)

    p = sub.add_parser("refs", help="reference verification")
    p.add_argument("action", choices=["verify", "add", "check"])
    p.add_argument("path")
    p.add_argument("dois", nargs="*", default=[])
    p.add_argument("--mailto", default="paperforge@example.org")
    p.add_argument("--offline", action="store_true")
    p.set_defaults(func=cmd_refs)

    p = sub.add_parser("figures", help="figure inventory and TOC rendering")
    p.add_argument("action", choices=["inventory", "toc"])
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--source", default="")
    p.add_argument("--out", default="toc.png")
    p.add_argument("--journal", default="")
    p.add_argument("--article-type", default="article")
    p.set_defaults(func=cmd_figures)

    p = sub.add_parser("draft", help="compose the manuscript")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--format", nargs="+", default=["all"], choices=["md", "tex", "docx", "txt", "all"])
    p.add_argument("--out", default="")
    p.add_argument("--journal", default="")
    p.add_argument("--article-type", default="")
    p.add_argument("--cover-letter", action="store_true")
    p.add_argument("--highlights", action="store_true")
    p.set_defaults(func=cmd_draft)

    p = sub.add_parser("check", help="run the full rule set")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--file", default="", help="check an existing .tex/.md/.docx instead of a project")
    p.add_argument("--journal", default="")
    p.add_argument("--article-type", default="")
    p.add_argument("--json", action="store_true")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--verify-refs", action="store_true", help="query Crossref for every DOI")
    p.add_argument("--offline", action="store_true")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("score", help="submission-readiness score (0–100)")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--journal", default="")
    p.add_argument("--article-type", default="")
    p.add_argument("--json", action="store_true")
    p.add_argument("--verify-refs", action="store_true")
    p.add_argument("--offline", action="store_true")
    p.add_argument("--min", type=float, default=0)
    p.set_defaults(func=cmd_score)

    p = sub.add_parser("si", help="render Supporting Information")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--out", default="")
    p.set_defaults(func=cmd_si)

    p = sub.add_parser("cover-letter", help="render the cover letter")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--out", default="")
    p.set_defaults(func=cmd_cover)

    p = sub.add_parser("bundle", help="build a submission zip")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--out", default="")
    p.add_argument("--journal", default="")
    p.add_argument("--article-type", default="")
    p.add_argument("--strict", action="store_true", help="refuse to bundle if the fail-on level is hit")
    p.add_argument("--fail-on", choices=["blocker", "error", "warn"], default="blocker")
    p.add_argument("--min-score", type=float, default=90.0)
    p.add_argument("--no-verify", action="store_true")
    p.add_argument("--offline", action="store_true")
    p.set_defaults(func=cmd_bundle)

    p = sub.add_parser("retarget", help="what changes if I submit elsewhere?")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--to", required=True)
    p.add_argument("--article-type", default="")
    p.set_defaults(func=cmd_retarget)

    p = sub.add_parser("rules", help="list every rule code")
    p.set_defaults(func=cmd_rules)

    p = sub.add_parser("scheme", help="draw reaction schemes / TOC graphics from SMILES")
    p.add_argument("action", choices=["reaction", "toc"])
    p.add_argument("reaction", help="'reactant>>product' (dot-separate multiple structures)")
    p.add_argument("--conditions", nargs="*", default=[])
    p.add_argument("--yield-text", default="")
    p.add_argument("--labels", default="")
    p.add_argument("--caption", default="")
    p.add_argument("--arrow", default="")
    p.add_argument("--journal", default="")
    p.add_argument("--out", default="scheme.png")
    p.set_defaults(func=cmd_scheme)

    p = sub.add_parser("doctor", help="environment check")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("llm-draft", help="optional LLM pass over the grounded outline")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--provider", default="ollama")
    p.add_argument("--model", default="")
    p.add_argument("--out", default="")
    p.set_defaults(func=cmd_llm_draft)
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except (ProjectError, CliError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except BrokenPipeError:  # pragma: no cover
        return 0
