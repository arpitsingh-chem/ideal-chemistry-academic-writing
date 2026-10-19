"""scripts/refresh_corpus.py — offline behaviour (no network)."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location("refresh_corpus",
                                                  ROOT / "scripts" / "refresh_corpus.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_429_is_reported_as_budget_exhaustion_not_retried(monkeypatch):
    import urllib.error

    mod = _load()
    calls = []

    def fake_urlopen(*a, **k):
        calls.append(1)
        raise urllib.error.HTTPError("u", 429, "Too Many Requests", {}, None)

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    try:
        mod.get("https://api.openalex.org/works")
    except mod.BudgetExhausted as exc:
        assert "429" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected BudgetExhausted")
    assert len(calls) == 1, "a 429 must not be retried"


def test_faculty_and_works_parsing(monkeypatch):
    mod = _load()

    def fake_get(url):
        if "/authors" in url:
            return {"meta": {"count": 2}, "results": [
                {"id": "https://openalex.org/A1", "display_name": "A One",
                 "works_count": 40, "x_concepts": [{"display_name": "Chemistry"}]},
                {"id": "https://openalex.org/A2", "display_name": "A Two",
                 "works_count": 2, "x_concepts": []},   # below the 5-work floor
            ]}
        return {"meta": {"count": 1}, "results": [
            {"id": "https://openalex.org/W1", "doi": "https://doi.org/10.1/x",
             "title": "T", "publication_year": 2024, "type": "article",
             "cited_by_count": 3,
             "primary_location": {"source": {"display_name": "Chem. Commun."}}},
        ]}

    monkeypatch.setattr(mod, "get", fake_get)
    authors = mod.faculty_author_ids()
    assert [a["id"] for a in authors] == ["A1"]
    works = mod.works_for(["A1"])
    assert works[0]["doi"] == "10.1/x"
    assert works[0]["journal"] == "Chem. Commun."


def test_dry_run_writes_nothing(monkeypatch, tmp_path):
    mod = _load()
    monkeypatch.setattr(mod, "faculty_author_ids", lambda: [{"id": "A1"}])
    monkeypatch.setattr(mod, "works_for", lambda ids, limit=None: [
        {"id": "W", "doi": "10.1/x", "title": "T", "year": 2024,
         "journal": "J", "type": "article", "cited_by_count": 0}])
    out = tmp_path / "corpus.json"
    assert mod.main(["--dry-run", "--out", str(out)]) == 0
    assert not out.exists()


def test_committed_corpus_matches_the_documented_counts():
    data = json.loads((ROOT / "paperforge" / "data" / "publications-openalex.json").read_text(encoding="utf-8"))
    works = data["works"] if isinstance(data, dict) else data
    venues = {w["journal"] for w in works if w.get("journal") and w["journal"] != "ChemInform"}
    merged = {"Angewandte Chemie International Edition" if v == "Angewandte Chemie" else v
              for v in venues}
    assert len(works) == 1616
    assert len(venues) == 253          # raw venue names
    assert len(merged) == 252          # after the German/International merge
