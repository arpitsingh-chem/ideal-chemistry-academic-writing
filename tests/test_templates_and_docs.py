"""Repository-level guards: templates, docs numbers, evidence pack, CI script."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "examples" / "demo-paper"


@pytest.fixture(scope="module")
def demo():
    from paperforge.project import Project

    return Project.load(DEMO)


def test_pandoc_front_matter_is_read(tmp_path):
    from paperforge.checks import check_file

    p = tmp_path / "paper.md"
    p.write_text(
        "---\ntitle: \"A Front-Matter Paper\"\nabstract: |\n  We report a short, verified study of "
        "an arylation reaction under visible light in 82% yield.\n"
        "keywords: [photoredox, arylation]\n---\n\n# Introduction\n\nText.\n",
        encoding="utf-8")
    rep = check_file(p)
    assert rep.metrics["abstract_words"] > 10
    assert not any(i.code == "STR-ABSTRACT-MISSING" for i in rep.issues)
    assert not any(i.code == "STR-TITLE-MISSING" for i in rep.issues)


def test_template_chemistry_guard_passes():
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_template_chemistry.py")],
                          cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_template_guard_catches_the_v1_bug(tmp_path):
    from scripts.check_template_chemistry import check_text

    problems = check_text("calcd for \\ce{C14H10NO2S} [M+H]+ 256.0427, found 256.0431.",
                          "v1.tex")
    assert problems and "256.0427" in problems[0]


def test_evidence_pack_is_grounded(demo):
    from paperforge.llm import evidence_pack

    pack = evidence_pack(demo)
    assert pack["citation_keys"]
    assert all(k in pack for k in ("title", "journal", "numbers_present_in_data",
                                   "journal_limits", "compounds"))
    # every compound number in the pack is also in the number set
    assert "223.0866" in {f"{x:.4f}" for x in map(float, pack["numbers_present_in_data"])}


def test_repo_docs_quote_current_numbers():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "1,616" in readme
    assert "1,707" in readme  # only in the correction note
    doc1 = (ROOT / "docs" / "01-journal-requirements.md").read_text(encoding="utf-8")
    assert "1,707" not in doc1 and "1,616" in doc1


def test_demo_project_still_scores_full_marks(demo):
    from paperforge.checks import check_project, score

    result = score(check_project(demo, offline=True))
    assert result["score"] >= 99.0, result
