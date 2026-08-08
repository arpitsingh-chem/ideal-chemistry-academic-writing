# LaTeX templates in this folder

## `manuscript/` — journal manuscript
- `main.tex` — complete skeleton: abstract, keywords, IMRaD sections,
  experimental section with characterisation data format, SI paragraph,
  CRediT/COI/data-availability back matter, natbib bibliography.
- `refs.bib` — sample bibliography (fill via `scripts/doi2bib.py`).
- `supporting-info.tex` — SI document with mini-TOC and contents checklist.
- `figures/` — put your figure PDFs here (`\graphicspath` is preconfigured).

### Compile
```bash
pdflatex main.tex && bibtex main && pdflatex main.tex && pdflatex main.tex
```

### Notes
- Uses `mhchem`, `chemfig`, `siunitx`, `chemmacros` (all in TeX Live —
  install `texlive-science`).
- Blue `\change{...}` macro + `lineno` for revision tracking (turn off before
  final submission — ACS rule).
- `natbib` set to author-year; switch to `unsrtnat` (numbered) or the
  publisher's `.bst` for ACS (`achemso` package) / RSC-Wiley (`rsc` package).

## `thesis/` — PhD thesis skeleton
- `thesis.tex` — book class, A4, 1.5-in binding margin, 1.5 spacing, roman
  preliminaries, arabic body, appendices.
- `chapters/prelims.tex` — title page, certificate, declaration,
  acknowledgements, abstract (adapt to institute manual).
- `chapters/abbreviations.tex` — chemistry-complete abbreviation list.
- `chapters/ch1..ch6` — introduction, methods, three results chapters,
  conclusions + future directions.
- `chapters/appendix_*` — spectra compilation + list of publications.

### Compile
```bash
pdflatex thesis && bibtex thesis && pdflatex thesis && pdflatex thesis
```

### Before final submission
- Insert institute logo (`figures/iiserb_logo.pdf`).
- Verify margins/fonts against the institute thesis manual.
- Run the institute similarity tool on a full draft; keep ≤10% similarity.
- Keep the whole project under Git — version history is authorship evidence.
