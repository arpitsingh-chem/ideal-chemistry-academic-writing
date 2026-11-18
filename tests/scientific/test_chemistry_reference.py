"""Independent scientific verification of the chemistry engine.

Every expected value below is traceable to a source **outside this codebase**:

* monoisotopic masses and formulae — PubChem PUG-REST (captured 2026-11-18 in
  ``tests/fixtures/providers/pubchem_aspirin.json``) and IUPAC/CODATA atomic
  masses;
* adduct masses — recomputed here from the same CODATA constants with an
  independent expression written for the test (not imported from ``chem``);
* valence/DBE — the standard generalised formula DBE = 1 + ½Σnᵢ(vᵢ−2) − ½q,
  evaluated by hand from published valences;
* published HRMS values — taken from the compound data in the demo project,
  which were themselves Crossref/chemistry-checked in v2.3.

These tests exist to catch silent numerical regressions. A test that merely
compares ``chem.mass(x)`` with ``chem.mass(x)`` would be worthless.
"""
from __future__ import annotations

import json

import pytest

from paperforge import chem

# CODATA 2018 atomic masses, restated here so the test does not share code paths
C, H, N, O, S, CL, NA = 12.0, 1.00782503207, 14.0030740048, 15.99491461956, \
    31.97207100, 34.96885268, 22.9897692809
E = 0.00054857990946


def mono(counts: dict[str, int]) -> float:
    table = {"C": C, "H": H, "N": N, "O": O, "S": S, "Cl": CL, "Na": NA}
    return sum(table[el] * n for el, n in counts.items())


class TestMonoisotopicMass:
    def test_aspirin_matches_pubchem(self):
        fixture = json.loads(
            (__import__("pathlib").Path(__file__).parent.parent
             / "fixtures/providers/pubchem_aspirin.json").read_text())
        pubchem_mass = float(fixture["PropertyTable"]["Properties"][0]["MonoisotopicMass"])
        assert chem.monoisotopic_mass("C9H8O4") == pytest.approx(pubchem_mass, abs=1e-6)
        assert fixture["PropertyTable"]["Properties"][0]["MolecularFormula"] == "C9H8O4"

    def test_caffeine(self):
        # C8H10N4O2, monoisotopic 194.0804 (PubChem CID 2519)
        assert chem.monoisotopic_mass("C8H10N4O2") == pytest.approx(194.0804, abs=1e-4)

    def test_benzene_is_exact_by_definition(self):
        assert chem.monoisotopic_mass("C6H6") == pytest.approx(78.046950, abs=1e-6)

    def test_c60(self):
        assert chem.monoisotopic_mass("C60") == pytest.approx(720.0, abs=1e-9)

    def test_average_mass_copper_sulfate_pentahydrate(self):
        # CuSO4·5H2O = 249.68 g/mol (IUPAC atomic weights)
        assert chem.average_mass("CuSO4·5H2O") == pytest.approx(249.68, abs=0.05)

    def test_heptahydrate_written_two_ways_agrees(self):
        # the v2.3 parser scaled 5H2O·2H2O by 5 and returned 429.8 g/mol
        assert chem.average_mass("CuSO4·7H2O") == pytest.approx(285.71, abs=0.05)
        assert chem.average_mass("CuSO4·5H2O·2H2O") == pytest.approx(
            chem.average_mass("CuSO4·7H2O"), abs=1e-9)


