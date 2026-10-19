# Agent prompt packs

PaperForge is deterministic: it assembles and verifies. The prompts below are the
*judgement* layer — the parts of paper writing that need a writer, not a template. Each
pack is grounded: the model receives `paperforge context` (a JSON evidence pack of the
only numbers, compounds, citation keys and journal limits it is allowed to use) and its
output is re-checked by `paperforge check`.

Nothing here lets a model invent a result. If a sentence needs a number that is not in the
evidence pack, the correct answer is to ask you for it.

| pack | use it when | output |
|---|---|---|
| `01-draft-from-data.md` | you have tables, compounds, figures, refs but no prose | section prose in the project's YAML shape |
| `02-literature-triage.md` | you have 50–300 abstracts to sort | a ranked, exclusion-coded shortlist |
| `03-reviewer-2.md` | you want a hostile but fair pre-submission review | a structured review mapped to rule codes |
| `04-rebuttal.md` | you have reviewer comments to answer | point-by-point response with evidence |

Workflow:

```bash
paperforge ingest ~/my-study --out papers/study-1     # folder → project
paperforge context papers/study-1 > facts.json        # grounded evidence pack
# paste facts.json + the prompt into your model, save the answer as prose.md
paperforge check papers/study-1                        # verify before drafting
```
