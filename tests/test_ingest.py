"""Folder → project ingestion."""
import json
import shutil
from pathlib import Path

import pytest

from paperforge.checks import check_project
from paperforge.draft import compose
from paperforge.ingest import ingest
from paperforge.project import Project

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "examples" / "demo-paper"


@pytest.fixture()
def research_folder(tmp_path: Path) -> Path:
    src = tmp_path / "lab-folder"
    src.mkdir()
    (src / "compounds.csv").write_text(
        "id,name,formula,mw,mmol,mass_g,yield_percent,hrms_calcd,hrms_found,hrms_adduct\n"
        "3a,3-(phenyl)quinoxalin-2(1H)-one,C14H10N2O,222.25,0.50,0.104,94,223.0866,223.0869,[M+H]+\n"
        "3b,3-(4-methylphenyl)quinoxalin-2(1H)-one,C15H12N2O,236.27,0.50,0.104,88,237.1022,237.1024,[M+H]+\n",
        encoding="utf-8")
    (src / "optimisation.csv").write_text(
        "entry,conversion,selectivity\n1,88,94\n2,76,91\n3,92,96\n", encoding="utf-8")
    (src / "title.txt").write_text("A Folder-Derived Paper\n", encoding="utf-8")
    shutil.copy(DEMO / "figures" / "fig1_mechanism.png", src / "fig1_mechanism.png")
    shutil.copy(DEMO / "refs" / "refs.bib", src / "library.bib")
    return src


def test_ingest_builds_valid_project(research_folder, tmp_path):
    out = tmp_path / "proj"
    report = ingest(research_folder, out, journal="Organic Letters")
    assert report["compounds"] == 2
    assert report["datasets"] == 1
    assert report["figures"] == 1
    assert report["references"] >= 8
    project = Project.load(out)
    assert project.title == "A Folder-Derived Paper"
    assert len(project.compounds) == 2
    assert project.compounds[0].formula == "C14H10N2O"
    assert (out / "ingest-report.json").exists()
    assert (out / "INGEST.md").read_text(encoding="utf-8").startswith("# Ingestion report")


def test_ingested_project_renders_experimental(research_folder, tmp_path):
    out = tmp_path / "proj"
    ingest(research_folder, out)
    doc = compose(Project.load(out))
    def _text(para) -> str:
        if isinstance(para, str):
            return para
        if isinstance(para, dict):
            return str(para.get("text", ""))
        return getattr(para, "text", "")

    text = "\n".join(_text(p) for sec in doc.sections for p in sec.paragraphs)
    assert "Compound 3a" in text
    assert "223.0866" in text


def test_ingest_report_is_json_serialisable(research_folder, tmp_path):
    report = ingest(research_folder, tmp_path / "proj")
    assert json.loads(json.dumps(report))["compounds"] == 2


def test_ingest_unknown_folder_is_empty_but_valid(tmp_path):
    src = tmp_path / "empty"
    src.mkdir()
    report = ingest(src, tmp_path / "proj")
    assert report["compounds"] == 0
    project = Project.load(tmp_path / "proj")
    rep = check_project(project, offline=True)
    assert rep.issues  # clearly not ready


def test_string_years_do_not_crash_checks(research_folder, tmp_path):
    """BibTeX years arrive as strings; REF-RECENCY must not raise."""
    out = tmp_path / "proj"
    ingest(research_folder, out)
    project = Project.load(out)
    rep = check_project(project, offline=True)
    assert rep.metrics["references"] >= 8


def test_ingest_cli(research_folder, tmp_path, capsys):
    from paperforge.cli import main

    code = main(["ingest", str(research_folder), "--out", str(tmp_path / "proj")])
    assert code == 0
    assert "compounds 2" in capsys.readouterr().out


# --- v2.3: decimal commas and Latin-1 exports --------------------------------

def test_decimal_comma_values_are_not_multiplied():
    from paperforge.ingest import _number

    assert _number("89,5") == 89.5
    assert _number("0,400") == 0.4        # leading zero is never a thousands group
    assert _number("162,21") == 162.21
    assert _number("1,234") == 1234.0     # three-digit group after a real digit count
    assert _number("1.234,5") == 1234.5
    assert _number("12,000") == 12000.0
    assert _number("") is None


def test_latin1_export_is_read_not_dropped(tmp_path):
    src = tmp_path / "lab"
    src.mkdir()
    body = ("id;name;formula;mw;mmol;mass_g;yield_percent;hrms_calcd;hrms_found;hrms_adduct\n"
            "P1;4-(thiophen-2-yl)pyrimidine;C8H6N2S;162,21;0,400;0,058;89,5;163,0324;163,0327;[M+H]+\n"
            "P2;4-(5-methylthiophen-2-yl)pyrimidine;C9H8N2S;176,24;0,400;0,049;70,0;177,0481;177,0484;[M+H]+\n")
    (src / "compounds.csv").write_bytes(b"\xef\xbb\xbf" + body.encode("latin-1"))
    report = ingest(src, tmp_path / "p")
    assert report["compounds"] == 2, report
    project = Project.load(tmp_path / "p")
    c = project.compounds[0]
    assert c.mmol == 0.4 and c.yield_percent == 89.5        # not 400 / 895
    assert c.mw == 162.21
