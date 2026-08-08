# 08 · Data Deposition & Reproducibility

Chemistry journals increasingly *require* data availability — RSC states "data available on request" is not acceptable; Wiley requires a data-availability statement; ACS expects deposition for crystallography, nucleic-acid and protein data, and (for an increasing number of titles) raw data in repositories.

## 1. Crystallographic data (mandatory for every structure)

| Item | Requirement | Where |
|------|-------------|-------|
| CIF file(s) | Full structure solution data | CCDC (or FIZ Karlsruhe for inorganic-only) |
| checkCIF report | Validation, A/B alerts explained | upload with submission (RSC explicit; ACS expects) |
| CCDC number | Quoted in manuscript + SI | "CCDC 2400000 contain the supplementary crystallographic data for this paper" |
| ORTEP / thermal ellipsoid plots | In SI at minimum | SI |

- Deposit **before submission** — the accession number goes in the manuscript.
- CheckCIF: run via the free [checkCIF service](https://checkcif.iucr.org) or PLATON.

## 2. Spectroscopic & analytical data

| Data type | Good practice | Repository |
|-----------|---------------|------------|
| NMR FIDs/processed spectra | JCAMP-DX (.dx/.jdx) for key compounds (RSC standard) | SI + Zenodo/Figshare |
| HRMS raw files | report calcd vs found in SI | SI |
| IR/Raman | JCAMP-DX | SI |
| UV–vis/fluorescence | ASCII export + fitting parameters | SI + Zenodo |
| EPR/Mössbauer | parameters + fits | SI |

## 3. Computational data (theory papers)

- Software + version, level of theory, basis set, solvation model (explicit, not "default").
- Optimised coordinates: **XYZ or Gaussian archive entries** in SI or a repository (RSC: must be reproducible).
- Energies table: E, ZPE, G; imaginary frequencies for TS.
- Input files for the *exact* software version (e.g., ORCA/Gaussian inputs) on Zenodo/GitHub.
- Machine-learning (if used): model, training data, code, seeds.

## 4. Biological/chemical-biology data (RSC Medicinal Chem & ChemBioChem practice)

- Sequences: GenBank/UniProt; microarray: MIAME-compliant + GEO; PDB for structures.
- Bioactivity: dose–response curves, replicate counts, statistical tests; compounds ≥95% pure with proof.

## 5. General data repositories (free)

| Repository | What for | Notes |
|------------|----------|-------|
| Zenodo | Anything; DOI minting; GitHub integration | Free, CERN, unlimited public |
| Figshare | Figures, spectra, datasets | Free tier |
| OSF | Project + data + preprints | Free |
| CCDC / FIZ | Crystal structures | Free deposit |
| ChemRxiv / bioRxiv | Preprints (ACS, RSC, Wiley partner) | Cite in manuscript |

## 6. Reproducibility statement pattern

> "All data supporting this study are available within the paper and its Supporting Information. Crystallographic data for compounds 4, 9 and 12 have been deposited with the Cambridge Crystallographic Data Centre (CCDC 2400000–2400002). DFT-optimised coordinates are available on Zenodo (DOI: 10.5281/zenodo.0000000)."

---

*Next: [09-originality-and-ai-detection.md](09-originality-and-ai-detection.md)*
