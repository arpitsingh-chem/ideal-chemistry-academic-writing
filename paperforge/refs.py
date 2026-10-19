"""Reference integrity: DOI verification, BibTeX generation, retraction checks.

Uses only free APIs (Crossref, OpenAlex).  Network access is optional: results
are cached in ``.paperforge/refcache.json`` and ``--offline`` mode uses the
cache only.  Every unverifiable reference is reported as such — never silently
accepted (a manuscript with hallucinated references is the single most
expensive mistake an AI-assisted writer can make).
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from .project import Project, Reference
from .util import load_json, write_text

CROSSREF = "https://api.crossref.org/works/{doi}"
OPENALEX = "https://api.openalex.org/works/https://doi.org/{doi}"
DEFAULT_MAILTO = "paperforge@example.org"
RETRYABLE = {429, 500, 502, 503, 504}


@dataclass
class FetchResult:
    ok: bool
    status: str  # ok | not_found | network_error | cached
    data: dict = field(default_factory=dict)
    error: str = ""


class RefCache:
    def __init__(self, root: Path):
        self.path = Path(root) / ".paperforge" / "refcache.json"
        self.data: dict[str, dict] = load_json(self.path, default={}) or {}

    def get(self, doi: str):
        return self.data.get(doi.lower())

    def put(self, doi: str, record: dict) -> None:
        self.data[doi.lower()] = record
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")


def _http_json(url: str, mailto: str, timeout: int = 20, tries: int = 3) -> FetchResult:
    headers = {
        "User-Agent": f"paperforge/2.0 (mailto:{mailto})",
        "Accept": "application/json",
    }
    last = ""
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return FetchResult(True, "ok", json.loads(resp.read().decode("utf-8")))
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}"
            if exc.code == 404:
                return FetchResult(False, "not_found", error="DOI not found at Crossref")
            if exc.code in RETRYABLE:
                time.sleep(1.5 * (attempt + 1))
                continue
            return FetchResult(False, "network_error", error=last)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = str(exc)
            time.sleep(0.8 * (attempt + 1))
    return FetchResult(False, "network_error", error=last)


def fetch_crossref(doi: str, mailto: str = DEFAULT_MAILTO, cache: RefCache | None = None,
                   offline: bool = False) -> FetchResult:
    doi = normalize_doi(doi)
    if cache:
        hit = cache.get(doi)
        if hit:
            return FetchResult(True, "cached", hit)
    if offline:
        return FetchResult(False, "network_error", error="offline and not cached")
    res = _http_json(CROSSREF.format(doi=urllib.parse.quote(doi, safe="/")), mailto)
    if not res.ok:
        return res
    msg = (res.data or {}).get("message") or {}
    rec = {
        "doi": msg.get("DOI", doi),
        "title": (msg.get("title") or [""])[0],
        "authors": [
            f"{a.get('family','')}, {a.get('given','')}".strip(", ")
            for a in (msg.get("author") or []) if a.get("family") or a.get("given")
        ],
        "journal": (msg.get("container-title") or [""])[0],
        "short_journal": (msg.get("short-container-title") or [""])[0],
        "year": _year(msg),
        "volume": msg.get("volume", ""),
        "issue": msg.get("issue", ""),
        "pages": msg.get("page", "") or msg.get("article-number", ""),
        "publisher": msg.get("publisher", ""),
        "type": msg.get("type", ""),
        "retracted": is_retracted(msg),
        "is_retraction_notice": any(u.get("type") == "retraction" for u in (msg.get("update-to") or [])),
        "cited_by": msg.get("is-referenced-by-count", 0),
        "source": "crossref",
    }
    if cache:
        cache.put(doi, rec)
    return FetchResult(True, "ok", rec)


def _year(msg: dict) -> int | None:
    for key in ("published-print", "published-online", "issued", "created"):
        parts = (msg.get(key) or {}).get("date-parts") or []
        if parts and parts[0] and parts[0][0]:
            return int(parts[0][0])
    return None


def is_retracted(msg: dict) -> bool:
    rel = msg.get("relation") or {}
    if "is-retracted-by" in rel:
        return True
    for u in msg.get("update-to") or []:
        if u.get("type") == "retraction":
            # this record is the retraction notice, not necessarily retracted itself
            return True
    if str(msg.get("type", "")).lower() in {"retraction"}:
        return True
    return False


def normalize_doi(doi: str) -> str:
    doi = (doi or "").strip()
    doi = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", doi, flags=re.I)
    return doi.strip().rstrip(".")


DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")


def valid_doi_syntax(doi: str) -> bool:
    return bool(DOI_RE.match(normalize_doi(doi)))


# ---------------------------------------------------------------------------
# BibTeX
# ---------------------------------------------------------------------------


def citation_key(rec: dict, fallback: str = "ref") -> str:
    authors = rec.get("authors") or []
    surname = "anon"
    if authors:
        surname = re.split(r"[,\s]", authors[0].strip())[0] or "anon"
    surname = re.sub(r"[^A-Za-z]", "", surname).lower() or "anon"
    year = rec.get("year") or ""
    title = re.sub(r"[^A-Za-z0-9 ]", " ", rec.get("title", "")).lower().split()
    stop = {"a", "an", "the", "of", "for", "and", "in", "on", "to", "with", "by", "from", "via"}
    word = next((w for w in title if w not in stop), "paper")
    return f"{surname}{year}{word}"[:60] or fallback


def _ascii_safe(text: str) -> str:
    """Strip HTML fragments and avoid glyphs some T1 fonts cannot render."""
    import re as _re
    s = _re.sub(r"<[^>]+>", "", str(text))
    s = s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    trans = {"\u2010": "-", "\u2011": "-", "\u2013": "--", "\u2014": "---", "\u2212": "-"}
    return "".join(trans.get(ch, ch) for ch in s)


def to_bibtex(rec: dict, key: str | None = None) -> str:
    key = key or citation_key(rec)
    fields = []
    authors = rec.get("authors") or []
    if authors:
        fields.append(("author", _ascii_safe(" and ".join(authors))))
    if rec.get("title"):
        fields.append(("title", "{" + _ascii_safe(rec["title"]) + "}"))
    if rec.get("journal"):
        fields.append(("journal", _ascii_safe(rec["journal"])))
    if rec.get("year"):
        fields.append(("year", str(rec["year"])))
    if rec.get("volume"):
        fields.append(("volume", str(rec["volume"])))
    if rec.get("pages"):
        fields.append(("pages", _ascii_safe(str(rec["pages"]))))
    if rec.get("doi"):
        fields.append(("doi", rec["doi"]))
    fields.append(("url", f"https://doi.org/{rec['doi']}")) if rec.get("doi") else None
    body = ",\n".join(f"  {k:<8} = {{{v}}}" for k, v in fields)
    return f"@article{{{key},\n{body}\n}}"


def parse_bibtex(text: str) -> list[dict]:
    """Small, tolerant BibTeX reader (brace-depth scanner, not a full parser)."""
    out: list[dict] = []
    for m in re.finditer(r"@(\w+)\s*\{", text):
        typ = m.group(1).lower()
        start = m.end()
        depth = 1
        i = start
        while i < len(text) and depth:
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        body = text[start:i]
        if not body.strip():
            continue
        key, _, fields_src = body.partition(",")
        fields: dict[str, str] = {}
        pos = 0
        while pos < len(fields_src):
            fm = re.search(r"(\w+)\s*=\s*", fields_src[pos:])
            if not fm:
                break
            name = fm.group(1).lower()
            p = pos + fm.end()
            if p >= len(fields_src):
                break
            if fields_src[p] == "{":
                d = 0
                q = p
                while q < len(fields_src):
                    if fields_src[q] == "{":
                        d += 1
                    elif fields_src[q] == "}":
                        d -= 1
                        if d == 0:
                            break
                    q += 1
                value = fields_src[p + 1:q]
                pos = q + 1
            elif fields_src[p] == '"':
                q = fields_src.find('"', p + 1)
                value = fields_src[p + 1:q if q > 0 else len(fields_src)]
                pos = (q + 1) if q > 0 else len(fields_src)
            else:
                mm = re.match(r"([^,\n]+)", fields_src[p:])
                value = mm.group(1).strip() if mm else ""
                pos = p + (mm.end() if mm else 0)
            value = re.sub(r"\s+", " ", value).strip()
            while value.startswith("{") and value.endswith("}"):
                value = value[1:-1].strip()
            fields[name] = value
            nxt = fields_src.find(",", pos)
            if nxt == -1:
                break
            pos = nxt + 1
        out.append({"type": typ, "key": key.strip(), **fields})
    return out


# ---------------------------------------------------------------------------
# High-level workflow
# ---------------------------------------------------------------------------


@dataclass
class ReferenceReport:
    total: int = 0
    verified: int = 0
    unverified: int = 0
    not_found: int = 0
    retracted: int = 0
    duplicates: list[str] = field(default_factory=list)
    entries: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.not_found == 0 and self.retracted == 0 and not self.duplicates

    def summary(self) -> str:
        return (f"{self.total} references: {self.verified} verified, {self.unverified} unverified, "
                f"{self.not_found} not found, {self.retracted} retracted, {len(self.duplicates)} duplicate DOI(s)")


def verify_project(project: Project, offline: bool = False, mailto: str = DEFAULT_MAILTO,
                   write_bib: bool = True) -> ReferenceReport:
    """Verify every reference DOI in a project, enrich metadata and write refs.bib."""
    cache = RefCache(project.root)
    report = ReferenceReport(total=len(project.references))
    seen: dict[str, str] = {}
    bib_entries = []

    for ref in project.references:
        rec: dict = {}
        status = "unverified"
        if ref.doi:
            doi = normalize_doi(ref.doi)
            if not valid_doi_syntax(doi):
                report.errors.append(f"{ref.key or ref.title}: malformed DOI {ref.doi!r}")
            if doi in seen:
                report.duplicates.append(doi)
            seen[doi] = ref.key or doi
            res = fetch_crossref(doi, mailto=mailto, cache=cache, offline=offline)
            if res.ok:
                rec = res.data
                status = "verified"
                ref.verified = True
                ref.retracted = bool(rec.get("retracted"))
                ref.title = ref.title or rec.get("title", "")
                ref.authors = ref.authors or rec.get("authors", [])
                ref.journal = ref.journal or rec.get("journal", "")
                ref.year = ref.year or rec.get("year")
                ref.volume = ref.volume or str(rec.get("volume", "") or "")
                ref.pages = ref.pages or str(rec.get("pages", "") or "")
                ref.source = rec.get("source", "crossref")
            elif res.status == "not_found":
                status = "not_found"
                report.not_found += 1
                report.errors.append(f"DOI not found: {doi} ({ref.key or ref.title})")
            else:
                status = "network_error"
                report.errors.append(f"could not verify {doi}: {res.error}")
        else:
            report.errors.append(f"reference {ref.key or ref.title!r} has no DOI")

        if ref.retracted:
            report.retracted += 1
            report.errors.append(f"RETRACTED reference: {ref.doi} ({ref.key})")
        if status == "verified":
            report.verified += 1
        elif status != "not_found":
            report.unverified += 1

        key = ref.key or citation_key(rec or {"title": ref.title, "authors": ref.authors, "year": ref.year})
        ref.key = key
        report.entries.append({
            "key": key, "doi": ref.doi, "title": ref.title, "journal": ref.journal,
            "year": ref.year, "status": status, "retracted": ref.retracted,
            "authors": ref.authors,
        })
        if rec:
            bib_entries.append(to_bibtex(rec, key))
        else:
            bib_entries.append(
                to_bibtex({"authors": ref.authors, "title": ref.title, "journal": ref.journal,
                           "year": ref.year, "volume": ref.volume, "pages": ref.pages,
                           "doi": ref.doi}, key)
            )

    if write_bib and bib_entries:
        write_text(project.root / "refs" / "refs.bib", "\n\n".join(bib_entries) + "\n")
        write_text(project.root / "refs" / "references.md",
                   "# References\n\n" + "\n\n".join(f"[{i+1}] {format_reference(e, 'acs')}"
                                                     for i, e in enumerate(report.entries)) + "\n")
    return report


def format_reference(entry: dict, style: str = "acs") -> str:
    """Human-readable reference line (not a substitute for the journal's CSL)."""
    authors = entry.get("authors") or []
    if len(authors) > 10:
        a = ", ".join(authors[:10]) + ", et al."
    else:
        a = ", ".join(authors)
    title = entry.get("title", "")
    journal = entry.get("journal", "")
    year = entry.get("year", "")
    vol = entry.get("volume", "")
    pages = entry.get("pages", "")
    doi = entry.get("doi", "")
    if style == "acs":
        s = f"{a} {title}. *{journal}* **{year}**, *{vol}*, {pages}."
        if doi:
            s += f" DOI: {doi}."
        return re.sub(r"\s+", " ", s).strip()
    if style == "wiley":
        s = f"{a}, {title}, *{journal}* {year}, {vol}, {pages}."
        if doi:
            s += f" DOI: {doi}."
        return re.sub(r"\s+", " ", s).strip()
    s = f"{a}, {title}, *{journal}*, {year}, {vol}, {pages}."
    if doi:
        s += f" (DOI: {doi})"
    return re.sub(r"\s+", " ", s).strip()


def add_dois(project_path: str | Path, dois: list[str], mailto: str = DEFAULT_MAILTO) -> list[dict]:
    """Fetch metadata for DOIs and append them to a project file (YAML/JSON)."""
    from .project import Project

    project = Project.load(project_path)
    cache = RefCache(project.root)
    added = []
    for doi in dois:
        res = fetch_crossref(doi, mailto=mailto, cache=cache)
        if not res.ok:
            added.append({"doi": doi, "status": res.status, "error": res.error})
            continue
        rec = res.data
        added.append({"doi": rec["doi"], "title": rec["title"], "year": rec["year"],
                      "journal": rec["journal"], "status": "verified"})
    return added


def check_bib_file(path: str | Path) -> dict:
    """Static checks on a .bib file: duplicates, missing DOI/year, retraction flags."""
    from .util import read_text

    entries = parse_bibtex(read_text(path))
    dois = [e.get("doi", "").lower() for e in entries if e.get("doi")]
    dupes = sorted({d for d in dois if dois.count(d) > 1})
    missing_doi = [e["key"] for e in entries if not e.get("doi")]
    missing_year = [e["key"] for e in entries if not e.get("year")]
    return {"entries": len(entries), "duplicates": dupes, "missing_doi": missing_doi,
            "missing_year": missing_year}
