"""Journal database, submission profiles and data-driven journal matching.

The matcher is trained on the real publication corpus shipped in
``data/publications-openalex.json`` (1,616 works by IISER Bhopal chemistry
faculty, 2009-2026): each journal is a TF-IDF document built from the titles
and abstracts of papers that department members actually published there.
That makes recommendations evidence-based instead of keyword-guessing.
"""
from __future__ import annotations

import csv
import difflib
import json
import math
import re
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path

from .util import load_json

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
JOURNALS_CSV = DATA / "journals.csv"
LIMITS_JSON = DATA / "journal_limits.json"
CORPUS_JSON = DATA / "publications-openalex.json"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArticleLimits:
    abstract_min: int = 0
    abstract_max: int = 300
    body_max_words: int | None = None
    refs_max: int | None = None
    figures_max: int | None = None
    printed_pages: int | None = None


@dataclass(frozen=True)
class JournalProfile:
    journal: str
    family: str
    publisher: str
    article_type: str
    limits: ArticleLimits
    keywords_min: int = 0
    keywords_max: int = 8
    title_max_words: int = 20
    abstract_forbids_citations: bool = True
    abstract_forbids_compound_numbers: bool = False
    abstract_toc_combined_words: int | None = None
    toc_required: bool = False
    toc_in_manuscript: bool = False
    toc_width_cm: float | None = None
    toc_height_cm: float | None = None
    toc_text_max_chars: int | None = None
    toc_dpi: int = 300
    highlights_required: bool = False
    cover_letter_required: bool = True
    data_statement_required: bool = True
    ai_disclosure_required: str = "recommended"
    credit_required: bool = True
    orcid_required: str = "corresponding"
    verified: bool = False
    source: str = ""
    notes: list[str] = field(default_factory=list)

    def article_types(self) -> list[str]:
        lim = _limits()
        override = ((lim.get("journals") or {}).get(self.journal, {}) or {}).get("article_types")
        if override:
            return list(override)
        fam = (lim.get("_families") or {}).get(self.family) or lim.get("_generic") or {}
        return list((fam.get("article_types") or {"article": {}}).keys())

    def as_dict(self) -> dict:
        d = {
            "journal": self.journal, "family": self.family, "publisher": self.publisher,
            "article_type": self.article_type, "limits": self.limits.__dict__,
            "keywords": [self.keywords_min, self.keywords_max],
            "title_max_words": self.title_max_words,
            "toc": {"required": self.toc_required, "in_manuscript": self.toc_in_manuscript,
                     "width_cm": self.toc_width_cm, "height_cm": self.toc_height_cm,
                     "text_max_chars": self.toc_text_max_chars, "dpi": self.toc_dpi},
            "highlights_required": self.highlights_required,
            "cover_letter_required": self.cover_letter_required,
            "data_statement_required": self.data_statement_required,
            "ai_disclosure": self.ai_disclosure_required,
            "credit_required": self.credit_required,
            "orcid": self.orcid_required,
            "verified": self.verified, "source": self.source, "notes": self.notes,
        }
        return d


# ---------------------------------------------------------------------------
# Database access
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def journals() -> list[dict]:
    if not JOURNALS_CSV.exists():
        return []
    with JOURNALS_CSV.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@lru_cache(maxsize=1)
def _limits() -> dict:
    if not LIMITS_JSON.exists():
        return {"_families": {}, "_generic": {}, "journals": {}}
    return json.loads(LIMITS_JSON.read_text(encoding="utf-8"))


def journal_names() -> list[str]:
    return [r["journal"] for r in journals()]


def resolve(name: str) -> dict:
    """Resolve a journal name / alias / abbreviation to a database row."""
    if not name:
        raise KeyError("journal name is empty")
    rows = journals()
    by_name = {r["journal"].lower(): r for r in rows}
    key = name.strip().lower()
    if key in by_name:
        return by_name[key]
    for r in rows:
        aliases = [a.strip().lower() for a in (r.get("aliases") or "").split(";") if a.strip()]
        if key in aliases:
            return r

    def norm(s: str) -> str:
        s = s.lower().replace("&", "and")
        s = re.sub(r"\b(the|journal|of|and|for|chemistry)\b", " ", s)
        return re.sub(r"[^a-z0-9]+", "", s)

    nkey = norm(name)
    for r in rows:
        if norm(r["journal"]) == nkey:
            return r
        for a in (r.get("aliases") or "").split(";"):
            if a.strip() and norm(a) == nkey:
                return r
    matches = difflib.get_close_matches(name, [r["journal"] for r in rows], n=3, cutoff=0.75)
    if matches:
        # only accept a near-match when it is not wildly shorter than the query
        cand = by_name[matches[0].lower()]
        if abs(len(norm(cand["journal"])) - len(nkey)) <= max(8, 0.35 * len(nkey)):
            return cand
    raise KeyError(f"unknown journal {name!r}. Try `paperforge journals search {name!r}`.")


