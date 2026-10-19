"""The PaperForge rule engine.

~70 checks across eight categories: structure, abstract, evidence,
references, figures, journal fit, ethics/reproducibility and style.
Every issue carries a stable code, a severity, a human message and a fix hint,
so the report can be used by a human *and* by CI.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import chem
from .chem import ORGANIC_ELEMENTS, dbe, dbe_applicable
from .figures import caption_issues, check_figure_file, check_toc, image_info
from .journals import JournalProfile, profile as journal_profile
from .project import Compound, Project
from .refs import RefCache
from .util import read_text, sentences, similarity, visible_text, word_count

CATEGORIES = ["structure", "abstract", "evidence", "references", "figures", "journal", "ethics", "style"]
WEIGHTS = {"structure": 15, "abstract": 10, "evidence": 20, "references": 15,
           "figures": 10, "journal": 15, "ethics": 10, "style": 5}

HYPE = {"novel", "novelty", "first-ever", "first ever", "unprecedented", "superb",
        "excellent", "exceptional", "outstanding", "groundbreaking", "revolutionary",
        "remarkable", "unique", "world-class", "state-of-the-art"}
WEASEL = {"very", "quite", "rather", "extremely", "highly", "remarkably", "notably",
          "interestingly", "clearly", "obviously", "significantly", "substantially"}
PASSIVE = re.compile(r"\b(?:was|were|is|are|be|been|being)\s+(?:\w+ly\s+)?(\w+ed|written|shown|made|done|found|taken|given)\b", re.I)
UNIT_ERRORS = [
    (r"\b\d+\s?ml\b", "mL", "use 'mL' (capital L)"),
    (r"\b\d+\s?uM\b", "µM", "use 'µM'"),
    (r"\b\d+\s?oC\b", "°C", "use '°C'"),
    (r"\b\d+\s?hrs?\b", "h", "use 'h' for hours"),
    (r"\b\d+\s?mins?\b", "min", "use 'min' for minutes"),
    (r"\b\d+\s?rpm\b", "rpm", "rpm is acceptable; check journal style"),
]


@dataclass
class Issue:
    code: str
    severity: str  # error | warn | info
    category: str
    message: str
    hint: str = ""
    data: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"code": self.code, "severity": self.severity, "category": self.category,
                "message": self.message, "hint": self.hint, "data": self.data}


@dataclass
class Report:
    issues: list[Issue] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    profile: JournalProfile | None = None
    source: str = ""

    def add(self, code: str, severity: str, category: str, message: str, hint: str = "", **data) -> None:
        self.issues.append(Issue(code, severity, category, message, hint, data))

    def by(self, category: str | None = None, severity: str | None = None) -> list[Issue]:
        out = self.issues
        if category:
            out = [i for i in out if i.category == category]
        if severity:
            out = [i for i in out if i.severity == severity]
        return out

    @property
    def errors(self) -> list[Issue]:
        return self.by(severity="error")

    @property
    def warnings(self) -> list[Issue]:
        return self.by(severity="warn")

    def counts(self) -> dict:
        return {"error": len(self.by(severity="error")), "warn": len(self.by(severity="warn")),
                "info": len(self.by(severity="info"))}

    def critical(self) -> list[Issue]:
        return [i for i in self.issues if i.data.get("critical")]


# ---------------------------------------------------------------------------
# Prose helpers
# ---------------------------------------------------------------------------


def prose_of(project: Project) -> str:
    parts = []
    for sec in project.sections:
        parts.append(sec.heading)
        for p in _walk_paragraphs(sec):
            parts.append(p.text)
    return "\n\n".join(parts)


def _walk_paragraphs(sec):
    for p in sec.paragraphs:
        yield p
    for sub in sec.subsections:
        yield from _walk_paragraphs(sub)


def abstract_moves(text: str) -> dict[str, bool]:
    t = (text or "").strip()
    sents = sentences(t)
    first = " ".join(sents[:2])
    return {
        "context": bool(first) and not re.search(r"\d", first) and len(first.split()) >= 5,
        "gap": bool(re.search(r"\b(however|remains?|unknown|unexplored|challeng|limited|lack\w*|gap|here we|we report|we describe)\b", t, re.I)),
        "results": bool(re.search(r"\d", t)),
        "impact": bool(re.search(r"\b(these results|this work|our (?:findings|results|study)|"
                                 r"pave\w*|enabl\w*|allow\w*|permit\w*|underpinn?\w*|inform\w*|"
                                 r"open\w*|provide\w*|offer\w*|demonstrat\w*|establish\w*)\b",
                                 t, re.I)),
    }


def style_stats(text: str) -> dict:
    sents = sentences(text)
    lens = [len(s.split()) for s in sents] or [0]
    mean = sum(lens) / len(lens)
    long_share = sum(1 for L in lens if L >= 40) / len(lens)
    passive = len(PASSIVE.findall(text)) / max(1, len(sents))
    words = re.findall(r"[A-Za-z]+", text.lower())
    trigrams = [" ".join(words[i:i + 3]) for i in range(max(0, len(words) - 2))]
    repeats = {}
    for t in trigrams:
        repeats[t] = repeats.get(t, 0) + 1
    top_repeat = max(repeats.items(), key=lambda kv: kv[1]) if repeats else ("", 0)
    return {"sentences": len(sents), "mean_sentence_words": round(mean, 1),
            "long_sentence_share": round(long_share, 3), "passive_per_sentence": round(passive, 2),
            "top_trigram": top_repeat, "words": len(words)}


def _num_token(value) -> str:
    """Normalise 89.50 and 89.5 to the same token."""
    return f"{float(value):.6f}".rstrip("0").rstrip(".")


def find_numbers(text: str) -> list[str]:
    """Numeric tokens, excluding years and reference/citation numbers."""
    out = []
    for m in re.finditer(r"(?<![\w-])(\d+(?:\.\d+)?)(?![\w-])", text):
        tok = m.group(1)
        if re.fullmatch(r"(19|20)\d{2}", tok):
            continue
        out.append(tok)
    return out


# ---------------------------------------------------------------------------
# Individual rule groups
# ---------------------------------------------------------------------------


def looks_character_spaced(text: str, min_run: int = 8) -> bool:
    """True when text contains a run of ≥min_run single characters separated by spaces.

    Catches the class of bug where a string is iterated as a sequence
    (``" ".join("word")``) anywhere upstream of rendering.
    """
    tokens = (text or "").split()
    run = 0
    for tok in tokens:
        if len(tok) == 1:
            run += 1
            if run >= min_run:
                return True
        else:
            run = 0
    return False


def check_structure(project: Project, profile: JournalProfile, rep: Report, abstract: str,
                    headings: list[str] | None = None) -> None:
    title = project.title.strip()
    if not title:
        rep.add("STR-TITLE-MISSING", "error", "structure", "Title is missing.", critical=True)
    else:
        n = word_count(title)
        if n > profile.title_max_words:
            rep.add("STR-TITLE-LONG", "warn", "structure",
                    f"Title is {n} words (journal guidance ≤{profile.title_max_words}).",
                    "Cut to the molecular result, drop generic phrases.")
        if len(title) > 135:
            rep.add("STR-TITLE-CHARS", "info", "structure",
                    f"Title is {len(title)} characters; ≤135 is safest for RSC/Elsevier layouts.")
        hypes = [w for w in HYPE if re.search(rf"\b{re.escape(w)}\b", title, re.I)]
        if hypes:
            rep.add("STR-TITLE-HYPE", "warn", "structure",
                    f"Title contains hype word(s) {hypes}.",
                    "ACS/RSC/Wiley editors desk-reject unsupported novelty claims; state the result instead.")

    if not project.authors:
        rep.add("STR-AUTHORS", "error", "structure", "No authors listed.", critical=True)
    if not project.corresponding:
        rep.add("STR-CORRESP", "error", "structure",
                "No corresponding author is marked (required by every portfolio journal).")
    for a in project.authors:
        if not a.affiliation:
            rep.add("STR-AFFIL", "warn", "structure", f"{a.name}: no affiliation assigned.")
        if a.corresponding and not a.orcid and profile.orcid_required != "none":
            rep.add("STR-ORCID", "warn", "structure",
                    f"Corresponding author {a.name} has no ORCID iD.",
                    "ACS/Wiley/RSC require ORCID at submission for the corresponding author.")
        if a.corresponding and not a.email:
            rep.add("STR-EMAIL", "error", "structure", f"Corresponding author {a.name} has no e-mail address.")

    if not project.affiliations:
        rep.add("STR-AFFIL-LIST", "error", "structure", "No affiliations dictionary provided.")

    # Abstract
    ab = (abstract or "").strip()
    if ab and looks_character_spaced(ab):
        rep.add("STR-ABSTRACT-SPACED", "error", "abstract",
                "The abstract reads as single characters separated by spaces.",
                "An abstract field was probably a string where a list of sentences "
                "was expected; check paper.yaml.", critical=True)
    if not ab:
        rep.add("STR-ABSTRACT-MISSING", "error", "abstract",
                "Abstract is missing — automatic return at ACS and a desk-reject risk everywhere.",
                "Provide context, gap, quantitative results and impact.", critical=True)
    n = word_count(ab) if ab else 0
    lim = profile.limits.abstract_max
    if n > lim:
        rep.add("STR-ABSTRACT-LONG", "error", "abstract",
                f"Abstract is {n} words (limit {lim} for {profile.journal} {profile.article_type}).",
                f"Cut {n-lim} words; move detail to the manuscript.")
    if n < max(50, profile.limits.abstract_min):
        rep.add("STR-ABSTRACT-SHORT", "warn", "abstract",
                f"Abstract is only {n} words (target {profile.limits.abstract_min}–{lim}).")
    moves = abstract_moves(ab) if ab else {}
    missing = [k for k in ("gap", "results", "impact") if not moves.get(k)]
    if ab and missing:
        rep.add("STR-ABSTRACT-MOVES", "warn", "abstract",
                f"Abstract lacks the {missing} move(s) (context → gap → results → impact).",
                "Each move is 1–2 sentences; results must carry numbers and units.")
    if ab and profile.abstract_forbids_citations and re.search(r"\[\d+\]|\(\d+,?\s?\d*\)|\\cite", ab):
        rep.add("STR-ABSTRACT-CITES", "error", "abstract",
                "Abstract contains reference citations, which this publisher forbids.")
    if ab and profile.abstract_forbids_compound_numbers and re.search(r"\b(compound\s+)?\d+[a-z]\b", ab):
        rep.add("STR-ABSTRACT-COMPOUNDS", "warn", "abstract",
                "Abstract contains compound numbers; Wiley requires compound names in the abstract.")
    if ab and profile.abstract_toc_combined_words:
        total = n + word_count(project.toc_text() or "")
        if total > profile.abstract_toc_combined_words:
            rep.add("STR-ABSTRACT-TOC-COMBINED", "error", "abstract",
                    f"Abstract + TOC graphic count as {total} words (limit "
                    f"{profile.abstract_toc_combined_words} at {profile.journal}).")

    # Keywords
    kw = project.keywords
    if not kw and profile.keywords_min:
        rep.add("STR-KEYWORDS", "warn", "structure",
                f"No keywords (journal expects {profile.keywords_min}–{profile.keywords_max}).")
    elif kw:
        if len(kw) < profile.keywords_min:
            rep.add("STR-KEYWORDS-FEW", "warn", "structure",
                    f"{len(kw)} keywords provided (expects ≥{profile.keywords_min}).")
        if len(kw) > profile.keywords_max:
            rep.add("STR-KEYWORDS-MANY", "warn", "structure",
                    f"{len(kw)} keywords provided (maximum {profile.keywords_max}).")

    # Sections
    headings = [h.lower() for h in (headings if headings is not None else [s.heading for s in project.sections])]
    if not any("intro" in h for h in headings):
        rep.add("STR-INTRO", "error", "structure", "No Introduction section.")
    if not any(("result" in h or "discussion" in h) for h in headings):
        rep.add("STR-RESULTS", "error", "structure", "No Results / Discussion section.")
    if not any("experimental" in h or "method" in h for h in headings):
        rep.add("STR-EXPERIMENTAL", "error", "structure",
                "No Experimental / Methods section (the reproducibility contract of chemistry).")
    if not any("conclusion" in h or "summary" in h for h in headings):
        rep.add("STR-CONCLUSION", "warn", "structure", "No Conclusion / Summary section.")
    order = [i for i, h in enumerate(headings) if "intro" in h]
    rorder = [i for i, h in enumerate(headings) if "result" in h or "discussion" in h]
    if order and rorder and order[0] > rorder[0]:
        rep.add("STR-SECTION-ORDER", "warn", "structure",
                "Results appear before the Introduction.")

    # Back matter that the renderer adds
    bm = project.back_matter or {}
    if not bm.get("data_availability"):
        rep.add("STR-DATA-STMT", "error", "ethics", "No data-availability statement.")
    if not bm.get("coi"):
        rep.add("STR-COI", "error", "ethics", "No conflict-of-interest statement.")
    if "supporting information" not in prose_of(project).lower() and project.compounds \
            and not project.options.get("auto_back_matter", True):
        rep.add("STR-SI-PARAGRAPH", "warn", "structure",
                "No descriptive Supporting Information paragraph in the manuscript.",
                "List what the SI contains, not a range of figure numbers.")

    # Hype in body
    body = prose_of(project)
    hits = [w for w in HYPE if re.search(rf"\b{re.escape(w)}\b", body, re.I)]
    if hits:
        rep.add("STR-HYPE-TEXT", "warn", "style",
                f"Hype word(s) in the body text: {sorted(set(hits))}.",
                "Replace with the measured claim.")


def check_evidence(project: Project, profile: JournalProfile, rep: Report, prose: str,
                   evidence_numbers: set[str]) -> None:
    compounds = project.compounds
    synthetic = bool(re.search(r"\b(synthes|prepar|catalys|material|complex)", project.title + " " + project.abstract_text(), re.I))

    if synthetic and not compounds:
        rep.add("EVI-NO-COMPOUNDS", "warn", "evidence",
                "No compounds declared — original synthetic work must document every new compound.",
                "Add a `compounds:` block with formula, yield, NMR, HRMS and spectra.")

    for c in compounds:
        label = c.id
        if c.known:
            continue
        if not c.formula:
            rep.add("EVI-FORMULA", "error", "evidence", f"Compound {label}: no molecular formula.")
        else:
            for i in chem.check_formula(c.formula):
                rep.add(i.code, i.severity, "evidence", f"Compound {label}: {i.message}", i.hint,
                        critical=(i.severity == "error"))
            if not c.mw:
                c.mw = round(chem.average_mass(c.formula), 2)
        if not c.nmr_1h:
            rep.add("EVI-NMR1H", "error", "evidence", f"Compound {label}: no ¹H NMR data.")
        if not c.nmr_13c:
            rep.add("EVI-NMR13C", "error", "evidence", f"Compound {label}: no ¹³C NMR data.")
        if not (c.hrms_calcd or c.hrms_found) and not c.known:
            rep.add("EVI-HRMS", "error", "evidence", f"Compound {label}: no HRMS data.")
        if not c.ir:
            rep.add("EVI-IR", "info", "evidence", f"Compound {label}: no IR data (expected for new compounds).")
        if not c.mp:
            rep.add("EVI-MP", "info", "evidence", f"Compound {label}: no melting point (solids).")
        if c.chiral and not c.alpha_d:
            rep.add("EVI-ALPHA", "warn", "evidence", f"Compound {label}: chiral but no [α]D reported.")
        if c.crystal and not c.ccdc:
            rep.add("EVI-CCDC", "error", "evidence",
                    f"Compound {label}: crystal structure without a CCDC deposition number.",
                    "Deposit before submission and quote the CCDC number in the manuscript.",
                    critical=True)
        if not c.purity:
            rep.add("EVI-PURITY", "info", "evidence", f"Compound {label}: no purity statement.")

        if c.formula and (c.hrms_calcd is not None or c.hrms_found is not None):
            for i in chem.check_hrms(c.formula, c.hrms_adduct, c.hrms_calcd, c.hrms_found):
                rep.add(i.code, i.severity, "evidence", f"Compound {label}: {i.message}", i.hint,
                        critical=(i.code == "CHEM-HRMS-CALCD"))
        if c.formula and c.nmr_1h:
            total, _ = chem.parse_integrals(c.nmr_1h)
            for i in chem.check_nmr(c.formula, total or None, c.n_13c_signals):
                rep.add(i.code, i.severity, "evidence", f"Compound {label}: {i.message}", i.hint)
        if c.formula and c.mmol is not None and c.yield_percent is not None:
            mw = c.mw or chem.average_mass(c.formula)
            for i in chem.check_yield(c.mass_g, c.mmol, mw, c.yield_percent):
                rep.add(i.code, i.severity, "evidence", f"Compound {label}: {i.message}", i.hint)
        if c.spectra_files:
            missing = [f for f in c.spectra_files if not project.path(f).exists()]
            if missing:
                rep.add("EVI-SPECTRA-FILES", "warn", "evidence",
                        f"Compound {label}: spectra files not found: {missing}")

    seen_ids: dict[str, int] = {}
    for c in project.compounds:
        seen_ids[c.id] = seen_ids.get(c.id, 0) + 1
    for cid, n in seen_ids.items():
        if n > 1:
            rep.add("EVI-DUP-ID", "error", "evidence",
                    f"Compound {cid} appears {n} times; the Experimental would print it {n} times.",
                    "Merge the duplicate rows (or give them distinct ids) before drafting.")

    # Safety / stats / computational rigour
    if synthetic and not (project.back_matter or {}).get("safety"):
        rep.add("EVI-SAFETY", "warn", "ethics",
                "No safety statement for experimental work (mandatory at ACS).")
    if re.search(r"\bDFT\b|density functional|B3LYP|PBE0|M06|ωB97", prose, re.I) and \
            not re.search(r"(B3LYP|PBE0|M06|ωB97|def2-|6-31G|cc-pV|LANL2DZ)", prose, re.I):
        rep.add("EVI-COMPUTATIONAL", "warn", "evidence",
                "Computational results mentioned without a functional/basis set.",
                "State level of theory, basis set, solvation model and software version.")
    if re.search(r"\b(IC50|Kd|Km|kcat|quantum yield|detection limit|LOD|TOF|TON)\b", prose) and \
            not re.search(r"(±|error bar|standard deviation|\bn\s*=\s*\d|triplicate|replicate)", prose, re.I):
        rep.add("EVI-STATS", "info", "evidence",
                "Quantitative claims without uncertainty or replicate counts.",
                "Add ± SD, n, and the fitting model.")
    # Grounding of abstract numbers (single digits are usually "two steps", "3 examples")
    untraced = sorted(n for n in find_numbers(project.abstract_text())
                      if n not in evidence_numbers and not (len(n) == 1 and n.isdigit()))
    if untraced:
        rep.add("EVI-UNGROUNDED-ABSTRACT", "warn", "evidence",
                f"Abstract numbers not found in the project data: {untraced[:8]}",
                "Every number in the abstract must trace to a dataset/compound record — or it is unverifiable.",
                data={"numbers": untraced})


def check_references(project: Project, profile: JournalProfile, rep: Report,
                     ref_report=None, offline: bool = False) -> None:
    refs = project.references
    cache = RefCache(project.root)
    keys = {r.key for r in refs if r.key}
    cited = project.citation_keys()

    if not refs:
        rep.add("REF-NONE", "error", "references",
                "No references — a chemistry paper without literature is not submittable.",
                critical=True)
        return
    for k in cited:
        if keys and k not in keys:
            rep.add("REF-MISSING-KEY", "error", "references",
                    f"Citation key {k!r} used in text but not defined in references.", critical=True)
    dois: dict[str, str] = {}
    for r in refs:
        doi = (r.doi or "").strip().lower()
        if not doi:
            continue
        if doi in dois:
            rep.add("REF-DUPLICATE-DOI", "warn", "references",
                    f"{r.key or r.title} and {dois[doi]} are the same work (DOI {doi}) — keep one.")
        else:
            dois[doi] = r.key or r.title
    for r in refs:
        if r.key and r.key not in cited:
            rep.add("REF-UNUSED", "warn", "references", f"Reference {r.key!r} is never cited in the text.")
        if not r.doi:
            rep.add("REF-NO-DOI", "warn", "references",
                    f"Reference {r.key or r.title}: no DOI (journals require resolvable references).")
        elif not r.verified:
            sev = "error" if not offline else "warn"
            rep.add("REF-UNVERIFIED", sev, "references",
                    f"Reference {r.key or r.doi}: DOI has not been verified against Crossref.",
                    "Run `paperforge refs verify .` with network access.")
        # a retraction verified earlier is in .paperforge/refcache.json; use it offline
        cached = cache.get(r.doi) if r.doi else None
        if r.retracted or (cached or {}).get("retracted"):
            rep.add("REF-RETRACTED", "error", "references",
                    f"Reference {r.key or r.doi} is retracted.", critical=True)

    if ref_report:
        if ref_report.not_found:
            rep.add("REF-NOT-FOUND", "error", "references",
                    f"{ref_report.not_found} DOI(s) not found at Crossref.", critical=True)
        if ref_report.duplicates:
            rep.add("REF-DUPLICATE", "error", "references",
                    f"Duplicate DOI(s): {ref_report.duplicates}")
        already = {i.message for i in rep.issues if i.code == "REF-RETRACTED"}
        for err in ref_report.errors:
            if "RETRACTED" not in err:
                continue
            # the per-reference loop above already reported known retractions;
            # only add what it could not know (e.g. retractions found during verify)
            key = re.search(r"\(([^)]+)\)\s*$", err.strip())
            doi = re.search(r"10\.\d{4,9}/\S+?(?=[\s,)]|$)", err)
            subject = key.group(1) if key else (doi.group(0) if doi else "")
            if subject and any(subject in m for m in already | {r.key or "" for r in refs}):
                if any(subject in m for m in already):
                    continue
            rep.add("REF-RETRACTED", "error", "references", err, critical=True)
    if profile.limits.refs_max and len(refs) > profile.limits.refs_max:
        rep.add("JNL-REFS-MAX", "error", "journal",
                f"{len(refs)} references exceed the {profile.limits.refs_max}-reference limit "
                f"for {profile.journal} {profile.article_type}.")
    # self-citation
    first_author = project.authors[0].family_name.lower() if project.authors else ""
    selfc = sum(1 for r in refs if r.authors and first_author and first_author in r.authors[0].lower())
    if refs and selfc / len(refs) > 0.3:
        rep.add("REF-SELF", "warn", "references",
                f"{selfc}/{len(refs)} references are self-citations (>30%).", "Balance the citation base.")
    years = []
    for r in refs:
        y = getattr(r, "year", None)
        try:
            years.append(int(str(y)[:4]))
        except (TypeError, ValueError):
            continue
    if years:
        recent = sum(1 for y in years if y >= 2021)
        if recent / len(years) < 0.2:
            rep.add("REF-RECENCY", "info", "references",
                    f"Only {recent}/{len(years)} references are from 2021 or later.")


def check_figures(project: Project, profile: JournalProfile, rep: Report, prose: str) -> None:
    figs = project.figures
    figure_counter = 0
    scheme_counter = 0
    for i, f in enumerate(figs, start=1):
        if f.kind == "scheme":
            scheme_counter += 1
        elif f.kind not in {"toc", "graphical"}:
            figure_counter += 1
        for issue in check_figure_file(f, project.root, min_dpi=profile.toc_dpi if f.kind in {"toc", "graphical"} else 300):
            rep.add(issue["code"], issue["severity"], "figures", issue["message"], issue.get("hint", ""))
        if f.kind in {"toc", "graphical"}:
            continue
        for issue in caption_issues(f.caption, f.kind):
            rep.add(issue["code"], issue["severity"], "figures",
                    f"{f.id}: {issue['message']}", issue.get("hint", ""))
        if f.kind not in {"toc", "graphical"}:
            # figures and schemes are numbered independently: Scheme 1 is not
            # "display item 3".  Prefer the explicit label, else a per-kind counter.
            # Number by order of appearance within the kind: that is what the
            # rendered document does, and it is what a reader sees.
            counter = scheme_counter if f.kind == "scheme" else figure_counter
            num = counter
            if f.kind == "scheme":
                # "Scheme 1" (panel letters are not used, plural is)
                cited = re.search(rf"schemes?\s+{num}(?![0-9])", prose, re.I) or \
                    re.search(rf"scheme\s+{num}(?![0-9])", f.caption, re.I)
            else:
                # "Figure 1", "Fig. 1", "Figure 1A", "Figures 1 and 2"
                cited = re.search(rf"(figures?|fig\.?)\s*{num}(?![0-9])", prose, re.I) or \
                    re.search(rf"figure\s+{num}(?![0-9])", f.caption, re.I)
            if not cited:
                rep.add("FIG-UNCITED", "warn", "figures",
                        f"{f.label or f.id} (position {i}) is never cited in the text.",
                        "Every display item must be called out at first mention.")
        if f.source_data and not project.path(f.source_data).exists():
            rep.add("FIG-SOURCE-DATA", "warn", "figures",
                    f"{f.id}: source_data file not found ({f.source_data}).")

    for t in project.tables:
        if not project.path(str(t.file or "")).exists():
            rep.add("TAB-MISSING", "error", "figures",
                    f"Table {t.id}: data file not found ({t.file or 'none'}); it renders as an empty column.",
                    "Point the table at its CSV/TSV or remove it.")

    n_display = len([f for f in figs if f.kind not in {"toc", "graphical"}]) + len(project.tables)
    if profile.limits.figures_max and n_display > profile.limits.figures_max:
        rep.add("JNL-FIGS-MAX", "error", "journal",
                f"{n_display} display items exceed the {profile.limits.figures_max}-item limit "
                f"for {profile.journal} {profile.article_type}.")
    # numbering gaps
    for kind, items in (("figure", [f for f in figs if f.kind == "figure"]),
                        ("scheme", [f for f in figs if f.kind == "scheme"]),
                        ("table", project.tables)):
        nums = []
        for it in items:
            m = re.search(r"(\d+)", getattr(it, "label", "") or "")
            if m:
                nums.append(int(m.group(1)))
        if nums and sorted(nums) != list(range(1, len(nums) + 1)):
            rep.add("FIG-NUMBERING", "warn", "figures",
                    f"{kind} numbering is not consecutive from 1: {sorted(nums)}")
    for issue in check_toc(project, profile):
        rep.add(issue["code"], issue["severity"], "journal", issue["message"], issue.get("hint", ""))


def check_journal(project: Project, profile: JournalProfile, rep: Report, prose: str) -> None:
    body_words = word_count(prose)
    rep.metrics["body_words"] = body_words
    lim = profile.limits.body_max_words
    if lim and body_words > lim:
        rep.add("JNL-BODY-MAX", "error", "journal",
                f"Body text is {body_words} words; {profile.journal} {profile.article_type} allows ~{lim}.",
                f"Move ~{body_words-lim} words of detail to the Supporting Information.")
    if lim and body_words < 0.35 * lim and profile.article_type in {"article", "letter"}:
        rep.add("JNL-BODY-SHORT", "info", "journal",
                f"Body text is {body_words} words, well below the ~{lim}-word norm for this article type.")
    if profile.highlights_required and not project.highlights:
        rep.add("JNL-HIGHLIGHTS", "error", "journal",
                "This journal requires 3–5 highlights (≤85 characters each).")
    elif project.highlights:
        bad = [h for h in project.highlights if len(h) > 85]
        if bad:
            rep.add("JNL-HIGHLIGHTS-LONG", "warn", "journal",
                    f"{len(bad)} highlight(s) exceed 85 characters.")
    if profile.toc_text_max_chars:
        text = project.toc_text()
        if text and len(text) > profile.toc_text_max_chars:
            rep.add("JNL-TOC-TEXT", "error", "journal",
                    f"TOC text is {len(text)} characters (limit {profile.toc_text_max_chars}).")
    if profile.limits.printed_pages:
        rep.add("JNL-PAGES", "info", "journal",
                f"{profile.journal} {profile.article_type} is limited to ~{profile.limits.printed_pages} printed pages "
                f"(figures, schemes and references count toward pages).")


def check_ethics(project: Project, profile: JournalProfile, rep: Report, prose: str) -> None:
    bm = project.back_matter or {}
    authors = project.authors
    if profile.credit_required:
        missing = [a.name for a in authors if not a.credit]
        if missing:
            rep.add("ETH-CREDIT", "error", "ethics",
                    f"CRediT roles missing for: {', '.join(missing)}.",
                    "Use the 14 CRediT roles for every author.")
        else:
            invalid = sorted({r for a in authors for r in a.credit if r.lower() not in CREDIT_ROLES})
            if invalid:
                rep.add("ETH-CREDIT-INVALID", "warn", "ethics",
                        f"Unrecognised CRediT role(s): {invalid}")
    if not bm.get("coi"):
        rep.add("ETH-COI", "error", "ethics", "Conflict-of-interest statement missing.")
    if not bm.get("funding") and not bm.get("acknowledgements"):
        rep.add("ETH-FUNDING", "warn", "ethics", "No funding/acknowledgement statement.")
    if profile.data_statement_required:
        data = (bm.get("data_availability") or "").lower()
        if not data:
            rep.add("ETH-DATA", "error", "ethics", "Data-availability statement missing.")
        elif "on request" in data or "upon request" in data:
            rep.add("ETH-DATA-REQUEST", "error", "ethics",
                    "'Data available on request' is not accepted by RSC and is discouraged by all publishers.",
                    "Deposit in a repository and cite the accession/DOI.", critical=True)
    if profile.ai_disclosure_required == "required" and not bm.get("ai_disclosure"):
        rep.add("ETH-AI", "error", "ethics",
                f"{profile.journal} requires disclosure of generative-AI use.")
    elif profile.ai_disclosure_required == "recommended" and not bm.get("ai_disclosure"):
        rep.add("ETH-AI", "info", "ethics",
                "No AI-use disclosure (recommended by this publisher if assistant tools were used).")
    if re.search(r"\b(human|patient|volunteer|animal|mice|rat|zebrafish|cell line)\b", prose, re.I) and \
            not bm.get("ethics_approval"):
        rep.add("ETH-APPROVAL", "error", "ethics",
                "Human/animal work detected but no ethics-approval statement.")
    if any(c.crystal for c in project.compounds) and "ccdc" not in (prose + json_free(bm)).lower():
        rep.add("ETH-CCDC", "error", "ethics",
                "Crystal structures are reported but no CCDC deposition statement appears.", critical=True)
    if project.compounds and not bm.get("safety"):
        rep.add("ETH-SAFETY", "warn", "ethics", "No affirmative safety statement.")


CREDIT_ROLES = {
    "conceptualization", "data curation", "formal analysis", "funding acquisition",
    "investigation", "methodology", "project administration", "resources", "software",
    "supervision", "validation", "visualization", "writing – original draft",
    "writing – review & editing", "writing - original draft", "writing - review & editing",
}


def json_free(obj) -> str:
    return " ".join(str(v) for v in obj.values()) if isinstance(obj, dict) else str(obj)


def check_style(project: Project, profile: JournalProfile, rep: Report, prose: str) -> None:
    st = style_stats(prose)
    rep.metrics.update({k: v for k, v in st.items() if k not in rep.metrics})
    if st["mean_sentence_words"] > 32:
        rep.add("STY-SENTENCE-LONG", "warn", "style",
                f"Mean sentence length {st['mean_sentence_words']} words — dense even for chemistry.",
                "Split long sentences; aim for a mean of 18–26 words.")
    if st["long_sentence_share"] > 0.15:
        rep.add("STY-SENTENCE-VERYLONG", "warn", "style",
                f"{st['long_sentence_share']*100:.0f}% of sentences are ≥40 words.")
    if st["top_trigram"][1] >= 4:
        rep.add("STY-REPEAT", "warn", "style",
                f"Phrase repeated {st['top_trigram'][1]}×: “{st['top_trigram'][0]}”.")
    weasels = sorted({w for w in WEASEL if re.search(rf"\b{w}\b", prose, re.I)})
    if len(weasels) >= 4:
        rep.add("STY-WEASEL", "info", "style", f"Weasel/intensifier words used: {weasels[:8]}.")
    for pat, good, hint in UNIT_ERRORS:
        if re.search(pat, prose):
            rep.add("STY-UNIT", "warn", "style", f"Non-standard unit styling detected ({hint}).")
    if "data not shown" in prose.lower() or "unpublished data" in prose.lower():
        rep.add("STY-DATA-NOT-SHOWN", "error", "style",
                "'Data not shown' / 'unpublished data' is not acceptable — show it or drop the claim.")
    if re.search(r"[ \t]{2,}", prose):
        rep.add("STY-SPACE", "info", "style", "Multiple consecutive spaces in the body text.")


def check_grounding(project: Project, rep: Report, prose: str, evidence_numbers: set[str]) -> None:
    keys = {r.key for r in project.references if r.key}
    for p in _walk_paragraphs_all(project):
        for c in p.cites:
            for k in re.split(r"[,;]", str(c)):
                k = k.strip()
                if k and keys and k not in keys:
                    rep.add("GRD-CITE", "error", "references",
                            f"Unknown citation key {k!r} in paragraph: {p.text[:60]}…", critical=True)
    body_nums = find_numbers(prose)
    untraced = [n for n in body_nums if n not in evidence_numbers]
    if untraced and project.compounds:
        share = len(untraced) / max(1, len(body_nums))
        if share > 0.5:
            rep.add("GRD-NUMBERS", "info", "evidence",
                    f"{len(untraced)}/{len(body_nums)} numbers in the body are not in the data files "
                    f"(e.g. {untraced[:6]}). Verify they are literature values or add the source data.",
                    data={"numbers": untraced[:20]})
    # A number that is *another* compound's own value is a misattribution, not prose.
    # shortcut: only yields (%) and amounts (mmol); widen when a real case needs it.
    owner: dict[tuple[str, str], set[str]] = {}
    for c in project.compounds:
        for field, unit in (("yield_percent", "%"), ("mmol", "mmol")):
            v = getattr(c, field, None)
            if isinstance(v, (int, float)):
                owner.setdefault((_num_token(v), unit), set()).add(c.id)
    ids = {c.id for c in project.compounds}
    for sec in project.sections:
        for p in _walk_paragraphs(sec):
            # clauses too: "P2 gave 89.5%, and P1 gave 70.0%"
            for sent in [c for s_ in sentences(p.text) for c in re.split(r",\s+and\s+|;\s+", s_)]:
                named = {i for i in ids if re.search(r"(?<![\w-])" + re.escape(i) + r"(?![\w-])", sent)}
                if len(named) != 1:
                    continue
                me = named.pop()
                for num, unit in re.findall(r"(?<![\w-])(\d+(?:\.\d+)?)\s*(%|mmol)(?![\w-])", sent):
                    who = owner.get((_num_token(num), unit), set()) - {me}
                    if who and me not in owner.get((_num_token(num), unit), set()):
                        rep.add("GRD-ATTRIB", "error", "evidence",
                                f"“{num}{unit}” belongs to {', '.join(sorted(who))}, not {me}: {sent[:80]}…",
                                "Fix the number or the compound id — reviewers check this against the SI.")
                        break

    if re.search(r"\b(first|novel|unprecedented)\b", prose, re.I):
        # every novelty claim needs a citation in the same sentence
        for s in sentences(prose):
            if re.search(r"\b(first|novel|unprecedented)\b", s, re.I) and not re.search(r"\[\d+\]|\\cite", s):
                rep.add("GRD-NOVELTY", "warn", "style",
                        f"Novelty claim without a citation: “{s[:90]}…”")
                break


def _walk_paragraphs_all(project: Project):
    for sec in project.sections:
        yield from _walk_paragraphs(sec)


# ---------------------------------------------------------------------------
# Evidence number extraction
# ---------------------------------------------------------------------------


def evidence_number_set(project: Project) -> set[str]:
    """All numbers that legitimately exist in the project's data files."""
    nums: set[str] = set()

    def collect(value):
        for m in re.finditer(r"(?<![\w-])(\d+(?:\.\d+)?)(?![\w-])", str(value)):
            tok = m.group(1)
            nums.add(tok)
            nums.add(tok.rstrip("0").rstrip(".") if "." in tok else tok)

    for c in project.compounds:
        for v in (c.formula, c.mw, c.mmol, c.mass_g, c.yield_percent, c.hrms_calcd,
                  c.hrms_found, c.nmr_1h, c.nmr_13c, c.ir, c.mp, c.alpha_d, c.ccdc, c.purity):
            collect(v)
    for d in project.datasets:
        path = project.path(str(d.get("file", "")))
        if path.exists():
            try:
                text = read_text(path)
                for line in text.splitlines():
                    collect(line)
            except Exception:
                pass
    for f in project.figures:
        if f.source_data:
            p = project.path(f.source_data)
            if p.exists():
                try:
                    collect(read_text(p))
                except Exception:
                    pass
    for t in project.tables:
        if t.file:
            p = project.path(t.file)
            if p.exists():
                try:
                    collect(read_text(p))
                except Exception:
                    pass
    # display-item and compound labels are structural, not claims
    for c in project.compounds:
        for m in re.finditer(r"\d+", c.id):
            nums.add(m.group(0))
    for i in range(1, len(project.figures) + len(project.tables) + 2):
        nums.add(str(i))
    return nums


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def score(report: Report) -> dict:
    cat_scores = {}
    for cat in CATEGORIES:
        issues = report.by(category=cat)
        penalty = sum({"error": 12, "warn": 4, "info": 0.5}[i.severity] for i in issues)
        cat_scores[cat] = max(0.0, round(100 - penalty, 1))
    overall = sum(cat_scores[c] * WEIGHTS[c] for c in CATEGORIES) / sum(WEIGHTS.values())
    blockers = report.critical()
    capped = False
    if blockers and overall > 55:
        overall = 55.0
        capped = True
    overall = round(overall, 1)
    if overall >= 90:
        status = "submission-ready"
    elif overall >= 75:
        status = "minor-fixes"
    elif overall >= 60:
        status = "major-fixes"
    else:
        status = "not-ready"
    return {
        "score": overall, "grade": _grade(overall), "status": status,
        "capped_by_blockers": capped, "blockers": [b.as_dict() for b in blockers],
        "categories": cat_scores, "weights": WEIGHTS,
        "counts": report.counts(),
    }


