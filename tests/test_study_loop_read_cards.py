from pathlib import Path

from backend.quiz import read_cards as rc


def test_digest_l5_topic_from_fixture(tmp_path: Path):
    note = tmp_path / "L05_pandas_operations_notes.md"
    note.write_text(
        "# Pandas\n\n## Topic Index\n\n| ID | Topic |\n|---|---|\n| `L5-T05` | Unique values |\n\n"
        "## `L5-T05` — Unique values\n\n"
        "Use `unique()` and `nunique()`.\n\n"
        "## `L5-T06` — Mutability\n\n"
        "Assigning through iloc.\n",
        encoding="utf-8",
    )
    cards = rc.list_read_cards(tag="L5-T05", root=tmp_path)
    assert len(cards) == 1
    card = cards[0]
    assert card["card_id"] == "L05_pandas_operations_notes.md::L5-T05"
    assert card["tag"] == "L5-T05"
    assert "unique()" in card["body_markdown"]
    assert "Mutability" not in card["body_markdown"]
    got = rc.get_read_card(card["card_id"], root=tmp_path)
    assert got is not None
    assert got["title"].lower().startswith("unique")


def test_real_notes_have_l5_or_mt1():
    from backend.paths import NOTES_DIR
    from backend.quiz import read_cards as rc

    if not (NOTES_DIR / "L05_pandas_operations_notes.md").is_file():
        return
    cards = rc.list_read_cards(tag="L5-T05")
    assert cards and "unique" in cards[0]["body_markdown"].lower()


def test_malformed_card_id_returns_none():
    assert rc.get_read_card("no-hash-here") is None
    assert rc.get_read_card("") is None


def test_writeback_replaces_section_body_only(tmp_path: Path):
    from backend.quiz import note_writeback as wb

    note = tmp_path / "math" / "MT1_aptitude_interview_notes.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        "# MT1\n\n## Topic Index\n\n- `MT1-T02` — LCM & HCF\n\n"
        "## `MT1-T02` — LCM & HCF\n\nOld body.\n\n"
        "## `MT1-T03` — Percentages\n\nKeep me.\n",
        encoding="utf-8",
    )
    mtime = note.stat().st_mtime
    out = wb.patch_note_section(
        note_path="math/MT1_aptitude_interview_notes.md",
        topic_id="MT1-T02",
        body_markdown="New body with formula.",
        title="LCM and HCF",
        expected_mtime=mtime,
        root=tmp_path,
    )
    text = note.read_text(encoding="utf-8")
    assert "New body with formula." in text
    assert "Keep me." in text
    assert "Old body." not in text
    assert "LCM and HCF" in text
    card = rc.get_read_card(out["card_id"], root=tmp_path)
    assert card and "New body" in card["body_markdown"]


def test_writeback_ignores_hash_heading_inside_code_fence(tmp_path: Path):
    """False ## inside a fence must not truncate the section."""
    from backend.quiz import note_writeback as wb

    note = tmp_path / "math" / "MT1_fence.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        "# MT1\n\n"
        "## `MT1-T02` — LCM\n\n"
        "Intro.\n\n"
        "```python\n"
        "# comment\n"
        "## fake heading inside fence\n"
        "print(1)\n"
        "```\n\n"
        "Still in section.\n\n"
        "## `MT1-T03` — Next\n\n"
        "Keep me.\n",
        encoding="utf-8",
    )
    wb.patch_note_section(
        note_path="math/MT1_fence.md",
        topic_id="MT1-T02",
        body_markdown=(
            "Replaced.\n\n```python\n## fake heading inside fence\nprint(2)\n```\n\nTail.\n"
        ),
        expected_mtime=note.stat().st_mtime,
        root=tmp_path,
    )
    text = note.read_text(encoding="utf-8")
    assert "Replaced." in text
    assert "Keep me." in text
    assert "## `MT1-T03`" in text
    assert text.index("Replaced.") < text.index("## `MT1-T03`")
    assert "## fake heading inside fence" in text


def test_writeback_mtime_conflict(tmp_path: Path):
    import pytest
    from backend.quiz import note_writeback as wb

    note = tmp_path / "math" / "MT1_mtime.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        "## `MT1-T02` — LCM\n\nOld.\n\n## `MT1-T03` — Next\n\nKeep.\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="mtime_conflict"):
        wb.patch_note_section(
            note_path="math/MT1_mtime.md",
            topic_id="MT1-T02",
            body_markdown="Nope.",
            expected_mtime=0.0,
            root=tmp_path,
        )
    assert "Old." in note.read_text(encoding="utf-8")
