# 06 · Supporting Information — The Second Manuscript

In chemistry, SI is where papers are won or lost at review. ~90% of IISER Bhopal portfolio papers carry SI; reviewers check it first for characterisation completeness.

## 1. SI rules that apply everywhere

| Rule | ACS | RSC | Wiley |
|------|-----|-----|-------|
| Separate file from manuscript | ✅ | ✅ | ✅ |
| Numbered pages consecutively | ✅ | ✅ | ✅ |
| Items labelled Figure S1 / Scheme S1 / Table S1 (prefix S) | ✅ | ✅ | ✅ |
| Descriptive "Supporting Information" paragraph in main text | ✅ | — | — |
| Spectral data for all new compounds | ✅ (required for characterisation) | ✅ (JCAMP-DX encouraged) | ✅ (required) |
| checkCIF files with CCDC numbers | ✅ | ✅ | ✅ |
| "Review-only" files (related submitted work) | ✅ | — | — |

## 2. The standard SI table of contents (chemistry)

1. **General experimental details** — instruments, software versions, sources of reagents.
2. **Synthetic procedures and characterisation** — every compound: yield, NMR, HRMS, IR, mp; spectra pages.
3. **NMR spectra** — one page per compound (¹H and ¹³C; 2D where claimed: COSY, NOESY, HSQC, HMBC). Label: compound number, solvent, frequency, structure inset (journal practice).
4. **HRMS / mass spectra** — calculated vs. found (exact mass), adduct annotation.
5. **IR spectra** — key bands annotated.
6. **UV–vis / fluorescence / lifetime data** — spectra, τ fits, quantum-yield details (reference standard, refractive-index correction if used).
7. **Crystallographic data** — ORTEP plots with thermal ellipsoids, CCDC numbers, checkCIF outputs, selected bond lengths/angles table, H-bond tables, Hirshfeld surface analyses (if discussed).
8. **Magnetic / EPR / Mössbauer data** — measurement conditions, corrections (Pascal's), fitting parameters.
9. **Electrochemical data** — CV/DPV conditions, potentials vs. reference, ferrocene internal reference.
10. **Computational details** — software, level of theory, basis sets, solvation model, coordinates of optimised structures, energies, imaginary frequencies (transition states), XYZ files or archive entries.
11. **Copies of "in press" related work** (review only, ACS).

## 3. Writing SI like a professional

- **One SI PDF** (or logical set: PDF + CIF + XYZ + mol files), professionally formatted: title page mirroring the manuscript ("Supporting Information — *Title*, Authors, Affiliation"), a mini-TOC, numbered pages S1…Sn.
- Descriptive SI paragraph in the manuscript (ACS format):

> Supporting Information: General experimental methods (PDF); ¹H and ¹³C NMR spectra for compounds 3–15 (PDF); HRMS spectra (PDF); crystallographic data for 4, 9 and 12 (CIF); DFT-optimised coordinates (XYZ); electrochemical data (PDF).

- **Insufficient** (ACS explicitly rejects): "Supporting Information: Figures S1–S3".

## 4. Spectral data reporting format (copy this)

```
Compound 5 (yellow solid, 68%): ¹H NMR (400 MHz, CDCl₃) δ 8.21 (d, J = 8.8 Hz, 2H, ArH),
7.42 (dd, J = 8.8, 2.1 Hz, 2H, ArH), 6.98 (d, J = 2.1 Hz, 2H, ArH), 3.92 (s, 3H, OCH₃);
¹³C{¹H} NMR (100 MHz, CDCl₃) δ 161.2, 144.3, 131.8, 125.4, 120.7, 111.9, 55.6;
IR (KBr) ν̄ 2224 (C≡N), 1608, 1512 cm⁻¹; HRMS (ESI-TOF) m/z calcd for C₁₄H₁₀NO₂S [M+H]⁺ 256.0427, found 256.0431; mp 142–144 °C.
```

## 5. Data deposition (see [08-data-deposition.md](08-data-deposition.md))

- CCDC for crystal structures (number + checkCIF at submission).
- CSD/other repositories per discipline.
- Raw NMR/FIDs: encourage Zenodo/Figshare/OSF deposits (RSC/Wiley now expect data availability).
- Coordinates/inputs for computational work.

---

*Next: [07-citations-and-references.md](07-citations-and-references.md)*
