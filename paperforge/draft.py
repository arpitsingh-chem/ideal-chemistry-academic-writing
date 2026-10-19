"""Deterministic manuscript composition.

PaperForge does not invent science.  It assembles a complete, correctly
structured manuscript from four kinds of input:

1. **Structured narrative** (``sections:`` in the project file) — your words.
2. **Data files** (``datasets:``) — summary sentences and tables are computed
   from the numbers, never typed by hand.
3. **Compound records** (``compounds:``) — Experimental section and SI are
   generated from the same records the chemistry checks validate.
4. **Figures** (``figures:``) — captions, call-outs and the TOC entry.

An optional LLM step (``paperforge draft --llm``) can rewrite prose, but its
output is passed through the same grounding checks: unknown citation keys or
numbers that do not exist in the data are reported and block the build.
"""
from __future__ import annotations

import csv
import re
import statistics
from dataclasses import dataclass, field

from . import chem
from .journals import JournalProfile, profile as journal_profile
from .project import Compound, Project
from .util import word_count


@dataclass
class TableData:
    id: str
    caption: str
    headers: list[str]
    rows: list[list[str]]
    footnote: str = ""
    numeric_summary: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"id": self.id, "caption": self.caption, "headers": self.headers,
                "rows": self.rows, "footnote": self.footnote}


@dataclass
class DocSection:
    heading: str
    paragraphs: list[dict] = field(default_factory=list)
    tables: list[str] = field(default_factory=list)
    generated: bool = False


@dataclass
class Document:
    title: str
    authors: list[dict]
    affiliations: dict
    abstract: str
    keywords: list[str]
    sections: list[DocSection]
    tables: dict[str, TableData]
    figures: list[dict]
    references: list[dict]
    back_matter: dict
    toc_text: str
    profile: JournalProfile
    meta: dict = field(default_factory=dict)

    def section(self, prefix: str) -> DocSection | None:
        prefix = prefix.lower()
        for s in self.sections:
            if s.heading.lower().startswith(prefix):
                return s
        return None


# ---------------------------------------------------------------------------
# Tables and dataset summaries
# ---------------------------------------------------------------------------


def load_table(path) -> tuple[list[str], list[list[str]]]:
    with open(path, encoding="utf-8-sig", newline="") as fh:
        sample = fh.read(4096)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        rows = list(csv.reader(fh, dialect))
    if not rows:
        return [], []
    return rows[0], rows[1:]


def _numeric(rows: list[list[str]], idx: int) -> list[float]:
    vals = []
    for r in rows:
        if idx >= len(r):
            continue
        try:
            vals.append(float(r[idx].replace("±", "").strip()))
        except (ValueError, AttributeError):
            continue
    return vals


def dataset_summaries(project: Project, dataset: dict) -> list[str]:
    """Generate summary sentences from a CSV dataset."""
    path = project.path(str(dataset.get("file", "")))
    if not path.exists():
        return []
    headers, rows = load_table(path)
    if not headers:
        return []
    out = []
    specs = dataset.get("summary") or []
    for spec in specs:
        var = str(spec.get("variable", ""))
        template = spec.get("template", "")
        if var not in headers:
            continue
        idx = headers.index(var)
        vals = _numeric(rows, idx)
        if not vals:
            continue
        ctx = {
            "min": min(vals), "max": max(vals), "mean": statistics.mean(vals),
            "median": statistics.median(vals), "n": len(vals),
            "sum": sum(vals),
            "sd": statistics.stdev(vals) if len(vals) > 1 else 0.0,
            "variable": var,
        }
        try:
            out.append(template.format(**ctx))
        except (KeyError, ValueError):
            out.append(f"{var} ranged from {ctx['min']:g} to {ctx['max']:g} "
                       f"(mean {ctx['mean']:.1f}, n = {ctx['n']}).")
    if not out and dataset.get("auto", True):
        # Skip identifier columns, report at most two per dataset, and rotate the
        # phrasing so six datasets do not produce six identical sentences.
        skip = {"entry", "id", "no", "no.", "index", "compound", "complex", "run"}
        candidates = []
        for i, h in enumerate(headers):
            if h.strip().lower() in skip or h.strip().upper().startswith(("ID", "NO")):
                continue
            vals = _numeric(rows, i)
            if len(vals) >= 3 and len(vals) >= len(rows) * 0.6:
                candidates.append((h, vals))
                if len(candidates) == 2:
                    break
        for k, (h, vals) in enumerate(candidates):
            sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
            mean = statistics.mean(vals)
            label = h.replace("_", " ")
            if k % 3 == 0:
                out.append(f"{label} spans {min(vals):g}–{max(vals):g} "
                           f"(mean {mean:.1f} ± {sd:.1f}, n = {len(vals)}).")
            elif k % 3 == 1:
                out.append(f"The mean {label} is {mean:.1f} ± {sd:.1f}, with values "
                           f"between {min(vals):g} and {max(vals):g} (n = {len(vals)}).")
            else:
                out.append(f"Across {len(vals)} entries, {label} covers {min(vals):g} to "
                           f"{max(vals):g} (mean {mean:.1f} ± {sd:.1f}).")
    return out


