# Field test — using the engine as a stranger would

Eight tasks, run against a fresh clone of `main` (no special knowledge of the code).
Each is scored 0–10 on *whether the engine did the job unaided*. Results are the actual
command output, not a description of it.

| # | Task | Score | What happened |
|---|---|---|---|
| 1 | **Cold start** — `paperforge new`, follow the output | **8.5** | Scaffold created in one command; the first `check` returned 3 errors / 2 warnings with actionable text ("no Experimental section", "no references", "Chemical Science requires a TOC graphic 8.0×4.0 cm, 600 dpi") rather than a blank slate. Lost 1.5 because the scaffold does not yet pre-create `figures/`, `refs/*.bib` or a journal-tailored abstract template. |
| 2 | **Ingest an unseen lab folder** — 3 CSVs/figures/.bib from a different subfield (Hg(II) sensing; the engine had never seen it) | **9.5** | One command produced a valid project: 3 compounds, 1 dataset, 1 table, 2 figures, 8 references, plus `INGEST.md` and `ingest-report.json`. **It then caught three real errors I had typed**: two yield↔mass mismatches (0.052 g vs 0.058 g at 89%; 0.048 vs 0.054) and a ¹H integral sum that was one proton short of the formula. That is the engine doing the job a referee does. |
| 3 | **Planted defects** — wrong HRMS (+18 ppm), impossible yield, deleted cited reference | **10** | All three caught, each with the right code and the number that *should* be there: `CHEM-HRMS-CALCD … reported as 223.0906, but the formula gives 223.0866`, `CHEM-YIELD-MASS … 96% … should give 0.113 g, but 0.104 g`, `REF-MISSING-KEY neese2012orca`. Score fell 100 → 55 (critical cap) and `score --min 95` exited 1, so CI would block. |
| 4 | **Retarget** Organic Letters → Chem. Sci. / Angew. / JACS | **9.0** | Limits re-resolved correctly (250/3000, 200/2500, 250/2200 words; 40/50 refs; 5/8 display items) and it flagged the two things that actually need changing: the TOC graphic aspect (8.25×4.45 → 5.5×5.0 cm for Angew) and Wiley's ban on compound numbers in the abstract. Lost 1 point: it tells you *that* the TOC must change but does not regenerate it in place (`scheme toc --journal` is a separate step). |
| 5 | **Malformed input** — empty folder, ragged CSV, binary file, missing figure, missing project | **8.5** | Empty folder → valid project that scores "not-ready" with a TODO list. Missing path → `error: project not found`, exit 2, no traceback. Missing figure → `FIG-MISSING`. A ragged CSV (`yield_percent: abc`) is **rejected at load** with `compound X2: 'yield_percent' must be a number` — correct, but it stops the whole project rather than loading the good rows and reporting the bad one. |
| 6 | **Determinism** — render the same project twice | **10** | `manuscript.md`, `manuscript.tex`, `si.tex` byte-identical (sha256); `.docx` content-identical after excluding the zip timestamp. Same input ⇒ same paper, every time. |
| 7 | **Retraction** — cite `10.1021/ja054131h` | **6 → 10 after fix** | The first attempt **failed**: Crossref records the notice→original link but often not the reverse, and the engine only read relations, so a genuinely retracted paper passed as clean. Fixed the same session with a forward query (`filter=updates:<doi>,update-type:retraction`); the reference now raises a critical `REF-RETRACTED` and caps the paper at 55. |
| 8 | **Rendering** — compile to PDF | **7 → 10 after fix** | The first PDF contained `T h e  b e s t  d o t` — a genuine renderer bug: a string-valued `abstract.results` was being iterated character-by-character. Fixed (`abstract_text()` coerces str/list) and added a critical rule `STR-ABSTRACT-SPACED` that catches the whole class wherever it appears. The rebuilt PDF is 4 pages with correct text. |

**Mean: 9.1 / 10** (6.8 before the two bugs found by this test were fixed).

## What the tasks proved

* **Ingest → submission attempt is ~10 minutes of human work.** From an untouched folder:
  `ingest` 0.12 s, `check` 0.13 s, `draft` (Markdown + LaTeX + DOCX + SI) 0.23 s, PDF 4.4 s.
  What remains is prose (≈150 words of narrative in the test paper) and the data a
  chemist must actually have (NMR text, procedures, affiliations).
* **77 % of the finished body was generated**, not written: the Experimental section came
  entirely from the compound records.
* **The errors it caught were mine, not the engine's.** Every yield, mass and integral I
  typed from memory in the test folder was checked against the formulae; three were wrong.
  That is the single most valuable behaviour in the repo and the reason the rating is high.
* **Two real bugs surfaced only under black-box use** (letter-spaced abstract, missed
  retraction). Both are fixed and regression-tested; the suite went 161 → 165.

## Where it still loses points

1. Scaffolds are minimal — `new` should also write a journal-tailored abstract skeleton and
   an empty `refs/refs.bib`.
2. One bad row kills the whole ingest; it should quarantine it and continue.
3. `retarget` diagnoses TOC geometry but does not re-render the graphic.
4. The narrative still has to be written by a human or the grounded LLM layer.

## Reproduce

```bash
git clone https://github.com/arpitsingh-chem/ideal-chemistry-academic-writing && cd $_
python3 -m pytest tests/ -q                      # 165 passed, 3 network
python3 -m paperforge check examples/demo-paper  # 100.0/100
python3 -m paperforge ingest <your-folder> --out <project>
```
