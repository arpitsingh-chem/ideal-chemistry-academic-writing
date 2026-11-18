# How to verify a journal profile

**Use when:** you are about to submit, or you maintain `paperforge/data/journal_limits.json`.

---

## 1. Check what the tool knows

```bash
python3 -m paperforge journals show "Organic Letters"
```

```json
{
  "journal": "Organic Letters",
  "family": "acs",
  "publisher": "American Chemical Society",
  "article_type": "letter",
  "limits": { "abstract_max": 200, "body_max_words": 3000, "refs_max": 50, "figures_max": 5 },
  "toc": { "required": true, "width_cm": 8.25, "height_cm": 4.45, "dpi": 300 },
  "ai_disclosure": "recommended",
  "verified": true,
  "source": "https://researcher-resources.acs.org/publish/author_guidelines?coden=orlef7",
  "notes": ["Organic Letters counts the abstract and TOC graphic together (limit 200 words)."]
}
```

(Abridged: the real output also carries `title_max_words`, `credit_required`,
`data_statement_required`, `orcid`, `highlights_required`, `cover_letter_required`.)

If `verified` is `false` or there is no `source`, the limits are a **publisher-family
default**, not that journal's rules. Treat them as a starting point only.

## 2. Verify against the publisher's page

| Read from the page | Field in `journal_limits.json` |
|---|---|
| abstract word limit | `article_types.<type>.abstract_max` |
| main-text word/page limit | `body_max_words` / `printed_pages` |
| figure/table caps | `figures_max` / tables |
| reference cap | `refs_max` |
| TOC / graphical-abstract size | `toc_width_cm`, `toc_height_cm`, `toc_dpi` |
| required statements (COI, data availability, ethics, AI use) | `required_statements` |

## 3. Write the entry

```json
"Organic Letters": {
  "family": "acs",
  "verified": true,
  "verified_on": "2026-11-18",
  "source": "https://researcher-resources.acs.org/publish/author_guidelines?coden=orlef7",
  "article_types": { "letter": { "abstract_max": 200, "body_max_words": 3000 } }
}
```

**Only set `verified: true` if you opened the page today.** A stale "verified" is worse than
an honest default, because an author will trust it.

## 4. Confirm

```bash
python3 -m paperforge journals show "Organic Letters"      # verified: true, with source
python3 -m pytest tests/test_journals.py -q
git commit -am "journals: verify Organic Letters limits (2026-11-18)"
```

## 5. When a publisher changes the rules

1. Update the numbers.
2. Bump `verified_on`.
3. Note the change in `CHANGELOG.md` under the next version — an author who relied on the
   old value deserves to know.

## 6. Do not do this

* Do not copy the publisher's guideline prose into the data file.
* Do not infer a limit from a sister journal.
* Do not add an impact factor, acceptance rate or APC value you have not sourced from a
  citable, current document; those columns exist and are deliberately empty
  (`AUDIT_REPORT.md` §4, D2–D3).