def _grade(score: float) -> str:
    for cut, g in ((95, "A+"), (90, "A"), (85, "A-"), (80, "B+"), (75, "B"), (70, "B-"),
                   (65, "C+"), (60, "C"), (50, "D"), (0, "F")):
        if score >= cut:
            return g
    return "F"


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def check_project(project: Project, journal: str | None = None, article_type: str | None = None,
                  ref_report=None, offline: bool = True) -> Report:
    from .draft import compose_prose

    from .draft import compose

    prof = journal_profile(journal or project.journal, article_type or project.article_type)
    rep = Report(profile=prof, source=project.title)
    doc = compose(project)
    prose = compose_prose(project)
    narrative = "\n\n".join(
        p["text"] for s in doc.sections
        if not s.heading.lower().startswith(("experimental", "method", "supporting"))
        for p in s.paragraphs if not p["text"].startswith("__SUB__"))
    abstract = project.abstract_text()
    rep.metrics.update({
        "title_words": word_count(project.title),
        "abstract_words": word_count(abstract),
        "keywords": len(project.keywords),
        "sections": len(doc.sections),
        "figures": len([f for f in project.figures if f.kind not in {"toc", "graphical"}]),
        "tables": len(project.tables),
        "compounds": len(project.compounds),
        "references": len(project.references),
    })
    evidence = evidence_number_set(project)
    check_structure(project, prof, rep, abstract, headings=[s.heading for s in doc.sections])
    check_evidence(project, prof, rep, prose, evidence)
    check_references(project, prof, rep, ref_report=ref_report, offline=offline)
    check_figures(project, prof, rep, abstract + "\n" + prose)
    check_journal(project, prof, rep, prose)
    check_ethics(project, prof, rep, prose + "\n" + abstract)
    check_style(project, prof, rep, narrative or prose)
    check_grounding(project, rep, prose + "\n" + abstract, evidence)
    _merge_repeated_info(rep)
    return rep


