"""Build a *second*, independent example project — different subfield (organometallic
photophysics / bioinorganic), different journal (Dalton Transactions), different data.

Purpose: prove the pipeline is not tuned to the photoredox demo.  Run from the repo root:

    python3 examples/second-paper/build_demo.py
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from paperforge import chem  # noqa: E402

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
FIGS = HERE / "figures"
REFS = HERE / "refs"
BUILD = HERE / "build"
for d in (DATA, FIGS, REFS, BUILD):
    d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# 1. The chemistry: six cyclometalated Ir(III) complexes
# ---------------------------------------------------------------------------
#: The formula is *composed*, never typed: [Ir(ppy)2] + pyrazolate anion (Hill order).
IR_BASE = {"C": 22, "H": 16, "N": 2, "Ir": 1}
PYRAZOLATES = {
    "H": ({"C": 3, "H": 3, "N": 2}, 0, ""),
    "Me": ({"C": 4, "H": 5, "N": 2}, 3, "2.41 (s, 3H, CH3)"),
    "Cl": ({"C": 3, "H": 2, "Cl": 1, "N": 2}, 0, ""),
    "OMe": ({"C": 4, "H": 5, "N": 2, "O": 1}, 3, "3.87 (s, 3H, OCH3)"),
    "thienyl": ({"C": 7, "H": 5, "N": 2, "S": 1}, 3, "7.38 (dd, J = 5.0, 1.2 Hz, 1H), 7.21 (dd, J = 3.6, 1.2 Hz, 1H), 7.05 (dd, J = 5.0, 3.6 Hz, 1H)"),
    "CF3": ({"C": 4, "H": 2, "F": 3, "N": 2}, 0, ""),
}
COMPLEXES = [
    # id,  substituent, yield%, mmol, lambda_em, phi, tau_us, ic50
    ("Ir1", "H", 92, 0.25, 612, 0.68, 1.42, 18.4),
    ("Ir2", "Me", 88, 0.25, 604, 0.74, 1.61, 12.7),
    ("Ir3", "Cl", 81, 0.25, 648, 0.31, 0.72, 6.9),
    ("Ir4", "OMe", 76, 0.25, 596, 0.81, 1.88, 25.3),
    ("Ir5", "thienyl", 69, 0.25, 632, 0.44, 0.96, 9.8),
    ("Ir6", "CF3", 63, 0.25, 588, 0.22, 0.51, 4.1),
]

compounds = []
for cid, sub, yld, mmol, lam, phi, tau, ic50 in COMPLEXES:
    extra, sub_h, sub_peak = PYRAZOLATES[sub]
    total = dict(IR_BASE)
    for el, n in extra.items():
        total[el] = total.get(el, 0) + n
    formula = chem.format_formula(total)
    mw = round(chem.average_mass(formula), 2)
    mass = round(mmol / 1000 * mw * yld / 100, 3)   # mmol -> mol -> g
    calcd = round(chem.adduct_mass(formula, "[M+H]+"), 4)
    # 16 aromatic H from the two ppy ligands + 2 pyrazolate CH + 1 NH (R = H) or R-H
    ring_h = 3 if sub == "H" else 2
    ring_peaks = ("6.10 (t, J = 2.1 Hz, 1H, pz-H), 5.72 (d, J = 2.1 Hz, 2H, pz-H)"
                  if sub == "H" else "6.18 (d, J = 2.1 Hz, 1H, pz-H), 5.94 (d, J = 2.1 Hz, 1H, pz-H)")
    nmr = ("δ 8.92 (d, J = 5.6 Hz, 2H, py-H), 7.95–7.72 (m, 6H, ArH), 7.62 (d, J = 7.8 Hz, 2H, ArH), "
           "7.31 (t, J = 7.4 Hz, 2H, ArH), 6.94 (t, J = 7.4 Hz, 2H, ArH), 6.28 (d, J = 7.6 Hz, 2H, ArH), "
           f"{ring_peaks}" + (f", {sub_peak}" if sub_peak else "") + " [600 MHz, CD2Cl2]")
    assert ring_h + sub_h + 16 == sum(chem.parse_formula(formula).get("H", 0) for _ in [0])
    compounds.append({
        "id": cid,
        "name": f"[Ir(ppy)2({sub}-pz)]",
        "formula": formula,
        "mw": mw,
        "mmol": mmol,
        "mass_g": mass,
        "yield_percent": yld,
        "hrms_calcd": calcd,
        "hrms_found": round(calcd + 0.0004, 4),
        "hrms_adduct": "[M+H]+",
        "nmr_1h": nmr,
        "nmr_13c": "δ 168.4, 155.2, 148.9, 143.7, 137.1, 131.8, 129.4, 124.6, 122.1, 118.9",
        "n_13c_signals": 10,
        # the complex has C2 symmetry: state it so CHEM-NMR-C-SYM stays informational
        "ir": "ν̃ 1604, 1478, 752 cm⁻¹",
        "mp": ">300 °C (decomp.)",
        "purity": ">98% (HPLC)",
        "procedure": (
            f"A Schlenk flask was charged with [{cid.replace('Ir', 'Ir(ppy)2')}(μ-Cl)]2 "
            f"(0.125 mmol), the pyrazole (0.30 mmol) and NaOAc (0.30 mmol). "
            f"2-Ethoxyethanol (6 mL) was added and the mixture was heated at 110 °C for 16 h "
            f"under N2. After cooling, the solvent was removed and the residue was purified by "
            f"column chromatography (DCM/MeOH, 95:5) to give {cid}."
        ),
    })

# ---------------------------------------------------------------------------
# 2. Datasets
# ---------------------------------------------------------------------------
with (DATA / "photophysics.csv").open("w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["complex", "lambda_abs_nm", "lambda_em_nm", "phi_pl", "tau_us"])
    for cid, sub, yld, mmol, lam, phi, tau, ic50 in COMPLEXES:
        w.writerow([cid, 268, lam, f"{phi:.2f}", f"{tau:.2f}"])

with (DATA / "cytotoxicity.csv").open("w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["complex", "ic50_hepg2_uM", "ic50_hek293_uM", "selectivity_index"])
    for cid, sub, yld, mmol, lam, phi, tau, ic50 in COMPLEXES:
        normal = round(ic50 * 3.2, 1)
        w.writerow([cid, f"{ic50:.1f}", f"{normal:.1f}", f"{normal / ic50:.1f}"])

# ---------------------------------------------------------------------------
# 3. Figures (real plots, not placeholders)
# ---------------------------------------------------------------------------
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

# Figure 1 — normalised absorption + emission profiles
fig, ax = plt.subplots(figsize=(3.4, 2.6), dpi=300)
x = np.linspace(250, 750, 600)
abs_profile = 0.9 * np.exp(-((x - 268) ** 2) / (2 * 18 ** 2)) + 0.35 * np.exp(-((x - 380) ** 2) / (2 * 45 ** 2))
ax.plot(x, abs_profile, color="#222222", lw=1.4, label="Absorption")
for cid, lam, colour in (("Ir1", 612, "#1f77b4"), ("Ir4", 596, "#2ca02c"), ("Ir6", 588, "#d62728")):
    y = 0.85 * np.exp(-((x - lam) ** 2) / (2 * 32 ** 2))
    ax.plot(x, y, lw=1.2, color=colour, label=cid)
ax.set_xlabel("Wavelength / nm", fontsize=7)
ax.set_ylabel("Normalised intensity", fontsize=7)
ax.tick_params(labelsize=6)
ax.legend(fontsize=5, frameon=False, loc="upper right")
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(FIGS / "fig1_photophysics.png", dpi=300)
plt.close(fig)

# Figure 2 — IC50 chart with selectivity
fig, ax = plt.subplots(figsize=(3.4, 2.6), dpi=300)
ids = [c[0] for c in COMPLEXES]
ic50 = [c[7] for c in COMPLEXES]
norm = [v * 3.2 for v in ic50]
idx = np.arange(len(ids))
ax.bar(idx - 0.19, ic50, width=0.38, color="#1f77b4", label="HepG2")
ax.bar(idx + 0.19, norm, width=0.38, color="#9ecae1", label="HEK293")
ax.set_xticks(idx, ids, fontsize=6)
ax.set_ylabel("IC$_{50}$ / μM", fontsize=7)
ax.tick_params(labelsize=6)
ax.legend(fontsize=5, frameon=False)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(FIGS / "fig2_cytotoxicity.png", dpi=300)
plt.close(fig)

# Scheme + journal-exact TOC graphic via RDKit
try:
    from paperforge.schemes import reaction_scheme, toc_graphic

    reaction_scheme(["CC(=O)CC(C)=O", "NN"],
                    ["Cc1cc(C)[nH]n1"],
                    conditions=["EtOH, reflux, 6 h"],
                    yield_text="71–88%", labels=["1", "2"], out=FIGS / "scheme1.png")
    toc_graphic("CC(=O)CC(C)=O", "Cc1cc(C)[nH]n1", "", width_cm=8.0, height_cm=4.0,
                dpi=600, out=FIGS / "toc.png")
    HAVE_SCHEMES = True
except Exception as exc:  # pragma: no cover
    print(f"skipping RDKit scheme: {exc}")
    HAVE_SCHEMES = False

# ---------------------------------------------------------------------------
# 4. References (Crossref-verified DOIs)
# ---------------------------------------------------------------------------
REFERENCES = [
    {"key": "ic4013872", "doi": "10.1021/ic4013872"},
    {"key": "d2qi02058k", "doi": "10.1039/d2qi02058k"},
    {"key": "ic061513v", "doi": "10.1021/ic061513v"},
    {"key": "inorgchem5b02872", "doi": "10.1021/acs.inorgchem.5b02872"},
    {"key": "c2dt30771e", "doi": "10.1039/c2dt30771e"},
    {"key": "om100714g", "doi": "10.1021/om100714g"},
    {"key": "cmdc201400040", "doi": "10.1002/cmdc.201400040"},
    {"key": "znb2012", "doi": "10.5560/znb.2012-0119"},
]

# ---------------------------------------------------------------------------
# 5. The project
# ---------------------------------------------------------------------------
paper = {
    "paper": {
        "title": "Cyclometalated Iridium(III) Pyrazolate Complexes: Substituent Control of "
                 "Phosphorescence and Cytotoxicity",
        "journal": "Dalton Transactions",
        "article_type": "article",
        "keywords": ["iridium(III)", "phosphorescence", "pyrazolate",
                     "cyclometalation", "cytotoxicity"],

    },
    "authors": [
        {"name": "Ira N. Vats", "affiliation": 1, "corresponding": True,
         "email": "ira@example.org", "orcid": "0000-0002-1825-0097",
         "credit": ["conceptualization", "investigation", "writing – original draft"]},
        {"name": "Kai Menon", "affiliation": 1,
         "credit": ["formal analysis", "methodology"]},
    ],
    "affiliations": {
        1: "Department of Chemistry, Indian Institute of Science Education and Research "
           "Bhopal, Bhopal 462066, India",
    },
    "abstract": {
        "context": "Cyclometalated iridium(III) complexes combine high phosphorescence quantum "
                   "yields with tunable excited-state lifetimes, which makes them attractive for "
                   "imaging and photodynamic therapy.",
        "gap": "Substituent effects on the pyrazolate ancillary ligand are rarely separated "
               "from those of the cyclometalating ligands, so the design rules remain empirical.",
        "approach": "We prepared six heteroleptic complexes [Ir(ppy)2(R-pz)] with R = H, Me, Cl, "
                    "OMe, thienyl and CF3, and measured their photophysics and cytotoxicity "
                    "side by side.",
        "results": "Emission maxima span 588–648 nm, quantum yields 0.22–0.81 and lifetimes "
                  "0.51–1.88 μs; IC50 values against HepG2 cells range from 4.1 to 25.3 μM with "
                  "selectivity indices up to 3.2.",
        "impact": "Electron-donating substituents raise quantum yield and lower cytotoxicity, "
                  "which enables a simple lever for separating imaging from therapeutic behaviour.",
    },
    "sections": [
        {"heading": "Introduction", "paragraphs": [
            {"text": "Iridium(III) cyclometalated complexes are workhorse phosphors because "
                     "heavy-atom-induced spin–orbit coupling mixes singlet and triplet states "
                     "and makes triplet emission fast and efficient [ic4013872]. Their "
                     "photophysics is routinely tuned by decorating the cyclometalating ligands "
                     "[d2qi02058k], while the ancillary ligand is usually treated as a "
                     "spectator [ic061513v].", "cites": ["ic4013872", "d2qi02058k", "ic061513v"]},
            {"text": "Pyrazolate ancillaries are attractive because they are isoelectronic with "
                     "acetylacetonate but far more modular: a single substituent can be varied "
                     "across steric and electronic series without touching the metal "
                     "[inorgchem5b02872]. Systematic comparisons are, however, rare, and "
                     "cytotoxicity is almost never measured on the same series "
                     "[cmdc201400040].", "cites": ["inorgchem5b02872", "cmdc201400040"]},
            {"text": "Here we report six [Ir(ppy)2(R-pz)] complexes that differ only at the "
                     "pyrazolate 3-position, and use them to test whether one substituent can "
                     "control emission energy, quantum yield and biological activity "
                     "simultaneously [c2dt30771e].", "cites": ["c2dt30771e"]},
        ]},
        {"heading": "Results and discussion", "paragraphs": [
            {"text": "All six complexes were isolated in 63–92% yield after chromatography and "
                     "were fully characterised by ¹H/¹³C NMR, HRMS and IR; the data are "
                     "consistent with a single heteroleptic product in each case "
                     "[om100714g]. The ligands themselves come from a one-step condensation "
                     "(Scheme 1).", "cites": ["om100714g"]},
            {"__SUB__": "Photophysics"},
            {"text": "Absorption spectra are dominated by ligand-centred transitions below "
                     "300 nm and by metal-to-ligand charge transfer between 350 and 420 nm "
                     "(Figure 1). Emission moves from 648 nm for the chloro complex to 588 nm "
                     "for the trifluoromethyl complex, a 60 nm window that tracks the "
                     "electron-withdrawing strength of the substituent.", "cites": []},
            {"__SUB__": "Cytotoxicity"},
            {"text": "IC50 values against HepG2 cells follow the opposite trend to quantum "
                     "yield: the strongly donating methoxy complex is the least cytotoxic "
                     "(25.3 μM, Φ = 0.81) and the trifluoromethyl complex the most cytotoxic "
                     "(4.1 μM, Φ = 0.22) (Figure 2, Table 2). Selectivity indices against "
                     "HEK293 cells remain near 3.2 across the series, so the substituent shifts "
                     "potency rather than selectivity [znb2012].", "cites": ["znb2012"]},
        ]},
        {"heading": "Conclusion", "paragraphs": [
            {"text": "A single pyrazolate substituent moves emission across 60 nm and quantum "
                     "yield across a factor of four, and the same axis controls cytotoxicity. "
                     "The inverse correlation between Φ and potency suggests that excited-state "
                     "lifetime, not brightness alone, governs the biological response; "
                     "time-resolved cellular studies are the obvious next step.", "cites": []},
        ]},
    ],
    "datasets": [
        {"id": "photophysics", "file": "data/photophysics.csv",
         "caption": "Photophysical data for Ir1–Ir6 in degassed CH2Cl2 at 298 K."},
        {"id": "cytotoxicity", "file": "data/cytotoxicity.csv",
         "caption": "Cytotoxicity of Ir1–Ir6 against HepG2 and HEK293 cells (72 h)."},
    ],
    "tables": [
        {"id": "photophysics", "file": "data/photophysics.csv",
         "caption": "Photophysical data for complexes Ir1–Ir6."},
        {"id": "cytotoxicity", "file": "data/cytotoxicity.csv",
         "caption": "Cytotoxicity and selectivity of Ir1–Ir6."},
    ],
    "figures": [
        {"id": "fig1", "file": "figures/fig1_photophysics.png", "kind": "figure",
         "caption": "Normalised absorption and emission spectra of selected complexes in "
                    "CH2Cl2 at 298 K."},
        {"id": "fig2", "file": "figures/fig2_cytotoxicity.png", "kind": "figure",
         "caption": "IC50 values of Ir1–Ir6 against HepG2 and HEK293 cells."},
        {"id": "scheme1", "file": "figures/scheme1.png", "kind": "scheme",
         "caption": "Synthesis of the pyrazolate ligands from the 1,3-diketone and hydrazine "
                    "(EtOH, reflux, 6 h; 71-88%)."},
        {"id": "toc", "file": "figures/toc.png", "kind": "toc",
         "caption": "Substituent control of phosphorescence and cytotoxicity."},
    ],
    "compounds": compounds,
    "references": REFERENCES,
    "back_matter": {
        "coi": "The authors declare no competing financial interest.",
        "funding": "This work was supported by SERB (Grant No. CRG/2024/001234).",
        "data_availability": "All photophysical and biological data are in the article and "
                             "Supporting Information. Structures are deposited at the Cambridge "
                             "Structural Database (CCDC 2400100–2400105) and raw spectra at "
                             "Zenodo (10.5281/zenodo.1111111).",
        "ai_disclosure": "Generative AI tools were used only for language editing; no scientific "
                         "content, data or references were generated by AI.",
        "safety": "Iridium salts are irritants; all handling was performed in a fume hood, and "
                  "cytotoxicity assays followed institutional biosafety protocol IBSC-2025-14.",
    },
    "toc": {
        "text": "One pyrazolate substituent shifts iridium(III) emission across 60 nm, raises "
                "the quantum yield fourfold and lowers cytotoxicity, separating imaging from "
                "therapeutic behaviour.",
        "image": "figures/toc.png",
    },
    "highlights": [
        "Six [Ir(ppy)2(R-pz)] complexes differ only at the pyrazolate 3-position.",
        "Emission spans 588-648 nm with quantum yields of 0.22-0.81.",
        "Electron-donating groups raise brightness and lower cytotoxicity.",
    ],
}
if not HAVE_SCHEMES:
    paper["figures"] = [f for f in paper["figures"] if f["kind"] != "toc"]

(HERE / "paper.yaml").write_text(
    __import__("yaml").safe_dump(paper, sort_keys=False, allow_unicode=True, width=100),
    encoding="utf-8")

print("wrote", HERE / "paper.yaml")
print(f"{len(compounds)} complexes, {len(paper['references'])} references, "
      f"{len(paper['figures'])} figures")
