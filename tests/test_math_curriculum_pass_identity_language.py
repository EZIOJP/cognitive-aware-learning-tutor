from backend.math.curriculum_pass.identity import make_question_id
from backend.math.curriculum_pass.language import decide_english


def test_id_from_source_pair_only():
    assert make_question_id("mathqa", "142") == "math.mathqa.142"
    assert "aptitude" not in make_question_id("mathqa", "142")
    assert make_question_id("mathqa", "142") != make_question_id("hendrycks", "142")


def test_explicit_language_skips_heuristic():
    keep, reason = decide_english(
        "これは日本語の長い問題文ですよ本当に", language_field="ja"
    )
    assert keep is False and reason == "explicit_non_en"


def test_short_stem_default_keep():
    keep, reason = decide_english("Solve: 3x+5=20", language_field=None)
    assert keep is True and reason == "short_keep"


def test_long_non_latin_script_drop():
    text = "これは数学の問題です。" * 5
    keep, reason = decide_english(text, language_field=None)
    assert keep is False and reason == "script_drop"