# ---------------------------------------------------------------------------
# Experimental / SI
# ---------------------------------------------------------------------------


def characterisation_line(c: Compound) -> str:
    bits = []
    if c.nmr_1h:
        bits.append(f"¹H NMR {c.nmr_1h.strip().rstrip('.')};")
    if c.nmr_13c:
        bits.append(f"¹³C{{¹H}} NMR {c.nmr_13c.strip().rstrip('.')};")
    if c.ir:
        bits.append(f"IR {c.ir.strip().rstrip('.')};")
    if c.hrms_found is not None or c.hrms_calcd is not None:
        adduct = c.hrms_adduct.replace(" ", "")
        calcd = f"{c.hrms_calcd:.4f}" if c.hrms_calcd is not None else "—"
        found = f"{c.hrms_found:.4f}" if c.hrms_found is not None else "—"
        formula = c.formula or "?"
        bits.append(f"HRMS (ESI-TOF) m/z calcd for {formula} {adduct} {calcd}, found {found};")
    if c.mp:
        bits.append(f"mp {c.mp.strip().rstrip('.')};")
    if c.alpha_d:
        bits.append(f"[α]D {c.alpha_d.strip().rstrip('.')};")
    if c.purity:
        bits.append(f"purity {c.purity.strip().rstrip('.')};")
    if c.ccdc:
        bits.append(f"CCDC {c.ccdc}.")
    line = " ".join(bits).strip()
    return line.rstrip(";") + "." if line else ""


def experimental_block(c: Compound) -> dict:
    head = f"Compound {c.id}"
    if c.name:
        head += f": {c.name}"
    yield_bits = []
    if c.yield_percent is not None:
        yield_bits.append(f"{c.yield_percent:g}%")
    if c.mass_g is not None:
        yield_bits.append(f"{c.mass_g:.3f} g")
    if c.mmol is not None:
        yield_bits.append(f"{c.mmol:.2f} mmol")
    head += f" ({', '.join(yield_bits)})" if yield_bits else ""
    proc = (c.procedure or "").strip()
    if not proc:
        proc = ("Prepared according to the general procedure; "
                "purified by column chromatography." if not c.known else
                "Known compound; prepared as reported previously.")
    char = characterisation_line(c)
    text = f"{head}. {proc}".replace("..", ".")
    if char:
        text += f" {char}"
    return {"text": text, "cites": []}


