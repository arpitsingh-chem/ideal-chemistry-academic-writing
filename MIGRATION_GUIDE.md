# MIGRATION_GUIDE — v2.3.x → v2.4.0

v2.4.0 is backward compatible: no command, flag, file format or public function was
removed. This guide covers what changes behaviour, what you should re-check, and how to
adopt the new research layer.

---

## 1. TL;DR

```bash
git pull
python3 -m pip install -e ".[figures,docx,dev]"
python3 -m pytest -q                        # expect 349 passed, 3 skipped
python3 -m paperforge doctor                # now also reports the research data layer
```

Nothing in your `paper.yaml` needs to change.

---

## 2. Behaviour changes you may notice

### 2.1 Fewer false errors on real chemistry

`check_formula` no longer reports a hard error for organophosphorus, organosilicon and
organoboron compounds, and it downgrades non-integer DBE to a note where an element has
variable valence.

| Formula | v2.3.x | v2.4.0 |
|---|---|---|
| `C18H15P` (PPh₃) | `error CHEM-DBE-FRACTION` (11.5) | no finding (DBE = 12) |
| `C3H9SiCl` (TMSCl) | `error CHEM-DBE-NEG` (−1) | no finding (DBE = 0) |
| `C6H5B(OH)2` | `error CHEM-DBE-FRACTION` (3.5) | no finding (DBE = 4) |
| `C14H10NO2S` | `error CHEM-DBE-FRACTION` | `info CHEM-DBE-FRACTION` (still surfaced, no longer fatal) |

**Action:** if your score *rises* after upgrading, that is this fix. No action required.

### 2.2 Corrected masses

If any of your projects use these forms, re-run `check`:

| Input | v2.3.x | v2.4.0 |
|---|---|---|
| `C7H7+` | parsed as `CH` | `C7H7` (charge +1) |
| `CuSO4·5H2O·2H2O` | 429.83 g/mol | 285.71 g/mol |
| `[M]+·` / `[M]−` adduct | neutral mass | ± one electron |
| `Nb`, `Tc`, `Pm`, `Be`, … | `unknown element` error | supported |

**Action:** if a v2.3 project passed with a formula containing a charge suffix, a
multi-hydrate, or a radical-ion adduct, re-check it — the earlier pass may have been
computed from a wrong formula.

### 2.3 New diagnostic codes

| Code | Severity | Meaning |
|---|---|---|
| `CHEM-CHARGE-SYNTAX` | warn | an attached charge magnitude is ambiguous (`SO42-`); write `SO4 2-` |
| `CHEM-DBE-METAL` | info | DBE not defined (metal-containing formula) — unchanged |
| `CHEM-DBE-FRACTION` | info (was error) | non-integer DBE where valence is variable or charge ≠ 0 |

If you gate CI on `--fail-on error`, the severity change may make a previously failing
build pass. That is intended: those were false positives.

### 2.4 NMR integral parsing

`1H NMR` in a report header is no longer counted as one proton, and a formula embedded in
the NMR field is ignored. Projects whose integrals previously summed "correctly" only
because of that phantom proton will now report `CHEM-NMR-H`.

**Action:** re-run `check`; if `CHEM-NMR-H` appears, the integral sum was genuinely wrong.

---

## 3. Packaging changes

| Before | After |
|---|---|
| `license = {text = "CC BY 4.0 (content); code provided for reuse"}` | `license = "CC-BY-4.0"` + `license-files` (PEP 639) |
| `packages = ["paperforge"]` | explicit list including `paperforge.providers`, `paperforge.research`, `paperforge.institutions` |
| extras: `figures`, `docx`, `structures`, `dev` | same, plus an aggregate `all` |
| `setuptools>=68` | `setuptools>=77` (PEP 639 support) |

If you build a wheel from your own fork, update the `packages` list if you add a subpackage
— otherwise its modules will be missing from the wheel (this is exactly the failure mode
3.3's explicit list prevents).

**No licence change was made**: the repository is still CC BY 4.0. See
`LICENSING_AND_PROVENANCE_AUDIT.md` D-1.

---

## 4. Adopting the research layer

The research layer is additive; nothing in the manuscript workflow depends on it.

```bash
export PF_MAILTO=you@example.org        # needed by Unpaywall; polite elsewhere
export OPENALEX_API_KEY=...             # free; strongly recommended

paperforge research providers           # is anything available?
paperforge research sync "your topic" --db research.sqlite3 --limit 100
paperforge research coverage --db research.sqlite3
```

### Migrating the old snapshot workflow

If you previously ran `scripts/refresh_corpus.py` to rebuild
`paperforge/data/publications-openalex.json`:

* that script still exists and is unchanged — it remains the way to refresh the
  **bundled institutional snapshot**;
* the research layer is the way to build a **live, local corpus** for a topic.

They are complementary: the snapshot is curated and reviewed; the sync store is
disposable and incremental.

### Python API

```python
from paperforge.providers.crossref import CrossrefProvider
from paperforge.research.dedup import compare, merge
from paperforge.research.store import ResearchStore

p = CrossrefProvider(mailto="you@example.org")
a = p.fetch("10.1021/jacs.5c13581").records[0]
b = CrossrefProvider(mailto="you@example.org").fetch("10.1021/jacs.5c13581").records[0]
print(compare(a, b).explain())          # same (score 1.00) | +doi:identical DOI …

with ResearchStore("research.sqlite3") as store:
    store.upsert([a])
    print(store.stats()["works"])
```

---

## 5. Database schema

New store → schema version 1. There is nothing to migrate from (the previous version had
no database). Migrations are applied automatically on open; `store.version()` reports the
current version.

---

## 6. Environment variables (all optional)

| Variable | Used by | Default |
|---|---|---|
| `PF_MAILTO` | all providers (polite pool), Unpaywall (required) | unset |
| `OPENALEX_API_KEY` | OpenAlex (own daily budget) | unset |
| `SEMANTIC_SCHOLAR_API_KEY` | Semantic Scholar | unset |
| `PF_HTTP_TIMEOUT` | transport | 20 s |
| `PF_HTTP_TRIES` | transport | 3 |
| `PF_HTTP_INTERVAL` | transport politeness | per provider |

---

## 7. Rollback

v2.4.0 changes no data file and no project format, so rolling back is safe:

```bash
git checkout v2.3.0
python3 -m pip install -e .
```

The only artefacts that are not backward-compatible are the ones v2.4.0 creates:
`research.sqlite3` and exported datasets. v2.3.0 simply ignores them.

---

## 8. Support

If a project that passed v2.3.0 now fails, that is a regression — please open an issue with
the project file and the `check --json` output. If it now *passes* where it used to fail,
check §2.1: it is probably the DBE fix, and the improvement is intended.
