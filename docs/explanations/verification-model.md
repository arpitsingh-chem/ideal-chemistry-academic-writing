# Explanation: what a passing score actually means

PaperForge reports `READINESS 100.0/100 grade A+`. It is important to be precise about what
that does and does not assert, because a tool that overstates its own guarantees is worse
than no tool.

---

## The three kinds of correctness

| Kind | Question | Can software answer it? |
|---|---|---|
| **Arithmetic** | Does 0.86 mmol × 257.31 g/mol × 82 % equal 0.181 g? | **Yes**, definitively |
| **Internal consistency** | Do the integrals sum to the number of hydrogens in the stated formula? Does the formula satisfy the valence rules? | **Yes**, given the stated inputs |
| **Experimental truth** | Was that mass actually weighed? Is the compound what the NMR says it is? | **No.** Only the laboratory can. |

PaperForge automates the first two. It is silent about the third, and its silence must not
be read as endorsement.

## What a 100/100 therefore asserts

* every declared number is arithmetically consistent with every other declared number;
* every formula parses and satisfies valence/DBE sanity (or the exception is reported);
* every DOI resolves and none is retracted;
* the manuscript satisfies the structural and ethical requirements of the target journal
  **as recorded in the journal profile**;
* no style or hype flags fire.

## What it does not assert

* that the data are real;
* that the compound is novel, or exists;
* that the journal's requirements are current (only 5 of 261 profiles are journal-verified);
* that the science is correct, reproducible, or important;
* that a reviewer will agree.

A paper can be perfectly self-consistent and entirely fabricated. This software cannot tell
the difference — and any tool that claims otherwise is lying.

## Why the checks are shaped the way they are

**Prefer a false negative to a false positive.** The audit found the DBE check raising hard
errors on triphenylphosphine and TMSCl. A tool that says "this molecule cannot exist" about
correct chemistry teaches users to ignore its errors, which destroys the value of every
other check. So where an element has variable valence, or a species is charged, the finding
is downgraded to a note rather than an error (`DECISIONS.md` D-05 and `chem.py`).

**Never invent a value to fill a gap.** An unknown mass is reported as unknown. If an
adduct is missing, the check is skipped; it does not assume `[M+H]⁺`.

**Separate severity from existence.** `error` / `warn` / `info` encode *how sure the tool
is that something is wrong*, not how bad it would be if it were.

## The score

```
score = 100 − 12·errors − 4·warnings − 0.5·notes      (any critical finding caps at 55)
≥ 90 submission-ready · ≥ 75 minor revision · ≥ 60 major revision
```

The weights are a judgment call, not a measurement. They are published so you can disagree
with them and change them. What they are *not* is a prediction of acceptance.

## The right mental model

PaperForge is a **tireless, literal-minded postdoc** who checks every number against every
other number and every reference against Crossref, and who never gets bored. It is not a
reviewer, an editor, or a scientist. Use it to eliminate the errors that are mechanically
detectable, then think.

## Corollary for the research layer

The same discipline applies to metadata:

* provenance is recorded for every value, so you can always ask "says who?";
* `retraction_status: none_known` means *no notice was found in the sources queried* —
  never "this paper is sound";
* the coverage report publishes its own gaps;
* a provider that fails is reported as failed, and the run says the results are incomplete.

The unifying rule: **the system's output tells you what it did and what it could not do,
and never fills the second category with something that looks like the first.**
