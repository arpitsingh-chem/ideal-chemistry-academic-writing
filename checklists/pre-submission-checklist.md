# Pre-Submission Checklist — Chemistry Manuscript

> Work through this 48 hours before submitting. It encodes the requirements of the 257-journal portfolio (`docs/01`). Print it, tick it, submit without fear.

## A. Science & claims
- [ ] Every headline claim in the abstract maps to a figure/table/entry in the paper.
- [ ] No hype words in title/abstract ("novel", "first", "superb", "excellent"…) unless rigorously supported.
- [ ] All quantities check out: yields (g ↔ mmol ↔ %), concentrations, rate constants, detection limits.
- [ ] Controls complete; alternative interpretations discussed.
- [ ] Error bars + uncertainty analysis; significant figures correct throughout.

## B. Characterisation (chemistry non-negotiables)
- [ ] Every NEW compound: ¹H NMR, ¹³C NMR, HRMS, IR, melting point (+ [α]D if chiral, + elemental analysis/purity proof).
- [ ] NMR assignments consistent (integration, multiplicity, J values); 2D data included where claims require.
- [ ] Known compounds: literature characterisation cited (RSC rule).
- [ ] Crystal structures: deposited at CCDC *before* submission; CCDC numbers + checkCIF in SI; ORTEPs in SI.
- [ ] Magnetic/EPR data: measurement conditions + Pascal's-correction statement (ACS).
- [ ] Computational work: level of theory + basis set + solvation stated; coordinates in SI.

## C. Manuscript format (verify against the target journal's template)
- [ ] Title ≤18 words; author list identical on ALL files (manuscript, SI, cover letter, submission form).
- [ ] ORCID for corresponding author; e-mails for all authors.
- [ ] Abstract present + within limit (ACS ≤300 / RSC 50–250 / Wiley ≤200) + no refs/graphics in abstract.
- [ ] TOC/graphical abstract: ACS 3.25×1.75 in / RSC 8×4 cm >600 dpi / Wiley 5×5 cm (+450-char text).
- [ ] Keywords 4–7, lowercase.
- [ ] Figures placed near first mention (ACS) or per template; ≥300 dpi (600 line art); all cited in text, numbering gapless.
- [ ] Experimental section complete + safety statement included.
- [ ] Conclusion present (recommended ACS; required Wiley reviews).
- [ ] References: journal style, complete entries incl. titles, DOIs tested, sequential numbering, no self-citation excess.
- [ ] CRediT + acknowledgements + funding/grant numbers + COI + data-availability statement.
- [ ] AI-use disclosure (per journal policy) in cover letter.
- [ ] Track changes OFF; manuscript clean.

## D. Supporting Information
- [ ] Separate file(s); pages numbered; items labelled S1…; mini-TOC on first page.
- [ ] All spectra pages present (one compound per page, labelled with structure).
- [ ] Descriptive "Supporting Information" paragraph in manuscript (ACS format).
- [ ] checkCIF files, CIFs, XYZ coordinates attached.
- [ ] Related in-press/submitted works attached as *review-only* SI (ACS).

## E. Cover letter (see `docs/05` + `examples/cover-letter-example.md`)
- [ ] 1 page; editor's name current; significance paragraph; scope-fit sentence.
- [ ] Originality/ethics declarations; suggested + opposed reviewers.
- [ ] AI-use statement if applicable.

## F. Final technical pass
- [ ] `python3 scripts/manuscript_check.py main.tex` → 0 errors.
- [ ] `python3 scripts/doi2bib.py $(grep -oP '10\.\S+' main.tex | sort -u)` → all DOIs resolve.
- [ ] `python3 scripts/text_stats.py main.tex` → read the rhythm profile (false-positive alarm only).
- [ ] PDF compiles from a clean checkout (LaTeX) or template PDF export (Word).
- [ ] Spell-check + one full read-aloud pass.
- [ ] All authors have read and approved the final version (co-author notification at ACS/Wiley).

## G. On submission day
- [ ] Files uploaded: manuscript, SI (publication), SI (review-only, if any), figures, cover letter, TOC graphic, checkCIF/CIFs, data files.
- [ ] Metadata matches manuscript exactly (title/authors/abstract box vs. file).
- [ ] Confirm submission e-mail arrives; note manuscript ID.
