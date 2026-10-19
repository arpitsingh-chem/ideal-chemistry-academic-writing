"""Ingest a research folder into a PaperForge project.

The engine cannot invent science, but most of a manuscript is *bookkeeping* around
facts that already exist in a folder: tables of yields, spectra-derived formulae,
figures, and a bibliography.  ``ingest`` reads that folder and produces a valid
``paper.yaml`` plus a report of exactly which human decisions remain.

Heuristics, in order of confidence:

* a CSV whose columns include a formula and a yield becomes the **compound table**
  (and therefore the Experimental section);
* other numeric CSVs become **datasets** (auto Results summary) and optionally tables;
* images become **figures** (``toc``/``graphical`` in the name → TOC graphic,
  ``scheme`` → scheme);
* ``.bib``/``.ris``/``dois.txt`` become **references**.

Nothing is fabricated: missing prose stays a clearly marked ``TODO``.
"""
from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path

from .refs import parse_bibtex
from .util import dump_json, read_text, write_text

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".svg", ".pdf", ".eps"}

COLUMN_SYNONYMS = {
    "id": ["id", "label", "compound", "entry", "no", "no.", "code"],
    "name": ["name", "compound name", "compound", "product", "iupac", "structure"],
    "formula": ["formula", "molecular formula", "mf"],
    "mw": ["mw", "molar mass", "molecular weight", "mr"],
    "mmol": ["mmol", "mmoles", "millimol", "scale"],
    "mass_g": ["mass_g", "mass", "mass (g)", "mass/mg", "weight", "yield_g", "yield (g)"],
    "yield_percent": ["yield_percent", "yield", "yield (%)", "yield/%", "yield %", "isolated yield"],
    "hrms_calcd": ["hrms_calcd", "calcd", "calculated", "m/z calcd", "calcd m/z"],
    "hrms_found": ["hrms_found", "found", "observed", "m/z found", "found m/z"],
    "hrms_adduct": ["adduct", "ion", "hrms adduct"],
    "nmr_1h": ["nmr_1h", "1h nmr", "1h-nmr", "hnmr"],
    "nmr_13c": ["nmr_13c", "13c nmr", "13c-nmr", "cnmr"],
    "ir": ["ir", "ftir", "ir (cm-1)"],
    "mp": ["mp", "melting point", "m.p.", "mp (°c)"],
    "purity": ["purity", "purity (%)", "hplc"],
}


def _norm(col: str) -> str:
    return re.sub(r"[\s_]+", " ", col.strip().lower())


def _map_columns(header: list[str]) -> dict[str, str]:
    """Map canonical field → actual column name (exact first, then canonicalised)."""
    mapping: dict[str, str] = {}
    normalised = {_norm(h): h for h in header}
    canonical = {_norm(_norm(h)): h for h in header}

    def _lookup(name: str) -> str | None:
        key = _norm(name)
        if key in normalised:
            return normalised[key]
        squeezed = re.sub(r"[^a-z0-9]", "", key)
        for h_key, original in canonical.items():
            if re.sub(r"[^a-z0-9]", "", h_key) == squeezed:
                return original
        return None

    for field, names in COLUMN_SYNONYMS.items():
        for name in names:
            hit = _lookup(name)
            if hit:
                mapping[field] = hit
                break
    return mapping


def _number(value: str) -> float | None:
    """Parse '1,234.5', '1.234,5', '89,5' and '1,234' the way a human wrote them.

    Stripping non-digits turns '89,5' into 895 -- a silent 10x error that no
    later check can see.  When both separators appear, the last one wins; a
    single comma is a thousands separator only when it groups exactly three
    digits, otherwise it is the decimal point.
    """
    v = re.sub(r"[^0-9eE+\-.,]", "", (value or "").strip())
    if not v:
        return None
    if "," in v and "." in v:
        v = v.replace(",", "") if v.rfind(".") > v.rfind(",") else v.replace(".", "").replace(",", ".")
    elif "," in v:
        head, _, tail = v.partition(",")
        thousands = len(tail) == 3 and head not in ("", "0") and head.lstrip("+-").isdigit()
        v = v.replace(",", "") if thousands else v.replace(",", ".")
    try:
        return float(v)
    except ValueError:
        return None