def _merge_repeated_info(rep: Report):
    """Collapse repeated per-compound informational notes into one line.

    Six organometallic complexes should not produce six copies of "DBE is not
    defined for metals".  Errors and warnings are never merged: each one needs
    its own fix.
    """
    from collections import defaultdict

    groups: dict[str, list] = defaultdict(list)
    keep = []
    for issue in rep.issues:
        (groups[issue.code] if issue.severity == "info" else keep).append(issue)
        if issue.severity != "info":
            continue
    for code, items in groups.items():
        if len(items) <= 2:
            keep.extend(items)
            continue
        subjects = []
        for it in items:
            head = it.message.split(":", 1)[0].strip()
            if head and head not in subjects:
                subjects.append(head)
        body = items[0].message.split(": ", 1)[-1].split(";")[0].strip()
        body = re.sub(r"^[A-Z0-9][A-Za-z0-9]*: ", "", body)
        keep.append(items[0].__class__(
            code, "info", items[0].category,
            f"{len(items)} compounds: {body} ({', '.join(subjects[:10])}"
            f"{'…' if len(subjects) > 10 else ''}).",
            items[0].hint, dict(items[0].data)))
    rep.issues = keep



# ---------------------------------------------------------------------------
# File-level checker: manuscripts that are not PaperForge projects
# ---------------------------------------------------------------------------

