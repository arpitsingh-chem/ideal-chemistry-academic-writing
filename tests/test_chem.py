"""Chemistry engine tests — the part that must never be wrong."""
import math

import pytest

from paperforge import chem


# ---------------------------------------------------------------------------
# Formula parsing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("formula,expected", [
    ("C6H6", {"C": 6, "H": 6}),
    ("C14H10N2O", {"C": 14, "H": 10, "N": 2, "O": 1}),
    ("C6H4(NO2)2", {"C": 6, "H": 4, "N": 2, "O": 4}),
    ("CuSO4·5H2O", {"Cu": 1, "S": 1, "O": 9, "H": 10}),
    ("C6H5NO2*HCl", {"C": 6, "H": 6, "N": 1, "O": 2, "Cl": 1}),
    ("C6H5O-", {"C": 6, "H": 5, "O": 1}),
    ("CH3CH2OH", {"C": 2, "H": 6, "O": 1}),
])
def test_parse_formula(formula, expected):
    assert chem.parse_formula(formula) == expected


@pytest.mark.parametrize("bad", ["", "Xx2", "C6H(6", "C6H6)", "6C", "C6H6))"])
def test_parse_formula_errors(bad):
    with pytest.raises(chem.FormulaError):
        chem.parse_formula(bad)


def test_hill_order():
    assert chem.format_formula({"O": 2, "C": 6, "H": 6}) == "C6H6O2"
    assert chem.format_formula({"H": 2, "O": 1}) == "H2O"


# ---------------------------------------------------------------------------
# Masses — reference values from IUPAC / NIST
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("formula,mass", [
    ("C6H6", 78.04695),
    ("H2O", 18.01056),
    ("C14H10", 178.07825),
    ("C6H12O6", 180.06339),
    ("C9H8O4", 180.04226),   # aspirin
    ("C8H9NO2", 151.06333),  # paracetamol
])
def test_monoisotopic_mass(formula, mass):
    assert chem.monoisotopic_mass(formula) == pytest.approx(mass, abs=2e-4)


def test_average_mass():
    assert chem.average_mass("C6H12O6") == pytest.approx(180.156, abs=0.01)
    assert chem.average_mass("NaCl") == pytest.approx(58.44, abs=0.02)


def test_adducts():
    m = chem.monoisotopic_mass("C6H6")
    assert chem.adduct_mass("C6H6", "[M+H]+") == pytest.approx(m + 1.00728, abs=1e-4)
    assert chem.adduct_mass("C6H6", "[M+Na]+") == pytest.approx(m + 22.98922, abs=1e-3)
    assert chem.adduct_mass("C6H6", "[M-H]-") == pytest.approx(m - 1.00728, abs=1e-4)
    assert chem.adduct_mass("C6H6", "[M+2H]2+") == pytest.approx((m + 2 * 1.00728) / 2, abs=1e-4)
    with pytest.raises(chem.FormulaError):
        chem.adduct_mass("C6H6", "[M+Unobtainium]+")


def test_ppm_error():
    assert chem.ppm_error(257.0505, 257.0508) == pytest.approx(1.17, abs=0.05)
    with pytest.raises(ValueError):
        chem.ppm_error(0, 1)


# ---------------------------------------------------------------------------
# DBE / valence
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("formula,dbe", [
    ("C6H6", 4), ("C6H12", 1), ("C2H6", 0), ("C6H5N", 5), ("C2H3Cl", 1),
    ("C14H10N2O", 11), ("C10H8", 7),
])
def test_dbe(formula, dbe):
    assert chem.dbe(formula) == pytest.approx(dbe)


def test_dbe_catches_the_v1_template_error():
    """The shipped v1 template used C14H10NO2S with [M+H]+ 256.0427 — impossible."""
    issues = chem.check_formula("C14H10NO2S")
    codes = {i.code for i in issues}
    assert "CHEM-DBE-FRACTION" in codes
    hrms = chem.check_hrms("C14H10NO2S", "[M+H]+", 256.0427, 256.0431)
    assert any(i.code == "CHEM-HRMS-CALCD" for i in hrms)


