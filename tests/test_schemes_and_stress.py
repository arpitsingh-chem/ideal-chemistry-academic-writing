"""Scheme drawing (optional RDKit) and adversarial / limit tests."""
import json
import random
import shutil
import string
import time
from pathlib import Path

import pytest

from paperforge.checks import check_file, check_project, score
from paperforge.project import Project
from paperforge.render import to_latex, to_markdown

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "examples" / "demo-paper"


@pytest.fixture(scope="module")
def demo() -> Project:
    return Project.load(DEMO)


def _has_rdkit() -> bool:
    try:
        import rdkit  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Scheme drawing
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _has_rdkit(), reason="RDKit not installed")
def test_reaction_scheme(tmp_path):
    from paperforge.schemes import reaction_scheme

    out = reaction_scheme(["c1ccccc1"], ["Cc1ccccc1"], conditions=["AlCl3", "0 °C"],
                          yield_text="88%", labels=["1", "2a"], out=tmp_path / "s.png")
    from PIL import Image

    im = Image.open(out)
    assert im.width > 800 and im.height > 200
    assert im.info.get("dpi", (0,))[0] >= 299


@pytest.mark.skipif(not _has_rdkit(), reason="RDKit not installed")
def test_toc_graphic_exact_pixels(tmp_path):
    from paperforge.schemes import toc_graphic

    out = toc_graphic("c1ccccc1", "Cc1ccccc1", "test", width_cm=8.25, height_cm=4.45,
                      dpi=300, out=tmp_path / "toc.png")
    from PIL import Image

    im = Image.open(out)
    assert (im.width, im.height) == (round(8.25 / 2.54 * 300), round(4.45 / 2.54 * 300))


@pytest.mark.skipif(not _has_rdkit(), reason="RDKit not installed")
def test_scheme_rejects_bad_smiles(tmp_path):
    from paperforge.schemes import reaction_scheme

    with pytest.raises(ValueError):
        reaction_scheme(["not-a-smiles"], ["c1ccccc1"], out=tmp_path / "x.png")


# ---------------------------------------------------------------------------
# Adversarial inputs: the engine must degrade gracefully, never crash
# ---------------------------------------------------------------------------

def test_unicode_chemistry_survives_rendering(demo):
    doc = __import__("paperforge.draft", fromlist=["compose"]).compose(demo)
    doc.abstract += " ΔG‡ = 18.4 kcal mol⁻¹; λmax 452 nm; Φ = 0.31; [α]D +12.4; ν̃ 1651 cm⁻¹."
    tex = to_latex(doc, demo)
    md = to_markdown(doc)
    assert "kcal" in tex and "452" in md


def test_huge_table_and_many_references_are_fast(tmp_path, demo):
    import yaml

    data = yaml.safe_load((DEMO / "paper.yaml").read_text(encoding="utf-8"))
    header = "col_a,col_b,col_c,col_d,col_e"
    rows = [f"{i},{i*2},x,{i/3:.2f},y" for i in range(2000)]
    (tmp_path / "big.csv").write_text(header + "\n" + "\n".join(rows), encoding="utf-8")
    data["tables"].append({"id": "big", "file": "big.csv", "caption": "Large table."})
    data["references"] = data["references"] * 20   # 160 reference objects
    (tmp_path / "paper.yaml").write_text(json.dumps(data), encoding="utf-8")
    shutil.copytree(DEMO / "figures", tmp_path / "figures")
    shutil.copytree(DEMO / "data", tmp_path / "data")
    project = Project.load(tmp_path)
    t0 = time.time()
    rep = check_project(project, offline=True)
    elapsed = time.time() - t0
    assert elapsed < 10, f"checks too slow: {elapsed:.1f}s"
    assert rep.metrics["references"] == 160


