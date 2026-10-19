#!/usr/bin/env python3
"""Generate the PaperForge demo project from scratch.

The chemistry is a *simulated* but internally consistent data set for
3-arylquinoxalin-2(1H)-ones: every formula, exact mass, yield/mass pair and
NMR integral is computed, so the chemistry checker has real work to do.
The references are real, DOI-verified papers; the data are not.

Run:  python3 build_demo.py
Requires: matplotlib, numpy, rdkit (optional for structure drawings), Pillow.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

from paperforge.chem import adduct_mass, average_mass, dbe  # noqa: E402

FIG = HERE / "figures"
DATA = HERE / "data"
for d in (FIG, DATA):
    d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Compound set (SMILES → RDKit formula)
# ---------------------------------------------------------------------------
CORE = "O=c1[nH]c2ccccc2nc1{R}"

COMPOUNDS = [
    ("3a", "phenyl", "", "-c1ccccc1", 94.0, ">99% (HPLC)", "258–260"),
    ("3b", "4-methylphenyl", "4-MeC6H4", "-c1ccc(C)cc1", 88.0, ">99% (HPLC)", "244–246"),
    ("3c", "4-methoxyphenyl", "4-MeOC6H4", "-c1ccc(OC)cc1", 81.0, ">98% (HPLC)", "231–233"),
    ("3d", "4-chlorophenyl", "4-ClC6H4", "-c1ccc(Cl)cc1", 76.0, ">99% (HPLC)", "269–271"),
    ("3e", "4-(trifluoromethyl)phenyl", "4-CF3C6H4", "-c1ccc(C(F)(F)F)cc1", 72.0, ">98% (HPLC)", "252–254"),
    ("3f", "4-nitrophenyl", "4-NO2C6H4", "-c1ccc([N+](=O)[O-])cc1", 68.0, ">97% (HPLC)", "283–285"),
    ("3g", "2-naphthyl", "2-C10H7", "-c1ccc2ccccc2c1", 64.0, ">98% (HPLC)", "240–242"),
    ("3h", "thiophen-3-yl", "3-thienyl", "-c1ccsc1", 61.0, ">97% (HPLC)", "225–227"),
]

from rdkit import Chem  # noqa: E402
from rdkit.Chem import Descriptors, rdMolDescriptors  # noqa: E402


def formula_of(smiles: str) -> str:
    mol = Chem.MolFromSmiles(smiles)
    return rdMolDescriptors.CalcMolFormula(mol)


rows = []
for cid, name, label, rgroup, yield_pct, purity, mp in COMPOUNDS:
    smi = CORE.format(R=rgroup)
    mol = Chem.MolFromSmiles(smi)
    formula = formula_of(smi)
    mw = average_mass(formula)
    mmol = 0.50
    mass = round(mmol * mw * yield_pct / 100 / 1000, 3)
    calcd = round(adduct_mass(formula, "[M+H]+"), 4)
    ppm = 0.8 + (len(cid) % 5) * 0.3
    found = round(calcd * (1 + ppm * 1e-6), 4)
    rows.append(dict(cid=cid, name=name, label=label, smiles=smi, formula=formula,
                     mw=mw, mmol=mmol, mass=mass, yield_pct=yield_pct, calcd=calcd,
                     found=found, purity=purity, mp=mp, ppm=ppm, dbe=dbe(formula)))

for r in rows:
    assert r["yield_pct"] and r["calcd"], r
    print(f"{r['cid']}  {r['formula']:<14} MW {r['mw']:7.2f}  [M+H]+ {r['calcd']:.4f}  "
          f"yield {r['yield_pct']:5.1f}%  mass {r['mass']:.3f} g  DBE {r['dbe']:.0f}")

# ---------------------------------------------------------------------------
# CSVs
# ---------------------------------------------------------------------------
with (DATA / "scope.csv").open("w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["entry", "product", "aryl_group", "formula", "yield_percent", "purity"])
    for r in rows:
        w.writerow([r["cid"], f"3-({r['name']})quinoxalin-2(1H)-one", r["label"],
                    r["formula"], f"{r['yield_pct']:.0f}", r["purity"]])

with (DATA / "controls.csv").open("w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["entry", "variation", "yield_percent", "conversion_percent"])
    w.writerows([
        [1, "standard conditions", 94, 99],
        [2, "no photocatalyst", 0, 6],
        [3, "no light (dark)", 3, 9],
        [4, "TEMPO (2.0 equiv.)", 0, 4],
        [5, "under air", 11, 27],
        [6, "no aryl diazonium salt", 0, 0],
    ])

sv_q = [0, 2, 4, 6, 8, 10]
sv_i = [1.00, 1.18, 1.37, 1.55, 1.73, 1.92]
with (DATA / "stern_volmer.csv").open("w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["quencher_mM", "I0_over_I"])
    w.writerows(zip(sv_q, [f"{v:.2f}" for v in sv_i]))
slope, intercept = np.polyfit(sv_q, sv_i, 1)
pred = np.polyval([slope, intercept], sv_q)
r2 = 1 - ((np.array(sv_i) - pred) ** 2).sum() / ((np.array(sv_i) - np.mean(sv_i)) ** 2).sum()
with (DATA / "sv_fit.csv").open("w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["parameter", "value"])
    w.writerow(["slope_mM-1", f"{slope:.3f}"])
    w.writerow(["intercept", f"{intercept:.3f}"])
    w.writerow(["r_squared", f"{r2:.3f}"])

dft = [("aryl radical + 1", 0.0), ("TS1 (radical addition)", 6.4), ("intermediate INT1", -8.1),
       ("TS2 (oxidation)", 2.9), ("product 3a", -52.3)]
with (DATA / "dft_profile.csv").open("w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["stationary_point", "relative_energy_kcal_per_mol"])
    w.writerows(dft)

# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
plt.rcParams.update({"font.family": "DejaVu Serif", "font.size": 9, "axes.linewidth": 0.8})


def save(fig, name, dpi=300):
    path = FIG / name
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    # stamp DPI metadata so downstream checks see it
    from PIL import Image
    im = Image.open(path)
    im.save(path, dpi=(dpi, dpi))
    print("figure:", path, im.size)


# Figure 1 — Stern–Volmer + trapping
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.2, 2.8))
ax1.plot(sv_q, sv_i, "o", color="#1f3b73", ms=5, label="3a")
xx = np.linspace(0, 10.5, 50)
ax1.plot(xx, slope * xx + intercept, "-", color="#c0392b", lw=1.2,
         label=f"fit: $I_0/I$ = 1 + {slope:.3f}[Q]  ($R^2$ = {r2:.3f})")
ax1.set_xlabel("[3a] (mM)")
ax1.set_ylabel("$I_0/I$")
ax1.set_title("A  Stern–Volmer quenching", loc="left", fontsize=9)
ax1.legend(frameon=False, fontsize=7)
ax1.set_xlim(0, 10.5)

labels = ["standard", "+TEMPO", "dark", "no PC"]
vals = [94, 0, 3, 0]
ax2.bar(range(len(vals)), vals, color=["#1f3b73", "#b0b7c3", "#b0b7c3", "#b0b7c3"], width=0.65)
ax2.set_xticks(range(len(vals)))
ax2.set_xticklabels(labels, fontsize=8)
ax2.set_ylabel("yield (%)")
ax2.set_ylim(0, 100)
ax2.set_title("B  Control experiments", loc="left", fontsize=9)
for i, v in enumerate(vals):
    ax2.text(i, v + 2, f"{v}", ha="center", fontsize=7)
for ax in (ax1, ax2):
    ax.spines[["top", "right"]].set_visible(False)
save(fig, "fig1_mechanism.png")

# Figure 2 — DFT profile
fig, ax = plt.subplots(figsize=(7.2, 2.6))
xs = range(len(dft))
ys = [e for _, e in dft]
ax.plot(xs, ys, "-o", color="#1f3b73", lw=1.2, ms=5)
for i, (label, e) in enumerate(dft):
    ax.annotate(f"{e:+.1f}", (i, e), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=7)
ax.set_xticks(list(xs))
ax.set_xticklabels([l.replace(" (", "\n(") for l, _ in dft], fontsize=7)
ax.set_ylabel("ΔG (kcal mol$^{-1}$)")
ax.set_title("PBE0-D3BJ/def2-TZVP (SMD, EtOH)", loc="left", fontsize=9)
ax.axhline(0, color="grey", lw=0.6, ls=":")
ax.spines[["top", "right"]].set_visible(False)
save(fig, "fig2_dft.png")

# Scheme 1 and the TOC graphic — real structures drawn from SMILES
from paperforge.schemes import reaction_scheme, toc_graphic  # noqa: E402

reaction_scheme(
    reactants=[CORE.format(R="")],
    products=[CORE.format(R="-c1ccccc1")],
    conditions=["4CzIPN (2 mol%)", "blue LEDs (450 nm), EtOH", "25 °C, 12 h, N2"],
    yield_text="94%",
    labels=["1", "3a"],
    out=FIG / "scheme1.png",
)
toc_graphic(
    CORE.format(R=""), CORE.format(R="-c1ccccc1"),
    caption="C–H arylation of quinoxalin-2(1H)-ones",
    arrow_label="visible light", yield_text="up to 94%",
    out=FIG / "toc.png",
)
print("figure:", FIG / "scheme1.png")
print("figure:", FIG / "toc.png")

# ---------------------------------------------------------------------------
# paper.yaml
# ---------------------------------------------------------------------------
import yaml  # noqa: E402

nmr = {
    "3a": ("δ 12.28 (s, 1H, NH), 8.12 (d, J = 8.0 Hz, 1H, ArH), 7.90–7.82 (m, 2H, ArH), "
           "7.76 (d, J = 7.8 Hz, 2H, ArH), 7.58–7.44 (m, 4H, ArH); (400 MHz, DMSO-d6)",
           "δ 161.4, 154.2, 142.1, 135.8, 133.1, 131.2, 129.6, 128.9, 128.1, 127.4, 115.8",
           11),
    "3b": ("δ 12.24 (s, 1H, NH), 8.10 (d, J = 8.0 Hz, 1H, ArH), 7.88–7.80 (m, 2H, ArH), "
           "7.64 (d, J = 8.1 Hz, 2H, ArH), 7.52–7.40 (m, 3H, ArH), 3.38 (s, 3H, CH3); (400 MHz, DMSO-d6)",
           "δ 161.5, 154.0, 142.2, 140.8, 133.0, 130.7, 129.1, 128.8, 127.9, 115.7, 21.3", 12),
    "3c": ("δ 12.20 (s, 1H, NH), 8.08 (d, J = 8.0 Hz, 1H, ArH), 7.86–7.78 (m, 2H, ArH), "
           "7.70 (d, J = 8.6 Hz, 2H, ArH), 7.50–7.38 (m, 3H, ArH), 3.84 (s, 3H, OCH3); (400 MHz, DMSO-d6)",
           "δ 161.6, 160.2, 153.9, 142.3, 132.9, 130.6, 129.5, 127.9, 115.6, 114.2, 55.8", 12),
    "3d": ("δ 12.32 (s, 1H, NH), 8.11 (d, J = 8.1 Hz, 1H, ArH), 7.89–7.81 (m, 2H, ArH), "
           "7.74 (d, J = 8.5 Hz, 2H, ArH), 7.56 (d, J = 8.5 Hz, 2H, ArH), 7.50–7.42 (m, 1H, ArH); (400 MHz, DMSO-d6)",
           "δ 161.3, 153.8, 142.4, 136.4, 134.6, 132.8, 131.0, 129.3, 128.4, 115.8", 11),
    "3e": ("δ 12.40 (s, 1H, NH), 8.14 (d, J = 8.0 Hz, 1H, ArH), 7.96 (d, J = 8.1 Hz, 2H, ArH), "
           "7.90–7.82 (m, 4H, ArH), 7.52–7.44 (m, 1H, ArH); (400 MHz, DMSO-d6)",
           "δ 161.2, 153.5, 142.5, 139.9, 132.7, 130.8, 129.8, 126.1, 125.8, 124.9, 115.9", 11),
    "3f": ("δ 12.55 (s, 1H, NH), 8.38 (d, J = 8.7 Hz, 2H, ArH), 8.16 (d, J = 8.0 Hz, 1H, ArH), "
           "8.02 (d, J = 8.7 Hz, 2H, ArH), 7.92–7.84 (m, 2H, ArH), 7.54–7.46 (m, 1H, ArH); (400 MHz, DMSO-d6)",
           "δ 161.0, 153.1, 148.4, 142.7, 141.6, 132.5, 130.9, 129.9, 124.2, 116.0", 11),
    "3g": ("δ 12.30 (s, 1H, NH), 8.22 (s, 1H, ArH), 8.14 (d, J = 8.0 Hz, 1H, ArH), 8.04–7.86 (m, 5H, ArH), "
           "7.82 (d, J = 8.5 Hz, 1H, ArH), 7.58–7.44 (m, 3H, ArH); (400 MHz, DMSO-d6)",
           "δ 161.4, 154.1, 142.2, 134.9, 133.4, 133.0, 132.6, 129.9, 128.8, 128.4, 128.0, 127.6, 126.8, 115.8", 14),
    "3h": ("δ 12.36 (s, 1H, NH), 8.10 (d, J = 8.0 Hz, 1H, ArH), 7.94 (dd, J = 2.8, 1.4 Hz, 1H, ArH), "
           "7.88–7.80 (m, 2H, ArH), 7.66 (dd, J = 5.0, 2.9 Hz, 1H, ArH), 7.50–7.42 (m, 1H, ArH), "
           "7.38 (dd, J = 5.0, 1.4 Hz, 1H, ArH); (400 MHz, DMSO-d6)",
           "δ 161.5, 154.0, 141.9, 136.7, 133.0, 129.6, 128.1, 127.5, 126.9, 115.7", 10),
}

compound_yaml = []
for r in rows:
    h1, c13, n13 = nmr[r["cid"]]
    compound_yaml.append({
        "id": r["cid"],
        "name": f"3-({r['name']})quinoxalin-2(1H)-one",
        "formula": r["formula"],
        "mw": round(r["mw"], 2),
        "mmol": r["mmol"],
        "mass_g": r["mass"],
        "yield_percent": r["yield_pct"],
        "hrms_calcd": r["calcd"],
        "hrms_found": r["found"],
        "hrms_adduct": "[M+H]+",
        "nmr_1h": h1,
        "nmr_13c": c13,
        "n_13c_signals": n13,
        "ir": "ν̃ 1651 (C=O), 1598, 1512 cm⁻¹",
        "mp": f"{r['mp']} °C",
        "purity": r["purity"],
        "procedure": (f"A vial was charged with quinoxalin-2(1H)-one (0.50 mmol, 73.1 mg), "
                      f"the aryl diazonium tetrafluoroborate (0.75 mmol, 1.5 equiv.) and 4CzIPN "
                      f"(2 mol%). EtOH (4.0 mL) was added under N2, and the mixture was irradiated "
                      f"with blue LEDs (450 nm) at 25 °C for 12 h. The solvent was removed and the "
                      f"residue purified by column chromatography (hexane/EtOAc, 7:3) to give "
                      f"{r['cid']} as a pale-yellow solid."),
    })

references = [
    {"key": "romero2016organic", "doi": "10.1021/acs.chemrev.6b00057", "title": "Organic Photoredox Catalysis",
     "authors": ["Romero, Nathan A.", "Nicewicz, David A."], "journal": "Chemical Reviews", "year": 2016,
     "volume": "116", "pages": "10075-10166", "verified": True},
    {"key": "prier2013visible", "doi": "10.1021/cr300503r",
     "title": "Visible Light Photoredox Catalysis with Transition Metal Complexes: Applications in Organic Synthesis",
     "authors": ["Prier, Christopher K.", "Rankic, Danica A.", "MacMillan, David W. C."],
     "journal": "Chemical Reviews", "year": 2013, "volume": "113", "pages": "5322-5363", "verified": True},
    {"key": "narayanam2011visible", "doi": "10.1039/B913880N",
     "title": "Visible light photoredox catalysis: applications in organic synthesis",
     "authors": ["Narayanam, Jagan M. R.", "Stephenson, Corey R. J."],
     "journal": "Chemical Society Reviews", "year": 2011, "volume": "40", "pages": "102-113", "verified": True},
    {"key": "xuan2012visible", "doi": "10.1002/anie.201200223", "title": "Visible-Light Photoredox Catalysis",
     "authors": ["Xuan, Jun", "Xiao, Wen-Jing"], "journal": "Angewandte Chemie International Edition",
     "year": 2012, "volume": "51", "pages": "6828-6838", "verified": True},
    {"key": "pan2024base", "doi": "10.1021/acs.joc.4c01641",
     "title": "Base-Mediated Visible-Light-Driven C–H Arylation of Quinoxalin-2(1H)-ones in Ethanol",
     "authors": ["Pan, Yitong", "Wang, Luohe"], "journal": "The Journal of Organic Chemistry",
     "year": 2024, "volume": "89", "pages": "14217-14227", "verified": True},
    {"key": "neese2012orca", "doi": "10.1002/wcms.81", "title": "The ORCA program system",
     "authors": ["Neese, Frank"], "journal": "WIREs Computational Molecular Science", "year": 2012,
     "volume": "2", "pages": "73-78", "verified": True},
    {"key": "xin2026recent", "doi": "10.1016/j.gresc.2024.12.003",
     "title": "Recent advancements in visible-light-induced direct C(3)–H functionalization of quinoxalin-2(1H)-ones",
     "authors": ["Xin, Han", "Guo, Yifan", "Hu, Yu", "Chang, Yuanyuan", "Guo, Yujing", "Shi, Linlin"],
     "journal": "Green Synthesis and Catalysis", "year": 2026, "volume": "7", "pages": "34-56", "verified": True},
    {"key": "yang2023recent", "doi": "10.3390/molecules28135030",
     "title": "Recent Developments in Direct C–H Functionalization of Quinoxalin-2(1H)-Ones via Heterogeneous Catalysis Reactions",
     "authors": ["Yang, Qiming", "Wang, Hu", "Wang, Xiang", "Lei, Yizhu"],
     "journal": "Molecules", "year": 2023, "volume": "28", "pages": "5030", "verified": True},
]

project = {
    "paper": {
        "title": "Visible-Light Photoredox C–H Arylation of Quinoxalin-2(1H)-ones with Aryl Diazonium Salts",
        "journal": "Organic Letters",
        "article_type": "letter",
        "keywords": ["photoredox catalysis", "quinoxalinones", "C–H arylation",
                     "aryl radicals", "reaction mechanism", "DFT"],
    },
    "authors": [
        {"name": "Meera Iyer", "affiliation": 1, "corresponding": True,
         "email": "meera.iyer@example.ac.in", "orcid": "0000-0002-1825-0097",
         "credit": ["conceptualization", "investigation", "writing – original draft"]},
        {"name": "Rohan Deshpande", "affiliation": 1,
         "credit": ["investigation", "formal analysis", "visualization"]},
        {"name": "A. K. Supervisor", "affiliation": 1,
         "credit": ["supervision", "funding acquisition", "writing – review & editing"]},
    ],
    "affiliations": {1: "Department of Chemistry, Indian Institute of Science Education and Research Bhopal, Bhopal 462066, India"},
    "abstract": {
        "context": "Visible-light photoredox catalysis has become a general strategy for forming C–C bonds under mild conditions.",
        "gap": "Direct C3–H arylation of quinoxalin-2(1H)-ones with aryl diazonium salts remains limited by competing N-arylation and a narrow substrate scope.",
        "results": [
            "Using 4CzIPN (2 mol%) and blue LEDs in ethanol, eight aryl groups were installed in 61–94% isolated yield.",
            "Chloro, nitro, trifluoromethyl and heteroaryl substituents were tolerated, and Stern–Volmer analysis (KSV = 0.091 mM−1) supports reductive quenching of the excited photocatalyst.",
        ],
        "impact": "The method provides a mild, operationally simple route to 3-arylquinoxalin-2(1H)-ones and should extend to other electron-poor heteroarenes.",
    },
    "sections": [
        {"heading": "Introduction", "paragraphs": [
            {"text": "Visible-light photoredox catalysis converts photon energy into single-electron chemistry under conditions that are often inaccessible thermally. Organic photoredox catalysts in particular avoid transition-metal residues and enable strong reducing or oxidising regimes with simple LED sources [romero2016organic]. Transition-metal polypyridyl complexes laid much of the mechanistic groundwork for these reactions [prier2013visible], and the strategy now spans radical additions, cross-couplings and C–H functionalisations [narayanam2011visible, xuan2012visible].",
             "cites": ["romero2016organic", "prier2013visible", "narayanam2011visible", "xuan2012visible"]},
            {"text": "Quinoxalin-2(1H)-ones are privileged scaffolds in medicinal chemistry, yet selective functionalisation of the C3 position remains challenging because the N–H and C3–H sites compete for the same electrophiles. Recent reviews catalogue visible-light C(3)–H functionalisation of these heterocycles [xin2026recent, yang2023recent], and a base-mediated arylation in ethanol has been reported [pan2024base]; however, the scope is dominated by activated aryl partners and the mechanism is rarely probed.",
             "cites": ["xin2026recent", "yang2023recent", "pan2024base"]},
            {"text": "We reasoned that an aryl diazonium salt could serve as both the aryl-radical source and the oxidant, allowing a photocatalyst to operate in a reductive-quenching regime. Here we report a mild C3–H arylation that tolerates electron-poor arenes and heteroarenes, and we support the proposed radical pathway with Stern–Volmer quenching, trapping experiments and DFT calculations [neese2012orca].",
             "cites": ["neese2012orca"]},
        ]},
        {"heading": "Results and Discussion", "subsections": [
            {"heading": "Reaction development", "paragraphs": [
                {"text": "Irradiation of quinoxalin-2(1H)-one (1) with 4-methylbenzenediazonium tetrafluoroborate in the presence of 4CzIPN (2 mol%) in ethanol at 25 °C gave 3a in 94% isolated yield (Scheme 1). Control experiments established that the photocatalyst, light and diazonium salt are each essential, and the reaction was completely suppressed by TEMPO (Table 1). Replacing ethanol with acetonitrile or water lowered the yield, while running the reaction open to air gave 11% of 3a."},
                {"text": "The scope was examined under the optimised conditions (Table 2). Electron-neutral, electron-rich and electron-poor aryl groups were all installed, and the yield decreased modestly with the electron deficiency of the aryl radical (61–94%). A thiophen-3-yl group was tolerated, showing that heteroaryl diazonium salts are competent substrates. No N-arylated product was detected in any case, which we attribute to the mild, base-free conditions."},
            ]},
            {"heading": "Mechanistic studies", "paragraphs": [
                {"text": "Stern–Volmer quenching of 4CzIPN by 1 was linear over the concentration range examined (Figure 1A), with a quenching constant of 0.091 mM−1 consistent with reductive quenching of the excited photocatalyst. Addition of TEMPO (2.0 equiv.) under otherwise identical conditions shut down product formation (Figure 1B), supporting a radical pathway. Under air, conversion fell to 27%, consistent with oxygen trapping the reduced photocatalyst."},
                {"text": "DFT calculations at the PBE0-D3BJ/def2-TZVP level (SMD, ethanol) place the radical-addition transition state at +6.4 kcal mol−1 relative to the separated radical and 1, and the subsequent oxidation at −8.1 kcal mol−1 (Figure 2). The computed profile is consistent with a stepwise radical addition/oxidation sequence rather than a concerted pathway."},
            ]},
        ]},
        {"heading": "Conclusion", "paragraphs": [
            {"text": "We have developed a visible-light photoredox C3–H arylation of quinoxalin-2(1H)-ones that proceeds under mild, base-free conditions and accommodates electron-poor and heteroaryl diazonium salts. Mechanistic experiments and DFT calculations support a reductive-quenching radical pathway. Extending the method to other electron-poor heteroarenes and to flow conditions is underway."},
        ]},
    ],
    "datasets": [
        {"id": "scope", "file": "data/scope.csv", "label": "Substrate scope",
         "summary": [{"variable": "yield_percent",
                      "template": "Isolated yields ranged from {min:.0f}% to {max:.0f}% across the series (mean {mean:.0f}%, n = {n})."}]},
    ],
    "tables": [
        {"id": "controls", "file": "data/controls.csv",
         "caption": "Control experiments for the arylation of 1.^a",
         "footnote": "a Conditions as in Scheme 1; yields determined by ¹H NMR against an internal standard."},
        {"id": "scope", "file": "data/scope.csv",
         "caption": "Substrate scope of the visible-light C3–H arylation.^a",
         "footnote": "a Isolated yields after chromatography; all products characterised by ¹H/¹³C NMR and HRMS."},
    ],
    "figures": [
        {"id": "scheme1", "file": "figures/scheme1.png", "kind": "scheme", "label": "Scheme 1",
         "caption": "Visible-light C3–H arylation of quinoxalin-2(1H)-one (1) with aryl diazonium salts; the yield shown is for 3a.",
         "width_cm": 17.0},
        {"id": "fig1", "file": "figures/fig1_mechanism.png", "kind": "figure", "label": "Figure 1",
         "caption": "Mechanistic experiments. (A) Stern–Volmer quenching of 4CzIPN by 1 in EtOH. (B) Yields of 3a under control conditions.",
         "source_data": "data/stern_volmer.csv", "width_cm": 17.0},
        {"id": "fig2", "file": "figures/fig2_dft.png", "kind": "figure", "label": "Figure 2",
         "caption": "DFT energy profile for the aryl-radical addition pathway at the PBE0-D3BJ/def2-TZVP level (SMD, EtOH).",
         "source_data": "data/dft_profile.csv", "width_cm": 17.0},
        {"id": "toc", "file": "figures/toc.png", "kind": "toc", "label": "TOC",
         "caption": "Table of contents graphic.", "width_cm": 8.25},
    ],
    "compounds": compound_yaml,
    "references": references,
    "back_matter": {
        "coi": "The authors declare no competing financial interest.",
        "funding": "This work was supported by the Science and Engineering Research Board (Grant No. CRG/2024/000000).",
        "acknowledgements": "We thank the Central Instrumentation Facility, IISER Bhopal, for NMR and HRMS access.",
        "data_availability": "All data supporting this study are included in the article and its Supporting Information. Source data for Figures 1 and 2 are provided in the data/ folder of the submission.",
        "ai_disclosure": "AI tools were used for language editing and reference formatting; all scientific content, data and conclusions are the authors' own.",
        "safety": "No unexpected or unusually high hazards were encountered. Aryl diazonium salts were handled in small quantities behind a blast shield.",
    },
    "highlights": [],
    "toc": {"text": "A mild visible-light route converts quinoxalin-2(1H)-ones into 3-aryl products in up to 94% yield.",
            "image": "figures/toc.png"},
    "narrative": {
        "general_methods": ("All reagents were obtained commercially and used as received. NMR spectra were recorded on a "
                            "Bruker Avance 400 MHz spectrometer in DMSO-d6; chemical shifts are reported in ppm relative to "
                            "TMS. HRMS data were acquired on an ESI-TOF instrument. UV–vis spectra were recorded on a "
                            "Shimadzu UV-2600; emission lifetime and quenching measurements used an Edinburgh FS5 "
                            "spectrofluorometer. DFT calculations were performed with ORCA 5.0 at the PBE0-D3BJ/def2-TZVP "
                            "level using the SMD solvation model (ethanol)."),
        "significance": ("The reaction couples a bench-stable diazonium salt with an unprotected heteroarene under "
                         "photocatalyst control, avoids base and transition-metal additives, and gives complete C3 "
                         "selectivity. It therefore provides a practical entry to a medicinal-chemistry scaffold and a "
                         "mechanistic framework that should transfer to other electron-poor N-heterocycles."),
        "suggested_reviewers": [],
        "conclusion": [],
    },
    "options": {"auto_results": True},
}

with (HERE / "paper.yaml").open("w", encoding="utf-8") as fh:
    yaml.safe_dump(project, fh, sort_keys=False, allow_unicode=True, width=110)

print("\nwrote paper.yaml")
print("compounds:", len(compound_yaml), "references:", len(references))
