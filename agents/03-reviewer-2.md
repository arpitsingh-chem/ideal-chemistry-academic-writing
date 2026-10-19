# Pack 03 — reviewer 2, before the editor is

**Input:** the composed manuscript (`paperforge draft <project>` → `build/manuscript.md`)
plus `paperforge check <project> --json`.

## Prompt

> Act as Reviewer 2 for *{journal}*, an expert in {subfield} with 20 years of experience.
> You are rigorous, not rude. Read the manuscript and produce:
>
> 1. **Summary** (3 sentences: what was done, what is claimed, what is new).
> 2. **Major concerns** — each with: the claim at issue, the evidence given, what would be
>    required to support it, and a severity (`blocking` / `major` / `minor`). Prioritise
>    claims that outrun the data: mechanism without kinetics or labelling, scope without
>    yield ranges, "first" without a search.
> 3. **Minor concerns** — presentation, units, compound numbering, SI completeness.
> 4. **Recommendation** (`accept` / `minor revision` / `major revision` / `reject`) with one
>    paragraph of justification.
>
> Do not invent missing experiments; say what is missing. Where a check code applies
> (`CHEM-HRMS-CALCD`, `EVI-CCDC`, `ETH-DATA-REQUEST`, `REF-RETRACTED`), name it.
>
> Manuscript:
> ```markdown
> {paste build/manuscript.md}
> ```

## Why this works

The rule engine finds *mechanical* faults; a model reviewer finds *scientific* ones —
overclaiming, unstated assumptions, experiments that do not isolate the variable. Run both
before submission; they rarely overlap.