def front_matter(raw: str) -> dict:
    """Parse Pandoc/Jekyll YAML front matter (--- … ---) if present."""
    m = re.match(r"^\ufeff?---\s*\n(.*?)\n---\s*(?:\n|$)", raw, re.S)
    if not m:
        return {}
    try:
        import yaml

        data = yaml.safe_load(m.group(1))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def extract_abstract(raw: str) -> str:
    fm = front_matter(raw)
    if fm.get("abstract"):
        return visible_text(str(fm["abstract"]), "x.md")
    m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", raw, re.S)
    if m:
        return visible_text(m.group(1))
    m = re.search(r"(?ims)^#{1,3}\s*abstract\s*$(.*?)(?=^#{1,3}\s|\Z)", raw)
    if m:
        return visible_text(m.group(1), "x.md")
    # plain-text / .docx: a line that is just "Abstract"
    m = re.search(r"(?im)^\s*abstract\s*:?\s*$", raw)
    if m:
        rest = raw[m.end():]
        stop = re.search(r"(?im)^\s*(keywords|graphical abstract|introduction|1\.?\s+introduction)\b.*$", rest)
        chunk = rest[: stop.start()] if stop else rest[:4000]
        return visible_text(chunk)
    m = re.search(r"(?is)^\s*abstract\s*[:.\-—]\s*(.*?)(?:\n\s*\n|\Z)", raw)
    if m:
        return visible_text(m.group(1))
    return ""


