"""Rule-engine tests: a clean project must score high, broken ones must fail."""
import json
import shutil
from pathlib import Path

import pytest

from paperforge.checks import check_file, check_project, score
from paperforge.project import Project, ProjectError, scaffold

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "examples" / "demo-paper"


@pytest.fixture(scope="module")
def demo() -> Project:
    return Project.load(DEMO)


def codes(report) -> set[str]:
    return {i.code for i in report.issues}


# ---------------------------------------------------------------------------
# The shipped example must be submission-ready
# ---------------------------------------------------------------------------

def test_demo_is_submission_ready(demo):
    rep = check_project(demo, offline=True)
    sc = score(rep)
    assert sc["score"] >= 95, [i.message for i in rep.errors]
    assert not sc["blockers"]
    assert sc["grade"] in {"A", "A+"}


def test_demo_metrics(demo):
    rep = check_project(demo, offline=True)
    assert rep.metrics["compounds"] == 8
    assert rep.metrics["abstract_words"] <= 200     # Organic Letters
    assert rep.metrics["body_words"] <= 3000
    assert rep.metrics["references"] == 8


def test_demo_matches_other_journals(demo):
    """The same manuscript must be judged differently at a different journal."""
    angew = check_project(demo, journal="Angewandte Chemie International Edition",
                          article_type="communication", offline=True)
    # Angew wants a 5.5 x 5.0 cm TOC, the demo graphic is 8.25 x 4.45 cm
    assert any(i.code == "TOC-ASPECT" for i in angew.issues)
    assert any(i.code == "JNL-PAGES" for i in angew.issues)
    ol = check_project(demo, journal="Organic Letters", article_type="letter", offline=True)
    assert not any(i.code == "TOC-ASPECT" for i in ol.issues)


# ---------------------------------------------------------------------------
# Broken variants: each must be caught with the right code
# ---------------------------------------------------------------------------

def _clone(tmp_path, mutate) -> Project:
    dest = tmp_path / "paper"
    shutil.copytree(DEMO, dest)
    data = json.loads(json.dumps(_yaml_to_json(dest / "paper.yaml")))
    mutate(data)
    (dest / "paper.yaml").write_text(json.dumps(data), encoding="utf-8")
    return Project.load(dest)


def _yaml_to_json(path: Path) -> dict:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_wrong_exact_mass_is_caught(tmp_path):
    def mutate(d):
        d["compounds"][0]["hrms_calcd"] = 256.0427   # the v1 template's impossible value
    rep = check_project(_clone(tmp_path, mutate), offline=True)
    assert "CHEM-HRMS-CALCD" in codes(rep)
    assert score(rep)["blockers"]


def test_wrong_yield_mass_is_caught(tmp_path):
    def mutate(d):
        d["compounds"][1]["mass_g"] = 0.999
    rep = check_project(_clone(tmp_path, mutate), offline=True)
    assert "CHEM-YIELD-MASS" in codes(rep)


def test_over_long_abstract_is_caught(tmp_path):
    def mutate(d):
        d["abstract"]["results"].append("word " * 300)
    rep = check_project(_clone(tmp_path, mutate), offline=True)
    assert "STR-ABSTRACT-LONG" in codes(rep)


def test_hype_in_title_is_caught(tmp_path):
    def mutate(d):
        d["paper"]["title"] = "A Novel First-Ever Unprecedented Catalyst for Everything"
    rep = check_project(_clone(tmp_path, mutate), offline=True)
    assert "STR-TITLE-HYPE" in codes(rep)


def test_missing_coi_and_data_statement_are_caught(tmp_path):
    def mutate(d):
        d["back_matter"].pop("coi")
        d["back_matter"].pop("data_availability")
    rep = check_project(_clone(tmp_path, mutate), offline=True)
    assert "ETH-COI" in codes(rep)
    assert "ETH-DATA" in codes(rep)


def test_data_on_request_is_a_blocker(tmp_path):
    def mutate(d):
        d["back_matter"]["data_availability"] = "Data are available on request from the authors."
    rep = check_project(_clone(tmp_path, mutate), offline=True)
    issue = next(i for i in rep.issues if i.code == "ETH-DATA-REQUEST")
    assert issue.data.get("critical")


