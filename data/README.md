# Data provenance

Everything here is generated from public APIs (OpenAlex, Crossref) or maintained by hand
from publisher guidelines. Nothing is scraped from paywalled sources.

| file | rows | what it is | who uses it |
|---|---|---|---|
| `publications-openalex.json` | 1,616 works | every work (2009–2026) by the 30 IISER Bhopal chemistry faculty, resolved by OpenAlex author ID and institution `I288749910`. **Single source of truth for the corpus.** | `paperforge journals match` |
| `journals.csv` | 261 | one row per journal the engine knows: family, publisher, scope terms, IF, APC, OA, aliases, limits flag | `journals list/search/show`, profile resolution |
| `journal_limits.json` | 261 + 35 overrides | family defaults plus per-journal overrides verified against author guidelines | every limit check |
| `journal-activity.csv` | 261 | derived: papers per journal per year, used for the frequency prior | matcher |
| `publications-sample.json` | 200 | a small slice kept for offline demos and documentation examples | docs |
| `iiserb-bhopal-*.csv/md` | — | **v1 raw exports**, retained for history. Superseded by `publications-openalex.json` and `journals.csv`; the v1 README's "1,707 publications / 257 journals" came from these and was wrong (double counting + ChemInform digests). | nothing in v2 |

## How the corpus was built

```
OpenAlex institutions/I288749910  → 30 faculty author IDs
OpenAlex works?filter=author.id:A1|A2|…&page=N&per-page=200   (cursor paging 401s)
  → dedupe by DOI/OpenAlex ID → 1,616 works → attributes:
      title, year, journal display name, DOI, type, cited_by_count
```

Counts as of 2026-10-19: **1,616 works**, 2009–2026. 253 distinct venue names, **252 after
merging the `Angewandte Chemie` German/International split** and excluding the ChemInform
digest. The engine maintains **261 profiles**, because it also knows venues the
department has not (yet) published in and that authors ask about.

## Refreshing

```bash
python3 scripts/refresh_corpus.py          # re-pulls OpenAlex, rewrites publications-openalex.json
python3 -m paperforge journals list | wc -l
```

`scripts/refresh_corpus.py` is rate-limit aware (polite pool, 1 request/second, retries on
429/503) and never deletes the previous file until the new one parses.
