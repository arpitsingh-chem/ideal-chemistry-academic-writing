# 09 · Originality, Plagiarism & AI-Detection Literacy (Evidence-Based)

> **The honest truth, stated once:** there is no reliable "bypass" for Turnitin's AI indicator, and anyone promising one is selling a race against a detector that is retrained quarterly. The professional path — the one that keeps working — is to **write original text, document your authorship, and use AI transparently as an assistant**. This document is that path, built from the detector's own documentation and independent evaluations.

---

## 1. How the detectors actually work (verified facts)

### Turnitin similarity (plagiarism check)
- Compares your text against a huge corpus (web, published literature, student submissions, your institution's archive).
- **Excluded by policy** in Indian universities (UGC/IISER norms): references/bibliography, TOC, acknowledgements, attributed quotes, generic terms/equations, common knowledge ≤14 consecutive words.
- Acceptable threshold at IISERs/Indian universities: **≤10% similarity** (core area) for theses; journal submissions must be essentially original beyond standard phrases.

### Turnitin AI-writing indicator
From Turnitin's own FAQs (guides.turnitin.com, [28477544839821](https://guides.turnitin.com/hc/en-us/articles/28477544839821-Turnitin-s-AI-writing-detection-capabilities-FAQs)):
- The model is **learned statistical patterns**, not hand-crafted rules; it is **retrained quarterly** with new AI outputs.
- It processes text in **overlapping sentence segments** and scores each segment; the headline % = share of flagged text.
- **Scores in 1–19% are NOT shown** — displayed as an asterisk (no number, no highlights). A visible score requires ≥20%.
- Turnitin's false-positive target: **<1%** for fully human text in documents with >20% flagged AI text — i.e., they admit false positives exist even in their design target.
- **Paraphraser/spinner-modified AI text is still detected** — Turnitin explicitly states detection includes text "modified using a word spinner/AI paraphrasing or bypassing tool".
- Turnitin itself instructs instructors: the AI score is an **indicator, not evidence of misconduct**, and must not be used to punish students without corroboration.

### What public analyses consistently find (independent studies, 2023–2026)
- Raw ChatGPT output: ~98% detected; Claude ~92%; Gemini ~89% (third-party benchmarks).
- **Synonym-swap paraphrasing (QuillBot-style): ~70% still detected** — because detection reads sentence *structure*, rhythm, and word-choice probability, not vocabulary.
- Manual, deep rewriting (restructure sentences, add your own claims/hedging): detection drops to ~12–45%.
- **False positives are real:** ~3–4% for native English writers, **6–8% for non-native (ESL) writers** — exactly the population most likely to be falsely accused. OpenAI *shut down its own AI classifier in 2023* because it was unreliable.

**Consequences:**
1. "Bypass" tools (spinners, "humanizers", invisible-character tricks) are the *most reliably detected* class of text — they fight the detector with the exact pattern the detector is trained to catch, and they destroy scientific precision (formulas, units, compound names get mangled).
2. A genuinely original, personally-written manuscript — the kind this repo helps you produce — has the lowest detection probability by construction *and* survives a human reading.

---

## 2. The professional workflow: originality by construction

### 2.1 Plagiarism-proof writing habits
- **Write first from sources with the source closed** — take structured notes (Zotero highlights + your own paraphrase in your own words), then draft from notes. This is the single most effective anti-plagiarism technique ever documented.
- **Paraphrase = restructure, not synonym-swap**: change sentence architecture, voice, and order of information; then cite. A paraphrase that keeps the source's sentence skeleton is plagiarism even with different words.
- **Quote when language matters**: instrument definitions, IUPAC nomenclature, safety warnings — short, quoted, cited (excluded from similarity by policy).
- **Standard phrases are fine**: "All reagents were used as received", "Yield: 82%" — these are genre conventions, not plagiarism. Writing them identically across papers is normal scientific practice and excluded as common knowledge/standard phrases.
- **Self-plagiarism**: reusing your own published text verbatim (in a thesis or a new paper) is treated as plagiarism by journals and by Turnitin. Rewrite; cite yourself.

### 2.2 Authorship evidence trail (protects you from false accusations)
Maintain, per manuscript:
- Overleaf/Google Docs/Word version history, or a **Git repository** (`git log` = dated authorship evidence).
- Lab notebook scans, raw data files, instrument files (NMR FIDs, XRD raw), notebook dates.
- Draft files with creation dates; intermediate versions.
- AI-use log if you used assistants (see §4) — transparency beats suspicion.

### 2.3 AI-detection-risk self-check (for genuinely human text)
Run `scripts/text_stats.py` on your draft. It reports sentence-length variance (burstiness), vocabulary richness, and rhythm metrics. **Use it as a false-positive alarm, not a "bypass" tool:**
- If your own text scores "low-variance", it means you write in very uniform sentences — vary length deliberately (short topic sentences, long evidential ones, one-sentence asides). This makes *human* writing read human.
- Add discipline-specific texture only you would write: your actual yield numbers, your instrument settings, your failed attempts, your hedged interpretations. Specificity is the strongest human signal.
- **Never** use the script's output to mutate AI text into "undetectable" text — that is exactly what §1 says fails, and it's academic misconduct if the AI text is passed off as yours.

## 3. Journal policies on AI use (2024–2026, portfolio journals)

| Publisher | Policy |
|-----------|--------|
| **ACS** | AI tools may assist with language/grammar editing; **must not** be listed as authors; disclose use in cover letter; authors responsible for all content. |
| **RSC** | Same principle: full author responsibility; disclosure recommended; AI-generated images require transparency. |
| **Wiley (incl. Angew., Chem. Eur. J.)** | AI tools may not be authors; use in writing must be disclosed to editors; authors accountable for accuracy. |
| **Elsevier/Springer** | Must disclose AI use in cover letter/methods; AI cannot be an author; no AI in figures without permission. |
| **IISER Bhopal / UGC** | Follow UGC's Academic Integrity policy: AI assistance must be disclosed per institute rules; similarity limits enforced. |

**Universal rule:** AI for *polish* (grammar, rewording suggestions, reference formatting) — disclosed; AI for *content claims* (data, conclusions, novelty) — never.

## 4. A defensible AI-assisted workflow (fully compliant)

```
1. YOU: design experiments, run them, analyse raw data → human-owned results.
2. AI (optional): literature triage, summarise papers you've read, suggest
   outline structures, rephrase your own sentences for clarity, format
   references (scripts/doi2bib.py), check grammar.
3. YOU: write every sentence about data, claims, and interpretation yourself;
   incorporate AI suggestions only where they preserve YOUR meaning.
4. Document: "AI tools [names] were used for grammar editing and reference
   formatting during the preparation of this manuscript. All scientific
   content, data, and conclusions are the authors' own."
5. Verify: rerun `paperforge check <project>` (87 rules) and `paperforge score`; keep drafts.
```

This workflow is: compliant with every publisher policy above, undetectable-by-construction (the science text is yours), and — most importantly — *true*.

## 5. If you are falsely flagged

- Stay calm; do not "confess". Ask which passages were flagged (per-segment highlights).
- Present the evidence trail (§2.2): version history, notes, raw data, earlier drafts with dates.
- Note the detector's documented false-positive rate (6–8% for non-native writers).
- Request a human re-read of the flagged passages; cite Turnitin's own guidance that the indicator is not proof of misconduct.

---

*Next: [10-free-tools-and-apis.md](10-free-tools-and-apis.md)*
