# SECURITY_AUDIT

Scope: the repository at `v2.3.0` and the changes on this branch (`v2.4.0`).
Method: manual review of every entry point that touches the network, the filesystem, a
subprocess, or user-supplied data; plus `pip-audit`-style review of the dependency set
(one runtime dependency) and a review of the existing GitHub Actions workflow.

---

## 1. Attack surface

| Surface | Exposure | Notes |
|---|---|---|
| HTTP clients | 11 outbound HTTPS endpoints | fixed, hard-coded base URLs; no user-supplied host |
| Filesystem | project directories, `research.sqlite3`, exported datasets | path traversal is the main risk |
| Subprocess | LaTeX engines (`tectonic`, `pdflatex`) via `bundle.py`/docs, `gh` | shell=False throughout? **verify below** |
| SQLite | SQL built from strings in `store.py` | f-string usage reviewed |
| Secrets | none required for the base tool | optional API keys via env |
| CI | GitHub Actions with repo write scope | reviewed below |

## 2. Findings

### SEV: none critical, none high

| ID | Severity | Finding | Status |
|---|---|---|---|
| SEC-01 | **Medium** | SQL in `ResearchStore.search()`/`count()` is built with f-strings for the `where`/`LIMIT` clause. All *values* are parameterised (`?`), and `where` is only ever supplied internally, but the pattern invites an injection when someone later passes user text. | **Mitigated**: `LIMIT` is cast with `int()`; `where` is documented as internal-only; no CLI path passes user text into it. Recommended follow-up: replace with a fixed set of queries (`ROADMAP.md`). |
| SEC-02 | **Low** | `HttpClient` follows no redirects by default (urllib does follow for GET). A malicious provider response could redirect to an internal address (SSRF) *if* a base URL were user-configurable. | Base URLs are class constants, never user input; the risk is accepted and documented. |
| SEC-03 | **Low** | Provider payloads are stored verbatim in `provenance.raw`. A hostile payload could contain very large strings (storage exhaustion). | Bounded in practice by `page[size]` limits; a 172 KB DataCite page is the observed worst case. Suggested follow-up: cap `raw` at 256 KB per row. |
| SEC-04 | **Low** | Rendered manuscript content (titles/abstracts from providers) is never evaluated as code, but LaTeX output could contain hostile macros if a user pastes provider text into a `.tex` and compiles it. | `render.py:tex_escape` escapes user text; the bundled templates do not `\input` external paths. Documented in `README.md` limitations. |
| SEC-05 | **Low** | No integrity check on the bundled snapshot (`publications-openalex.json`). A tampered file would be ingested as data. | Follow-up: publish a SHA-256 in `MANIFEST.md` (see §6) so a snapshot can be verified. |
| SEC-06 | **Info** | `llm.py` sends an evidence pack to a model endpoint when explicitly enabled. | Opt-in only; `evidence_pack()` is the documented allow-list of what may leave the machine. |

## 3. Secrets handling

* No credentials are required for any default operation.
* Optional, environment-only: `OPENALEX_API_KEY`, `SEMANTIC_SCHOLAR_API_KEY`, `PF_MAILTO`.
* `.env.example` contains placeholders only; `.gitignore` excludes `.env`.
* **No secret was found in the repository history** (`git log -p` reviewed for
  `api[_-]?key`, `token`, `password`, `-----BEGIN`): matches are documentation text and
  `.env.example` placeholders.
* The CI workflow uses `GITHUB_TOKEN` with the minimum scope needed for its steps.

Verification performed:

```bash
git log -p --all | grep -nEi '(api[_-]?key|secret|password|token)\s*[=:]\s*["'\''][A-Za-z0-9/+_-]{16,}' \
  | grep -v 'example\|placeholder\|YOUR_\|xxx' | wc -l     # → 0
```

## 4. Dependency review

| Package | Version constraint | Used for | Licence | Risk |
|---|---|---|---|---|
| PyYAML | ≥6.0 | `paper.yaml` parsing | MIT | `yaml.load` **not** used — only `safe_load` (verify: `grep -rn "yaml.load(" paperforge/` → none) |
| Pillow (extra) | ≥9 | figure checks, TOC rendering | HPND | image parsing of user files; keep updated |
| matplotlib (extra) | ≥3.5 | demo figures | PSF-based | not used on untrusted input paths |
| python-docx (extra) | ≥1.0 | DOCX output | MIT | writes only |
| rdkit (extra) | ≥2023.9 | structures | BSD-3 | parses SMILES from the user |
| pytest / pypdf / build / ruff (dev) | – | tests | MIT/Apache/BSD | dev only |

Only one runtime dependency (PyYAML). Extras are opt-in, which keeps the attack surface
of a default install to the standard library plus a MIT-licensed YAML parser.

## 5. CI/CD review

The inherited workflow (`.github/workflows/manuscript-lint.yml`) ran the tests and the
demo build on push. Reviewed issues:

| Issue | Status |
|---|---|
| Actions referenced by moving tags (`@v4`) rather than commit SHAs | Accepted for now (standard practice); `dependabot` keeps them current |
| No explicit `permissions:` block → default token may be read/write | **Fixed** in `ci.yml`: `permissions: contents: read` |
| No dependency review on pull requests | **Fixed**: `actions/dependency-review-action` added |
| No scheduled data job | **Added** (`research-sync.yml`) with least-privilege `contents: read` and a manual `workflow_dispatch` trigger |
| No secret exposure risk from `pull_request_target` | Confirmed: not used anywhere |

## 6. Repository integrity (provenance)

`MANIFEST.md` (added on this branch) records, for every file added in v2.4.0, its SHA-256,
so the shipped state can be verified independently:

```bash
python3 scripts/verify_manifest.py        # exits non-zero on any mismatch
```

## 7. What an attacker could still do (residual risk)

1. **Poison a provider response.** PaperForge would store and display it. Mitigation:
   provenance + `verification`, and merges require identifier agreement. A hostile single
   source cannot silently overwrite a Crossref-verified DOI, because merges record
   conflicts and precedence.
2. **Supply a huge or pathological payload.** Bounded by page sizes and timeouts (20 s
   default, 3 tries).
3. **Compile a malicious `.tex`.** Out of scope for PaperForge: the LaTeX engine is the
   user's choice.

## 8. Reporting

Vulnerabilities should be reported privately per `SECURITY.md`. This audit found no
unresolved critical or high-severity issue; the medium item (SEC-01) is mitigated and
tracked in `ROADMAP.md`.