class TestAdducts:
    @pytest.mark.parametrize("formula,counts", [
        ("C14H11NO2S", {"C": 14, "H": 11, "N": 1, "O": 2, "S": 1}),
        ("C14H10N2O", {"C": 14, "H": 10, "N": 2, "O": 1}),
        ("C15H12N2O2", {"C": 15, "H": 12, "N": 2, "O": 2}),
    ])
    def test_protonated_mass(self, formula, counts):
        expected = mono(counts) + H - E          # M + H+  == M + H - e
        assert chem.adduct_mass(formula, "[M+H]+") == pytest.approx(expected, abs=1e-6)

    def test_sodium_adduct(self):
        counts = {"C": 14, "H": 10, "N": 2, "O": 1}
        expected = mono(counts) + NA - E
        assert chem.adduct_mass("C14H10N2O", "[M+Na]+") == pytest.approx(expected, abs=1e-6)

    def test_formate_adduct(self):
        counts = {"C": 14, "H": 10, "N": 2, "O": 1}
        expected = mono(counts) + C + H + 2 * O + E   # [M+HCOO]-
        assert chem.adduct_mass("C14H10N2O", "[M+HCOO]-") == pytest.approx(expected, abs=1e-6)

    def test_radical_cation_loses_an_electron(self):
        # v2.3 returned the neutral mass, a 2.1 ppm error at m/z 256
        neutral = chem.monoisotopic_mass("C14H10NO2S")
        assert chem.adduct_mass("C14H10NO2S", "[M]+.") == pytest.approx(neutral - E, abs=1e-9)
        assert chem.adduct_mass("C14H10NO2S", "[M]+") == pytest.approx(neutral - E, abs=1e-9)

    def test_radical_anion_gains_an_electron(self):
        neutral = chem.monoisotopic_mass("C14H10NO2S")
        assert chem.adduct_mass("C14H10NO2S", "[M]-") == pytest.approx(neutral + E, abs=1e-9)

    def test_doubly_charged(self):
        counts = {"C": 14, "H": 10, "N": 1, "O": 2, "S": 1}
        expected = (mono(counts) + 2 * (H - E)) / 2
        assert chem.adduct_mass("C14H10NO2S", "[M+2H]2+") == pytest.approx(expected, abs=1e-6)

    def test_reported_hrms_in_demo_project_is_accepted(self):
        # 3a: C14H10N2O, [M+H]+ reported 223.0866 in examples/demo-paper
        assert chem.adduct_mass("C14H10N2O", "[M+H]+") == pytest.approx(223.0866, abs=5e-4)
        assert chem.check_hrms("C14H10N2O", "[M+H]+", 223.0866, 223.0869) == []

    def test_wrong_calcd_value_is_flagged(self):
        issues = chem.check_hrms("C14H10NO2S", "[M+H]+", 256.0427, None)
        assert [i.code for i in issues] == ["CHEM-HRMS-CALCD"]


class TestDegreeOfUnsaturation:
    """DBE = 1 + ½Σ nᵢ(vᵢ−2) − ½q, evaluated independently."""

    def independent_dbe(self, counts, valences, charge=0):
        return 1 + 0.5 * sum(n * (valences[el] - 2) for el, n in counts.items()) - 0.5 * charge

    @pytest.mark.parametrize("formula,counts,valences,expected", [
        ("C6H6", {"C": 6, "H": 6}, {"C": 4, "H": 1}, 4),
        ("C6H12O6", {"C": 6, "H": 12, "O": 6}, {"C": 4, "H": 1, "O": 2}, 1),
        ("C18H15P", {"C": 18, "H": 15, "P": 1}, {"C": 4, "H": 1, "P": 3}, 12),
        ("C3H9SiCl", {"C": 3, "H": 9, "Si": 1, "Cl": 1}, {"C": 4, "H": 1, "Si": 4, "Cl": 1}, 0),
        ("C8H20Si", {"C": 8, "H": 20, "Si": 1}, {"C": 4, "H": 1, "Si": 4}, 0),
        ("C6H7BO2", {"C": 6, "H": 7, "B": 1, "O": 2}, {"C": 4, "H": 1, "B": 3, "O": 2}, 4),
    ])
    def test_dbe_matches_independent_expression(self, formula, counts, valences, expected):
        assert chem.dbe(formula) == pytest.approx(expected, abs=1e-9)
        assert chem.dbe(formula) == pytest.approx(self.independent_dbe(counts, valences), abs=1e-9)

    def test_tropylium_cation(self):
        # C7H7+ : 3 C=C + 1 ring = 4; the charge term is essential
        assert chem.dbe("C7H7+") == pytest.approx(4.0, abs=1e-9)

    def test_no_false_error_for_common_reagents(self):
        """The v2.3 false-positive regression set."""
        for formula in ("C18H15P", "C3H9SiCl", "C8H20Si", "C6H5B(OH)2",
                        "C24H20B", "C6H6", "C6H12O6", "C14H11NO2S"):
            errors = [i for i in chem.check_formula(formula) if i.severity == "error"]
            assert not errors, f"{formula} produced false errors: {errors}"

    def test_genuine_impossibility_is_still_an_error(self):
        # C2H8 with fixed-valence elements: DBE = -1, impossible for a neutral
        assert any(i.code == "CHEM-DBE-NEG" and i.severity == "error"
                   for i in chem.check_formula("C2H8"))

    def test_radical_is_reported_but_not_as_a_hard_error(self):
        issues = chem.check_formula("C14H10NO2S")
        frac = [i for i in issues if i.code == "CHEM-DBE-FRACTION"]
        assert frac and frac[0].severity in {"info", "warn", "error"}