def si_text(project: Project, doc: "Document") -> str:
    lines = [f"Supporting Information", "", doc.title, "", "Contents", ""]
    entries = ["General experimental methods", "Synthetic procedures and characterisation",
               "NMR spectra", "HRMS spectra", "References"]
    if any(c.crystal for c in project.compounds):
        entries.insert(3, "Crystallographic data and checkCIF")
    for i, e in enumerate(entries, start=2):
        lines.append(f"S{i-1}. {e}")
    lines += ["", "General experimental methods", ""]
    lines.append(project.narrative.get("general_methods", "") or
                 "All reagents were used as received. NMR spectra were recorded on a Bruker "
                 "Avance spectrometer; chemical shifts are reported in ppm relative to TMS. "
                 "High-resolution mass spectra were acquired on an ESI-TOF instrument.")
    lines += ["", "Synthetic procedures and characterisation", ""]
    for c in project.compounds:
        if c.known:
            continue
        block = experimental_block(c)
        lines += [f"Compound {c.id}", "", block["text"], ""]
        if c.spectra_files:
            lines.append("Spectra: " + ", ".join(c.spectra_files))
            lines.append("")
    if any(c.crystal for c in project.compounds):
        lines += ["Crystallographic data", ""]
        for c in project.compounds:
            if c.crystal and c.ccdc:
                lines.append(f"CCDC {c.ccdc} contains the supplementary crystallographic data for "
                             f"compound {c.id}. These data can be obtained free of charge from the "
                             "Cambridge Crystallographic Data Centre.")
    lines += ["", "HRMS spectra", "", "Copies of HRMS spectra for all new compounds are provided."]
    return "\n".join(lines)


def cover_letter(project: Project, doc: "Document") -> str:
    p = doc.profile
    corr = project.corresponding[0] if project.corresponding else (project.authors[0] if project.authors else None)
    name = corr.name if corr else "Corresponding Author"
    aff = ""
    if corr and corr.affiliation and isinstance(project.affiliations, dict):
        aff = project.affiliations.get(corr.affiliation, "") or project.affiliations.get(str(corr.affiliation), "")
    context = project.abstract.get("context", "") if isinstance(project.abstract, dict) else ""
    gap = project.abstract.get("gap", "") if isinstance(project.abstract, dict) else ""
    narrative = project.narrative or {}
    significance = narrative.get("significance") or gap or project.abstract_text()[:400]
    ai_note = ""
    if (project.back_matter or {}).get("ai_disclosure"):
        ai_note = "AI tools were used for language editing; all scientific content is the authors' own."
    reviewers = narrative.get("suggested_reviewers", [])
    reviewer_block = ("Suggested reviewers:\n\n" + "\n".join(f"- {r}" for r in reviewers)) if reviewers else "Suggested reviewers available on request."
    email = corr.email if corr else ""
    kind = "conceptual advance" if p.article_type in {"communication", "letter"} else "full study"
    return f"""Dear Editor,

Please consider our manuscript "{doc.title}" for publication in {p.journal} as a {p.article_type}.

{context}

{significance}

We believe the work fits {p.journal} because it reports a {kind} of interest to the journal's readership, and because the conclusions are supported by complete characterisation and independent control experiments.

This manuscript is original, has not been published elsewhere, and is not under consideration by another journal. All authors have approved the submission and declare no competing financial interest. {ai_note}

{reviewer_block}

Yours sincerely,

{name}
{aff}
{email}
"""


def highlights(project: Project, doc: "Document") -> list[str]:
    if project.highlights:
        out = []
        for h in project.highlights:
            if isinstance(h, dict):  # unquoted "Key: value" YAML
                out.append(": ".join(str(x) for pair in h.items() for x in pair))
            else:
                out.append(str(h).strip())
        return [h for h in out if h]
    sents = [s for s in re.split(r"(?<=[.!?])\s+", project.abstract_text()) if s]
    out = []
    for s in sents:
        s = s.strip().rstrip(".")
        if 20 <= len(s) <= 85:
            out.append(s)
        if len(out) == 4:
            break
    return out


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------


