"""End-to-end CLI and submission-package tests."""
import json
import shutil
import zipfile
from pathlib import Path

import pytest

from paperforge.cli import main

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "examples" / "demo-paper"


def run(capsys, *argv):
    code = main(list(argv))
    out = capsys.readouterr()
    return code, out.out + out.err


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0


def test_cli_doctor(capsys):
    code, out = run(capsys, "doctor")
    assert code == 0
    assert "chem engine" in out


def test_cli_journals_match(capsys):
    code, out = run(capsys, "journals", "match", "gold catalysis heterocycles", "--top", "5")
    assert code == 0
    assert "score" in out
    assert any(j in out for j in ("Angewandte", "Chemical Communications", "Chemistry - A European"))


def test_cli_journals_show(capsys):
    code, out = run(capsys, "journals", "show", "ChemComm", "--article-type", "communication")
    assert code == 0
    assert '"abstract_max": 250' in out


def test_cli_rules(capsys):
    code, out = run(capsys, "rules")
    assert code == 0
    assert "CHEM-HRMS-CALCD" in out
    assert len(out.splitlines()) > 40


def test_cli_check_json(capsys):
    code, out = run(capsys, "check", str(DEMO), "--json")
    payload = json.loads(out)
    assert code == 0
    assert payload["score"]["score"] >= 95
    assert "issues" in payload


def test_cli_score_fails_below_minimum(capsys, tmp_path):
    run(capsys, "new", str(tmp_path / "empty"))
    code, out = run(capsys, "score", str(tmp_path / "empty"), "--min", "90")
    assert code == 1


def test_cli_new_creates_project(capsys, tmp_path):
    code, out = run(capsys, "new", str(tmp_path / "np"), "--title", "X", "--journal", "ChemComm")
    assert code == 0
    assert (tmp_path / "np" / "paper.yaml").exists()


def test_cli_draft_all_formats(capsys, tmp_path):
    code, out = run(capsys, "draft", str(DEMO), "--format", "md", "tex", "docx", "--out", str(tmp_path / "b"))
    assert code == 0
    for name in ("manuscript.md", "manuscript.tex", "si.tex", "manuscript.docx"):
        assert (tmp_path / "b" / name).exists(), name


def test_cli_retarget(capsys):
    code, out = run(capsys, "retarget", str(DEMO), "--to", "Angewandte Chemie International Edition",
                    "--article-type", "communication")
    assert code == 0
    assert "TOC graphic" in out


def test_cli_missing_project_is_graceful(capsys, tmp_path):
    code, out = run(capsys, "check", str(tmp_path / "nope"))
    assert code == 2
    assert "error" in out.lower()


def test_cli_figures_inventory(capsys):
    code, out = run(capsys, "figures", "inventory", str(DEMO))
    assert code == 0
    assert "scheme1" in out


def test_cli_refs_check(capsys, tmp_path):
    bib = tmp_path / "r.bib"
    bib.write_text("@article{a, title={T}, year={2020}, doi={10.1/x}}", encoding="utf-8")
    code, out = run(capsys, "refs", "check", str(bib))
    assert code == 0
    assert '"entries": 1' in out


def test_bundle_builds_zip(capsys, tmp_path):
    code, out = run(capsys, "bundle", str(DEMO), "--out", str(tmp_path / "sub"), "--no-verify")
    assert code == 0
    zip_path = Path([l.split("zip: ")[1] for l in out.splitlines() if l.startswith("zip:")][0])
    assert zip_path.exists()
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
    for required in ("manuscript.tex", "manuscript.md", "manuscript.docx", "si.tex",
                     "cover_letter.md", "references.md", "CHECKLIST.md", "manifest.json"):
        assert required in names, required
    assert any(n.startswith("figures/") for n in names)
    manifest = json.loads((tmp_path / "sub" / "manifest.json").read_text())
    assert manifest["journal"] == "Organic Letters"
    assert manifest["score"]["score"] >= 95


def _mutate_project(tmp_path, name, mutate):
    import yaml

    shutil.copytree(DEMO, tmp_path / name)
    p = tmp_path / name
    data = yaml.safe_load((p / "paper.yaml").read_text(encoding="utf-8"))
    mutate(data)
    (p / "paper.yaml").write_text(json.dumps(data), encoding="utf-8")
    return p


def test_bundle_strict_refuses_blockers(capsys, tmp_path):
    def mutate(d):
        d["sections"][0]["paragraphs"][0]["cites"].append("ghost2024fake")

    p = _mutate_project(tmp_path, "p", mutate)
    with pytest.raises(SystemExit):
        main(["bundle", str(p), "--out", str(tmp_path / "sub2"), "--no-verify", "--strict"])


def test_bundle_strict_fail_on_error(capsys, tmp_path):
    def mutate(d):
        d["back_matter"].pop("coi")

    p = _mutate_project(tmp_path, "p3", mutate)
    with pytest.raises(SystemExit):
        main(["bundle", str(p), "--out", str(tmp_path / "sub3"), "--no-verify",
              "--strict", "--fail-on", "error"])


def test_checklist_marks_manual_items(tmp_path, capsys):
    run(capsys, "bundle", str(DEMO), "--out", str(tmp_path / "s"), "--no-verify")
    text = (tmp_path / "s" / "CHECKLIST.md").read_text()
    assert "Journal limits confirmed" in text
    assert "Readiness score" in text
