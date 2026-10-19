#!/usr/bin/env python3
"""Refresh the publication corpus from OpenAlex.

Usage:
    python3 scripts/refresh_corpus.py                 # full refresh
    python3 scripts/refresh_corpus.py --dry-run       # fetch + report, do not write
    python3 scripts/refresh_corpus.py --limit 200     # smoke test

OpenAlex notes baked into this script (all learned the hard way):
  * cursor paging returns HTTP 401 on page 2 for this endpoint — use page=N;
  * `raw_affiliation_strings.search:` is unreliable — filter by institution +
    author IDs;
  * per-page maximum is 200;
  * the polite pool needs a `mailto`.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import os
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "paperforge" / "data" / "publications-openalex.json"
INSTITUTION = "I288749910"           # IISER Bhopal
MAILTO = "paperforge@example.org"
API = "https://api.openalex.org"


class BudgetExhausted(RuntimeError):
    """OpenAlex's shared, keyless daily budget is spent (HTTP 429 with a message)."""


API_KEY = os.environ.get("OPENALEX_API_KEY", "")


def _keyed(url: str) -> str:
    return f"{url}&api_key={API_KEY}" if API_KEY else url


def get(url: str, retries: int = 4) -> dict:
    """GET with polite-pool mailto, retry/backoff on 5xx.

    A 429 is *not* retried: without a key, OpenAlex's budget is shared by every
    user on the same IP and can be exhausted for the rest of the day.  Retrying
    only deepens the hole.  Set OPENALEX_API_KEY to get a private budget.
    """
    url = _keyed(url)
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={
            "User-Agent": f"paperforge/2.1 (mailto:{MAILTO})",
            "Accept": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise BudgetExhausted(
                    "OpenAlex returned 429: the keyless daily budget for this IP is "
                    "exhausted.\nSet an API key (free at https://openalex.org/settings/api) "
                    "and re-run:  OPENALEX_API_KEY=… python3 scripts/refresh_corpus.py"
                ) from exc
            if exc.code in (500, 502, 503, 504):
                wait = 2 ** attempt
                print(f"  HTTP {exc.code}; retrying in {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            raise
        except urllib.error.URLError as exc:
            print(f"  network error ({exc}); retrying", file=sys.stderr)
            time.sleep(2 ** attempt)
    raise RuntimeError(f"giving up on {url}")


def faculty_author_ids() -> list[dict]:
    """All authors at the institution with chemistry-relevant works."""
    authors: dict[str, dict] = {}
    page = 1
    while True:
        url = (f"{API}/authors?filter=last_known_institutions.id:{INSTITUTION}"
               f"&per-page=200&page={page}&mailto={MAILTO}")
        data = get(url)
        for a in data.get("results", []):
            works = a.get("works_count", 0)
            if works < 5:
                continue
            authors[a["id"].rsplit("/", 1)[-1]] = {
                "id": a["id"].rsplit("/", 1)[-1],
                "name": a.get("display_name", ""),
                "works_count": works,
                "concepts": [c["display_name"] for c in (a.get("x_concepts") or [])[:5]],
            }
        if page * 200 >= data.get("meta", {}).get("count", 0):
            break
        page += 1
        time.sleep(1)
    return sorted(authors.values(), key=lambda a: -a["works_count"])


def works_for(author_ids: list[str], limit: int | None = None) -> list[dict]:
    out: dict[str, dict] = {}
    per_page = 200
    page = 1
    while True:
        batch = author_ids[(page - 1) * 25: page * 25]
        if not batch:
            break
        filt = "|".join(batch)
        url = (f"{API}/works?filter=author.id:{filt}"
               f"&per-page={per_page}&page=1&select="
               "id,doi,title,publication_year,primary_location,type,cited_by_count,authorships"
               f"&mailto={MAILTO}")
        # one request per author batch, paginated inside the batch
        sub_page = 1
        while True:
            paged = url.replace("&page=1&", f"&page={sub_page}&")
            data = get(paged)
            results = data.get("results", [])
            for w in results:
                key = (w.get("doi") or w["id"]).lower()
                if key in out:
                    continue
                loc = w.get("primary_location") or {}
                src = loc.get("source") or {}
                out[key] = {
                    "id": w["id"],
                    "doi": (w.get("doi") or "").replace("https://doi.org/", "") or None,
                    "title": w.get("title") or "",
                    "year": w.get("publication_year"),
                    "journal": src.get("display_name") or "",
                    "type": w.get("type") or "",
                    "cited_by_count": w.get("cited_by_count", 0),
                }
                if limit and len(out) >= limit:
                    return sorted(out.values(), key=lambda x: (x["year"] or 0), reverse=True)
            meta = data.get("meta", {})
            if sub_page * per_page >= meta.get("count", 0) or not results:
                break
            sub_page += 1
            time.sleep(0.15)
            if sub_page > 25:      # guard against runaway pagination
                break
        page += 1
        time.sleep(1)
    return sorted(out.values(), key=lambda x: (x["year"] or 0), reverse=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args(argv)

    try:
        return _run(args)
    except BudgetExhausted as exc:
        print(f"\nerror: {exc}", file=sys.stderr)
        print("The committed corpus in data/ is unchanged and still valid.", file=sys.stderr)
        return 3


def _run(args) -> int:
    print(f"1/2 authors at {INSTITUTION} …", flush=True)
    authors = faculty_author_ids()
    print(f"    {len(authors)} authors with ≥5 works")
    if len(authors) > 40:
        authors = authors[:40]

    print("2/2 works …", flush=True)
    works = works_for([a["id"] for a in authors], limit=args.limit)
    journals = Counter(w["journal"] for w in works if w["journal"])
    print(f"    {len(works)} works, {len(journals)} distinct venues, "
          f"{min((w['year'] for w in works if w['year']), default=0)}–"
          f"{max((w['year'] for w in works if w['year']), default=0)}")
    print("    top venues:", ", ".join(f"{j} ({n})" for j, n in journals.most_common(5)))

    if args.dry_run:
        print("dry run: nothing written")
        return 0

    payload = {
        "_meta": {
            "source": "OpenAlex",
            "institution": INSTITUTION,
            "generated": time.strftime("%Y-%m-%d"),
            "mailto": MAILTO,
            "note": "Regenerate with scripts/refresh_corpus.py; do not hand-edit.",
        },
        "authors": authors,
        "works": works,
    }
    out = Path(args.out)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    json.loads(tmp.read_text(encoding="utf-8"))   # validate before replacing
    tmp.replace(out)
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
