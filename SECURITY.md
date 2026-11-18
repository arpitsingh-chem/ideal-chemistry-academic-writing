# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 2.4.x | ✅ |
| 2.3.x and earlier | ❌ (please upgrade) |

## Reporting a vulnerability

**Please do not open a public issue for a security problem.**

* Use GitHub's private reporting: **Security → Report a vulnerability** on the repository.
* If that is unavailable, contact the maintainer through the address on their GitHub
  profile, and say only that you have a security report — do not include exploit details in
  a first message to a public channel.

Please include: affected version, a minimal reproduction, impact, and whether the issue
requires a malicious provider response, a crafted manuscript file, or only local access.

**What to expect:** acknowledgement within 7 days; an assessment within 14; a fix or a
documented mitigation plan for anything rated medium or above. Reporters are credited in
`CHANGELOG.md` unless they ask not to be.

## Scope

In scope:

* the provider transport (`paperforge/providers/base.py`) — SSRF, redirect handling,
  response-size and timeout behaviour;
* the research store — SQL construction, path handling, untrusted payload storage;
* file handling in `paperforge/util.py` and `bundle.py` — path traversal, archive
  construction;
* the CLI — argument injection into subprocesses (LaTeX engines), exit-code integrity;
* CI workflows in `.github/workflows/`.

Out of scope:

* **Data accuracy.** A wrong retraction flag or a stale journal limit is a bug — report it
  as a normal issue (it is exactly what the audit trail is for), not as a vulnerability.
* Provider-side incidents (an upstream API outage).
* Anything requiring the user to compile untrusted LaTeX — that is the LaTeX engine's
  security boundary, not PaperForge's.
* Vulnerabilities in optional extras (`rdkit`, `Pillow`, `python-docx`, `matplotlib`) —
  report those upstream; we track them via Dependabot.

## Design commitments

* **No secrets in the repository.** API keys are read from the environment only
  (`OPENALEX_API_KEY`, `SEMANTIC_SCHOLAR_API_KEY`); `.env` is git-ignored.
* **No telemetry.** PaperForge phones home to nobody. Network calls go only to the
  scholarly APIs named in `DATA_SOURCES.md`, from the base URLs hard-coded in each adapter.
* **Least privilege in CI.** Workflows declare `permissions: contents: read`; no
  `pull_request_target`; scheduled jobs write nothing back to the repository.
* **No paywall circumvention, no scraping, no CAPTCHA bypass** — this is an ethical
  boundary and also a legal one.
* **Failures are visible.** A provider that cannot be reached is reported; it is never
  silently replaced with invented data.

## Known accepted risks

Documented in `SECURITY_AUDIT.md`:

| ID | Severity | Status |
|---|---|---|
| SEC-01 | Medium (mitigated) | SQL built with f-strings for internal clauses; values parameterised; replacement tracked in `ROADMAP.md` |
| SEC-02 | Low | urllib follows redirects; base URLs are constants, not user input |
| SEC-03 | Low | raw provider payloads stored verbatim (bounded by page sizes) |
| SEC-05 | Low | no checksum yet on the bundled data snapshot |