def extract_title(raw: str) -> str:
    fm = front_matter(raw)
    if fm.get("title"):
        return str(fm["title"]).strip()
    m = re.search(r"\\title\{((?:[^{}]|\{[^{}]*\})*)\}", raw)
    if m:
        return visible_text(m.group(1))
    m = re.search(r"^#\s+(.+)$", raw, re.M)
    if m:
        return m.group(1).strip()
    for line in raw.splitlines():
        if line.strip() and not line.startswith(("%", "\\documentclass", "---", "title:")):
            return line.strip()
    return ""


def count_references(raw: str) -> int:
    n = len(re.findall(r"\\bibitem", raw))
    if n:
        return n
    n = len(re.findall(r"\\cite[pt]?\{[^}]+\}", raw))
    if n:
        return n
    if re.search(r"(?im)^#{1,4}\s*(references|bibliography)\s*$", raw):
        sec = raw[re.search(r"(?im)^#{1,4}\s*(references|bibliography)\s*$", raw).end():]
        rows = re.findall(r"(?m)^\s*(?:\[?\d+\]?[.)]?|\-|\*)\s+\S", sec)
        return len(rows)
    return 0


def check_file(path: str | Path, journal: str = "Organic Letters", article_type: str = "article",
               offline: bool = True) -> Report:
    """Check a manuscript that is not a structured PaperForge project (.tex/.md/.docx)."""
    prof = journal_profile(journal, article_type)
    rep = Report(profile=prof, source=str(path))
    try:
        raw = read_text(path)
    except Exception as exc:
        rep.add("FILE-READ", "error", "structure", str(exc), critical=True)
        return rep
    text = visible_text(raw, str(path))
    abstract = extract_abstract(raw)
    rep.metrics.update({
        "raw_words": word_count(text), "abstract_words": word_count(abstract),
        "sections": len(re.findall(r"^\s*(?:\\section\{|#{1,3}\s+)", raw, re.M)),
        "references": count_references(raw),
        "figures": len(re.findall(r"\\includegraphics|!\[[^\]]*\]\(", raw)),
        "tables": len(re.findall(r"\\begin\{table", raw)) + len(re.findall(r"^\s*\|.+\|\s*$", raw, re.M)),
    })
    title = extract_title(raw)
    if not title:
        rep.add("STR-TITLE-MISSING", "error", "structure", "No title found.", critical=True)
    else:
        n = word_count(title)
        if n > prof.title_max_words:
            rep.add("STR-TITLE-LONG", "warn", "structure", f"Title is {n} words.")
        hypes = [w for w in HYPE if re.search(rf"\b{re.escape(w)}\b", title, re.I)]
        if hypes:
            rep.add("STR-TITLE-HYPE", "warn", "structure", f"Title contains hype word(s): {hypes}.")
    if abstract and looks_character_spaced(abstract):
        rep.add("STR-ABSTRACT-SPACED", "error", "abstract",
                "The abstract reads as single characters separated by spaces.",
                "An abstract field was probably a string where a list of "
                "sentences was expected; check paper.yaml.", critical=True)
    if not abstract:
        rep.add("STR-ABSTRACT-MISSING", "error", "abstract",
                "No abstract found (checked \\begin{abstract}, ## Abstract and 'Abstract:').", critical=True)
    else:
        n = word_count(abstract)
        if n > prof.limits.abstract_max:
            rep.add("STR-ABSTRACT-LONG", "error", "abstract",
                    f"Abstract is {n} words (limit {prof.limits.abstract_max}).")
        if n < prof.limits.abstract_min:
            rep.add("STR-ABSTRACT-SHORT", "warn", "abstract", f"Abstract is only {n} words.")
        missing = [k for k, ok in abstract_moves(abstract).items() if not ok and k != "context"]
        if missing:
            rep.add("STR-ABSTRACT-MOVES", "warn", "abstract",
                    f"Abstract lacks the {missing} move(s).",
                    "Each move is 1–2 sentences; results must carry numbers and units.")
    # structure: a results section must exist
    if not re.search(r"(?im)^(?:\s*\\section\*?\{|#{1,3}\s*)(results|results and discussion)\b", raw):
        rep.add("STR-RESULTS", "warn", "structure", "No Results section found.")
    # journal limits on the body
    body_words = max(0, word_count(text) - word_count(abstract))
    if prof.limits.body_max_words and body_words > prof.limits.body_max_words:
        rep.add("JNL-BODY-LONG", "error", "journal",
                f"Body is {body_words} words (limit {prof.limits.body_max_words}).")
    if prof.limits.refs_max and rep.metrics["references"] > prof.limits.refs_max:
        rep.add("JNL-REFS-MAX", "error", "journal",
                f"{rep.metrics['references']} references exceed the {prof.limits.refs_max} limit.")
    # references
    dois = re.findall(r"10\.\d{4,9}/[^\s}\"',;]+", raw)
    seen, dups = set(), set()
    for d in dois:
        (dups if d.lower() in seen else seen).add(d.lower())
    if dups:
        rep.add("REF-DUPLICATE", "error", "references", f"Duplicate DOI(s): {sorted(dups)}.")
    if re.search(r"\bet al\.\s*,?\s*and\b", text):
        rep.add("REF-STYLE", "info", "references", "Check 'et al.' usage against the journal style.")
    # figures
    for m in re.finditer(r"\\(?:includegraphics|begin\{figure\})", raw):
        pass
    if rep.metrics["figures"] and not re.search(r"(?i)figure\s+1", text):
        rep.add("FIG-UNCITED", "warn", "figures", "Figures are present but Figure 1 is never cited.")
    # journal/abstract interplay
    if prof.abstract_toc_combined_words and abstract and word_count(abstract) > prof.abstract_toc_combined_words:
        rep.add("STR-ABSTRACT-TOC-COMBINED", "error", "abstract",
                f"Abstract counts {word_count(abstract)} words against a combined "
                f"abstract + TOC limit of {prof.abstract_toc_combined_words}.")
    # ethics
    if "data not shown" in text.lower() or "unpublished data" in text.lower():
        rep.add("STY-DATA-NOT-SHOWN", "error", "style",
                "'Data not shown' / 'unpublished data' is not acceptable — show it or drop the claim.")
    if re.search(r"data (?:are |is )?(?:available )?(?:up)?on request", text, re.I):
        rep.add("ETH-DATA-REQUEST", "error", "ethics",
                "'Data available on request' is not acceptable — deposit the data.", critical=True)
    if not re.search(r"conflict of interest|competing (?:financial )?interest", text, re.I):
        rep.add("ETH-COI", "error", "ethics", "No conflict-of-interest statement found.")
    if not re.search(r"CRediT|author contributions?", text, re.I):
        rep.add("ETH-CREDIT", "warn", "ethics", "No CRediT / author-contribution statement found.")
    if not re.search(r"data availability|data are available", text, re.I):
        rep.add("ETH-DATA", "error", "ethics", "No data-availability statement found.")
    for pat, good, hint in UNIT_ERRORS:
        if re.search(pat, text):
            rep.add("STY-UNIT", "warn", "style", f"Non-standard unit styling ({hint}).")
    st = style_stats(text)
    rep.metrics.update({k: v for k, v in st.items() if k not in rep.metrics})
    if st["mean_sentence_words"] > 32:
        rep.add("STY-SENTENCE-LONG", "warn", "style",
                f"Mean sentence length {st['mean_sentence_words']} words — dense even for chemistry.")
    if re.search(r"[ \t]{2,}", text):
        rep.add("STY-SPACE", "info", "style", "Multiple consecutive spaces in the body text.")
    _merge_repeated_info(rep)
    return rep