def test_random_garbage_text_file(tmp_path):
    alphabet = string.printable + "ΔλΦµ¹³⁴⁵⁶⁷⁸⁹⁻·—–’“”"
    random.seed(7)
    text = "".join(random.choice(alphabet) for _ in range(50_000))
    p = tmp_path / "garbage.tex"
    p.write_text(text, encoding="utf-8")
    rep = check_file(p, journal="Chemical Communications")
    assert rep.issues  # reports problems, no exception


def test_deeply_nested_markdown(tmp_path):
    text = "# Title\n\n## Abstract\n" + "word " * 400 + "\n\n" + "\n".join(
        f"## Section {i}\n" + "text " * 50 for i in range(200))
    p = tmp_path / "deep.md"
    p.write_text(text, encoding="utf-8")
    rep = check_file(p)
    assert "STR-ABSTRACT-LONG" in {i.code for i in rep.issues}


def test_malformed_compound_record_rejected(tmp_path):
    import yaml
    from paperforge.project import ProjectError

    data = yaml.safe_load((DEMO / "paper.yaml").read_text(encoding="utf-8"))
    data["compounds"][0]["yield_percent"] = "ninety-four"
    (tmp_path / "paper.yaml").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ProjectError):
        Project.load(tmp_path)


def test_missing_optional_fields_do_not_crash(tmp_path):
    import yaml

    minimal = {
        "paper": {"title": "Minimal", "journal": "ChemRxiv"},
        "authors": [{"name": "A B"}],
    }
    (tmp_path / "paper.yaml").write_text(json.dumps(minimal), encoding="utf-8")
    project = Project.load(tmp_path)
    rep = check_project(project, offline=True)
    assert rep.issues
    assert score(rep)["score"] < 60


def test_compound_with_impossible_formula(tmp_path):
    import yaml

    data = yaml.safe_load((DEMO / "paper.yaml").read_text(encoding="utf-8"))
    data["compounds"][0]["formula"] = "C6H99"
    (tmp_path / "paper.yaml").write_text(json.dumps(data), encoding="utf-8")
    shutil.copytree(DEMO / "figures", tmp_path / "figures")
    shutil.copytree(DEMO / "data", tmp_path / "data")
    project = Project.load(tmp_path)
    rep = check_project(project, offline=True)
    assert any(i.code == "CHEM-DBE-NEG" for i in rep.issues)


def test_negative_and_zero_values(tmp_path):
    import yaml

    data = yaml.safe_load((DEMO / "paper.yaml").read_text(encoding="utf-8"))
    data["compounds"][0]["yield_percent"] = 0
    data["compounds"][1]["yield_percent"] = -5
    (tmp_path / "paper.yaml").write_text(json.dumps(data), encoding="utf-8")
    shutil.copytree(DEMO / "figures", tmp_path / "figures")
    shutil.copytree(DEMO / "data", tmp_path / "data")
    rep = check_project(Project.load(tmp_path), offline=True)
    assert rep.issues


def test_very_long_title_and_abstract(tmp_path):
    import yaml

    data = yaml.safe_load((DEMO / "paper.yaml").read_text(encoding="utf-8"))
    data["paper"]["title"] = "Very " * 60 + "long title"
    data["abstract"]["context"] = "context " * 500
    (tmp_path / "paper.yaml").write_text(json.dumps(data), encoding="utf-8")
    shutil.copytree(DEMO / "figures", tmp_path / "figures")
    shutil.copytree(DEMO / "data", tmp_path / "data")
    rep = check_project(Project.load(tmp_path), offline=True)
    codes = {i.code for i in rep.issues}
    assert "STR-TITLE-LONG" in codes
    assert "STR-ABSTRACT-LONG" in codes


def test_end_to_end_performance(demo):
    """Whole-pipeline budget: check + compose + render under 3 seconds."""
    from paperforge.draft import compose

    t0 = time.time()
    check_project(demo, offline=True)
    doc = compose(demo)
    to_markdown(doc)
    to_latex(doc, demo)
    elapsed = time.time() - t0
    assert elapsed < 3.0, f"pipeline too slow: {elapsed:.2f}s"
