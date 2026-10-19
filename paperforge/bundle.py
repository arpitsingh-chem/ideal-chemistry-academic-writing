"""Build a submission-ready package (manuscript + SI + cover letter + manifest)."""
from __future__ import annotations

import json
import zipfile
from datetime import date
from pathlib import Path

from .checks import Report, score
from .draft import Document, compose, cover_letter, highlights
from .project import Project
from .render import to_docx, to_latex, to_markdown, to_plain
from .util import sha256_file, write_text


def build(project: Project, out_dir: str | Path, strict: bool = False,
          min_score: float = 90.0, report: Report | None = None,
          fail_on: str = "blocker") -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    doc = compose(project)

    paths = {
        "manuscript.md": write_text(out / "manuscript.md", to_markdown(doc)),
        "manuscript.tex": write_text(out / "manuscript.tex", to_latex(doc, project)),
        "manuscript.txt": write_text(out / "manuscript.txt", to_plain(doc)),
        "si.tex": write_text(out / "si.tex", to_latex(doc, project, si=True)),
        "cover_letter.md": write_text(out / "cover_letter.md", cover_letter(project, doc)),

        "references.md": write_text(out / "references.md",
                                    "# References\n\n" + "\n".join(f"{r['n']}. {r['text']}" for r in doc.references) + "\n"),
    }
    items = highlights(project, doc)
    if items:
        paths["highlights.md"] = write_text(out / "highlights.md",
                                            "# Highlights\n\n" +
                                            "\n".join(f"- {h}" for h in items) + "\n")
    try:
        paths["manuscript.docx"] = to_docx(doc, out / "manuscript.docx", project)
    except Exception as exc:  # python-docx missing is not fatal
        paths["manuscript.docx.error"] = write_text(out / "manuscript.docx.error", str(exc))

    # Copy assets
    asset_copies = []
    for f in project.figures:
        src = project.path(f.file)
        if src.exists():
            dest = out / "figures" / src.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(src.read_bytes())
            asset_copies.append(dest)
    for sub in ("refs",):
        src_dir = project.root / sub
        if src_dir.exists():
            for src in src_dir.glob("*.bib"):
                dest = out / "refs" / src.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(src.read_bytes())
                asset_copies.append(dest)

    scoring = score(report) if report else None
    checklist = _checklist(project, doc, scoring)
    paths["CHECKLIST.md"] = write_text(out / "CHECKLIST.md", checklist)

    manifest = {
        "generated": date.today().isoformat(),
        "paper": project.title,
        "journal": doc.profile.journal,
        "article_type": doc.profile.article_type,
        "score": scoring,
        "files": {},
        "assets": {},
    }
    for p in list(paths.values()) + asset_copies:
        if isinstance(p, Path) and p.exists():
            key = str(p.relative_to(out))
            manifest["files" if p.suffix != ".bib" else "assets"][key] = {
                "bytes": p.stat().st_size, "sha256": sha256_file(p)}
    write_text(out / "manifest.json", json.dumps(manifest, indent=2))

    if strict and scoring:
        errors = [i for i in (report.issues if report else []) if i.severity == "error"]
        if fail_on == "blocker" and scoring["blockers"]:
            raise SystemExit(f"Refusing to bundle: {len(scoring['blockers'])} blocker(s). See CHECKLIST.md.")
        if fail_on == "error" and errors:
            raise SystemExit(f"Refusing to bundle: {len(errors)} error(s). See CHECKLIST.md.")
        if fail_on == "warn" and (errors or report.warnings):
            raise SystemExit("Refusing to bundle: warnings present. See CHECKLIST.md.")
        if scoring["score"] < min_score:
            raise SystemExit(f"Refusing to bundle: score {scoring['score']} < {min_score}.")

    zip_path = out.parent / f"{_slug(project.title)}-submission.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in out.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(out))
    return {"out_dir": str(out), "zip": str(zip_path), "files": [str(p.relative_to(out)) for p in paths.values()],
            "score": scoring}


def _slug(text: str) -> str:
    import re
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:50] or "paper"


def _checklist(project: Project, doc: Document, scoring: dict | None) -> str:
    p = doc.profile
    rows = []
    rows.append(("Journal limits confirmed on the official page", "manual", p.verified))
    rows.append(("Abstract within limit", "auto", f"{len(doc.abstract.split())} words / ≤{p.limits.abstract_max}"))
    rows.append(("TOC graphic present", "auto", bool(project.toc_image()) or any(f.kind in {"toc", "graphical"} for f in project.figures)))
    rows.append(("All DOIs verified", "auto", all(r.verified for r in project.references) if project.references else False))
    rows.append(("Characterisation complete", "auto", all(c.nmr_1h and c.nmr_13c and (c.hrms_found or c.hrms_calcd) for c in project.compounds if not c.known) if project.compounds else "n/a"))
    rows.append(("SI compiled", "manual", (project.root / "si").exists()))
    rows.append(("Cover letter", "auto", True))
    rows.append(("All authors approved the version", "manual", False))
    lines = [f"# Submission checklist — {project.title}", "",
             f"Target: **{p.journal}** ({p.article_type})", ""]
    if scoring:
        lines += [f"Readiness score: **{scoring['score']}/100** ({scoring['grade']}, {scoring['status']})", ""]
    lines += ["| Item | How | Status |", "|---|---|---|"]
    for item, how, status in rows:
        mark = "✅" if status is True else ("—" if status == "manual" else ("n/a" if status == "n/a" else f"⚠️ {status}"))
        lines.append(f"| {item} | {how} | {mark} |")
    lines += ["", "## Publisher declarations to paste into the submission system", "",
              "- All authors have approved the manuscript and its submission.",
              "- The work is original and not under consideration elsewhere.",
              "- Conflicts of interest: see the manuscript statement.",
              "- Data availability: see the manuscript statement.",
              "- AI use: see the AI-use disclosure.", ""]
    return "\n".join(lines)
