# Pack 02 — literature triage

**Input:** title + abstract records (from `paperforge refs add`, a `.bib`, or an export).
**Output:** a table with a decision and a reason code for every record.

## Prompt

> You are screening the literature for a study on **{topic}**. For each record below,
> decide: `INCLUDE`, `MAYBE` or `EXCLUDE`, with one of these reason codes:
> `OFF-TOPIC`, `WRONG-METHOD`, `REVIEW-ONLY`, `NO-DATA`, `DUPLICATE`, `RETRACTED`,
> `SUPERFICIAL` (background only). Use only the title and abstract — do not infer results.
> Mark `SUPERFICIAL` for papers that are relevant background but not direct precedent.
>
> Return a Markdown table: `| key | decision | reason | one-line justification |`
> and then a short paragraph: what is already established, what is contested, and what gap
> the study fills. Do not propose citations that are not in the input.
>
> Records:
> ```json
> {paste records}
> ```

## Then, in the repo

```bash
paperforge refs add papers/study-1 10.1021/... 10.1039/...
paperforge refs verify papers/study-1        # retractions and DOI check
```

`REF-RETRACTED` is a blocker: a retracted paper in a manuscript is a desk-rejection risk.
