# The hardest task — limit audit of PaperForge

**Method.** One project, built to be hostile in every dimension at once, was pushed through
`ingest → check → draft → PDF → bundle → retarget`. Every failure was reproduced, logged,
root-caused and fixed under the *ponytail* rule (smallest complete diff, no new dependency,
one small test per real bug). Nothing was fixed speculatively.

**Verdict: 5.9/10 as shipped → 8.7/10 after 14 fixes.** The engine is excellent at the
things it measures and was blind to the one thing that matters most: **a number attached to
the wrong compound**. That is now a hard error, not a silent pass.

---

## 1. The task

| Dimension | What was built |
|---|---|
| Encoding | `compounds.csv`: UTF-8 **BOM** byte-order mark over a **Latin-1** body, CRLF line endings |
| Delimiters | `;` separator, **decimal commas** (`89,5`, `0,400`) |
| Schema drift | headers `MW`, `mass (g)`, `yield`, `HRMS calcd`, `compound` (not `name`) |
| Dirty data | duplicate `P2` row, an inorganic salt (CuSO₄·5H₂O) and an Ir(III) complex in an "organic compounds" table |
| Scale | `kinetics.csv`, 2,000 rows, same dialect |
| References | Zotero-style `.bib`: LaTeX accents (`J{\"o}rg`), nested braces, a **duplicate DOI in different case**, a **retracted DOI**, a key containing `_` |
| Figures | 299 dpi (must fail), 300 dpi, TOC at 16:9 for a 2:1 slot |
| Tables | one 14-column table; one **whose data file does not exist** |
| Manuscript | formally impeccable, **scientifically wrong**: a detection limit that exists in no data file, a selectivity figure that appears nowhere, and two yields swapped between compounds |

## 2. Every error found

Severity: **A** = wrong output, **B** = silent data loss, **C** = crash/cosmetic.