def search(query: str, top: int = 15) -> list[dict]:
    q = query.lower()
    rows = [r for r in journals() if q in r["journal"].lower() or q in (r.get("aliases") or "").lower()]
    return rows[:top]


def profile(journal: str, article_type: str | None = None) -> JournalProfile:
    """Build the effective submission profile for a journal + article type."""
    lim = _limits()
    row = resolve(journal) if journal else {"journal": journal or "Generic journal", "family": "other"}
    jname = row["journal"]
    override = dict((lim.get("journals") or {}).get(jname, {}))
    family = override.get("family") or row.get("family") or "other"
    fam = dict((lim.get("_families") or {}).get(family) or lim.get("_generic") or {})

    # Journal-specific types override the family typology; exclusive journals
    # (e.g. Organic Letters, which publishes only Letters) replace it entirely.
    if override.get("article_types"):
        if override.get("exclusive_types"):
            types = dict(override["article_types"])
        else:
            types = dict(fam.get("article_types") or {})
            types.update(override["article_types"])
    else:
        types = dict(fam.get("article_types") or {})
    if not types:
        types = {"article": {}}
    aliases = {
        "paper": "article", "full paper": "article", "research article": "article",
        "full-length article": "article", "letter": "communication", "edge article": "article",
        "minireview": "review", "perspective": "review",
    }
    at = (article_type or fam.get("default_article_type") or "article").lower()
    ov_types = override.get("article_types") or {}
    if ov_types:
        # Prefer a synonym that the journal itself declares (JACS "letter" -> "communication").
        if at not in ov_types:
            cand = aliases.get(at, at)
            if cand in ov_types:
                at = cand
            elif at not in types:
                at = cand if cand in types else next(iter(types))
    else:
        if at not in types:
            at = aliases.get(at, at)
        if at not in types:
            at = next(iter(types))
    t = dict(types.get(at, {}))
    limits = ArticleLimits(
        abstract_min=int(t.get("abstract_min", 0) or 0),
        abstract_max=int(t.get("abstract_max", 300)),
        body_max_words=t.get("body_max_words"),
        refs_max=t.get("refs_max"),
        figures_max=t.get("figures_max"),
        printed_pages=t.get("printed_pages"),
    )

    def pick(key, default=None):
        if key in override:
            return override[key]
        return fam.get(key, default)

    notes = []
    if not override.get("verified"):
        notes.append("Limits are publisher-family defaults; confirm on the journal's official guidelines page.")
    if override.get("abstract_toc_combined_words"):
        notes.append(
            f"{jname} counts the abstract and TOC graphic together (limit "
            f"{override['abstract_toc_combined_words']} words)."
        )

    return JournalProfile(
        journal=jname,
        family=family,
        publisher=row.get("publisher") or fam.get("publisher", ""),
        article_type=at,
        limits=limits,
        keywords_min=int(pick("keywords_min", 0) or 0),
        keywords_max=int(pick("keywords_max", 8) or 8),
        title_max_words=int(pick("title_max_words", 20) or 20),
        abstract_forbids_citations=bool(pick("abstract_forbids_citations", True)),
        abstract_forbids_compound_numbers=bool(pick("abstract_forbids_compound_numbers", False)),
        abstract_toc_combined_words=override.get("abstract_toc_combined_words"),
        toc_required=bool(pick("toc_required", False)),
        toc_in_manuscript=bool(pick("toc_in_manuscript", False)),
        toc_width_cm=pick("toc_width_cm"),
        toc_height_cm=pick("toc_height_cm"),
        toc_text_max_chars=pick("toc_text_max_chars"),
        toc_dpi=int(pick("toc_dpi", 300) or 300),
        highlights_required=bool(pick("highlights_required", False)),
        cover_letter_required=bool(pick("cover_letter_required", True)),
        data_statement_required=bool(pick("data_statement_required", True)),
        ai_disclosure_required=str(pick("ai_disclosure_required", "recommended")),
        credit_required=bool(pick("credit_required", True)),
        orcid_required=str(pick("orcid_required", "corresponding")),
        verified=bool(override.get("verified", False)),
        source=override.get("source", "") or row.get("url", ""),
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Data-driven matching
# ---------------------------------------------------------------------------

_TOKEN = re.compile(r"[a-z][a-z\-]{2,}")
_STOP = set("""the and for with from that this are was were has have had not but can may
their there these those which while where into than then they using used use such also more
most other upon within without between under over after before during among through because
although however therefore thus herein here our we study studies report reported new novel
first two three four one highly respectively significantly based been being both each also
shows show shown via toward towards its it is of in on to a an as at by or""".split())


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]


