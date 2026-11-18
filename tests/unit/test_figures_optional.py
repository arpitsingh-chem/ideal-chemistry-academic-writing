"""Figure checks must degrade honestly when the optional Pillow extra is absent.

Found by installing the built wheel into a clean venv **without** extras and running
`check` against the demo project: it reported four `FIG-READ` **errors** saying
"cannot read image: No module named 'PIL'" with the hint "re-export the figure",
and scored the project 95.2/100. Nothing was wrong with the figures — the package
was not installed. A tool whose advice is "re-export your figure" when the real
fix is `pip install "paperforge[figures]"` teaches users to distrust its errors.

These tests pin the corrected behaviour: one informational note per figure, no
errors, an actionable hint, and a note whose wording is not nonsense.
"""
from __future__ import annotations

import sys

import pytest

from paperforge.checks import Report, _merge_repeated_info
from paperforge.figures import PIL_MISSING, check_figure_file, image_info
from paperforge.project import Figure

PNG = "examples/demo-paper/figures/fig2_dft.png"


@pytest.fixture
def no_pil(monkeypatch):
    """Make `from PIL import Image` raise ImportError for the duration of a test."""
    monkeypatch.setitem(sys.modules, "PIL", None)
    yield


def test_pil_absence_is_reported_as_missing_dependency(no_pil):
    info = image_info(PNG)
    assert info.exists is True
    assert info.error == PIL_MISSING


def test_pil_absence_is_not_a_figure_defect(no_pil):
    fig = Figure(id="fig2", file="figures/fig2_dft.png", caption="DFT", kind="figure")
    issues = check_figure_file(fig, __import__("pathlib").Path("examples/demo-paper"))
    codes = [i["code"] for i in issues]
    assert codes == ["FIG-NO-PIL"], issues
    assert issues[0]["severity"] == "info", "must not be an error: nothing is wrong with the file"
    assert "paperforge[figures]" in issues[0]["hint"]


def test_real_unreadable_file_is_still_an_error(no_pil, tmp_path):
    """A genuinely broken file must still be FIG-READ, not excused as a missing extra."""
    bad = tmp_path / "broken.png"
    bad.write_bytes(b"this is not a png")
    info = image_info(bad)
    # Pillow is blocked here, so the dependency message wins — this asserts the branch
    # order explicitly so a future refactor cannot silently swap them.
    assert info.error == PIL_MISSING


def test_grouped_note_uses_the_right_noun_for_figures():
    rep = Report()
    for fid in ("scheme1", "fig1", "fig2", "toc"):
        rep.add("FIG-NO-PIL", "info", "figures",
                f"{fid}: raster checks skipped — Pillow is not installed",
                'pip install "paperforge[figures]"')
    _merge_repeated_info(rep)
    assert len(rep.issues) == 1
    message = rep.issues[0].message
    assert message.startswith("4 display item(s):")
    assert "compounds" not in message
    assert "scheme1" in message and "toc" in message


def test_grouped_note_still_says_compounds_for_chemistry():
    """The fix must not break the case it was written for (PF-0xx metal DBE notes)."""
    rep = Report()
    for cid in ("Ir1", "Ir2", "Ir3"):
        rep.add("CHEM-DBE-METAL", "info", "evidence",
                f"Compound {cid}: DBE is not defined for formulae containing Ir", "n/a")
    _merge_repeated_info(rep)
    assert rep.issues[0].message.startswith("3 compound(s):")
