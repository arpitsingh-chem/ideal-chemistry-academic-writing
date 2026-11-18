# DECISIONS

Architecture and policy decisions with their evidence and the alternatives that were
rejected. Format: decision · context · choice · why · what would reverse it.

---

## D-01 — Extend the v2 engine; do not rewrite it into the proposed tree

**Context.** The brief proposed `paperforge/{core,chemistry,spectroscopy,…,cli}`. The
existing tree is `paperforge/{chem,checks,draft,…}` with 173 passing tests and a demo
manuscript at 100.0/100.
**Choice.** Keep the modules; add `providers/`, `research/`, `institutions/` beside them.
**Why.** The brief also says "do not rewrite stable modules simply to make the repository
appear newer" and "do not replace functioning code without a documented reason". Moving
8,400 tested lines would risk the only thing demonstrably working, for zero user benefit.
The proposed tree was used as a checklist of *missing capability*, which yielded one real
gap (external sources + a place for normalised records) — now implemented.
**Reverse if.** A second maintainer joins and `checks.py`'s 1,071 lines become a merge
bottleneck. Then split it with the test suite as the contract.

## D-02 — No new runtime dependencies

**Choice.** `urllib`, `sqlite3`, `dataclasses`, `enum`. One required dependency remains
(PyYAML).
**Why.** The installation story ("pip install paperforge, done") is a feature for the
intended audience of chemists, and every dependency is a supply-chain and licence surface.
The transport needs no HTTP/2, no pooling, no async; the schema needs no ORM.
**Reverse if.** A provider requires TLS features urllib cannot do, or a feature genuinely
needs a scientific stack (e.g. NetworkX for the citation graph — planned, but only when the
feature exists).

## D-03 — SQLite for the research store

**Choice.** A single SQLite file with ordered SQL migrations.
**Why.** Corpus of 10³–10⁵ records, single user, local-first; the 10,000-record adversarial
test runs in about a second. PostgreSQL would add an operational dependency and hide the
migration SQL, which is an audit artefact here.
**Reverse if.** Multi-user or > 10⁶ records. Export to JSON/CSV already exists.

## D-04 — Two different DOIs are never "the same work"

**Context.** The first live `research sync` merged `10.5281/zenodo.18233709` into
`10.5281/zenodo.23352136` on title + first author alone. Zenodo mints a DOI per version, so
this destroyed a distinct record (PF-007).
**Choice.** If both records carry a DOI and the DOIs differ, the verdict is `DISTINCT` —
unless one DOI is a version-suffixed form of the other (`…/ncl.34472799` vs `….v1`), which
yields `RELATED_VERSION` (linked, both kept).
**Why.** A registered DOI is a registered object. Content similarity is evidence of
relation, not of identity.
**Cost.** Some genuine duplicates (a publisher's correction record, a ChemInform digest of
the same paper) are kept as related rather than merged. That is the safe direction to err.
**Reverse if.** Never for same-DOI-vs-different-DOI; the version rule may be extended as
more schemes are observed.

## D-05 — Unknown metadata is `None`, never inferred

**Choice.** `WorkRecord` fields default to `None`; `missing_fields()` and `completeness()`
expose the gaps. Absent OpenAlex fields in the institutional snapshot report as
"not captured", not `0`.
**Why.** Filling a field from a sibling record or a default converts ignorance into
apparent knowledge — the exact failure mode this project exists to prevent. A user can act
on `None`; they cannot detect a plausible-looking guess.
**Reverse if.** A provider documents a value as derivable (e.g. OA status from a licence
URL) — then it is *derived*, labelled as such, and tested.

## D-06 — Unusable sources are documented, not faked

**Choice.** `providers/registry.py:BLOCKED` lists ChemRxiv, Google Scholar, Scopus, Web of
Science, Dimensions, CORE and NIST WebBook with reason, verification date and an
alternative.
**Why.** An adapter that returns nothing silently is worse than a documented "we cannot use
this". For ChemRxiv the evidence is concrete: HTTP 403 Cloudflare challenge on 2026-11-18.
**Reverse if.** A provider publishes a usable API; then the entry moves to `IMPLEMENTED`
with a fixture test.

## D-07 — No unilateral licensing change

**Context.** `LICENSE` is CC BY 4.0; the README claimed MIT for code; no MIT text exists;
`LICENSE` has no copyright line; `CITATION.cff` says "Arpit Singh" while the brief says
"Arpit Rajput"; one commit is authored by an institutional address.
**Choice.** Correct the *documentation* to match reality; do not change the licence; do not
invent a copyright holder; escalate D-1/D-2 in `LICENSING_AND_PROVENANCE_AUDIT.md`.
**Why.** Relicensing and copyright attribution are the owner's legal decisions, and
institutional authorship may affect ownership. A technically tidy but legally unauthorised
change is worse than an honest open question.

## D-08 — Journal profiles carry `verified: false` when they are not verified

**Choice.** 5 of 261 profiles are journal-verified; 256 say so explicitly.
**Why.** A stale or invented limit causes a desk rejection — the precise harm the tool is
sold to prevent. Reporting a family default as verified would be a compliance lie.
**Reverse if.** Never; the fix is to verify more profiles (P1 item 1).

## D-09 — No network calls inside `paperforge check`

**Choice.** The manuscript checker stays offline. PubChem and provider lookups are separate
commands.
**Why.** A linter that blocks on a remote timeout is unusable in CI, and a flaky network
must not change a manuscript's score. Reference verification is an explicit, separate step
(`refs verify`) whose results are cached and then used offline.

## D-10 — Failures are typed, visible and non-fatal per provider

**Choice.** `NotFound` / `RateLimited(retry_after)` / `ProviderUnavailable` /
`MalformedResponse`; one provider's failure never aborts a sync; a daily quota is never
retried within a run.
**Why.** Observed live: OpenAlex exhausted a shared IP budget and Semantic Scholar returned
429 during ordinary use. A tool that either crashes or hangs in that condition is not
usable; a tool that reports "2 of 6 sources unavailable" is.

## D-11 — Tests must not depend on the network

**Choice.** Live payloads are captured into `tests/fixtures/providers/`; live checks are
marked `-m network` and skipped by default.
**Why.** Deterministic CI, and the suite stays runnable on a plane. The cost is fixture
staleness, mitigated by the scheduled `Research sync` workflow, which exercises the real
APIs weekly and reports drift without failing the build.
