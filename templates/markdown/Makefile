# Makefile — Markdown → journal manuscript (Pandoc)
# Usage:
#   make pdf     -> manuscript.pdf (LaTeX engine, ci author-year)
#   make docx    -> manuscript.docx (Word; then paste into journal template)
#   make clean
#
# Requires: pandoc, pandoc-citeproc (or built-in citeproc), a CSL style file.
# CSL styles: ACS  -> https://www.zotero.org/styles/journal-of-the-american-chemical-society
#             RSC  -> https://www.zotero.org/styles/royal-society-of-chemistry
#             Wiley-> https://www.zotero.org/styles/angewandte-chemie

PAPER   := manuscript
STYLE   := acs.csl
BIB     := refs.bib
ENGINE  := pdflatex

all: pdf docx

pdf:
	pandoc $(PAPER).md --citeproc --csl=$(STYLE) --bibliography=$(BIB) \
	  -V geometry:margin=2.5cm -V fontsize=12pt -V linestretch=1.5 \
	  -V colorlinks=true --pdf-engine=$(ENGINE) -o $(PAPER).pdf

docx:
	pandoc $(PAPER).md --citeproc --csl=$(STYLE) --bibliography=$(BIB) \
	  --reference-doc=ref.docx -o $(PAPER).docx

html:
	pandoc $(PAPER).md --citeproc --csl=$(STYLE) --bibliography=$(BIB) \
	  --standalone -o $(PAPER).html

clean:
	rm -f $(PAPER).pdf $(PAPER).docx $(PAPER).html *.aux *.log *.out *.bbl *.blg

.PHONY: all pdf docx html clean
