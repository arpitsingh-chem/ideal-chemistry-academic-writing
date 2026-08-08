#!/usr/bin/env python3
"""
text_stats.py — Prose rhythm profile for your draft.

Computes the sentence-level statistics that AI-detection tools are (publicly)
reported to weigh — sentence-length variance ("burstiness"), word-prediction
regularity proxy ("perplexity" is NOT computed here; it needs a language model)
— plus readability and repetition metrics.

HOW TO USE IT (read docs/09 before running):
  * If the text is YOUR OWN writing, use this as a false-positive alarm:
    very uniform rhythm (low variance) is a documented cause of human text
    being flagged. Vary sentence length deliberately.
  * Do NOT use this to mutate AI-generated text into "undetectable" text.
    That is academic misconduct and it fails against quarterly-retrained
    detectors anyway.

Usage:
    python3 text_stats.py main.tex        (.tex/.md/.txt accepted)
"""
import re
import sys
import math
import statistics

def strip_latex(text: str) -> str:
    text = re.sub(r"(?m)^%.*$", "", text)
    text = re.sub(r"\\[a-zA-Z]+\*?", " ", text)
    text = re.sub(r"[{}]", " ", text)
    text = re.sub(r"\$[^$]*\$", " X ", text)
    return text

def sentences(text: str):
    text = re.sub(r"\s+", " ", text)
    # split on sentence boundaries, keep abbreviations intact-ish
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(])", text)
    out = []
    for p in parts:
        p = p.strip()
        if p and not re.match(r"^(fig|figs|et al|vs|i\.e|e\.g|cf|no|ref|eq|eqs|pp|vol|ca|approx)\.", p, re.I):
            out.append(p)
    return out

def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    raw = open(sys.argv[1], encoding="utf-8").read()
    text = strip_latex(raw)
    sents = sentences(text)
    if len(sents) < 10:
        print("Not enough sentences (<10) to profile meaningfully."); sys.exit(0)

    lengths = [len(s.split()) for s in sents]
    mean = statistics.mean(lengths)
    stdev = statistics.stdev(lengths) if len(lengths) > 1 else 0.0
    cv = stdev / mean if mean else 0.0          # coefficient of variation (burstiness proxy)
    short = sum(1 for L in lengths if L <= 8) / len(lengths)
    long = sum(1 for L in lengths if L >= 30) / len(lengths)
    words_all = re.findall(r"[A-Za-z]+", text)
    vocab = len(set(w.lower() for w in words_all))
    ttr = vocab / len(words_all) if words_all else 0.0
    # repetition: most common trigrams
    trigrams = [" ".join(w.lower() for w in words_all[i:i+3])
                for i in range(len(words_all) - 2)]
    from collections import Counter
    top = Counter(trigrams).most_common(5)
    top = [(t, c) for t, c in top if c > 2]

    print(f"=== Prose rhythm profile: {sys.argv[1]} ===")
    print(f"sentences analysed : {len(sents)}")
    print(f"mean sentence len  : {mean:.1f} words")
    print(f"sentence std dev   : {stdev:.1f}  (CV = {cv:.2f})")
    print(f"short (<=8 w)      : {short*100:.0f}%   long (>=30 w): {long*100:.0f}%")
    print(f"vocabulary         : {vocab} unique of {len(words_all)}  (TTR = {ttr:.3f})")
    print(f"repeated trigrams  : {top if top else 'none'}")
    print()
    print("Interpretation (docs/09):")
    if cv < 0.45:
        print("  LOW sentence-length variance — if this is your own text, you may be")
        print("  writing in very uniform sentences; vary rhythm (short topic sentences,")
        print("  long evidential ones, occasional asides). This reduces false-positive")
        print("  AI flags on genuinely human prose.")
    else:
        print("  Natural sentence-length variance — typical of varied human prose.")
    if ttr > 0.5:
        print("  Rich vocabulary. Good.")
    elif ttr < 0.35:
        print("  Narrow vocabulary — consider tightening repeated phrases.")
    if not top:
        print("  No notable trigram repetition detected.")

if __name__ == "__main__":
    main()
