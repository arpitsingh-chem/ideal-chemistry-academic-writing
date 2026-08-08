#!/usr/bin/env bash
# new_paper.sh — scaffold a new manuscript folder in one command.
#
# Usage:
#   bash scripts/new_paper.sh my_first_paper
#   bash scripts/new_paper.sh "pd-catalyzed-coupling"   (kebab-case preferred)
set -euo pipefail

NAME="${1:-}"
if [[ -z "$NAME" ]]; then
  echo "Usage: bash scripts/new_paper.sh <paper-name>"; exit 1
fi
NAME="$(echo "$NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')"
DEST="${NAME}"
mkdir -p "${DEST}/figures" "${DEST}/data" "${DEST}/si"

# Copy templates (this script lives in scripts/, templates in ../templates)
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"

if [[ -f "${ROOT}/templates/latex/manuscript/main.tex" ]]; then
  cp "${ROOT}/templates/latex/manuscript/main.tex" "${DEST}/main.tex"
  cp "${ROOT}/templates/latex/manuscript/supporting-info.tex" "${DEST}/si/si.tex"
  : > "${DEST}/refs.bib"
  echo "LaTeX templates copied (main.tex, si/si.tex, refs.bib)."
else
  echo "NOTE: templates not found at ${ROOT}/templates — creating empty structure only."
fi

cat > "${DEST}/notes.md" <<'EOF'
# Notes for this paper

## One-line story
[We discovered/disproved/synthesised X, which matters because Y, as shown by Z.]

## Target journals (shortlist, ranked)
1. (first choice)
2. (backup)
3. (safety)

## Claims -> evidence map
| Claim | Evidence (figure/table/SI) | Status |
|-------|---------------------------|--------|
|       |                           |        |

## Characterisation tracker
| Compound | 1H NMR | 13C NMR | HRMS | IR | mp | purity | CCDC |
|----------|--------|---------|------|----|----|--------|------|
EOF

cat > "${DEST}/TODO.md" <<'EOF'
# TODO
- [ ] Literature review complete (Zotero)
- [ ] Figures finalised (>=300 dpi)
- [ ] Experimental section complete + safety statement
- [ ] SI compiled (spectra for all new compounds)
- [ ] Run: python3 ../ideal-chemistry-academic-writing/scripts/manuscript_check.py main.tex
- [ ] Cover letter drafted (examples/cover-letter-example.md)
- [ ] Internal review by co-authors
EOF

echo ""
echo "Scaffolded paper folder: ${DEST}/"
echo "  main.tex      — manuscript (fill refs.bib: python3 scripts/doi2bib.py <DOI>)"
echo "  si/si.tex     — supporting information"
echo "  figures/ data/ — assets"
echo "  notes.md      — story, journal shortlist, claims map, characterisation tracker"
echo "  TODO.md       — submission checklist"
echo ""
echo "Next: bash ${ROOT}/scripts/manuscript_check.py ${DEST}/main.tex"