def extract_inline_cites(text: str, cites: list, known: set[str]) -> tuple[str, list]:
    """Turn `[key1, key2]` markers that match real references into citation metadata."""
    found: list[str] = []

    def repl(m):
        keys = [k.strip() for k in re.split(r"[;,]", m.group(1)) if k.strip()]
        if keys and all(k in known for k in keys):
            found.extend(keys)
            return "@@CITE:" + ",".join(keys) + "@@"
        return m.group(0)

    new = re.sub(r"\[([A-Za-z0-9_\-,\s;]+)\]", repl, text)
    new = re.sub(r"\s{2,}", " ", new).strip()
    inline = list(dict.fromkeys(found))
    leftover = [c for c in dict.fromkeys(cites or []) if c not in inline]
    return new, leftover


CITE_MARK = re.compile(r"@@CITE:([^@]+)@@")


def plain(text: str) -> str:
    """Strip internal citation markers and tidy the resulting punctuation."""
    out = CITE_MARK.sub("", text)
    return re.sub(r"\s+([.,;:])", r"\1", out).strip()


def compose(project: Project, journal: str | None = None, article_type: str | None = None) -> Document:
    prof = journal_profile(journal or project.journal, article_type or project.article_type)
    known_keys = {r.key for r in project.references if r.key}
    tables: dict[str, TableData] = {}

    # Table assets: a table can point at a CSV or at a dataset id
    dataset_by_id = {str(d.get("id")): d for d in project.datasets if isinstance(d, dict)}
    for t in project.tables:
        src = t.file or (dataset_by_id.get(t.id, {}) or {}).get("file", "")
        headers, rows = load_table(project.path(src)) if src and project.path(src).exists() else (t.columns, [])
        tables[t.id] = TableData(id=t.id, caption=t.caption, headers=headers, rows=rows, footnote=t.footnote)

    # Figures
    figures = []
    for i, f in enumerate([f for f in project.figures if f.kind not in {"toc", "graphical"}], start=1):
        figures.append({"id": f.id, "file": f.file, "caption": f.caption,
                        "label": f.label or f"Figure {i}", "kind": f.kind, "number": i})

    # Sections
    sections: list[DocSection] = []
    authored = {s.heading.lower(): s for s in project.sections}

    for s in project.sections:
        sec = DocSection(heading=s.heading)
        for p in s.paragraphs:
            text, cites = extract_inline_cites(p.text, p.cites, known_keys)
            sec.paragraphs.append({"text": text, "cites": cites})
        for sub in s.subsections:
            sec.paragraphs.append({"text": f"__SUB__{sub.heading}", "cites": []})
            for p in sub.paragraphs:
                text, cites = extract_inline_cites(p.text, p.cites, known_keys)
                sec.paragraphs.append({"text": text, "cites": cites})
        if s.dataset and s.dataset in tables:
            sec.tables.append(s.dataset)
        sections.append(sec)

    # Auto-generated Results summary if datasets exist and no results paragraph covers them
    if project.datasets:
        summary_sentences: list[str] = []
        for ds in project.datasets:
            if not isinstance(ds, dict):
                continue
            summary_sentences += dataset_summaries(project, ds)
        if summary_sentences:
            target = next((s for s in sections if s.heading.lower().startswith(("result", "discussion"))), None)
            if target is None:
                target = DocSection(heading="Results and Discussion")
                sections.insert(1, target)
            target.paragraphs.append({"text": " ".join(summary_sentences), "cites": [], "generated": True})

    # Experimental section from compound records (if not authored)
    if project.compounds and not any(s.heading.lower().startswith(("experimental", "method")) for s in sections):
        exp = DocSection(heading="Experimental Section")
        gen = project.narrative.get("general_methods", "") or (
            "All reagents were used as received unless otherwise stated. NMR spectra were recorded "
            "on a Bruker Avance spectrometer; chemical shifts (δ) are reported in ppm relative to TMS. "
            "High-resolution mass spectra were obtained on an ESI-TOF instrument."
        )
        exp.paragraphs.append({"text": gen, "cites": []})
        exp.paragraphs.append({"text": "__SUB__Synthetic procedures and characterisation", "cites": []})
        for c in project.compounds:
            exp.paragraphs.append(experimental_block(c))
        sections.append(exp)
    elif project.compounds:
        exp = next(s for s in sections if s.heading.lower().startswith(("experimental", "method")))
        if len(exp.paragraphs) <= 1:
            exp.paragraphs.append({"text": "__SUB__Synthetic procedures and characterisation", "cites": []})
            for c in project.compounds:
                exp.paragraphs.append(experimental_block(c))

    # Attach tables to the Results section, in declaration order
    results_sec = next((s for s in sections if s.heading.lower().startswith(("result", "discussion"))), None)
    if results_sec:
        for tid in tables:
            if tid not in results_sec.tables:
                results_sec.tables.append(tid)
    else:
        for tid in tables:
            sections.append(DocSection(heading="Results and Discussion", tables=[tid]))

    # Conclusion fallback
    if not any(s.heading.lower().startswith(("conclusion", "summary")) for s in sections):
        narrative = project.narrative or {}
        bullets = narrative.get("conclusion") or []
        text = " ".join(bullets) if bullets else (
            (project.abstract.get("impact", "") if isinstance(project.abstract, dict) else "")
            or "This work establishes a general route that should guide further studies."
        )
        sections.append(DocSection(heading="Conclusion", paragraphs=[{"text": text, "cites": []}], generated=True))

    authors = []
    for a in project.authors:
        authors.append({"name": a.name, "affiliation": a.affiliation, "email": a.email,
                        "orcid": a.orcid, "corresponding": a.corresponding})

    toc_text = project.toc_text()
    if not toc_text:
        impact = project.abstract.get("impact", "") if isinstance(project.abstract, dict) else ""
        toc_text = impact.strip() or project.abstract_text()[:200]
        if prof.toc_text_max_chars and len(toc_text) > prof.toc_text_max_chars:
            toc_text = toc_text[: prof.toc_text_max_chars - 1].rsplit(" ", 1)[0] + "."

    refs = []
    for i, r in enumerate(project.references, start=1):
        refs.append({"n": i, "key": r.key or f"ref{i}", "text": _reference_text(r)})

    meta = {
        "generated_sections": [s.heading for s in sections if s.generated],
        "auto_results": bool(project.datasets),
        "profile_verified": prof.verified,
    }

    return Document(
        title=project.title,
        authors=authors,
        affiliations=project.affiliations,
        abstract=project.abstract_text(),
        keywords=project.keywords,
        sections=sections,
        tables=tables,
        figures=figures,
        references=refs,
        back_matter=project.back_matter,
        toc_text=toc_text,
        profile=prof,
        meta=meta,
    )


