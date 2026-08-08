# Contributing

This repository is a living document: journal guidelines change (often
without notice), new templates appear, and bugs surface. Contributions from
chemists, reviewers, and journal editors keep it accurate.

## What helps most

1. **Guideline updates** — a journal changed its abstract limit / TOC size /
   SI rules? Update `docs/01-journal-requirements.md` with the source link.
2. **Template fixes** — a LaTeX template fails to compile on a fresh TeX Live?
   File an issue with the error log.
3. **New scripts** — small, stdlib-only Python tools that fit the workflow.
4. **New data** — publication datasets for other departments/institutions in
   the `data/` format.

## Process

1. Fork the repo.
2. Create a branch: `git checkout -b fix/journal-guideline-2026`
3. Make your change; if it's a script, add a one-line usage to its docstring
   and test it: `python3 script.py --help`.
4. Update the relevant checklist if behaviour changes.
5. Open a PR with a clear description and, for guideline changes, the source
   URL.

## Standards

- Scripts: Python 3, **standard library only** (no pip dependencies), clear
  docstrings, exit code 0 on success.
- Docs: plain Markdown, tables for structured data, links relative within
  the repo, every claim about a journal requirement sourced.
- No claims of "undetectability" or detector-bypass magic — originality
  guidance follows `docs/09` (evidence-based, ethical).

## Code of conduct

Be constructive and specific. This project serves students and researchers;
comments that mock authors or journals are not welcome.
