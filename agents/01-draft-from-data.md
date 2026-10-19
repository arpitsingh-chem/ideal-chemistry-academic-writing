# Pack 01 — draft a section from grounded data

**Input:** `facts.json` from `paperforge context <project>`.
**Output:** Markdown, one `## <Heading>` per requested section.

## Prompt

> You are a chemist writing a manuscript for *{journal}* ({article_type}).
> Below is the ONLY evidence you may use. Rules, all enforced afterwards by `paperforge check`:
>
> 1. Every number must appear verbatim in `numbers_present_in_data` (rounding is allowed to
>    the reported precision, nothing else). If a claim needs a number that is absent, write
>    `[NEEDS DATA: what is missing]` instead of guessing.
> 2. Cite only keys listed in `citation_keys`, as `[key]` or `[key1,key2]`. Never cite a
>    paper that is not in that list, and never cite a method you did not use.
> 3. Respect the journal: abstract ≤ {abstract_max_words} words, body ≤
>    {body_max_words} words, title ≤ {title_max_words} words.
> 4. No hype vocabulary (novel, first, unprecedented, excellent, remarkable, groundbreaking)
>    and no claims of mechanism the data do not support.
> 5. Mean sentence length 18–26 words; vary rhythm; one idea per sentence.
>
> Evidence pack:
> ```json
> {paste facts.json}
> ```
>
> Write: {Introduction | Results and discussion | Conclusion}. Return only the Markdown.

## Acceptance checklist

- [ ] `paperforge check` reports 0 errors; `EVI-UNGROUNDED-ABSTRACT` absent.
- [ ] Every `[NEEDS DATA: …]` is resolved by you, not by the model.
- [ ] No citation key outside `citation_keys`.
- [ ] The abstract contains the five moves: context, gap, approach, result, impact.
