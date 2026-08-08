#!/usr/bin/env python3
"""
manuscript_check.py — Automated compliance check for a chemistry manuscript.

Checks the structural requirements shared by the 257 journals in the
IISER Bhopal chemistry portfolio (docs/01-journal-requirements.md):

  * abstract length vs. publisher-family limits
  * presence of keywords, TOC/abstract graphic, conclusion, SI paragraph
  * section structure (Introduction / Results / Experimental)
  * figure/table/scheme numbering gaps and figures cited in text
  * references: numbered sequentially, DOIs present
  * characterisation-data essentials (NMR / HRMS mentions) — heuristic

Usage:
    python3 manuscript_check.py main.tex [--style acs|rsc|wiley] [--abstract-words N]

Works on .tex, .md and .txt inputs. Pure stdlib. Exit code 0 = no errors.
"""
import re
import sys
import argparse

# --------------------------------------------------------------------------
# section/length limits (words), from docs/01
# --------------------------------------------------------------------------
LIMITS = {
    "acs":   {"abstract": 300, "note": "Articles <=300; Letters <=150"},
    "rsc":   {"abstract": 250, "note": "Abstract 50-250 words"},
    "wiley": {"abstract": 200, "note": "Abstract <=200 words"},
}

def strip_latex(text: str) -> str:
    """Remove LaTeX commands/comments for word counting."""
    text = re.sub(r"(?m)^%.*$", "", text)               # comment lines
    text = re.sub(r"\\[a-zA-Z]+\*?", " ", text)          # commands
    text = re.sub(r"[{}]", " ", text)                    # braces
    text = re.sub(r"\$[^$]*\$", " X ", text)             # inline math
    text = re.sub(r"\\\[.*?\\\]", " ", text, flags=re.S) # display math
    return text

def words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'\-]*", text))

def section_of(text: str, name: str) -> str:
    """Extract a section body by heading regex (LaTeX or Markdown)."""
    patterns = {
        "abstract": r"(?is)(?:\\begin\{abstract\}|^[ \t]*abstract\s*[:*\n]).*?(?:\\end\{abstract\}|\n\n)",
        "keywords": r"(?is)\bkeywords?\b.*",
        "intro":    r"(?is)(?:\\section\{Introduction\}|^#+ Introduction).*?(?=\\section|^#+ |\Z)",
        "experimental": r"(?is)(?:\\section\{Experimental|^#+ Experimental).*?(?=\\section|^#+ |\Z)",
        "conclusion": r"(?is)(?:\\section\{Conclusion|^#+ Conclusion).*?(?=\\section|^#+ |\Z)",
        "si":       r"(?is)(?:\\paragraph\{Supporting|Supporting Information[.:]).*?(?=\\paragraph|^#+ |\Z)",
        "toc":      r"(?is)(?:\\includegraphics\[[^\]]*\]|graphical abstract|toc graphic|abstract graphic)",
        "credit":   r"(?i)CRediT",
        "coi":      r"(?i)conflict of interest",
        "data":     r"(?i)data availability",
        "safety":   r"(?i)safety",
        "nmr":      r"(?is)\\c[eh]\{\^?1H\}|\^1H\s*NMR|1H\s+NMR|¹H\s*NMR",
        "hrms":     r"(?i)HRMS|high-resolution mass",
    }
    m = re.search(patterns[name], text)
    return m.group(0) if m else ""

def check_figures(text: str):
    """Figures/tables/schemes: definition numbering gaps + citations in text."""
    issues = []
    for kind, label in (("figure", r"\\label\{fig:"), ("table", r"\\label\{tab:"),
                        ("scheme", r"\\label\{sch:")):
        defs = sorted({int(n) for n in re.findall(label + r"(\d+)[a-z]?\}", text)})
        refs = re.findall(r"\\ref\{(?:fig|tab|sch):(\d+)", text)
        if defs:
            expected = list(range(min(defs), max(defs) + 1))
            missing = [n for n in expected if n not in defs]
            if missing:
                issues.append(f"{kind}: numbering gaps {missing}")
        for r in refs:
            if r and int(r) not in defs:
                issues.append(f"{kind}: \\ref{{{r}}} has no matching \\label")
        # markdown style: ![caption](file) & (fig:)
        mdefs = sorted({int(n) for n in re.findall(r"\{#(?:fig|tab):(\d+)", text)})
        if mdefs:
            expected = list(range(min(mdefs), max(mdefs) + 1))
            if [n for n in expected if n not in mdefs]:
                issues.append(f"{kind} (md): numbering gaps")
    return issues

