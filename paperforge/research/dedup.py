"""Deduplication and reconciliation.

The rule this module exists to enforce: **similar titles are not identity.**
A merge happens only when an identifier agrees, or when several independent
signals agree *and* nothing contradicts them. Every decision is recorded with
its reasons, so a librarian can audit (or reverse) it.

Verdicts
--------
``SAME``
    The two records describe the same bibliographic entity.
``RELATED_VERSION``
    Same work, different *version* (preprint vs version of record, correction,
    conference abstract). These are linked, never merged: the preprint and the
    published paper have different DOIs, licences and citation counts.
``DISTINCT``
    Different works, even if titles collide.

Scoring is deliberately transparent — a weighted sum of named signals, printed
in the decision — rather than a trained model with no explanation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import Enum
from typing import Any, Iterable

from .schema import (PeerReview, VersionType, WorkRecord, normalise_doi,
                     normalise_title)


class Verdict(str, Enum):
    SAME = "same"
    RELATED_VERSION = "related_version"
    DISTINCT = "distinct"


@dataclass
class Signal:
    name: str
    weight: float
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "weight": self.weight, "detail": self.detail}


@dataclass
class MatchDecision:
    verdict: Verdict
    score: float
    reasons: list[Signal] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)

    @property
    def merge(self) -> bool:
        return self.verdict is Verdict.SAME

    def explain(self) -> str:
        head = f"{self.verdict.value} (score {self.score:.2f})"
        bits = [f"+{s.name}:{s.detail}" for s in self.reasons]
        bits += [f"-{c}" for c in self.conflicts]
        return head + (" | " + "; ".join(bits) if bits else "")

    def as_dict(self) -> dict[str, Any]:
        return {"verdict": self.verdict.value, "score": round(self.score, 4),
                "merge": self.merge, "reasons": [r.as_dict() for r in self.reasons],
                "conflicts": list(self.conflicts), "explanation": self.explain()}


# ---------------------------------------------------------------------------
# Text similarity
# ---------------------------------------------------------------------------

_STOP = {"a", "an", "the", "of", "for", "and", "in", "on", "to", "with", "by",
         "from", "via", "at", "as", "is", "are", "using", "toward", "towards",
         "new", "novel", "towards", "into", "their"}


def _tokens(text: str) -> set[str]:
    return {t for t in normalise_title(text).split() if t not in _STOP and len(t) > 1}


def title_similarity(a: str | None, b: str | None) -> float:
    """Blend of token Jaccard and character ratio.

    Jaccard alone punishes a single long word ("photoredox" vs "photocatalysis");
    the character ratio alone rewards shared boilerplate. The mean of the two
    is stable for chemistry titles, and the pair is reported separately in the
    decision so a reviewer can see which signal drove it.
    """
    ta, tb = _tokens(a or ""), _tokens(b or "")
    if not ta or not tb:
        return 0.0
    jaccard = len(ta & tb) / len(ta | tb)
    ratio = SequenceMatcher(None, normalise_title(a), normalise_title(b)).ratio()
    return round((jaccard + ratio) / 2, 4)


def _first_family(rec: WorkRecord) -> str:
    if not rec.authors:
        return ""
    return re.sub(r"[^a-z]", "", rec.authors[0].family_name.lower())


def _shared_surnames(a: WorkRecord, b: WorkRecord) -> int:
    sa = {re.sub(r"[^a-z]", "", x.family_name.lower()) for x in a.authors if x.name}
    sb = {re.sub(r"[^a-z]", "", x.family_name.lower()) for x in b.authors if x.name}
    sa.discard("")
    sb.discard("")
    return len(sa & sb)


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

_VERSION_SUFFIX = re.compile(r"(?:\.v\d+|\.version\.?\d+|/v\d+)$", re.IGNORECASE)


def _strip_version(doi: str) -> str:
    """Drop a trailing version marker from a DOI (``...34472799.v1`` -> ``...34472799``)."""
    return _VERSION_SUFFIX.sub("", normalise_doi(doi))


def compare(a: WorkRecord, b: WorkRecord) -> MatchDecision:
    """Decide how two normalised records relate."""
    reasons: list[Signal] = []
    conflicts: list[str] = []
    score = 0.0

    # 1. Identifiers: agreement is decisive.
    doi_a, doi_b = normalise_doi(a.doi), normalise_doi(b.doi)
    if doi_a and doi_a == doi_b:
        return MatchDecision(Verdict.SAME, 1.0,
                             [Signal("doi", 1.0, f"identical DOI {doi_a}")])

    shared_ids = {k: v for k, v in a.provider_ids.items()
                  if k in b.provider_ids and b.provider_ids[k] == v and v}
    if shared_ids:
        detail = ", ".join(f"{k}:{v}" for k, v in shared_ids.items())
        return MatchDecision(Verdict.SAME, 0.98,
                             [Signal("provider_id", 0.98, f"identical {detail}")])

    # 2. Two different registered DOIs mean two registered objects.
    #
    # This rule was added after the sync pipeline merged two Zenodo records
    # (10.5281/zenodo.18233709 and 10.5281/zenodo.23352136) on title+author
    # alone. Zenodo mints a new DOI per version, so a content-only merge
    # destroyed a genuinely distinct record. Only an explicit version
    # relationship justifies linking suffixed DOIs.
    if doi_a and doi_b and doi_a != doi_b:
        base_a, base_b = _strip_version(doi_a), _strip_version(doi_b)
        if base_a == base_b:
            return MatchDecision(Verdict.RELATED_VERSION, 0.9,
                                 [Signal("version_suffix", 0.9,
                                         f"{doi_a} is a version of {doi_b}")])
        return MatchDecision(Verdict.DISTINCT, 0.0, [],
                             [f"different DOIs ({doi_a} vs {doi_b})"])

    # 3. Version relationships: a preprint and its VoR are NOT duplicates.
    versionish = (a.version_type in {VersionType.PREPRINT, VersionType.ACCEPTED_MANUSCRIPT}
                  or b.version_type in {VersionType.PREPRINT, VersionType.ACCEPTED_MANUSCRIPT})
    linked = (a.version_of and doi_b and normalise_doi(a.version_of) == doi_b) or \
             (b.version_of and doi_a and normalise_doi(b.version_of) == doi_a)
    if linked:
        return MatchDecision(Verdict.RELATED_VERSION, 0.95,
                             [Signal("version_link", 0.95, "explicit version-of link")])
    if a.version_type is VersionType.CORRECTION or b.version_type is VersionType.CORRECTION:
        if title_similarity(a.title, b.title) > 0.6:
            return MatchDecision(Verdict.RELATED_VERSION, 0.8,
                                 [Signal("correction", 0.8, "correction/erratum of the same work")])

    # 4. Content signals.
    sim = title_similarity(a.title, b.title)
    if sim >= 0.96:
        reasons.append(Signal("title", 0.6, f"near-identical titles ({sim:.3f})"))
        score += 0.6
    elif sim >= 0.85:
        reasons.append(Signal("title", 0.45, f"very similar titles ({sim:.3f})"))
        score += 0.45
    elif sim >= 0.70:
        reasons.append(Signal("title", 0.2, f"similar titles ({sim:.3f})"))
        score += 0.2
    else:
        conflicts.append(f"titles differ (similarity {sim:.2f})")

    if a.publication_year and b.publication_year:
        gap = abs(a.publication_year - b.publication_year)
        if gap == 0:
            reasons.append(Signal("year", 0.12, "same publication year"))
            score += 0.12
        elif gap <= 1:
            reasons.append(Signal("year", 0.06, f"publication years within {gap}"))
            score += 0.06
        else:
            conflicts.append(f"publication years differ by {gap}")

    shared = _shared_surnames(a, b)
    fam_a, fam_b = _first_family(a), _first_family(b)
    if fam_a and fam_b:
        if fam_a == fam_b:
            reasons.append(Signal("first_author", 0.12, f"same first-author family name ({fam_a})"))
            score += 0.12
        elif shared:
            reasons.append(Signal("coauthors", 0.08, f"{shared} shared author surnames"))
            score += 0.08
        else:
            conflicts.append("no shared author surnames")

    if a.venue and b.venue:
        same_venue = normalise_title(a.venue) == normalise_title(b.venue)
        if same_venue:
            reasons.append(Signal("venue", 0.08, a.venue))
            score += 0.08

    score = round(min(score, 0.95), 4)

    # 5. Verdict rules for the identifier-less (or singly-identified) case.
    if versionish and sim >= 0.85 and shared:
        return MatchDecision(Verdict.RELATED_VERSION, round(score, 4), reasons, conflicts)
    if sim >= 0.90 and (shared >= 1 or (fam_a and fam_a == fam_b)) and not conflicts:
        return MatchDecision(Verdict.SAME, max(score, 0.86), reasons, conflicts)
    if sim >= 0.96 and shared >= 2:
        return MatchDecision(Verdict.SAME, max(score, 0.8), reasons, conflicts)
    return MatchDecision(Verdict.DISTINCT, score, reasons, conflicts)


def find_duplicates(records: Iterable[WorkRecord], *, threshold: float = 0.8) -> list[dict[str, Any]]:
    """Blocking + pairwise comparison; returns merge proposals.

    Blocking key is the first four significant title words, so the pairwise
    comparison stays linear-ish instead of quadratic over a large batch.
    """
    blocks: dict[str, list[WorkRecord]] = {}
    for rec in records:
        from .schema import title_key
        key = title_key(rec.title) or rec.ensure_id()
        blocks.setdefault(key, []).append(rec)

    proposals: list[dict[str, Any]] = []
    for key, group in blocks.items():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                decision = compare(group[i], group[j])
                if decision.score >= threshold or decision.verdict is not Verdict.DISTINCT:
                    proposals.append({
                        "block": key,
                        "a": group[i].ensure_id(),
                        "b": group[j].ensure_id(),
                        "a_title": group[i].title,
                        "b_title": group[j].title,
                        **decision.as_dict(),
                    })
    proposals.sort(key=lambda p: -p["score"])
    return proposals


# ---------------------------------------------------------------------------
# Merging
# ---------------------------------------------------------------------------

#: Field precedence when two SAME records disagree. Order matters: an integrity
#: registry (Crossref) outranks a discovery index (OpenAlex), which outranks an
#: enricher (Unpaywall). Values are only taken from a lower-precedence source
#: when the higher one left the field unknown.
PRECEDENCE = ("crossref", "europepmc", "datacite", "openalex", "semantic_scholar",
              "arxiv", "doaj", "unpaywall")

#: Fields that must never be silently overwritten by a merge.
CONFLICT_SENSITIVE = ("doi", "publication_year", "venue", "citation_count", "license")


def _rank(rec: WorkRecord) -> int:
    names = {p.provider for p in rec.sources}
    best = len(PRECEDENCE)
    for name in names:
        if name in PRECEDENCE:
            best = min(best, PRECEDENCE.index(name))
    return best


def merge(records: list[WorkRecord]) -> tuple[WorkRecord, dict[str, Any]]:
    """Reconcile a group of records judged SAME into one.

    Returns the merged record and an audit dict listing every field taken from
    a specific provider, every conflict and how it was resolved. The recorder
    of this audit dict is what makes the merge reversible.
    """
    if not records:
        raise ValueError("merge() needs at least one record")
    if len(records) == 1:
        return records[0], {"sources": [p.provider for p in records[0].sources], "fields": {}}

    ordered = sorted(records, key=_rank)
    audit_fields: dict[str, Any] = {}
    conflicts: list[dict[str, Any]] = []

    base = ordered[0]
    merged = WorkRecord.from_dict(base.as_dict())

    for other in ordered[1:]:
        for fname in ("doi", "title", "abstract", "publication_year", "publication_date",
                      "venue", "publisher", "license", "fulltext_url", "article_type",
                      "subdiscipline", "data_availability"):
            mine, theirs = getattr(merged, fname), getattr(other, fname)
            if mine in (None, "") and theirs not in (None, ""):
                setattr(merged, fname, theirs)
                audit_fields[fname] = other.sources[0].provider if other.sources else "?"
            elif mine not in (None, "") and theirs not in (None, "") and str(mine).lower() != str(theirs).lower():
                if fname in CONFLICT_SENSITIVE:
                    conflicts.append({"field": fname, "kept": mine, "discarded": theirs,
                                      "kept_from": merged.sources[0].provider if merged.sources else "?",
                                      "discarded_from": other.sources[0].provider if other.sources else "?"})
        for fname in ("issn", "keywords", "funding"):
            current = list(getattr(merged, fname))
            for item in getattr(other, fname):
                if item not in current:
                    current.append(item)
            setattr(merged, fname, current)
        # authors: keep the longer, more complete list (it usually carries ORCIDs)
        if len(other.authors) > len(merged.authors):
            merged.authors = other.authors
        # enums: prefer a definite value over UNKNOWN
        for fname, unknown in (("oa_status", "unknown"), ("retraction_status", "unknown"),
                               ("peer_review", "unknown"), ("version_type", "unknown")):
            if str(getattr(merged, fname)) == unknown and str(getattr(other, fname)) != unknown:
                setattr(merged, fname, getattr(other, fname))
        # citation counts: keep the highest, and remember it may be a different as-of date
        if isinstance(other.citation_count, int):
            if merged.citation_count is None or other.citation_count > merged.citation_count:
                merged.citation_count = other.citation_count
                merged.citation_count_source = other.citation_count_source
                merged.citation_count_date = other.citation_count_date
        merged.references = sorted({*merged.references, *other.references})
        merged.provider_ids.update({k: v for k, v in other.provider_ids.items() if k not in merged.provider_ids})
        merged.sources = merged.sources + other.sources

    from .schema import VerificationStatus
    merged.verification = (VerificationStatus.CONFLICTING if conflicts
                           else VerificationStatus.CROSS_CHECKED)
    if conflicts:
        merged.confidence.per_field = {c["field"]: "conflict" for c in conflicts}
    merged.ensure_id()

    audit = {
        "sources": [p.provider for p in merged.sources],
        "fields": audit_fields,
        "conflicts": conflicts,
        "kept_id": merged.work_id,
        "merged_ids": [r.ensure_id() for r in ordered[1:]],
        "rule": "precedence " + " > ".join(PRECEDENCE),
    }
    return merged, audit
