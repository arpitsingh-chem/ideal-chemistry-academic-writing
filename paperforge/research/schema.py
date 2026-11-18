"""Normalised research record schema.

Design rules (deliberate, and enforced by tests):

1. **No fabrication.** A field the provider did not supply is ``None``. It is
   never filled in from a guess, a sibling record, or a default value.
2. **Absence is not evidence.** ``RetractionStatus.NONE_KNOWN`` means *no
   retraction notice was found in the sources queried*; it does not mean the
   work is sound. The distinction is carried in the enum, not in prose.
3. **Provenance is first class.** Every record keeps a list of
   :class:`Provenance` entries (which provider, which URL, when, which raw
   payload hash), so a stale value can always be traced to its origin.
4. **Raw provider payloads are stored separately** (see
   :mod:`paperforge.research.store`), never merged into the normalised view.

The normalised model is intentionally a plain dataclass rather than a
``pydantic`` model: PaperForge's base install has no runtime dependency beyond
PyYAML, and the validation needs here (enumerations, ranges, unknown states)
are small enough to express directly.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Iterable

SCHEMA_VERSION = "1.0"


class StrEnum(str, Enum):
    """String enum that serialises as its value (3.10-compatible)."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)


class RetractionStatus(StrEnum):
    """What the queried sources say about the integrity of a work."""

    NONE_KNOWN = "none_known"          # no notice found in the sources queried
    RETRACTED = "retracted"            # a retraction notice exists
    CORRECTION = "correction"          # an erratum / correction exists
    EXPRESSION_OF_CONCERN = "expression_of_concern"
    UNKNOWN = "unknown"                # source does not publish this signal


class PeerReview(StrEnum):
    """Peer-review state. ``UNKNOWN`` is the honest default for most indexes."""

    PREPRINT = "preprint"
    PEER_REVIEWED = "peer_reviewed"
    UNKNOWN = "unknown"


class VersionType(StrEnum):
    """Version relationship, used by the deduplication layer."""

    VERSION_OF_RECORD = "version_of_record"
    ACCEPTED_MANUSCRIPT = "accepted_manuscript"
    PREPRINT = "preprint"
    CONFERENCE = "conference"
    CORRECTION = "correction"
    RETRACTION = "retraction"
    UNKNOWN = "unknown"


class OaStatus(StrEnum):
    GOLD = "gold"
    HYBRID = "hybrid"
    GREEN = "green"
    BRONZE = "bronze"
    CLOSED = "closed"
    UNKNOWN = "unknown"


class VerificationStatus(StrEnum):
    """How far the record's identifiers have been checked."""

    UNVERIFIED = "unverified"      # normalised only
    IDENTIFIER_CHECKED = "identifier_checked"   # DOI resolved at a resolver
    CROSS_CHECKED = "cross_checked"             # agreed by 2+ providers
    CONFLICTING = "conflicting"                 # providers disagree


#: Canonical chemistry subdisciplines (Part V of the brief). Classification is a
#: keyword model, therefore *advisory*: it is exposed as a hint and never used
#: to filter a record out of a search result.
CHEMISTRY_SUBDISCIPLINES: tuple[str, ...] = (
    "organic", "inorganic", "physical", "analytical", "theoretical",
    "computational", "quantum", "organometallic", "coordination", "bioinorganic",
    "biochemistry", "medicinal", "materials", "polymer", "supramolecular",
    "photochemistry", "electrochemistry", "environmental", "atmospheric",
    "catalysis", "surface", "solid_state", "crystallography", "spectroscopy",
    "chemical_biology", "chemical_engineering", "nanochemistry", "green",
)


@dataclass
class Author:
    """An author as reported by one provider. ``orcid`` is never inferred."""

    name: str
    orcid: str | None = None
    given: str | None = None
    family: str | None = None
    affiliations: list[str] = field(default_factory=list)
    institutions: list[dict[str, str]] = field(default_factory=list)

    @property
    def family_name(self) -> str:
        if self.family:
            return self.family
        parts = [p for p in re.split(r"\s+", self.name.strip()) if p]
        return parts[-1] if parts else ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Author":
        return cls(
            name=data.get("name") or "",
            orcid=data.get("orcid"),
            given=data.get("given"),
            family=data.get("family"),
            affiliations=list(data.get("affiliations") or []),
            institutions=list(data.get("institutions") or []),
        )


@dataclass
class Provenance:
    """Where one value came from, and when it was retrieved."""

    provider: str
    url: str = ""
    retrieved_at: str = ""
    payload_sha256: str = ""
    license: str | None = None
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Provenance":
        return cls(**{k: data.get(k) for k in
                      ("provider", "url", "retrieved_at", "payload_sha256", "license", "notes")})