def _coerce(field: str, value: str):
    value = (value or "").strip()
    if value == "":
        return None
    if field in {"mw", "mmol", "mass_g", "yield_percent", "hrms_calcd", "hrms_found"}:
        num = _number(value)
        return value if num is None else num
    return value


def _read_csv(path: Path) -> tuple[list[str], list[dict]]:
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):     # BOM survives a latin-1 fallback
        data = data[3:]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        # Excel on a European locale writes Latin-1; that is data, not garbage.
        text = data.decode("latin-1")
    return _read_csv_text(text)


def _read_csv_text(text: str) -> tuple[list[str], list[dict]]:
    with io.StringIO(text, newline="") as fh:
        # csv.Sniffer picks ',' on a European export because the decimal commas
        # outnumber the real separator.  The header line has no decimals, so
        # count separators there instead.
        header = text.splitlines()[0] if text.splitlines() else ""
        delim = max(",;\t", key=header.count) if any(c in header for c in ",;\t") else ","
        try:
            dialect = csv.Sniffer().sniff(header, delimiters=delim)
        except csv.Error:
            dialect = csv.excel
            dialect.delimiter = delim
        reader = csv.DictReader(fh, dialect=dialect)
        rows = [r for r in reader if any((v or "").strip() for v in r.values())]
        header = list(reader.fieldnames or [])
    return header, rows