def test_valid_formula_is_clean():
    assert chem.check_formula("C14H11NO2S") == []
    assert chem.check_formula("C6H6") == []


# ---------------------------------------------------------------------------
# HRMS
# ---------------------------------------------------------------------------

def test_hrms_tolerance():
    ok = chem.check_hrms("C14H11NO2S", "[M+H]+", 258.0583, 258.0587)
    assert ok == []
    bad_ppm = chem.check_hrms("C14H11NO2S", "[M+H]+", 258.0583, 258.0683)
    assert any(i.code == "CHEM-HRMS-PPM" for i in bad_ppm)
    bad_calcd = chem.check_hrms("C14H11NO2S", "[M+H]+", 259.0583, 259.0585)
    assert any(i.code == "CHEM-HRMS-CALCD" for i in bad_calcd)


def test_hrms_text_extraction():
    text = ("HRMS (ESI-TOF) m/z calcd for C14H11NO2S [M+H]+ 258.0583, found 258.0587.")
    formula, adduct, calcd, found = chem.formula_from_hrms_text(text)
    assert formula == "C14H11NO2S"
    assert adduct == "[M+H]+"
    assert calcd == 258.0583 and found == 258.0587


# ---------------------------------------------------------------------------
# Yields
# ---------------------------------------------------------------------------

def test_yield_arithmetic():
    # 0.86 mmol of MW 257.31 at 82% = 0.181 g
    assert chem.check_yield(0.181, 0.86, 257.31, 82) == []
    bad = chem.check_yield(0.242, 0.86, 257.31, 82)
    assert bad and bad[0].code == "CHEM-YIELD-MASS"
    assert chem.theoretical_mass_g(1.0, 100.0) == pytest.approx(0.1)


# ---------------------------------------------------------------------------
# NMR
# ---------------------------------------------------------------------------

def test_nmr_integral_parsing():
    text = "δ 8.21 (d, J = 8.8 Hz, 2H, ArH), 7.42 (dd, 2H), 3.92 (s, 3H, OCH3)"
    total, _ = chem.parse_integrals(text)
    assert total == 7
    assert chem.parse_integrals("δ 1.2 (t, J = 7.1 Hz, 6 H), 3.4 (s, 2 H)")[0] == 8


def test_nmr_consistency():
    issues = chem.check_nmr("C14H11NO2S", h_integrals=7, n_13c_signals=6)
    assert any(i.code == "CHEM-NMR-H" and i.severity == "error" for i in issues)
    # benzene: 6 H and 1 symmetry-unique carbon is chemically correct
    assert chem.check_nmr("C6H6", h_integrals=6, n_13c_signals=1) == []
    assert chem.check_nmr("C14H11NO2S", h_integrals=11, n_13c_signals=14) == []


def test_compound_label_parsing():
    assert chem.parse_compound_id("Compound 3a") == "3a"
    assert chem.parse_compound_id("4b:") == "4b"


# --- v2.1: coordination compounds and adduct aliases -------------------------

def test_square_bracket_complexes():
    from paperforge.chem import parse_formula

    assert parse_formula("[Cu(NH3)4]SO4") == {"Cu": 1, "N": 4, "H": 12, "S": 1, "O": 4}
    assert parse_formula("K4[Fe(CN)6]") == {"K": 4, "Fe": 1, "C": 6, "N": 6}


def test_unbalanced_bracket_raises():
    import pytest
    from paperforge.chem import FormulaError, parse_formula

    with pytest.raises(FormulaError):
        parse_formula("[Cu(NH3)4SO4")


def test_adduct_aliases():
    from paperforge.chem import adduct_mass

    assert adduct_mass("C14H10NO2S", "M+Na") == adduct_mass("C14H10NO2S", "[M+Na]+")
    assert adduct_mass("C14H10NO2S", "M+H") == adduct_mass("C14H10NO2S", "[M+H]+")
    assert adduct_mass("C14H10NO2S", "[M+FA-H]-") == adduct_mass("C14H10NO2S", "[M+HCOO]-")
    assert adduct_mass("C14H10NO2S", "M+\u2022") == adduct_mass("C14H10NO2S", "[M]+.")