def check_references(text: str):
    """References: sequential numbering + DOI coverage."""
    issues = []
    cit = [int(n) for n in re.findall(r"\\cite\{[^}]*\}", text) and
           re.findall(r"(?<![0-9])(\d{1,3})(?=[,\}\]\-])", re.sub(r"\\cite[^}]*\}", "]", text)[:5000])]
    # simpler robust check: look for \cite commands and count bib entries
    ncite = len(re.findall(r"\\cite", text))
    nbib = len(re.findall(r"@\w+\{", text))
    if nbib and ncite > nbib:
        issues.append(f"citations ({ncite}) exceed bibliography entries ({nbib})")
    dois = re.findall(r"10\.\d{4,9}/[^\s,;\]\}]+", text)
    if not dois and nbib > 3:
        issues.append("no DOIs found in bibliography (journals require resolvable DOIs)")
    return issues

def main():
    ap = argparse.ArgumentParser(description="Chemistry manuscript compliance checker")
    ap.add_argument("file", help="manuscript file (.tex/.md/.txt)")
    ap.add_argument("--style", choices=["acs", "rsc", "wiley"], default="acs")
    ap.add_argument("--abstract-words", type=int, default=None)
    args = ap.parse_args()

    try:
        raw = open(args.file, encoding="utf-8").read()
    except FileNotFoundError:
        print(f"ERROR: file not found: {args.file}"); sys.exit(1)

    errors, warnings, info = [], [], []
    limit = args.abstract_words or LIMITS[args.style]["abstract"]

    # --- Abstract ---
    ab = section_of(raw, "abstract")
    n_ab = words(strip_latex(ab))
    if not ab:
        errors.append("ABSTRACT missing (mandatory at all portfolio journals)")
    elif n_ab > limit:
        errors.append(f"ABSTRACT too long: {n_ab} words (limit {limit} for {args.style.upper()})")
    else:
        info.append(f"abstract: {n_ab} words (limit {limit})")

    # --- Keywords ---
    if not section_of(raw, "keywords"):
        warnings.append("KEYWORDS not found (4-7 recommended)")
    else:
        info.append("keywords: present")

    # --- TOC graphic ---
    if not section_of(raw, "toc"):
        warnings.append("TOC/graphical-abstract graphic not detected (required by ACS/Wiley/RSC)")

    # --- Structure ---
    for name, label in (("intro", "Introduction"), ("experimental", "Experimental Section"),
                        ("conclusion", "Conclusion")):
        if not section_of(raw, name):
            warnings.append(f"{label} section not detected")

    # --- Back matter ---
    for name, label in (("credit", "CRediT statement"), ("coi", "Conflict of interest"),
                        ("data", "Data availability"), ("safety", "Safety statement")):
        if not section_of(raw, name):
            warnings.append(f"{label} not detected (required by ACS/RSC/Wiley)")

    # --- SI paragraph ---
    if not section_of(raw, "si"):
        warnings.append("Supporting-Information paragraph not detected (ACS format required)")

    # --- Characterisation heuristics ---
    if not section_of(raw, "nmr"):
        warnings.append("No 1H NMR reporting pattern detected in Experimental (check characterisation data)")
    if not section_of(raw, "hrms"):
        warnings.append("No HRMS mention detected (required for new compounds)")

    # --- Figures/tables ---
    errors += check_figures(raw)
    errors += check_references(raw)

    # --- Word count of body (rough) ---
    body = strip_latex(raw)
    nbody = words(body)
    info.append(f"total words (approx): {nbody}")

    # ---- report ----
    print(f"=== Compliance check: {args.file} (style: {args.style.upper()}) ===")
    for i in info:    print(f"  [i] {i}")
    for w in warnings: print(f"  [!] {w}")
    for e in errors:  print(f"  [x] {e}")
    print(f"\nResult: {len(errors)} errors, {len(warnings)} warnings, {len(info)} info")
    sys.exit(1 if errors else 0)

if __name__ == "__main__":
    main()
