# MAINTENANCE_GUIDE

How to keep PaperForge correct over time. The software will not silently rot: what rots is
**data and external APIs**, and that is what this guide schedules.

---

## 1. Cadence

| Interval | Task | Command | Failure looks like |
|---|---|---|---|
| every push / PR | tests, lint, package, links | GitHub Actions `CI` | a red check |
| weekly | research pipeline smoke test | `Research sync` workflow | a job summary with FAIL providers |
| weekly | dependency PRs | Dependabot | an unreviewed PR pile-up |
| monthly | verify 5 journal profiles per month | see §3 | profiles drifting toward `verified: false` |
| monthly | dependency audit | `pip-audit` (or Dependabot alerts) | an advisory with no PR |
| quarterly | re-read `DATA_SOURCES.md` access conditions | `curl` table in that file | a provider that now needs a key |
| quarterly | refresh the institutional snapshot | `scripts/refresh_corpus.py` | a snapshot that no longer matches reality |
| annually | re-baseline documentation numbers | §5 | a README that lies |
| annually | review `ROADMAP.md` | — | a roadmap nobody believes |

---

## 2. The four things that break

### 2.1 A provider changes its schema
**Symptom:** a fixture test fails, or a field is suddenly `None` for everything.
**Diagnose:**
```bash
python -m pytest tests/unit/test_providers_offline.py -v
python -m paperforge research fetch 10.1021/jacs.5c13581 --source crossref
```
**Fix:** re-capture the fixture and update `normalise()`. Record the change in
`DATA_SOURCES.md` with the date you verified it. If the source is unusable, move it to
`BLOCKED` with the evidence — do not leave a broken adapter enabled.

### 2.2 A provider changes its access terms
**Symptom:** 401/403, or a new `X-RateLimit` header, or a Terms-of-Service email.
**Action:** a terms change outranks a feature. Disable the adapter (`registry.BLOCKED`),
record the reason and date, and find an alternative. Never work around an access control.

### 2.3 A journal changes its limits
**Symptom:** an author reports that the abstract limit is wrong.
**Fix:** open the journal's author-guidelines page, update the entry, set
`verified: true` and `verified_on` to today, and record the URL. If you cannot verify,
leave `verified: false` — an unverified default is honest; a stale "verified" is not.

### 2.4 Quota exhaustion
**Symptom:** `rate_limited: Insufficient budget … retryAfter …`.
**Action:** confirm `OPENALEX_API_KEY` / `SEMANTIC_SCHOLAR_API_KEY` are set in CI secrets.
PaperForge deliberately does **not** retry a daily quota; it records `retryAfter` and moves
on. Partial results are reported as partial.

---

## 3. Verifying a journal profile (the monthly task)

1. Open the official author-guidelines page (the `source` URL in
   `paperforge/data/journal_limits.json`; if absent, find it on the publisher's site).
2. Record: abstract limit, body word/page limit, figure/table caps, reference cap,
   required statements (COI, data availability, ethics, AI disclosure), TOC/graphical
   abstract dimensions.
3. Edit the `verified` block:
```json
"Organic Letters": {
  "family": "acs",
  "verified": true,
  "verified_on": "2026-11-18",
  "source": "https://researcher-resources.acs.org/publish/author_guidelines?coden=orlef7",
  "article_types": { "letter": { "abstract_max": 200, "body_max_words": 3000 } }
}
```
4. Run `python -m paperforge journals show "Organic Letters"` and confirm it prints as
   verified.
5. Commit with a message naming the journal and the date.

**Never** set `verified: true` for a journal you did not open.

---

## 4. Refreshing the institutional snapshot

```bash
python3 scripts/refresh_corpus.py            # rewrites paperforge/data/publications-openalex.json
python3 -m paperforge institution stats      # check the counts moved sensibly
python3 -m pytest tests/test_refresh_corpus.py tests/integration -q
```

Then update the numbers in `README.md` §6-adjacent text and `GLOBAL_RESEARCH_COVERAGE.md`
§6 **if and only if they changed**, and say the date of the snapshot.

The snapshot has no `is_oa`/`is_retracted` fields; if the refresh script starts emitting
them, `institutions/iiserb.py` will pick them up automatically (it reports `None` until
then).

---

## 5. Re-baselining documentation (the annual task)

Every number in the README must come from a command. To re-check:

```bash
python -m pytest -q                              # test count
python -m paperforge rules | head -1             # rule count
python -c "from paperforge import journals; print(len(journals.journals()))"
python -c "from paperforge.institutions import iiserb; print(iiserb.stats())"
python -m paperforge research providers | head -1
python -m paperforge check examples/demo-paper | tail -3
```

Update the README, and if a claim no longer holds, **remove the claim** rather than
softening the wording. Nine such claims were removed in 2.4.0 (`AUDIT_REPORT.md` §4).

---

## 6. Release procedure

```bash
# 1. green baseline
python -m pytest -q && python -m ruff check paperforge tests

# 2. version bump in ONE place + the changelog
#    paperforge/__init__.py and pyproject.toml must agree
grep -n "version" pyproject.toml | head -1; grep -n "__version__" paperforge/__init__.py

# 3. artefacts
rm -rf dist build && python -m build

# 4. prove the artefacts work
python -m venv /tmp/v && /tmp/v/bin/pip install dist/*.whl
/tmp/v/bin/paperforge research providers > /dev/null && /tmp/v/bin/paperforge institution stats > /dev/null
sha256sum dist/*

# 5. changelog, then tag
git tag -a vX.Y.Z -m "PaperForge X.Y.Z"
git push origin main --follow-tags
```

Release checklist:

- [ ] `CHANGELOG.md` has the version, dated, with measured numbers
- [ ] `CITATION.cff` `version` and `date-released` updated to match
- [ ] `pyproject.toml` version == `paperforge.__version__`
- [ ] wheel and sdist built, installed in a clean venv, CLI exercised
- [ ] `dist/` is **not** committed (it is git-ignored)
- [ ] no secret in the diff (`git diff | grep -iE 'api[_-]?key|token|secret'`)
- [ ] the tag matches an annotated commit message

**Publishing to PyPI requires explicit owner approval** and should use Trusted Publishing
(OIDC), not a stored token — see `ROADMAP.md`/release notes; not configured here.

---

## 7. Health signals to watch

| Signal | Healthy | Investigate |
|---|---|---|
| `research providers` ready count | 9–11 | ≤ 8 |
| `provider_state` consecutive failures | 0 for crossref/openalex/europepmc | ≥ 3 |
| `coverage` conflicting records | a few % | > 10 % (suspect a dedup rule) |
| `coverage` records merged | non-zero on overlapping queries | 0 on a duplicate-heavy query |
| test suite runtime | < 30 s | > 2 min (a fixture or a test is doing network I/O) |
| wheel size | ~0.9 MB (data dominates) | > 2 MB (someone added a dataset) |
| demo score | 100.0 · 99.7 (`--verify-refs`) · 94.9 (offline) | any drop |

---

## 8. When to say no

* A pull request that adds a dataset without licence and provenance → **no**.
* A feature that reports a number it cannot measure (an impact factor, an acceptance rate)
  → **no**, or a documented `None`.
* A provider integration that requires bypassing an access control → **never**.
* A refactor of `checks.py` without the suite as a contract → not yet.
