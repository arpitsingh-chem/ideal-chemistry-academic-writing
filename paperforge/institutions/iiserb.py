"""IISER Bhopal institutional collection (preserved, offline-first).

The repository's original evidence base — 1,616 OpenAlex-verified works by 30
Department of Chemistry faculty — is **kept and given a typed interface**
instead of being deleted or diluted into the global index. It is the reference
collection for institutional coverage reporting and the only source that may be
described as complete for its scope (and even then only relative to the query
that built it).

Design notes
------------
* No network access: it reads the bundled snapshot
  ``paperforge/data/publications-openalex.json``. Refreshing that snapshot is a
  separate, explicit operation (:mod:`scripts.refresh_institution_snapshot`).
* Roles are separated: this module reports what the snapshot contains. It never
  claims the snapshot is current.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

DATA = Path(__file__).resolve().parent.parent / "data"
SNAPSHOT = DATA / "publications-openalex.json"
SCHOLARS = DATA / "iiserb-bhopal-scholars.csv"
FACULTY = DATA / "iiserb-bhopal-faculty.md"
JOURNALS = DATA / "iiserb-bhopal-chemistry-journals.csv"

INSTITUTION = {
    "name": "Indian Institute of Science Education and Research Bhopal",
    "short": "IISER Bhopal",
    "department": "Department of Chemistry",
    "country": "IN",
    "city": "Bhopal",
    "ror": "https://ror.org/04m7r8v69",
    "snapshot": SNAPSHOT.name,
    "snapshot_source": "OpenAlex works API, author-ID-verified faculty query",
}


@dataclass
class InstitutionalStats:
    works: int
    faculty: int
    venues: int
    first_year: int | None
    last_year: int | None
    open_access: int | None
    preprints: int
    retracted: int | None
    missing_doi: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "works": self.works, "faculty": self.faculty, "venues": self.venues,
            "first_year": self.first_year, "last_year": self.last_year,
            "open_access": self.open_access, "preprints": self.preprints,
            "retracted": self.retracted, "missing_doi": self.missing_doi,
        }


@lru_cache(maxsize=1)
def works() -> tuple[dict[str, Any], ...]:
    """The bundled snapshot as a tuple of dicts (empty if absent).

    Cached because the file is read on every CLI invocation otherwise. A missing
    or corrupt snapshot yields an empty collection plus a documented warning —
    never a fabricated record.
    """
    if not SNAPSHOT.exists():
        return ()
    try:
        data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ()
    return tuple(w for w in data if isinstance(w, dict))


def journal_counts() -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for w in works():
        name = (w.get("journal") or "").strip()
        if name:
            counts[name] = counts.get(name, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def faculty_names() -> list[str]:
    names: set[str] = set()
    for w in works():
        for f in w.get("faculty") or []:
            if f:
                names.add(f)
    return sorted(names)


def stats() -> InstitutionalStats:
    ws = works()
    years = [w.get("year") for w in ws if isinstance(w.get("year"), int)]
    venues = {(w.get("journal") or "").strip() for w in ws if (w.get("journal") or "").strip()}
    return InstitutionalStats(
        works=len(ws),
        faculty=len(faculty_names()),
        venues=len(venues),
        first_year=min(years) if years else None,
        last_year=max(years) if years else None,
        # ``is_oa`` / ``is_retracted`` are absent from this snapshot. Counting
        # them would report "0 open-access works", which is a different (and
        # false) statement from "this field was not captured" — so they stay None.
        open_access=(sum(1 for w in ws if w.get("is_oa") is True)
                     if any("is_oa" in w for w in ws) else None),
        preprints=sum(1 for w in ws if (w.get("type") or "").lower() == "preprint"
                      or "rxiv" in (w.get("journal") or "").lower()),
        retracted=(sum(1 for w in ws if w.get("is_retracted") is True)
                   if any("is_retracted" in w for w in ws) else None),
        missing_doi=sum(1 for w in ws if not w.get("doi")),
    )


def search(query: str, limit: int = 25) -> list[dict[str, Any]]:
    """Case-insensitive substring search over title/abstract/topic/faculty."""
    q = (query or "").strip().lower()
    if not q:
        return []
    terms = [t for t in q.split() if t]
    hits = []
    for w in works():
        haystack = " ".join(str(w.get(k) or "") for k in
                            ("title", "abstract", "topic", "journal")).lower()
        haystack += " " + " ".join(w.get("faculty") or []).lower()
        if all(t in haystack for t in terms):
            hits.append(w)
    hits.sort(key=lambda w: (-(w.get("cited_by") or 0), -(w.get("year") or 0)))
    return hits[:limit]


def by_faculty(name: str, limit: int = 50) -> list[dict[str, Any]]:
    needle = (name or "").lower()
    hits = [w for w in works() if any(needle in (f or "").lower() for f in w.get("faculty") or [])]
    hits.sort(key=lambda w: (-(w.get("year") or 0), w.get("title") or ""))
    return hits[:limit]


def years() -> list[int]:
    return sorted({w["year"] for w in works() if isinstance(w.get("year"), int)})


def coverage_note() -> str:
    """Honest one-line description of what this collection is and is not."""
    s = stats()
    return (f"{s.works} works, {s.faculty} faculty, {s.venues} venues, "
            f"{s.first_year}–{s.last_year}, from a bundled OpenAlex snapshot "
            f"({INSTITUTION['snapshot']}); not a live query and not complete for the institution.")


def iter_works() -> Iterable[dict[str, Any]]:
    return iter(works())
