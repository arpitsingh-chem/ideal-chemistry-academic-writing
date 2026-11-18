"""Regression tests for physically impossible values in declared data tables.

Why this file exists
--------------------
`check` grounds prose numbers against the declared CSV tables, but until v2.4.0 it
never validated the *values* in those tables. A black-box test (documentation pass,
2026-11-18) changed a yield in `examples/demo-paper/data/scope.csv` from 94 to 194
and the manuscript still scored 100.0/100 with zero findings: a number no
experiment can produce passed silently. These tests pin the fix.

The cases are chosen to fail loudly if the check is ever loosened back into a
grounding-only role:

* a percentage above 100 → error
* a negative mass / amount → error
* a temperature below absolute zero → error
* a negative duration → warning
* a *valid* table → no finding (no false positives on the demo project)
* junk cells ("n.d.", ">99% (HPLC)", "") → tolerated, not crashed on
* a missing table file → already handled by TAB-MISSING, must not double-report
"""

from __future__ import annotations

import csv

import pytest

from paperforge.checks import Report, check_table_values
from paperforge.project import Project

HEADER = ["entry", "formula", "yield_percent", "mass_g", "temperature_C", "time_h"]


def _project(tmp_path, rows, *, header=None, file="data/t.csv") -> Project:
    header = header or HEADER
    path = tmp_path / "p" / file
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    (tmp_path / "p" / "paper.yaml").write_text(
        "paper:\n"
        "  title: T\n"
        "  journal: Organic Letters\n"
        "  article_type: letter\n"
        "authors: [{name: A, corresponding: true, email: a@b.org}]\n"
        "affiliations: {x: Dept}\n"
        "tables:\n"
        "- id: t\n"
        f"  file: {file}\n"
        "  caption: Data\n",
        encoding="utf-8",
    )
    return Project.load(tmp_path / "p")


def _codes(project):
    rep = Report()
    check_table_values(project, rep)
    return [(issue.code, issue.severity) for issue in rep.issues]


def test_valid_table_is_silent(tmp_path):
    project = _project(tmp_path, [["3a", "C14H10N2O", 94, 0.164, 25, 12]])
    assert _codes(project) == []


def test_yield_above_100_is_an_error(tmp_path):
    project = _project(tmp_path, [["3a", "C14H10N2O", 194, 0.164, 25, 12]])
    codes = _codes(project)
    assert ("TAB-IMPOSSIBLE-VALUE", "error") in codes


def test_negative_yield_is_an_error(tmp_path):
    project = _project(tmp_path, [["3a", "C14H10N2O", -5, 0.164, 25, 12]])
    assert ("TAB-IMPOSSIBLE-VALUE", "error") in _codes(project)


def test_boundary_values_are_accepted(tmp_path):
    """0 % and 100 % are legitimate; the check must not fire on them."""
    project = _project(tmp_path, [
        ["a", "CH4", 0, 0.0, -273.15, 0],
        ["b", "CH4", 100, 1.0, 25, 1],
    ])
    assert _codes(project) == []


def test_negative_mass_is_an_error(tmp_path):
    project = _project(tmp_path, [["3a", "C14H10N2O", 94, -0.164, 25, 12]])
    assert ("TAB-IMPOSSIBLE-VALUE", "error") in _codes(project)


def test_temperature_below_absolute_zero_is_an_error(tmp_path):
    project = _project(tmp_path, [["3a", "C14H10N2O", 94, 0.164, -300, 12]])
    assert ("TAB-IMPOSSIBLE-VALUE", "error") in _codes(project)


def test_negative_duration_is_a_warning_not_an_error(tmp_path):
    project = _project(tmp_path, [["3a", "C14H10N2O", 94, 0.164, 25, -2]])
    assert _codes(project) == [("TAB-IMPOSSIBLE-VALUE", "warn")]


def test_non_numeric_cells_are_tolerated(tmp_path):
    project = _project(tmp_path, [
        ["3a", "C14H10N2O", "n.d.", "", 25, 12],
        ["3b", "C15H12N2O", ">99% (HPLC)", 0.2, 25, 12],
    ])
    assert _codes(project) == []


def test_unicode_minus_is_parsed(tmp_path):
    project = _project(tmp_path, [["3a", "C14H10N2O", "\u22125", 0.164, 25, 12]])
    assert ("TAB-IMPOSSIBLE-VALUE", "error") in _codes(project)


def test_missing_file_is_not_double_reported(tmp_path):
    project = _project(tmp_path, [["3a", "C14H10N2O", 94, 0.164, 25, 12]])
    (tmp_path / "p" / "data" / "t.csv").unlink()
    assert _codes(project) == []


def test_unmatched_columns_are_ignored(tmp_path):
    """A column with no known physical range must never be guessed at."""
    project = _project(
        tmp_path,
        [["3a", 999999, -7]],
        header=["entry", "citation_count", "delta_ppm"],
    )
    assert _codes(project) == []


def test_only_the_offending_rows_are_counted(tmp_path):
    project = _project(tmp_path, [
        ["a", "CH4", 94, 0.1, 25, 1],
        ["b", "CH4", 101, 0.1, 25, 1],
        ["c", "CH4", 150, 0.1, 25, 1],
    ])
    rep = Report()
    check_table_values(project, rep)
    issues = [i for i in rep.issues if i.code == "TAB-IMPOSSIBLE-VALUE"]
    assert len(issues) == 1
    assert issues[0].data["count"] == 2


def test_demo_project_table_is_clean():
    """The shipped demo must not trip the new rule (guards against over-strictness)."""
    project = Project.load("examples/demo-paper")
    rep = Report()
    check_table_values(project, rep)
    assert [i.code for i in rep.issues] == []


@pytest.mark.parametrize("cell,expected", [
    ("94", 94.0), ("94.5", 94.5), (" 94 ", 94.0), ("+94", 94.0),
    ("94%", 94.0), ("94 ± 2", 94.0), ("\u221294", -94.0),
    ("n.d.", None), ("", None), (">99", None), ("12-14", None),
])
def test_cell_number_parsing(cell, expected):
    from paperforge.checks import _cell_number
    assert _cell_number(cell) == expected