@lru_cache(maxsize=1)
def _corpus() -> list[dict]:
    if not CORPUS_JSON.exists():
        return []
    return json.loads(CORPUS_JSON.read_text(encoding="utf-8"))


class Matcher:
    """Similarity between a described study and journals, using per-paper vectors.

    Each of the department's papers is a TF-IDF vector.  A journal's score is
    the mean similarity of the *k* closest papers it published on the topic,
    blended with how often the department publishes there.  Per-paper scoring
    (rather than concatenating a journal into one document) stops small
    journals from being flattered by document-length effects.
    """

    TOP_K = 3

    def __init__(self) -> None:
        self._build()

    def _build(self) -> None:
        papers: list[tuple[str, dict[str, float]]] = []
        df: dict[str, int] = {}
        tokenised: list[tuple[str, dict[str, float]]] = []
        for rec in _corpus():
            j = rec.get("journal")
            if not j or j == "Unknown":
                continue
            text = " ".join(filter(None, [rec.get("title"), (rec.get("abstract") or "")[:900]]))
            toks = _tokens(text)
            if len(toks) < 4:
                continue
            tf: dict[str, float] = {}
            for t in toks:
                tf[t] = tf.get(t, 0.0) + 1.0
            tokenised.append((j, tf))
            for t in tf:
                df[t] = df.get(t, 0) + 1
        n = max(1, len(tokenised))
        self.idf = {t: math.log((1 + n) / (1 + c)) + 1.0 for t, c in df.items()}
        for j, tf in tokenised:
            vec = {t: (1 + math.log(c)) * self.idf[t] for t, c in tf.items()}
            norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
            papers.append((j, {t: v / norm for t, v in vec.items()}))
        self.papers = papers
        self.by_journal: dict[str, list[dict[str, float]]] = {}
        for j, vec in papers:
            self.by_journal.setdefault(j, []).append(vec)
        self.counts = {j: len(v) for j, v in self.by_journal.items()}

    def query_vector(self, text: str) -> dict[str, float]:
        toks = _tokens(text)
        tf: dict[str, float] = {}
        for t in toks:
            tf[t] = tf.get(t, 0.0) + 1.0
        vec = {t: (1 + math.log(c)) * self.idf.get(t, math.log(1 + len(self.papers))) for t, c in tf.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {t: v / norm for t, v in vec.items()}

    def recommend(self, text: str, top: int = 10, family: str | None = None,
                  min_papers: int = 2, include_flagships: bool = True,
                  exclude_preprints: bool = True) -> list[dict]:
        q = self.query_vector(text)
        rows = {r["journal"]: r for r in journals()}
        scores = []
        for j, vecs in self.by_journal.items():
            fam = rows.get(j, {}).get("family")
            if family and fam != family:
                continue
            if exclude_preprints and fam == "preprint":
                continue
            if len(vecs) < min_papers:
                continue
            paired = []
            for vec in vecs:
                if len(vec) > len(q):
                    small, big = q, vec
                else:
                    small, big = vec, q
                sim = sum(v * big.get(t, 0.0) for t, v in small.items())
                paired.append((sim, vec))
            paired.sort(key=lambda x: -x[0])
            k = min(self.TOP_K, len(paired))
            best = sum(sim for sim, _ in paired[:k]) / k
            if best <= 0:
                continue
            top_vecs = [vec for _, vec in paired[:k]]
            matched = sorted(((q[t], t) for t in q if any(t in vec for vec in top_vecs)),
                             reverse=True)[:6]
            scores.append({
                "journal": j, "score": 0.0, "similarity": round(best, 4),
                "papers": len(vecs), "family": fam or "",
                "publisher": rows.get(j, {}).get("publisher", ""),
                "matched_terms": [t for _, t in matched],
                "nearest_papers": k,
            })
        if include_flagships:
            for j, r in rows.items():
                if j in self.by_journal or not r.get("scope_terms"):
                    continue
                terms = [t.strip() for t in r["scope_terms"].split(";") if t.strip()]
                if not terms:
                    continue
                overlap = {t for t in terms if t in q}
                if overlap:
                    scores.append({
                        "journal": j, "score": 0.0, "similarity": 0.0,
                        "papers": int(r.get("papers") or 0),
                        "family": r.get("family", ""), "publisher": r.get("publisher", ""),
                        "matched_terms": sorted(overlap), "nearest_papers": 0,
                    })
        NON_VENUES = {"ChemInform", "Unknown", "Elsevier eBooks", "SSRN Electronic Journal"}
        scores = [d for d in scores if d["journal"] not in NON_VENUES]
        if not scores:
            return []
        max_sim = max(d["similarity"] for d in scores) or 1.0
        max_p = max(d["papers"] for d in scores) or 1
        for d in scores:
            sim_part = d["similarity"] / max_sim
            freq_part = math.log1p(d["papers"]) / math.log1p(max_p)
            d["score"] = round(100 * (0.78 * sim_part + 0.22 * freq_part), 1)
            if d["papers"] < 3:
                d["score"] = round(d["score"] * 0.75, 1)
        scores.sort(key=lambda d: (-d["score"], -d["papers"], d["journal"]))
        return scores[:top]


def retarget(source: JournalProfile, target: JournalProfile, metrics: dict) -> list[dict]:
    """Report what must change when moving a manuscript between journals."""
    out = []

    def add(item, now, limit, action, hard=True):
        if limit is None:
            return
        status = "pass" if (now <= limit) else ("fail" if hard else "warn")
        out.append({"item": item, "current": now, "target_limit": limit, "status": status,
                    "action": action if status != "pass" else ""})

    add("abstract words", metrics.get("abstract_words", 0), target.limits.abstract_max,
        f"cut the abstract to ≤{target.limits.abstract_max} words")
    add("body words", metrics.get("body_words", 0), target.limits.body_max_words,
        f"cut ~{max(0, metrics.get('body_words', 0) - (target.limits.body_max_words or 0))} words "
        f"(move detail to the SI)")
    add("references", metrics.get("references", 0), target.limits.refs_max,
        f"reduce to ≤{target.limits.refs_max} references")
    add("display items", metrics.get("figures", 0), target.limits.figures_max,
        f"move {max(0, metrics.get('figures', 0) - (target.limits.figures_max or 0))} figure(s) to the SI")
    if target.highlights_required and not source.highlights_required:
        out.append({"item": "highlights", "current": 0, "target_limit": 5, "status": "fail",
                    "action": "add 3–5 highlights (≤85 characters each)"})
    if target.toc_required and (target.toc_width_cm, target.toc_height_cm) != (source.toc_width_cm, source.toc_height_cm):
        out.append({"item": "TOC graphic", "current": f"{source.toc_width_cm}×{source.toc_height_cm} cm",
                    "target_limit": f"{target.toc_width_cm}×{target.toc_height_cm} cm", "status": "fail",
                    "action": "re-render the TOC graphic at the new size/aspect ratio"})
    if target.abstract_forbids_compound_numbers and not source.abstract_forbids_compound_numbers:
        out.append({"item": "compound numbers in abstract", "current": "allowed", "target_limit": "forbidden",
                    "status": "warn", "action": "replace compound numbers with names in the abstract"})
    return out


def metrics_from_text(text: str) -> dict:
    """Quick metrics for retargeting decisions."""
    from .util import visible_text, word_count

    vis = visible_text(text)
    return {"abstract_words": word_count(vis), "body_words": word_count(vis), "references": 0, "figures": 0}
