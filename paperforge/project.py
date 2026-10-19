"""Project file loading and validation.

A PaperForge project is a single ``paper.yaml`` (or ``.json``/``.toml``) plus
asset folders.  The schema is deliberately boring: everything a manuscript
needs is declared once, and the renderers/checkers read from it.

Minimal project
---------------
```yaml
paper:
  title: "..."
  journal: "Organic Letters"
  article_type: letter
  keywords: [gold catalysis, heterocycles]
authors:
  - name: "A. Author"
    affiliation: 1
    corresponding: true
    email: "a@example.edu"
    orcid: "0000-0002-1825-0097"
affiliations:
  1: "Department of Chemistry, ..."
abstract:
  context: "..."
  gap: "..."
  results: ["..."]
  impact: "..."
```
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:  # optional, but recommended
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


class ProjectError(ValueError):
    """Raised for malformed project files."""


REQUIRED = {
    "paper": ["title", "journal"],
    "authors": None,
}


def _load_yaml(path: Path) -> dict:
    if yaml is None:
        raise ProjectError(
            "PyYAML is required to read .yaml projects. Install it (`pip install pyyaml`) "
            "or use paper.json / paper.toml."
        )
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ProjectError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ProjectError(f"{path} must contain a mapping at the top level")
    return data


def _load_toml(path: Path) -> dict:
    try:
        import tomllib  # Python 3.11+
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise ProjectError("TOML projects need Python 3.11+") from exc
    with path.open("rb") as fh:
        return tomllib.load(fh)


@dataclass
class Author:
    name: str
    affiliation: str | int = ""
    email: str = ""
    orcid: str = ""
    corresponding: bool = False
    credit: list[str] = field(default_factory=list)

    @property
    def family_name(self) -> str:
        parts = self.name.replace(",", " ").split()
        return parts[-1] if parts else self.name

    @classmethod
    def from_dict(cls, d: dict | str) -> "Author":
        if isinstance(d, str):
            return cls(name=d)
        return cls(
            name=str(d.get("name", "")).strip(),
            affiliation=d.get("affiliation", ""),
            email=str(d.get("email", "")),
            orcid=str(d.get("orcid", "")),
            corresponding=bool(d.get("corresponding", False)),
            credit=list(d.get("credit") or []),
        )


@dataclass
class Compound:
    id: str
    name: str = ""
    formula: str = ""
    mw: float | None = None
    mmol: float | None = None
    mass_g: float | None = None
    yield_percent: float | None = None
    hrms_calcd: float | None = None
    hrms_found: float | None = None
    hrms_adduct: str = "[M+H]+"
    nmr_1h: str = ""
    nmr_13c: str = ""
    n_13c_signals: int | None = None
    ir: str = ""
    mp: str = ""
    alpha_d: str = ""
    chiral: bool = False
    ccdc: str = ""
    crystal: bool = False
    purity: str = ""
    spectra_files: list[str] = field(default_factory=list)
    known: bool = False
    procedure: str = ""
    notes: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Compound":
        if "id" not in d:
            raise ProjectError("each compound needs an 'id' (e.g. '3a')")
        kwargs: dict[str, Any] = {}
        for f in cls.__dataclass_fields__:  # type: ignore[attr-defined]
            if f in d:
                kwargs[f] = d[f]
        for f in ("mw", "mmol", "mass_g", "yield_percent", "hrms_calcd", "hrms_found"):
            if kwargs.get(f) is not None:
                try:
                    kwargs[f] = float(kwargs[f])
                except (TypeError, ValueError):
                    raise ProjectError(f"compound {d['id']}: '{f}' must be a number")
        cid = str(d["id"])
        kwargs.pop("id", None)
        return cls(id=cid, **{k: v for k, v in kwargs.items() if k in cls.__dataclass_fields__})  # type: ignore[attr-defined]


@dataclass
class Figure:
    id: str
    file: str
    caption: str = ""
    label: str = ""
    kind: str = "figure"  # figure | scheme | toc | graphical
    source_data: str = ""
    width_cm: float | None = None
    panels: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "Figure":
        if "id" not in d or "file" not in d:
            raise ProjectError("each figure needs 'id' and 'file'")
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})  # type: ignore[attr-defined]


@dataclass
class Table:
    id: str
    file: str = ""
    caption: str = ""
    columns: list[str] = field(default_factory=list)
    footnote: str = ""
    source_data: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Table":
        if "id" not in d:
            raise ProjectError("each table needs an 'id'")
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})  # type: ignore[attr-defined]


@dataclass
class Paragraph:
    text: str
    cites: list[str] = field(default_factory=list)
    label: str = ""

    @classmethod
    def from_any(cls, d: dict | str) -> "Paragraph":
        if isinstance(d, str):
            return cls(text=d)
        return cls(text=str(d.get("text", "")), cites=list(d.get("cites") or []), label=str(d.get("label", "")))


@dataclass
class Section:
    heading: str
    paragraphs: list[Paragraph] = field(default_factory=list)
    subsections: list["Section"] = field(default_factory=list)
    dataset: str = ""
    type: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Section":
        if isinstance(d, str):
            return cls(heading=d)
        return cls(
            heading=str(d.get("heading") or d.get("title") or ""),
            paragraphs=[Paragraph.from_any(p) for p in (d.get("paragraphs") or d.get("text") or [])],
            subsections=[cls.from_dict(s) for s in (d.get("subsections") or [])],
            dataset=str(d.get("dataset", "") or ""),
            type=str(d.get("type", "") or ""),
        )


@dataclass
class Reference:
    key: str = ""
    doi: str = ""
    title: str = ""
    authors: list[str] = field(default_factory=list)
    journal: str = ""
    year: int | None = None
    volume: str = ""
    pages: str = ""
    verified: bool = False
    retracted: bool = False
    source: str = ""

    @classmethod
    def from_dict(cls, d: dict | str) -> "Reference":
        if isinstance(d, str):
            return cls(doi=d) if d.lower().startswith("10.") else cls(key=d)
        return cls(
            key=str(d.get("key", "")), doi=str(d.get("doi", "")).replace("https://doi.org/", ""),
            title=str(d.get("title", "")), authors=list(d.get("authors") or []),
            journal=str(d.get("journal", "")), year=d.get("year"),
            volume=str(d.get("volume", "")), pages=str(d.get("pages", "")),
            verified=bool(d.get("verified", False)), retracted=bool(d.get("retracted", False)),
            source=str(d.get("source", "")),
        )


class Project:
    """Validated, read-only view over a paper project."""

    def __init__(self, data: dict, root: Path | str = "."):
        if not isinstance(data, dict):
            raise ProjectError("project file must contain a mapping")
        self.data = data
        self.root = Path(root)

        if "paper" not in data:
            raise ProjectError("missing top-level 'paper' section")
        self.paper = data["paper"] or {}
        if not self.paper.get("title"):
            raise ProjectError("paper.title is required")
        if not self.paper.get("journal"):
            raise ProjectError("paper.journal is required (e.g. 'Organic Letters')")

        raw_authors = data.get("authors") or []
        if isinstance(raw_authors, dict):
            raw_authors = [raw_authors]
        if not raw_authors:
            raise ProjectError("at least one author is required")
        self.authors = [Author.from_dict(a) for a in raw_authors]

        aff = data.get("affiliations") or {}
        if isinstance(aff, list):
            aff = {i + 1: a for i, a in enumerate(aff)}
        self.affiliations: dict = aff

        self.abstract = data.get("abstract") or {}
        self.keywords = list(self.paper.get("keywords") or data.get("keywords") or [])
        self.sections = [Section.from_dict(s) for s in (data.get("sections") or [])]
        self.datasets = list(data.get("datasets") or [])
        self.figures = [Figure.from_dict(f) for f in (data.get("figures") or [])]
        self.tables = [Table.from_dict(t) for t in (data.get("tables") or [])]
        self.compounds = [Compound.from_dict(c) for c in (data.get("compounds") or [])]
        self.references = [Reference.from_dict(r) for r in (data.get("references") or [])]
        self.back_matter = data.get("back_matter") or {}
        self.highlights = list(data.get("highlights") or [])
        self.toc = data.get("toc") or {}
        self.narrative = data.get("narrative") or {}
        self.options = data.get("options") or {}
        self.issues: list[str] = []

    # -- convenience -------------------------------------------------------
    @classmethod
    def load(cls, path: str | os.PathLike) -> "Project":
        p = Path(path)
        if not p.exists():
            raise ProjectError(f"project not found: {p}")
        if p.is_dir():
            for name in ("paper.yaml", "paper.yml", "paper.json", "paper.toml"):
                cand = p / name
                if cand.exists():
                    p = cand
                    break
            else:
                raise ProjectError(f"no paper.yaml/paper.json/paper.toml found in {p}")
        suffix = p.suffix.lower()
        if suffix in (".yaml", ".yml"):
            data = _load_yaml(p)
        elif suffix == ".json":
            data = json.loads(p.read_text(encoding="utf-8"))
        elif suffix == ".toml":
            data = _load_toml(p)
        else:
            raise ProjectError(f"unsupported project format {suffix!r} (use .yaml/.json/.toml)")
        return cls(data, root=p.parent)

    def path(self, rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else (self.root / p)

    @property
    def title(self) -> str:
        return str(self.paper.get("title", ""))

    @property
    def journal(self) -> str:
        return str(self.paper.get("journal", ""))

    @property
    def article_type(self) -> str:
        return str(self.paper.get("article_type", "article"))

    @property
    def corresponding(self) -> list[Author]:
        return [a for a in self.authors if a.corresponding]

    def section(self, heading: str) -> Section | None:
        h = heading.lower()
        for s in self.sections:
            if s.heading.lower().startswith(h):
                return s
        return None

    def all_paragraphs(self) -> list[Paragraph]:
        out: list[Paragraph] = []

        def walk(sec: Section):
            out.extend(sec.paragraphs)
            for sub in sec.subsections:
                walk(sub)

        for s in self.sections:
            walk(s)
        return out

    def abstract_text(self) -> str:
        if not self.abstract:
            return ""
        if isinstance(self.abstract, str):
            return self.abstract
        parts = [self.abstract.get("context", ""), self.abstract.get("gap", "")]
        parts += list(self.abstract.get("results") or [])
        parts.append(self.abstract.get("impact", ""))
        return " ".join(p.strip() for p in parts if p and p.strip())

    def citation_keys(self) -> list[str]:
        keys: list[str] = []
        for p in self.all_paragraphs():
            for c in p.cites:
                for k in str(c).replace(";", ",").split(","):
                    k = k.strip()
                    if k and k not in keys:
                        keys.append(k)
            # inline markers such as "... as shown [patil2023gold]."
            for m in re.finditer(r"\[([A-Za-z0-9_\-,\s;]{3,})\]", p.text or ""):
                for k in m.group(1).replace(";", ",").split(","):
                    k = k.strip()
                    if k and k not in keys:
                        keys.append(k)
        return keys

    def toc_text(self) -> str:
        return str(self.toc.get("text", "") or "")

    def toc_image(self) -> str:
        return str(self.toc.get("image", "") or "")

    def to_dict(self) -> dict:
        return self.data

    def summary(self) -> dict:
        return {
            "title": self.title, "journal": self.journal, "article_type": self.article_type,
            "authors": len(self.authors), "sections": [s.heading for s in self.sections],
            "figures": len(self.figures), "tables": len(self.tables),
            "compounds": len(self.compounds), "references": len(self.references),
            "datasets": [d.get("id") for d in self.datasets if isinstance(d, dict)],
        }


# ---------------------------------------------------------------------------
# Scaffolding
# ---------------------------------------------------------------------------

SCAFFOLD = {
    "paper": {
        "title": "Informative title, ≤18 words, no hype words",
        "journal": "Organic Letters",
        "article_type": "letter",
        "keywords": ["keyword one", "keyword two", "keyword three", "keyword four"],
    },
    "authors": [
        {
            "name": "First Author", "affiliation": 1, "corresponding": True,
            "email": "first.author@institute.ac.in", "orcid": "0000-0000-0000-0000",
            "credit": ["conceptualization", "investigation", "writing – original draft"],
        }
    ],
    "affiliations": {1: "Department of Chemistry, Indian Institute of Science Education and Research Bhopal, Bhopal 462066, India"},
    "abstract": {
        "context": "The field-level problem and why it matters (1–2 sentences).",
        "gap": "What was missing and what this work does (1–2 sentences).",
        "results": ["Key quantitative results with numbers, units and compound labels."],
        "impact": "What the result means beyond this system (1 sentence).",
    },
    "sections": [
        {"heading": "Introduction", "paragraphs": [{"text": "Context, state of the art, gap, approach.", "cites": []}]},
        {"heading": "Results and Discussion", "paragraphs": [{"text": "Results, with figures cited.", "cites": []}]},
        {"heading": "Conclusion", "paragraphs": [{"text": "Achievement, limitations, outlook."}]},
    ],
    "datasets": [],
    "figures": [],
    "tables": [],
    "compounds": [],
    "references": [],
    "back_matter": {
        "coi": "The authors declare no competing financial interest.",
        "funding": "This work was supported by [funder] (Grant No. ...).",
        "data_availability": "All data are available in the paper and Supporting Information.",
        "ai_disclosure": "AI tools were used for language editing; all scientific content is the authors' own.",
        "safety": "No unexpected hazards were encountered.",
    },
    "highlights": [],
    "toc": {"text": "", "image": ""},
}


def scaffold(dest: str | os.PathLike, title: str = "", journal: str = "Organic Letters") -> Path:
    """Create a new project folder with paper.yaml and asset directories."""
    root = Path(dest)
    root.mkdir(parents=True, exist_ok=True)
    data = json.loads(json.dumps(SCAFFOLD))  # deep copy
    if title:
        data["paper"]["title"] = title
    if journal:
        data["paper"]["journal"] = journal
    for sub in ("data", "figures", "refs", "si"):
        (root / sub).mkdir(exist_ok=True)
    if yaml is not None:
        text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)
        (root / "paper.yaml").write_text(text, encoding="utf-8")
        project_file = root / "paper.yaml"
    else:
        (root / "paper.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        project_file = root / "paper.json"
    (root / "README.md").write_text(
        f"# {data['paper']['title']}\n\n"
        "PaperForge project. Commands:\n\n"
        "```bash\npaperforge draft .        # build manuscript.md / .tex / .docx\n"
        "paperforge score .        # 0–100 submission-readiness score\n"
        "paperforge check .        # rule-by-rule compliance report\n"
        "paperforge refs verify .  # check every DOI against Crossref\npaperforge bundle .       # submission zip\n```\n",
        encoding="utf-8",
    )
    return project_file