def test_unknown_citation_key_is_a_blocker(tmp_path):
    def mutate(d):
        d["sections"][0]["paragraphs"][0]["cites"].append("ghost2024fake")
    rep = check_project(_clone(tmp_path, mutate), offline=True)
    assert "REF-MISSING-KEY" in codes(rep)


def test_ungrounded_abstract_number_is_flagged(tmp_path):
    def mutate(d):
        d["abstract"]["results"].append("The reaction proceeded in 1234% yield.")
    rep = check_project(_clone(tmp_path, mutate), offline=True)
    assert "EVI-UNGROUNDED-ABSTRACT" in codes(rep)


def test_crystal_without_ccdc_is_a_blocker(tmp_path):
    def mutate(d):
        d["compounds"][0]["crystal"] = True
    rep = check_project(_clone(tmp_path, mutate), offline=True)
    assert "EVI-CCDC" in codes(rep)


def test_missing_compound_data_is_caught(tmp_path):
    def mutate(d):
        d["compounds"][2].pop("nmr_13c")
        d["compounds"][2].pop("hrms_found")
        d["compounds"][2].pop("hrms_calcd")
    rep = check_project(_clone(tmp_path, mutate), offline=True)
    assert "EVI-NMR13C" in codes(rep)
    assert "EVI-HRMS" in codes(rep)


def test_credit_roles_required(tmp_path):
    def mutate(d):
        for a in d["authors"]:
            a["credit"] = []
    rep = check_project(_clone(tmp_path, mutate), offline=True)
    assert "ETH-CREDIT" in codes(rep)


def test_missing_figure_file_is_an_error(tmp_path):
    def mutate(d):
        d["figures"][0]["file"] = "figures/does_not_exist.png"
    rep = check_project(_clone(tmp_path, mutate), offline=True)
    assert "FIG-MISSING" in codes(rep)


def test_low_dpi_figure_is_an_error(tmp_path):
    from PIL import Image

    def mutate(d):
        d["figures"][1]["file"] = "figures/lowres.png"
    paper = _clone(tmp_path, mutate)
    Image.new("RGB", (400, 300), "white").save(paper.root / "figures" / "lowres.png", dpi=(72, 72))
    paper = Project.load(paper.root)
    rep = check_project(paper, offline=True)
    assert "FIG-DPI" in codes(rep)


def test_toc_required_and_sized(demo):
    rep = check_project(demo, journal="Organic Letters", article_type="letter", offline=True)
    assert "TOC-DPI" not in codes(rep)          # demo TOC is 975×525 px = 300 dpi at 8.25 cm
    rep2 = check_project(demo, journal="Chemical Communications", article_type="communication", offline=True)
    assert "TOC-DPI" in codes(rep2)             # ChemComm demands 600 dpi


def test_safety_statement_required(tmp_path):
    def mutate(d):
        d["back_matter"].pop("safety")
    rep = check_project(_clone(tmp_path, mutate), offline=True)
    assert "ETH-SAFETY" in codes(rep)


def test_highlights_required_for_elsevier(tmp_path):
    def strip_highlights(d):
        d.pop("highlights", None)

    rep = check_project(_clone(tmp_path, strip_highlights),
                        journal="Journal of Molecular Structure", offline=True)
    assert "JNL-HIGHLIGHTS" in codes(rep)


# ---------------------------------------------------------------------------
# Legacy / file-based checker (the v1 input formats)
# ---------------------------------------------------------------------------

def test_file_checker_markdown(tmp_path):
    md = tmp_path / "paper.md"
    md.write_text("""# A Study of Something

## Abstract
We report a thing. It works well.

## Introduction
Text [1].

## Results and Discussion
Data.

## Experimental
NMR.

## Conclusion
Done.
""", encoding="utf-8")
    rep = check_file(md, journal="Organic Letters", article_type="article")
    assert "STR-RESULTS" not in codes(rep)


def test_file_checker_docx(tmp_path, demo):
    from paperforge.render import to_docx
    from paperforge.draft import compose

    out = to_docx(compose(demo), tmp_path / "m.docx", demo)
    rep = check_file(out, journal="Organic Letters", article_type="letter")
    assert not any(i.code == "FILE-READ" for i in rep.issues)
    assert rep.metrics["abstract_words"] > 50