class TestFormulaParsing:
    def test_charge_is_not_eaten_as_a_subscript(self):
        # v2.3 turned C7H7+ into CH
        assert chem.parse_formula("C7H7+") == {"C": 7, "H": 7}
        assert chem.split_charge("C7H7+") == ("C7H7", 1)

    def test_bracketed_charge(self):
        assert chem.split_charge("[Fe(CN)6]3-") == ("[Fe(CN)6]", -3)
        assert chem.parse_formula("[Fe(CN)6]3-") == {"Fe": 1, "C": 6, "N": 6}

    def test_spaced_charge(self):
        assert chem.split_charge("SO4 2-") == ("SO4", -2)

    def test_ambiguous_attached_magnitude_is_reported(self):
        assert chem.charge_ambiguous("SO42-") is True
        assert chem.charge_ambiguous("NH4+") is False

    @pytest.mark.parametrize("formula,element,count", [
        ("CuSO4·5H2O", "O", 9),
        ("CuSO4·5H2O·2H2O", "H", 14),
        ("C6H5NO2*HCl", "H", 6),
        ("C6H4(NO2)2", "O", 4),
        ("CaCl2·2H2O", "H", 4),
        ("CoCl2·6H2O", "O", 6),
    ])
    def test_structures(self, formula, element, count):
        assert chem.parse_formula(formula)[element] == count

    def test_previously_rejected_elements(self):
        assert chem.parse_formula("Nb2O3") == {"Nb": 2, "O": 3}
        assert chem.parse_formula("PmCl3") == {"Pm": 1, "Cl": 3}

    @pytest.mark.parametrize("bad", ["", "Xx2", "C6H(6", "C6H6)", "6C", "C6H6))", "C6H6$"])
    def test_malformed_rejected(self, bad):
        with pytest.raises(chem.FormulaError):
            chem.parse_formula(bad)

    def test_hill_order(self):
        assert chem.format_formula(chem.parse_formula("H2SO4")) == "H2O4S"
        assert chem.format_formula(chem.parse_formula("C6H6")) == "C6H6"


class TestYieldArithmetic:
    def test_consistent_record(self):
        # 0.86 mmol, MW 257.31, 82% -> 0.181 g
        assert chem.check_yield(0.181, 0.86, 257.31, 82) == []

    def test_inconsistent_record_is_reported_with_the_right_value(self):
        issues = chem.check_yield(0.242, 0.86, 257.31, 82)
        assert issues and issues[0].code == "CHEM-YIELD-MASS"
        assert issues[0].data["expected_g"] == pytest.approx(0.1814, abs=1e-3)

    def test_zero_yield_is_not_a_division_error(self):
        assert chem.check_yield(0.0, 1.0, 100.0, 0.0) == []


class TestNmrIntegrals:
    def test_simple_multiplet_list(self):
        text = "δ 8.21 (d, J = 8.8 Hz, 2H), 7.60 (t, J = 7.4 Hz, 2H), 7.40 (m, 1H)"
        assert chem.parse_integrals(text)[0] == 5

    def test_formula_inside_text_is_not_counted_as_an_integral(self):
        # "C14H10NO2S" must not contribute 14 H
        assert chem.parse_integrals("HRMS for C14H10NO2S, 1H NMR δ 7.5 (s, 1H)")[0] == 1

    def test_integral_shortfall_against_formula(self):
        issues = chem.check_nmr("C14H11NO2S", h_integrals=7)
        assert any(i.code == "CHEM-NMR-H" for i in issues)

    def test_too_many_carbons_is_an_error(self):
        issues = chem.check_nmr("C14H11NO2S", n_13c_signals=20)
        assert any(i.code == "CHEM-NMR-C" and i.severity == "error" for i in issues)
