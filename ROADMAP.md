# ROADMAP

Ordered by value per unit of risk. Every item states what would *prove* it done — a
capability without a verification story does not belong on a roadmap for a measurement tool.

Legend: **P1** next · **P2** planned · **P3** considered · **—** explicitly not planned.

---

## P1 — correctness and coverage debt

### 1. Verify the remaining journal profiles
**Why:** 256 of 261 profiles inherit a publisher-family default. That is the largest
honesty gap in the product.
**Work:** read each journal's current author guidelines; record abstract/body/figure limits,
TOC dimensions, required statements, and the exact URL + date; set `verified: true` only
then. Add a `--check-stale` command that flags profiles whose verification date is older
than 12 months.
**Proven:** `journals show <name> --json` reports `verified: true` with a source URL and a
date < 12 months old, for every profile claimed as verified; a test asserts that
`verified: true` implies `source` and `verified_on` are present.

### 2. Benchmark subdiscipline classification
**Why:** the keyword classifier returns a label but nobody knows its accuracy.
**Work:** hand-label 300 abstracts spanning ≥10 subdisciplines, commit the label set as
test data, measure precision/recall per label, publish the confusion matrix.
**Proven:** a reproducible script prints the matrix; the README quotes the measured
numbers instead of "not benchmarked".

### 3. Replace string-built SQL in the store
**Why:** SEC-01. All values are parameterised today, but the pattern is fragile.
**Proven:** `store.py` contains no f-string SQL; the 10k-record adversarial test still
passes; a grep-based test asserts no f-string appears in a `conn.execute` call.

### 4. A type-check gate
**Why:** annotations are partial; the provider layer would benefit most.
**Work:** run `mypy --strict` (or pyright) on `paperforge/providers`, `paperforge/research`,
then widen module by module. Add to CI as a non-blocking report first, blocking later.
**Proven:** CI job present, baseline recorded, no new errors on a PR.

### 5. Snapshot integrity
**Why:** SEC-05 — the bundled 1,616-work snapshot has no checksum.
**Work:** record SHA-256 for every data file in `MANIFEST.md`; add
`scripts/verify_manifest.py` and a CI step.
**Proven:** a modified data file fails CI with a clear message.

## P2 — research capability

### 6. Citation-graph analysis
**Why:** the most-requested capability that is not a gimmick: which works matter in a
subfield, and where a paper sits in that graph.
**Work:** ingest `referenced_works` (OpenAlex) and `reference` DOIs (Crossref) into a
`citations` table; expose `research graph --doi X --depth 2`; compute in-degree, PageRank
and a co-citation map with NetworkX (already an evaluated dependency, not yet added).
**Proven:** on a fixture graph with a known answer, PageRank ranks the hub first; the
command runs offline on stored data.

### 7. Research-gap surfacing (careful version)
**Why:** "gap discovery" is where academic tools most often fabricate insight.
**Work:** restricted to *reportable statistics*: publication volume per subdiscipline per
year, venue concentration, and **under-cited recent works that cite a seed paper**. Never
a natural-language claim about what the literature "lacks".
**Proven:** every output row traces to stored records; no generated prose.

### 8. Full-text access through legitimate routes only
**Why:** metadata alone cannot answer "was this compound reported in that paper".
**Work:** Unpaywall/Europe PMC OA full-text links → download only CC-BY/CC0 works, store
the licence with the text, extract with a bounded parser. Explicitly no paywall
circumvention.
**Proven:** a licence check refuses non-OA records; a test asserts the refusal.

### 9. Chemistry manuscript validators beyond synthetic organic
**Why:** the research layer is discipline-general; the manuscript validators are not.
**Work, in order:** (a) crystallography: CIF header validation (cell, space group, R
factors, CCDC number consistency); (b) electrochemistry: potential reference scale,
scan-rate reporting, reversibility criteria; (c) photophysics: quantum-yield method,
reference standard, lifetime fit quality; (d) computational: level of theory, basis set,
solvation, software version, dispersion correction.
**Proven:** each validator has a fixture pair (valid/invalid) derived from published
reporting standards, plus a reference document in `docs/reference/`.

## P3 — platform

### 10. Plugin architecture for providers
Third-party adapters without touching core, registered via entry points
(`paperforge.providers`). **Proven:** an example plugin package in `examples/` loads via
entry point and appears in `research providers`.

### 11. Asynchronous provider fan-out
Only if measured: current sync of 6 providers with `--limit 50` takes ~8 s wall clock,
dominated by per-provider latency. Revisit when a corpus sync is slow enough to matter.

### 12. PostgreSQL backend
Only on evidence of need (multi-user or > 10⁶ records). Export/import path already exists.

### 13. CSL-exact reference styles
Requires a CSL engine plus the CSL style repository (CC BY-SA 3.0) — a licence decision
before an engineering one.

## Not planned

| Item | Why not |
|---|---|
| Scraping Google Scholar | Violates its Terms of Service |
| Paywall circumvention / Sci-Hub-style access | Illegal and unethical |
| Fabricating impact factors, APCs or acceptance rates | The failure mode this project exists to prevent |
| Training a chemistry classifier on unlicensed text | Licensing risk with no necessity |
| Auto-writing whole papers unsupervised | The tool grounds and verifies human-authored claims; it does not replace authorship |
| A hosted SaaS in this repository | Out of scope; the library and CLI are the deliverable |

---

## How this roadmap is revised

Items are removed when shipped (with the release that shipped them) and when evidence
shows they are not worth it — with the evidence recorded here. A roadmap that only grows
is a wish list.
