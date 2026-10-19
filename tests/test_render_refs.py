"""Renderer, reference and end-to-end pipeline tests."""
import json
import re
from pathlib import Path

import pytest

from paperforge.draft import compose, cover_letter, dataset_summaries, experimental_block
from paperforge.project import Project
from paperforge.refs import (
    RefCache, citation_key, check_bib_file, fetch_crossref, is_retracted,
    normalize_doi, parse_bibtex, to_bibtex, valid_doi_syntax,
)
from paperforge.render import human_header, tex_escape, to_docx, to_latex, to_markdown

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "examples" / "demo-paper"


@pytest.fixture(scope="module")
def demo() -> Project:
    return Project.load(DEMO)


# ---------------------------------------------------------------------------
# Text escaping
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("50% yield", r"50\% yield"),
    ("C–H activation", "C--H activation"),
    ("cm⁻¹", r"cm$^{-1}$"),
    ("¹H NMR", r"\ce{^1H} NMR"),
    ("¹³C NMR", r"\ce{^{13}C} NMR"),
    ("C14H10N2O", r"\ce{C14H10N2O}"),
    (r"a\b", r"a\textbackslash{}b"),
    ("K_SV", r"K\_SV"),
    ("mM−1", r"mM$^{-1}$"),
])
def test_tex_escape(raw, expected):
    assert tex_escape(raw) == expected


def test_no_internal_markers_leak(demo):
    doc = compose(demo)
    tex = to_latex(doc, demo)
    assert "@@" not in tex
    md = to_markdown(doc)
    assert "@@" not in md


def test_table_headers_humanised():
    assert human_header("yield_percent") == "Yield (%)"
    assert human_header("conversion_percent") == "Conversion (%)"
    assert human_header("aryl_group") == "Aryl group"


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def test_markdown_structure(demo):
    md = to_markdown(compose(demo))
    assert md.startswith("# Visible-Light")
    for heading in ("## Abstract", "## Introduction", "## Results and Discussion", "## Conclusion", "## References"):
        assert heading in md
    assert "1. " in md and "DOI:" in md


def test_latex_is_complete(demo):
    tex = to_latex(compose(demo), demo)
    assert tex.count(r"\begin{document}") == 1
    assert tex.count(r"\end{document}") == 1
    assert r"\begin{abstract}" in tex
    assert r"\bibliography{refs/refs}" in tex
    # balanced braces (rough check that ignores escaped braces)
    stripped = re.sub(r"\\[{}]", "", tex)
    assert stripped.count("{") == stripped.count("}")


def test_si_latex_contains_every_compound(demo):
    si = to_latex(compose(demo), demo, si=True)
    for c in demo.compounds:
        assert f"Compound {c.id}" in si


def test_docx_roundtrip(demo, tmp_path):
    out = to_docx(compose(demo), tmp_path / "ms.docx", demo)
    assert out.exists() and out.stat().st_size > 10_000
    import zipfile

    with zipfile.ZipFile(out) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    assert "Visible-Light" in xml
    assert "Compound 3a" in xml


def test_cover_letter(demo):
    letter = cover_letter(demo, compose(demo))
    assert "Organic Letters" in letter
    assert "not under consideration" in letter
    assert "Yours sincerely" in letter


# ---------------------------------------------------------------------------
# Generated content is derived from data, not invented
# ---------------------------------------------------------------------------

def test_dataset_summary_is_computed(demo):
    ds = next(d for d in demo.datasets if d["id"] == "scope")
    s = dataset_summaries(demo, ds)
    assert any("61%" in x and "94%" in x for x in s)


def test_experimental_block_uses_records(demo):
    c = demo.compounds[0]
    block = experimental_block(c)
    assert c.formula in block["text"]
    assert f"{c.hrms_calcd:.4f}" in block["text"]
    assert ".." not in block["text"]


# ---------------------------------------------------------------------------
# References
# ---------------------------------------------------------------------------

def test_doi_normalisation():
    assert normalize_doi("https://doi.org/10.1021/jacs.1c01020") == "10.1021/jacs.1c01020"
    assert normalize_doi("doi: 10.1039/D4CC01234A.") == "10.1039/D4CC01234A"
    assert valid_doi_syntax("10.1021/jacs.1c01020")
    assert not valid_doi_syntax("jacs.1c01020")


def test_bibtex_roundtrip():
    rec = {"authors": ["Doe, Jane", "Roe, Richard"], "title": "A 50% Test",
           "journal": "J. Test", "year": 2024, "volume": "1", "pages": "1-2",
           "doi": "10.1000/test"}
    bib = to_bibtex(rec)
    parsed = parse_bibtex(bib)
    assert parsed and parsed[0]["title"] == "A 50% Test"
    assert parsed[0]["doi"] == "10.1000/test"


def test_citation_key_style():
    assert citation_key({"authors": ["Patil, Nitin T."], "year": 2021,
                         "title": "Divergent Gold Catalysis"}) == "patil2021divergent"


def test_retraction_detection():
    assert is_retracted({"relation": {"is-retracted-by": [{"id": "x"}]}})
    assert is_retracted({"type": "retraction"})
    assert not is_retracted({"type": "journal-article"})


def test_bib_file_checks(tmp_path):
    bib = tmp_path / "x.bib"
    bib.write_text(to_bibtex({"authors": ["A, B"], "title": "T", "year": 2020, "doi": "10.1/a"}) +
                   "\n\n" + to_bibtex({"authors": ["A, B"], "title": "T2", "year": 2020, "doi": "10.1/a"}) +
                   "\n\n" + to_bibtex({"authors": ["C, D"], "title": "NoDOI"}),
                   encoding="utf-8")
    res = check_bib_file(bib)
    assert res["duplicates"] == ["10.1/a"]
    assert res["missing_year"] == ["cnodoi"]


@pytest.mark.network
def test_crossref_live():
    cache = RefCache("/tmp/paperforge-test-cache")
    res = fetch_crossref("10.1021/acs.chemrev.6b00057", cache=cache)
    assert res.ok
    assert "Photoredox" in res.data["title"]
    assert res.data["year"] == 2016
    # cached second call must not hit the network
    again = fetch_crossref("10.1021/acs.chemrev.6b00057", cache=cache, offline=True)
    assert again.ok and again.status == "cached"


@pytest.mark.network
def test_crossref_rejects_bogus_doi():
    res = fetch_crossref("10.9999/definitely-not-a-real-doi-xyz")
    assert not res.ok


def test_visible_text_keeps_heading_and_paragraph_text():
    from paperforge.util import visible_text

    tex = (r"\section{Results and discussion}We made \textbf{3a}."
           "\n" r"\paragraph{Data availability.} All data are in the SI."
           "\n" r"\caption{Scope of the reaction.}")
    text = visible_text(tex, "x.tex")
    assert "Results and discussion" in text
    assert "Data availability" in text
    assert "Scope of the reaction" in text
    assert "3a" in text
