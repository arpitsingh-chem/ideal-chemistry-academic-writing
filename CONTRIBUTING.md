# Contributing

Thank you for considering a contribution. This project has one unusual rule, and it
matters more than style conventions:

> **Do not claim a capability that has not been executed and verified.**
> A failing test, a documented "we cannot reach this source", or an honest `None` is worth
> more than a feature that looks complete.

## 1. Set up

```bash
git clone https://github.com/arpitsingh-chem/ideal-chemistry-academic-writing
cd ideal-chemistry-academic-writing
python3 -m venv .venv && source .venv/bin/activate
python3 -m pip install -e ".[figures,docx,dev]"
python3 -m pytest -q          # expect: 360 passed, 3 skipped
python3 -m paperforge doctor
```

Optional extras: `.[structures]` for RDKit (scheme drawing), `.[all]` for everything.

## 2. What a good contribution looks like

| Contribution | What it must include |
|---|---|
| **A new provider adapter** | a fixture captured from the live API, an offline parsing test, a `Capabilities` declaration, an access-conditions note in `DATA_SOURCES.md`, and the licence in `THIRD_PARTY_NOTICES.md` |
| **A chemistry fix** | an independent reference value (PubChem, CODATA, IUPAC, a published table) — not a value copied from the implementation — plus a regression test in `tests/scientific/` |
| **A rule** | a rule code in the `PREFIX-NAME` shape, a test that fires it and a test that does not fire on correct input (false positives are defects) |
| **A journal profile** | the official author-guidelines URL and the date you read it; `verified: true` only if you actually checked that journal |
| **Documentation** | every command in it executed; paste the real output |
| **Dependency** | justification in the PR (why the standard library is insufficient), licence compatibility, and a `THIRD_PARTY_NOTICES.md` entry |

### Not accepted

* Scraped data, paywall circumvention, or anything that violates a provider's terms.
* Fabricated metadata, impact factors, APCs, acceptance rates, benchmark scores or test
  results.
* Relicensing, or removing third-party attribution.
* Rewriting git history.
* New dependencies for convenience where the standard library suffices.

## 3. Adding a provider adapter

1. Read the provider's API terms and confirm key-less (or key-based) access actually works:
   `curl -s -o /dev/null -w '%{http_code}\n' '<endpoint>'`.
2. Subclass `paperforge.providers.api.Provider`; declare `name`, `base_url`, `license`,
   `docs_url`, `default_interval` and a `Capabilities` instance that reflects reality
   (`search=False` if there is no search endpoint).
3. Implement `normalise()` returning a `WorkRecord`. **Leave unknown fields as `None`.**
4. Register it in `providers/registry.py`. If it is unusable, register it in `BLOCKED` with
   `reason`, `verified_on` and `alternative` instead — that is a valid contribution.
5. Add a fixture + test. Run `python -m paperforge research providers` and confirm the
   readiness table is truthful.

## 4. Tests

```bash
python -m pytest                       # the whole suite, offline
python -m pytest tests/scientific -v   # independent reference values
python -m pytest tests/adversarial -v  # faults, hostile payloads, exit codes
python -m pytest -m network            # opt-in live API checks
```

Requirements for a PR:

* the full suite passes;
* new behaviour is covered by a test that **fails before** your change;
* no test depends on the network unless marked `network`;
* performance stays sane (the 10 k-record store test is the benchmark).

## 5. Code style

* Python ≥ 3.10, `from __future__ import annotations`, type hints on public functions.
* `ruff check paperforge tests` (config in `pyproject.toml`).
* Keep the runtime dependency count at one unless there is a written justification.
* Docstrings explain *why*, not what the next line does. Cite the bug a check exists to
  prevent, where one exists.

## 6. Documentation

Follow [Diátaxis](https://diataxis.fr/): `docs/tutorials/` (learning), `docs/guides/`
(tasks), `docs/reference/` (information), `docs/explanations/` (understanding).

Every command shown must have been run. If you cannot verify a claim, write the limitation
instead.

## 7. Commit messages

Conventional-commit prefixes (`feat:`, `fix:`, `docs:`, `test:`, `build:`, `ci:`, `refactor:`).
The body should say what was broken or missing and how you verified the change. Reference
`BUG_REGISTER.md` ids where relevant.

## 8. Reporting a bug

Use the issue template. Include:

* the command and its exact output;
* `paperforge doctor`;
* the input that triggered it (a minimal file is ideal);
* for chemistry findings: the compound, the formula and the value you expected, with a
  source.

## 9. Code of conduct

Participation is covered by [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

## 10. Licence of contributions

By contributing you agree that your contribution is licensed under the repository's
licence (see `LICENSE` and `LICENSING_AND_PROVENANCE_AUDIT.md`). Do not contribute code you
do not have the right to license.