@dataclass
class Confidence:
    """Field-level confidence for reconciled records.

    Only populated when two or more providers supplied the same field; a single
    provider's value is reported as ``single_source`` rather than "100 %".
    """

    per_field: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"per_field": dict(self.per_field)}


@dataclass
class WorkRecord:
    """One normalised scholarly work.

    Field semantics: ``None`` means *unknown / not supplied*. An empty list
    means *the provider supplied the field and it is empty*, which is a
    different and meaningful state (e.g. a pre-registered paper with no
    references deposited yet).
    """

    # --- identity ---------------------------------------------------------
    work_id: str = ""                      # stable internal id (see :meth:`ensure_id`)
    doi: str | None = None
    provider_ids: dict[str, str] = field(default_factory=dict)   # {"openalex": "W123", ...}

    # --- descriptive ------------------------------------------------------
    title: str | None = None
    abstract: str | None = None
    authors: list[Author] = field(default_factory=list)
    publication_year: int | None = None
    publication_date: str | None = None
    venue: str | None = None
    publisher: str | None = None
    issn: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)

    # --- classification ---------------------------------------------------
    article_type: str | None = None
    subdiscipline: str | None = None
    peer_review: PeerReview = PeerReview.UNKNOWN
    version_type: VersionType = VersionType.UNKNOWN
    version_of: str | None = None          # DOI of the version of record, when known

    # --- access -----------------------------------------------------------
    oa_status: OaStatus = OaStatus.UNKNOWN
    license: str | None = None
    fulltext_url: str | None = None
    data_availability: str | None = None
    funding: list[dict[str, str]] = field(default_factory=list)

    # --- bibliometrics (never invented; source + date always carried) -----
    citation_count: int | None = None
    citation_count_source: str | None = None
    citation_count_date: str | None = None

    # --- integrity --------------------------------------------------------
    retraction_status: RetractionStatus = RetractionStatus.UNKNOWN
    retraction_notice_doi: str | None = None
    references: list[str] = field(default_factory=list)   # DOIs of cited works

    # --- provenance -------------------------------------------------------
    sources: list[Provenance] = field(default_factory=list)
    verification: VerificationStatus = VerificationStatus.UNVERIFIED
    confidence: Confidence = field(default_factory=Confidence)
    retrieved_at: str | None = None
    source_url: str | None = None

    # --- internal ---------------------------------------------------------
    scheme: str = "paperforge.work/1"

    # -- identity helpers --------------------------------------------------
    def ensure_id(self) -> str:
        """Assign a stable id: DOI-based when available, else content hash.

        DOI-based ids are stable across providers, which is what makes
        idempotent ingestion possible.
        """
        if not self.work_id:
            doi = normalise_doi(self.doi)
            # A whitespace-only or syntactically invalid DOI must not become an
            # identity: every such record would collapse onto "doi:".
            if doi and valid_doi(doi):
                self.work_id = "doi:" + doi
            else:
                basis = "|".join([
                    (self.title or "").lower(),
                    str(self.publication_year or ""),
                    (self.authors[0].family_name if self.authors else "").lower(),
                ])
                self.work_id = "hash:" + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]
        return self.work_id

    def fingerprint(self) -> str:
        """Hash of the identifying content — used to detect real changes."""
        basis = json.dumps(
            {
                "doi": normalise_doi(self.doi) if self.doi else None,
                "title": (self.title or "").strip().lower(),
                "year": self.publication_year,
                "venue": (self.venue or "").strip().lower(),
                "authors": [a.name.lower() for a in self.authors],
            },
            sort_keys=True,
        )
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()

    # -- reporting ---------------------------------------------------------
    def missing_fields(self) -> list[str]:
        """Field names that are unknown. Drives metadata-completeness metrics."""
        interesting = ("doi", "title", "abstract", "authors", "publication_year",
                       "venue", "publisher", "issn", "keywords", "article_type",
                       "license", "oa_status", "funding", "citation_count")
        out = []
        for name in interesting:
            value = getattr(self, name)
            if value is None or value == [] or value == OaStatus.UNKNOWN:
                out.append(name)
        if self.retraction_status == RetractionStatus.UNKNOWN:
            out.append("retraction_status")
        return out

    def completeness(self) -> float:
        """Fraction of the tracked fields that are known (0.0–1.0)."""
        empty = len(self.missing_fields())
        return round(1.0 - empty / 16.0, 4)

    # -- serialisation -----------------------------------------------------
    def as_dict(self) -> dict[str, Any]:
        data = {
            "schema": self.scheme,
            "schema_version": SCHEMA_VERSION,
            "work_id": self.ensure_id(),
            "doi": self.doi,
            "provider_ids": dict(self.provider_ids),
            "title": self.title,
            "abstract": self.abstract,
            "authors": [a.as_dict() for a in self.authors],
            "publication_year": self.publication_year,
            "publication_date": self.publication_date,
            "venue": self.venue,
            "publisher": self.publisher,
            "issn": list(self.issn),
            "keywords": list(self.keywords),
            "article_type": self.article_type,
            "subdiscipline": self.subdiscipline,
            "peer_review": str(self.peer_review),
            "version_type": str(self.version_type),
            "version_of": self.version_of,
            "oa_status": str(self.oa_status),
            "license": self.license,
            "fulltext_url": self.fulltext_url,
            "data_availability": self.data_availability,
            "funding": list(self.funding),
            "citation_count": self.citation_count,
            "citation_count_source": self.citation_count_source,
            "citation_count_date": self.citation_count_date,
            "retraction_status": str(self.retraction_status),
            "retraction_notice_doi": self.retraction_notice_doi,
            "references": list(self.references),
            "sources": [p.as_dict() for p in self.sources],
            "verification": str(self.verification),
            "confidence": self.confidence.as_dict(),
            "retrieved_at": self.retrieved_at,
            "source_url": self.source_url,
            "missing_fields": self.missing_fields(),
            "completeness": self.completeness(),
        }
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkRecord":
        def _enum(enum_cls, value, default):
            if value in (None, ""):
                return default
            try:
                return enum_cls(str(value))
            except ValueError:
                return default

        return cls(
            work_id=data.get("work_id") or "",
            doi=data.get("doi"),
            provider_ids=dict(data.get("provider_ids") or {}),
            title=data.get("title"),
            abstract=data.get("abstract"),
            authors=[Author.from_dict(a) for a in data.get("authors") or []],
            publication_year=data.get("publication_year"),
            publication_date=data.get("publication_date"),
            venue=data.get("venue"),
            publisher=data.get("publisher"),
            issn=list(data.get("issn") or []),
            keywords=list(data.get("keywords") or []),
            article_type=data.get("article_type"),
            subdiscipline=data.get("subdiscipline"),
            peer_review=_enum(PeerReview, data.get("peer_review"), PeerReview.UNKNOWN),
            version_type=_enum(VersionType, data.get("version_type"), VersionType.UNKNOWN),
            version_of=data.get("version_of"),
            oa_status=_enum(OaStatus, data.get("oa_status"), OaStatus.UNKNOWN),
            license=data.get("license"),
            fulltext_url=data.get("fulltext_url"),
            data_availability=data.get("data_availability"),
            funding=list(data.get("funding") or []),
            citation_count=data.get("citation_count"),
            citation_count_source=data.get("citation_count_source"),
            citation_count_date=data.get("citation_count_date"),
            retraction_status=_enum(RetractionStatus, data.get("retraction_status"),
                                    RetractionStatus.UNKNOWN),
            retraction_notice_doi=data.get("retraction_notice_doi"),
            references=list(data.get("references") or []),
            sources=[Provenance.from_dict(p) for p in data.get("sources") or []],
            verification=_enum(VerificationStatus, data.get("verification"),
                               VerificationStatus.UNVERIFIED),
            confidence=Confidence(per_field=dict((data.get("confidence") or {}).get("per_field") or {})),
            retrieved_at=data.get("retrieved_at"),
            source_url=data.get("source_url"),
        )


