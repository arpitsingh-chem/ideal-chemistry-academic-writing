# Ideal Chemistry Academic Writing

**A research-grade toolkit for writing, reviewing, and submitting chemistry manuscripts, theses, and peer reviews — built from an evidence base of 1,700+ publications from the IISER Bhopal Department of Chemistry, 257 target journals, and publisher-verified author guidelines (ACS · RSC · Wiley).**

> *"Write like the chemists who publish where you want to publish."*

This repository distils what a **publishable, defensible, original** chemistry manuscript, thesis, or peer review must contain — verified against the actual journals in which IISER Bhopal chemists publish (JACS, Angewandte Chemie, Chemical Science, Organic Letters, ChemComm, Inorganic Chemistry, and 250+ more) — and packages it as templates, checklists, and working scripts you can use today.

---

## What is inside

```
ideal-chemistry-academic-writing/
│
├── docs/                       # The "why" — evidence-based writing guides
│   ├── 01-journal-requirements.md        # 40+ journals analysed: IF, scope, limits, quirks
│   ├── 02-ideal-paper-blueprint.md       # The synthesised "ideal paper" specification
│   ├── 03-thesis-blueprint.md            # PhD thesis (Indian-university standard)
│   ├── 04-peer-review-blueprint.md       # How to review like a professional chemist
│   ├── 05-cover-letter-and-response.md   # Cover letters + response-to-reviewers
│   ├── 06-supporting-information.md      # SI standards across publishers
│   ├── 07-citations-and-references.md    # ACS/RSC/Wiley styles, DOI hygiene
│   ├── 08-data-deposition.md             # CCDC, CSD, NMR/HRMS deposition, checkCIF
│   ├── 09-originality-and-ai-detection.md# Evidence-based originality & AI-detector literacy
│   └── 10-free-tools-and-apis.md         # Free tiers: APIs, keys, local LLMs
│
├── templates/                  # The "how" — ready-to-compile starting points
│   ├── latex/manuscript/       # Chemistry manuscript (mhchem, chemfig, SI)
│   ├── latex/thesis/           # Full PhD thesis skeleton (7 chapters + bib)
│   ├── word/                   # Manuscript template (.docx)
│   ├── markdown/               # Pandoc-manuscript workflow
│   └── review/                 # Peer-review report template
│
├── checklists/                 # One-page compliance lists
│   ├── pre-submission-checklist.md
│   ├── thesis-checklist.md
│   └── peer-review-checklist.md
│
├── scripts/                    # Working tools (Python 3, stdlib only)
│   ├── manuscript_check.py     # Automated compliance checker for your manuscript
│   ├── text_stats.py           # Readability / sentence-rhythm ("humanisation") profile
│   ├── doi2bib.py              # DOI → BibTeX via the free CrossRef API
│   ├── journal_matcher.py      # Journal suggestion from the IISER Bhopal dataset
│   └── new_paper.sh            # Scaffold a new manuscript folder in one command
│
├── examples/                   # Realistic, journal-calibrated examples
│   ├── abstract-before-after.md
│   ├── cover-letter-example.md
│   ├── response-to-reviewers-example.md
│   ├── experimental-section-example.md
│   └── peer-review-example.md
│
└── data/                       # The evidence base (OpenAlex, free API)
    ├── iiserb-bhopal-chemistry-journals.csv   # 257 journals, paper counts
    ├── iiserb-bhopal-scholars.csv             # 200 early-career co-authors
    ├── iiserb-bhopal-faculty.md               # 30 faculty + research areas
    └── publications-sample.json               # 200 sample records
```

---

## Quick start (5 minutes)

```bash
# 1. Scaffold a new manuscript
bash scripts/new_paper.sh my_first_paper

# 2. Write your draft in LaTeX (templates/latex/manuscript/) or Word/Markdown

# 3. Run the compliance checker on your draft
python3 scripts/manuscript_check.py my_first_paper/main.tex

# 4. Convert DOIs to BibTeX as you go (free CrossRef API, no key needed)
python3 scripts/doi2bib.py 10.1002/anie.202100123 10.1021/jacs.1c01020

# 5. Profile your prose before submission
python3 scripts/text_stats.py my_first_paper/main.tex

# 6. Work through checklists/pre-submission-checklist.md, then submit
```

---

## The evidence base

| Item | Value |
|---|---|
| Faculty analysed | 30 (all IISER Bhopal Department of Chemistry faculty) |
| Publications captured | 1,646–1,707 (2009–2026, OpenAlex) |
| Distinct journals | 257 |
| Early-career co-authors (PhD scholars, postdocs, alumni) | 800+ |
| Publisher families covered | ACS, RSC, Wiley-VCH, Elsevier, Springer, IUCr, RSC preprints |

**Top-10 journals** in the IISER Bhopal chemistry portfolio:

| # | Journal | Papers | Publisher |
|---|---------|--------|-----------|
| 1 | Chemical Communications | 99 | RSC |
| 2 | Chemistry – A European Journal | 93 | Wiley-VCH |
| 3 | Organic Letters | 82 | ACS |
| 4 | Angewandte Chemie Int. Ed. | 74 | Wiley-VCH |
| 5 | Chemistry – An Asian Journal | 49 | Wiley |
| 6 | Crystal Growth & Design | 49 | ACS |
| 7 | Dalton Transactions | 44 | RSC |
| 8 | Inorganic Chemistry | 39 | ACS |
| 9 | The Journal of Organic Chemistry | 38 | ACS |
| 10 | CrystEngComm | 32 | RSC |

Full analysis (scope, impact factor, article types, word/page limits, graphics rules, unique quirks per journal): **[docs/01-journal-requirements.md](docs/01-journal-requirements.md)**

---

## The core philosophy (read this before anything else)

1. **Journals are the spec.** Every claim in this repo about "what a paper must contain" traces back to a publisher guideline (ACS, RSC, Wiley) or to the observed practice of IISER Bhopal chemists in 1,700+ papers. When in doubt, check the journal's own "author guidelines" page — links are in `docs/01`.

2. **Originality is built, not patched.** The only reliable way to pass originality checks (Turnitin similarity) and to survive AI-detection false positives is to write original text yourself, document your process, and cite correctly. There is no shortcut that survives contact with the quarterly-updated detectors; the professional workflow is presented in `docs/09`.

3. **Reproducibility is a chemistry requirement, not a bonus.** Every new compound needs full characterisation (¹H/¹³C NMR, HRMS, IR, melting point, [α]D where chiral, elemental analysis or HRMS), yields in g *and* mmol, CCDC deposition for crystal structures with checkCIF, and an experimental section a skilled researcher can repeat. This is non-negotiable at all 257 journals analysed.

4. **AI tools are assistants, not authors.** Use them for editing, templating, and literature triage — disclose per journal policy — and keep authorship, claims, and data human-owned. Details in `docs/09` and `docs/10`.

---

## License & citation

Content is licensed under **CC BY 4.0** (attribution appreciated, reuse encouraged). If this toolkit saves you a desk-rejection, cite it:

```bibtex
@misc{ideal-chemistry-academic-writing,
  title  = {Ideal Chemistry Academic Writing},
  year   = {2026},
  note   = {Evidence base: 1700+ publications, IISER Bhopal Department of Chemistry}
}
```

---

## Contributing

Found a journal guideline that changed? A template bug? See [CONTRIBUTING.md](CONTRIBUTING.md). PRs from chemists and journal editors are the way this stays accurate.
