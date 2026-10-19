# Pack 04 — response to reviewers

**Input:** the decision letter, the reviewer comments, the revised manuscript, and the new
data (as CSV or compound records).

## Prompt

> Draft a point-by-point response. For each comment: quote it verbatim, then answer in
> three parts — (1) what we changed, with the exact new text or the new figure/table
> number; (2) where it appears (page, line, SI section); (3) the scientific reasoning.
> If we disagree, say so once, politely, with evidence; never repeat the same argument.
> Never promise an experiment that was not done. Never claim a change that the revised
> manuscript does not contain.
>
> Return Markdown with `### Reviewer 1, comment 3` style headings.

## Then

```bash
paperforge check papers/study-1            # the revision must still pass
paperforge bundle papers/study-1 --strict  # new zip, new checklist
```

The response letter must not introduce numbers that are absent from the revised data —
`EVI-UNGROUNDED-ABSTRACT` exists precisely because revision letters are where invented
numbers appear.
