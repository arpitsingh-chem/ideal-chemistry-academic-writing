#!/usr/bin/env python3
"""
doi2bib.py — DOI → BibTeX via the free CrossRef API (no key required).

Usage:
    python3 doi2bib.py 10.1002/anie.202100123
    python3 doi2bib.py 10.1021/jacs.1c01020 10.1039/D4CC01234A --append refs.bib

Polite pool: include your e-mail with --mailto (recommended by CrossRef).
"""
import json
import sys
import time
import urllib.parse
import urllib.request

API = "https://api.crossref.org/works/{}/transform/application/x-bibtex"

def fetch_bibtex(doi: str, mailto: str = "") -> str:
    url = API.format(urllib.parse.quote(doi))
    headers = {
        "User-Agent": f"doi2bib/1.0 (mailto:{mailto})" if mailto else "doi2bib/1.0 (mailto:research@example.org)",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__); sys.exit(0)
    dois, append = [], None
    for a in sys.argv[1:]:
        if a == "--append":
            append = sys.argv[sys.argv.index(a) + 1]
        elif a.startswith("--mailto"):
            pass
        elif not a.startswith("--"):
            dois.append(a)
        else:
            mailto = sys.argv[sys.argv.index(a) + 1]

    mailto = ""
    if "--mailto" in sys.argv:
        mailto = sys.argv[sys.argv.index("--mailto") + 1]

    out = []
    for doi in dois:
        try:
            b = fetch_bibtex(doi, mailto)
            out.append(b.strip())
            print(f"OK   {doi}")
        except Exception as e:
            print(f"FAIL {doi}: {e}", file=sys.stderr)
        time.sleep(0.5)  # be polite

    if append and out:
        with open(append, "a", encoding="utf-8") as f:
            f.write("\n" + "\n\n".join(out) + "\n")
        print(f"Appended {len(out)} entries to {append}")
    elif out:
        print("\n" + "\n\n".join(out))

if __name__ == "__main__":
    main()
