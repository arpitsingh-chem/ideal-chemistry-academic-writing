"""Small dependency-free helpers used across PaperForge."""
from __future__ import annotations

import hashlib
import json
import os
import re
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# File IO
# ---------------------------------------------------------------------------

TEXT_SUFFIXES = {".tex", ".md", ".txt", ".rst", ".bib", ".csv", ".json", ".yaml", ".yml", ".toml"}
OFFICE_SUFFIXES = {".docx", ".xlsx", ".pptx"}


class FileReadError(RuntimeError):
    pass


def read_text(path: str | os.PathLike) -> str:
    """Read a text-ish file.

    Supports plain text and OOXML (``.docx``/``.xlsx``/``.pptx``) by extracting
    the XML text nodes.  Raises :class:`FileReadError` with a helpful message
    instead of a raw UnicodeDecodeError (a bug in v1 of this toolkit).
    """
    p = Path(path)
    if not p.exists():
        raise FileReadError(f"file not found: {p}")
    suffix = p.suffix.lower()

    if suffix == ".docx":
        return _docx_text(p)
    if suffix == ".xlsx":
        return _xlsx_text(p)
    if suffix == ".pptx":
        return _office_xml_text(p, "ppt/slides/slide*.xml")

    data = p.read_bytes()
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise FileReadError(
        f"cannot decode {p} as text (binary file?). "
        "Supported: .tex .md .txt .bib .csv .json .yaml .docx .xlsx .pptx"
    )


def _office_xml_text(path: Path, pattern: str) -> str:
    try:
        import zipfile as _z

        with _z.ZipFile(path) as z:
            names = sorted(n for n in z.namelist() if _match_glob(n, pattern))
            chunks = []
            for n in names:
                xml = z.read(n).decode("utf-8", "ignore")
                xml = re.sub(r"</w:p>", "\n", xml)
                xml = re.sub(r"<[^>]+>", " ", xml)
                chunks.append(re.sub(r"[ \t]+", " ", xml))
            return "\n".join(chunks)
    except (zipfile.BadZipFile, KeyError, OSError) as exc:
        raise FileReadError(f"cannot read Office file {path}: {exc}") from exc


def _match_glob(name: str, pattern: str) -> bool:
    """Tiny glob supporting a single '*' (enough for slide*.xml)."""
    if "*" not in pattern:
        return name == pattern
    pre, post = pattern.split("*", 1)
    return name.startswith(pre) and name.endswith(post)


def _docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
    except (zipfile.BadZipFile, KeyError, OSError) as exc:
        raise FileReadError(f"cannot read .docx {path}: {exc}") from exc
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab[^>]*/>", "\t", xml)
    xml = re.sub(r"<[^>]+>", " ", xml)
    text = re.sub(r"[ \t]+", " ", xml)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def _xlsx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as z:
            shared = []
            if "xl/sharedStrings.xml" in z.namelist():
                sx = z.read("xl/sharedStrings.xml").decode("utf-8", "ignore")
                shared = [re.sub(r"<[^>]+>", " ", si).strip() for si in re.findall(r"<si>(.*?)</si>", sx, re.S)]
            rows = []
            for name in sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet")):
                xml = z.read(name).decode("utf-8", "ignore")
                for row in re.findall(r"<row[^>]*>(.*?)</row>", xml, re.S):
                    cells = []
                    for c in re.findall(r"<c[^>]*?(?:t=\"(\w+)\")?[^>]*>(.*?)</c>", row, re.S):
                        typ, body = c
                        v = re.sub(r"<[^>]+>", "", body)
                        if typ == "s" and v.strip().isdigit():
                            idx = int(v)
                            v = shared[idx] if idx < len(shared) else v
                        cells.append(v.strip())
                    rows.append(",".join(cells))
            return "\n".join(rows)
    except (zipfile.BadZipFile, KeyError, OSError) as exc:
        raise FileReadError(f"cannot read .xlsx {path}: {exc}") from exc


def write_text(path: str | os.PathLike, text: str) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")
    return p