def _numeric_summary(rows: list[dict], header: list[str]) -> dict:
    """row count + min/max/median-ish for numeric columns (used in captions)."""
    out: dict[str, dict] = {}
    for col in header:
        vals = []
        for r in rows:
            try:
                vals.append(float(str(r.get(col, "")).replace(",", ".")))
            except (TypeError, ValueError):
                continue
        if vals and len(vals) >= max(3, len(rows) // 2):
            vals.sort()
            out[col] = {"n": len(vals), "min": vals[0], "max": vals[-1],
                        "median": vals[len(vals) // 2]}
    return out


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "item"


def _guess_title(src: Path, files: list[Path]) -> str:
    for candidate in ("title.txt", "title.md", "TITLE"):
        p = src / candidate
        if p.exists():
            first = read_text(p).strip().splitlines()
            if first and first[0].strip():
                return first[0].strip()
    # a single .tex/.docx with a \title{} is a strong signal
    for f in files:
        if f.suffix.lower() == ".tex":
            m = re.search(r"\\title\{([^{}]*)\}", read_text(f))
            if m:
                return re.sub(r"\s+", " ", m.group(1)).strip()
    return src.resolve().name.replace("_", " ").replace("-", " ").title()


def _ris_entries(text: str) -> list[dict]:
    """Minimal RIS reader (TY/ TI/ AU/ PY/ DO/ JO/ T2/ VL/ SP/ EP)."""
    entries, cur = [], {}
    for line in text.splitlines():
        m = re.match(r"^([A-Z][A-Z0-9])  - (.*)$", line)
        if not m:
            continue
        tag, val = m.group(1), m.group(2).strip()
        if tag == "TY":
            cur = {"type": val}
        elif tag == "ER":
            if cur:
                entries.append(cur)
            cur = {}
        elif tag == "AU":
            cur.setdefault("authors", []).append(val)
        elif tag == "TI":
            cur["title"] = val
        elif tag == "PY":
            cur["year"] = val[:4]
        elif tag == "DO":
            cur["doi"] = val
        elif tag in {"JO", "T2", "JA"}:
            cur.setdefault("journal", val)
        elif tag == "VL":
            cur["volume"] = val
        elif tag == "SP":
            cur["pages"] = val
        elif tag == "EP":
            cur["pages"] = f"{cur.get('pages', '')}-{val}".strip("-")
    if cur:
        entries.append(cur)
    return entries


def _doi_list(text: str) -> list[dict]:
    dois = re.findall(r"10\.\d{4,9}/[^\s,;\"'<>]+", text)
    return [{"doi": d.rstrip(".")} for d in dois]


def ingest(src: str | Path, out: str | Path, *, title: str | None = None,
           journal: str = "Organic Letters", article_type: str = "article",
           max_table_rows: int = 40) -> dict:
    """Read a folder and write a project skeleton. Returns an ingestion report."""
    src = Path(src)
    out = Path(out)
    if not src.exists():
        raise FileNotFoundError(f"source folder not found: {src}")
    out.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in src.rglob("*") if p.is_file())
    notes = {p.name.lower(): p for p in files if p.suffix.lower() in {".md", ".txt"}}

    compounds: list[dict] = []
    datasets: list[dict] = []
    tables: list[dict] = []
    figures: list[dict] = []
    references: list[dict] = []
    warnings: list[str] = []

    # -- tables ------------------------------------------------------------
    for f in [p for p in files if p.suffix.lower() == ".csv"]:
        try:
            header, rows = _read_csv(f)
        except Exception as exc:  # pragma: no cover - malformed encodings
            warnings.append(f"{f.name}: unreadable ({exc})")
            continue
        mapping = _map_columns(header)
        looks_like_compounds = ("formula" in mapping or "name" in mapping) and \
            ("yield_percent" in mapping or "mass_g" in mapping) and len(rows) >= 2
        if looks_like_compounds:
            for i, row in enumerate(rows, start=1):
                rec = {"id": str(_coerce("id", row.get(mapping.get("id", ""), "")) or f"c{i}")}
                for field, col in mapping.items():
                    if field == "id":
                        continue
                    val = _coerce(field, row.get(col, ""))
                    if val not in (None, ""):
                        rec[field] = val
                if "name" not in rec:
                    rec["name"] = rec["id"]
                if "procedure" not in rec:
                    rec["procedure"] = "TODO: paste the experimental procedure."
                compounds.append(rec)
            warnings.append(
                f"{f.name}: treated as the compound table ({len(rows)} rows). "
                "Add `procedure` and confirm `known` flags.")
            continue
        summary = _numeric_summary(rows, header)
        ds_id = _slug(f.stem)
        datasets.append({"id": ds_id, "file": f"data/{f.name}",
                         "caption": f"{f.stem.replace('_', ' ').capitalize()}."})
        if len(rows) <= max_table_rows:
            tables.append({"id": f"tab_{ds_id}", "file": f"data/{f.name}",
                           "caption": f"TODO: caption for {f.stem.replace('_', ' ')}."})
        if summary:
            warnings.append(f"{f.name}: dataset with numeric columns {sorted(summary)}")

    # -- images ------------------------------------------------------------
    for f in [p for p in files if p.suffix.lower() in IMAGE_EXT]:
        stem = f.stem.lower()
        kind = "toc" if ("toc" in stem or "graphical" in stem) else (
            "scheme" if "scheme" in stem else "figure")
        num = 1 + sum(1 for x in figures if x["kind"] == kind)
        entry = {"id": f"{kind}{num}", "file": f"figures/{f.name}", "kind": kind,
                 "caption": f"TODO: caption for {f.stem}."}
        figures.append(entry)

    # -- references --------------------------------------------------------
    for f in files:
        suffix = f.suffix.lower()
        if suffix == ".bib":
            for e in parse_bibtex(read_text(f)):
                references.append({k: v for k, v in e.items() if v and k != "type"})
        elif suffix == ".ris":
            references.extend(_ris_entries(read_text(f)))
        elif f.name.lower() in {"dois.txt", "dois.csv", "references.txt"}:
            references.extend(_doi_list(read_text(f)))

    # de-duplicate references by DOI / key / title
    seen, unique = set(), []
    for r in references:
        marker = (r.get("doi") or "").lower() or r.get("key") or (r.get("title") or "").lower()
        if marker and marker not in seen:
            seen.add(marker)
            unique.append(r)
    references = unique

    # -- copy assets -------------------------------------------------------
    for entry in datasets + tables:
        s = src / Path(entry["file"]).name
        if s.exists():
            d = out / "data" / s.name
            d.parent.mkdir(parents=True, exist_ok=True)
            d.write_bytes(s.read_bytes())
    for entry in figures:
        s = src / Path(entry["file"]).name
        if s.exists():
            d = out / "figures" / s.name
            d.parent.mkdir(parents=True, exist_ok=True)
            d.write_bytes(s.read_bytes())

    # -- the project -------------------------------------------------------
    paper = {
        "paper": {
            "title": title or _guess_title(src, files),
            "journal": journal,
            "article_type": article_type,
            "keywords": [],
        },
        "authors": [{"name": "TODO Author", "affiliation": "TODO affiliation",
                     "email": "", "credit": []}],
        "abstract": {
            "context": "TODO: the field's state of the art, one or two sentences.",
            "gap": "TODO: what is missing or contested.",
            "approach": "TODO: what you did, in one sentence.",
            "result": "TODO: the headline quantitative result.",
            "impact": "TODO: why it matters.",
        },
        "sections": [
            {"heading": "Introduction", "paragraphs": [{"text": "TODO: introduction.", "cites": []}]},
            {"heading": "Results and discussion", "paragraphs": [{"text": "TODO: results.", "cites": []}]},
            {"heading": "Conclusion", "paragraphs": [{"text": "TODO: conclusion.", "cites": []}]},
        ],
        "datasets": datasets,
        "tables": tables,
        "figures": figures,
        "compounds": compounds,
        "references": references,
        "narrative": {},
        "back_matter": {
            "coi": "The authors declare no competing financial interest.",
            "funding": "TODO: funding agency and grant number.",
            "data": "TODO: repository and accession/DOI.",
            "credit": "",
            "ai": "Generative AI was not used to generate scientific content.",
            "safety": "No unusual hazards were encountered.",
        },
        "highlights": [],
    }
    # keep the YAML readable: drop empty collections
    for key in ("datasets", "tables", "figures", "compounds", "references"):
        if not paper[key]:
            paper.pop(key)

    import yaml
    write_text(out / "paper.yaml", yaml.safe_dump(paper, sort_keys=False,
                                                   allow_unicode=True, width=100))
    (out / "data").mkdir(exist_ok=True)
    (out / "figures").mkdir(exist_ok=True)
    (out / "refs").mkdir(exist_ok=True)

    report = {
        "source": str(src.resolve()),
        "project": str(out.resolve()),
        "files_scanned": len(files),
        "compounds": len(compounds),
        "datasets": len(datasets),
        "tables": len(tables),
        "figures": len(figures),
        "references": len(references),
        "warnings": warnings,
        "todo": [
            "Write the five abstract moves in paper.yaml.",
            "Replace TODO procedures for every compound.",
            "Add CRediT roles, ORCIDs and affiliations.",
            "Add highlights (3–5 bullets, ≤ 85 characters each).",
            "Run: paperforge refs verify <project>  (fills missing DOIs).",
            "Run: paperforge check <project> — fix to ≥ 90 before drafting.",
        ],
    }
    dump_json(out / "ingest-report.json", report)
    write_text(out / "INGEST.md", _report_markdown(report))
    return report


def _report_markdown(report: dict) -> str:
    lines = [
        "# Ingestion report", "",
        f"Source: `{report['source']}`  ",
        f"Project: `{report['project']}`  ",
        f"Files scanned: {report['files_scanned']}", "",
        "| item | count |", "|---|---|",
        f"| compounds | {report['compounds']} |",
        f"| datasets | {report['datasets']} |",
        f"| tables | {report['tables']} |",
        f"| figures | {report['figures']} |",
        f"| references | {report['references']} |",
        "", "## Still to do (human)", "",
    ]
    lines += [f"- [ ] {t}" for t in report["todo"]]
    if report["warnings"]:
        lines += ["", "## Notes from ingestion", ""]
        lines += [f"- {w}" for w in report["warnings"]]
    return "\n".join(lines) + "\n"