def test_file_checker_binary_does_not_crash(tmp_path):
    bad = tmp_path / "x.tex"
    bad.write_bytes(b"\x00\xff\xfe garbage")
    rep = check_file(bad)
    assert rep.issues          # reports something instead of raising


def test_missing_file_reports_cleanly(tmp_path):
    rep = check_file(tmp_path / "nope.tex")
    assert any(i.code == "FILE-READ" for i in rep.issues)


# ---------------------------------------------------------------------------
# Project schema
# ---------------------------------------------------------------------------

def test_scaffold_and_load(tmp_path):
    path = scaffold(tmp_path / "p", title="Test manuscript")
    project = Project.load(path)
    assert project.title == "Test manuscript"


def test_missing_title_rejected(tmp_path):
    path = scaffold(tmp_path / "p2")
    data = __import__("yaml").safe_load(path.read_text())
    data["paper"].pop("title")
    path.write_text(json.dumps(data))
    with pytest.raises(ProjectError):
        Project.load(path)


def test_missing_journal_rejected(tmp_path):
    path = scaffold(tmp_path / "p3")
    data = __import__("yaml").safe_load(path.read_text())
    data["paper"].pop("journal")
    (tmp_path / "p3" / "paper.json").write_text(json.dumps(data))
    (tmp_path / "p3" / "paper.yaml").unlink()
    with pytest.raises(ProjectError):
        Project.load(tmp_path / "p3")


def test_empty_project_scores_low(tmp_path):
    path = scaffold(tmp_path / "empty")
    project = Project.load(path)
    rep = check_project(project, offline=True)
    sc = score(rep)
    assert sc["score"] < 60
    assert sc["status"] == "not-ready"
    assert sc["capped_by_blockers"]


def test_blank_lines_between_sections_are_not_double_spaces(demo):
    """Section breaks produce \n\n; that is layout, not a doubled space."""
    from paperforge.checks import Report, check_style
    from paperforge.journals import profile

    rep = Report(profile=profile("Organic Letters", "letter"), source="prose")
    prose = "First paragraph ends here.\n\nSecond paragraph starts here with a subsection.\n\n\nThird."
    check_style(demo, rep.profile, rep, prose)
    assert not any(i.code == "STY-SPACE" for i in rep.issues)

    rep2 = Report(profile=profile("Organic Letters", "letter"), source="prose")
    check_style(demo, rep2.profile, rep2, "A sentence with  two spaces in it.")
    assert any(i.code == "STY-SPACE" for i in rep2.issues)


# ---------------------------------------------------------------------------
# Legacy / file-based checker (the v1 input formats)
# ---------------------------------------------------------------------------

def test_file_checker_markdown(tmp_path):
    md = tmp_path / "paper.md"
    md.write_text("""# A Study of Something

## Abstract
We report a thing. It works well.

## Introduction
Text [1].

## Results and Discussion
Data.

## Experimental
NMR.

## Conclusion
Done.
""", encoding="utf-8")
    rep = check_file(md, journal="Organic Letters", article_type="article")
    assert "STR-RESULTS" not in codes(rep)


def test_file_checker_docx(tmp_path, demo):
    from paperforge.render import to_docx
    from paperforge.draft import compose

    out = to_docx(compose(demo), tmp_path / "m.docx", demo)
    rep = check_file(out, journal="Organic Letters", article_type="letter")
    assert not any(i.code == "FILE-READ" for i in rep.issues)
    assert rep.metrics["abstract_words"] > 50


def test_file_checker_binary_does_not_crash(tmp_path):
    bad = tmp_path / "x.tex"
    bad.write_bytes(b"\x00\xff\xfe garbage")
    rep = check_file(bad)
    assert rep.issues          # reports something instead of raising


def test_missing_file_reports_cleanly(tmp_path):
    rep = check_file(tmp_path / "nope.tex")
    assert any(i.code == "FILE-READ" for i in rep.issues)


# ---------------------------------------------------------------------------
# Project schema
# ---------------------------------------------------------------------------