def sha256_file(path: str | os.PathLike) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: str | os.PathLike, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def dump_json(path: str | os.PathLike, obj) -> Path:
    return write_text(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Text processing
# ---------------------------------------------------------------------------

LATEX_CMD = re.compile(r"\\[a-zA-Z@]+\*?(?:\[[^\]]*\])?(?:\{[^{}]*\})?")


def strip_latex(text: str) -> str:
    """Remove LaTeX markup while keeping human-visible words.

    v1 removed commands *and* their arguments inconsistently, which corrupted
    word counts.  This version is conservative: it drops math, comments and
    commands, keeps the contents of ``\\section{...}``-style arguments by first
    unwrapping braces.
    """
    text = re.sub(r"(?m)(?<!\\)%.*$", "", text)          # comments
    text = re.sub(r"\\\[.*?\\\]", " ", text, flags=re.S)  # display math
    text = re.sub(r"\\\(.*?\\\)", " ", text, flags=re.S)  # inline math
    text = re.sub(r"\$\$.*?\$\$", " ", text, flags=re.S)
    text = re.sub(r"\$[^$\n]*\$", " ", text)
    # Keep the *contents* of headings / captions: `\paragraph{Data availability.}`
    # is prose to a reader and to a journal, even though it is a command.
    def _unwrap(m: re.Match) -> str:
        return " " + m.group(2) + " "

    text = re.sub(
        r"\\(?:part|chapter|section|subsection|subsubsection|paragraph|subparagraph|"
        r"title|caption|thanks)\*?(?:\[[^\]]*\])?\{([^{}]*)\}",
        lambda m: " " + m.group(1) + " ", text)
    # Inline formatting and \ce{} carry visible content (compound labels,
    # formulae): unwrap them instead of deleting the argument.
    for _ in range(2):  # two passes handle the common one-level nesting
        new = re.sub(
            r"\\(?:textbf|textit|textsl|textsc|texttt|textsf|textrm|textnormal|emph|"
            r"underline|mbox|text|ce|mathrm)\*?(?:\[[^\]]*\])?\{([^{}]*)\}",
            lambda m: " " + m.group(1) + " ", text)
        if new == text:
            break
        text = new
    text = re.sub(r"\\(?:documentclass|usepackage|bibliographystyle|graphicspath|newcommand|renewcommand)\s*(?:\[[^\]]*\])?\s*\{[^{}]*\}", " ", text)
    text = re.sub(r"\\(?:title|author|date|maketitle|caption|label|ref|eqref|cite\w*|citep|citet|includegraphics|bibliography|end|begin)\b\*?(?:\[[^\]]*\])?(?:\{[^{}]*\})?", " ", text)
    text = LATEX_CMD.sub(" ", text)
    text = re.sub(r"[{}]", " ", text)
    text = text.replace("~", " ").replace("\\,", " ").replace("\\;", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
MARKDOWN_IMG = re.compile(r"!\[[^\]]*\]\([^)]*\)")
MD_FENCE = re.compile(r"```.*?```", re.S)


def strip_markdown(text: str) -> str:
    text = MD_FENCE.sub(" ", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"(?m)^\s*>\s?", "", text)
    text = re.sub(r"(?m)^\s*[-*+]\s+", "", text)
    text = re.sub(r"(?m)^\s*\d+[.)]\s+", "", text)
    text = MARKDOWN_IMG.sub(" ", text)
    text = MARKDOWN_LINK.sub(r"\1", text)
    text = re.sub(r"(\*\*|__|\*|_|`|~~)", "", text)
    text = re.sub(r"\{#[^}]*\}", "", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’\-]*")


def word_count(text: str) -> int:
    """Count words the way journals do (whitespace tokens containing a letter/digit)."""
    return len(WORD_RE.findall(text))


def visible_text(text: str, name: str = "") -> str:
    """Return reading text for .tex/.md/.txt/OOXML content."""
    suffix = Path(name).suffix.lower() if name else ""
    if suffix == ".tex" or "\\documentclass" in text or "\\section{" in text:
        return strip_latex(text)
    if suffix in {".md", ".markdown"} or re.search(r"(?m)^#{1,6}\s", text):
        return strip_markdown(text)
    return re.sub(r"\s+", " ", text).strip()


def sentences(text: str) -> list[str]:
    """Split prose into sentences, protecting common chemistry abbreviations."""
    protected = {
        "e.g.": "eg<DOT>", "i.e.": "ie<DOT>", "et al.": "etal<DOT>", "cf.": "cf<DOT>",
        "vs.": "vs<DOT>", "Fig.": "Fig<DOT>", "Figs.": "Figs<DOT>", "Eq.": "Eq<DOT>",
        "Ref.": "Ref<DOT>", "approx.": "approx<DOT>", "ca.": "ca<DOT>", "no.": "no<DOT>",
        "ppm.": "ppm<DOT>", "mol.": "mol<DOT>", "equiv.": "equiv<DOT>",
    }
    t = text
    for k, v in protected.items():
        t = t.replace(k, v)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(\"“])", t)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if re.fullmatch(r"(Fig|Figs|Eq|Ref|Table|Scheme)\.", p):
            continue
        for k, v in protected.items():
            p = p.replace(v, k)
        if len(WORD_RE.findall(p)) >= 2:
            out.append(p)
    return out


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def similarity(a: str, b: str) -> float:
    """Jaccard similarity over word trigrams (cheap near-duplicate detector)."""
    ta = set(_trigrams(a.lower()))
    tb = set(_trigrams(b.lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _trigrams(text: str):
    words = re.findall(r"[a-z0-9]+", text)
    return [" ".join(words[i : i + 3]) for i in range(max(0, len(words) - 2))]


def slugify(text: str, max_len: int = 60) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:max_len].rstrip("-")
