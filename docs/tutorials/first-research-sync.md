# Tutorial: your first research sync

**Time:** 10 minutes. **You need:** network access and a contact e-mail address.

You will query six open scholarly indexes at once, store the results in a local SQLite
database, and read a coverage report that tells you what failed.

Every transcript below was captured on **2026-11-18** on the current build. Counts change
with the query and the day; the *shape* of the output does not.

---

## 1. Identify yourself

```bash
export PF_MAILTO=you@example.org
```

Two reasons: Unpaywall **requires** an e-mail, and the other providers use it to identify a
polite client. Your address is sent only to those APIs and is never written into this
repository.

Optionally give OpenAlex its own quota:

```bash
export OPENALEX_API_KEY=...      # free: https://openalex.org/settings/api
```

Keyless OpenAlex shares one daily budget **per IP address**, and in practice it runs out.

## 2. See what is available

```bash
python3 -m paperforge research providers
```

```
11 provider adapter(s) implemented

source             ready  search  doi   OA  cited  note
arxiv              yes    yes     -     -   -      ready
crossref           yes    yes     yes   -   yes    ready
datacite           yes    yes     yes   yes -      ready
doaj               yes    yes     -     yes -      ready
europepmc          yes    yes     yes   yes -      ready
openalex           yes    yes     yes   yes yes    ready
orcid              yes    yes     -     -   -      ready
pubchem            yes    yes     -     -   -      ready
ror                yes    yes     -     -   -      ready
semantic_scholar   yes    yes     yes   -   yes    ready
unpaywall          ...    -       yes   yes -      requires a contact e-mail (PF_MAILTO)
```

Read the capability columns, not just "ready": a `-` under `cited` means that source cannot
give you citation counts at all, which is why a count is always stored with its source.

Below the table, `research providers` lists the **known unavailable** sources — ChemRxiv
(Cloudflare 403), Google Scholar (no API), Scopus, Web of Science, Dimensions, NIST WebBook
and CORE — each with the verified reason and an alternative. That list is part of the
product: it stops you waiting for data that will never arrive.

## 3. Search without storing anything

```bash
python3 -m paperforge research search "lanthanide single molecule magnet" --limit 3
```

```
2026  Reversible Pressure-Magnetic Modulation in a Tetrathiafulvalene-Based Dyad Piezochromic Dysprosium Single-Molecule Magnet
      Newcastle University                           10.25405/ncl.34472799            [datacite]
2023  Single-Molecule Magnets Based on Heteroleptic Terbium(III) Trisphthalocyaninate …
      Magnetochemistry                               10.3390/magnetochemistry9020036  [doaj]
...
15 record(s) from 5/7 providers
  unavailable: openalex (rate_limited: Insufficient budget. …)
  unavailable: semantic_scholar (rate_limited: Too Many Requests. …)
```

Note the last two lines. Seven sources were tried; five answered. PaperForge says so
instead of quietly returning fifteen records as if that were everything.

The `[datacite]` tag is provenance: this record came from that source.

## 4. Synchronise

```bash
python3 -m paperforge research sync "lanthanide single molecule magnet" \
    --db research.sqlite3 --limit 10 --from-year 2015
```

```
query: 'lanthanide single molecule magnet'   mode: write
  FAIL openalex         rate_limited: Insufficient budget. This request has no API key, …
  OK   crossref           10 record(s)  (index reports 751215)  716 ms
  OK   europepmc          10 record(s)  (index reports 892)  2078 ms
  OK   arxiv              10 record(s)  (index reports 10)  7837 ms
  OK   datacite           10 record(s)  (index reports 71)  3845 ms
  OK   doaj               10 record(s)  (index reports 27)  1147 ms
  FAIL semantic_scholar rate_limited: Too Many Requests. …
found 50, unique 50, merged 0, inserted 50, updated 0, unchanged 0
note: 2 provider(s) unavailable — results are incomplete, not empty
```

The run **exits 1**, because the result set is incomplete. In a cron job that is exactly
what you want: a partial sync is not a successful sync.

Run it again:

```bash
python3 -m paperforge research sync "lanthanide single molecule magnet" \
    --db research.sqlite3 --limit 10 --from-year 2015
```

```
found 50, unique 50, merged 0, inserted 0, updated 0, unchanged 50
```

`unchanged 50` — ingestion is idempotent. Nothing was duplicated, and the second run cost
five API round-trips instead of fifty inserts.

## 5. Read the coverage report

```bash
python3 -m paperforge research coverage --db research.sqlite3
```

```
Research coverage
=================
store                 : research.sqlite3
records               : 50
  with DOI            : 39
  with abstract       : 41
  authors with ORCID  : 13
  cross-checked       : 0
  conflicting         : 0
  retracted           : 0
venues / publishers   : 24 / 15
countries/institutions: 0 / 0
year range            : 2010–2026
records merged away   : 0
last successful sync  : 2026-11-18T08:37:56Z
...
provider health:
  openalex         failures=2 FAIL (Insufficient budget. …)
  semantic_scholar failures=2 FAIL (Too Many Requests. …)
```

Note what it does **not** say: it does not say "50 papers exist on this topic". It says
what is in *your* store, from the sources that answered. `cross-checked 0` and
`countries/institutions 0 / 0` are consequences of OpenAlex being unavailable — the fields
are reported as unknown rather than guessed from the venue.

## 6. Export something reproducible

```bash
python3 -m paperforge research export --db research.sqlite3 --out lanthanides.json
```

```
wrote 50 record(s) to lanthanides.json (+ coverage sidecar lanthanides.json.meta.json)
```

Two files: the dataset, and a sidecar carrying the coverage report **as it was at export
time**. Anyone can now see exactly which sources produced that file, and which were down.

## 7. Look at a single record

```bash
python3 -m paperforge research fetch 10.1021/jacs.5c13581
```

```
work_id              doi:10.1021/jacs.5c13581
doi                  10.1021/jacs.5c13581
title                Rapid and High-Yielding Disulfide Bioconjugation at Any Desired Site in Proteins
publication_year     2026
venue                Journal of the American Chemical Society
publisher            American Chemical Society (ACS)
article_type         journal-article
oa_status            closed
license              https://doi.org/10.15223/policy-029
citation_count       6
retraction_status    none_known
verification         cross_checked
completeness         0.9375
authors              Dastgir Shakil Shaikh, Suman Rajput, Dimpy Kalia
sources              ['crossref', 'europepmc', 'openalex']
```

`completeness 0.9375` means 1 of 16 tracked fields is unknown — and the record says which,
rather than filling it in. `sources` shows that three independent indexes agreed on this
record, which is what `verification: cross_checked` means.

## Next

* [Coverage and honesty](../explanations/coverage-and-honesty.md) — why `none_known` is not
  "safe".
* [Record schema](../reference/record-schema.md) — every field and its unknown semantics.
* [Add a provider](../guides/add-a-provider.md) — contribute a new source.
