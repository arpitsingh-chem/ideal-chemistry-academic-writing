#!/usr/bin/env python3
"""Fail if a template reports an HRMS value that disagrees with its formula.

The v1 template claimed [M+H]+ 256.0427 for C14H10NO2S; the true value is
257.0505 — a 0.99 ppm-clean-looking number that was simply the wrong compound.
This guard scans .tex/.md templates for "calcd for FORMULA ... [M+X]... mass"
and recomputes the mass from the formula.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from paperforge.chem import adduct_mass, ppm_error  # noqa: E402

SUBSCRIPT = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")

PATTERN = re.compile(
    r"calcd(?:\s+for)?\s+(?:\\ce\{)?([A-Z][A-Za-z0-9]*)\}?.*?"
    r"\[M([^\]]*)\][^0-9]{0,40}?([0-9]{2,3}\.[0-9]{3,4})"
)
TOL_PPM = 20.0


def check_text(text: str, name: str) -> list[str]:
    problems = []
    text = text.translate(SUBSCRIPT)
    for m in PATTERN.finditer(text):
        formula, adduct, mass = m.group(1), "[M" + m.group(2) + "]", float(m.group(3))
        try:
            calc = adduct_mass(formula, adduct)
        except Exception as exc:  # unknown formula/adduct is itself a defect
            problems.append(f"{name}: cannot recompute {formula} {adduct}: {exc}")
            continue
        err = ppm_error(calc, mass)
        if abs(err) > TOL_PPM:
            problems.append(
                f"{name}: {formula} {adduct} reported {mass:.4f} but calcd {calc:.4f} "
                f"({err:+.1f} ppm)")
    return problems


def main(argv: list[str]) -> int:
    targets = [Path(p) for p in argv[1:]] or sorted(Path("templates").rglob("*.[tm][ed]*"))
    checked = problems = 0
    for path in targets:
        if path.suffix.lower() not in {".tex", ".md", ".txt"} or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        found = check_text(text, str(path))
        checked += len(PATTERN.findall(text))
        problems += len(found)
        for line in found:
            print("FAIL", line)
    print(f"{checked} HRMS line(s) checked, {problems} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