def test_scaffold_and_load(tmp_path):
    path = scaffold(tmp_path / "p", title="Test manuscript")
    project = Project.load(path)
    assert project.title == "Test manuscript"


def test_missing_title_rejected(tmp_path):
    path = scaffold(tmp_path / "p2")
    data = __import__("yaml").safe_load(path.read_text())
    data["paper"].pop("title")
    path.write_text(json.dumps(data))
    with pytest.raises(ProjectError):
        Project.load(path)


def test_missing_journal_rejected(tmp_path):
    path = scaffold(tmp_path / "p3")
    data = __import__("yaml").safe_load(path.read_text())
    data["paper"].pop("journal")
    (tmp_path / "p3" / "paper.json").write_text(json.dumps(data))
    (tmp_path / "p3" / "paper.yaml").unlink()
    with pytest.raises(ProjectError):
        Project.load(tmp_path / "p3")


def test_empty_project_scores_low(tmp_path):
    path = scaffold(tmp_path / "empty")
    project = Project.load(path)
    rep = check_project(project, offline=True)
    sc = score(rep)
    assert sc["score"] < 60
    assert sc["status"] == "not-ready"
    assert sc["capped_by_blockers"]



def test_blank_lines_between_sections_are_not_double_spaces(demo):
    """Section breaks produce newlines; that is layout, not a doubled space."""
    from paperforge.checks import Report, check_style
    from paperforge.journals import profile

    prof = profile("Organic Letters", "letter")
    rep = Report(profile=prof, source="prose")
    prose = ("First paragraph ends here.\n\nSecond paragraph starts here.\n\n\nThird.")
    check_style(demo, prof, rep, prose)
    assert not any(i.code == "STY-SPACE" for i in rep.issues)

    rep2 = Report(profile=prof, source="prose")
    check_style(demo, prof, rep2, "A sentence with  two spaces in it.")
    assert any(i.code == "STY-SPACE" for i in rep2.issues)


# ---------------------------------------------------------------------------
# v2.1 fixes found by the second (organometallic) example
# ---------------------------------------------------------------------------

def test_dbe_is_skipped_for_organometallics():
    from paperforge.chem import check_formula, dbe_applicable

    assert not dbe_applicable("C25H19IrN4")
    assert not dbe_applicable("K4[Fe(CN)6]")
    assert dbe_applicable("C14H10N2O")
    codes = [i.code for i in check_formula("C25H19IrN4")]
    assert "CHEM-DBE-METAL" in codes
    assert "CHEM-DBE-FRACTION" not in codes


def test_scheme_numbering_is_independent_of_figures(tmp_path):
    """A scheme listed before the figures is Scheme 1, not display item 1."""
    def reorder(d):
        d["figures"] = sorted(d["figures"], key=lambda f: 0 if f.get("kind") == "scheme" else 1)

    rep = check_project(_clone(tmp_path, reorder), offline=True)
    assert not any(i.code == "FIG-UNCITED" for i in rep.issues)


def test_figure_panel_letters_count_as_citations(tmp_path):
    """'Figure 1A' must satisfy the citation requirement for Figure 1."""
    def cite_panels(d):
        for sec in d["sections"]:
            for para in sec.get("paragraphs", []):
                if isinstance(para, dict) and "text" in para:
                    para["text"] = "The quenching data (Figure 1A) and the DFT profile (Figure 2) agree."

    rep = check_project(_clone(tmp_path, cite_panels), offline=True)
    assert not any(i.code == "FIG-UNCITED" for i in rep.issues)


def test_repeated_info_notes_are_merged(demo):
    from paperforge.checks import check_project

    odd = check_project(demo, journal="Dalton Transactions", offline=True)
    dbe = [i for i in odd.issues if i.code == "CHEM-DBE-METAL"]
    assert len(dbe) <= 1


def test_dataset_summaries_vary_phrasing(tmp_path):
    from paperforge.draft import dataset_summaries
    from paperforge.project import Project

    project = Project.load(DEMO)
    ds = {"id": "x", "file": "data/scope.csv"}
    out = dataset_summaries(project, ds)
    assert out
    assert not all(s.startswith("ranged") for s in out)