| # | Sev | Bug | Evidence before the fix | Fix |
|---|---|---|---|---|
| 1 | B | A Latin-1 CSV is dropped, exit 0 | `compounds 0 … note: unreadable ('utf-8' codec can't decode byte 0xb7 in position 392)` | decode utf-8, then Latin-1; BOM stripped first |
| 2 | A | Decimal comma read as a thousands separator | `'89,5'→895.0`, `'0,400'→400.0`, `'162,21'→16221.0` — a silent **10–1000×** error no later rule can see | `_number()`: last separator wins; a comma groups thousands only when followed by exactly 3 digits and not preceded by `0` |
| 3 | A | `csv.Sniffer` picks `,` on a European export (decimal commas outnumber the real separator) → header becomes one column | `compounds 0 · datasets 2 · tables 1` | count separators in the **header line only** |
| 4 | A | Duplicate compound ID passes | Experimental printed "Compound P2" twice, score unaffected | `EVI-DUP-ID` (error) |
| 5 | B | A table whose data file is missing renders an empty one-column table | `\begin{tabular}{l}` + `\toprule\midrule\bottomrule`, **no diagnostic at all** (figures had `FIG-MISSING`, tables had nothing) | `TAB-MISSING` (error) |
| 6 | C | Reference keys containing `_` break the LaTeX build | `manuscript.tex:37: Missing \endcsname inserted` — every Zotero key like `smith_2020` kills the PDF | un-escape only inside `\cite{…}` |
| 7 | C | `¹³C{¹H}` printed as `¹³C\{¹H\}` (escaped braces) in every Experimental | visible in the rendered page | stash the whole token before escaping |
| 8 | C | "Compound P1: **P1** (89.5 %…)" — a name column called `compound` is not recognised, the name falls back to the id | `name: 'P1'` for all five compounds | `compound` added to the `name` aliases + a `name != id` guard |
| 9 | A | **A yield attributed to the wrong compound passes** | "P2 was obtained in 89.5 % yield" (89.5 is P1's) → **95.2/100 A+, submission-ready** | `GRD-ATTRIB`: a `%`/`mmol` value that is another compound's own value is an error |
| 10 | A | Duplicate DOI (one work, two keys) passes | `refs check file.bib` caught it; `check <project>` did not | `REF-DUPLICATE-DOI` (warn) |
| 11 | A | An **offline** check forgets a retraction it already cached → `check` says A-, `bundle` says D for the same project | 87.4 A- vs 55.0 D | consult `.paperforge/refcache.json` offline |
| 12 | C | `llm-draft` with no model running dumps a `URLError` traceback | `urllib.error.URLError: [Errno 111] Connection refused` | `error: LLM request failed (…); is ollama reachable and configured?`, exit 2 |
| 13 | A | `paperforge rules` under-reports the rule set: the prefix regex misses `TOC-*` and `TABLE-*`, and `figures.py` is never scanned | printed **91** codes, engine emits **113** | scan both modules, widen the prefixes |
| 14 | C | `refs add` tells the user to run `paperforge refs add --write`; **that flag does not exist** | `error: unrecognized arguments: --write` | deleted the false option from the hint |

Two further defects found and **deliberately not fixed**, because the fix would cost more
than the defect:

- An unknown citation key is reported twice (`REF-MISSING-KEY` from the bibliography pass and
  `GRD-CITE` from the paragraph pass). Both messages are correct; merging them would couple
  two independent passes for cosmetics. `shortcut: duplicate message per unknown key, when a
  user reports it as noise.`
- `EVI-UNGROUNDED-ABSTRACT` is a **warning**: an abstract number absent from every data file
  costs ~1.5 points and still grades A+. Raising it to an error needs a way to mark
  literature values, otherwise every real abstract fails. `shortcut: warn-level ungrounded
  abstract numbers, upgrade when a citation-aware number provenance model exists.`

## 3. The central finding

The tool's promise is that a green score means a submittable paper. On the hard case it
delivered **95.6/100, grade A+, zero errors** for a manuscript that claimed a **12.4 nM**
detection limit that appears in no data file, a **38-fold** selectivity that appears nowhere
either, and — after the swap — two yields attached to the wrong compounds.

Root cause: `evidence_number_set()` collects every number in every file into one flat set,
and `check_grounding` asks only *"is this number anywhere in the project?"* With a 2,000-row
kinetics table, most small integers are "grounded" by coincidence. Numbers were grounded to
the **project**, never to the **object** they describe.

`GRD-ATTRIB` closes the highest-value half of that gap for 15 lines: for each clause that
names exactly one compound, a percentage or amount that is *another* compound's recorded
value is an error. It catches the swap, and it does not fire on either bundled example.

## 4. Feature-by-feature check

| Feature | Command | Result on the hard case | Score |
|---|---|---|---|
| Ingest | `ingest` | Now 5 compounds with correct names, 2 datasets, 14-col table; was 0 compounds | **9** (was 3) |
| Chemistry arithmetic | `check` | HRMS formula/ppm, yield↔mass, H-count vs formula, MW — all correct | **10** |
| Journal profiles | `journals`, `retarget` | TOC 8×4 → Angew 5.5×5.0 and JACS 8.25×4.45 both flagged with the new geometry | **9** |
| Figures | `figures inventory` | 299 dpi caught; 600 dpi TOC accepted | **9** |
| References | `refs verify/check/add` | retraction found via `updates:` filter; bib-level duplicate detection; project-level now too | **9** |
| Attribution | `check` | **was the hole**, now `GRD-ATTRIB` | **8** (was 2) |
| Composition | `draft` | MD/TeX/DOCX/SI in 0.2 s; LaTeX now compiles with hostile keys | **9** |
| Rendering | `tectonic` | 4 pages, 0 `[?]`, table shrunk to fit, subscripts and ¹³C{¹H} correct | **9** |
| Packaging | `bundle` | 15 files, score now agrees with `check` | **9** |
| Rules registry | `rules` | 113 codes, was silently 91 | **9** (was 5) |
| LLM pass | `llm-draft` | graceful failure; **not tested against a live model** (no endpoint) | **6** |
| Schemes | `scheme` | clean "RDKit is required" error; RDKit not installed | n/a |

## 5. What it did right

- Caught the retracted reference and capped the paper at **55.0 D** — twice, from two
  independent code paths, deduplicated.
- Caught a 299 dpi figure, an over-long TOC text, a missing data-availability statement, an
  abstract below the journal minimum, a TOC geometry mismatch on retarget, and a 14-column
  table that would overflow (auto `\resizebox`).
- Deterministic byte-for-byte output; 0.2 s to compose, 4 s to typeset.

## 6. Rating

| | Before | After |
|---|---|---|
| Hostile ingest | 3/10 | 9/10 |
| Formal compliance | 10/10 | 10/10 |
| Scientific correctness | 2/10 | 8/10 |
| Rendering | 6/10 | 9/10 |
| Feature coverage | 8/10 | 9/10 |
| **Hard-case total** | **5.9/10** | **8.7/10** |

The remaining 1.3 points are the attribution model: `%` and `mmol` are covered, nothing else
is.

## 7. Reproduce

`/tmp/hard` is the audit fixture built for this run; it is not committed (the hostile CSV
dialects and the wrong-but-green manuscript are the point, and shipping them would be noise).
Rebuild it with the recipe in §1, or ask and it can be committed under `tests/fixtures/`.

```bash
cd ideal-chemistry-academic-writing
python3 -m paperforge ingest   /tmp/hard --out /tmp/hard/p
python3 -m paperforge check    /tmp/hard/p --verify-refs   # 55.0 D, retracted ref
python3 -m paperforge draft    /tmp/hard/p
cd /tmp/hard/p/build && tectonic -X compile manuscript.tex
python3 -m pytest -q                                        # 173 passed, 3 skipped
```

## 8. Skipped, and the risk

- `GRD-ATTRIB` covers **yields (%) and amounts (mmol)** only — not HRMS m/z, ee, or
  temperatures. Risk: a swapped HRMS value between two compounds still passes if each value
  is individually valid.
- The grounding set is still **project-wide**, not object-wide; with a large dataset most
  numbers are "grounded" by coincidence. Risk: an invented number that happens to occur in
  the data is invisible.
- `llm-draft` and `scheme` were exercised only on their failure paths. Risk: unknown.
- LaTeX was compiled with `tectonic` only; no journal class files were tested. Risk: a
  real RSC/ACS template may still complain.
- The final PDF (4 pages, 0 `[?]`, 3 references) was built with `tectonic`; no publisher
  class file (RSC/ACS) was exercised.
