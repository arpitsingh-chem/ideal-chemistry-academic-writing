#!/usr/bin/env python3
"""
journal_matcher.py — Suggest target journals from your research description,
using the real IISER Bhopal chemistry portfolio as the recommendation base
(data/iiserb-bhopal-chemistry-journals.csv + the department's observed
area -> journal mapping).

Usage:
    python3 journal_matcher.py "gold catalyzed synthesis of heterocycles"
    python3 journal_matcher.py --list-areas

Outputs: ranked journals with paper counts and publisher, plus the area you
matched. Always verify scope + current guidelines on the journal's page
(docs/01 has links and full requirement matrices).
"""
import csv
import re
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "iiserb-bhopal-chemistry-journals.csv")

# Observed area -> keyword sets (from the department's research-group mapping)
AREAS = {
    "synthesis & catalysis": ["synthesis", "catal", "coupling", "c-h", "activation",
                              "organocatal", "gold", "palladium", "heterocycle",
                              "carbene", "asymmetric", "radical", "fluorination"],
    "chemical biology & bioconjugation": ["protein", "peptide", "bioconjugat", "enzyme",
                                          "cell", "antibody", "drug", "nucleic", "bioorthogonal"],
    "materials & polymers": ["porous", "polymer", "framework", "co2", "carbon", "nanomaterial",
                             "electrode", "battery", "supercapacitor", "solar", "perovskite"],
    "supramolecular & soft matter": ["self-assembl", "gel", "micelle", "host", "molecular recognition",
                                     "supramolecular", "amphiphile", "vesicle"],
    "photochemistry & spectroscopy": ["fluorescen", "luminescen", "photophysic", "singlet",
                                      "photo", "probe", "sensor", "bioimag", "nanocluster"],
    "coordination & organometallic": ["metal", "coordination", "organometallic", "complex",
                                      "lanthanide", "transition metal", "ligand", "magnetism",
                                      "spin", "magnetic"],
    "crystallography & intermolecular": ["crystal", "intermolecular", "hydrogen bond",
                                         "halogen bond", "chalcogen bond", "cocrystal",
                                         "polymorph", "hirshfeld", "cage"],
    "computational & theory": ["dft", "density functional", "molecular dynamics", "simulation",
                               "ab initio", "electronic structure", "machine learning",
                               "mechanism", "kinetic", "thermodynamic", "pka", "computational"],
    "electrochemistry & energy": ["electro", "voltammet", "battery", "supercapacitor",
                                  "electrocatal", "water splitting", "fuel", "impedance"],
    "analytical & bioanalytical": ["detection", "sensor", "chromatograph", "mass spectrometr",
                                   "analyte", "quantitative", "assay"],
}

def load_journals():
    with open(DATA, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return rows

def match_area(desc):
    d = desc.lower()
    scores = []
    for area, kws in AREAS.items():
        s = sum(1 for k in kws if k in d)
        scores.append((s, area))
    scores.sort(reverse=True)
    return scores[0] if scores else (0, "general")

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__); sys.exit(0)
    if sys.argv[1] == "--list-areas":
        print("Areas in the matcher:")
        for a in AREAS:
            print(f"  - {a}")
        sys.exit(0)

    desc = " ".join(sys.argv[1:])
    score, area = match_area(desc)
    rows = load_journals()
    top = rows[:60]

    print(f"Description: {desc}")
    print(f"Matched area: {area} (score {score})\n")
    print("Top candidate journals from the IISER Bhopal portfolio:")
    print(f"{'journal':<45}{'papers':>7}  publisher")
    print("-" * 75)
    for r in top:
        j = r["journal"]
        pub = r.get("publisher", "") or ""
        print(f"{j[:44]:<45}{r['papers']:>7}  {pub[:40]}")
    print("\nNext: read docs/01-journal-requirements.md for limits & quirks,")
    print("then check the journal's official author-guidelines page.")

if __name__ == "__main__":
    main()
