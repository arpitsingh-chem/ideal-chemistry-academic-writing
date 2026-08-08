# 07 · Citations & References — Styles, Hygiene, and Tools

## 1. The three families

| Family | Style | Example | Used by |
|--------|-------|---------|---------|
| **ACS** | Numbered, superscript/bracketed; title required in most titles | (1) *J. Am. Chem. Soc.* **2024**, *146*, 1234–1245. | JACS, Org. Lett., JOC, Inorg. Chem., CGD, ACS Catal., JPCC… |
| **RSC** | Numbered or author–year per journal; some require titles | *Chem. Commun.*, **2024**, *60*, 1234 (DOI: 10.1039/…) | ChemComm, Dalton Trans., Chem. Sci., NJC, PCCP… |
| **Wiley** | Numbered, bracketed; titles required; article numbers | *Angew. Chem. Int. Ed.* **2024**, *63*, e2024xxxxx. | Angew., Chem. Eur. J., Eur. JOC, Small… |

**Universal minimum per entry:** authors (all or first 10 + et al.), article title, journal (abbreviated properly), year, volume, page/article number, DOI.

## 2. Reference hygiene checklist

- [ ] Every reference resolvable: DOI or stable URL. (Test: `scripts/doi2bib.py` fetches metadata; a successful fetch = resolvable DOI.)
- [ ] Journal abbreviations standardised (CASSI-style: *J. Am. Chem. Soc.*, not *Journal of the American Chemical Society* — check the target journal's practice).
- [ ] No duplicate references; no "ibid./op. cit." in numbered styles.
- [ ] Online-only items cited by DOI.
- [ ] Personal communications → author permission + "unpublished results" convention; in-press papers → uploaded as SI for review (ACS).
- [ ] Balanced recency: include ≥30% references from the last 3–4 years for a methods paper.
- [ ] No excessive self-citation (ACS explicitly prohibits).
- [ ] Citation order follows first mention (numbered styles).

## 3. Building the bibliography

### Workflow (all free)
1. **Zotero** (or JabRef) as the master library; *Better BibTeX* extension for citation keys.
2. For papers not in your library: `scripts/doi2bib.py <DOI> [<DOI> …]` → pulls clean BibTeX from **CrossRef (free, no key)**.
3. For DOIs from publishers without CrossRef metadata (rare): manual entry.
4. Compile with the journal's BibTeX style:
   - ACS: `achemso` class + `acs-*.bst` styles (Joseph Wright, CTAN/GitHub).
   - RSC/Wiley: `rsc` package styles (Joseph Wright, GitHub).
   - Or paste into the journal's Word template and use its EndNote/Zotero CSL (ACS/RSC/Wiley all provide CSL files for Zotero/Mendeley).

### BibTeX keys
`[FirstAuthorSurname][Year][FirstKeywordWord]` → `dutta2024chalcogen`. Consistent keys make revisions painless.

## 4. Citing chemistry specifics

- **Compounds/structures** are numbered in text (1, 2, 3…); they are *not* references.
- **Software**: cite the package + the method paper (Gaussian 16, ORCA, VASP, ChemDraw…).
- **Crystallographic data**: cite the CCDC deposition number as a data citation.
- **Datasets**: RSC data-citation format — `[Name(s)], [Repository], [Deposition number], [Year], DOI: …` (see `docs/06`).
- **Preprints** (ChemRxiv/bioRxiv): cite as such with DOI; disclose in cover letter; most journals accept and expect the preprint citation.

## 5. Common rejectable citation errors

- Citing reviews where primary data is the point.
- Citing retracted papers (check: PubMed/Retraction Watch/Crossref "retracted" flags).
- Incomplete entries (missing volume/pages → automated checks fail).
- Reference numbering gaps (ACS requires sequential first-mention order).

---

*Next: [08-data-deposition.md](08-data-deposition.md)*
