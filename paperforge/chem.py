"""Chemistry-domain validation.

This module is what turns PaperForge from a prose linter into a chemistry
checker.  It parses molecular formulae, computes exact/average masses, checks
HRMS values against the declared formula, verifies yield arithmetic and
sanity-checks NMR reporting.

All masses are in Da (g/mol) and use CODATA/IUPAC values.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Isotope data
# ---------------------------------------------------------------------------

#: monoisotopic masses of the most abundant isotope
MONO: dict[str, float] = {
    "H": 1.00782503207, "D": 2.0141017778, "T": 3.0160492777,
    "He": 4.00260325415, "Li": 7.01600455, "B": 11.0093054, "C": 12.0,
    "N": 14.0030740048, "O": 15.99491461956, "F": 18.99840322,
    "Na": 22.9897692809, "Mg": 23.985041700, "Al": 26.98153863,
    "Si": 27.9769265325, "P": 30.97376163, "S": 31.97207100,
    "Cl": 34.96885268, "Ar": 39.9623831225, "K": 38.96370668,
    "Ca": 39.96259098, "Sc": 44.9559119, "Ti": 47.9479463,
    "V": 50.9439595, "Cr": 51.9405075, "Mn": 54.9380451,
    "Fe": 55.9349375, "Co": 58.9331950, "Ni": 57.9353429,
    "Cu": 62.9295975, "Zn": 63.9291422, "Ga": 68.9255736,
    "Ge": 73.9211778, "As": 74.9215965, "Se": 79.9165213,
    "Br": 78.9183371, "Kr": 83.911507, "Rb": 84.9117897,
    "Sr": 87.9056121, "Y": 88.9058483, "Zr": 89.9047044,
    "Mo": 97.9054082, "Ru": 101.9043493, "Rh": 102.905504,
    "Pd": 105.903486, "Ag": 106.905097, "Cd": 113.9033585,
    "In": 114.903878, "Sn": 119.9021947, "Sb": 120.9038157,
    "Te": 129.9062244, "I": 126.904473, "Xe": 131.9041535,
    "Cs": 132.9054519, "Ba": 137.9052472, "La": 138.9063533,
    "Ce": 139.9054387, "Pr": 140.9076528, "Nd": 141.9077233,
    "Sm": 151.9197324, "Eu": 152.9212303, "Gd": 157.9241039,
    "Tb": 158.9253468, "Dy": 163.9291748, "Ho": 164.9303221,
    "Er": 166.920867, "Tm": 168.9342133, "Yb": 173.9388621,
    "Lu": 174.9407718, "Hf": 179.94655, "Ta": 180.9479958,
    "W": 183.9509312, "Re": 186.9557531, "Os": 191.9614807,
    "Ir": 192.9629264, "Pt": 194.9647911, "Au": 196.9665687,
    "Hg": 201.970643, "Tl": 204.9744275, "Pb": 207.9766521,
    "Bi": 208.9803987, "Th": 232.0380553, "U": 238.0507882,
}

#: average atomic weights (IUPAC 2021, abridged)
AVG: dict[str, float] = {
    "H": 1.008, "D": 2.014, "T": 3.016, "He": 4.0026, "Li": 6.94, "B": 10.81,
    "C": 12.011, "N": 14.007, "O": 15.999, "F": 18.998, "Na": 22.990,
    "Mg": 24.305, "Al": 26.982, "Si": 28.085, "P": 30.974, "S": 32.06,
    "Cl": 35.45, "Ar": 39.948, "K": 39.098, "Ca": 40.078, "Sc": 44.956,
    "Ti": 47.867, "V": 50.942, "Cr": 51.996, "Mn": 54.938, "Fe": 55.845,
    "Co": 58.933, "Ni": 58.693, "Cu": 63.546, "Zn": 65.38, "Ga": 69.723,
    "Ge": 72.630, "As": 74.922, "Se": 78.971, "Br": 79.904, "Kr": 83.798,
    "Rb": 85.468, "Sr": 87.62, "Y": 88.906, "Zr": 91.224, "Mo": 95.95,
    "Ru": 101.07, "Rh": 102.91, "Pd": 106.42, "Ag": 107.87, "Cd": 112.41,
    "In": 114.82, "Sn": 118.71, "Sb": 121.76, "Te": 127.60, "I": 126.90,
    "Xe": 131.29, "Cs": 132.91, "Ba": 137.33, "La": 138.91, "Ce": 140.12,
    "Pr": 140.91, "Nd": 144.24, "Sm": 150.36, "Eu": 151.96, "Gd": 157.25,
    "Tb": 158.93, "Dy": 162.50, "Ho": 164.93, "Er": 167.26, "Tm": 168.93,
    "Yb": 173.05, "Lu": 174.97, "Hf": 178.49, "Ta": 180.95, "W": 183.84,
    "Re": 186.21, "Os": 190.23, "Ir": 192.22, "Pt": 195.08, "Au": 196.97,
    "Hg": 200.59, "Tl": 204.38, "Pb": 207.2, "Bi": 208.98, "Th": 232.04,
    "U": 238.03,
}

ELECTRON = 0.00054857990946
PROTON = 1.007276466621  # mass of H+ (proton, no electron)

#: common adducts: (mass shift for the ion, absolute charge)
ADDUCTS: dict[str, tuple[float, int]] = {
    "[M+H]+": (PROTON, 1),
    "[M+Na]+": (MONO["Na"] - ELECTRON, 1),
    "[M+K]+": (MONO["K"] - ELECTRON, 1),
    "[M+NH4]+": (MONO["N"] + 4 * MONO["H"] - ELECTRON, 1),
    "[M+Li]+": (MONO["Li"] - ELECTRON, 1),
    "[M+Ag]+": (MONO["Ag"] - ELECTRON, 1),
    "[M-H]-": (-PROTON, 1),
    "[M+Cl]-": (MONO["Cl"] + ELECTRON, 1),
    "[M+Br]-": (MONO["Br"] + ELECTRON, 1),
    "[M+HCOO]-": (MONO["C"] + MONO["H"] + 2 * MONO["O"] + ELECTRON, 1),
    "[M+CH3COO]-": (2 * MONO["C"] + 3 * MONO["H"] + 2 * MONO["O"] + ELECTRON, 1),
    "[M+2H]2+": (2 * PROTON, 2),
    "[M+2Na]2+": (2 * (MONO["Na"] - ELECTRON), 2),
    "[M+3H]3+": (3 * PROTON, 3),
    "[M]+": (0.0, 1),
    "[M]+.": (0.0, 1),
    "[M]-": (0.0, 1),
}


class FormulaError(ValueError):
    """Raised when a molecular formula cannot be parsed."""


# ---------------------------------------------------------------------------
# Formula parsing
# ---------------------------------------------------------------------------

_TOKEN = re.compile(r"([A-Z][a-z]?)(\d*)|(\()|(\))(\d*)|([·.*])(\d*)")


def parse_formula(formula: str) -> dict[str, int]:
    """Parse a molecular formula into ``{element: count}``.

    Supports hydrated salts (``CuSO4·5H2O``), dot/asterisk adducts
    (``C6H5NO2*HCl``), nested brackets (``C6H4(NO2)2``) and charge suffixes
    (``+``/``-``), which are ignored for mass purposes.

    >>> parse_formula("C14H10NO2S")["C"]
    14
    >>> parse_formula("CuSO4·5H2O")["O"]
    9
    """
    if not formula or not formula.strip():
        raise FormulaError("empty formula")
    s = formula.strip().replace(" ", "")
    s = re.sub(r"(\^?\d*[+-]+)$", "", s)          # strip charge
    s = s.replace("·", ".").replace("⋅", ".")
    counts: dict[str, int] = {}
    stack: list[dict[str, int]] = [counts]
    i = 0
    last_element: str | None = None

    while i < len(s):
        ch = s[i]
        if ch in "([":
            stack.append({})
            last_element = None
            i += 1
        elif ch in ")]":
            if len(stack) == 1:
                raise FormulaError(f"unbalanced {ch!r} in {formula!r}")
            group = stack.pop()
            i += 1
            num = ""
            while i < len(s) and s[i].isdigit():
                num += s[i]
                i += 1
            mult = int(num) if num else 1
            for el, n in group.items():
                stack[-1][el] = stack[-1].get(el, 0) + n * mult
            last_element = None
        elif ch in ".*":
            i += 1
            num = ""
            while i < len(s) and s[i].isdigit():
                num += s[i]
                i += 1
            # hydrate multiplier applies to the following stoichiometric block
            mult = int(num) if num else 1
            if mult > 1:
                # capture the rest of the string as a block and scale it
                rest = s[i:]
                sub = parse_formula(rest)
                for el, n in sub.items():
                    stack[-1][el] = stack[-1].get(el, 0) + n * mult
                return stack[0]
            last_element = None
        elif ch.isupper():
            m = re.match(r"([A-Z][a-z]?)(\d*)", s[i:])
            if not m:
                raise FormulaError(f"bad element at {s[i:]!r} in {formula!r}")
            el, num = m.group(1), m.group(2)
            if el not in MONO and el not in AVG:
                raise FormulaError(f"unknown element {el!r} in {formula!r}")
            n = int(num) if num else 1
            stack[-1][el] = stack[-1].get(el, 0) + n
            last_element = el
            i += len(m.group(0))
        else:
            raise FormulaError(f"unexpected character {ch!r} in {formula!r}")
    if len(stack) != 1:
        raise FormulaError(f"unbalanced bracket in {formula!r}")
    return {k: v for k, v in counts.items() if v}


def format_formula(counts: dict[str, int]) -> str:
    """Hill-order formula string (C, H, then alphabetical)."""
    if not counts:
        return ""
    order = []
    if "C" in counts:
        order.append("C")
        if "H" in counts:
            order.append("H")
        order += sorted(k for k in counts if k not in ("C", "H"))
    else:
        order = sorted(counts)
    return "".join(f"{el}{counts[el] if counts[el] != 1 else ''}" for el in order)


def monoisotopic_mass(formula: str) -> float:
    """Exact mass of the neutral molecule in Da."""
    return sum(MONO.get(el, AVG.get(el, 0.0)) * n for el, n in parse_formula(formula).items())


def average_mass(formula: str) -> float:
    """Molecular weight (average) in g/mol."""
    return sum(AVG.get(el, MONO.get(el, 0.0)) * n for el, n in parse_formula(formula).items())


def nominal_mass(formula: str) -> int:
    return int(round(monoisotopic_mass(formula)))


#: elements for which the organic DBE expression is meaningful
ORGANIC_ELEMENTS = {"C", "H", "D", "T", "N", "O", "S", "F", "Cl", "Br", "I",
                    "P", "B", "Si", "Se", "Te"}


def dbe_applicable(formula: str) -> bool:
    """False for organometallic / main-group formulae where DBE is undefined.

    The organic expression assumes trivalent N, divalent O/S and monovalent
    halogens.  A transition metal or an alkali/alkaline-earth counter-ion
    breaks every one of those assumptions, so a half-integer DBE is not a
    defect — the formula is simply outside the model.
    """
    try:
        return set(parse_formula(formula)) <= ORGANIC_ELEMENTS
    except FormulaError:
        return False


def dbe(formula: str) -> float:
    """Degree of unsaturation (rings + double bonds).

    DBE = C - H/2 + N/2 + 1 - X/2  (O and S are ignored; D counts as H).
    A neutral, closed-shell molecule must have a non-negative **integer** DBE;
    a half-integer value means the formula describes a radical ion.
    """
    c = parse_formula(formula)
    c_val = c.get("C", 0)
    h = c.get("H", 0) + c.get("D", 0) + c.get("T", 0)
    n = c.get("N", 0)
    x = c.get("F", 0) + c.get("Cl", 0) + c.get("Br", 0) + c.get("I", 0)
    return c_val - h / 2 + n / 2 + 1 - x / 2


#: aliases seen in the wild (ChemDraw, MassLynx, authors' shorthand)
ADDUCT_ALIASES = {
    "M+H": "[M+H]+", "[M+H]+.": "[M+H]+", "[M+H]": "[M+H]+",
    "M+Na": "[M+Na]+", "[M+Na]": "[M+Na]+",
    "M-H": "[M-H]-", "[M-H]-.": "[M-H]-", "[M-H]": "[M-H]-",
    "M+": "[M]+", "M+.": "[M]+.", "M+•": "[M]+.", "[M]+": "[M]+",
    "M-": "[M]-", "[M]-": "[M]-",
    "M+FA-H": "[M+HCOO]-", "[M+FA-H]-": "[M+HCOO]-", "[M+HCOO]": "[M+HCOO]-",
    "M+Ac-H": "[M+CH3COO]-", "[M+CH3COO]": "[M+CH3COO]-",
}


def normalise_adduct(adduct: str) -> str:
    """Canonicalise adduct spelling; raises FormulaError for unknown ones."""
    key = adduct.replace(" ", "").replace("−", "-").replace("–", "-")
    key = ADDUCT_ALIASES.get(key, key)
    if key not in ADDUCTS:
        raise FormulaError(
            f"unknown adduct {adduct!r}; supported: {', '.join(sorted(ADDUCTS))}"
        )
    return key


def adduct_mass(neutral_formula: str, adduct: str = "[M+H]+") -> float:
    """m/z of the specified adduct for a neutral formula."""
    key = normalise_adduct(adduct)
    shift, charge = ADDUCTS[key]
    return (monoisotopic_mass(neutral_formula) + shift) / charge


def mz_calcd(formula: str, adduct: str) -> float:
    return adduct_mass(formula, adduct)


def ppm_error(calculated: float, found: float) -> float:
    """Signed ppm error of found relative to calculated."""
    if calculated <= 0:
        raise ValueError("calculated mass must be > 0")
    return (found - calculated) / calculated * 1e6


# ---------------------------------------------------------------------------
# Structured checks
# ---------------------------------------------------------------------------


@dataclass
class Issue:
    severity: str  # "error" | "warn" | "info"
    code: str
    message: str
    hint: str = ""
    data: dict = field(default_factory=dict)


def check_formula(formula: str) -> list[Issue]:
    """Valence/DBE sanity of a neutral formula."""
    issues: list[Issue] = []
    try:
        counts = parse_formula(formula)
    except FormulaError as exc:
        return [Issue("error", "CHEM-FORMULA", f"Invalid molecular formula {formula!r}: {exc}")]
    if not counts:
        return [Issue("error", "CHEM-FORMULA", f"Empty molecular formula {formula!r}")]

    if not dbe_applicable(formula):
        # organometallic / salt: the organic DBE model does not apply
        foreign = sorted(set(counts) - ORGANIC_ELEMENTS)
        issues.append(Issue(
            "info", "CHEM-DBE-METAL",
            f"{formula}: DBE is not defined for formulae containing "
            f"{', '.join(foreign)}; valence checks skipped.",
            "State the ligand count and metal oxidation state in the text."))
        return issues

    d = dbe(formula)
    if d < 0:
        issues.append(
            Issue(
                "error",
                "CHEM-DBE-NEG",
                f"{formula}: DBE = {d:.1f} is negative — more H than valence allows.",
                "Re-count hydrogens (account for charges and salts).",
            )
        )
    elif abs(d - round(d)) > 1e-9:
        issues.append(
            Issue(
                "error",
                "CHEM-DBE-FRACTION",
                f"{formula}: DBE = {d:.1f} is not an integer — a neutral closed-shell "
                "molecule cannot have this formula (radical/ion, or an H count is wrong).",
                "Check the hydrogen count and charge state.",
            )
        )

    # nitrogen rule for C,H,N,O,S,halogen-only compounds
    if set(counts) <= {"C", "H", "N", "O", "S", "F", "Cl", "Br", "I"}:
        nm = nominal_mass(formula)
        nparity = counts.get("N", 0) % 2
        if nparity == 0 and nm % 2 != 0:
            issues.append(
                Issue("warn", "CHEM-NRULE", f"{formula}: nominal mass {nm} is odd but N count is even (nitrogen rule).")
            )
        if nparity == 1 and nm % 2 == 0:
            issues.append(
                Issue("warn", "CHEM-NRULE", f"{formula}: nominal mass {nm} is even but N count is odd (nitrogen rule).")
            )
    return issues


def check_hrms(
    formula: str,
    adduct: str,
    calcd: float | None,
    found: float | None,
    tol_ppm: float = 5.0,
) -> list[Issue]:
    """Verify reported HRMS values against the molecular formula.

    * recalculation of the *calcd* value (catches copy errors / wrong adduct)
    * found vs calcd ppm error
    """
    issues: list[Issue] = []
    if calcd is None and found is None:
        return issues
    try:
        expected = adduct_mass(formula, adduct)
    except FormulaError as exc:
        return [Issue("error", "CHEM-HRMS", str(exc))]
    label = adduct.replace(" ", "")
    if calcd is not None:
        err = ppm_error(expected, calcd)
        if abs(err) > max(1.0, tol_ppm):
            issues.append(
                Issue(
                    "error",
                    "CHEM-HRMS-CALCD",
                    f"HRMS calcd for {formula} {label} is reported as {calcd:.4f}, but the "
                    f"formula gives {expected:.4f} (Δ = {err:+.0f} ppm).",
                    "Recompute with the correct adduct or fix the formula/mass.",
                    {"reported": calcd, "expected": expected, "ppm": err},
                )
            )
    if found is not None:
        ref = calcd if calcd is not None else expected
        err = ppm_error(ref, found)
        if abs(err) > tol_ppm:
            issues.append(
                Issue(
                    "error",
                    "CHEM-HRMS-PPM",
                    f"HRMS found {found:.4f} vs calcd {ref:.4f} = {err:+.1f} ppm "
                    f"(limit {tol_ppm:.0f} ppm).",
                    "Re-calibrate or correct the reported value.",
                    {"ppm": err},
                )
            )
    return issues


def theoretical_mass_g(mmol: float, mw: float) -> float:
    """Mass (g) corresponding to ``mmol`` of a compound of molar mass ``mw``."""
    return mmol * mw / 1000.0


def check_yield(
    reported_mass_g: float | None,
    mmol: float | None,
    mw: float | None,
    yield_percent: float | None,
    tolerance: float = 0.05,
) -> list[Issue]:
    """Check that mass, mmol, molecular weight and % yield agree."""
    issues: list[Issue] = []
    if mmol is None or mw is None:
        return issues
    theoretical = theoretical_mass_g(mmol, mw)
    if yield_percent is not None and reported_mass_g is not None:
        expected = theoretical * yield_percent / 100.0
        if theoretical <= 0:
            return issues
        rel = abs(reported_mass_g - expected) / theoretical
        if rel > tolerance:
            implied = reported_mass_g / theoretical * 100
            issues.append(
                Issue(
                    "error",
                    "CHEM-YIELD-MASS",
                    f"Yield arithmetic: {yield_percent:g}% of {mmol:g} mmol (MW {mw:.2f}) "
                    f"should give {expected:.3f} g, but {reported_mass_g:.3f} g is reported "
                    f"(that mass corresponds to {implied:.1f}%).",
                    "Recompute the isolated mass or the stated yield.",
                    {"expected_g": expected, "reported_g": reported_mass_g},
                )
            )
    return issues


def parse_integrals(nmr_text: str) -> tuple[int, list[str]]:
    """Sum proton integrals from a free-text ¹H NMR string.

    Understands ``δ 8.21 (d, J = 8.8 Hz, 2H)``, ``3H, OCH3``, ``1 H`` and
    ``0.9 (t, 6H)``-style reporting.  Returns ``(total_H, warnings)``.
    """
    warnings: list[str] = []
    total = 0
    # integrals such as "2H", "3 H", "1H" immediately after a comma or parenthesis
    for m in re.finditer(r"(?<![\d.])(\d{1,2})\s*H\b", nmr_text):
        total += int(m.group(1))
    if total == 0:
        # fall back: numbers inside parentheses whose unit is H
        for m in re.finditer(r"\((\d{1,2})\s*H", nmr_text):
            total += int(m.group(1))
    if re.search(r"\b(exchange|D2O|br s,?\s*\d*H?)", nmr_text, re.I) and total == 0:
        warnings.append("integrals not parseable")
    return total, warnings


def check_nmr(
    formula: str,
    h_integrals: int | None = None,
    n_13c_signals: int | None = None,
    exchangeable_h: int = 0,
    symmetry: bool = True,
) -> list[Issue]:
    """Sanity-check NMR reporting against the molecular formula."""
    issues: list[Issue] = []
    try:
        counts = parse_formula(formula)
    except FormulaError:
        return issues
    h_formula = counts.get("H", 0) + counts.get("D", 0)
    c_formula = counts.get("C", 0)

    if h_integrals is not None and h_formula:
        expected = h_formula - exchangeable_h
        if h_integrals != expected:
            sev = "error" if abs(h_integrals - expected) >= max(2, 0.2 * expected) else "warn"
            issues.append(
                Issue(
                    sev,
                    "CHEM-NMR-H",
                    f"¹H integrals sum to {h_integrals} H but {formula} contains {h_formula} H"
                    + (f" ({exchangeable_h} exchangeable excluded)" if exchangeable_h else "")
                    + ".",
                    "Check integrals or the formula; exchangeable protons must be accounted for.",
                )
            )
    if n_13c_signals is not None and c_formula:
        if n_13c_signals > c_formula:
            issues.append(
                Issue(
                    "error",
                    "CHEM-NMR-C",
                    f"¹³C NMR lists {n_13c_signals} signals but the formula has only {c_formula} carbons.",
                    "Remove spurious peaks (solvent/impurity) or fix the formula.",
                )
            )
        elif symmetry and n_13c_signals and n_13c_signals < c_formula // 2 and c_formula > 6:
            issues.append(
                Issue(
                    "info",
                    "CHEM-NMR-C-SYM",
                    f"¹³C NMR lists {n_13c_signals} signals for {c_formula} carbons — "
                    "consistent with symmetry; state this if it is load-bearing.",
                )
            )
    return issues


def parse_compound_id(text: str) -> str:
    """Extract a compound label from a heading such as 'Compound 3a' or '3a:'."""
    m = re.search(r"\b(?:compound\s+)?([0-9]{1,3}[a-z]?)\b", text, re.I)
    return m.group(1) if m else text.strip()


def formula_from_hrms_text(text: str) -> tuple[str | None, str | None, float | None, float | None]:
    """Best-effort extraction from 'HRMS (ESI-TOF) m/z calcd for C14H10NO2S [M+H]+ 257.0505, found 257.0508'.

    Returns ``(formula, adduct, calcd, found)``.
    """
    m = re.search(
        r"(?:calcd|calculated)[^.]*?for\s+([A-Z][A-Za-z0-9()·.*]*)\s*(\[[^\]]+\][0-9]*[+-]?)?\s*[:\s]*([\d.]+)",
        text,
        re.I,
    )
    calcd = float(m.group(3)) if m else None
    formula = m.group(1) if m else None
    adduct = m.group(2) if m and m.group(2) else None
    f = re.search(r"found\s*[:=]?\s*(\d+\.\d+)", text, re.I)
    found = float(f.group(1)) if f else None
    return formula, adduct, calcd, found
