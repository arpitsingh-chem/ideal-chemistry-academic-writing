"""Regression guards for behaviour that existed before v2.4.0.

The v2.4.0 work touched `chem.py` and `checks.py`, both of which the whole engine
depends on. These tests pin the *pre-existing* contract so a future change cannot
silently alter it while the new feature tests stay green.

They are deliberately about observable behaviour through public entry points
(CLI, `check_project`, data files), not about internals, so a legitimate refactor
of `checks.py` can still land — it just has to keep these promises.

Why some numbers are asserted exactly: they are golden values for *shipped data*
(261 journal rows, 1,616 snapshot works). If one of them changes, either the data
changed on purpose (regenerate and update here) or something corrupted it — and
that is exactly the event worth failing a build over.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from paperforge.checks import check_project, score
from paperforge.journals import journals, profile, resolve
from paperforge.project import Project

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "paperforge" / "data"


# --------------------------------------------------------------- data integrity

def test_journal_database_row_count():
    assert len(journals()) == 261


def test_journal_database_has_no_invented_metrics():
    """`apc_usd` and `if_2024` must stay empty until a citable source fills them."""
    path = DATA / "journals.csv"
    rows = path.read_text(encoding="utf-8").splitlines()
    header = rows[0].split(",")
    apc = header.index("apc_usd")
    imp = header.index("if_2024")
    populated = [r for r in rows[1:]
                 if len(r.split(",")) > max(apc, imp)
                 and (r.split(",")[apc].strip() or r.split(",")[imp].strip())]
    assert populated == [], "impact factors / APCs must not be populated without a source"


def test_institutional_snapshot_shape():
    works = json.loads((DATA / "publications-openalex.json").read_text(encoding="utf-8"))
    assert isinstance(works, list)
    assert len(works) == 1616
    first = works[0]
    assert "doi" in first or "title" in first


# ------------------------------------------------------------- journal contract

def test_journal_aliases_resolve():
    for alias in ("Org. Lett.", "organic letters", "OL", "OrgLett"):
        assert resolve(alias)["journal"] == "Organic Letters"


def test_verified_profile_keeps_its_source():
    p = profile("Organic Letters")
    assert p.verified is True
    assert p.source and p.source.startswith("http")


def test_unverified_journal_reports_family_default():
    """A journal without a per-journal override must not claim to be verified."""
    names = [j["journal"] for j in journals() if not profile(j["journal"]).verified]
    assert names, "expected some unverified profiles"
    p = profile(names[0])
    assert p.verified is False


# ----------------------------------------------------------------- demo projects

def test_demo_project_scores_full_marks_offline():
    result = score(check_project(Project.load(ROOT / "examples/demo-paper"), offline=True))
    assert result["score"] >= 99.0, result


def test_second_paper_offline_score_is_unchanged():
    """8 unverified DOIs offline; 99.7 only with --verify-refs (live)."""
    rep = check_project(Project.load(ROOT / "examples/second-paper"), offline=True)
    result = score(rep)
    assert result["score"] == pytest.approx(94.9, abs=0.2), result
    codes = {i.code for i in rep.issues if i.severity == "warn"}
    assert codes == {"REF-UNVERIFIED"}, codes


def test_rule_count_never_decreases():
    proc = subprocess.run([sys.executable, "-m", "paperforge", "rules"],
                          cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0
    count = int(proc.stdout.split()[0])
    assert count >= 113, proc.stdout[:200]


# ------------------------------------------------------------------- CLI contract

def test_cli_exit_codes():
    ok = subprocess.run([sys.executable, "-m", "paperforge", "check",
                         str(ROOT / "examples" / "demo-paper")],
                        cwd=ROOT, capture_output=True, text=True)
    assert ok.returncode == 0, ok.stdout[-500:]

    bad = subprocess.run([sys.executable, "-m", "paperforge", "check", "/nonexistent"],
                         cwd=ROOT, capture_output=True, text=True)
    assert bad.returncode == 2, bad.stdout[-500:]


def test_bundle_contains_the_manuscript(tmp_path):
    """`build` writes a flat submission folder plus a manifest.json inventory."""
    from paperforge.bundle import build

    project = Project.load(ROOT / "examples" / "demo-paper")
    out = tmp_path / "bundle"
    report = build(project, out)
    assert isinstance(report, dict) and report, report

    names = sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file())
    assert "manuscript.tex" in names
    assert "manuscript.docx" in names
    assert "si.tex" in names
    assert "manifest.json" in names
    assert any(n.startswith("figures/") for n in names)
