"""Tests for GRE material import / dedupe."""

from __future__ import annotations

from pathlib import Path

from backend.vocab.gref_import import (
    collect_gref_entries,
    dedupe_entries,
    display_lemma,
    has_usable_meaning,
    lemma_key,
    merge_into_bank,
    parse_gref_file,
)


def test_display_lemma_title_case():
    assert display_lemma("abate") == "Abate"
    assert display_lemma("ABATE") == "Abate"
    assert display_lemma("self-abnegation") == "Self-Abnegation"


def test_dedupe_case_variants():
    entries = [
        {"word": "abate", "meaning": "short", "examples": [], "tags": [], "sources": ["a"]},
        {"word": "Abate", "meaning": "become less in amount or intensity", "examples": [{"text": "x"}], "tags": [], "sources": ["b"]},
        {"word": "ABATE", "meaning": "mid", "examples": [], "tags": [], "sources": ["c"]},
    ]
    out = dedupe_entries(entries)
    assert len(out) == 1
    assert out[0]["word"] == "Abate"
    assert "become less" in out[0]["meaning"]
    assert out[0]["examples"]
    assert set(out[0]["sources"]) == {"a", "b", "c"}


def test_parse_txt_and_csv(tmp_path: Path):
    txt = tmp_path / "Sample.txt"
    txt.write_text("Abate:become less\nFoo:bar; ???\n", encoding="utf-8")
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text(
        "word,definition,example\nabate,longer definition here,The storm will abate.\nQuux,,\n",
        encoding="utf-8",
    )
    a = parse_gref_file(txt)
    b = parse_gref_file(csv_path)
    merged = dedupe_entries(a + b)
    by = {lemma_key(w["word"]): w for w in merged}
    assert "abate" in by
    assert "longer definition" in by["abate"]["meaning"]
    assert by["abate"]["examples"]
    assert "foo" in by
    assert "???" not in by["foo"]["meaning"]
    assert "quux" in by
    assert not has_usable_meaning(by["quux"])


def test_embeddings_csv_ignores_vectors(tmp_path: Path):
    path = tmp_path / "words_meaning_embeddings.csv"
    path.write_text(
        "word,definition,word_list,embedding_1,embedding_2\n"
        "abate,\"(v) reduce, diminish\",manhattan_500,0.1,-0.2\n",
        encoding="utf-8",
    )
    rows = parse_gref_file(path)
    assert len(rows) == 1
    assert rows[0]["word"] == "Abate"
    assert "reduce" in rows[0]["meaning"]
    assert "embedding" not in rows[0]


def test_merge_into_bank_no_dupes():
    existing = [
        {
            "id": 1,
            "word": "Abate",
            "meaning": "",
            "examples": [],
            "tags": [],
            "sources": [],
        }
    ]
    imported = [
        {
            "word": "abate",
            "meaning": "become less",
            "examples": [{"text": "Rain will abate."}],
            "tags": [],
            "sources": ["barrons"],
        },
        {
            "word": "Zenith",
            "meaning": "highest point",
            "examples": [],
            "tags": [],
            "sources": ["magoosh"],
        },
    ]
    out, stats = merge_into_bank(existing, imported, replace=False)
    assert stats["added"] == 1
    assert stats["updated"] == 1
    assert len(out) == 2
    assert lemma_key(out[0]["word"]) == "abate"
    assert out[0]["meaning"] == "become less"


def test_priority_from_source_overlap():
    from backend.vocab.gref_import import priority_from_sources, sort_by_priority

    assert priority_from_sources(["a"]) == 1
    assert priority_from_sources(["a", "b", "c", "d", "e"]) == 4
    words = [
        {"word": "Zebra", "meaning": "z", "sources": ["a"], "examples": [], "tags": []},
        {"word": "Abate", "meaning": "a", "sources": ["a", "b", "c", "d", "e", "f", "g", "h"], "examples": [], "tags": []},
        {"word": "Middle", "meaning": "m", "sources": ["a", "b"], "examples": [], "tags": []},
    ]
    ordered = sort_by_priority(words)
    assert ordered[0]["word"] == "Abate"
    assert ordered[0]["priority"] == 5
    assert ordered[0]["id"] == 1
    assert ordered[-1]["word"] == "Zebra"
