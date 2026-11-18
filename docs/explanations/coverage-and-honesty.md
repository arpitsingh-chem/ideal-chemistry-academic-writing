# Explanation: coverage, and why "none known" is not "safe"

The research layer answers questions about the literature. Every one of those answers is
bounded by *which sources answered, and when*. This page explains how PaperForge keeps that
boundary visible instead of hiding it.

---

## 1. The three lies a search tool can tell

| Lie | How it usually happens | What PaperForge does |
|---|---|---|
| "Nothing was published on this" | a provider timed out and its empty result was treated as a real zero | a failed provider is reported as **failed**; the run says *"results are incomplete, not empty"* and exits `1` |
| "This paper is fine" | every paper gets `retracted: false` because the source has no retraction field | `RetractionStatus.NONE_KNOWN` vs `UNKNOWN`; the coverage report states the distinction |
| "We have N papers" | N counts rows, including duplicates and stale copies | duplicates are merged with an audit trail; `records` is what remains, and coverage lists what was merged away |

## 2. Absence of evidence

`none_known` is the single most misreadable value in the system, so it is named for what it
is: the sources queried contained **no notice** of retraction.

| Sources queried | `retraction_status` | Interpretation |
|---|---|---|
| Crossref answered, no notice | `none_known` | Crossref has no retraction notice for this DOI |
| Crossref unavailable | `unknown` | nothing is known; do not infer safety |
| notice found | `retracted` (+ notice DOI) | |
| correction found | `correction` | the paper stands, with a published correction |

That third row is why the pipeline never merges a provider's silence with another
provider's silence into a confident `false`.

## 3. Completeness is measured per record

```python
rec.completeness()      # 0.75
rec.missing_fields()    # ['abstract', 'keywords', 'oa_status', 'funding']
```

`0.75` is not a quality score for the paper. It means a quarter of the tracked fields are
unknown — usually because that provider does not publish them (Crossref has no
open-access field; arXiv has no citation count). The number is a *statement about
metadata*, and it travels with the record.

## 4. Coverage is measured per store

`paperforge research coverage` reports: records, DOIs, abstracts, ORCIDs, cross-checked and
conflicting records, retractions, venues, publishers, countries, institutions, year range,
merged records, per-source provenance counts, provider health, and the last successful sync.

It also always prints **known gaps**, including:

* citation counts are point-in-time and provider-specific;
* retraction status is source-scoped;
* full text is never downloaded for closed access;
* any provider with a recorded failure;
* institution/country fields are empty when OpenAlex is unavailable.

## 5. Why institutions can legitimately be zero

In the reference run (`GLOBAL_RESEARCH_COVERAGE.md` §2), `countries: 0` and
`institutions: 0` — because OpenAlex was rate-limited and OpenAlex is the only integrated
source that publishes institutional affiliations in structured form. Reporting `0` is the
honest answer to "how many institutions are represented *in this store*". It is not an
answer to "how many institutions published on this topic".

## 6. The bundled institutional collection

`paperforge institution stats` reads a fixed snapshot of 1,616 IISER Bhopal works and prints,
every time:

> not a live query and not complete for the institution

Two fields in that snapshot (`is_oa`, `is_retracted`) were never captured. The code reports
them as *"not captured in snapshot"* rather than `0`, because "zero open-access works" would
be a false negative dressed up as data.

## 7. The rule

> A tool that cannot distinguish "we found nothing" from "we could not look" will eventually
> report the first when it means the second.

Every design choice in this layer exists to keep those two apart: typed provider errors,
per-provider failure records, provenance on every value, explicit unknown states, and a
coverage report that publishes its own gaps.
