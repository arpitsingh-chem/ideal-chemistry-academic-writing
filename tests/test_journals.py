"""Journal database, profile resolution and matcher tests."""
import pytest

from paperforge.journals import (
    Matcher, journal_names, profile, resolve, retarget, search,
)

MATCH_CASES = [
    # (query, must appear in the top 5)
    ("gold-catalyzed synthesis of heterocycles", {"Organic Letters", "Chemical Communications",
                                                   "Chemistry - A European Journal", "ACS Catalysis",
                                                   "Asian Journal of Organic Chemistry", "Tetrahedron Letters",
                                                   "Angewandte Chemie International Edition",
                                                   "Angewandte Chemie"}),
    ("single-molecule magnets based on lanthanide complexes",
     {"Dalton Transactions", "Inorganic Chemistry", "Chemistry - A European Journal",
      "Chemical Communications", "Coordination Chemistry Reviews"}),
    ("porous organic polymers for CO2 capture and conversion",
     {"Chemical Communications", "Chemistry - An Asian Journal", "ACS Applied Materials & Interfaces",
      "Journal of Materials Chemistry A", "Langmuir", "ACS Omega"}),
    ("crystal engineering of halogen bonds and polymorphism",
     {"CrystEngComm", "Crystal Growth & Design", "Journal of Molecular Structure",
      "Acta Crystallographica Section C Structural Chemistry"}),
    ("fluorescent probe for protein bioconjugation and bioimaging",
     {"Chemical Communications", "Chemistry - A European Journal", "Organic & Biomolecular Chemistry",
      "The Journal of Organic Chemistry", "Chemical Science", "Chemical Reviews",
      "Journal of the American Chemical Society", "Bioconjugate Chemistry", "The Analyst",
      "Journal of Materials Chemistry B", "Chemical Society Reviews"}),
]


@pytest.mark.parametrize("query,expected", MATCH_CASES)
def test_matcher_is_relevant(query, expected):
    m = Matcher()
    top = {r["journal"] for r in m.recommend(query, top=5)}
    assert top & expected, f"top-5 {top} did not intersect {expected}"


def test_matcher_changes_with_input():
    """Regression test for the v1 bug: every query returned the same list."""
    m = Matcher()
    a = [r["journal"] for r in m.recommend("gold catalysis heterocycles", top=5)]
    b = [r["journal"] for r in m.recommend("single molecule magnets lanthanides", top=5)]
    assert a != b


def test_matcher_excludes_preprints_and_non_venues():
    m = Matcher()
    names = [r["journal"] for r in m.recommend("visible light photoredox catalysis", top=15)]
    assert "ChemRxiv" not in names
    assert "ChemInform" not in names


def test_matcher_family_filter():
    m = Matcher()
    rows = m.recommend("organic synthesis methodology", top=5, family="rsc")
    assert rows and all(r["family"] == "rsc" for r in rows)


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

def test_alias_resolution():
    assert resolve("ChemComm")["journal"] == "Chemical Communications"
    assert resolve("OL")["journal"] == "Organic Letters"
    assert resolve("JACS")["journal"] == "Journal of the American Chemical Society"
    assert resolve("Angew. Chem. Int. Ed.")["journal"] == "Angewandte Chemie International Edition"
    assert resolve("PCCP")["journal"] == "Physical Chemistry Chemical Physics"


def test_unknown_journal_raises():
    with pytest.raises(KeyError):
        resolve("Advances in Completely Fictional Chemistry")


def test_verified_limits():
    ol = profile("Organic Letters", "letter")
    assert ol.limits.abstract_max == 200
    assert (ol.toc_width_cm, ol.toc_height_cm) == (8.25, 4.45)
    assert ol.verified

    angew = profile("Angewandte Chemie International Edition", "communication")
    assert angew.limits.abstract_max == 200
    assert angew.limits.printed_pages == 4
    assert angew.toc_text_max_chars == 450
    assert angew.abstract_forbids_compound_numbers

    chemcomm = profile("Chemical Communications", "communication")
    assert chemcomm.limits.abstract_max == 250
    assert chemcomm.toc_dpi == 600


def test_unverified_journal_is_flagged():
    p = profile("Journal of Molecular Structure")
    assert any("official guidelines" in n for n in p.notes)


def test_article_type_alias():
    assert profile("Journal of the American Chemical Society", "letter").article_type == "communication"
    # Organic Letters only publishes Letters, so any synonym resolves to its single type
    assert profile("Organic Letters", "paper").article_type == "letter"
    # a journal with several types honours the requested one
    assert profile("Chemistry - A European Journal", "review").article_type == "review"


def test_retarget_reports_required_changes():
    src = profile("Chemistry - A European Journal", "article")
    dst = profile("Organic Letters", "letter")
    rows = retarget(src, dst, {"abstract_words": 240, "body_words": 5000, "references": 60, "figures": 7})
    items = {r["item"]: r["status"] for r in rows}
    assert items["abstract words"] == "fail"
    assert items["body words"] == "fail"
    assert items["references"] == "fail"


def test_database_integrity():
    names = journal_names()
    assert len(names) > 240
    assert len(names) == len(set(names))
    for n in ("Chemical Communications", "Nature", "Chemical Science", "ChemRxiv"):
        assert n in names
    rows = search("angew")
    assert rows