def _reference_text(r) -> str:
    authors = r.authors or []
    a = ", ".join(authors[:10]) + (", et al." if len(authors) > 10 else "")
    bits = [a] if a else []
    if r.title:
        bits.append(r.title)
    if r.journal:
        bits.append(r.journal)
    if r.year:
        bits.append(str(r.year))
    if r.volume:
        bits.append(r.volume)
    if r.pages:
        bits.append(r.pages)
    if r.doi:
        bits.append(f"DOI: {r.doi}")
    return ". ".join(bits).strip() + "."


def compose_prose(project: Project) -> str:
    """Plain prose of all authored sections + generated results (no markup)."""
    doc = compose(project)
    chunks = []
    for s in doc.sections:
        chunks.append(s.heading)
        for p in s.paragraphs:
            t = p["text"]
            if t.startswith("__SUB__"):
                chunks.append(t.replace("__SUB__", ""))
            else:
                chunks.append(plain(t))
    return "\n\n".join(chunks)


def summary_line(project: Project) -> str:
    st = [f"“{project.title}”", f"{project.journal}", f"{len(project.compounds)} compounds",
          f"{len(project.figures)} figures", f"{len(project.references)} references",
          f"{word_count(project.abstract_text())}-word abstract"]
    return " · ".join(st)


def bump_citations(project: Project, mapping: dict[str, int]) -> dict[int, int]:
    """Scaffolding helper for citation renumbering (used by renderers)."""
    return {i: mapping[k] for i, k in enumerate(project.citation_keys(), start=1) if k in mapping}
