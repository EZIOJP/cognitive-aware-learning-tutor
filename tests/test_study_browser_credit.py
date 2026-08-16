"""Browser title → productive study credit (Scaler + Lecture Notes)."""

from backend.behavior.category_scores import build_scores_from_rules
from backend.behavior.domain_classify import classify_browser_title
from backend.behavior.productivity_policy import default_policy_dict, resolve_productivity_score


def _eff(title: str) -> tuple[str, int]:
    cat, _raw = classify_browser_title(title)
    scores = build_scores_from_rules()
    pol = default_policy_dict()
    return cat, resolve_productivity_score(cat, scores, pol)


def test_lecture_notes_titles_count_as_study():
    cat, eff = _eff("numpy lecture3 notes - Lecture Notes - Microsoft Edge")
    assert cat == "Study (Browser)"
    assert eff >= 60


def test_scaler_titles_count_as_coursework():
    cat, eff = _eff("Watch | Module 3 | Scaler Topics — Microsoft Edge")
    assert cat == "Coursework (Browser)"
    assert eff >= 60


def test_scaler_topics_without_brand_still_counts():
    cat, eff = _eff("Topics | Arrays - Microsoft Edge")
    assert "Study" in cat or "Coursework" in cat
    assert eff >= 60


def test_generic_browser_still_blocked():
    cat, eff = _eff("Shopping deals - Microsoft Edge")
    assert cat == "Other (Browser)"
    assert eff == 0