# ---------------------------------------------------------------------------
# Identifiers and text
# ---------------------------------------------------------------------------

DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


def normalise_doi(doi: str | None) -> str:
    """Canonical DOI form: no resolver prefix, lower case, no trailing point.

    Lower-casing is safe because DOIs are case-insensitive for resolution
    (Crossref recommendation) and it makes deduplication deterministic.
    """
    if not doi:
        return ""
    value = str(doi).strip()
    value = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", value, flags=re.IGNORECASE)
    value = value.split("?")[0].strip().rstrip(".,;")
    return value.lower()


def valid_doi(doi: str | None) -> bool:
    return bool(DOI_RE.match(normalise_doi(doi)))


def normalise_orcid(orcid: str | None) -> str | None:
    """Canonical 0000-0000-0000-000X form, or ``None`` if it is not valid.

    The check digit is verified with the ISO 7064 MOD 11-2 algorithm, so a
    plausible-looking but wrong ORCID is rejected rather than stored.
    """
    if not orcid:
        return None
    value = str(orcid).strip()
    value = re.sub(r"^https?://orcid\.org/", "", value, flags=re.IGNORECASE)
    digits = value.replace("-", "").upper()
    if len(digits) != 16 or not re.fullmatch(r"\d{15}[\dX]", digits):
        return None
    total = 0
    for ch in digits[:15]:
        total = (total + int(ch)) * 2
    remainder = total % 11
    check = (12 - remainder) % 11
    expected = "X" if check == 10 else str(check)
    if expected != digits[15]:
        return None
    return f"{digits[0:4]}-{digits[4:8]}-{digits[8:12]}-{digits[12:16]}"


