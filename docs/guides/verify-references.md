# How to verify references (and what to do about a retraction)

**Use when:** before submission, or whenever you inherit a reference list you did not build
yourself.

---

## 1. Verify

```bash
python3 -m paperforge refs verify path/to/project
```

```
8 references: 8 verified, 0 unverified, 0 not found, 0 retracted, 0 duplicate DOI(s)
```

Each line shows the citation key, the DOI, and the title Crossref returned. **Check the
titles** — a DOI that resolves to a different paper is the most dangerous failure here, and
it is only visible by reading this output.

## 2. Understand what was checked

| Check | What it means |
|---|---|
| DOI resolves | the registration agency knows this DOI |
| Metadata matches | title/author/year returned by Crossref |
| Retraction (forward) | Crossref was asked *"is there a retraction notice that updates this DOI?"* — the reliable direction, because the notice carries the link |
| Duplicates | the same DOI appearing under two keys |

It does **not** check that the paper says what you claim it says. That is your reading.

## 3. When a DOI is not found

```
✗ mykey  10.9999/does.not.exist  not found
```

Possible causes, in order of likelihood:

1. **A typo.** DOIs are case-insensitive but must be exact otherwise.
2. **A preprint DOI** that was later replaced by a journal DOI — search the title.
3. **A dataset or book chapter** registered with DataCite rather than Crossref. Verify with
   `paperforge research fetch <doi> --source datacite`.
4. **A fabricated reference.** This is what the check exists for. Delete it.

## 4. When a reference is retracted

```
✗ somekey  10.1021/ja054131h  RETRACTED (notice: 10.1021/ja207910h)
```

`check` treats this as a **critical** finding and caps the score at 55.

What to do:

1. Read the retraction notice — retractions are sometimes partial or contested.
2. Remove the citation, or cite it explicitly *as retracted* if the retraction is itself
   part of your argument ("this result was later retracted [12]").
3. Re-verify: `paperforge refs verify .`

Never keep a retracted reference silently. Reviewers check.

## 5. Offline / CI use

`refs verify` caches results in `.paperforge/refcache.json`. Commit that file if you want CI
to check references without network access:

```bash
python3 -m paperforge refs verify .      # populates the cache (once, with network)
git add .paperforge/refcache.json
python3 -m paperforge check .            # now works offline, using the cache
```

A cached retraction stays flagged offline — that is why the cache stores the retraction
verdict rather than just "verified".

## 6. Adding references by DOI

```bash
python3 -m paperforge refs add path/to/project 10.1021/jacs.5c13581 10.1039/D0SC01234A
```

This fetches the metadata and appends entries to `refs/refs.bib` and `references.md`. It
will refuse a DOI it cannot resolve rather than writing a stub.

## 7. A reference list is evidence

Two rules that are worth more than any tool:

* **Cite what you read.** A reference you copied from another paper's list may not exist,
  may be misattributed, or may be retracted.
* **Never cite for volume.** `REF-SELF` warns above 30 % self-citation, and
  `REF-RECENCY` notes when fewer than 20 % of references are recent — both are hints about
  the citation base, not verdicts.
