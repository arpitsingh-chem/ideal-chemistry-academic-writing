# ARCHITECTURE_ASSESSMENT

An assessment of the v2.3.0 architecture *before* the changes on this branch, and the
reasoning behind what was kept, extended and rejected. Complements `ARCHITECTURE.md`
(which describes the resulting design).

---

## 1. Verdict

**The existing architecture was sound for its purpose and did not need to be rewritten.**
The brief proposed a `paperforge/{core,chemistry,spectroscopy,reactions,structures,
publications,institutions,journals,references,manuscripts,supporting_information,figures,
templates,database,cli,integrations}/` tree. Adopting it wholesale would have:

* moved ~8,400 working, tested lines for cosmetic reasons;
* invalidated 173 tests and every documented import path;
* risked the one thing the repository demonstrably does well (produce a 100/100 manuscript).

That directly contradicts the brief's own instruction: *"Do not rewrite stable modules
simply to make the repository appear newer."* The tree was therefore treated as what it
says it is — a target design — and used as a **checklist of missing capability**, not a
file-move exercise.

What the tree asked for that was genuinely missing is exactly one thing: **a place for
external sources and a place to put normalised records**. Both were added as subpackages
beside the existing modules.

## 2. What was already good

| Property | Evidence |
|---|---|
| Dependency discipline | one runtime dependency (PyYAML); extras for RDKit/Pillow/docx |
| Test suite | 173 tests, adversarial and regression material included |
| Separation of concerns (engine) | `project` → `checks`/`draft` → `render`/`bundle` is a clean pipeline; `chem` is imported by `checks` but imports nothing from it |
| Error handling | `ProjectError`/`CliError` with user-facing messages, documented exit codes |
| Idempotent tooling | `build_demo.py` regenerates the demos deterministically |
| Self-criticism | `FIELD-TEST.md`, `HARD-CASE-REPORT.md` — prior defect hunts with fixes |

## 3. Structural weaknesses (before this branch)

| # | Weakness | Consequence | Response |
|---|---|---|---|
| A1 | No abstraction over external sources: Crossref was called directly from `refs.py`, and the institutional snapshot was read straight from JSON | Adding a second source meant editing a manuscript module; no provenance, no dedup, no coverage | **Fixed**: `providers/` + `research/` |
| A2 | `checks.py` is 1,071 lines mixing eight rule families | Hard to extend, easy to regress | **Deferred** (documented debt in `ARCHITECTURE.md` §7). Splitting it now would be a large, behaviour-neutral refactor with real regression risk and no present benefit |
| A3 | No data model for a "work" — the journal matcher consumed raw dicts | No validation, no unknown-state semantics | **Fixed**: `WorkRecord` |
| A4 | No persistence layer | Every run re-fetched; no history; no incremental sync | **Fixed**: SQLite store with migrations |
| A5 | No typed error taxonomy for network failures | A 429 and a 404 were treated alike by callers | **Fixed**: `NotFound`/`RateLimited`/`ProviderUnavailable`/`MalformedResponse` |
| A6 | No CI for packaging or for the new subpackages | A broken wheel could ship | **Fixed**: `ci.yml` `package` job |
| A7 | No copyright/licence clarity | Legal ambiguity | **Documented, escalated** (owner decision) |
| A8 | `draft.py`/`render.py` overlapping citation renumbering | Minor duplication | **Deferred** (low value, non-trivial risk) |

## 4. Technology decisions — evidence, not fashion

| Candidate | Decision | Evidence |
|---|---|---|
| **httpx / asyncio** | Rejected | A sync run is sequential by design: rate limits are per-provider, and 6 providers × 10 records took ~8 s wall clock, dominated by provider latency. Concurrency would need per-provider semaphores to stay polite, for no user-visible gain at this scale. Revisit if `--limit 2000` becomes common. |
| **Pydantic** | Rejected | The schema's needs (enums, explicit unknowns, provenance, `missing_fields()`) are met in ~200 lines with zero dependencies. Pydantic v2 is a large dependency for a tool whose selling point is a one-package install. |
| **PostgreSQL** | Rejected (documented escape hatch) | 10,000-record ingest + search completes in ~1 s on SQLite. Export to JSON/CSV exists for anyone who needs a server. |
| **SQLAlchemy** | Rejected | ~40 lines of SQL against 6 tables; an ORM would add a dependency and hide the migration SQL, which is an audit artifact here. |
| **NetworkX** | Deferred to P2 | Needed only for the citation-graph feature, which is not implemented. Adding it now would be an unused dependency. |
| **RDKit** | Kept optional | Already an extra; the scheme tests skip cleanly when absent. |
| **ruff / mypy** | ruff config added; mypy deferred to P1 | Lint is cheap to adopt; a type gate needs a baseline first. |
| **PEP 639 licence metadata** | Adopted | Machine-readable, and forced the licence contradiction into the open. |

## 5. Backward compatibility

Everything preserved deliberately:

* all v2.3 CLI commands, flags and exit codes unchanged;
* all public function signatures in `chem`, `journals`, `refs`, `checks`, `draft`,
  `render`, `bundle` unchanged — `chem.dbe()` keeps its name and now returns a *correct*
  value; `ORGANIC_ELEMENTS` is retained as an alias for the new valence set;
* `paper.yaml`, project layout, `refs.bib` and `get_paper`-style accessors untouched;
* the bundled data files are byte-identical;
* `python -m paperforge` and the `paperforge` console script both work;
* the 173 inherited tests are unchanged and still pass.

Two behaviour changes are intentional and are bug fixes, not compatibility breaks:

1. `check_formula` now emits `info` rather than `error` where an element has variable
   valence. A manuscript that previously scored lower for containing triphenylphosphine
   now scores correctly.
2. `parse_formula("C7H7+")` returns `{C:7, H:7}` instead of `{C:7, H:1}`.

Both are recorded in `CHANGELOG.md` and `BUG_REGISTER.md`.

## 6. Risk assessment of the chosen path

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| New provider layer has undiscovered defects | Medium | Medium | 34 adversarial tests; 4 defects found and fixed pre-release (PF-007…009) |
| Provider APIs change | High over time | Medium | Fixture tests, capability declarations, per-provider isolation, `research providers` readiness check |
| Chemistry fixes break the demo projects | Low | High | Demo re-scored after every change (100.0 / 99.7 preserved); 47 reference tests |
| Documentation drifts again | Medium | Medium | Every README number has a command; CI guards relative links; `MAINTENANCE_GUIDE.md` sets a re-verification cadence |
| Licence ambiguity persists | Certain until owner decides | Medium | Escalated as D-1/D-2; no unilateral action taken |

## 7. What a future architect should do first

1. Split `checks.py` into rule families **with the test suite as the contract** (A2).
2. Add the type gate (P1 item 4) — the provider layer is where it pays off.
3. Verify journal profiles (P1 item 1) — the honesty deficit with the highest user impact.
4. Only then consider concurrency or a server database.
