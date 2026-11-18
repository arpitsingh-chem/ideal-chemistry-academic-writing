# Tutorial: your first manuscript

**Time:** 20 minutes. **You need:** Python ≥ 3.10 and this repository checked out.

You will scaffold a project, verify its references against Crossref, run the 115-rule
checker, and produce LaTeX, Markdown and DOCX output.

---

## 1. Install

```bash
python3 -m pip install -e ".[figures,docx,dev]"
python3 -m paperforge doctor
```

Expected (versions will differ):

```
paperforge 2.4.0
python 3.13.18
  ✓ yaml         YAML projects
  ✓ PIL          figure resolution checks
  ✓ docx         DOCX output
  ✓ matplotlib   demo figures
  ✓ chem engine: C14H10NO2S [M+H]+ = 257.0505
  data: 261 journals, corpus loaded
```

The last line is the important one: it is the chemistry engine computing a real adduct mass
during startup. If that number looked wrong, stop — everything downstream depends on it.

## 2. Look at a finished project first

```bash
python3 -m paperforge check examples/demo-paper
```

```
=== Visible-Light Photoredox C–H Arylation of Quinoxalin-2(1H)-ones with Aryl Diazonium Salts — Organic Letters (letter) ===
0 errors · 0 warnings · 0 notes

READINESS  100.0/100   grade A+   (submission-ready)
```

Now break something deliberately — change one yield in the scope table from 94 % to 194 %:

```bash
cp -a examples/demo-paper /tmp/broken
python3 - <<'EOF'
import csv, pathlib
p = pathlib.Path("/tmp/broken/data/scope.csv")
rows = list(csv.reader(p.open(newline="", encoding="utf-8-sig")))
for row in rows[1:]:
    if row[0] == "3a":
        row[4] = "194"                      # the yield column
csv.writer(p.open("w", newline="", encoding="utf-8")).writerows(rows)
EOF
python3 -m paperforge check /tmp/broken
```

```
1 errors · 0 warnings · 0 notes

[EVIDENCE]
  ✗ TAB-IMPOSSIBLE-VALUE     data/scope.csv: column 'yield_percent' has 1 percentage
                             value(s) outside the physical range (line 2: 194)
      → A percentage outside 0-100 is arithmetically impossible; recheck the value …

READINESS  97.6/100   grade A+   (submission-ready)
  evidence    ████████████████████░░  88.0  (weight 20%)
```

This is the whole idea: the checker reads the data, not just the prose. (This exact
black-box test is how the gap in `BUG_REGISTER.md` PF-021 was found — before v2.4.0 the
194 % table scored a perfect 100.)

## 3. Scaffold your own

```bash
python3 -m paperforge new my-paper --journal "Organic Letters"
find my-paper -type f | sort
```

```
created my-paper/paper.yaml
next: edit paper.yaml, then `paperforge draft .`
my-paper/README.md
my-paper/paper.yaml
```

A project is just a `paper.yaml` plus whatever data, figures and references you add;
`ingest` can build the YAML from a folder of files if you already have them.

Open `paper.yaml`. The fields that matter most:

```yaml
journal: Organic Letters
article_type: letter
title: "..."
authors:
  - name: Your Name
    affiliation: iiserb
    corresponding: true
    email: you@example.org
    orcid: 0000-0002-1825-0097      # check-digit validated
affiliations:
  iiserb: Department of Chemistry, IISER Bhopal
compounds:
  - id: "3a"
    formula: C14H10N2O              # parsed, validated, weighed
    mmol: 0.86
    yield_percent: 94
    mass_g: 0.164                   # cross-checked against mmol × MW × yield
    nmr_1h: "δ 8.21 (d, J = 8.8 Hz, 2H), 7.60 (t, 2H), 6.95 (m, 6H)"
    nmr_13c: "δ 162.1, 148.3, ..."
    hrms_adduct: "[M+H]+"
    hrms_calcd: 223.0866
    hrms_found: 223.0869
```

Do not fill in a value you do not have. A missing `hrms_found` produces a warning; an
invented one produces a passing score and a retraction later.

## 4. Verify references

```bash
python3 -m paperforge refs verify my-paper
```

```
8 references: 8 verified, 0 unverified, 0 not found, 0 retracted, 0 duplicate DOI(s)
  ✓ romero2016organic            10.1021/acs.chemrev.6b00057         Organic Photoredox Catalysis
  ...
```

This resolves every DOI at Crossref, checks **backwards** for a retraction notice that
updates the DOI, and caches the result in `.paperforge/refcache.json` so later checks work
offline.

## 5. Check, then draft

```bash
python3 -m paperforge check my-paper
python3 -m paperforge draft my-paper --format all --cover-letter --highlights
```

```
wrote my-paper/build/manuscript.md
wrote my-paper/build/manuscript.tex
wrote my-paper/build/si.tex
wrote my-paper/build/manuscript.docx
wrote my-paper/build/cover_letter.md
wrote my-paper/build/highlights.md
```

To get a PDF, compile the `.tex` with any LaTeX engine:

```bash
cd my-paper/build && tectonic manuscript.tex
```

## 6. What just happened

| Step | What verified it |
|---|---|
| `doctor` | the chemistry engine computes a known adduct mass |
| `check` | 115 rules over structure, evidence, references, figures, journal fit, ethics, style |
| `refs verify` | every DOI resolved at Crossref, retraction lookup included |
| `draft` | Markdown/LaTeX/DOCX from the same data, so they cannot disagree |

## Next

* [Verify references properly](../guides/verify-references.md) — including what to do with
  a retracted citation.
* [The verification model](../explanations/verification-model.md) — what a green score
  actually means (less than you might hope).
* [CLI reference](../reference/cli.md) — every command and flag.