def normalise_title(title: str | None) -> str:
    """Case-, accent- and punctuation-insensitive title key for blocking.

    HTML entities and markup are stripped because several indexes return
    ``<i>``/``&amp;`` inside titles; superscript digits are kept because
    ``CO2`` and ``C2`` must not collide.
    """
    if not title:
        return ""
    text = re.sub(r"<[^>]+>", " ", title)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def title_key(title: str | None) -> str:
    """Blocking key: first four significant words of the normalised title."""
    words = [w for w in normalise_title(title).split() if len(w) > 1]
    return " ".join(words[:4])


def classify_subdiscipline(title: str | None, abstract: str | None = None,
                           keywords: Iterable[str] | None = None) -> str | None:
    """Keyword-based chemistry subdiscipline hint.

    Returns ``None`` when no keyword matches — an explicit unknown rather than
    a wrong guess. Deliberately not a classifier trained on unlicensed data.
    """
    text = " ".join(filter(None, [title or "", abstract or "", " ".join(keywords or [])])).lower()
    if not text:
        return None
    patterns: list[tuple[str, tuple[str, ...]]] = [
        ("catalysis", ("catalys", "catalyst", "catalytic")),
        ("photochemistry", ("photoredox", "photocatal", "photophysic", "fluorescence",
                            "luminescence", "excited state", "singlet oxygen", "quantum yield")),
        ("electrochemistry", ("electrochem", "voltammetr", "cyclic voltamm", "overpotential",
                              "battery", "electrode")),
        ("organometallic", ("organometallic", "ligand", "iridium", "palladium", "rhodium",
                            "ruthenium", "nickel catal", "copper catal")),
        ("coordination", ("coordination polymer", "metal organic framework", "mof", "complexes of")),
        ("medicinal", ("anticancer", "cytotox", "ic50", "drug", "inhibitor", "antibacter",
                       "antimicrobial", "pharmacokinet")),
        ("materials", ("perovskite", "thin film", "band gap", "semiconductor", "energy storage",
                       "solar cell", "material")),
        ("polymer", ("polymer", "copolymer", "hydrogel", "polymeric")),
        ("supramolecular", ("supramolecular", "host guest", "self assembl", "hydrogen bond",
                            "halogen bond", "macrocycle")),
        ("crystallography", ("crystal structure", "single crystal", "cif", "space group",
                             "crystallograph", "scxrd")),
        ("spectroscopy", ("nmr", "infrared spectr", "raman", "uv vis", "mass spectrometry",
                          "spectroscop")),
        ("nanochemistry", ("nanoparticle", "nanocrystal", "nanomaterial", "quantum dot", "2d material")),
        ("computational", ("dft", "density functional", "molecular dynamics", "ab initio", "docking")),
        ("green", ("green chemistry", "sustainable", "biomass", "solvent free", "atom econom")),
        ("environmental", ("environmental", "wastewater", "pollutant", "adsorption", "remediation")),
        ("bioinorganic", ("bioinorganic", "metalloprotein", "heme", "metalloenzyme")),
        ("chemical_biology", ("chemical biology", "bioconjugation", "probe", "bioorthogonal")),
        ("biochemistry", ("enzyme", "protein", "peptide", "dna", "rna", "biochemical")),
        ("surface", ("surface", "adsorbate", "monolayer", "heterogeneous catal")),
        ("solid_state", ("solid state", "lattice", "phase transition", "ceramic")),
        ("atmospheric", ("atmospher", "aerosol", "ozone", "air quality")),
        ("analytical", ("sensor", "detection limit", "hplc", "chromatograph", "quantification")),
        ("quantum", ("quantum chemistry", "wavefunction", "coupled cluster", "caspt2")),
        ("theoretical", ("theoretical", "thermodynamic model", "kinetic model")),
        ("inorganic", ("inorganic", "metal complex", "main group", "lanthanide")),
        ("organic", ("synthesis", "synthetic", "substrate scope", "yield", "organic")),
    ]
    for label, needles in patterns:
        if any(n in text for n in needles):
            return label
    return None


#: Field names that appear in :meth:`WorkRecord.missing_fields` output.
TRACKED_FIELDS = ("doi", "title", "abstract", "authors", "publication_year", "venue",
                  "publisher", "issn", "keywords", "article_type", "license",
                  "oa_status", "funding", "citation_count", "retraction_status",
                  "data_availability")
