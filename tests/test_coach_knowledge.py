from backend.hub.services.coach_knowledge import _extract_sections, _tokenize_query


def test_tokenize_query_strips_stopwords():
    tokens = _tokenize_query("What is exploratory data analysis in my lecture notes?")
    assert "exploratory" in tokens
    assert "analysis" in tokens
    assert "what" not in tokens


def test_extract_sections_prefers_matching_headers():
    text = """# Title

## Intro
General intro text.

## Exploratory Data Analysis
EDA is about patterns.

## Other
Unrelated section.
"""
    out = _extract_sections(text, ["exploratory", "eda"], max_chars=500)
    assert "Exploratory Data Analysis" in out
    assert "Unrelated section" not in out
